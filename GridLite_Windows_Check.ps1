<#
Windows setup and diagnostics for GridLite. No uv or Unix shell required.
Run from PowerShell in the extracted project root:
  powershell -NoProfile -ExecutionPolicy Bypass -File .\GridLite_Windows_Check.ps1 -Setup
Later diagnostics without reinstalling:
  powershell -NoProfile -ExecutionPolicy Bypass -File .\GridLite_Windows_Check.ps1
#>
[CmdletBinding()]
param([switch]$Setup, [string]$ProjectRoot = $PSScriptRoot)

$ErrorActionPreference = 'Stop'
$ProjectRoot = (Resolve-Path -LiteralPath $ProjectRoot).Path
$Python = Join-Path $ProjectRoot 'api\.venv\Scripts\python.exe'
$Venv = Join-Path $ProjectRoot 'api\.venv'

function Run-Checked([string]$Program, [string[]]$Arguments) {
    Write-Host ('> ' + $Program + ' ' + ($Arguments -join ' ')) -ForegroundColor Cyan
    & $Program @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Command exited $LASTEXITCODE : $Program $($Arguments -join ' ')"
    }
}

if (-not (Test-Path (Join-Path $ProjectRoot 'package.json')) -or
    -not (Test-Path (Join-Path $ProjectRoot 'api\requirements.txt'))) {
    throw "Not a GridLite project folder: $ProjectRoot"
}

Push-Location $ProjectRoot
try {
    Write-Host "GridLite Windows check — $ProjectRoot" -ForegroundColor Cyan
    if (-not (Get-Command node -ErrorAction SilentlyContinue)) { throw 'Node.js 24 is missing.' }
    if (-not (Get-Command npm.cmd -ErrorAction SilentlyContinue)) { throw 'npm.cmd is missing.' }
    Run-Checked 'node' @('--version')
    $NodeVersion = (& node --version).Trim()
    if ($NodeVersion -notmatch '^v24\.') {
        throw "GridLite standardizes on Node.js 24.x; detected $NodeVersion. Install Node 24."
    }
    Run-Checked 'npm.cmd' @('--version')
    if ($Setup) {
        if (-not (Test-Path $Python)) {
            if (Test-Path $Venv) {
                throw 'api\.venv exists but has no Windows python.exe. Remove or rename the copied/incomplete venv before setup.'
            }
            if (-not (Get-Command py -ErrorAction SilentlyContinue)) {
                throw 'Python 3.12 launcher (py) is missing. Install Python 3.12 from python.org.'
            }
            Run-Checked 'py' @('-3.12', '-m', 'venv', 'api/.venv')
        }
        Run-Checked $Python @('-m', 'pip', 'install', '-r', 'api/requirements.txt')
        Run-Checked 'npm.cmd' @('run', 'install:all')
    }
    if (-not (Test-Path $Python)) {
        throw 'Windows api\.venv\Scripts\python.exe is missing; run this script with -Setup.'
    }
    Run-Checked $Python @('-c', 'import sys; print(sys.executable); print(sys.version)')
    Run-Checked $Python @('-c', 'import flask, pandas, pytest; print("Flask, pandas, pytest imports: OK"); print("pandas:", pandas.__version__); print("pytest:", pytest.__version__)')
    Run-Checked 'npm.cmd' @('run', 'test:all')
    Write-Host "`nAutomated checks passed. Start GridLite using npm run dev, then open http://localhost:5173." -ForegroundColor Green
    Write-Host 'Perform the Excel-lock and manual-browser checks in docs/WINDOWS.md.'
} catch {
    Write-Host "`nGridLite Windows check FAILED" -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red
    Write-Host 'Keep the full terminal output when reporting a Windows-specific failure.'
    exit 1
} finally {
    Pop-Location
}
