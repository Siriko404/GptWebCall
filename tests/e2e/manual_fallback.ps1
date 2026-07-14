[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$repositoryRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$fixture = & (Join-Path $PSScriptRoot 'fixture_call.ps1') | ConvertFrom-Json
$exchange = Join-Path $fixture.root (Join-Path 'calls' $fixture.exchange_id)
$response = Join-Path $exchange 'response'

Copy-Item -LiteralPath (Join-Path $repositoryRoot 'tests\mock_chatgpt\fixtures\result.json') -Destination (Join-Path $response 'result.json')
Copy-Item -LiteralPath (Join-Path $repositoryRoot 'tests\mock_chatgpt\fixtures\report.md') -Destination (Join-Path $response 'report.md')

$validated = & python -m companion.cli --root $fixture.root validate --exchange $fixture.exchange_id | ConvertFrom-Json
if (-not $validated.ok) { throw 'Manual validation command failed.' }
if ($validated.result.status -ne 'COMPLETE') { throw "Manual fallback status was $($validated.result.status)." }
$report = Get-Content -LiteralPath (Join-Path $exchange 'validation\VALIDATION_REPORT.json') -Raw | ConvertFrom-Json
if ($report.status -ne 'COMPLETE' -or $report.missing_files.Count -ne 0 -or $report.invalid_files.Count -ne 0) {
    throw 'Manual fallback validation report is not complete.'
}

@{ exchange_id = $fixture.exchange_id; status = $report.status; mode = 'manual-fallback' } | ConvertTo-Json -Compress
