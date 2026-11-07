"""Verify a completed run against an exact commit; exports GitHub Checks payload."""
import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from acceptance.engine import Store
from acceptance.integrations.store import IntegrationStore
from acceptance.ci import receipt

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('run_id');p.add_argument('--revision',required=True)
    p.add_argument('--scope',choices=['full','scoped'],default='full')
    p.add_argument('--data',type=Path);p.add_argument('--output',required=True,type=Path)
    args=p.parse_args();store=Store(args.data) if args.data else Store()
    result=receipt(store,IntegrationStore(store.root/'integrations'),args.run_id,args.revision,args.scope)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(result['decision']+': '+'；'.join(result['reasons']))
    return result['exit_code']
if __name__=='__main__':sys.exit(main())
