# AWS MCP Server vs DevOps Agent On-Demand Conversation 调研

## 一、AWS MCP Server

### 1.1 是什么

Agent Toolkit for AWS 是 AWS 提供的一套工具集，让 AI 编码代理（如 Claude Code、Cursor、Codex、Kiro、Windsurf、Cline）能安全地在 AWS 上构建、部署和管理应用。核心是一个**托管的 MCP Server**，通过单一端点提供所有功能，免费使用（仅按 AWS 资源标准计费）。

### 1.2 四大组件

| 组件 | 说明 |
|------|------|
| **AWS MCP Server** | 托管服务器，通过 MCP 协议访问 AWS |
| **Agent Skills** | 精选指令包，按需加载，指导代理完成复杂任务 |
| **Plugins** | 一键安装包（捆绑 MCP 配置 + Skills） |
| **Rules Files** | 项目级配置，设置代理的护栏和偏好 |

### 1.3 提供的工具

#### 知识工具（无需认证）

| 工具 | 说明 |
|------|------|
| `aws___search_documentation` | 搜索 AWS 文档、API 参考、服务指南、Skills |
| `aws___read_documentation` | 读取文档并转为 markdown |
| `aws___recommend` | 获取内容推荐 |
| `aws___list_regions` | 列出所有 AWS 区域 |
| `aws___get_regional_availability` | 查服务/功能的区域可用性 |
| `aws___retrieve_skill` | 检索特定域的技能指导 |

#### API 工具（需 IAM 认证）

| 工具 | 说明 |
|------|------|
| `aws___call_aws` | 执行 AWS API 调用（支持 15,000+ API） |
| `aws___suggest_aws_commands` | 获取 API 语法帮助（含新发布的 API） |
| `aws___run_script` | 在 AWS 云端沙箱中执行 Python 脚本（支持多步操作、并行调用） |
| `aws___get_presigned_url` | 生成 S3 预签名 URL |
| `aws___get_tasks` | 轮询异步任务状态 |

### 1.4 架构

```
本地 Mac                            AWS 云端
┌──────────────────┐              ┌─────────────────────────────┐
│ AI Agent         │              │  AWS MCP Server (托管)        │
│ (Claude Code等)  │  ──MCP请求──► │                             │
│                  │              │  ┌───────────────────────┐   │
│ mcp-proxy-for-aws│  ◄──结果返回──│  │ 沙箱环境 (run_script) │   │
│ (仅做SigV4签名)   │              │  │ - Python 运行时        │   │
└──────────────────┘              │  │ - AWS SDK (boto3)     │   │
                                  │  │ - 使用你的IAM凭证      │   │
                                  │  └───────────────────────┘   │
                                  └─────────────────────────────┘
```

- 本地只有轻量 proxy（`mcp-proxy-for-aws`），仅做 SigV4 签名
- Python 脚本在 AWS 基础设施上执行，隔离沙箱，执行完销毁
- 沙箱内只能调 AWS API，不能访问本地文件或任意互联网

### 1.5 安装配置

#### 先决条件

- 安装 `uv`（MCP proxy 依赖）
- AWS CLI ≥ 2.32.0 + IAM 凭证（可选，用于 API 工具）

#### Claude Code 安装

```bash
/plugin marketplace add aws/agent-toolkit-for-aws
/plugin install aws-core@agent-toolkit-for-aws
/reload-plugins
```

#### 通用 MCP 配置（Kiro / Cursor / Claude Desktop 等）

```json
{
  "mcpServers": {
    "aws-mcp": {
      "command": "uvx",
      "timeout": 100000,
      "transport": "stdio",
      "args": [
        "mcp-proxy-for-aws@latest",
        "https://aws-mcp.us-east-1.api.aws/mcp",
        "--metadata", "AWS_REGION=us-west-2"
      ]
    }
  }
}
```

#### Codex 配置

