#Requires -Version 5.1
<#
.SYNOPSIS
    一键启动 WorkBuddy 反代服务器（Windows PowerShell）

.EXAMPLE
    .\start.ps1                # 默认端口 19090
    .\start.ps1 -Port 8080     # 指定端口
#>

param(
    [int]$Port = 19090
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$env:PYTHONIOENCODING = "utf-8"
Set-Location $PSScriptRoot

# 检查 Python
$py = Get-Command python -ErrorAction SilentlyContinue
if (-not $py) {
    Write-Host "[ERROR] 未找到 python，请先安装 Python 3.10+ 并添加到 PATH" -ForegroundColor Red
    Write-Host "        下载: https://www.python.org/downloads/"
    Write-Host "        安装时务必勾选 'Add Python to PATH'"
    Read-Host "按 Enter 退出"
    exit 1
}

$pyVer = python --version 2>&1
Write-Host "[INFO] $pyVer" -ForegroundColor Gray

# 检查依赖
$missing = $false
try {
    python -c "import fastapi, httpx, uvicorn, jwt" 2>$null
} catch {
    $missing = $true
}
if ($LASTEXITCODE -ne 0) { $missing = $true }

if ($missing) {
    Write-Host "[INFO] 正在安装依赖..." -ForegroundColor Yellow
    python -m pip install -r requirements.txt -q
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[ERROR] 依赖安装失败，请检查网络或 pip 配置" -ForegroundColor Red
        Read-Host "按 Enter 退出"
        exit 1
    }
}

# 首次运行：尝试从 CDP 提取 token
if (-not (Test-Path "data\token.json")) {
    Write-Host "[INFO] 首次运行，尝试从 WorkBuddy 提取 Token..." -ForegroundColor Cyan
    try {
        python -c "import websockets" 2>$null
        if ($LASTEXITCODE -eq 0) {
            python extract_token.py --save
            if ($LASTEXITCODE -ne 0) {
                Write-Host "[WARN] CDP 提取失败，请确认 WorkBuddy 已用调试模式启动" -ForegroundColor Yellow
                Write-Host "       或手动设置: `$env:WB_TOKEN = '<your-jwt>'"
            }
        } else {
            Write-Host "[WARN] websockets 未安装，跳过 CDP 提取" -ForegroundColor Yellow
            Write-Host "       安装: python -m pip install websockets"
        }
    } catch {
        Write-Host "[WARN] CDP 提取失败: $_" -ForegroundColor Yellow
    }
}

Write-Host ""
Write-Host "==================================================" -ForegroundColor Green
Write-Host "  WorkBuddy OpenAI-Compatible Reverse Proxy"        -ForegroundColor Green
Write-Host "==================================================" -ForegroundColor Green
Write-Host "  端口:    http://127.0.0.1:${Port}/v1"             -ForegroundColor White
Write-Host "  API Key: wb-proxy-key"                             -ForegroundColor White
Write-Host "==================================================" -ForegroundColor Green
Write-Host "  按 Ctrl+C 停止服务"                                -ForegroundColor Gray
Write-Host ""

$env:PROXY_PORT = $Port
python server.py

if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "[ERROR] 服务异常退出 (exit code: $LASTEXITCODE)" -ForegroundColor Red
    Read-Host "按 Enter 退出"
}
