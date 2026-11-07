"""Compile frozen model responses again, preserving original oracle and provenance."""
import copy
import json
import uuid

from ..automatic import check_source
from ..integrations.formats import require
from ..integrations.registry import locks
from ..integrations.runner import encode,sha
from ..planning.models import Document
from .bindings import context


def prepare(store,rid):
    from . import service
    run=store.snapshot(rid)
    require(run['status']=='completed' and run['integrity'] and run.get('universal_plan'),'仅支持完整性有效且已结束的通用验收记录')
    old=run['universal_plan'];generation=run['universal_generation']
    require(not old.get('frozen_design_run'),'请从原始模型设计记录创建复验，避免隐藏多层来源')
    require(bool(generation['batches']) and sorted(b['index'] for b in generation['batches'])==list(range(len(old['batches']))) and all(b['state']=='completed' for b in generation['batches']),'原始模型设计为空或存在未完整结束的批次，需要重新设计')
    check_source(old)
    require(old['toolchain_digest']==sha(encode(locks())),'工具链已变化，需要重新识别并确认范围')
    p=copy.deepcopy(old);p.update(id='auto-'+uuid.uuid4().hex[:16],implementation_digest=service.implementation(),runtime_identity=service.runtime_identity(),projection_context=context(old['discovery']['units']),frozen_design_run=rid)
    if hasattr(store,'path') and (store.path(rid)/'run.json').is_file():p['frozen_parent_record_sha256']=sha((store.path(rid)/'run.json').read_bytes())
    validator=run.get('universal_drivers',{}).get('callback_contract.cjs')
    if validator:p['frozen_syntax_validator_sha']=sha(store.artifact_bytes_for_record(run,validator)[1])
    p['profile']['id']='local-universal-'+uuid.uuid4().hex[:12];p['profile']['name']+=' · 冻结设计复验'
    from .fixture_preparation import augment
    augment(p)
    design_ids={t['id'] for t in p['profile']['tasks'] if t['tool']=='universal-design'}
    for check in p['checks']:
        if check['id'] in design_ids:check.update(title='复核冻结设计 · '+check['id'].removeprefix('design-'),expected='保留原模型响应、独立原文、输入和预期，按当前平台重新校验并执行')
    folder=store.root/'automatic-plans';digest=sha(encode(p));(folder/(p['id']+'.json')).write_bytes(encode(dict(record=p,sha256=digest)))
    return service.public(p,digest)


def recompile(original,projection_context,source,model_output=None):
    from .generation import validate
    require(sha(encode(original['record']))==original['sha256'],'原模型草稿摘要不符')
    prior=original['record']
    require(not prior.get('recompiled_from'),'复验必须直接绑定原始模型草稿')
    if model_output is None:model_output=prior['model_output']
    require(model_output==prior['model_output'],'原响应正文与原草稿不一致')
    syntax=[]
    rows,issues,anchors=validate(model_output,[Document.model_validate(x) for x in prior['documents']],prior['target'],projection_context=projection_context,collect_syntax=syntax)
    record=copy.deepcopy(prior);record.update(id='draft-'+uuid.uuid4().hex[:16],requirements=rows,issues=issues,citations=anchors,projection_context=projection_context,recompiled_from={**source,'draft':prior['id'],'sha256':original['sha256']},syntax_evidence=syntax)
    return record


