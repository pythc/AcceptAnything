"""Real generic project controls: same config, correct and intentionally faulty fixtures.
These are calibration fixtures, not three mature production projects.
"""
from pathlib import Path
import json,sys,uuid,time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from acceptance.engine import ROOT,Store
from acceptance.project_config import prepare
from acceptance.planning.service import create_run
from acceptance.integrations.store import IntegrationStore
from acceptance.jobs import Jobs

APP='''import http.server,json,os
items={}
class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def send(self,status,body,cookie=False,html=False):
        self.send_response(status)
        self.send_header('Content-Type','text/html; charset=utf-8' if html else 'application/json')
        if cookie:self.send_header('Set-Cookie','session=synthetic; HttpOnly; Path=/; SameSite=Strict')
        self.end_headers();self.wfile.write((body if html else json.dumps(body)).encode())
    def do_POST(self):
        if self.path=='/login':return self.send(200,{'role':'editor'},True)
        if self.headers.get('Cookie')!='session=synthetic':return self.send(403,{'error':'forbidden'})
        if self.path=='/items':
            value=json.loads(self.rfile.read(int(self.headers.get('Content-Length','0'))))
            key=str(len(items)+1);items[key]=value['name'];return self.send(201,{'id':key,'name':value['name']})
        self.send(404,{'error':'missing'})
    def do_GET(self):
        if self.path=='/health':return self.send(200,{'ready':True})
        key=self.path.removeprefix('/items/')
        if key in items:
            return self.send(200,'<h1 id="name">'+('WRONG' if BROKEN else items[key])+'</h1>',html=True)
        self.send(404,{'error':'missing'})
http.server.ThreadingHTTPServer(('0.0.0.0',int(os.environ['PORT'])),Handler).serve_forever()
'''
BASIS='匿名创建必须返回403。编辑者登录后可创建项目，接口返回201及项目编号；打开详情页面并刷新后必须显示创建时的名称。'


def configuration():
    return dict(schema_version=1,documents=[dict(id='PRD',path='产品说明.txt')],include_scanners=False,
        exclusions=[dict(subject='性能与恢复',reason='本次为 API 与浏览器联合执行器正负对照，不证明完整应用验收')],
        specification=dict(title='项目创建与页面读回',scope='合成数据：匿名权限负例、会话登录、接口创建及页面持久读回',environment=dict(mode='service',runtime='python',entrypoint='app.py'),requirements=[
          dict(id='AUTH',title='匿名创建拒绝',source='PRD',quote='匿名创建必须返回403。',scenarios=[dict(id='ANON',title='匿名不能创建',dimension='permission',engine='api',steps=[dict(kind='http',method='POST',path='/items',body={'name':'forbidden'},status=403,assertions=[dict(pointer='/error',value='forbidden')])])]),
          dict(id='CREATE',title='创建后页面一致',source='PRD',quote='编辑者登录后可创建项目，接口返回201及项目编号；打开详情页面并刷新后必须显示创建时的名称。',scenarios=[dict(id='FLOW',title='登录创建并读回页面',dimension='persistence',engine='browser',steps=[
            dict(kind='http',method='POST',path='/login',status=200,assertions=[dict(pointer='/role',value='editor')]),
            dict(kind='http',method='POST',path='/items',body=dict(name='验收-${run_id}'),status=201,assertions=[dict(pointer='/name',value='验收-${run_id}')],capture=dict(item='/id')),
            dict(kind='goto',value='/items/${item}'),dict(kind='expect_text',selector='#name',value='验收-${run_id}'),
            dict(kind='goto',value='/items/${item}'),dict(kind='expect_text',selector='#name',value='验收-${run_id}')])])]))


def main():
    root=ROOT/'var/d025-controls'/uuid.uuid4().hex[:8];root.mkdir(parents=True)
    store=IntegrationStore();jobs=Jobs(ROOT/'var/jobs');rows=[]
    for broken in (False,True):
        repo=root/('broken' if broken else 'correct');repo.mkdir()
        (repo/'app.py').write_text('BROKEN='+str(broken)+'\n'+APP)
        (repo/'产品说明.txt').write_text(BASIS)
        config=root/(repo.name+'.json');config.write_text(json.dumps(configuration(),ensure_ascii=False))
        plan=prepare(store,str(repo),str(config));run=create_run(store,plan['id'],plan['digest'])
        job=jobs.enqueue('integration',run['id']);rows.append(dict(run_id=run['id'],job_id=job['id'],expected='reject' if broken else 'allow'))
    deadline=time.monotonic()+180
    while time.monotonic()<deadline:
        if all(jobs.read(row['job_id'])['state'] not in {'queued','running'} for row in rows):break
        time.sleep(1)
    for row in rows:
        run=store.snapshot(row['run_id']);row.update(status=run['status'],decision=run['decision'],integrity=run['integrity'],
            tasks=[dict(id=t['id'],state=t['state'],error=t.get('error'),tests=t.get('report',{}).get('metrics',{})) for t in run['tasks']])
        assert run['status']=='completed' and run['decision']==row['expected'] and run['integrity'],row
    (ROOT/'docs/design/d025/business-controls.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2))
    print(json.dumps(rows,ensure_ascii=False))
if __name__=='__main__':main()
