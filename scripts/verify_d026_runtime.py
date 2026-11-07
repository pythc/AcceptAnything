from pathlib import Path
import sys,json
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from acceptance.integrations.registry import ROOT,locks
from acceptance.integrations.models import Task
from acceptance.integrations.runner import execute
source=ROOT/'var/d026-runtime-preflight/source'
for tool in ('gmah-build','gmah-regression','gmah-performance','gmah-recovery'):
 out=ROOT/'var/d026-native'/tool;out.mkdir(parents=True,exist_ok=True)
 try:
  report,command=execute(Task(id=tool,tool=tool,target='.',timeout=300,network='none'),source,out,locks()['gmah-api']['id'],lambda:False)
  print(json.dumps(dict(tool=tool,command=command,metrics=report['metrics'],tests=report['tests']),ensure_ascii=False),flush=True)
 except Exception as exc:print(json.dumps(dict(tool=tool,error=str(exc)),ensure_ascii=False),flush=True)
