# PDF Step 5 (local test on Windows): run from ugc-machine folder
$env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
Set-Location $PSScriptRoot
if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) {
    Write-Host "FFmpeg not found. Install: winget install Gyan.FFmpeg" -ForegroundColor Red
    exit 1
}
$cfg = Get-Content config.json -Raw | ConvertFrom-Json
$placeholderKeys = @("", "PASTE_THE_REAL_KEY_HERE", "PASTE_YOUR_KIE_KEY_HERE")
if ($placeholderKeys -contains $cfg.kie_api_key) {
    Write-Host "Step 4: Paste your Kie key in config.json (https://kie.ai/api-key) then run again." -ForegroundColor Yellow
}
Write-Host "Starting UGC Machine -> http://localhost:8745"
python server.py
