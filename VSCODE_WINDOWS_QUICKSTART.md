# GridLite: VS Code setup on a Windows laptop

This package includes the repaired GridLite source **plus** four VS Code workspace files in `.vscode/`.

## 1. Install prerequisite applications

- [Visual Studio Code](https://code.visualstudio.com/)
- [Node.js 24.x](https://nodejs.org/en/download)
- [Python 3.12](https://www.python.org/downloads/) with the Windows `py` launcher enabled
- Git (recommended, for saving and reviewing source changes)

Close and reopen VS Code after installing Node or Python so it picks up the updated PATH.

## 2. Extract and open the correct directory

Extract the package to a local folder such as `C:\Projects\gridlite-windows`.
If extraction creates another nested folder, **open the folder containing `package.json`, `api/`, `gateway/`, `web/`, and `.vscode/`**.

Do not run from inside a ZIP, a OneDrive-synced folder, or the old Mac `~/Projects/...` location.
Do not copy `api/.venv` or `node_modules` from macOS.

In VS Code: **File > Open Folder**, select that project folder, and accept the recommended Python extensions.

## 3. Perform first-time setup

In VS Code, open **Terminal > Run Task... > GridLite: first-time setup (Windows)**.
This uses the project's PowerShell script to create the Windows virtual environment, install Python and Node dependencies, and run its automated checks.

You can equivalently open a PowerShell terminal in the project root and run:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\GridLite_Windows_Check.ps1 -Setup
```

Before setup, warnings about the missing Python interpreter are expected.
**The interpreter VS Code should use after setup is:**
`api\.venv\Scripts\python.exe`.

## 4. Run the application

Use **Terminal > Run Task... > GridLite: run app**.
Wait until the API, gateway, and web development servers are ready, then open:

http://127.0.0.1:5173

You should see sample CSV tables. Keep that terminal running while you use the app.
Stop it using `Ctrl+C` in the task terminal, or Terminal > Terminate Task.

## 5. Test and debug code

- **Run tests:** Terminal > Run Task... > GridLite: test all.
- **Python test explorer:** Use the Testing beaker icon in VS Code (pytest is configured for `api/tests`).
- **Debug Flask + gateway:** First stop the normal `GridLite: run app` task to free ports 4000 and 5001. Start `GridLite: web only`. Then go to Run and Debug (Ctrl+Shift+D), select **Debug Flask + gateway**, and press F5.
- **Debug React:** With the normal app running or the debugging arrangement above, select **React app (Edge breakpoints)** in Run and Debug, then press F5.

A red breakpoint in `api/storage.py` or `api/app.py` should be hit by an actual edit in GridLite if the Flask debugger is running. If you use `npm run dev` for Flask instead, the Python debugger is *not* attached; use the debug configuration.

## 6. If something fails

Paste the **first actual error and the full relevant VS Code terminal output**, rather than just the final line. Common checks:

```powershell
node --version
npm.cmd --version
py -3.12 --version
.\api\.venv\Scripts\python.exe --version
npm.cmd run test:all
```

If PowerShell complains that `npm.ps1` is blocked, run `npm.cmd` explicitly. The provided VS Code tasks already use `npm.cmd`.

If ports 4000, 5001 or 5173 are already occupied, stop existing GridLite terminals/tasks before launching a second instance.
If the Python environment points to a Mac path or a copied venv, delete only the **copied/broken** `api/.venv` and rerun setup.

## Important limits

This VS Code configuration is **prepared but not tested on an actual Windows PC** in this environment. It does not change GridLite's production functionality. Use sample data or disposable copies of your files. GridLite remains a single-user editor and this setup does not add login or undo.
