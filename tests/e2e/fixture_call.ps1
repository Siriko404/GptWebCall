[CmdletBinding()]
param(
    [string]$Root = (Join-Path ([System.IO.Path]::GetTempPath()) ("gptwebcall-fixture-" + [Guid]::NewGuid().ToString('N')))
)

$ErrorActionPreference = 'Stop'
$repositoryRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$sources = Join-Path $Root 'sources'
New-Item -ItemType Directory -Force -Path $sources | Out-Null

$requestPath = Join-Path $sources 'WEB_REVIEW_REQUEST.json'
$schemaPath = Join-Path $sources 'WEB_RESPONSE_SCHEMA.json'
$contextPath = Join-Path $sources 'context.txt'
$specPath = Join-Path $Root 'spec.json'

function Write-Utf8NoBom([string]$Path, [string]$Content) {
    [System.IO.File]::WriteAllText($Path, $Content, [System.Text.UTF8Encoding]::new($false))
}

Write-Utf8NoBom $requestPath ((@{ request_id = 'fixture_request' } | ConvertTo-Json) + "`n")
Write-Utf8NoBom $schemaPath ((@{ type = 'object' } | ConvertTo-Json) + "`n")
Write-Utf8NoBom $contextPath "fixture context`n"

$spec = @{
    subject = 'Fixture call'
    request_id = 'fixture_request'
    expected_main_json = 'result.json'
    prompt_text = 'Return the required files only.'
    created_at = '2026-07-14T20:15:00-04:00'
    input_files = @(
        @{ path = $requestPath; filename = 'WEB_REVIEW_REQUEST.json' },
        @{ path = $schemaPath; filename = 'WEB_RESPONSE_SCHEMA.json' },
        @{ path = $contextPath; filename = 'context.txt' }
    )
}
Write-Utf8NoBom $specPath (($spec | ConvertTo-Json -Depth 5) + "`n")

$prepared = & python -m companion.cli --root $Root prepare --spec $specPath | ConvertFrom-Json
if (-not $prepared.ok) { throw 'Fixture call preparation failed.' }
$exchange = Join-Path $Root (Join-Path 'calls' $prepared.result.exchange_id)
$manifest = Get-Content -LiteralPath (Join-Path $exchange 'EXCHANGE_MANIFEST.json') -Raw | ConvertFrom-Json
$names = @($manifest.request_files | ForEach-Object filename)
$expected = @('PROMPT_2026-07-14_201500.txt', 'WEB_REVIEW_REQUEST.json', 'WEB_RESPONSE_SCHEMA.json', 'context.txt')
if (@(Compare-Object $expected $names).Count -ne 0) { throw "Unexpected fixture files: $($names -join ', ')" }
if ($manifest.request_files.Count -ne 4) { throw 'Fixture call contains an unexpected request file.' }
if (-not (Test-Path -LiteralPath (Join-Path $exchange 'response') -PathType Container)) { throw 'Response directory is missing.' }

@{ root = $Root; exchange_id = $manifest.exchange_id; request_files = $names } | ConvertTo-Json -Compress
