# WorkBuddy Proxy

将 WorkBuddy 内置的 AI 模型通过 OpenAI 兼容 API 暴露，可直接接入 Cherry Studio、ChatGPT-Next-Web、Cursor 等第三方工具。

## 可用模型

| 类别 | 模型 |
|------|------|
| **DeepSeek** | `deepseek-r1`, `deepseek-v3`, `deepseek-v3-1`, `deepseek-v3-0324` |
| **Claude** | `claude-opus-4.6`, `claude-opus-4.5`, `claude-4.5`, `claude-haiku-4.5` |
| **GPT** | `gpt-5.4`, `gpt-5.3-codex`, `gpt-5.2`, `gpt-5.1` |
| **Gemini** | `gemini-3.0-pro`, `gemini-3.0-flash`, `gemini-3.1-flash-lite` |
| **GLM** | `glm-5.0-turbo-ioa`, `glm-5.0-ioa`, `glm-4.7`, `glm-4.6` |
| **其他** | `hunyuan-2.0-instruct`, `kimi-k2`, `minimax-m2.7-ioa` 等 |

## 快速开始

### 前提条件

- 已安装 [Docker Desktop](https://www.docker.com/products/docker-desktop/) 或 [OrbStack](https://orbstack.dev/)
- WorkBuddy 已登录（首次提取 Token 时需要）

### 一、首次设置（提取 Token）

1. 以调试模式启动 WorkBuddy：

```bash
/Applications/WorkBuddy.app/Contents/MacOS/Electron --remote-debugging-port=9222
```

2. 提取并保存 Token：

```bash
pip3 install httpx websockets pyjwt
python3 extract_token.py --save
```

3. 提取成功后可以关闭 WorkBuddy。

### 二、启动服务

```bash
docker compose up -d
```

服务将在 `http://127.0.0.1:19090` 启动。

### 三、配置第三方工具

| 配置项 | 值 |
|--------|------|
| **Base URL** | `http://127.0.0.1:19090/v1` |
| **API Key** | `wb-proxy-key` |

### 四、验证

```bash
# 健康检查
curl http://127.0.0.1:19090/health

# 模型列表
curl -H "Authorization: Bearer wb-proxy-key" http://127.0.0.1:19090/v1/models

# 发送消息
curl http://127.0.0.1:19090/v1/chat/completions \
  -H "Authorization: Bearer wb-proxy-key" \
  -H "Content-Type: application/json" \
  -d '{"model":"deepseek-v3","messages":[{"role":"user","content":"你好"}]}'
```

## 日常使用

| 操作 | 命令 |
|------|------|
| 启动 | `docker compose up -d` |
| 停止 | `docker compose down` |
| 查看日志 | `docker compose logs -f` |
| 重启 | `docker compose restart` |

服务配置了 `restart: unless-stopped`，Docker/OrbStack 启动后容器会自动恢复。

## Token 管理

- Token 缓存在 `data/token.json`（已 gitignore）
- 到期前 5 分钟自动通过 Refresh Token 续期
- 如果 Refresh Token 也失效，重新执行「首次设置」步骤即可

## 不用 Docker？

也可以直接运行：

```bash
pip3 install -r requirements.txt
python3 server.py
# 或
./start.sh
```

## 配置项

复制 `.env.example` 为 `.env` 按需修改：

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `PROXY_PORT` | `19090` | 监听端口 |
| `PROXY_API_KEY` | `wb-proxy-key` | API Key |
| `CDP_URL` | `http://127.0.0.1:9222` | CDP 调试地址 |

User ID、Enterprise ID、Domain 等信息会从 JWT Token 自动解析，无需手动配置。
