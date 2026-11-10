<#
.SYNOPSIS
    重启 Fast Building 平台后端（先停止，再启动）。

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts\restart.ps1
#>
[CmdletBinding()]
param(
    [switch]$SkipFrontendBuild
)

$ErrorActionPreference = 'Stop'

& (Join-Path $PSScriptRoot 'stop.ps1')
Start-Sleep -Milliseconds 800

if ($SkipFrontendBuild) {
    & (Join-Path $PSScriptRoot 'start.ps1') -SkipFrontendBuild
} else {
    & (Join-Path $PSScriptRoot 'start.ps1')
}
exit $LASTEXITCODE
