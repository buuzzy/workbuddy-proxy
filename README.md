# WorkBuddy Proxy

将 WorkBuddy 内置的 AI 模型通过 **OpenAI 兼容 API** 暴露，可直接接入 Cherry Studio、ChatGPT-Next-Web、Cursor 等第三方工具。

> **无需公司 VPN 或特殊网络环境**，`copilot.tencent.com` 是公网 SaaS 服务，普通网络直连即可。

---

## 可用模型

| 类别 | 模型 ID |
|------|---------|
| **DeepSeek** | `deepseek-r1` · `deepseek-v3` · `deepseek-v3-1` · `deepseek-v3-0324` |
| **Claude** | `claude-opus-4.6` · `claude-opus-4.5` · `claude-4.5` · `claude-haiku-4.5` |
| **GPT** | `gpt-5.4` · `gpt-5.3-codex` · `gpt-5.2` · `gpt-5.1` |
| **Gemini** | `gemini-3.0-pro` · `gemini-3.0-flash` · `gemini-3.1-flash-lite` |
| **GLM** | `glm-5.0-turbo-ioa` · `glm-5.0-ioa` · `glm-4.7` · `glm-4.6` |
| **混元** | `hunyuan-2.0-instruct` · `hunyuan-turbos` · `hunyuan-2.0-thinking-ioa` |
| **其他** | `kimi-k2` · `kimi-k2.5-ioa` · `minimax-m2.7-ioa` 等 |

---

## 快速开始

### 前提条件

- [Docker Desktop](https://www.docker.com/products/docker-desktop/)（macOS / Windows 均可）
- WorkBuddy 已安装并**登录过**
- Python 3.10+（仅首次提取 Token 时需要）

---

### 第一步：克隆仓库

```bash
git clone https://github.com/buuzzy/workbuddy-proxy.git
cd workbuddy-proxy
```

---

### 第二步：提取 Token（首次 & Token 失效时）

Token 的有效期约 **1 年**，正常情况下提取一次即可长期使用。

#### macOS

```bash
# 1. 以调试模式启动 WorkBuddy
/Applications/WorkBuddy.app/Contents/MacOS/Electron --remote-debugging-port=9222

# 2. 新开一个终端，安装依赖并提取 Token
pip3 install httpx websockets pyjwt
python3 extract_token.py --save

# 3. 看到 "已保存到 data/token.json" 后，可以关闭 WorkBuddy
```

#### Windows

```powershell
# 1. 以调试模式启动 WorkBuddy（在 PowerShell 中运行）
& "$env:LOCALAPPDATA\Programs\WorkBuddy\WorkBuddy.exe" --remote-debugging-port=9222

# 如果上面的路径不对，可以这样找到 WorkBuddy 的安装位置：
# Get-Command WorkBuddy -ErrorAction SilentlyContinue | Select-Object Source
# 或者右键 WorkBuddy 快捷方式 → 属性 → 查看「目标」路径
# 常见路径：
#   C:\Users\<用户名>\AppData\Local\Programs\WorkBuddy\WorkBuddy.exe
#   C:\Program Files\WorkBuddy\WorkBuddy.exe

# 2. 新开一个 PowerShell，安装依赖并提取 Token
pip install httpx websockets pyjwt
python extract_token.py --save

# 3. 看到 "已保存到 data\token.json" 后，可以关闭 WorkBuddy
```

> **提取失败？** 检查以下几点：
> - WorkBuddy 是否已登录（打开 WorkBuddy 能正常使用 AI 功能）
> - 是否用 `--remote-debugging-port=9222` 参数启动的
> - 端口 9222 是否被占用（可以换成 9223，对应 `python extract_token.py --port 9223 --save`）

---

### 第三步：启动服务

```bash
docker compose up -d
```

看到 `Container workbuddy-proxy Started` 即表示启动成功。

验证服务状态：

```bash
# macOS / Linux
curl http://127.0.0.1:19090/health

# Windows PowerShell
Invoke-RestMethod http://127.0.0.1:19090/health
```

返回 `{"status":"ok","has_token":true,"expired":false}` 即表示一切正常。

---

### 第四步：配置第三方工具

在 Cherry Studio / ChatGPT-Next-Web / Cursor 等工具中：

| 配置项 | 值 |
|--------|------|
| **Base URL** | `http://127.0.0.1:19090/v1` |
| **API Key** | `wb-proxy-key` |

选择模型时填写上方表格中的**模型 ID**（如 `deepseek-v3`、`claude-opus-4.6`）。

---

## 日常使用

服务配置了 `restart: unless-stopped`，**开机后 Docker Desktop 自动启动容器**，无需手动操作。

| 操作 | 命令 |
|------|------|
| 查看状态 | `docker ps` |
| 查看日志 | `docker compose logs -f` |
| 重启 | `docker compose restart` |
| 停止 | `docker compose down` |
| 启动 | `docker compose up -d` |

---

## Token 管理

### Token 有效期

| Token | 有效期 | 说明 |
|-------|--------|------|
| Access Token | ~1 年 | 主认证令牌 |
| Refresh Token | 更长 | 用于自动续期 Access Token |

### 自动续期

代理内置了自动续期逻辑：Access Token 到期前 5 分钟，会用 Refresh Token 自动调用 WorkBuddy API 获取新 Token，**全程无需人工干预**。

### 手动更新 Token（当自动续期也失效时）

如果长时间未使用导致 Refresh Token 也过期，需要手动重新提取：

```bash
# 1. 调试模式启动 WorkBuddy（见「第二步」的平台对应命令）

# 2. 重新提取 Token
python3 extract_token.py --save      # macOS
python extract_token.py --save       # Windows

# 3. 重启容器加载新 Token
docker compose restart

# 4. 验证
curl http://127.0.0.1:19090/health   # 应返回 status: ok
```

### 如何判断 Token 是否有效

```bash
# 健康检查
curl http://127.0.0.1:19090/health
```

| 返回 | 含义 |
|------|------|
| `{"status":"ok", ...}` | 正常，Token 有效 |
| `{"status":"degraded", "has_token":false, ...}` | 无 Token，需要提取 |
| `{"status":"degraded", "expired":true, ...}` | Token 过期，等待自动续期或手动更新 |

---

## 不用 Docker？

也可以直接用 Python 运行：

```bash
pip3 install -r requirements.txt
python3 server.py
```

---

## 配置项

复制 `.env.example` 为 `.env` 按需修改：

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `PROXY_PORT` | `19090` | 代理监听端口 |
| `PROXY_API_KEY` | `wb-proxy-key` | 客户端使用的 API Key |
| `CDP_URL` | `http://127.0.0.1:9222` | CDP 调试地址 |

> User ID、Enterprise ID、Domain 会从 JWT Token **自动解析**，无需手动配置。

---

## 常见问题

**Q: 公司网络能检测到吗？**
A: 代理只是本地转发请求到 `copilot.tencent.com`，和你正常用 WorkBuddy 的网络流量完全一样。

**Q: 可以在家使用吗？**
A: 可以。`copilot.tencent.com` 是公网服务，任何网络环境都能用。

**Q: 多人能共用一个 Token 吗？**
A: 技术上可以，但不建议。每个人应该用自己的 WorkBuddy 账号提取 Token。

**Q: Docker 构建失败（TLS 证书错误）？**
A: 网络代理（如 Clash）可能干扰 Docker 拉取镜像。关闭代理后重试 `docker compose up -d --build`。

**Q: 端口 19090 被占用？**
A: 修改 `docker-compose.yml` 中的端口映射（如改为 `29090:19090`），Base URL 对应改为 `http://127.0.0.1:29090/v1`。
