param([string]$Python = 'python', [switch]$Dev)
$ErrorActionPreference = 'Stop'
$labPython = Join-Path $PSScriptRoot '.venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $labPython)) {
    & $Python -m venv (Join-Path $PSScriptRoot '.venv')
    if ($LASTEXITCODE -ne 0) { throw 'Cannot create .venv. Use setup.ps1 -Python <python.exe>.' }
}
$labArguments = @('-X', 'utf8', (Join-Path $PSScriptRoot 'bootstrap.py'))
if ($Dev) { $labArguments += '--dev' }
& $labPython @labArguments
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed. See the actionable error above.' }
