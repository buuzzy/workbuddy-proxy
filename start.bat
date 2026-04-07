@echo off
chcp 65001 >nul 2>&1
title WorkBuddy Proxy
cd /d "%~dp0"

:: ---- Locate Python ----
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] 未找到 python，请先安装 Python 3.10+ 并添加到 PATH
    echo         下载: https://www.python.org/downloads/
    echo         安装时务必勾选 "Add Python to PATH"
    pause
    exit /b 1
)

:: ---- Check Python version ----
for /f "tokens=2 delims= " %%v in ('python --version 2^>^&1') do set PYVER=%%v
echo [INFO] Python %PYVER%

:: ---- Install dependencies if missing ----
python -c "import fastapi, httpx, uvicorn, jwt" >nul 2>&1
if %errorlevel% neq 0 (
    echo [INFO] 正在安装依赖...
    python -m pip install -r requirements.txt -q
    if %errorlevel% neq 0 (
        echo [ERROR] 依赖安装失败，请检查网络或 pip 配置
        pause
        exit /b 1
    )
)

:: ---- First-run: extract token via CDP if no saved token ----
if not exist "data\token.json" (
    echo [INFO] 首次运行，尝试从 WorkBuddy 提取 Token...
    python -c "import websockets" >nul 2>&1
    if %errorlevel% equ 0 (
        python extract_token.py --save
        if %errorlevel% neq 0 (
            echo [WARN] CDP 提取失败，请确认 WorkBuddy 已用调试模式启动
            echo        或手动设置环境变量: set WB_TOKEN=^<your-jwt^>
        )
    ) else (
        echo [WARN] websockets 未安装，跳过 CDP 提取
        echo        安装: python -m pip install websockets
    )
)

:: ---- Parse optional port argument ----
set PORT=19090
if not "%~1"=="" set PORT=%~1

echo.
echo ==================================================
echo   WorkBuddy OpenAI-Compatible Reverse Proxy
echo ==================================================
echo   端口:    http://127.0.0.1:%PORT%/v1
echo   API Key: wb-proxy-key
echo ==================================================
echo   按 Ctrl+C 停止服务
echo.

set PROXY_PORT=%PORT%
python server.py
if %errorlevel% neq 0 (
    echo.
    echo [ERROR] 服务异常退出 (exit code: %errorlevel%)
    pause
)
