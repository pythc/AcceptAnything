"""Generate the explicit calibration scope; synthetic defects never claim product defects."""
from pathlib import Path
import json
root=Path(__file__).resolve().parents[1];repo=root/'integrations/fixtures/multitool'
choices={'bandit':'py','ruff':'py','pytest':'py','pytest-allure':'py','coverage':'py','robot':'check.robot','pip-audit':'requirements.txt','checkov':'iac','eslint':'js/quality.js','spectral':'openapi.json','node-test':'js/arithmetic.test.mjs','npm-audit':'.','semgrep':'py','gitleaks':'.','trivy-config':'iac','trivy-fs':'.','syft-cyclonedx':'.','syft-spdx':'.','grype':'.','hadolint':'iac/Dockerfile','shellcheck':'script.sh','newman':'collection.json','schemathesis':'openapi.json'}
tasks=[dict(id=name,tool=name,target=target,timeout=240,network='registry' if name in {'pip-audit','npm-audit','trivy-fs','grype'} else 'none') for name,target in choices.items()]
for t in tasks:
    if t['tool'] in {'newman','schemathesis'}:t['service_script']='api-server.cjs' if t['tool']=='newman' else 'api-server.py'
rules=[]
for task in tasks:
    name=task['id'];metric='tests.failed' if name in {'pytest','pytest-allure','robot','node-test','newman','schemathesis'} else 'coverage.lines' if name=='coverage' else 'sbom.components' if name.startswith('syft') else 'findings.total'
    rules.append(dict(id=name,kind='metric',tasks=[name],metric=metric,operator='ge' if name=='coverage' or name.startswith('syft') else 'eq',threshold=1 if name=='coverage' or name.startswith('syft') else 0))
profile=dict(id='integration-calibration-v2',name='多工具集成校准 · 含已知缺陷',repository=str(repo),version='D014-v2',environment='Linux Docker · synthetic calibration',scope='合成输入校准扫描、报告和门禁；不代表产品缺陷',files=sorted(str(p.relative_to(repo)) for p in repo.rglob('*') if p.is_file()),tasks=tasks,rules=rules,exclusions=[dict(subject='真实邮箱、云账号、移动真机、商业平台',reason='不属于本地合成校准范围')])
(root/'integrations/profiles/calibration-v2.json').write_text(json.dumps(profile,ensure_ascii=False,indent=2)+'\n')
