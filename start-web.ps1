param([int]$Port = 8766)
$ErrorActionPreference = 'Stop'
$labUrl = 'http://127.0.0.1:' + $Port
$labOutput = Join-Path $PSScriptRoot 'output'
New-Item -ItemType Directory -Force -Path $labOutput | Out-Null
try {
    $labHealth = Invoke-RestMethod -Uri ($labUrl + '/api/health') -TimeoutSec 2
    if ($labHealth.app -eq 'challenge-b-context-lab') {
        Write-Output ('Context Lab is already running: ' + $labUrl)
        exit 0
    }
} catch { }
$labPython = (Get-Command python -CommandType Application -ErrorAction Stop | Select-Object -First 1).Source
$labScript = Join-Path $PSScriptRoot 'webapp.py'
$labProcess = Start-Process -FilePath $labPython `
    -ArgumentList @('-B', '-X', 'utf8', '-u', ('"' + $labScript + '"'), '--port', [string]$Port) `
    -WorkingDirectory $PSScriptRoot -WindowStyle Hidden -PassThru `
    -RedirectStandardOutput (Join-Path $labOutput 'web-server.log') `
    -RedirectStandardError (Join-Path $labOutput 'web-server-error.log')
$labProcess.Id | Set-Content -LiteralPath (Join-Path $labOutput 'web-server.pid')
for ($labAttempt = 0; $labAttempt -lt 30; $labAttempt++) {
    Start-Sleep -Milliseconds 200
    try {
        $labHealth = Invoke-RestMethod -Uri ($labUrl + '/api/health') -TimeoutSec 2
        if ($labHealth.app -eq 'challenge-b-context-lab') {
            Write-Output ('Context Lab is running: ' + $labUrl)
            Write-Output 'B1 + B2 execute locally. Evidence is saved in output/web-runs.'
            exit 0
        }
    } catch {
        if ($labProcess.HasExited) { break }
    }
}
throw 'Context Lab did not start. Check output/web-server-error.log or choose another -Port.'
