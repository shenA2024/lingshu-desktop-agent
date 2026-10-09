$ErrorActionPreference = 'Stop'
$workbenchRoot = $PSScriptRoot
$pidPath = Join-Path $workbenchRoot 'data/server.pid'
if (-not (Test-Path -LiteralPath $pidPath)) { Write-Host 'No recorded server process.'; exit 0 }
$serverPid = [int](Get-Content -LiteralPath $pidPath)
$serverProcess = Get-CimInstance Win32_Process -Filter "ProcessId = $serverPid"
$expectedScript = Join-Path $workbenchRoot 'workbench.py'
$expectedHarness = Join-Path $workbenchRoot 'harness_runner.cjs'
$expectedBridge = Join-Path $workbenchRoot 'mcp_bridge.py'
if ($serverProcess -and $serverProcess.CommandLine.Contains($expectedScript)) {
    # Windows venv launchers may create another Python process. Validate the
    # entire descendant tree before stopping any process, deepest first.
    function Get-LabProcessTree([int]$labProcessId) {
        $labIds = @()
        foreach ($child in (Get-CimInstance Win32_Process -Filter "ParentProcessId = $labProcessId")) {
            if (-not ($child.CommandLine -and ($child.CommandLine.Contains($expectedScript) -or $child.CommandLine.Contains($expectedHarness) -or $child.CommandLine.Contains($expectedBridge) -or $child.CommandLine.Contains('md_cg.mcp_server'))) -and $child.Name -ne 'conhost.exe') {
                throw 'Unexpected service descendant; refusing to stop it.'
            }
            $labIds += Get-LabProcessTree $child.ProcessId
        }
        $labIds += $labProcessId
        return $labIds
    }
    $ownedProcessIds = @(Get-LabProcessTree $serverPid)
    foreach ($ownedProcessId in $ownedProcessIds) { Stop-Process -Id $ownedProcessId -Force -ErrorAction SilentlyContinue }
    Write-Host 'Lingshu World Model Lab stopped. Sessions and demo memory are retained.'
} elseif ($serverProcess) {
    throw 'Recorded process belongs to another application; refusing to stop it.'
}
Remove-Item -LiteralPath $pidPath -ErrorAction SilentlyContinue
