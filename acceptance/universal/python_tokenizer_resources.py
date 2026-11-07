"""Warm installed Tiktoken registry resources, using its public APIs and cache.

Each encoding runs in its own bounded process. A failed registry item does not
erase successful items or prevent the remaining resources from being prepared.
"""
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time


def cache_directory():
    configured=os.environ.get('TIKTOKEN_CACHE_DIR',os.environ.get('DATA_GYM_CACHE_DIR'))
    if configured=='':return None
    return Path(configured if configured is not None else Path(tempfile.gettempdir())/'data-gym-cache')


def files(directory):
    rows=[]
    if directory is None or not directory.is_dir():return rows
    root=directory.resolve()
    for file in sorted(directory.rglob('*')):
        if file.is_symlink() or not file.is_file() or not file.resolve().is_relative_to(root):continue
        digest=hashlib.sha256()
        with file.open('rb') as stream:
            for chunk in iter(lambda:stream.read(1024*1024),b''):digest.update(chunk)
        rows.append(dict(path=str(file.relative_to(directory)),bytes=file.stat().st_size,sha256=digest.hexdigest()))
    return rows


def collect(timeout=180):
    try:version=importlib.metadata.version('tiktoken')
    except importlib.metadata.PackageNotFoundError:return dict(provider='tiktoken',state='not_installed',encodings=[],files=[])
    directory=cache_directory()
    if directory is None:return dict(provider='tiktoken',version=version,state='cache_disabled',encodings=[],files=[])
    try:
        import tiktoken
        names=tiktoken.list_encoding_names()
    except Exception as error:
        return dict(provider='tiktoken',version=version,state='error',error_type=type(error).__name__,encodings=[],files=[])
    if not names:return dict(provider='tiktoken',version=version,state='error',error_type='empty_registry',encodings=[],files=[])
    rows=[]
    for name in names:
        started=time.monotonic()
        try:
            result=subprocess.run([sys.executable,'-P',str(Path(__file__).resolve()),'--encoding',name],capture_output=True,text=True,timeout=timeout)
            item=json.loads(result.stdout)
            if not isinstance(item,dict):raise ValueError('invalid resource response')
            if result.returncode or item.get('name')!=name or item.get('state')!='ready':
                item=dict(name=name,state='error',error_type=item.get('error_type','resource_subprocess_failed'),exit_code=result.returncode)
            elif any(type(item.get(key)) is not int or item[key]<1 for key in ('n_vocab','probe_token_count')):
                item=dict(name=name,state='error',error_type='invalid_resource_response',exit_code=result.returncode)
        except subprocess.TimeoutExpired:item=dict(name=name,state='error',error_type='resource_timeout',timeout_seconds=timeout)
        except (OSError,ValueError) as error:item=dict(name=name,state='error',error_type=type(error).__name__)
        item['duration_ms']=round((time.monotonic()-started)*1000);rows.append(item)
    return dict(provider='tiktoken',version=version,state='ready' if all(x['state']=='ready' for x in rows) else 'partial',cache_directory=str(directory),encodings=rows,files=files(directory))


def one(name):
    try:
        import tiktoken
        encoding=tiktoken.get_encoding(name)
        return dict(name=name,state='ready',n_vocab=encoding.n_vocab,probe_token_count=len(encoding.encode('acceptance resource preparation')))
    except Exception as error:return dict(name=name,state='error',error_type=type(error).__name__)


if __name__=='__main__':
    report=one(sys.argv[2]) if len(sys.argv)==3 and sys.argv[1]=='--encoding' else collect()
    print(json.dumps(report,ensure_ascii=False,allow_nan=False))
    raise SystemExit(0 if report['state'] in {'ready','not_installed'} else 1)
