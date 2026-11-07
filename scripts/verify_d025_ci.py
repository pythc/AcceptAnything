"""Real local Git + Bandit + OPA control for commit-bound CI receipts."""
from pathlib import Path
import json,subprocess,sys,uuid
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from acceptance.engine import ROOT,Store
from acceptance.integrations.store import IntegrationStore
from acceptance.ci import receipt
root=ROOT/'var/d025-ci'/uuid.uuid4().hex[:8];repo=root/'repo';repo.mkdir(parents=True)
def git(*args):return subprocess.check_output(['git','-C',str(repo),*args]).decode().strip()
git('init','-q');git('config','user.name','Acceptance synthetic control');git('config','user.email','control@example.invalid')
(repo/'app.py').write_text('answer=42\n');git('add','app.py');git('commit','-qm','clean control');first=git('rev-parse','HEAD')
store=Store(root/'state');integrations=IntegrationStore(store.root/'integrations')
integrations.register(dict(id='ci-control',name='Commit-bound gate control',repository=str(repo),version='1',environment='isolated',scope='app.py Bandit',files=['app.py'],tasks=[dict(id='scan',tool='bandit')],rules=[dict(id='findings',kind='metric',tasks=['scan'],metric='findings.total',threshold=0)]))
def run():
    with integrations.lease():r=integrations.create('ci-control');return integrations.execute(r['id'])
clean=run();rows=[]
for label,r,revision,scope,code in [('clean',clean,first,'scoped',0),('scan-not-full',clean,first,'full',2),('wrong-commit',clean,'0'*40,'scoped',2)]:
    result=receipt(store,integrations,r['id'],revision,scope);assert result['exit_code']==code,result;rows.append(dict(label=label,**result))
(repo/'app.py').write_text('answer=43\n');dirty=run();result=receipt(store,integrations,dirty['id'],first,'scoped');assert result['exit_code']==2;rows.append(dict(label='dirty-source',**result))
(repo/'app.py').write_text('import subprocess\nsubprocess.call("echo synthetic",shell=True)\n');git('add','app.py');git('commit','-qm','negative control')
bad=run();result=receipt(store,integrations,bad['id'],git('rev-parse','HEAD'),'scoped');assert result['exit_code']==1;rows.append(dict(label='real-findings',**result))
(ROOT/'docs/design/d025/ci-controls.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2));print(json.dumps([{'label':r['label'],'exit_code':r['exit_code'],'decision':r['decision']} for r in rows]))
