"""Build dependency-only images; do not edit or execute the target on the host."""
import json,pathlib,subprocess,tomllib,hashlib
ROOT=pathlib.Path(__file__).resolve().parents[1]
repo=ROOT/'var/integrations/gmah-pr-gate'
out=ROOT/'var/gmah-images';out.mkdir(exist_ok=True)
lock=json.loads((ROOT/'integrations/toolchain.lock.json').read_text())
project=tomllib.loads((repo/'pyproject.toml').read_text())['project']
deps=project['dependencies']+project['optional-dependencies']['dev']+project['optional-dependencies']['rag']+['pytest-asyncio==1.2.0']
(out/'requirements.txt').write_text('\n'.join(deps)+'\n')
(out/'Dockerfile.api').write_text('FROM '+lock['python']['requested_tag']+'\nCOPY requirements.txt /requirements.txt\nRUN pip install --no-cache-dir -r /requirements.txt\n')
for name in ('package.json','package-lock.json'):(out/name).write_bytes((repo/'web'/name).read_bytes())
(out/'Dockerfile.web').write_text("FROM "+lock['node-base']['requested_tag']+"""
WORKDIR /deps
COPY package*.json ./
RUN npm ci --ignore-scripts
RUN node -e "const cp=require('child_process');const r=require('./node_modules/rollup/package.json').version;const e=require('./node_modules/esbuild/package.json').version;cp.execFileSync('npm',['install','--no-save','--package-lock=false','--ignore-scripts','@rollup/rollup-linux-arm64-musl@'+r,'@esbuild/linux-arm64@'+e],{stdio:'inherit'});"
""")
for key,file in [('gmah-api','Dockerfile.api'),('gmah-web','Dockerfile.web')]:
 tag='acceptance-'+key+':d026'
 with (out/(key+'.log')).open('w') as log:subprocess.run(['docker','build','--progress=plain','-f',str(out/file),'-t',tag,str(out)],stdout=log,stderr=subprocess.STDOUT,check=True)
 value=json.loads(subprocess.check_output(['docker','image','inspect',tag]))[0]
 lock[key]=dict(id=value['Id'],requested_tag=tag,recipe_sha256=hashlib.sha256((out/file).read_bytes()).hexdigest())
for key,tag in [('gmah-redis','redis:8-alpine'),('gmah-postgres','postgres:17-alpine')]:
 value=json.loads(subprocess.check_output(['docker','image','inspect',tag]))[0];lock[key]=dict(id=value['Id'],requested_tag=tag)
(ROOT/'integrations/toolchain.lock.json').write_text(json.dumps(lock,indent=2)+'\n')
print(json.dumps({k:v for k,v in lock.items() if k.startswith('gmah-')},indent=2))