```toml
[mcp_servers.aws_mcp]
command = "uvx"
args = [
  "mcp-proxy-for-aws@latest",
  "https://aws-mcp.us-east-1.api.aws/mcp",
  "--metadata", "AWS_REGION=us-west-2"
]
startup_timeout_sec = 60
```

#### 可用区域端点

- US East (N. Virginia): `https://aws-mcp.us-east-1.api.aws/mcp`
- Europe (Frankfurt): `https://aws-mcp.eu-central-1.api.aws/mcp`

#### 认证

推荐使用 `aws login`（自动每 15 分钟轮换凭证，有效 12 小时）。

### 1.6 安全机制

- 自动注入两个 IAM 条件键：`aws:ViaAWSMCPService` 和 `aws:CalledViaAWSMCP`
- 可在 IAM 策略中区分 MCP 发起的操作 vs 直接 API 调用
- CloudTrail 记录所有 API 调用
- CloudWatch 指标监控代理活动
- 使用 SigV4 签名认证请求
- 建议使用最小权限 IAM 角色

### 1.7 附加插件

- **aws-agents** — 构建 AI Agent（API Gateway + AgentCore）
- **aws-data-analytics** — 数据湖、分析、ETL 工作流

---

## 二、AWS DevOps Agent — On-Demand Conversation

### 2.1 是什么

AWS DevOps Agent 的 On-Demand Tasks 是一款生成式 AI 驱动的对话助手，使运营团队能够使用自然语言查询应用架构、分析系统运行状况和访问调查见解。集成在 DevOps Agent Space Web 应用程序中。

### 2.2 核心能力

#### 资源查询

询问代理空间中的 AWS 资源（Lambda、DynamoDB、EKS、证书、基础设施配置），可根据运行时版本、容量设置或部署状态筛选。

示例：
- "有多少 Lambda 在使用 Python 3.8？"
- "我有即将过期的证书吗？"
- "列出所有包含按需计费的 DynamoDB 表"

#### 系统运行状况分析

查询当前和历史系统运行状况指标，包括警报状态、错误率、CPU 利用率和服务可用性。

示例：
- "过去 24 小时内触发了哪些警报？"
- "过去一小时内有 5xx 错误吗？"
- "我的 ECS 集群的 CPU 使用率是多少？"

#### 调查见解 & 调查指导

访问已完成和正在进行的调查信息，包括根本原因分析、假设探讨、日志审查和解决方案模式。可主动指导调查方向。

示例：
- "上个月最常见的事件原因是什么？"
- "关注支付服务的日志并更新您的 RCA"
- "探索 DynamoDB 限流导致问题的假设"

#### 预防性建议

使用特定标准查询事件预防建议，解释每项建议的影响和实施注意事项。

示例：
- "向我展示可以防止涉及 DynamoDB 的事件的建议"
- "哪些建议对系统弹性的影响最大？"

#### 生成工件 (Artifacts)

生成结构化报告和文档（运行状况摘要、错误报告、事件分析），支持版本化编辑。

示例：
- "为我的 Agent Space 生成每周运行状况报告"
- "创建上周所有 4xx 错误的报告"

#### 第三方可观测性工具集成

- Splunk 日志组
- Prometheus 指标及警报阈值
- Datadog 监视器
- New Relic 警报策略
- Dynatrace 仪表板配置

### 2.3 上下文感知

Chat 根据当前查看的页面自动调整响应：

| 页面 | 上下文范围 |
|------|----------|
| **拓扑** | 所有资源、架构和运行状况（资源配置、部署历史、可观测性集成） |
| **事件响应** | 调查趋势、解决时间和事件模式 |
| **调查详情** | 特定调查的上下文感知回复（日志、假设、根因、缓解计划） |
| **预防** | 事件预防建议的查询、优先级排序和影响分析 |

### 2.4 对话管理

- 对话历史保留 90 天
- 支持继续之前的讨论
- 对话在每个代理空间中隔离

### 2.5 IAM 权限

启用聊天所需的 IAM 权限：

- `aidevops:ListChats` — 查看聊天对话记录
- `aidevops:CreateChat` — 创建新的聊天对话
- `aidevops:SendMessage` — 发送消息并接收回复

