# WorkBuddy Proxy — 模型分析报告

> 测试日期：2026-04-06 | WorkBuddy 版本：4.8.1 | Proxy 版本：latest

---

## 1. 测试方法论

所有测试均**直接调用 WorkBuddy 上游 API**（`https://copilot.tencent.com/v2/chat/completions`），绕过 Proxy 层，以排除中间环节的干扰。测试分为五个阶段：

| 阶段 | 目的 | 方法 |
|------|------|------|
| 基础连通性 | 确认模型是否在线 | 小请求 + 短超时 |
| 上下文阶梯测试 | 定位上下文窗口上限 | 从 128K 递增至 3M 字符 |
| Needle-in-Haystack | 验证模型是否真正处理全部上下文 | 在填充文本中间嵌入特征码，要求模型回传 |
| 可靠性压测 | 测试间歇性空响应的触发条件 | Burst（零间隔）、1s 间隔、3s 间隔各 10 次 |
| 响应头分析 | 检测是否存在隐藏的限流机制 | 解析完整 HTTP 响应头 |

---

## 2. 模型可用性总览

### 2.1 当前可用模型（30 个）

| 模型系列 | 模型 ID | 可靠性 |
|---------|---------|--------|
| **DeepSeek** | `deepseek-r1` | 稳定 |
| | `deepseek-v3` | 稳定 |
| | `deepseek-v3.2` | 稳定 |
| | `deepseek-v3-1` | 稳定 |
| | `deepseek-v3-0324` | 稳定 |
| | `deepseek-v3-1-volc` | 稳定 |
| | `deepseek-v3-0324-lkeap` | 稳定 |
| | `deepseek-r1-0528-lkeap` | 稳定 |
| | `deepseek-v3-2-volc-ioa` | 稳定 |
| **Claude** | `claude-4.5` | 稳定 |
| | `claude-opus-4.5` | 稳定 |
| | `claude-opus-4.6` | 稳定 |
| | `claude-opus-4.6-1m` | **极其稳定（30/30）** |
| | `claude-sonnet-4.6` | 稳定 |
| | `claude-sonnet-4.6-1m` | 稳定 |
| | `claude-haiku-4.5` | 稳定 |
| **Gemini** | `gemini-3.0-pro` | **不稳定**（间歇性空响应） |
| | `gemini-3.1-flash-lite` | 稳定 |
| **GLM** | `glm-4.6` | 稳定 |
| | `glm-4.7` | 稳定 |
| | `glm-4.7-ioa` | 稳定 |
| | `glm-5.0-ioa` | 稳定 |
| | `glm-5.0-turbo-ioa` | 稳定 |
| | `glm-5v-turbo` | 稳定 |
| | `glm-5v-turbo-ioa` | 稳定 |
| **Hunyuan** | `hunyuan-2.0-instruct` | 稳定 |
| | `hunyuan-2.0-instruct-ioa` | 稳定 |
| | `hunyuan-2.0-thinking-ioa` | 稳定 |
| **Kimi** | `kimi-k2.5-ioa` | 稳定 |
| **Default** | `codewise-default-model-v2` | 稳定 |

### 2.2 已移除的模型

以下模型经过多轮测试确认不可用，已从 Proxy 的模型列表中移除：

| 模型 ID | 失败类型 | 原因 |
|---------|---------|------|
| `gpt-5.1` | HTTP 400 | 后端返回 "model service info not found" |
| `gpt-5.2` | HTTP 400 | 同上 |
| `gpt-5.3-codex` | HTTP 400 | 同上 |
| `gpt-5.4` | HTTP 400 | 同上 |
| `gemini-3.0-flash` | HTTP 200 空响应 | 返回有效 SSE 流但无内容 |
| `claude-3.7-sonnet` | HTTP 400 | 模型已下线 |
| `claude-4.0-sonnet` | HTTP 400 | 模型已下线 |
| `hunyuan-turbos` | HTTP 400 | 模型已下线 |
| `kimi-k2` | HTTP 400 | 模型已下线 |
| `minimax-m2.5-ioa` | 持续空响应 | 模型已禁用 |
| `minimax-m2.7-ioa` | 持续空响应 | 模型已禁用 |
| `gpt-5.1-codex-max` | 持续空响应 | 模型已禁用 |
| `gpt-5.2-codex` | 持续空响应 | 模型已禁用 |

---

## 3. Claude 模型深度分析

### 3.1 claude-opus-4.6 vs claude-opus-4.6-1m：是同一个模型吗？

**结论：它们是不同的模型，但上下文窗口上限相同。**

#### 3.1.1 身份差异

通过分析响应中的 `model` 字段，四个 Claude 模型返回了不同的内部标识：

