"""Download declared fixture wheels only. Run in a disposable registry container."""
import base64,hashlib,importlib.metadata,json,os,subprocess,sys
from pathlib import Path
from pip._vendor.packaging.requirements import Requirement
from pip._vendor.packaging.utils import canonicalize_name


def main(raw,root):
    request=json.loads(raw);root.mkdir(exist_ok=True)
    installed={canonicalize_name(d.metadata['Name']):d.version for d in importlib.metadata.distributions() if d.metadata.get('Name')}
    constraints=root/'constraints.txt';constraints.write_text(''.join(name+'=='+version+'\n' for name,version in sorted(installed.items())))
    wheels=root/'wheels';wheels.mkdir(exist_ok=True)
    receipt=dict(version=1,input_sha256=hashlib.sha256(raw).hexdigest(),state='error',installed=installed,commands=[],wheels=[],index='https://pypi.org/simple')
    try:
        for i,manifest in enumerate(request['manifests']):
            if not isinstance(manifest.get('name'),str) or not manifest['name']:receipt['gap_category']='platform';raise ValueError('缺少静态发行包名，不能证明夹具不会覆盖原环境')
            if manifest.get('name') and canonicalize_name(manifest['name']) in installed:receipt['gap_category']='case';raise ValueError('夹具名称与已安装发行包冲突，禁止覆盖原环境：'+manifest['name'])
            requirements=list(manifest['build'])
            for value in manifest['runtime']:
                req=Requirement(value)
                if req.marker and not req.marker.evaluate():continue
                version=installed.get(canonicalize_name(req.name))
                if version is None or not req.specifier.contains(version,prereleases=True):requirements.append(value)
            for value in requirements:
                req=Requirement(value)
                if req.url:raise ValueError('夹具依赖不接受直接 URL 或本地替换：'+req.name)
            if not requirements:continue
            file=root/('requirements-'+str(i)+'.txt');file.write_text('\n'.join(requirements)+'\n')
            argv=[sys.executable,'-m','pip','--isolated','download','--only-binary=:all:','--no-cache-dir','--index-url',receipt['index'],'--dest',str(wheels),'--constraint',str(constraints),'--requirement',str(file)]
            with (root/('pip-'+str(i)+'.stdout')).open('wb') as out,(root/('pip-'+str(i)+'.stderr')).open('wb') as err:p=subprocess.run(argv,stdout=out,stderr=err)
            receipt['commands'].append(dict(argv=argv,exit_code=p.returncode))
            if p.returncode:receipt['gap_category']='environment';raise ValueError('夹具依赖解析或 wheel 下载失败；已保留原始 pip 日志')
        for file in sorted(wheels.iterdir()):
            if not file.is_file():continue
            h=hashlib.sha256()
            with file.open('rb') as stream:
                for block in iter(lambda:stream.read(1024*1024),b''):h.update(block)
            digest=h.hexdigest()
            receipt['wheels'].append(dict(name=file.name,size=file.stat().st_size,sha256=digest))
        receipt['state']='ready'
    except Exception as exc:receipt['error']=type(exc).__name__+': '+str(exc)
    (root/'receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,sort_keys=True,indent=2));return receipt


if __name__=='__main__':
    receipt=main(base64.b64decode(sys.argv[1]),Path('/fixture-cache'));print(json.dumps(dict(state=receipt['state'],error=receipt.get('error')),ensure_ascii=False));sys.exit(0 if receipt['state']=='ready' else 1)