---

## 三、对比分析

### 3.1 定位差异

| 维度 | AWS DevOps Agent (On-Demand) | AWS MCP Server |
|------|------------------------------|----------------|
| **目标用户** | 运维团队 / SRE / 值班人员 | 开发者 / AI 编码代理 |
| **使用场景** | 事件调查、运行状况监控、故障排查 | 在 AWS 上构建、部署、管理应用 |
| **交互界面** | 专属 Web 应用（DevOps Agent Space） | IDE / CLI 中的 AI 代理（Claude Code、Cursor 等） |
| **协议** | 专有 Web Chat 界面 | 开放的 MCP 协议 |
| **定价** | Pro tier（付费） | 免费（仅 AWS 资源计费） |

### 3.2 能力对比

| 能力 | DevOps Agent On-Demand | AWS MCP Server |
|------|----------------------|----------------|
| 查看 EC2 列表/状态 | ✅ 通过资源查询 | ✅ `aws___call_aws` |
| 查看 CloudWatch 告警 | ✅ 系统健康分析 | ✅ 调用 CloudWatch API |
| 查看日志 | ✅ 上下文感知，自动关联 | ✅ 需自行指定日志组 |
| 执行 AWS API（写操作） | ❌ 只读查询 | ✅ 15,000+ API，读写均可 |
| 运行脚本 | ❌ | ✅ `run_script` 沙箱 Python |
| 创建/修改资源 | ❌ | ✅ 受 IAM 权限控制 |
| 事件调查 & RCA | ✅ 核心能力（自动根因分析） | ❌ 需人工判断 |
| 调查指导 | ✅ 可引导关注特定日志/假设 | ❌ |
| 预防性建议 | ✅ 基于历史事件模式 | ❌ |
| 生成结构化报告 | ✅ 版本化工件 | ❌ 返回原始数据 |
| 对话历史 | ✅ 保留 90 天 | ❌ 依赖客户端上下文 |
| 上下文感知 | ✅ 根据页面自动调整 | ❌ 需用户明确指定 |
| 第三方可观测性工具 | ✅ Splunk/Datadog/Prometheus/New Relic/Dynatrace | ❌ 仅 AWS 原生服务 |
| 部署应用 | ❌ | ✅ |
| 编写代码 | ❌ | ✅（配合 AI 代理） |
| 搜索 AWS 文档 | ❌ | ✅ |

### 3.3 架构对比

```
DevOps Agent On-Demand                    AWS MCP Server

┌─────────────────────────┐              ┌──────────────────┐
│  DevOps Agent Space     │              │ 本地 IDE / CLI    │
│  (AWS 托管 Web 应用)     │              │ + AI 编码代理     │
│                         │              │ + mcp-proxy-for-aws│
│  ┌───────────────────┐  │              └────────┬─────────┘
│  │ Chat 面板 (左侧)   │  │                       │
│  │ - 上下文感知       │  │                       │ MCP 协议 + SigV4
│  │ - 对话历史         │  │                       ▼
│  │ - 工件生成         │  │              ┌──────────────────┐
│  └───────────────────┘  │              │ AWS MCP Server   │
│                         │              │ (托管端点)        │
│  连接到你的 AWS 账号     │              │ - 文档搜索        │
│  + 第三方监控工具        │              │ - API 执行        │
└─────────────────────────┘              │ - Python 沙箱     │
                                         └──────────────────┘
```

### 3.4 总结

| | DevOps Agent On-Demand | AWS MCP Server |
|--|----------------------|----------------|
| **一句话** | 懂你系统架构的运维 AI 助手 | 能执行任何 AWS 操作的 AI 代理工具箱 |
| **类比** | 坐在监控大屏旁帮你分析问题的专家 | 装在你 IDE 里帮你操作 AWS 的万能助手 |
| **核心价值** | 发现问题、分析问题、预防问题 | 执行操作、构建系统、获取知识 |
| **读/写** | 只读（查询、分析） | 读写均可 |
| **智能程度** | 高（自动关联上下文、根因分析） | 中（依赖 AI 代理的推理能力） |

