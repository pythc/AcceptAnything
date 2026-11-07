from copy import deepcopy
import pytest
from acceptance.planning.citations import locate,ground,verify_record
from acceptance.planning.models import Document,Specification


@pytest.mark.parametrize('source,quote,accepted',[
    ('before\n  the backend runs.','before\nthe backend runs.',True),
    ('before\nthe backend runs.','before\n  the backend runs.',True),
    ('before\n    code','before\ncode',False),
    ('before\n\tcode','before\ncode',False),
    ('before\n  a  b','before\na b',False),
    ('before\n  overwrites','before\nreplaces',False),
    ('before\n  **required**','before\nrequired',False),
    ('before\n  done\nbefore\n done','before\ndone',False),
    ('```\nx\n  y\n```','```\nx\ny\n```',False),
    ('`x\n  y`','`x\ny`',False),
])
def test_only_unambiguous_prose_continuation_indentation_can_resolve(source,quote,accepted):
    result=locate(source,quote)
    assert bool(result)==accepted
    if result:
        start,end,method=result
        assert source[start:end] in source and method=='line-wrap-indent-v1'


def test_exact_quotes_retain_their_existing_policy():
    assert locate('a literal\n    x','literal\n    x')==(2,15,'exact')


def test_citation_projection_preserves_steps_and_oracles_and_detects_tampering():
    doc=Document(id='D',title='契约',content='Returns\n  exactly 128.')
    spec=Specification.model_validate(dict(title='字段验收',scope='独立范围',requirements=[dict(
        id='R',title='字段',source='D',quote='Returns\nexactly 128.',scenarios=[dict(
            id='S',title='保留预期',engine='module',dimension='normal',steps=[dict(kind='call',module='x.py',function='f',assertions=[dict(value=128)])])])]))
    original=spec.model_dump();result,anchors,errors=ground(spec,[doc])
    assert not errors and result.requirements[0].quote==doc.content
    assert result.requirements[0].scenarios==spec.requirements[0].scenarios
    assert spec.model_dump()==original
    record=dict(specification=result.model_dump(),citation_specification=original,citations=anchors,documents=[doc.model_dump()])
    assert verify_record(record)
    changed=deepcopy(record);changed['specification']['requirements'][0]['scenarios'][0]['steps'][0]['assertions'][0]['value']=129
    assert not verify_record(changed)
    changed=deepcopy(record);changed['citations'][0]['start']=1
    assert not verify_record(changed)


def test_collect_all_missing_and_wrong_document_references():
    doc=Document(id='D',title='需求',content='这是独立的需求原文。')
    spec=Specification.model_validate(dict(title='需求验收',scope='独立范围',requirements=[dict(
        id='R'+str(i),title='待确认',source=s,quote='错误的原文引用',disposition='unresolved',reason='缺少入口') for i,s in enumerate(['D','UNKNOWN'])]))
    _,anchors,errors=ground(spec,[doc])
    assert not anchors and len(errors)==2
    assert errors[0]['document']=='需求' and errors[1]['reason']=='文档编号不存在'
