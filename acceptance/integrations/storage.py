"""Content-addressed, streamed JSON payloads; size is not an acceptance criterion."""
import hashlib,json,os,uuid
from pathlib import Path


def file_digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()


def write_json(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_name('.write-'+uuid.uuid4().hex);h=hashlib.sha256()
    try:
        with temporary.open('wb') as f:
            for chunk in json.JSONEncoder(ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False).iterencode(value):
                raw=chunk.encode();h.update(raw);f.write(raw)
            f.write(b'\n');h.update(b'\n')
        os.replace(temporary,path)
    finally:temporary.unlink(missing_ok=True)
    return h.hexdigest()


def compact(directory,record):
    """Payloads are independently hashed. Never rewrite historical raw reports."""
    directory=Path(directory)/'payloads';directory.mkdir(exist_ok=True)
    def put(value):
        temp=directory/('.payload-'+uuid.uuid4().hex)
        checksum=write_json(temp,value);target=directory/(checksum+'.json')
        if target.exists():temp.unlink()
        else:temp.replace(target)
        return {'$payload':checksum}
    result=dict(record)
    result['tasks']=[{**t,**({'report':put(t['report'])} if t.get('report') else {})} for t in record['tasks']]
    for key in ['finding_review','universal_plan','universal_generation']:
        if key in result:result[key]=put(result[key])
    return result


def expand(directory,record):
    def get(value):
        if not isinstance(value,dict) or set(value)!={'$payload'}:return value
        digest=value['$payload']
        if not isinstance(digest,str) or len(digest)!=64 or any(c not in '0123456789abcdef' for c in digest):raise ValueError('数据分片身份非法')
        p=Path(directory)/'payloads'/(digest+'.json')
        if p.is_symlink() or file_digest(p)!=digest:raise ValueError('数据分片摘要不一致')
        return json.loads(p.read_bytes())
    record['tasks']=[{**t,**({'report':get(t['report'])} if t.get('report') else {})} for t in record['tasks']]
    for key in ['finding_review','universal_plan','universal_generation']:
        if key in record:record[key]=get(record[key])
    return record