**两者互补而非竞争**：
- DevOps Agent 聚焦于 **"发现问题、分析问题"**
- AWS MCP Server 聚焦于 **"执行操作、构建系统"**

典型协作场景：DevOps Agent 发现并分析了一个事件的根因 → 开发者在 IDE 中通过 AWS MCP Server 实施修复 → DevOps Agent 验证修复后系统恢复正常。

---

## 四、DevOps Agent MCP Server 设计方案

### 4.1 定位

将 AWS DevOps Agent 的 On-Demand Conversation 能力封装为 MCP Server，让 SRE/运维人员在 AI Agent（Claude Code / Cursor / Codex / Kiro）中直接查询 AWS 环境运行状况、事件调查、根因分析，无需切换到 DevOps Agent Space Web 界面。

聚焦"查问题"，不做"修问题"（修问题由 AWS MCP Server 承担）。

### 4.2 架构

```
本地 Agent (Claude Code 等)                AWS 云端
┌──────────────────────────┐             ┌──────────────────────────────────┐
│  MCP Client              │             │  AgentCore Gateway                │
│  配置:                    │             │  (Remote MCP endpoint)            │
│   type: url              │  ─ HTTPS ──►│  - 默认 Cognito JWT 认证          │
│   url: https://...       │  OAuth2     │  - /.well-known/oauth-protected-  │
│   oauth: {clientId}      │             │    resource (自动发现)             │
│                          │  ◄─ 响应 ───│           │                      │
└──────────────────────────┘             │           ▼                      │
                                         │  Lambda (Python)                  │
                                         │  - boto3 devops-agent client     │
                                         │  - IAM 执行角色（自动轮换凭证）    │
                                         └──────────────────────────────────┘
```

**关键特点：**
- Remote MCP 格式，用户本地无需安装 proxy 或 uv
- Cognito JWT 认证（Gateway 默认自动创建 Cognito User Pool）
- Claude Code 通过 OAuth2 自动发现 + Authorization Code 流程获取 token
- Lambda 执行角色自带 IAM 凭证，无需用户配置 AWS 凭证
- MCP Server 无状态

### 4.3 MCP 客户端配置

```json
{
  "mcpServers": {
    "devops-agent": {
      "type": "url",
      "url": "https://<gateway-endpoint>/mcp",
      "oauth": {
        "clientId": "<部署输出的 client_id>"
      }
    }
  }
}
```

Claude Code 首次连接时自动走 OAuth 流程：Gateway 返回 401 → Claude Code 发现 `/.well-known/oauth-protected-resource` → 获取 token → 完成认证。

### 4.4 工具定义

#### 工具 1: `devops_list_spaces`

> 列出当前账号下所有可用的 DevOps Agent Space。当用户需要查看或切换 Agent Space 时调用。

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| （无） | | | |

**返回：**
```json
{
  "spaces": [
    {
      "id": "space-abc123",
      "name": "Production",
      "description": "生产环境监控"
    }
  ]
}
```

#### 工具 2: `devops_query`

> 向 AWS DevOps Agent 提问，查询 AWS 环境的运行状况、告警、事件调查、资源状态等。支持多轮追问。
>
> context_scope 选择指引：
> - general：资源查询、系统健康、架构问题、CloudWatch 指标、可观测性工具状态
> - incidents：事件趋势、解决时间、历史事件模式、调查见解
> - investigation：特定事件的深入分析、日志审查、根因分析、假设探索
> - prevention：事件预防建议、优先级排序、影响分析

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `message` | string | 是 | 自然语言问题 |
| `context_scope` | enum | 否 | `"general"` \| `"incidents"` \| `"investigation"` \| `"prevention"`，默认 `"general"` |
| `session_id` | string | 否 | 传入则继续已有对话，不传则创建新对话 |
| `agent_space_id` | string | 否 | 不传则使用配置的默认 Agent Space |

