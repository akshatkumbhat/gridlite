// Every HTTP call the app makes lives in this file.
// All URLs start with /api, which goes to the Node gateway (never to Flask directly).

const BASE = '/api';

async function request(path, options = {}) {
  let res;
  try {
    res = await fetch(BASE + path, options);
  } catch {
    throw new Error('Cannot reach the gateway. Is the Node server running on port 4000?');
  }
  const text = await res.text();
  let data = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    // not JSON (e.g. an HTML error page)
  }
  if (!res.ok) {
    throw new Error((data && data.error) || `Request failed (${res.status})`);
  }
  return data;
}

function json(method, body, version) {
  return {
    method,
    headers: { 'Content-Type': 'application/json', 'If-Match': version },
    body: JSON.stringify(body ?? {}),
  };
}

const t = (name) => `/tables/${encodeURIComponent(name)}`;

export const api = {
  health: () => request('/health'),
  listTables: () => request('/tables'),

  uploadTable: (file) => {
    const form = new FormData();
    form.append('file', file);
    return request('/tables', { method: 'POST', body: form });
  },

  getRows: (name, { page, pageSize, sort, order, search, searchColumn }) => {
    const params = new URLSearchParams({ page, page_size: pageSize });
    if (sort) params.set('sort', sort);
    if (sort) params.set('order', order);
    if (search) params.set('search', search);
    if (search && searchColumn) params.set('search_column', searchColumn);
    return request(`${t(name)}/rows?${params}`);
  },

  updateCell: (name, rowId, column, value, version) => request(`${t(name)}/rows/${rowId}`, json('PATCH', { column, value }, version)),
  addRow: (name, version) => request(`${t(name)}/rows`, json('POST', {}, version)),
  deleteRow: (name, rowId, version) => request(`${t(name)}/rows/${rowId}`, { method: 'DELETE', headers: { 'If-Match': version } }),
  addColumn: (name, column, version) => request(`${t(name)}/columns`, json('POST', { name: column }, version)),
  history: (name) => request(`${t(name)}/history`),

  downloadUrl: (name) => `${BASE}${t(name)}/download`,
};
