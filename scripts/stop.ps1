<#
.SYNOPSIS
    停止 Fast Building 平台后端。

.DESCRIPTION
    优先按 .run/backend.pid 记录的进程号停止；若记录缺失，
    则回退为结束占用 8756 端口的进程。

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts\stop.ps1
#>
[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$port = 8756
$pidFile = Join-Path $root '.run\backend.pid'
$stopped = $false

if (Test-Path $pidFile) {
    $backendPid = (Get-Content $pidFile -ErrorAction SilentlyContinue | Select-Object -First 1)
    if ($backendPid) { $backendPid = $backendPid.Trim() }
    if ($backendPid -and (Get-Process -Id $backendPid -ErrorAction SilentlyContinue)) {
        Stop-Process -Id $backendPid -Force
        Write-Host "已停止后端进程（PID $backendPid）"
        $stopped = $true
    }
    Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
}

if (-not $stopped) {
    $listener = Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue |
        Where-Object { $_.State -eq 'Listen' }
    if ($listener) {
        foreach ($owner in ($listener.OwningProcess | Sort-Object -Unique)) {
            Stop-Process -Id $owner -Force -ErrorAction SilentlyContinue
            Write-Host "已停止占用端口 $port 的进程（PID $owner）"
        }
        $stopped = $true
    }
}

if (-not $stopped) {
    Write-Host "后端未在运行（端口 $port 空闲）"
}
