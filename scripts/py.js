/**
 * Cross-platform launcher for the Python interpreter in api/.venv.
 * Never silently use global Python or the wrong Anaconda installation.
 *
 * Windows: api/.venv/Scripts/python.exe
 * macOS/Linux: api/.venv/bin/python
 * Usage: node scripts/py.js <python arguments...>
 */
const fs = require('node:fs');
const path = require('node:path');
const { spawn } = require('node:child_process');

const venv = path.resolve(__dirname, '..', 'api', '.venv');
const executable = process.platform === 'win32'
  ? path.join(venv, 'Scripts', 'python.exe')
  : path.join(venv, 'bin', 'python');

if (!fs.existsSync(executable)) {
  console.error(`GridLite's Python environment is missing: ${executable}`);
  console.error(process.platform === 'win32'
    ? 'Run: py -3.12 -m venv api/.venv'
    : 'Run: python3.12 -m venv api/.venv');
  console.error('Then install api/requirements.txt (see README.md).');
  process.exit(1);
}

const child = spawn(executable, process.argv.slice(2), { stdio: 'inherit' });
child.on('error', (error) => {
  console.error(`Could not start GridLite Python at ${executable}: ${error.message}`);
  process.exitCode = 1;
});

for (const signal of ['SIGINT', 'SIGTERM']) {
  process.on(signal, () => {
    // Windows doesn't support every POSIX signal; SIGTERM is supported by Node's
    // child_process.kill() on Windows. Ignore a child that already exited.
    if (child.exitCode === null && child.signalCode === null) {
      try { child.kill(process.platform === 'win32' ? 'SIGTERM' : signal); }
      catch (error) { console.error(`Stopping Python: ${error.message}`); }
    }
  });
}
child.on('close', (code, signal) => {
  if (!process.exitCode) process.exitCode = code ?? (signal ? 1 : 0);
});
