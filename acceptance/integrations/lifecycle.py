"""Evidence-bound reimport into DefectDojo OSS, not another finding database.

Sidecars hold connector receipts only. DefectDojo owns finding status/history.
A lost mutation response is deliberately unknown and never automatically retried.
"""
import fcntl
import json
from pathlib import Path
import uuid
from .runner import encode, sha
from .formats import require

SECURITY_FORMATS={'sarif','bandit','semgrep','gitleaks','trivy','grype','npm-audit','pip-audit','checkov','zap'}


def prepared(store, rid, task_id):
    run=store.snapshot(rid)
    require(run.get('integrity') and run['status']=='completed','执行或证据不完整，禁止同步关闭缺陷')
    require(run.get('mode')=='executor','导入报告不能冒充本平台完整执行')
    task=next((x for x in run['tasks'] if x['id']==task_id),None)
    require(task and task['state']=='completed' and task.get('report',{}).get('complete') is True,'任务没有完整终态')
    require(task['format'] in SECURITY_FORMATS,'此报告不属于已支持的安全发现格式')
    require(run.get('scope_digest') and run.get('context',{}).get('files'),'缺少可比较的扫描范围')
    require(task.get('report_ref'),'缺少原始报告')
    _,raw=store.artifact_bytes(rid,task['report_ref'])
    scope=sha(encode(dict(scope=run['scope_digest'],files=sorted(x['path'] for x in run['context']['files']),task=task_id,format=task['format'])))
    findings=[]
    for hit in task['report']['findings']:
        require(hit['severity']!='unknown','未知严重性需要复核，不能降为 Info 同步')
        findings.append(dict(title=hit['title'][:500],description=hit['detail'],
            severity={'info':'Info','unknown':'Info'}.get(hit['severity'],hit['severity'].capitalize()),
            unique_id_from_tool=sha(encode([task['tool'],hit['id']])),file_path=hit.get('path') or '',
            **({'line':hit['line']} if hit.get('line') else {}),
            references=f"验收记录 {rid}\n原始报告 {task['report_ref']}\nSHA-256 {sha(raw)}\n规则 {hit['rule']}"))
    return run,scope,dict(findings=findings)


class DojoLifecycle:
    def __init__(self, root):
        self.root=Path(root);self.root.mkdir(parents=True,exist_ok=True)

    def save(self,key,record):
        temp=self.root/(key+'.'+uuid.uuid4().hex+'.tmp')
        temp.write_bytes(encode(record));temp.replace(self.root/(key+'.json'))

    def publish(self,store,service,rid,task_id,engagement):
        require(service.kind=='defectdojo' and type(engagement) is int and engagement>0,'缺少有效的 DefectDojo 目标')
        run,scope,report=prepared(store,rid,task_id)
        key=sha(encode([service.url,engagement,run['context']['repository'],task_id]))
        with (self.root/(key+'.lock')).open('a') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX)
            path=self.root/(key+'.json')
            record=json.loads(path.read_bytes()) if path.exists() else dict(
                key=key,url=service.url,engagement=engagement,repository=run['context']['repository'],
                task_id=task_id,scope=scope,test_id=None,attempts=[])
            require(record['scope']==scope,'工具、规则、环境或文件范围变化；需要新 Engagement，禁止据此关闭旧缺陷')
            require(not any(x['state']!='confirmed' for x in record['attempts']),'之前写入结果未知；先在 DefectDojo 核对，不能自动重复写入')
            previous=next((x for x in record['attempts'] if x['run_id']==rid),None)
            if previous:return previous
            if record['test_id']:
                identity=service.request(f"api/v2/tests/{record['test_id']}/")
                require(identity.get('engagement')==engagement,'远端 Test 所属 Engagement 已变化')
            attempt=dict(run_id=rid,state='pending',snapshot=run['context']['snapshot_digest'],report_digest=sha(encode(report)),revision=run['context']['revision'])
            record['attempts'].append(attempt);self.save(key,record)
            try:
                response=service.dojo_import(encode(report),'Generic Findings Import',
                    test_id=record['test_id'],engagement=None if record['test_id'] else engagement,
                    close_old=bool(record['test_id']),commit=run['context']['revision'],build=rid)
                tid=response['test'];tid=tid['id'] if isinstance(tid,dict) else tid
                require(type(tid) is int and tid>0,'远端未返回 Test 身份')
                require(record['test_id'] in {None,tid},'重导入返回了其他 Test')
                record['test_id']=tid
                data=service.dojo_pull(tid)
                require(data['test'].get('engagement')==engagement,'回读目标不匹配')
                attempt.update(state='confirmed',response=response,findings=data['findings'],
                    test_url=service.url+f'test/{tid}',receipt_sha256=sha(encode(data)),receipt=data)
            except Exception:
                attempt['state']='unknown';self.save(key,record)
                raise
            self.save(key,record)
            return attempt

    def list(self, rid=None):
        output=[]
        for path in self.root.glob('*.json'):
            record=json.loads(path.read_bytes())
            if rid and not any(a['run_id']==rid for a in record['attempts']):continue
            output.append({k:record[k] for k in ('key','url','engagement','repository','task_id','test_id')} | dict(
                attempts=[{k:a[k] for k in ('run_id','state','snapshot','revision','test_url','findings') if k in a} for a in record['attempts']]))
        return output
