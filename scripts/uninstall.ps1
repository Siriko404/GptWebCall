[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$manifestPath = Join-Path $root 'native-host\com.sina.gptwebcall.json'
$registryPath = 'HKCU:\Software\Google\Chrome\NativeMessagingHosts\com.sina.gptwebcall'

if (Test-Path -LiteralPath $registryPath) {
    Remove-Item -LiteralPath $registryPath -Force
}
if (Test-Path -LiteralPath $manifestPath -PathType Leaf) {
    Remove-Item -LiteralPath $manifestPath -Force
}

Write-Output 'Removed only the GPT Web Call native-host registration and generated manifest.'
