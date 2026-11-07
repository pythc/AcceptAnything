import hashlib
import importlib.metadata
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
import pytest
from acceptance.universal import python_tokenizer_resources as provider


def test_absent_distribution_is_not_installed_or_downloaded(monkeypatch):
    def absent(name):raise importlib.metadata.PackageNotFoundError(name)
    monkeypatch.setattr(provider.importlib.metadata,'version',absent)
    assert provider.collect()['state']=='not_installed'


def test_each_registered_resource_is_independent_and_unbounded_in_count(tmp_path,monkeypatch):
    monkeypatch.setenv('TIKTOKEN_CACHE_DIR',str(tmp_path))
    monkeypatch.setattr(provider.importlib.metadata,'version',lambda name:'0.14.0')
    names=['timeout','bad']+[f'encoding-{i}' for i in range(55)]
    monkeypatch.setitem(sys.modules,'tiktoken',SimpleNamespace(list_encoding_names=lambda:names))
    calls=[]
    def run(argv,**kwargs):
        name=argv[-1];calls.append(name)
        if name=='timeout':raise subprocess.TimeoutExpired(argv,kwargs['timeout'])
        if name=='bad':return SimpleNamespace(returncode=0,stdout='[]')
        return SimpleNamespace(returncode=0,stdout=json.dumps(dict(name=name,state='ready',n_vocab=100,probe_token_count=3)))
    monkeypatch.setattr(provider.subprocess,'run',run)
    result=provider.collect(timeout=2)
    assert calls==names and result['state']=='partial'
    assert sum(x['state']=='ready' for x in result['encodings'])==55
    assert result['encodings'][0]['error_type']=='resource_timeout'


def test_cache_manifest_binds_bytes_and_does_not_follow_symlinks(tmp_path):
    cache=tmp_path/'cache';cache.mkdir();(cache/'vocabulary').write_bytes(b'original')
    private=tmp_path/'private';private.write_bytes(b'private-sentinel')
    (cache/'outside').symlink_to(private)
    result=provider.files(cache)
    assert result==[dict(path='vocabulary',bytes=8,sha256=hashlib.sha256(b'original').hexdigest())]
    (cache/'vocabulary').write_bytes(b'changed')
    assert provider.files(cache)[0]['sha256']!=result[0]['sha256']


def test_explicit_empty_cache_does_not_scan_the_current_directory(monkeypatch):
    monkeypatch.setenv('TIKTOKEN_CACHE_DIR','')
    monkeypatch.setattr(provider.importlib.metadata,'version',lambda name:'0.14.0')
    assert provider.cache_directory() is None and provider.files(None)==[]
    assert provider.collect()['state']=='cache_disabled'


def test_an_empty_installed_registry_is_not_reported_as_ready(tmp_path,monkeypatch):
    monkeypatch.setenv('TIKTOKEN_CACHE_DIR',str(tmp_path))
    monkeypatch.setattr(provider.importlib.metadata,'version',lambda name:'0.14.0')
    monkeypatch.setitem(sys.modules,'tiktoken',SimpleNamespace(list_encoding_names=lambda:[]))
    assert provider.collect()['state']=='error'
