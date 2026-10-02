$ErrorActionPreference = 'Stop'
$project = $PSScriptRoot

# Re-running the logon task must not start another receiver.
try {
    $health = Invoke-RestMethod -Uri 'http://127.0.0.1:8765/health' -TimeoutSec 2 -Proxy $null
    if ($health.ok) { exit 0 }
} catch {
    # The receiver is not ready; start it below.
}

$python = Join-Path $project '.venv\Scripts\python.exe'
$server = Join-Path $project 'pc_server.py'
if (-not (Test-Path -LiteralPath $python) -or -not (Test-Path -LiteralPath $server)) {
    throw 'Run setup_pc.ps1 before enabling automatic startup.'
}

Start-Process -FilePath $python -ArgumentList $server -WorkingDirectory $project `
    -WindowStyle Hidden `
    -RedirectStandardOutput (Join-Path $project 'pc_server.auto.log') `
    -RedirectStandardError (Join-Path $project 'pc_server.auto.err.log')
