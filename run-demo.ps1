param([switch]$WithApi)
$ErrorActionPreference = 'Stop'
$pythonCommand = Get-Command python -ErrorAction SilentlyContinue
if ($pythonCommand) {
    $challengePython = $pythonCommand.Source
} else {
    $challengePython = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
    if (-not (Test-Path -LiteralPath $challengePython)) {
        throw 'Python 3.10+ is required. Install Python or add it to PATH.'
    }
}
Push-Location -LiteralPath $PSScriptRoot
try {
    & $challengePython -B -X utf8 run_checks.py
    if ($LASTEXITCODE -ne 0) { throw 'Tests failed; see output/tests.log' }
    if ($WithApi) {
        & $challengePython -B -X utf8 demo.py --with-api
    } else {
        & $challengePython -B -X utf8 demo.py
    }
    if ($LASTEXITCODE -ne 0) { throw 'Demo failed; inspect the latest evidence directory.' }
} finally {
    Pop-Location
}