**返回：**
```json
{
  "session_id": "exec-abc123",
  "response": "过去1小时内有3个告警触发：\n1. 支付服务 5xx 错误率升高...\n2. ..."
}
```

### 4.5 核心设计决策

| 决策 | 选择 | 理由 |
|------|------|------|
| 工具粒度 | 2 个工具（list_spaces + query） | 兼容弱 Agent，首次查询一步到位 |
| 会话管理 | 无状态，session_id 由 Agent 记忆 | MCP Server 保持简单，强 Agent 自然会复用 session_id，弱 Agent 降级为每次新对话 |
| page_context | 暴露为枚举参数 `context_scope` | Agent 根据问题语义自动选择，保留 DevOps Agent 的上下文感知优势 |
| 多 Agent Space | 配置默认值 + 参数可覆盖 | 90% 场景零摩擦，多 Space 用户可随时切换 |
| 返回格式 | 完整文本，不截断 | 不在 MCP 层做信息损失决策 |
| 凭证管理 | Lambda 执行角色 | 用户无感，不存在凭证过期问题 |
| 客户端认证 | Cognito JWT（Gateway 默认） | Claude Code OAuth 自动发现，安全且标准 |
| 历史对话 | 不暴露 list_chats | 极简优先，DevOps Agent 自带历史调查数据查询能力 |

### 4.6 使用场景示例

#### 场景 1：全局态势感知

```
用户："我的系统现在整体健康吗？"
Agent 调用：devops_query(message="系统整体健康状况如何？过去1小时有什么告警？", context_scope="general")
```

#### 场景 2：深入事件调查（多轮追问）

```
用户："支付服务最近出了什么问题？"
Agent 调用：devops_query(message="支付服务最近的事件和告警？", context_scope="incidents")
返回：{session_id: "exec-001", response: "过去24小时支付服务有2次5xx错误率升高..."}

用户："第一次错误的根因是什么？"
Agent 调用：devops_query(message="第一次5xx错误的根因分析是什么？", context_scope="investigation", session_id="exec-001")
返回：{session_id: "exec-001", response: "根因分析：DynamoDB 限流导致..."}
```

#### 场景 3：预防性建议

```
用户："怎么防止 DynamoDB 限流问题再次发生？"
Agent 调用：devops_query(message="如何预防 DynamoDB 限流导致的事件？", context_scope="prevention")
```

#### 场景 4：跨 Agent Space 查询

```
用户："生产环境和预发环境的健康状况对比？"
Agent 调用：devops_list_spaces()
Agent 调用：devops_query(message="系统健康状况？", agent_space_id="prod-space")
Agent 调用：devops_query(message="系统健康状况？", agent_space_id="staging-space")
Agent 综合两个结果回答用户
```

### 4.7 底层 API 映射

| MCP 操作 | boto3 API 调用 |
|---------|---------------|
| `devops_list_spaces` | `client.list_agent_spaces()` |
| `devops_query`（新对话） | `client.create_chat(agentSpaceId)` → `client.send_message(agentSpaceId, executionId, content, context)` |
| `devops_query`（追问） | `client.send_message(agentSpaceId, executionId, content, context)` |

`send_message` 返回 EventStream，Lambda 中需消费完整个 stream，拼接 `contentBlockDelta.textDelta.text` 后返回完整文本。

### 4.8 可行性确认

| 验证点 | 结论 |
|--------|------|
| boto3 是否有 DevOps Agent Chat API | ✅ `create_chat`、`send_message`、`list_chats` 均已暴露 |
| 能否通过 API 模拟 Web 端的 On-Demand 体验 | ✅ `context.currentPage` 参数对应 `context_scope` |
| 流式响应能否在 Lambda 中处理 | ✅ 消费 EventStream 拼接文本后同步返回 |
| AgentCore Gateway + Lambda 是否支持 MCP | ✅ AgentCore Gateway 可暴露 Remote MCP endpoint |
| 多 Agent 兼容性 | ✅ 2 个工具 + 清晰描述，任何 MCP 客户端都能使用 |

