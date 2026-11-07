"""Resolve local documentation evidence without importing or fetching target code.

README feature links select supporting sections; navigation is catalogued, not
silently promoted into a promise to verify every linked third-party product.
"""
import ast
import posixpath
import re
from pathlib import PurePosixPath
from urllib.parse import unquote, urlsplit
from ..integrations.runner import sha

TEXT={'.md','.mkd','.markdown','.rst','.txt'}
NAV={'documentation','documents','resources','ecosystem','support','team','license','contributing','donate','links','table of contents','文档','参考资料'}


def catalog(root,files):
    return [dict(path=n,sha256=sha((root/n).read_bytes()),characters=len((root/n).read_text(errors='replace')))
            for n in files if PurePosixPath(n).suffix.lower() in TEXT
            and (set(PurePosixPath(n).parts[:-1]) & {'docs','doc','documentation'}
                 or PurePosixPath(n).stem.lower() in {'readme','prd','requirements','contract','spec','specification'})
            and PurePosixPath(n).name!='requirements.txt']


def links(text):
    """Small, non-executing link inventory; ignore code fences and navigation."""
    scope=[];navigation=False;fenced=False
    for line in text.splitlines(keepends=True):
        if re.match(r'^\s*(```|~~~)',line):fenced=not fenced
        heading=re.match(r'^#{1,6}\s+(.+?)\s*#*\s*$',line)
        if heading:navigation=heading.group(1).strip().lower() in NAV
        if not fenced and not navigation and not line.lstrip().startswith('[![') and not re.search(r'\[full (?:CLI |library )?documentation\]',line,re.I):scope.append(line)
    body=''.join(scope)
    values=re.findall(r'\]\(([^\s)]+)(?:\s+[^)]*)?\)',body)
    values+=re.findall(r'href=[\"\']([^\"\']+)[\"\']',body)
    values+=re.findall(r'^\s*(?:\[[^\]]+\]:|\.\. _[^:\n]+:)\s*(\S+)',body,re.M)
    return list(dict.fromkeys(v.strip('<>') for v in values if not v.startswith('#')))


def origins(units):
    rows=[]
    for u in units:
        settings=u.get('settings',{});urls=settings.get('project',{}).get('urls',{})
        for k,v in urls.items():
            if k.lower() in {'documentation','docs'} and isinstance(v,str):rows.append(v.rstrip('/')+'/')
    ordered=sorted(set(rows),key=len)
    return [v for v in ordered if not any(v!=base and v.startswith(base) for base in ordered)]


def resolve(source,url,paths,bases):
    parsed=urlsplit(url);path=unquote(parsed.path);fragment=unquote(parsed.fragment)
    if '\\' in path or '\0' in path or parsed.query:return None
    candidates=set()
    if parsed.scheme or parsed.netloc:
        if parsed.scheme not in {'http','https'} or parsed.username or parsed.password:return None
        for base in bases:
            origin=urlsplit(base)
            if parsed.netloc!=origin.netloc or not path.startswith(origin.path):continue
            rel=path[len(origin.path):].rstrip('/')
            if not rel:rel='index'
            if rel.endswith('.html'):rel=rel[:-5]
            for folder in ('docs','doc','documentation'):
                for suffix in ('.rst','.md','/index.rst','/index.md'):
                    candidates.add(folder+'/'+rel+suffix)
    else:
        rel=posixpath.normpath(posixpath.join(str(PurePosixPath(source).parent),path))
        if rel.startswith('../') or rel.startswith('/'):return None
        candidates.add(rel)
        if not PurePosixPath(rel).suffix:
            candidates.update(rel+s for s in ('.rst','.md','/index.rst','/index.md'))
    found=sorted(candidates & paths)
    return (found[0],fragment) if len(found)==1 else None


def section(text,fragment,*,markdown=True):
    if not fragment:return 0,len(text)
    # RST labels and CommonMark-style heading slugs both bind exact source spans.
    lines=text.splitlines(keepends=True);offsets=[];offset=0;heads=[];labels={}
    levels={};fence=None
    for i,line in enumerate(lines):
        offsets.append(offset);offset+=len(line)
        marker=re.match(r'^ {0,3}(`{3,}|~{3,})',line) if markdown else None
        if marker:
            if fence is None:fence=marker.group(1)
            elif marker.group(1)[0]==fence[0] and len(marker.group(1))>=len(fence):fence=None
            continue
        if fence is not None:continue
        label=re.match(r'^\.\. _([^:]+):\s*$',line)
        if label:labels.setdefault(label.group(1),[]).append(offsets[-1])
        h=re.match(r'^(#{1,6})\s+(.+?)\s*#*\s*$',line)
        if h:heads.append((offsets[-1],len(h.group(1)),h.group(2)))
        elif i+1<len(lines) and line.strip() and re.fullmatch(r'([=~^"`:#*+\-])\1{2,}\s*',lines[i+1]):
            marker=lines[i+1].strip()[0];levels.setdefault(marker,len(levels)+1)
            heads.append((offsets[-1],levels[marker],line.strip()))
    def slug(title):return re.sub(r'\s+','-',re.sub(r'[^\w\s-]','',title.lower()))
    matches=[h for h in heads if slug(h[2])==fragment]
    if fragment in labels:
        if len(labels[fragment])!=1:return None
        start=labels[fragment][0];following=next((h for h in heads if h[0]>start),None)
        if not following:return start,len(text)
        bound=following
    elif len(matches)==1:start=matches[0][0];bound=matches[0]
    else:return None
    end=next((p for p,level,_ in heads if p>bound[0] and level<=bound[1]),len(text))
    return start,end


