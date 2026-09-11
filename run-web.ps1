$ErrorActionPreference = 'Stop'
Push-Location $PSScriptRoot
try {
    $bankguardPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
    if (-not (Test-Path -LiteralPath $bankguardPython)) {
        $bankguardPython = (Get-Command python -ErrorAction Stop).Source
    }
    & $bankguardPython server.py
} finally {
    Pop-Location
}