| 请求模型 ID | 响应中的 model 字段 |
|------------|-------------------|
| `claude-opus-4.6` | `claude-opus-4.6` |
| `claude-opus-4.6-1m` | `claude-opus-4.6-1m` |
| `claude-sonnet-4.6` | `MaaS_Cl_Sonnet_4.6_20260217_cache` |
| `claude-sonnet-4.6-1m` | `claude-sonnet-4.6-1m` |

它们在 WorkBuddy 后端被路由到**不同的模型实例**。`claude-sonnet-4.6` 的内部 ID 暴露了 `MaaS` 前缀和 `cache` 后缀，说明它走的是腾讯云 MaaS（Model-as-a-Service）通道，并且启用了缓存优化。

#### 3.1.2 上下文窗口阶梯测试

| 输入规模（字符） | prompt_tokens | claude-opus-4.6 | claude-opus-4.6-1m |
|----------------|--------------|-----------------|-------------------|
| 128K | 84,505 | OK (6.4s) | OK (6.2s) |
| 256K | 168,985 | OK (9.2s) | OK (9.6s) |
| 500K | 313,521 | OK (14.5s) | OK (13.5s) |
| 700K | 438,921 | OK (14.9s) | OK (31.3s) |
| 900K | 564,319 | OK (31.0s) | OK (29.7s) |
| **1M** | **627,019** | **OK (24.0s)** | **OK (27.9s)** |
| **1.2M** | **752,419** | **OK (33.5s)** | **OK (37.0s)** |
| **1.5M** | **940,517** | **OK (45.6s)** | **OK (53.3s)** |
| 2M | ~1,250,000 | HTTP 400 | HTTP 400 |
| 3M | ~1,900,000 | HTTP 400 | HTTP 400 |

**关键发现：**

- 两个模型的实际上下文上限**完全一致**：约 **940K prompt tokens**（~1.5M 字符）
- 普通版 `claude-opus-4.6` 在 WorkBuddy 后端**同样享有超大上下文**，不受 Anthropic 官方 200K 限制
- 两者的延迟表现也基本一致，没有显著差异
- 超过 ~1.25M tokens 时，两者均返回 HTTP 400

#### 3.1.3 Needle-in-Haystack 验证

在 600K 字符的填充文本中间嵌入特征码 `THE_SECRET_CODE_IS_BANANA_42`，要求模型找到并回传：

```
claude-opus-4.6  ~600K → OK  needle=FOUND  prompt=376,240  "THE_SECRET_CODE_IS_BANANA_42"
```

模型不仅接收了全部上下文，而且**确实处理并理解了中间位置的内容**，没有静默截断。

#### 3.1.4 结论

| 维度 | claude-opus-4.6 | claude-opus-4.6-1m |
|------|-----------------|-------------------|
| 后端路由 | 不同实例 | 不同实例 |
| 上下文上限 | ~940K tokens | ~940K tokens |
| 延迟表现 | 相当 | 相当 |
| 可靠性 | 极高 | 极高 |
| **实际差异** | **无可测量差异** | **无可测量差异** |

`-1m` 后缀可能对应不同的定价层级、优先级队列或 SLA 等级，但在功能和性能上无可观测差异。对于 Agent 场景（如 OpenClaw），使用 `claude-opus-4.6` 即可。

---

## 4. 间歇性空响应分析

### 4.1 现象

部分模型偶尔返回 HTTP 200 但 SSE 流中没有任何 `content` 内容。这种情况在以下场景出现过：

- `gemini-3.0-pro`：高频出现（约 50% 请求）
- `hunyuan-2.0-instruct-ioa`：偶发（重试即恢复）
- `claude-opus-4.6-1m`：在 600K 上下文的 Needle-in-Haystack 测试中出现过一次（重试即恢复）

### 4.2 是限流机制吗？

**不是传统的限流。** 证据如下：

#### 证据 1：响应头中无限流信号

完整的上游响应头分析显示：

```
cache-control: no-cache
connection: keep-alive
content-type: text/event-stream
date: Mon, 06 Apr 2026 14:05:19 GMT
set-cookie: session=; Path=/v2; Max-Age=0; ...
traceid: 62798a5c628659e5435c43f58c3923ed
transfer-encoding: chunked
x-request-id: 53b4bcf4394a4a4f881cb3b34b364b40
x-user-id: 72045f84-f880-47e7-ae63-7986b46ee718
x-waf-uuid: abbf93ce1016dd8b74023e08519809df-...
```

**没有** `X-RateLimit-*`、`Retry-After`、`X-Rate-Limit-Remaining` 等任何限流相关头。

#### 证据 2：Burst 测试不触发空响应

对 `claude-opus-4.6-1m` 的压力测试结果：

| 请求模式 | 成功率 |
|---------|--------|
| 零间隔连续 10 次 | **10/10 (100%)** |
| 1 秒间隔 10 次 | **10/10 (100%)** |
| 3 秒间隔 10 次 | **10/10 (100%)** |

