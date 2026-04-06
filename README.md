# WorkBuddy Proxy

将 WorkBuddy 内置的 AI 模型通过 **OpenAI 兼容 API** 暴露，可直接接入 Cherry Studio、ChatGPT-Next-Web、Cursor 等第三方工具。

> **无需公司 VPN 或特殊网络环境**，`copilot.tencent.com` 是公网 SaaS 服务，普通网络直连即可。

---

## 可用模型

共 **30** 个模型，全部经过可用性验证（2026-04-06）。

| 类别 | 模型 ID | 备注 |
|------|---------|------|
| **DeepSeek** (9) | `deepseek-r1` · `deepseek-v3` · `deepseek-v3.2` · `deepseek-v3-1` · `deepseek-v3-0324` · `deepseek-v3-1-volc` · `deepseek-v3-0324-lkeap` · `deepseek-r1-0528-lkeap` · `deepseek-v3-2-volc-ioa` | 全部稳定 |
| **Claude** (7) | `claude-opus-4.6` · `claude-opus-4.6-1m` · `claude-sonnet-4.6` · `claude-sonnet-4.6-1m` · `claude-opus-4.5` · `claude-4.5` · `claude-haiku-4.5` | 推荐首选；`-1m` 后缀为 1M 上下文版本 |
| **Gemini** (2) | `gemini-3.0-pro` · `gemini-3.1-flash-lite` | `gemini-3.0-pro` 偶有间歇性空响应 |
| **GLM** (7) | `glm-4.6` · `glm-4.7` · `glm-4.7-ioa` · `glm-5.0-ioa` · `glm-5.0-turbo-ioa` · `glm-5v-turbo` · `glm-5v-turbo-ioa` | `5v` 系列支持视觉 |
| **混元** (3) | `hunyuan-2.0-instruct` · `hunyuan-2.0-instruct-ioa` · `hunyuan-2.0-thinking-ioa` | `thinking` 为推理模型 |
| **Kimi** (1) | `kimi-k2.5-ioa` | |
| **默认** (1) | `codewise-default-model-v2` | WorkBuddy 默认路由模型 |

> 完整的模型测试报告参见 [MODEL_ANALYSIS.md](./MODEL_ANALYSIS.md)。

---

## 前置准备

根据你的操作系统，准备以下环境：

### Windows 11

