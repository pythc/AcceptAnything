"""Trusted CLI driver. Target bytes are data, never executable test source."""
import json
from decimal import Decimal
import subprocess
import time
from xml.etree.ElementTree import Element,SubElement,tostring
from pathlib import Path


def stream(value):
    def reject(value):raise ValueError('非标准 JSON 数值')
    decoder=json.JSONDecoder(parse_float=Decimal,parse_int=Decimal,parse_constant=reject);remaining=value.strip();result=[]
    while remaining:
        obj,end=decoder.raw_decode(remaining);result.append(obj);remaining=remaining[end:].strip()
    return result


def equal(actual,expected,comparison):
    if comparison=='json_stream':return typed_equal(stream(actual),stream(expected))
    if comparison=='contains':return expected in actual
    return actual==expected


def typed_equal(a,b):
    if type(a) is not type(b):return False
    if isinstance(a,list):return len(a)==len(b) and all(typed_equal(x,y) for x,y in zip(a,b))
    if isinstance(a,dict):return a.keys()==b.keys() and all(typed_equal(a[k],b[k]) for k in a)
    return a==b


def run(spec,execute=subprocess.run):
    suite=Element('testsuite',name='模型设计的独立业务验收');results=[];failed=0;execution_errors=0
    for requirement in spec['requirements']:
        for s in requirement['scenarios']:
            started=time.monotonic();execution_error=False
            case=SubElement(suite,'testcase',name=s['id']+' · '+s['title'],classname=requirement['id']);errors=[];row=dict(id=s['id'],title=s['title'],basis=requirement['quote'])
            try:
                proc=execute(['/app',*s['argv']],input=s['stdin'],capture_output=True,text=True,timeout=15)
                row.update(stdout=proc.stdout,stderr=proc.stderr,exit_code=proc.returncode)
                if s['exit_code'] is not None and proc.returncode!=s['exit_code']:errors.append('退出码与独立预期不符')
                if s['stdout']:
                    try:
                        if not equal(proc.stdout,s['stdout'],s['comparison']):errors.append('标准输出与独立预期不符')
                    except ValueError:errors.append('标准输出不是预期的合法 JSON')
                if s['stderr_contains'] and s['stderr_contains'] not in proc.stderr:errors.append('错误输出缺少预期内容')
            except Exception as exc:execution_error=True;errors.append('执行异常：'+type(exc).__name__)
            duration=time.monotonic()-started;case.set('time',str(duration))
            row.update(status='error' if execution_error else 'failed' if errors else 'passed',errors=errors,expected=s,duration_ms=round(duration*1000));results.append(row)
            if errors:
                failed+=1;execution_errors+=int(execution_error)
                SubElement(case,'error' if execution_error else 'failure',message='；'.join(errors)).text=json.dumps(row,ensure_ascii=False)
    suite.set('tests',str(len(results)));suite.set('failures',str(failed-execution_errors));suite.set('errors',str(execution_errors))
    return suite,results,failed


if __name__=='__main__':
    spec=json.loads(Path('/cases.json').read_text());suite,results,failed=run(spec)
    Path('/output/report.xml').write_bytes(tostring(suite,encoding='utf-8'))
    Path('/output/cases.json').write_text(json.dumps(results,ensure_ascii=False,indent=2))
    raise SystemExit(1 if failed else 0)