def toc(root,path,paths):
    """Follow explicit Sphinx toctree entries only; no guessed directory crawl."""
    result=[];active=False
    for line in (root/path).read_text().splitlines():
        if line.startswith('.. toctree::'):active=True;continue
        if active:
            if not line.strip():continue
            if not line.startswith((' ','\t')):active=False;continue
            value=line.strip()
            if value.startswith(':'):continue
            if '<' in value and value.endswith('>'):value=value.rsplit('<',1)[1][:-1]
            found=resolve(path,value,paths,[])
            if found:result.append(found)
    return result


def enrich(root,groups,inventory,units):
    """Keep primary scope and support roles separate; every selection is audited."""
    paths={d['path'] for d in inventory};bases=origins(units);result=[];receipts=[];number=0
    primary_groups=[]
    for group in groups:
        for part in group:
            if primary_groups and primary_groups[-1]['title']==part['title'] and len(primary_groups[-1]['content'])+len(part['content'])<=18000:
                prior=primary_groups[-1];prior['content']+=part['content'];prior['origin']=prior['origin'].split(':')[0]+':'+part['origin'].rsplit(':',1)[1]
            else:primary_groups.append(dict(part))
    for group in [primary_groups]:
        # One primary document per request keeps example/package scope distinct.
        for primary in group:
            selected=[];seen=set();entries=[]
            def add(path,fragment,via):
                key=(path,fragment)
                if key in seen:return
                seen.add(key);raw=(root/path).read_text();span=section(raw,fragment,markdown=not path.endswith('.rst'))
                if span is None:entries.append(dict(url=via,path=path,fragment=fragment,status='anchor_unresolved'));return
                start,end=span
                if primary['title']==path and primary['content']==raw[start:end]:return
                # Large sections are partitioned without dropping their tail.
                while start<end:
                    stop=min(end,start+5000)
                    if stop<end:
                        newline=raw.rfind('\n',start,stop)
                        if newline>start:stop=newline+1
                    selected.append(dict(title=path,origin=f'{path}#chars={start}:{stop}',content=raw[start:stop]));start=stop
                entries.append(dict(url=via,path=path,fragment=fragment,status='selected',span=list(span),sha256=sha((root/path).read_bytes())))
                if PurePosixPath(path).stem.lower()=='index' and not fragment:
                    for child,anchor in toc(root,path,paths):add(child,anchor,path)
            for url in links(primary['content']):
                found=resolve(primary['title'],url,paths,bases)
                if found:add(*found,url)
                else:entries.append(dict(url=url,status='not_local_or_ambiguous'))
            # Direct references in selected guidance may contain the missing
            # input/error contract. Retrieve them as context, not new scope.
            related={};reference_pool={}
            for doc in selected:
                related[doc['origin']]=set()
                for url in links(doc['content']):
                    found=resolve(doc['title'],url,paths,bases)
                    if not found or found[0]==primary['title']:continue
                    path,fragment=found;raw=(root/path).read_text();span=section(raw,fragment,markdown=not path.endswith('.rst'))
                    if span is None:continue
                    start,end=span
                    while start<end:
                        stop=min(end,start+5000)
                        if stop<end:
                            newline=raw.rfind('\n',start,stop)
                            if newline>start:stop=newline+1
                        origin=f'{path}#chars={start}:{stop}'
                        reference_pool.setdefault(origin,dict(title=path,origin=origin,content=raw[start:stop]))
                        related[doc['origin']].add(origin);start=stop
                    entries.append(dict(url=url,path=path,fragment=fragment,status='reference_context',via=doc['title'],span=list(span),sha256=sha((root/path).read_bytes())))
            # Bound each design job's output scope, not the repository size.
            # Every selected span is focused once. Other spans remain context
            # while the request budget permits; nothing is silently truncated.
            slices=[];current=[];size=0
            for doc in selected:
                if current and size+len(doc['content'])>8000:
                    slices.append(current);current=[];size=0
                current.append(doc);size+=len(doc['content'])
            if current or not slices:slices.append(current)
            for slice_index,focus in enumerate(slices):
                focus_origins={d['origin'] for d in focus}
                context=[];size=len(primary['content'])+sum(len(d['content']) for d in focus)
                wanted=set().union(*(related[d['origin']] for d in focus)) if focus else set()
                pool={d['origin']:d for d in [*selected,*reference_pool.values()]}
                ordered=sorted(pool.values(),key=lambda d:(d['origin'] not in wanted,d['origin'] not in {x['origin'] for x in selected}))
                for doc in ordered:
                    if doc['origin'] in focus_origins:continue
                    if size+len(doc['content'])<=45000:
                        context.append(doc);size+=len(doc['content'])
                docs=[dict(primary),*[dict(d) for d in focus],*[dict(d) for d in context]]
                for d in docs:number+=1;d['id']='D'+str(number)
                result.append(docs)
                receipt=dict(primary=[docs[0]['id']],support=[d['id'] for d in docs[1:]],links=entries)
                if len(slices)>1 or reference_pool:
                    receipt.update(focus=[d['id'] for d in docs[1:1+len(focus)]],
                        primary_review=slice_index==0,slice_index=slice_index,slice_count=len(slices),
                        context_omitted=[d['origin'] for d in ordered if d['origin'] not in {x['origin'] for x in docs}],
                        scope='Only current focus introduces support-derived requirements; other sections are context and have their own design jobs')
                receipts.append(receipt)
    return result,dict(version=3,budget=dict(focus_characters=8000,span_characters=5000,context_characters=45000,total_scope_limit=None),method='primary scope and linked evidence; all selected spans receive a bounded focus slice',catalog=inventory,batches=receipts)
