#!/bin/bash
#
# 一键启动 WorkBuddy 反代服务器
#
# 用法:
#   ./start.sh              # 自动从 CDP 提取 token 并启动
#   ./start.sh --port 8080  # 指定代理端口
#

set -e
cd "$(dirname "$0")"

PROXY_PORT="${1:-19090}"
if [ "$1" = "--port" ]; then
    PROXY_PORT="$2"
fi

# 检查依赖
if ! python3 -c "import fastapi, httpx, uvicorn, jwt" 2>/dev/null; then
    echo "正在安装依赖..."
    pip3 install -r requirements.txt -q
fi

# 如果没有保存的 token，尝试从 CDP 提取
if [ ! -f data/token.json ]; then
    echo "首次运行，尝试从 WorkBuddy 提取 token..."
    if python3 -c "import websockets" 2>/dev/null; then
        python3 extract_token.py --save || echo "⚠ CDP 提取失败，请手动设置 WB_TOKEN"
    else
        echo "⚠ websockets 未安装，跳过 CDP 提取"
        echo "  安装: pip3 install websockets"
        echo "  或手动设置: export WB_TOKEN=<your-jwt>"
    fi
fi

echo ""
echo "╔══════════════════════════════════════════════════╗"
echo "║  WorkBuddy OpenAI-Compatible Reverse Proxy      ║"
echo "╠══════════════════════════════════════════════════╣"
echo "║  端口:    http://127.0.0.1:${PROXY_PORT}/v1          ║"
echo "║  API Key: wb-proxy-key                          ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""

PROXY_PORT=$PROXY_PORT exec python3 server.py
