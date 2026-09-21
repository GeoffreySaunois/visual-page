import assert from 'node:assert/strict';
import { test } from 'node:test';
import worker from '../deploy/gcp/proxy.js';

const origin = 'https://artefacts.saunois.xyz';
const backend = 'https://artefacts-example.a.run.app';

test('refuses alternate hosts and unsigned requests without contacting backend', async () => {
  const previous = globalThis.fetch;
  globalThis.fetch = () => { throw new Error('unexpected backend request'); };
  try {
    const wrongHost = await worker.fetch(new Request('https://example.workers.dev/'), { BACKEND_ORIGIN: backend });
    assert.equal(wrongHost.status, 404);
    const noIdentity = await worker.fetch(new Request(origin), { BACKEND_ORIGIN: backend });
    assert.equal(noIdentity.status, 401);
    assert.match(noIdentity.headers.get('Cache-Control'), /no-store/);
  } finally {
    globalThis.fetch = previous;
  }
});

test('preserves mutation body and identity, sanitizes forwarding, and never follows redirects', async () => {
  const previous = globalThis.fetch;
  globalThis.fetch = async (request, options) => {
    assert.equal(request.url, backend + '/api/documents/report-demo/shares?check=1');
    assert.equal(request.method, 'PUT');
    assert.equal(await request.text(), '{"role":"reader"}');
    assert.equal(request.headers.get('Cf-Access-Jwt-Assertion'), 'signed-identity');
    assert.equal(request.headers.get('Forwarded'), null);
    assert.equal(request.headers.get('X-Forwarded-Host'), 'artefacts.saunois.xyz');
    assert.equal(options.redirect, 'manual');
    return new Response(null, { status: 307, headers: { Location: backend + '/reports/report-demo', 'Cache-Control': 'public,max-age=3600' } });
  };
  try {
    const request = new Request(origin + '/api/documents/report-demo/shares?check=1', {
      method: 'PUT', body: '{"role":"reader"}',
      headers: { 'Cf-Access-Jwt-Assertion': 'signed-identity', Forwarded: 'host=evil.example' },
    });
    const response = await worker.fetch(request, { BACKEND_ORIGIN: backend });
    assert.equal(response.status, 307);
    assert.equal(response.headers.get('Location'), origin + '/reports/report-demo');
    assert.match(response.headers.get('Cache-Control'), /private, no-store/);
    assert.equal(response.headers.get('Cloudflare-CDN-Cache-Control'), 'no-store');
  } finally {
    globalThis.fetch = previous;
  }
});
