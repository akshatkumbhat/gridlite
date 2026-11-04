import test from 'node:test';
import assert from 'node:assert/strict';
import { api } from '../src/api.js';

const mockFetch = async (callback) => {
  const original = globalThis.fetch;
  let request;
  globalThis.fetch = async (url, options) => {
    request = { url, options };
    return { ok: true, text: async () => JSON.stringify({ version: 'new' }) };
  };
  try {
    await callback();
    return request;
  } finally {
    globalThis.fetch = original;
  }
};

test('PATCH carries the version token that protects a row', async () => {
  const request = await mockFetch(() => api.updateCell('my file.csv', 4, 'name', 'Bob', 'abc123'));
  assert.equal(request.url, '/api/tables/my%20file.csv/rows/4');
  assert.equal(request.options.headers['If-Match'], 'abc123');
  assert.deepEqual(JSON.parse(request.options.body), { column: 'name', value: 'Bob' });
});

test('row addition and column addition include If-Match', async () => {
  const add = await mockFetch(() => api.addRow('people.csv', 'v1'));
  assert.equal(add.options.headers['If-Match'], 'v1');
  const column = await mockFetch(() => api.addColumn('people.csv', 'remarks', 'v2'));
  assert.equal(column.options.headers['If-Match'], 'v2');
});

test('DELETE includes If-Match', async () => {
  const deleteReq = await mockFetch(() => api.deleteRow('people.csv', 7, 'v3'));
  assert.equal(deleteReq.options.method, 'DELETE');
  assert.equal(deleteReq.options.headers['If-Match'], 'v3');
});

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
const testDir = path.dirname(fileURLToPath(import.meta.url));

test('unauthenticated gateway and development UI bind only to loopback', () => {
  const server = fs.readFileSync(path.join(testDir, '../../gateway/server.js'), 'utf8');
  const vite = fs.readFileSync(path.join(testDir, '../vite.config.js'), 'utf8');
  assert.match(server, /app\.listen\(PORT, '127\.0\.0\.1'/);
  assert.match(vite, /host:\s*'127\.0\.0\.1'/);
});