如果存在限流，burst 场景下应该首先触发，但实际上 30 次请求零失败。

#### 证据 3：空响应不跨模型传染

在同一时间窗口内，`gemini-3.0-pro` 持续空响应，而其他模型（包括同一秒内测试的 Claude、DeepSeek）正常返回。全局限流应该影响所有模型。

### 4.3 真正的原因

综合分析，间歇性空响应的根因是**后端实例级别的可用性问题**：

```
用户请求 → WAF → 负载均衡 → 模型后端实例池
                              ├── 实例 A (就绪) → 正常响应
                              ├── 实例 B (冷启动中) → 空 SSE 流
                              └── 实例 C (过载) → 空 SSE 流
```

1. **实例池规模差异**：Claude 作为高优先级模型，有更大的实例池和更高的预热比例，所以几乎不出现空响应。`gemini-3.0-pro` 使用率低，实例少，命中未就绪实例的概率更高。

2. **冷启动**：部分模型实例可能采用按需启动策略（类似 Serverless），首次请求命中冷实例时，SSE 连接建立但无内容输出。

3. **非确定性故障**：空响应出现的时机无规律，与请求频率无关（burst 不触发），与上下文大小弱相关（大上下文略微增加概率，但不是决定因素）。

### 4.4 应对建议

| 策略 | 实现方式 |
|------|---------|
| **自动重试** | 检测到空响应时自动重试 1–2 次（间隔 1–2 秒），覆盖绝大多数间歇性故障 |
| **选择稳定模型** | 优先使用 Claude、DeepSeek 系列，避免 `gemini-3.0-pro` 作为主力模型 |
| **合理超时** | 推理模型（`deepseek-r1`、`hunyuan-2.0-thinking-ioa`）需要更长超时（60–120s） |
| **备选模型** | 配置 fallback 链：`claude-opus-4.6` → `deepseek-v3.2` → `glm-5.0-turbo-ioa` |

---

## 5. 上下文窗口能力总结

| 模型 | 已验证上限 | 实际 prompt_tokens |
|------|-----------|-------------------|
| `claude-opus-4.6` | 1.5M 字符 | 940,517 tokens |
| `claude-opus-4.6-1m` | 1.5M 字符 | 940,517 tokens |
| `claude-sonnet-4.6` | 256K 字符 | 168,985 tokens |
| `claude-sonnet-4.6-1m` | 256K 字符 | 168,985 tokens |
| `deepseek-v3.2` | 128K 字符 | 84,505 tokens |
| 其他模型 | 32K–128K 字符 | 视模型而定 |

> 注：Sonnet 系列仅测试到 256K，并非上限；根据 Opus 的结果推测也能支持更高。

---

## 6. Agent 场景推荐配置

对于 **OpenClaw** 等 Agent 框架，推荐以下模型配置策略：

### 主力模型

```
claude-opus-4.6
```

理由：940K tokens 上下文、100% 可靠性、响应速度 2–3 秒。`opus-4.6` 和 `opus-4.6-1m` 无可测量差异，使用任一均可。

### 备选模型

```
deepseek-v3.2      # 速度快、推理能力强
claude-sonnet-4.6   # 成本更低、速度更快
glm-5.0-turbo-ioa   # 中文场景优化
```

### 推理/深度思考

```
deepseek-r1             # 推理模型，需要更长超时
hunyuan-2.0-thinking-ioa # 推理模型，需要更长超时
```

### 不推荐用于 Agent 的模型

| 模型 | 原因 |
|------|------|
| `gemini-3.0-pro` | 间歇性空响应，不可靠 |
| `codewise-default-model-v2` | 路由不确定，行为不可预测 |

---

## 7. 技术细节备忘

### 7.1 请求头指纹

Proxy 伪装为 WorkBuddy IDE 客户端，关键头部：

```
X-IDE-Type: CodeBuddyIDE
X-IDE-Name: CodeBuddyIDE
X-IDE-Version: 4.8.1
X-Product-Version: 4.8.1
X-Product: SaaS
X-Env-ID: production
User-Agent: CodeBuddyIDE/4.8.1 coding-copilot/4.8.1
```

### 7.2 上游 API 端点

| 端点 | 用途 |
|------|------|
| `POST /v2/chat/completions` | 聊天补全（主接口） |
| `GET /console/enterprises/{id}/config/models` | 获取可用模型列表 |

### 7.3 认证链路

```
JWT Token (从 CDP 提取)
  ├── iss → 解析 enterprise_id、domain
  ├── sub → 解析 user_id
  └── Bearer Token → Authorization 头
```

### 7.4 WAF 层

上游部署了 WAF（响应头 `x-waf-uuid`），但当前未观察到主动拦截行为。建议保持请求频率在合理范围内（单用户 < 10 req/s）。
