[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Push-Location $root
try {
    gofmt -l .
    if ($LASTEXITCODE -ne 0) { throw 'gofmt failed' }
    go test ./... -race -count=1
    if ($LASTEXITCODE -ne 0) { throw 'Go tests failed' }
    python -m unittest discover -s companion/tests -v
    if ($LASTEXITCODE -ne 0) { throw 'Python tests failed' }
    npm --prefix extension test
    if ($LASTEXITCODE -ne 0) { throw 'Extension tests failed' }
    .\scripts\build.ps1
    if ($LASTEXITCODE -ne 0) { throw 'Native host build failed' }
    .\tests\e2e\fixture_call.ps1
    if ($LASTEXITCODE -ne 0) { throw 'Fixture call failed' }
    git diff --check
    if ($LASTEXITCODE -ne 0) { throw 'Git whitespace validation failed' }
}
finally {
    Pop-Location
}
