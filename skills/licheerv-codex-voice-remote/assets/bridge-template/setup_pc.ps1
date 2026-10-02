$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot

if (-not (Test-Path -LiteralPath '.venv\Scripts\python.exe')) {
    python -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Could not create Python virtual environment.' }
}
& '.\.venv\Scripts\python.exe' -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw 'Could not upgrade pip.' }
& '.\.venv\Scripts\python.exe' -m pip install -r requirements-pc.txt
if ($LASTEXITCODE -ne 0) { throw 'Could not install PC dependencies.' }

$senseVoiceRoot = Join-Path $PSScriptRoot 'models\sensevoice'
$senseVoiceModel = Join-Path $senseVoiceRoot 'sherpa-onnx-sense-voice-zh-en-ja-ko-yue-int8-2024-07-17\model.int8.onnx'
if (-not (Test-Path -LiteralPath $senseVoiceModel)) {
    New-Item -ItemType Directory -Force -Path $senseVoiceRoot | Out-Null
    $archive = Join-Path $senseVoiceRoot 'sensevoice.tar.bz2'
    & curl.exe -L --retry 3 --retry-delay 2 --output $archive `
        'https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/sherpa-onnx-sense-voice-zh-en-ja-ko-yue-int8-2024-07-17.tar.bz2'
    if ($LASTEXITCODE -ne 0) { throw 'Could not download the SenseVoice model.' }
    & tar.exe -xf $archive -C $senseVoiceRoot
    if ($LASTEXITCODE -ne 0) { throw 'Could not extract the SenseVoice model.' }
    if (-not (Test-Path -LiteralPath $senseVoiceModel)) { throw 'SenseVoice model file is missing after extraction.' }
    Remove-Item -LiteralPath $archive -Force
}

if (-not (Test-Path -LiteralPath 'pc_config.json')) {
    $config = Get-Content -LiteralPath 'pc_config.example.json' -Raw -Encoding UTF8 | ConvertFrom-Json
    $bytes = New-Object byte[] 32
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try { $rng.GetBytes($bytes) } finally { $rng.Dispose() }
    $config.token = [BitConverter]::ToString($bytes).Replace('-', '').ToLowerInvariant()
    $json = $config | ConvertTo-Json -Depth 10
    [System.IO.File]::WriteAllText((Join-Path $PSScriptRoot 'pc_config.json'), $json, (New-Object System.Text.UTF8Encoding($false)))
    Write-Host 'Created pc_config.json with a random token. Copy the token to board_config.json.'
} else {
    Write-Host 'pc_config.json already exists; kept unchanged.'
}
Write-Host 'Setup complete. Run .\start_pc.ps1 to start the PC server.'
