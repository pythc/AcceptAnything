"""Preserve neutral SQLite protocol calibration; no third-party project recipe."""
import asyncio, hashlib, importlib.util, json, sys, tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from acceptance.universal import scenario,runtime
from acceptance.universal.scenarios import evaluate
spec=importlib.util.spec_from_file_location('stateful_tests',ROOT/'tests/test_stateful_protocol.py');tests=importlib.util.module_from_spec(spec);spec.loader.exec_module(tests)
out=ROOT/'docs/design/d039/calibration';out.mkdir(exist_ok=True)
with tempfile.TemporaryDirectory() as tmp:
 root=Path(tmp).resolve();tests.database(root);source=(root/'database.py').read_bytes();(out/'database.py').write_bytes(source)
 flow=tests.flow();request={k:flow[k] for k in ('steps','cleanup')}
 receipt=asyncio.run(scenario.execute(request,root))
 bad=json.loads(json.dumps(flow));bad['checks'][0]['expected']=[[7,'错误结果']]
 (out/'result.json').write_text(json.dumps(dict(source_sha256=hashlib.sha256(source).hexdigest(),source_unchanged=source==(root/'database.py').read_bytes(),request=request,receipt=receipt,positive=dict(flow=flow,result=evaluate(flow,receipt,runtime.compare,runtime.pointer)),negative=dict(flow=bad,result=evaluate(bad,receipt,runtime.compare,runtime.pointer))),ensure_ascii=False,indent=2))
 print('positive',evaluate(flow,receipt,runtime.compare,runtime.pointer)[0],'negative',evaluate(bad,receipt,runtime.compare,runtime.pointer)[0])
