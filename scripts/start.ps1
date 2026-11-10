<#
.SYNOPSIS
    启动 Fast Building 平台后端（前端由同一端口托管）。

.DESCRIPTION
    - 端口 8756 已被占用时直接提示并退出，避免重复启动；
    - frontend/dist 缺失时自动执行 npm run build（可用 -SkipFrontendBuild 跳过）；
    - 运行日志写入 .run/backend.log / backend.err.log，进程号写入 .run/backend.pid。

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts\start.ps1
#>
[CmdletBinding()]
param(
    [switch]$SkipFrontendBuild
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$port = 8756
$python = if ($env:FASTBUILD_PYTHON) { $env:FASTBUILD_PYTHON } else { 'D:\thirdparty\venvs\fastbuild\Scripts\python.exe' }

$runDir = Join-Path $root '.run'
$pidFile = Join-Path $runDir 'backend.pid'
$logFile = Join-Path $runDir 'backend.log'
$errFile = Join-Path $runDir 'backend.err.log'

if (-not (Test-Path $python)) {
    Write-Host "未找到 Python 解释器：$python（可用环境变量 FASTBUILD_PYTHON 指定）" -ForegroundColor Red
    exit 1
}
New-Item -ItemType Directory -Force -Path $runDir | Out-Null

$listener = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
if ($listener) {
    Write-Host "后端已在运行：http://127.0.0.1:$port（PID $($listener.OwningProcess)）"
    exit 0
}

$distIndex = Join-Path $root 'frontend\dist\index.html'
if (-not $SkipFrontendBuild -and -not (Test-Path $distIndex)) {
    Write-Host '未发现前端构建产物，正在执行 npm run build ...'
    Push-Location (Join-Path $root 'frontend')
    try { npm run build } finally { Pop-Location }
}

$process = Start-Process -FilePath $python `
    -ArgumentList 'run.py' `
    -WorkingDirectory (Join-Path $root 'backend') `
    -WindowStyle Hidden -PassThru `
    -RedirectStandardOutput $logFile `
    -RedirectStandardError $errFile
Write-Host "后端进程已启动（PID $($process.Id)），等待就绪 ..."

# venv 的 python.exe 是启动器，会再派生真实解释器进程，
# 因此以端口就绪为准，而不是以启动器进程是否存活为准。
for ($i = 0; $i -lt 60; $i++) {
    Start-Sleep -Milliseconds 500
    try {
        $null = Invoke-RestMethod "http://127.0.0.1:$port/api/health" -TimeoutSec 3
        $listener = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
        if ($listener) {
            ($listener.OwningProcess | Select-Object -First 1) | Set-Content -Path $pidFile -Encoding ASCII
        } else {
            $process.Id | Set-Content -Path $pidFile -Encoding ASCII
        }
        Write-Host "启动成功：http://127.0.0.1:$port"
        exit 0
    } catch {
        # 端口尚未就绪，继续等待
    }
}

Write-Host "启动失败，请查看日志：$errFile" -ForegroundColor Red
if (Test-Path $errFile) { Get-Content $errFile -Tail 20 }
exit 1
