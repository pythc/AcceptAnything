"""Explain coverage gaps without turning guesses or tool failures into defects."""
import json
LABELS={'basis':'缺少依据','environment':'环境未就绪','platform':'平台能力不足','case':'用例契约问题','unclassified':'待分类'}


def classify(run,issues):
    tasks={t['id']:t for t in run.get('tasks',[])};result=[]
    for issue in issues:
        row=dict(issue);kind=row.get('kind');category=row.get('category');source=row.get('classification_source')
        if not category:
            if kind=='basis':category='basis'
            elif kind in {'adapter','entry','syntax-index','generation','service'}:category='platform'
            elif kind in {'manifest','dependency'}:category='environment'
            elif kind=='case':category='case'
            elif kind=='execution':
                task=tasks.get(row.get('source'),{})
                category='environment' if task.get('tool') in {'universal-prepare','universal-service','universal-fixture'} else 'unclassified'
                row['observations']=row.get('observations') or [{k:x[k] for k in ('name','status','message','detail') if k in x} for x in task.get('report',{}).get('tests',[]) if x['status'] in {'skipped','error'}]
                if task.get('tool') in {'universal-business','universal-fixture'} and row['observations']:
                    categories=[]
                    for observation in row['observations']:
                        try:categories.append(json.loads(observation.get('detail','')).get('gap_category'))
                        except (ValueError,AttributeError):categories.append(None)
                    if len(set(categories))==1 and categories[0] in LABELS:category=categories[0]
            else:category='unclassified'
            source='execution-stage' if kind=='execution' else 'contract-validation'
        row.update(category=category,category_label=LABELS.get(category,'待分类'),classification_source=source)
        result.append(row)
    return result
