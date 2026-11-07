"""Correct a proven locator fault, preserving the original model response and oracle."""
from pathlib import Path
import sys,json
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from acceptance.engine import ROOT
from acceptance.integrations.store import IntegrationStore
from acceptance.integrations.runner import sha
from acceptance.planning.provider import rebind_service
out=ROOT/'docs/design/d026'
original=json.loads((out/'table-browser-proposal.json').read_text())
trace=ROOT/'var/integrations/runs/int-22a9f379c9904bd3/outputs/generated-browser/browser/generated-test-C0005/error-context.md'
assert 'button "批 准"' in trace.read_text() and 'button "拒 绝"' in trace.read_text()
result=rebind_service(IntegrationStore(),original['id'],[dict(step=4,
    before='tr:has-text("${approval}") button:has-text("${action}")',
    after='tr:has-text("${approval}") >> xpath=.//button[translate(normalize-space(.), " ", "")="${action}"]'),
    dict(step=5,before='.ant-message-notice-content:has-text("已${action}")',after='[role="alert"]:has-text("已${action}")')],
    reason='浏览器实际 DOM 中 Ant Design 在双字中文按钮之间插入空格；仅对按钮文本匹配移除空格。录像证明成功提示已出现，Ant Design 6 改用 notice-title 和 role=alert；改用 role=alert 保留原提示文本断言。审批 ID、动作、状态断言、模型输入和预期不变。',
    evidence=dict(run_id='int-22a9f379c9904bd3',case_id='C0005',path=str(trace.relative_to(ROOT)),sha256=sha(trace.read_bytes()),toast_run='int-d748e1763bb04063',toast_trace='outputs/generated-browser/browser/generated-test-C0005/trace.zip',toast_frame='docs/design/d026/toast-locator-evidence.jpeg'))
(out/'table-browser-bound-proposal.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
print(result['id'])