### 4.9 项目结构

```
aws-devops-agent-mcp/
├── CLAUDE.md                  ← Claude Code 读此文件帮用户部署
├── README.md                  ← 人类阅读的说明文档
├── cdk/
│   ├── app.py                 ← CDK 入口
│   ├── stacks/
│   │   └── devops_agent_mcp_stack.py  ← Gateway + Lambda + IAM
│   └── requirements.txt      ← CDK Python 依赖
├── lambda/
│   ├── handler.py             ← Lambda 入口，MCP 工具逻辑
│   └── requirements.txt      ← Lambda 依赖（boto3）
└── scripts/
    └── setup.sh               ← 可选，一键部署脚本
```

**技术栈：**
- CDK：Python（`aws_cdk.aws_bedrockagentcore`）
- Lambda：Python 3.12
- 认证：AgentCore Gateway 默认 Cognito JWT
- 协议：MCP (MCP_2025_03_26)

### 4.10 部署与使用流程

```
用户体验（Claude Code 辅助）:

1. git clone https://github.com/readybuilderone/aws-devops-agent-mcp
2. 打开 Claude Code，说"帮我部署这个 DevOps Agent MCP"
3. Claude Code 读 CLAUDE.md，执行：
   ├── 检查前提条件（AWS CLI、CDK、已有 DevOps Agent Space）
   ├── pip install -r cdk/requirements.txt
   ├── cdk bootstrap（如果首次使用 CDK）
   └── cdk deploy
4. 部署输出：
   ├── Gateway URL: https://xxx.bedrock-agentcore.us-east-1.amazonaws.com/mcp
   ├── Client ID: xxxxxxxx
   └── Token Endpoint: https://xxx.auth.us-east-1.amazoncognito.com/oauth2/token
5. Claude Code 帮用户配置 MCP 连接：
   └── 写入 .claude/settings.json 或项目级 MCP 配置
6. 完成 ✅ 用户可以开始查询
```

### 4.11 CDK 核心逻辑（伪代码）

```python
from aws_cdk import Stack
from aws_cdk import aws_bedrockagentcore as agentcore
from aws_cdk import aws_lambda as _lambda

class DevOpsAgentMcpStack(Stack):
    def __init__(self, scope, id, *, agent_space_id, **kwargs):
        super().__init__(scope, id, **kwargs)

        # 1. 创建 Lambda（MCP 工具逻辑）
        handler = _lambda.Function(self, "Handler",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="handler.lambda_handler",
            code=_lambda.Code.from_asset("../lambda"),
            environment={"DEFAULT_AGENT_SPACE_ID": agent_space_id},
        )

        # 2. 授予 Lambda 调用 DevOps Agent API 的权限
        handler.add_to_role_policy(...)  # aidevops:CreateChat, SendMessage, ListAgentSpaces

        # 3. 创建 AgentCore Gateway（默认 Cognito 认证 + MCP 协议）
        gateway = agentcore.Gateway(self, "Gateway",
            gateway_name="devops-agent-mcp",
            description="DevOps Agent MCP Server for SRE queries",
        )

        # 4. 添加 Lambda Target（定义 MCP 工具 schema）
        gateway.add_lambda_target("DevOpsTools",
            gateway_target_name="devops-tools",
            lambda_function=handler,
            tool_schema=agentcore.ToolSchema.from_inline([
                {
                    "name": "devops_list_spaces",
                    "description": "列出所有可用的 DevOps Agent Space...",
                    "inputSchema": {...}
                },
                {
                    "name": "devops_query",
                    "description": "向 AWS DevOps Agent 提问...",
                    "inputSchema": {...}
                }
            ]),
        )

        # 5. 输出连接信息
        CfnOutput(self, "GatewayUrl", value=gateway.gateway_url)
        CfnOutput(self, "ClientId", value=gateway.user_pool_client.user_pool_client_id)
        CfnOutput(self, "TokenEndpoint", value=gateway.token_endpoint_url)
```
