"""Explicit maintenance operation: resolve public releases, then freeze build inputs."""
from pathlib import Path
import json, urllib.request
root=Path(__file__).parent
py=['bandit','ruff','pip-audit','pytest','pytest-cov','allure-pytest','robotframework','schemathesis','checkov']
js=['eslint','@stoplight/spectral-cli','@stoplight/spectral-rulesets','newman']
def get(url):
    with urllib.request.urlopen(url,timeout=30) as r: return json.load(r)
(root/'requirements.in').write_text('\n'.join(p+'=='+get('https://pypi.org/pypi/'+p+'/json')['info']['version'] for p in py)+'\n')
(root/'package.json').write_text(json.dumps({'private':True,'dependencies':{p:get('https://registry.npmjs.org/'+p.replace('/', '%2f')+'/latest')['version'] for p in js}},indent=2)+'\n')