def load_draft(store,run,index):
    rid=run['universal_plan']['frozen_design_run'];p=run['universal_plan'];pinned=p.get('frozen_parent_record_sha256')
    if pinned:
        require(sha((store.path(rid)/'run.json').read_bytes())==pinned,'已复核的原始记录字节发生变化')
        # prepare() already verified this envelope. Hydrated payloads and each
        # selected raw artifact are still hash-checked; don't restart mutable
        # external validators merely to read the same frozen input.
        parent=store.read(rid)
        from ..integrations.discovery import manifest
        require(sha(encode(manifest(str(store.path(rid)/'source'),[x['path'] for x in parent['context']['files']])))==p['snapshot_digest'],'原始冻结源码字节发生变化')
        for artifact in parent['artifacts']:store.verified_artifact_path(parent,artifact['id'])
    else:parent=store.snapshot(rid)
    require(parent['status']=='completed' and (pinned or parent['integrity']),'原始验收证据失效')
    p=run['universal_plan'];require(parent['context']['snapshot_digest']==p['snapshot_digest'],'冻结设计不属于同一源码快照')
    previous=next(b for b in parent['universal_generation']['batches'] if b['index']==index)
    require(previous['state']=='completed','原始模型批次未完整结束')
    raw=store.artifact_bytes_for_record(parent,previous['draft_ref'])[1];original=json.loads(raw)
    source=dict(run=rid,batch=index,snapshot_digest=p['snapshot_digest'])
    copied={key:store.artifact_bytes_for_record(parent,previous[key+'_ref'])[1] for key in ['input','response','receipt']}
    model_output=json.loads(json.loads(copied['response'])['choices'][0]['message']['content'])
    record=recompile(original,p['projection_context'],source,model_output=model_output)
    folder=store.root/'drafts';folder.mkdir(exist_ok=True);(folder/(record['id']+'.json')).write_bytes(encode(dict(record=record,sha256=sha(encode(record)))))
    copied['original_draft']=raw;copied['draft']=encode(dict(record=record,sha256=sha(encode(record))))
    copied['format_retries']=[dict(entry=copy.deepcopy(attempt),raws={key:store.artifact_bytes_for_record(parent,attempt[key+'_ref'])[1] for key in ['model-calls','model-inputs','model-responses']}) for attempt in previous.get('format_retries',[])]
    return record,copied


def verify_original(original,derived,plan,model_output,*,syntax_validator_sha=None):
    from .generation import validate,legacy_tool_rejections
    from .service import requirement_defaults
    require(sha(encode(original['record']))==original['sha256'],'原始草稿摘要不符')
    prior=original['record'];source=derived['recompiled_from']
    if prior.get('syntax_evidence'):require(plan.get('frozen_syntax_validator_sha'),'原始语法回执缺少冻结校验器绑定')
    require(source['run']==plan['frozen_design_run'] and source['snapshot_digest']==plan['snapshot_digest'] and source['draft']==prior['id'] and source['sha256']==original['sha256'],'复验来源不属于冻结方案')
    # Only compilation outputs and the new identity/provenance may differ.
    changed={'id','requirements','issues','citations','projection_context','recompiled_from','syntax_evidence'}
    require({k:v for k,v in derived.items() if k not in changed}=={k:v for k,v in prior.items() if k not in changed},'复验改变了原模型输入、响应、业务输入或预期')
    require(model_output==prior['model_output'],'原响应正文与原草稿不一致')
    old_rejections=legacy_tool_rejections(prior);prior_syntax=prior.get('syntax_evidence')
    # The grammar is unchanged: the new compilation's source-bound AST receipt
    # can verify old accepted cases without starting another mutable process.
    # A historically refused case stays refused while checking the parent.
    if prior_syntax is None and 'syntax_evidence' in derived and all(e['receipt']['validator_sha256']==plan.get('frozen_syntax_validator_sha') for e in derived['syntax_evidence']):
        prior_syntax=[e for e in derived['syntax_evidence'] if (e['requirement'],e['case']) not in old_rejections]
    rows,issues,anchors=validate(model_output,[Document.model_validate(x) for x in prior['documents']],prior['target'],projection_context=prior.get('projection_context'),syntax_evidence=prior_syntax,validator_sha=plan.get('frozen_syntax_validator_sha'),tool_rejections=old_rejections)
    require(requirement_defaults(rows)==requirement_defaults(prior['requirements']) and issues==prior['issues'] and anchors==prior['citations'],'原始模型投影不一致')
    require(derived.get('projection_context')==plan['projection_context'],'复验公开依赖编译上下文不符')
    rows,issues,anchors=validate(model_output,[Document.model_validate(x) for x in derived['documents']],derived['target'],projection_context=plan['projection_context'],syntax_evidence=derived.get('syntax_evidence'),validator_sha=syntax_validator_sha,tool_rejections=legacy_tool_rejections(derived))
    require(requirement_defaults(rows)==requirement_defaults(derived['requirements']) and issues==derived['issues'] and anchors==derived['citations'],'复验改变了编译输出中的输入或预期')
    return rows,issues,anchors
