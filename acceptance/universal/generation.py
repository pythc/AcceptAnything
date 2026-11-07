"""Independent row validation: keep valid work and make every rejected row a gap."""
import json
import re
import uuid
from pathlib import PurePosixPath
from .models import Case,Requirement,Proposal
from ..planning.citations import locate
from ..planning.verification import verified_connection
from ..integrations.runner import encode,sha
from ..integrations.formats import require
from .bindings import accessible


def legacy_tool_rejections(draft):
    """Preserve only an old, conservative tool rejection; never grant a pass.

    Older drafts did not keep parser stderr/timeout receipts. Their exact
    recorded refusal remains an observation, not proof a parser later passed.
    """
    from .callback_contract import UNAVAILABLE
    if 'syntax_evidence' in draft:return {}
    return {(x['requirement'],x['case']):x['reason'] for x in draft.get('issues',[]) if x.get('kind')=='case' and x.get('reason')==UNAVAILABLE and x.get('requirement') and x.get('case')}


def validate(output,documents,target,projection_context=None,*,syntax_evidence=None,collect_syntax=None,validator_sha=None,tool_rejections=None):
    rows=Proposal.model_validate(output).requirements
    docs={d.id:d for d in documents};units={u['id']:u for u in target['units']}
    allowed={(i['unit'],i['path'],f['name']) for i in target['interfaces'] for f in i['functions']}
    protocol_version=target.get('execution_contract',{}).get('version',0)
    def module_path(c):
        permitted=accessible(target,c.unit,projection_context)
        if any((uid,c.module,c.function) in allowed for uid in permitted):return c.module
        # A package import name is a locator, never an oracle. Resolve it only
        # when the static index proves one public file/function binding.
        matches=set()
        for i in target['interfaces']:
            if i['unit'] not in permitted or not any(f['name']==c.function for f in i['functions']):continue
            u=units[i['unit']];path=PurePosixPath(i['path']);relative=path.relative_to(u.get('path','.'))
            aliases=set()
            if u['runtime']=='python':
                parts=list(relative.parts)
                if parts[0]=='src':parts=parts[1:]
                parts[-1]=parts[-1].removesuffix('.py')
                if parts[-1]=='__init__':parts=parts[:-1]
                aliases.add('.'.join(parts))
            if u['runtime']=='node':
                export=u.get('settings',{}).get('exports') or u.get('settings',{}).get('main')
                if isinstance(export,str) and str(PurePosixPath(u.get('path','.'))/export)==i['path']:aliases.add(u['settings'].get('name'))
            if c.module in aliases:matches.add(i['path'])
        require(len(matches)==1,'调用入口不在公开语法索引中，或别名存在歧义')
        return matches.pop()
    valid=[];issues=[];anchors=[];ids=set();caseids=set();used=set();rejected=set()
    frozen=None if syntax_evidence is None else {(e['requirement'],e['case']):e['receipt'] for e in syntax_evidence}
    if frozen is not None:require(len(frozen)==len(syntax_evidence),'语法复核回执身份重复')
    tool_rejections=tool_rejections or {}
    def callbacks(quote,flow,case,check_returns):
        from .callback_contract import verify
        key=(label,case.id)
        if key in tool_rejections:rejected.add(key);raise ValueError(tool_rejections[key])
        receipt=None
        if frozen is not None:require(key in frozen,'缺少冻结的语法复核回执');receipt=frozen[key];used.add(key)
        def save(receipt):
            if collect_syntax is not None:collect_syntax.append(dict(requirement=label,case=case.id,receipt=receipt))
        verify(quote,flow,check_returns=check_returns,receipt=receipt,on_receipt=save,validator_sha=validator_sha)
    for index,raw in enumerate(rows):
        if not isinstance(raw,dict):
            issues.append(dict(kind='requirement',source='row-'+str(index+1),reason='模型返回非对象标准；本条未执行'));continue
        label=raw.get('id','row-'+str(index+1));doc=docs.get(raw.get('source'))
        try:
            require(label not in ids,'需求编号重复');ids.add(label)
            require(doc is not None,'文档编号不存在')
            found=locate(doc.content,raw.get('quote',''),rst_literal=protocol_version>=14 and doc.title.endswith('.rst'),rst_relative=protocol_version>=15,unique_exact=protocol_version>=15)
            require(found is not None,'引用不能在指定文档中唯一定位')
            start,end,method=found
            require(bool(re.search(r'[\u4e00-\u9fff]',raw.get('title',''))),'标题必须是中文')
            cases=[];case_issues_start=len(issues)
            for case_raw in raw.get('cases',[]):
                try:
                    c=Case.model_validate(case_raw,context={'protocol_version':protocol_version})
                    require(c.id not in caseids,'用例编号重复');caseids.add(c.id)
                    require(c.unit in units and c.kind in units[c.unit]['capabilities'],'执行组件或协议不可用')
                    require(bool(re.search(r'[\u4e00-\u9fff]',c.title)),'用例标题必须是中文')
                    if protocol_version<18:require(c.kind!='journey' and not c.requires,'本次冻结协议不支持浏览器流程和多服务依赖')
                    if c.requires:
                        known={n['id'] for n in units[c.unit].get('service_graph',{}).get('nodes',[])}
                        require(set(c.requires)<=known,'用例引用未发现的服务依赖')
                    if c.kind=='journey':
                        from .scenarios import validate_bindings
                        for step in [*c.journey.setup,*c.journey.cleanup]:
                            if step.module:step.module=module_path(c.model_copy(update=dict(module=step.module,function=step.export)))
                        validate_bindings(c.journey.preparation(),target,c.unit,projection_context=projection_context)
                        runtime=units[c.unit]['runtime']
                        require((runtime=='python' and c.journey.adapter in {'wsgi','asgi'}) or (runtime=='node' and c.journey.adapter=='node-listener'),'应用适配器与组件运行时不符')
                        if runtime=='node':
                            require(not any(s.kwargs for s in [*c.journey.setup,*c.journey.cleanup]),'JavaScript准备步骤不支持关键字参数')
                            callbacks(doc.content[start:end],c.journey.preparation(),c,True)
                        for step in c.journey.steps:
                            if step.action=='poll' and step.pointer=='/status' and type(step.expected) is int:
                                require(re.search(r'(?<![0-9])'+str(step.expected)+r'(?![0-9])',doc.content[start:end]),'轮询状态码缺少原文依据')
                        if protocol_version>=19:
                            from .journeys import validate_status_basis as browser_status_basis
                            browser_status_basis(c.journey,doc.content[start:end])
                    if protocol_version<13:require(c.comparison!='one_of' and not (c.flow and any(x.comparison=='one_of' for x in c.flow.checks)),'本次冻结协议不支持候选值断言')
                    if protocol_version<15:require(c.comparison!='json_schema','本次冻结协议不支持JSON Schema比较')
                    if c.comparison=='json_schema':
                        from .scenarios import validate_schema
                        validate_schema(c.expected)
                    if c.comparison=='one_of':require(isinstance(c.expected,list) and bool(c.expected),'one_of需要非空候选值数组')
                    if c.kind=='module':
                        c.module=module_path(c)
                        require(units[c.unit]['runtime']!='node' or not c.kwargs,'JavaScript不支持Python关键字实参')
                    if c.kind=='scenario':
                        from .scenarios import validate_bindings
                        for step in [*c.flow.steps,*c.flow.cleanup]:
                            if step.module and protocol_version>=4:step.module=module_path(c.model_copy(update=dict(module=step.module,function=step.export)))
                            require(step.op!='cli' or protocol_version>=4,'本次冻结协议不支持流程CLI')
                        validate_bindings(c.flow,target,c.unit,projection_context=projection_context)
                        if projection_context:
                            from .scenarios import validate_observation_checks
                            validate_observation_checks(c.flow)
                        if protocol_version>=15:
                            from .scenarios import validate_status_basis
                            validate_status_basis(c.flow,doc.content[start:end])
                        if protocol_version>=9:
                            # A constructor plus configuration reads cannot
                            # substantiate an unquoted architectural guarantee.
                            permitted=accessible(target,c.unit,projection_context)
                            classes={(i['path'],f['name']) for i in target['interfaces'] if i['unit'] in permitted for f in i['functions'] if f.get('kind')=='class'}
                            config_only=all(s.op in {'get','item'} or s.op=='call' and (s.instantiate or (s.module,s.export) in classes) for s in c.flow.steps)
                            if config_only:
                                steps={s.id:s for s in c.flow.steps}
                                require(all(steps[ch.step].op=='get' and re.search(r'(?<!\w)'+re.escape(steps[ch.step].member)+r'(?!\w)',doc.content[start:end]) for ch in c.flow.checks),'仅构造对象和读回配置，原文未说明被检查属性；不能据此证明架构、IO或上下文隔离')
                        if units[c.unit]['runtime']=='node':
                            require(not any(s.kwargs for s in [*c.flow.steps,*c.flow.cleanup]),'JavaScript流程不支持关键字参数')
                            if protocol_version>=7:
                                callbacks(doc.content[start:end],c.flow,c,protocol_version>=8)
                    if c.kind=='cli':
                        entries=list(units[c.unit].get('cli_commands',{})) or units[c.unit].get('entries',[])
                        require(c.entry in entries if c.entry else len(entries)==1,'CLI需要唯一或明确选定的已声明入口')
                        require(isinstance(c.expected,str) or c.comparison=='exit_code' and type(c.expected) is int and 0<=c.expected<=255,'CLI预期必须为字符串或明确退出码')
                    cases.append(c.model_dump(exclude=({'flow'} if c.kind!='scenario' else set())|({'journey'} if c.kind!='journey' else set())))
                except ValueError as exc:
                    issue=dict(kind='case',requirement=label,source=raw.get('source'),case=case_raw.get('id') if isinstance(case_raw,dict) else None,reason=str(exc)[:800])
                    from .callback_contract import SyntaxUnavailable
                    if isinstance(exc,SyntaxUnavailable):issue.update(category='platform',classification_source='syntax-tool')
                    issues.append(issue)
            proposed={**raw,'quote':doc.content[start:end],'cases':cases}
            if raw.get('disposition','required')=='required' and not cases:
                proposed.update(disposition='unresolved',reason='该需求没有经契约校验的可执行用例；具体原因见逐项诊断')
            r=Requirement.model_validate(proposed,context={'protocol_version':protocol_version})
            normalized=r.model_dump()
            if protocol_version<13:normalized.pop('gap_category',None)
            for c in normalized['cases']:
                if c['kind']!='journey':c.pop('journey',None)
                if protocol_version<18:c.pop('requires',None)
                if c['kind']!='scenario':c.pop('flow',None)
                elif protocol_version<15:
                    for step in [*c['flow']['steps'],*c['flow']['cleanup']]:step.pop('encoding',None)
                if c['kind']=='scenario' and protocol_version<4:
                    for step in [*c['flow']['steps'],*c['flow']['cleanup']]:
                        for key in ('entry','argv','stdin'):step.pop(key,None)
            valid.append(normalized)
            anchors.append(dict(requirement=r.id,source=r.source,document=doc.title,document_sha256=sha(doc.content.encode()),start=start,end=end,line=doc.content[:start].count('\n')+1,method=method,model_quote=raw['quote'],quote=r.quote))
            if r.disposition=='unresolved':
                issue=dict(kind='requirement',requirement=r.id,source=r.source,reason=r.reason)
                compiler_unresolved=bool(projection_context and raw.get('disposition','required')=='required' and not cases)
                if protocol_version>=13:issue.update(category=r.gap_category or 'unclassified',classification_source='contract-validation' if compiler_unresolved else 'model',document=doc.title)
                if compiler_unresolved:issue['category']='case'
                # Per-case rejections already explain this compiler-created
                # unresolved state. Do not count its summary as another gap.
                if not compiler_unresolved or len(issues)==case_issues_start:issues.append(issue)
        except (ValueError,TypeError) as exc:
            issue=dict(kind='requirement',requirement=label,source=raw.get('source'),reason=str(exc)[:800])
            if protocol_version>=14:issue.update(category='case',classification_source='contract-validation',document=doc.title if doc else None)
            issues.append(issue)
    require(frozen is None or used==set(frozen),'语法复核回执未全部用于原始用例')
    require(rejected==set(tool_rejections),'旧版工具拒绝没有对应的语法复核步骤')
    return valid,issues,anchors


def finish_draft(store,data,output,connection,raw,prompt,system,input_sha):
    require(verified_connection(connection),'模型来源或响应型号未核验')
    projection_context=data.universal_target.get('projection_context')
    syntax=[]
    rows,issues,anchors=validate(output,data.documents,data.universal_target,projection_context=projection_context,collect_syntax=syntax)
    record=dict(id='draft-'+uuid.uuid4().hex[:16],kind='universal-v1',repository=data.repository,documents=[d.model_dump() for d in data.documents],scope=data.scope,
        target=data.universal_target,model=connection['requested_model'],connection=connection,model_output=output,requirements=rows,issues=issues,citations=anchors,
        prompt_sha256=sha(encode(prompt)),response_sha256=sha(encode(raw)),input_sha256=input_sha,system=system,usage=raw.get('usage'),syntax_evidence=syntax)
    if projection_context is not None:record['projection_context']=projection_context
    folder=store.root/'drafts';folder.mkdir(exist_ok=True)
    (folder/(record['id']+'.json')).write_bytes(encode(dict(record=record,sha256=sha(encode(record)))))
    return record
