"""Ground citations without fuzzy text matching or changing business oracles."""
import re
from ..integrations.runner import sha


def _multiline_code(text):
    # An inline literal spanning a newline must retain its significant whitespace.
    return '```' in text or '~~~' in text or any(
        '\n' in match.group() for match in re.finditer(r'(`+).*?\1',text,re.S))


def locate(text,quote,*,rst_literal=False,rst_relative=False,unique_exact=False):
    start=text.find(quote)
    if start>=0:
        if unique_exact and text.find(quote,start+1)>=0:return None
        return start,start+len(quote),'exact'
    if rst_literal:
        from .citation_indent import locate_rst_literal
        found=locate_rst_literal(text,quote,relative=rst_relative)
        if found:return found
    if '\n' not in quote or _multiline_code(quote):return None
    # Only indentation of Markdown continuation lines (0..3 ASCII spaces).
    # Internal spaces, tabs, punctuation, words and code indentation stay exact.
    parts=re.split(r'\n {0,3}(?! )',quote)
    if len(parts)<2:return None
    pattern=r'\n {0,3}(?! )'.join(re.escape(p) for p in parts)
    matches=list(re.finditer(pattern,text))
    if len(matches)!=1:return None
    match=matches[0];span=match.group()
    if _multiline_code(span):return None
    return match.start(),match.end(),'line-wrap-indent-v1'


def ground(spec,documents):
    """Return an exact-source spec, auditable locators and every invalid reference."""
    canonical=spec.model_copy(deep=True)
    docs={d.id:d for d in documents};anchors=[];errors=[]
    for req in canonical.requirements:
        doc=docs.get(req.source)
        found=locate(doc.content,req.quote) if doc else None
        if found is None:
            errors.append(dict(requirement=req.id,source=req.source,
                document=doc.title if doc else None,quote=req.quote,
                reason='文档编号不存在' if doc is None else '引用无法在该文档中唯一定位；没有改写或跳过'))
            continue
        start,end,method=found;original=req.quote
        req.quote=doc.content[start:end]
        anchors.append(dict(requirement=req.id,source=req.source,document=doc.title,
            document_sha256=sha(doc.content.encode()),start=start,end=end,
            line=doc.content[:start].count('\n')+1,method=method,
            model_quote=original,quote=req.quote))
    return canonical,anchors,errors


def verify_record(record):
    """Reproduce citation-only changes; expected values and steps cannot change."""
    if 'citation_specification' not in record:return True  # Historical drafts.
    from .models import Specification,CliSpecification,Document
    schema=CliSpecification if record['specification']['environment']['mode']=='cli' else Specification
    spec=schema.model_validate(record['citation_specification'])
    projected,anchors,errors=ground(spec,[Document.model_validate(d) for d in record['documents']])
    return not errors and anchors==record['citations'] and projected.model_dump()==record['specification']