| 项目 | 说明 |
|------|------|
| **Python 3.10+** | 从 [python.org](https://www.python.org/downloads/) 下载安装，**安装时勾选 "Add Python to PATH"** |
| **Git** | 从 [git-scm.com](https://git-scm.com/download/win) 下载安装 |
| **WorkBuddy** | 已安装并**至少登录过一次**（确保有有效会话） |
| **Docker Desktop**（可选） | 如需 Docker 方式运行，从 [docker.com](https://www.docker.com/products/docker-desktop/) 安装，并在 Settings → General 中勾选 **"Start Docker Desktop when you sign in"** |

> **验证 Python 安装**：打开 PowerShell，执行 `python --version`，应输出 `Python 3.10.x` 或更高版本。

### macOS

| 项目 | 说明 |
|------|------|
| **Python 3.10+** | 推荐通过 `brew install python` 安装 |
| **Git** | macOS 自带，或通过 `brew install git` 安装 |
| **WorkBuddy** | 已安装并**至少登录过一次** |
| **Docker Desktop**（可选） | 从 [docker.com](https://www.docker.com/products/docker-desktop/) 安装 |

---

## 快速开始

### 第一步：克隆仓库

```bash
git clone https://github.com/buuzzy/workbuddy-proxy.git
cd workbuddy-proxy
```

---

### 第二步：提取 Token（首次 & Token 失效时）

Token 的有效期约 **1 年**，正常情况下提取一次即可长期使用。

<details>
<summary><b>Windows（PowerShell）</b></summary>

```powershell
# 1. 以调试模式启动 WorkBuddy
& "$env:LOCALAPPDATA\Programs\WorkBuddy\WorkBuddy.exe" --remote-debugging-port=9222

# 如果上面的路径不对，可以这样查找 WorkBuddy 位置：
# Get-Command WorkBuddy -ErrorAction SilentlyContinue | Select-Object Source
# 或者右键 WorkBuddy 快捷方式 → 属性 → 查看「目标」路径
# 常见路径：
#   C:\Users\<用户名>\AppData\Local\Programs\WorkBuddy\WorkBuddy.exe
#   C:\Program Files\WorkBuddy\WorkBuddy.exe

# 2. 新开一个 PowerShell 窗口，安装依赖并提取 Token
python -m pip install httpx websockets pyjwt
python extract_token.py --save

# 3. 看到 "已保存到 data\token.json" 后，可以关闭 WorkBuddy
```

</details>

<details>
<summary><b>macOS（Terminal）</b></summary>

```bash
# 1. 以调试模式启动 WorkBuddy
/Applications/WorkBuddy.app/Contents/MacOS/Electron --remote-debugging-port=9222

# 2. 新开一个终端，安装依赖并提取 Token
pip3 install httpx websockets pyjwt
python3 extract_token.py --save

# 3. 看到 "已保存到 data/token.json" 后，可以关闭 WorkBuddy
```

</details>

> **提取失败？** 检查以下几点：
> - WorkBuddy 是否已登录（打开 WorkBuddy 能正常使用 AI 功能）
> - 是否用 `--remote-debugging-port=9222` 参数启动的
> - 端口 9222 是否被占用（可以换成 9223，对应 `python extract_token.py --port 9223 --save`）

---

### 第三步：启动服务

有两种方式可选：**Docker（推荐）** 或 **直接运行 Python**。

#### 方式一：Docker（推荐）

适用于 Windows 和 macOS，安装好 Docker Desktop 后：

```bash
docker compose up -d
```

看到 `Container workbuddy-proxy Started` 即表示启动成功。

#### 方式二：直接运行 Python

<details>
<summary><b>Windows</b></summary>

```powershell
# 安装依赖
python -m pip install -r requirements.txt

# 启动服务
python server.py

# 或使用一键启动脚本
.\start.ps1
.\start.ps1 -Port 8080   # 指定端口
```

</details>

<details>
<summary><b>macOS</b></summary>

```bash
# 安装依赖
pip3 install -r requirements.txt

# 启动服务
python3 server.py

# 或使用一键启动脚本
./start.sh
./start.sh --port 8080   # 指定端口
```

</details>

#### 验证服务状态

```powershell
# Windows PowerShell
Invoke-RestMethod http://127.0.0.1:19090/health

# macOS / Linux
curl http://127.0.0.1:19090/health
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

## Windows 持久化运行

在 Windows 主机上让服务**开机自启、后台常驻**，有以下几种方案：

### 方案一：Docker Desktop 自动启动（最简单）

Docker Desktop 默认会随 Windows 启动，容器配置了 `restart: unless-stopped`，所以 **开机后服务自动恢复**，无需额外配置。

确认设置：
1. Docker Desktop → Settings → General → 勾选 **"Start Docker Desktop when you sign in"**
2. 确认容器已用 `docker compose up -d` 启动过

之后每次开机，容器自动启动。

### 方案二：Windows 任务计划程序（不用 Docker）

适合不想装 Docker、直接用 Python 运行的场景。

**1. 创建启动脚本**

项目已包含 `start.ps1`，它会自动检查依赖、提取 Token 并启动服务。

**2. 配置任务计划**

打开 PowerShell（管理员），执行以下命令创建开机自启任务：

```powershell
$action = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument "-ExecutionPolicy Bypass -WindowStyle Hidden -File `"C:\path\to\workbuddy-proxy\start.ps1`"" `
    -WorkingDirectory "C:\path\to\workbuddy-proxy"

$trigger = New-ScheduledTaskTrigger -AtLogon

$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 1)

Register-ScheduledTask `
    -TaskName "WorkBuddyProxy" `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Description "WorkBuddy OpenAI-compatible reverse proxy"
```

> **注意**：将 `C:\path\to\workbuddy-proxy` 替换为你的实际项目路径。

**管理任务：**

```powershell
# 查看任务状态
Get-ScheduledTask -TaskName "WorkBuddyProxy"

# 手动启动
Start-ScheduledTask -TaskName "WorkBuddyProxy"

# 停止任务
Stop-ScheduledTask -TaskName "WorkBuddyProxy"

# 删除任务
Unregister-ScheduledTask -TaskName "WorkBuddyProxy" -Confirm:$false
```

### 方案三：NSSM 注册为 Windows 服务（最稳定）

[NSSM](https://nssm.cc/) 可以将任意程序注册为 Windows 服务，支持自动重启、日志记录等。

```powershell
# 1. 下载 NSSM（https://nssm.cc/download）
# 2. 解压后将 nssm.exe 放到 PATH 目录（如 C:\Windows）

# 3. 安装服务（交互式配置）
nssm install WorkBuddyProxy

# 在弹出的界面中配置：
#   Path:              C:\Users\<用户名>\AppData\Local\Programs\Python\Python312\python.exe
#   Startup directory: C:\path\to\workbuddy-proxy
#   Arguments:         server.py
#   在 "Exit actions" 标签页，设置 Restart delay: 5000 (毫秒)

# 4. 启动服务
nssm start WorkBuddyProxy
```

**管理服务：**

```powershell
nssm status WorkBuddyProxy    # 查看状态
nssm restart WorkBuddyProxy   # 重启
nssm stop WorkBuddyProxy      # 停止
nssm remove WorkBuddyProxy    # 删除服务
```

---

## 日常使用

### Docker 方式

服务配置了 `restart: unless-stopped`，**开机后 Docker Desktop 自动启动容器**，无需手动操作。

| 操作 | 命令 |
|------|------|
| 查看状态 | `docker ps` |
| 查看日志 | `docker compose logs -f` |
| 重启 | `docker compose restart` |
| 停止 | `docker compose down` |
| 启动 | `docker compose up -d` |

### Python 直接运行方式

| 操作 | Windows (PowerShell) | macOS (Terminal) |
|------|---------------------|------------------|
| 启动 | `.\start.ps1` 或 `python server.py` | `./start.sh` 或 `python3 server.py` |
| 停止 | `Ctrl+C` | `Ctrl+C` |

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

**Windows：**

```powershell
# 1. 调试模式启动 WorkBuddy
& "$env:LOCALAPPDATA\Programs\WorkBuddy\WorkBuddy.exe" --remote-debugging-port=9222

# 2. 新开 PowerShell，重新提取 Token
python extract_token.py --save

# 3. 重启服务
docker compose restart
# 或者如果用 Python 直接运行，重启 start.ps1

# 4. 验证
Invoke-RestMethod http://127.0.0.1:19090/health
```

**macOS：**

```bash
# 1. 调试模式启动 WorkBuddy
/Applications/WorkBuddy.app/Contents/MacOS/Electron --remote-debugging-port=9222

# 2. 重新提取 Token
python3 extract_token.py --save

# 3. 重启服务
docker compose restart

# 4. 验证
curl http://127.0.0.1:19090/health
```

### 如何判断 Token 是否有效

```bash
# 健康检查（Windows 用 Invoke-RestMethod，macOS 用 curl）
curl http://127.0.0.1:19090/health
```

| 返回 | 含义 |
|------|------|
| `{"status":"ok", ...}` | 正常，Token 有效 |
| `{"status":"degraded", "has_token":false, ...}` | 无 Token，需要提取 |
| `{"status":"degraded", "expired":true, ...}` | Token 过期，等待自动续期或手动更新 |

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

**Q: Windows 上 PowerShell 提示"无法加载脚本"？**
A: 执行策略限制。以管理员身份打开 PowerShell，执行：
```powershell
Set-ExecutionPolicy RemoteSigned -Scope CurrentUser
```

**Q: Windows 任务计划程序启动后窗口一闪而过？**
A: 这是正常现象，`-WindowStyle Hidden` 参数会隐藏窗口。服务在后台运行，通过 `Invoke-RestMethod http://127.0.0.1:19090/health` 验证。
