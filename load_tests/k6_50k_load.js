import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate } from 'k6/metrics';
const cacheHit = new Rate('cache_hit');
// Spec script (Blueprint Gate 15/16). Tier selection via env: TIER=5k|10k|50k ; THINK=<seconds>; BASE=http://localhost:8000
const TIERS = {
  '1k':  [{ duration: '10s', target: 1000 },  { duration: '30s', target: 1000 },  { duration: '5s', target: 0 }],
  '5k':  [{ duration: '20s', target: 5000 },  { duration: '40s', target: 5000 },  { duration: '5s', target: 0 }],
  '10k': [{ duration: '30s', target: 10000 }, { duration: '40s', target: 10000 }, { duration: '5s', target: 0 }],
  '50k': [{ duration: '2m', target: 10000 }, { duration: '3m', target: 50000 }, { duration: '5m', target: 50000 }, { duration: '2m', target: 0 }],
};
export const options = {
  stages: TIERS[__ENV.TIER || '1k'],
  thresholds: {
    http_req_duration: ['p(50)<250', 'p(95)<450', 'p(99)<600'],
    http_req_failed: ['rate<0.0005'],
    checks: ['rate>0.999'],
  },
  summaryTrendStats: ['avg', 'p(50)', 'p(95)', 'p(99)', 'max'],
};
const QUERIES = ['Verify batch LOT-88392 safety protocol and return triage status', 'What is the return policy?', 'How does approval work?', 'Summarize the SOP for cold chain'];
export default function () {
  const vu = __VU, tenant = `tenant_${vu % 50}`;
  const payload = JSON.stringify({ tenant_id: tenant, user_id: `user_${vu}`, query: `${QUERIES[__ITER % QUERIES.length]} v${Math.floor(Math.random() * parseInt(__ENV.VARIANTS || '400'))}` });
  const res = http.post(`${__ENV.BASE || 'http://localhost:8000'}/api/v1/agent/query`, payload,
    { headers: { 'Content-Type': 'application/json', 'X-Tenant-ID': tenant } });
  check(res, {
    'status is 200': (r) => r.status === 200,
    'latency within 200-600ms SLA': (r) => r.timings.duration <= 600,
    'no cross-tenant leak': (r) => r.status === 200 && r.json('tenant_id') === tenant,
  });
  if (res.status === 200) cacheHit.add(res.json('mode') === 'cache_hit');
  sleep(parseFloat(__ENV.THINK || '1'));
}
