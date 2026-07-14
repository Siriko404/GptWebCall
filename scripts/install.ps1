[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[a-p]{32}$')]
    [string]$ExtensionId,
    [switch]$WhatIf
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$hostPath = Join-Path $root 'bin\gptwebcall-host.exe'
$templatePath = Join-Path $root 'native-host\com.sina.gptwebcall.template.json'
$manifestPath = Join-Path $root 'native-host\com.sina.gptwebcall.json'
$registryPath = 'HKCU:\Software\Google\Chrome\NativeMessagingHosts\com.sina.gptwebcall'

if ($WhatIf) {
    Write-Output "Would build: $hostPath"
    Write-Output "Would write host manifest: $manifestPath"
    Write-Output "Would register: $registryPath"
    Write-Output "Unpacked extension directory: $(Join-Path $root 'extension')"
    exit 0
}

& (Join-Path $PSScriptRoot 'build.ps1')
if (-not (Test-Path -LiteralPath $hostPath -PathType Leaf)) {
    throw "Native host was not built: $hostPath"
}

$template = Get-Content -LiteralPath $templatePath -Raw -Encoding UTF8
$rendered = $template.Replace('__HOST_PATH__', $hostPath.Replace('\', '\\')).Replace('__EXTENSION_ID__', $ExtensionId)
Set-Content -LiteralPath $manifestPath -Value $rendered -Encoding UTF8 -NoNewline
New-Item -Path $registryPath -Force | Out-Null
Set-Item -LiteralPath $registryPath -Value $manifestPath

Write-Output "Installed native host: $manifestPath"
Write-Output "Registered: $registryPath"
Write-Output "Load this unpacked extension directory in Chrome: $(Join-Path $root 'extension')"
