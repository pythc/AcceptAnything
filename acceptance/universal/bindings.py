"""Public APIs of declared local Python packages installed into the same unit."""
from ..integrations.formats import require


def context(units):
    return dict(version=1,python_dependencies={u['id']:list(dict.fromkeys(u.get('local_dependencies',[]))) for u in units if u['runtime']=='python'})


def accessible(target,unit,projection_context=None):
    rows={u['id']:u for u in target['units']}
    require(unit in rows,'调用组件不存在')
    if not projection_context or rows[unit]['runtime']!='python':return {unit}
    require(projection_context.get('version')==1,'公开依赖绑定版本不支持')
    deps=projection_context.get('python_dependencies',{}).get(unit,[])
    require(isinstance(deps,list) and all(isinstance(x,str) and x in rows and rows[x]['runtime']=='python' for x in deps),'公开依赖绑定包含未声明组件')
    # Preparation explicitly installs direct local packages from frozen paths.
    # Transitive resolver choices are not assumed to be the same source package.
    return {unit,*deps}
