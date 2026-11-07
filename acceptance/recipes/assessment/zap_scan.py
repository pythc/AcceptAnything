"""Bounded OWASP ZAP active/passive scan against this disposable app only."""
import json
import os
import subprocess
import time
import base64
import hashlib
import urllib.request
from pathlib import Path
from zapv2 import ZAPv2

target = 'http://127.0.0.1:5380'
process = subprocess.Popen(['zap.sh', '-daemon', '-host', '127.0.0.1', '-port', '8090',
    '-config', 'api.disablekey=true', '-config', 'connection.timeoutInSecs=5',
    '-config', 'autoupdate.checkOnStart=false'], stdout=open('/tmp/zap-start.log', 'w'), stderr=subprocess.STDOUT)
zap = ZAPv2(proxies={'http': 'http://127.0.0.1:8090', 'https': 'http://127.0.0.1:8090'})
def wait_for(fn, seconds):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        try:
            if fn(): return
        except Exception: pass
        time.sleep(1)
    raise RuntimeError('ZAP phase did not complete within its bound')
try:
    wait_for(lambda: bool(zap.core.version), 60)
    zap.context.new_context('acceptance')
    zap.context.include_in_context('acceptance', r'http://127\.0\.0\.1:5380(?:/.*)?')
    seeds = ['/login', '/register', '/api/health', '/api/batches', '/api/auth/me', '/api/admin/overview']
    for route in seeds: zap.core.access_url(target + route, followredirects=False)
    zap.spider.set_option_max_depth(2)
    zap.context.set_context_in_scope('acceptance', 'true')
    sid = zap.spider.scan(target + '/', maxchildren=10, contextname='acceptance')
    assert str(sid).isdigit(), f'ZAP spider rejected scope: {sid}'
    wait_for(lambda: zap.spider.status(sid) == '100', 90)
    zap.ascan.set_option_thread_per_host(2)
    zap.ascan.set_option_max_rule_duration_in_mins(1)
    zap.ascan.set_option_max_scan_duration_in_mins(2)
    plan = json.loads(Path('/recipe/zap-plan.json').read_text())
    zap.ascan.disable_all_scanners()
    zap.ascan.enable_scanners(','.join(plan['enabled_ids']))
    selected = sorted(str(x['id']) for x in zap.ascan.scanners() if str(x['enabled']).lower() == 'true')
    assert selected == sorted(plan['enabled_ids']), 'ZAP active rule plan differs'
    aid = zap.ascan.scan(target + '/', recurse=True, inscopeonly=True)
    assert str(aid).isdigit(), f'ZAP active scan rejected scope: {aid}'
    wait_for(lambda: zap.ascan.status(aid) == '100', 160)
    wait_for(lambda: int(zap.pscan.records_to_scan) == 0, 45)
    urls = sorted(u for u in zap.core.urls() if u.startswith(target + '/'))
    report = {'tool': 'OWASP ZAP', 'version': zap.core.version, 'target': target,
              'spider_status': zap.spider.status(sid), 'active_status': zap.ascan.status(aid),
              'pending_passive': int(zap.pscan.records_to_scan), 'urls': urls,
              'messages': int(zap.core.number_of_messages(baseurl=target)),
              'selected_rules': selected, 'excluded_rules': plan['excluded'],
              'active_progress': zap.ascan.scan_progress(aid), 'scan_limits': {'max_rule_minutes': 1, 'max_scan_minutes': 2},
              'diagnostics': [line for line in Path('/home/zap/.ZAP/zap.log').read_text().splitlines() if ' ERROR ' in line or ' WARN ' in line],
              'native_report': json.loads(zap.core.jsonreport())}
    # Preserve actual asset bytes for timestamp-like numeric matches. A number
    # in minified arithmetic is not evidence of sensitive date disclosure.
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *args, **kwargs):return None
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())
    report['timestamp_assets']=[]
    seen=set()
    for site in report['native_report'].get('site',[]):
        for alert in site.get('alerts',[]):
            if alert.get('pluginid')!='10096':continue
            for instance in alert.get('instances',[]):
                uri=instance['uri']
                if uri in seen or not uri.startswith(target+'/assets/') or not uri.endswith('.js'):continue
                seen.add(uri)
                try:
                    with opener.open(uri,timeout=5) as response:
                        body=response.read(1024*1024+1)
                    if len(body)>1024*1024:raise ValueError('asset exceeds bound')
                    report['timestamp_assets'].append(dict(uri=uri,sha256=hashlib.sha256(body).hexdigest(),body_base64=base64.b64encode(body).decode()))
                except Exception as exc:report['diagnostics'].append('Timestamp asset evidence unavailable: '+type(exc).__name__)
    print(json.dumps(report))
finally:
    try: zap.core.shutdown()
    except Exception: pass
    try: process.wait(timeout=15)
    except subprocess.TimeoutExpired: process.kill(); process.wait()
