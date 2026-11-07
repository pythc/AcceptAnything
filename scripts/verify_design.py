"""Real D020 calibration; outputs remain evidence, including failed attempts."""
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from acceptance.planning.models import DesignInput
from acceptance.planning.service import prepare,create_run
from acceptance.integrations.store import IntegrationStore

def calibration():
    root=ROOT/'docs/design/d020/calibration';root.mkdir(parents=True,exist_ok=True)
    for mode in ('fixed','buggy'):(root/mode).mkdir(exist_ok=True)
    source=(ROOT/'tests/fixtures/design_service.py').read_text()
    (root/'fixed/server.py').write_text(source)
    (root/'buggy/server.py').write_text(source.replace("{'status':'ok'}","{'status':123}").replace("return self.reply(401,{'error':'login required'})","return self.reply(200,{'error':'login required'})").replace("'已保存：'","'错误：'"))
    doc='匿名访问私有资源必须返回401。创建条目返回201及字符串id，按id读回得到200与原始名称。名称为空时返回400。页面填写名称并保存后显示已保存及该名称。健康接口返回200且status为字符串ok。'
    req=[]
    def add(id,title,quote,engine,dimension,steps,**kw):
        req.append(dict(id=id,title=title,source='PRD',quote=quote,scenarios=[dict(id=id+'-case',title=title,engine=engine,dimension=dimension,steps=steps,**kw)]))
    add('AUTH','匿名私有资源访问','匿名访问私有资源必须返回401。','api','permission',[dict(kind='http',path='/private',status=401)])
    add('CREATE','创建后按ID读回','创建条目返回201及字符串id，按id读回得到200与原始名称。','api','persistence',[
        dict(kind='http',method='POST',path='/items',body={'name':'synthetic-${run_id}'},status=201,assertions=[dict(pointer='/id',operator='schema',value={'type':'string','minLength':1})],capture={'id':'/id'}),
        dict(kind='http',path='/items/${id}',status=200,assertions=[dict(pointer='/name',value='synthetic-${run_id}')])])
    add('EMPTY','空名称拒绝','名称为空时返回400。','api','error',[dict(kind='http',method='POST',path='/items',body={'name':''},status=400)])
    add('PAGE','页面保存反馈','页面填写名称并保存后显示已保存及该名称。','browser','normal',[
        dict(kind='goto',value='/'),dict(kind='fill',selector='#name',value='验收样本'),dict(kind='click',selector='button'),dict(kind='expect_text',selector='#result',value='已保存：验收样本')])
    response={'description':'OK','content':{'application/json':{'schema':{'type':'object','required':['status'],'properties':{'status':{'type':'string','enum':['ok']}}}}}}
    schema={'openapi':'3.0.3','info':{'title':'Independent health contract','version':'1'},'paths':{'/health':{'get':{'responses':{'200':response}}}}}
    add('HEALTH','健康接口契约','健康接口返回200且status为字符串ok。','openapi','boundary',[],contract='openapi')
    return dict(repository=str(root/'fixed'),include_scanners=False,documents=[dict(id='PRD',title='独立校准标准',content=doc),dict(id='openapi',title='健康接口OpenAPI',content=json.dumps(schema))],specification=dict(title='生成用例校准 · 正确实现',scope='验证生成、执行与失败检出，合成服务非业务项目',environment=dict(mode='service',runtime='python',entrypoint='server.py'),requirements=req))

def run(mode):
    if mode=='assessment':
        data=json.loads((ROOT/'acceptance/planning/examples/assessment.json').read_text())
    else:
        data=calibration();data['repository']=str(Path(data['repository']).parent/mode)
        data['specification']['title']='生成用例校准 · '+('正确实现' if mode=='fixed' else '故意违反契约')
    store=IntegrationStore()
    with store.lease():
        p=prepare(store,DesignInput.model_validate(data));r=create_run(store,p['id'],p['digest'])
        print(json.dumps(dict(mode=mode,run=r['id'],cases=len(p['cases']))),flush=True)
        store.execute(r['id']);r=store.snapshot(r['id'])
    summary=dict(run=r['id'],mode=mode,status=r['status'],decision=r['decision'],integrity=r['integrity'],errors=r['errors'],
        requirements=len(p['coverage']),generated_cases=len(p['cases']),tasks=[dict(id=t['id'],state=t['state'],error=t.get('error'),metrics=t.get('report',{}).get('metrics'),tests=[dict(name=x['name'],status=x['status']) for x in t.get('report',{}).get('tests',[])]) for t in r['tasks']])
    (ROOT/'docs/design/d020'/f'{mode}-verification.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(summary,ensure_ascii=False),flush=True)
    return summary

if __name__=='__main__':run(sys.argv[1] if len(sys.argv)>1 else 'fixed')
