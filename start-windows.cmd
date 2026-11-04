@echo off
setlocal
cd /d "%~dp0"
if not exist "api\.venv\Scripts\python.exe" (
  echo GridLite is not set up. Run GridLite_Windows_Check.ps1 -Setup first.
  pause
  exit /b 1
)
where node >nul 2>nul
if errorlevel 1 (
  echo Node.js 24 is missing. See docs\WINDOWS.md.
  pause
  exit /b 1
)
npm run dev
if errorlevel 1 (
  echo GridLite failed to start. See the error above and docs\WINDOWS.md.
  pause
  exit /b 1
)
