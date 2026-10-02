$root = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not (Test-Path "$root\reachy_config.json")) {
  Copy-Item "$root\reachy_config.example.json" "$root\reachy_config.json"
  Write-Host '已创建 reachy_config.json；请设置随机 token 后再启动。'
  exit 1
}
& "$root\.venv\Scripts\python.exe" "$root\reachy_bridge.py"
