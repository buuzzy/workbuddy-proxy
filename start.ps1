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
Set-Location $PSScriptRoot

# 检查 Python
$py = Get-Command python -ErrorAction SilentlyContinue
if (-not $py) {
    Write-Host "未找到 python，请先安装 Python 3.10+ 并添加到 PATH" -ForegroundColor Red
    exit 1
}

# 检查依赖
$missing = $false
try {
    python -c "import fastapi, httpx, uvicorn, jwt" 2>$null
} catch {
    $missing = $true
}
if ($LASTEXITCODE -ne 0) { $missing = $true }

if ($missing) {
    Write-Host "正在安装依赖..." -ForegroundColor Yellow
    python -m pip install -r requirements.txt -q
}

# 首次运行：尝试从 CDP 提取 token
if (-not (Test-Path "data\token.json")) {
    Write-Host "首次运行，尝试从 WorkBuddy 提取 token..." -ForegroundColor Cyan
    try {
        python -c "import websockets" 2>$null
        if ($LASTEXITCODE -eq 0) {
            python extract_token.py --save
            if ($LASTEXITCODE -ne 0) {
                Write-Host "CDP 提取失败，请手动设置 WB_TOKEN 环境变量" -ForegroundColor Yellow
            }
        } else {
            Write-Host "websockets 未安装，跳过 CDP 提取" -ForegroundColor Yellow
            Write-Host "  安装: python -m pip install websockets"
            Write-Host "  或手动设置: `$env:WB_TOKEN = '<your-jwt>'"
        }
    } catch {
        Write-Host "CDP 提取失败: $_" -ForegroundColor Yellow
    }
}

Write-Host ""
Write-Host "==================================================" -ForegroundColor Green
Write-Host "  WorkBuddy OpenAI-Compatible Reverse Proxy"        -ForegroundColor Green
Write-Host "==================================================" -ForegroundColor Green
Write-Host "  端口:    http://127.0.0.1:${Port}/v1"             -ForegroundColor White
Write-Host "  API Key: wb-proxy-key"                             -ForegroundColor White
Write-Host "==================================================" -ForegroundColor Green
Write-Host ""

$env:PROXY_PORT = $Port
python server.py
