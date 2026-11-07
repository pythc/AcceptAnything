"""Configure the acceptance-owned gateway without interrupting the shared 5006 service."""
import json,subprocess,pathlib,sys,os
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from acceptance.planning import calls
from acceptance.integrations.store import IntegrationStore
name='acceptance-gmah-planner';config_path=ROOT/'var/planner-connection-gmah.json'
os.environ['ACCEPTANCE_PLANNER_CONFIG_FILE']=str(config_path)
store=IntegrationStore();calls.reconcile(store)
assert not calls.pending(store),'Do not interrupt a pending/unknown model request'
current=json.loads(subprocess.check_output(['docker','inspect',name]))[0]
assert current['Config']['Labels'].get('acceptance.planner')=='true'
# An idle WS must leave time for the existing SSE resume and exact-branch readback.
# No retry or additional generation is enabled.
settings={'AUTO_CONTINUE_TIMEOUT':'600','CONVERSATION_TIMEOUT':'90','WEBSOCKET_IDLE_TIMEOUT':'15','RETRY_TIMES':'0','AUTO_CONTINUE':'false','AUTO_CONTINUE_MAX_ROUNDS':'0','SCHEDULED_REFRESH':'false'}
subprocess.run(['docker','stop','-t','5',name],check=True,capture_output=True)
subprocess.run(['docker','rm',name],check=True,capture_output=True)
args=['docker','run','-d','--name',name,'--label','acceptance.planner=true','--restart','unless-stopped','-p','127.0.0.1:5007:5005',
 '--env-file','/Users/alex/.local/share/chat2api/diagnostic-private/request-scope-diag.env','--entrypoint',current['Config']['Entrypoint'][0]]
for k,v in settings.items():args+=['-e',k+'='+v]
for m in sorted(current['Mounts'],key=lambda x:len(x['Destination'])):args+=['--mount',f'type=bind,src={m["Source"]},dst={m["Destination"]}'+('' if m['RW'] else ',readonly')]
args += [current['Image'],*current['Config']['Entrypoint'][1:],*current['Config']['Cmd']]
r=subprocess.run(args,capture_output=True,text=True);assert r.returncode==0,r.stderr
(ROOT/'docs/design/d026/gateway.json').write_text(json.dumps(dict(name=name,image=current['Image'],port=5007,settings=settings,previous_gateway_unchanged=True),indent=2))
print('Acceptance-owned gateway configured; shared gateway unchanged.')
# Wait for this process to accept HTTP before returning to a caller.
import time,httpx
for _ in range(100):
 try:
  httpx.get('http://127.0.0.1:5007/',timeout=1,trust_env=False)
  break
 except httpx.HTTPError:time.sleep(.2)
else:raise RuntimeError('Gateway process did not become ready')
