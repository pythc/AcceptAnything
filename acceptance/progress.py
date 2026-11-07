"""Observed execution state, separate from validated final assertions."""
from contextlib import contextmanager
from time import monotonic


@contextmanager
def checks(store, run, criteria):
    from .engine import now
    started = monotonic()
    rows = []
    for criterion in criteria:
        row = dict(criterion_id=criterion['id'], status='running', started_at=now(),
                   finished_at=None, duration_ms=None, batch=len(criteria) > 1)
        run.setdefault('check_runs', []).append(row)
        rows.append(row)
    store.save(run)
    try:
        yield
    finally:
        for row in rows:
            result = next((r for r in run['results'] if r['criterion_id'] == row['criterion_id']), None)
            row.update(status=result['status'] if result else 'error', finished_at=now(),
                       duration_ms=round((monotonic() - started) * 1000, 2))
        store.save(run)


def register_cases(store, run):
    from .engine import encode, case_plans
    from .validation import require
    criteria = run['baseline']['criteria']
    plans = case_plans(run)
    require(len({c['id'] for c in criteria}) == len(criteria), '重复验收标准编号')
    require(len({c['case_id'] for c in criteria}) == len(criteria), '重复测试用例编号')
    require(set(plans) == {c['id'] for c in criteria}, '标准与用例计划未完整对应')
    for c in criteria:
        require(c['expected'].strip() and c['executor'] and c['layer'] in ('L1','L2','L3','L4'), '缺少预期、执行器或层级')
        require(plans[c['id']]['subject'] and plans[c['id']]['steps'], '用例缺少主题或步骤')
    record = dict(baseline_digest=run['baseline']['digest'], target_digest=run['target_digest'],
                  criteria=criteria, plans=plans, exclusions=run['baseline'].get('exclusions', []))
    run['case_registration_ref'] = store.artifact(run, 'case-registration.json', encode(record), media_type='application/json')
    store.save(run)


def activity(store, run, name):
    from .engine import now
    run['current_activity'] = dict(name=name, started_at=now(), finished_at=None)
    store.save(run)


def end_activity(store, run):
    from .engine import now
    if run.get('current_activity'):
        run['current_activity']['finished_at'] = now()
        store.save(run)
