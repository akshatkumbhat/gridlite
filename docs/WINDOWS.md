# GridLite on Windows 10/11 — developer setup and verification

The project ZIP includes no installed dependencies. **Do not copy a Mac `.venv` or
`node_modules` into Windows.** Build these independently on each computer.

## 1. Check prerequisites

In a new PowerShell window:

```powershell
node --version        # expected v24.x
npm --version
py -3.12 --version    # expected Python 3.12
```

Install Node.js **24** from https://nodejs.org/, Python **3.12** from
https://www.python.org/downloads/ if needed. The Python installer should
include the `py` launcher. Git is recommended.

## 2. Extract to a normal local directory

Extract the ZIP so that the folder containing `package.json` is, for example,
`C:\Projects\gridlite`. Do not run from inside the ZIP, a OneDrive-synced
folder, or a shared network folder.

Open PowerShell in that directory:

```powershell
cd C:\Projects\gridlite
```

## 3. Set up the isolated Python environment

```powershell
py -3.12 -m venv api\.venv
.\api\.venv\Scripts\python.exe -m pip install -r api\requirements.txt
```

No `Activate.ps1` or change to PowerShell execution policy is required. All
npm scripts run GridLite's own Python using `scripts/py.js`.

## 4. Install Node packages using their lockfiles

```powershell
npm run install:all
```

This runs `npm ci` independently for the root, gateway and frontend; it fails
rather than quietly changing a lockfile. Use Node 24 for a consistent baseline.

## 5. Run validation

```powershell
npm run test:all
```

This runs Python API tests, Node API-client tests, and a React production build.

Then start the three services:

```powershell
npm run dev
```

Open http://localhost:5173 in your browser. For one-port demo mode, stop with
Ctrl+C and run `npm run build` followed by `npm start`; visit
http://localhost:4000.

You can optionally use `GridLite_Windows_Check.ps1` in the project root as a
single diagnostic command (it reports each failing check). After setup, you can
also double-click `start-windows.cmd` to start the development app.

## 6. Windows-specific manual tests that CI cannot replace

**Use only the included sample CSVs or disposable copies:**

1. Edit a cell, refresh, confirm it persisted. Check Enter, Tab, Esc, Delete.
2. Open a disposable CSV in Excel, edit it in GridLite. If Excel blocks the
   replacement, verify GridLite shows an error and has not changed the CSV.
3. Close Excel and retry. Check that backups appear in `data/backups/`.
4. Test a fully quoted Oracle export and a CRLF file. Confirm the original
   quoting convention and line endings are retained.
5. Edit the CSV externally while GridLite is open, then attempt an edit in
   GridLite. The write must reject a stale file version, not change a wrong row.
6. Verify search, sorting, filtering, adding/deleting rows, adding columns,
   history, upload, and download.

## Common failures

- **`No Python found at ...api\.venv\Scripts\python.exe`**: the Windows virtual
  environment was not created in the correct folder. Recreate it using step 3.
- **`ModuleNotFoundError: flask`**: dependencies were installed into a different
  Python. Use the explicit `.venv\Scripts\python.exe -m pip` command above.
- **`Cannot reach gateway`**: check the output of `npm run dev` for crashes or
  occupied ports 4000, 5001, 5173.
- **`Could not save ... Excel`**: close the CSV in Excel, check file permissions,
  then reload and retry. Windows file locking differs from macOS.
- **`409 This CSV changed`**: another tool modified it. Refresh before editing.
- **`npm ci` lockfile conflict**: do not delete the lockfile casually; reconcile
  package metadata and lockfiles in a reviewed code change.

## What these checks do NOT prove

Automated tests are not a substitute for actually launching the app on Windows.
GridLite is still a **single-user** CSV editor: optimistic version tokens
protect against many stale writes but are not a full inter-process locking or
multi-user transaction system. Mixed per-cell quoting is normalized when saved.
