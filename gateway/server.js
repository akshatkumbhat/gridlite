/**
 * GridLite gateway (Node.js + Express)
 *
 * The browser only ever talks to this server. Its jobs:
 *   1. Forward every /api/* request to the Flask data service.
 *   2. Log every request (method, path, status, time taken).
 *   3. Report whether both services are up (GET /api/health).
 *   4. In production, serve the built React app, so the whole tool runs on one port.
 *
 * Flask is never exposed to the browser, so later we can add login, rate
 * limits or caching here without touching the data code.
 */

const fs = require('fs');
const path = require('path');
const express = require('express');
const morgan = require('morgan');
const { createProxyMiddleware } = require('http-proxy-middleware');

const PORT = Number(process.env.PORT || 4000);
// 127.0.0.1 instead of "localhost": Node 17+ may resolve localhost to IPv6 (::1),
// while Flask listens on IPv4.
const FLASK_URL = process.env.FLASK_URL || 'http://127.0.0.1:5001';
const WEB_DIST = path.join(__dirname, '..', 'web', 'dist');

const app = express();

// 2. Request logging, e.g. "PATCH /api/tables/x.csv/rows/3 200 - 412.3 ms"
app.use(morgan(':date[iso] :method :url :status - :response-time ms'));

// 3. Health check. Answered by Node itself, so it works even when Flask is down.
app.get('/api/health', async (req, res) => {
  let flask = 'down';
  try {
    const r = await fetch(`${FLASK_URL}/api/health`, { signal: AbortSignal.timeout(2000) });
    if (r.ok) flask = 'ok';
  } catch {
    // Flask not reachable; reported below.
  }
  res.status(flask === 'ok' ? 200 : 503).json({ gateway: 'ok', flask });
});

// 1. Everything else under /api goes to Flask unchanged (uploads and downloads
// are streamed, so no body parser is used before this line).
app.use(
  createProxyMiddleware({
    target: FLASK_URL,
    pathFilter: '/api',
    on: {
      error: (err, req, res) => {
        console.error(`Proxy error for ${req.method} ${req.url}: ${err.code || err.message}`);
        if (!res.headersSent) {
          res.writeHead(502, { 'Content-Type': 'application/json' });
        }
        res.end(JSON.stringify({ error: `Data service (Flask) is not reachable at ${FLASK_URL}. Is it running?` }));
      },
    },
  })
);

// 4. Serve the built React app if it exists (after `npm run build` in web/).
if (fs.existsSync(WEB_DIST)) {
  app.use(express.static(WEB_DIST));
  app.get(/^(?!\/api\/).*/, (req, res) => res.sendFile(path.join(WEB_DIST, 'index.html')));
}

// Local-only tool with no authentication: never expose the gateway to the LAN.
app.listen(PORT, '127.0.0.1', () => {
  console.log(`GridLite gateway on http://127.0.0.1:${PORT}  ->  Flask at ${FLASK_URL}`);
  if (fs.existsSync(WEB_DIST)) console.log(`Serving the built web app from ${WEB_DIST}`);
});
