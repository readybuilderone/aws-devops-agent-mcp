# AWS DevOps Agent MCP Server

将AWS DevOps Agent的On-Demand Conversation能力封装为MCP Server，让Claude Code能够直接查询AWS环境运行状况、告警、事件调查和根因分析。

## 🚀 快速开始

**新用户请从这里开始** → [QUICKSTART.md](./QUICKSTART.md)

或使用一键设置脚本：

```bash
./scripts/setup.sh
```

## 📖 文档

- **[QUICKSTART.md](./QUICKSTART.md)** - 新手完整指南（15-20分钟）
- **[INTEGRATION.md](./INTEGRATION.md)** - 详细集成文档和故障排查
- **[aws-mcp-vs-devops-agent.md](./aws-mcp-vs-devops-agent.md)** - 架构设计和对比分析

## ✅ 测试状态

**当前状态**: 基础框架已验证 ✓

- ✅ AgentCore Gateway + Lambda + Cognito部署成功
- ✅ MCP Client Credentials认证成功
- ✅ `devops_echo`工具测试通过
- 🚧 `devops_list_spaces`和`devops_query`待实现

查看完整测试报告：[Issue #7](https://github.com/readybuilderone/aws-devops-agent-mcp/issues/7)

## 🛠️ 工具和脚本

### 自动化脚本

```bash
# 一键设置（交互式）—— 获取凭证、配置OAuth、写token-config.sh、注册MCP
./scripts/setup.sh
```

token由 `scripts/get-headers.sh`（headersHelper）在每次连接时自动获取并缓存，
过期会自动续期 —— **无需手动刷新、无需cron、无需重启Claude Code**。

### 可用工具

当前已实现：

- `mcp__devops-agent__devops-tools___devops_echo` - 测试连接性的echo工具

计划实现（参考Issues）：

- `devops_list_spaces` - 列出所有DevOps Agent Space ([Issue #3](../../issues/3))
- `devops_query` - 查询系统健康、告警、事件等 ([Issue #4](../../issues/4), [Issue #5](../../issues/5))

## 🏗️ 架构

```
Claude Code CLI
    ↓ MCP协议
AgentCore Gateway (Cognito OAuth)
    ↓ Lambda调用
Lambda Handler (Python)
    ↓ boto3 API
AWS DevOps Agent On-Demand API
```

**关键技术**:
- AWS CDK (Python) - 基础设施即代码
- AWS Bedrock AgentCore Gateway - Remote MCP endpoint
- AWS Cognito - OAuth 2.0 Client Credentials认证
- AWS Lambda (Python 3.12) - MCP工具实现

## 🎯 功能特性

### 已实现
- ✅ Remote MCP Server (HTTP)
- ✅ OAuth 2.0 Client Credentials认证
- ✅ AgentCore Gateway集成
- ✅ 基础工具测试框架
- ✅ Token自动刷新（`scripts/get-headers.sh` + Claude Code headersHelper）

### 待实现
- 🚧 查询Agent Space列表
- 🚧 查询系统健康状态
- 🚧 查询告警和事件
- 🚧 多轮对话支持（session_id）
- 🚧 上下文感知（context_scope）

## 📊 项目结构

```
.
├── QUICKSTART.md              # 新手完整指南
├── INTEGRATION.md             # 详细集成文档
├── aws-mcp-vs-devops-agent.md # 架构设计文档
├── cdk/                       # CDK部署代码
│   ├── app.py                 # CDK入口
│   └── stacks/
│       └── devops_agent_mcp_stack.py  # Stack定义
├── lambda/                    # Lambda函数代码
│   ├── handler.py             # 工具处理逻辑
│   └── requirements.txt       # Python依赖
└── scripts/                   # 自动化脚本
    ├── setup.sh               # 一键设置脚本
    ├── get-headers.sh         # headersHelper：连接时自动获取/缓存token
    └── token-config.sh.example # 配置模板
```

## 🔧 开发

### 部署

```bash
cd cdk
pip install -r requirements.txt
cdk deploy --region us-west-2
```

### 更新Lambda

```bash
cd cdk
cdk deploy --hotswap  # 快速部署Lambda变更
```

### 查看日志

```bash
aws logs tail /aws/lambda/DevOpsAgentMcpStack-Handler --follow --region us-west-2
```

## 📚 相关Issue

- [#1 - PRD: DevOps Agent MCP Server](../../issues/1)
- [#3 - devops_list_spaces实现](../../issues/3)
- [#4 - devops_query单轮实现](../../issues/4)
- [#5 - devops_query多轮实现](../../issues/5)
- [#6 - CLAUDE.md + README部署指南](../../issues/6)
- [#7 - MCP集成测试成功报告](../../issues/7)

## 🤝 贡献

欢迎提Issue和PR！

## 📄 许可

MIT License

---

**需要帮助?** 查看 [QUICKSTART.md](./QUICKSTART.md) 或提交 [Issue](../../issues)
