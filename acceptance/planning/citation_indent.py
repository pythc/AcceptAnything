"""Locate exact RST code excerpts with a recorded common indentation prefix."""
import re


def locate_rst_literal(text,quote,*,relative=False):
    if '\n' not in quote:return None
    matches=[];lines=text.splitlines(keepends=True);positions=[];pos=0
    for line in lines:positions.append(pos);pos+=len(line)
    for i,line in enumerate(lines):
        directive=re.match(r'^( *)\.\. (?:code-block|code)::\s*\S*\s*$',line.rstrip('\n'))
        if not directive:continue
        outer=len(directive.group(1));start=i+1
        while start<len(lines) and (not lines[start].strip() or lines[start].lstrip().startswith(':')):start+=1
        if start==len(lines):continue
        first=lines[start];base=len(first)-len(first.lstrip(' '))
        if base<=outer or '\t' in first[:base]:continue
        end=start
        while end<len(lines) and (not lines[end].strip() or len(lines[end])-len(lines[end].lstrip(' '))>=base):end+=1
        content=text[positions[start]:positions[end] if end<len(lines) else len(text)]
        # Exact relative indentation and every character within each code line.
        prefixes={base}
        first_quote=quote.splitlines()[0]
        if relative and first_quote.strip():
            quote_indent=len(first_quote)-len(first_quote.lstrip(' '))
            for candidate in content.splitlines():
                if candidate.lstrip(' ')==first_quote.lstrip(' '):
                    prefix=len(candidate)-len(candidate.lstrip(' '))-quote_indent
                    if prefix>=base:prefixes.add(prefix)
        for prefix in sorted(prefixes):
            decorated=''.join((' '*prefix+part if part.strip() else part) for part in quote.splitlines(keepends=True))
            for hit in re.finditer(re.escape(decorated),content):
                if hit.start() and content[hit.start()-1]!='\n':continue
                begin=positions[start]+hit.start();matches.append((begin,begin+len(decorated),'rst-relative-code-indent-v2' if prefix!=base else 'rst-literal-wrapper-indent-v1'))
    return matches[0] if len(matches)==1 else None
