@echo off
REM PM2 / 计划任务用：在完整 CMD 环境下走 PATH（兼容 pyenv-win 的 python.bat）
cd /d "%~dp0"
python -u server.py
