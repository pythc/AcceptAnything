"""Target-side invocation only. This file never receives expected results."""
import asyncio,base64,dataclasses,importlib,importlib.util,json,sys
from enum import Enum
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from python_imports import load

def json_value(value):
 if dataclasses.is_dataclass(value) and not isinstance(value,type):return dataclasses.asdict(value)
 if isinstance(value,Enum):return value.value
 try:
  from pydantic import BaseModel
 except ImportError:BaseModel=()
 if BaseModel and isinstance(value,BaseModel):
  return value.model_dump(mode='json') if hasattr(value,'model_dump') else json.loads(value.json())
 try:
  from pydantic.v1 import BaseModel as LegacyModel
 except ImportError:LegacyModel=()
 if LegacyModel and isinstance(value,LegacyModel):return json.loads(value.json())
 raise TypeError('Return value has no supported JSON representation')

request=json.loads(base64.b64decode(sys.argv[1]))
module=load(Path('/work/repo'),request['module'])
value=getattr(module,request['function'])(*request['args'],**request.get('kwargs',{}))
if asyncio.iscoroutine(value):value=asyncio.run(value)
print('\nACCEPTANCE_VALUE:'+json.dumps(value,default=json_value,allow_nan=False))
