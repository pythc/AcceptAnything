import http from 'k6/http';
import {check, sleep} from 'k6';
export const options = {
  vus: 5, duration: '20s', gracefulStop: '5s',
  thresholds: {checks: ['rate==1'], http_req_failed: ['rate==0'], iterations: ['count>=20']},
  summaryTrendStats: ['min', 'med', 'avg', 'p(90)', 'p(95)', 'max'],
};
export default function () {
  const health = http.get('http://127.0.0.1:5380/api/health', {timeout: '5s'});
  check(health, {'database healthy': r => r.status === 200 && r.json('database') === 'ok'});
  const batches = http.get('http://127.0.0.1:5380/api/batches', {timeout: '5s'});
  check(batches, {'batches readable': r => r.status === 200 && Array.isArray(r.json('rounds'))});
  sleep(0.2);
}
export function handleSummary(data) { return {'/report/summary.json': JSON.stringify(data)}; }
