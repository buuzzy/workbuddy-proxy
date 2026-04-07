#!/usr/bin/env bash
# PM2 用：在非 Windows 上与 run-proxy.cmd 等价
set -e
cd "$(dirname "$0")"
exec python3 -u server.py
