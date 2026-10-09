param([switch]$NoBrowser, [switch]$Desktop, [string]$Python)
$ErrorActionPreference = 'Stop'
$workbenchRoot = $PSScriptRoot
$workbenchConfig = Get-Content -LiteralPath (Join-Path $workbenchRoot 'config.json') -Raw | ConvertFrom-Json
$workbenchUrl = "http://127.0.0.1:$($workbenchConfig.port)"
function Open-LingshuWindow {
    $edgePath = Join-Path ${env:ProgramFiles(x86)} 'Microsoft/Edge/Application/msedge.exe'
    if ($Desktop -and (Test-Path -LiteralPath $edgePath)) {
        Start-Process -FilePath $edgePath -ArgumentList @("--app=$workbenchUrl", '--window-size=1280,900')
    } else { Start-Process $workbenchUrl }
}
try {
    $health = Invoke-RestMethod -Uri "$workbenchUrl/api/health" -TimeoutSec 2
    if ($health.world -ne 'lingshu.world.UnifiedWorldModel') { throw 'Port is occupied by another service.' }
    $listener = Get-NetTCPConnection -LocalPort $workbenchConfig.port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
    $runningProcess = if ($listener) { Get-CimInstance Win32_Process -Filter "ProcessId = $($listener.OwningProcess)" }
    if (-not $runningProcess -or -not $runningProcess.CommandLine.Contains((Join-Path $workbenchRoot 'workbench.py'))) { throw 'Port is occupied by another service.' }
    Write-Host "Lingshu World Model Lab is already running: $workbenchUrl"
    if (-not $NoBrowser) { Open-LingshuWindow }
    exit 0
} catch {
    if ($_.Exception.Message -eq 'Port is occupied by another service.') { throw }
}
$pythonCommand = if ($Python) { (Get-Command $Python -ErrorAction Stop).Source } else { Join-Path $workbenchRoot '.venv/Scripts/python.exe' }
if (-not (Test-Path -LiteralPath $pythonCommand)) { $pythonCommand = (Get-Command python -ErrorAction Stop).Source }
Push-Location -LiteralPath $workbenchRoot
try {
    & $pythonCommand -X utf8 -c "from dependencies import resolve; resolve()"
    if ($LASTEXITCODE -ne 0) { throw 'Run setup.ps1 to install the pinned external dependencies.' }
} finally { Pop-Location }
New-Item -ItemType Directory -Path (Join-Path $workbenchRoot 'data') -Force | Out-Null
$serverScript = Join-Path $workbenchRoot 'workbench.py'
$serverProcess = Start-Process -FilePath $pythonCommand -ArgumentList @('-X','utf8',('"' + $serverScript + '"')) -WorkingDirectory $workbenchRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $workbenchRoot 'data/server.stdout.log') -RedirectStandardError (Join-Path $workbenchRoot 'data/server.stderr.log') -PassThru
$serverProcess.Id | Set-Content -LiteralPath (Join-Path $workbenchRoot 'data/server.pid')
for ($attempt = 0; $attempt -lt 60; $attempt++) {
    Start-Sleep -Milliseconds 500
    if ($serverProcess.HasExited) { throw "Server exited. See data/server.stderr.log. Install dependencies: python -m pip install -r requirements.txt" }
    try {
        $health = Invoke-RestMethod -Uri "$workbenchUrl/api/health" -TimeoutSec 1
        if ($health.world -eq 'lingshu.world.UnifiedWorldModel') {
            Write-Host "Lingshu World Model Lab: $workbenchUrl"
            if (-not $NoBrowser) { Open-LingshuWindow }
            exit 0
        }
    } catch { }
}
throw 'Startup timed out. See data/server.stderr.log.'
