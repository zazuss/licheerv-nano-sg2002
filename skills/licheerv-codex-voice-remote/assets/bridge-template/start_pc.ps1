$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
if (-not (Test-Path -LiteralPath 'pc_config.json')) {
    throw 'Run .\setup_pc.ps1 first.'
}
& '.\.venv\Scripts\python.exe' '.\pc_server.py'
