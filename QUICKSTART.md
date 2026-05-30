# DevOps Agent MCP - 快速开始指南

> **适用人群**: 第一次使用此MCP服务器的新用户  
> **预计时间**: 10分钟  
> **难度**: 中级

## 📋 前提条件

在开始之前，请确保你有：

- ✅ AWS账号，并配置好AWS CLI凭证
- ✅ AWS CDK已安装 (`npm install -g aws-cdk`)
- ✅ Python 3.12+ 和 pip
- ✅ Claude Code CLI已安装 (版本 ≥ 2.1.156)
- ✅ 在us-west-2区域有权限部署CloudFormation、Lambda、Cognito

检查版本：
```bash
aws --version          # AWS CLI version 2.x
cdk --version          # >= 2.x
python3 --version      # >= 3.12
claude --version       # >= 2.1.156
```

---

## 🔑 认证方案概述

本MCP服务器是远程HTTP服务器，由AgentCore Gateway通过Cognito OAuth
（Client Credentials / M2M流程）保护。access token有效期1小时。

Claude Code通过 **`headersHelper`** 机制对接：在 `.mcp.json` 中指向
`scripts/get-headers.sh`，Claude Code会在**每次连接时**执行该脚本，
脚本自动获取（并缓存）token、输出 `Authorization` header。

这意味着：

- ✅ **无需** 手动注入 `~/.claude/.credentials.json`
- ✅ **无需** 查找 hash key
- ✅ **无需** cron 定时刷新
- ✅ **无需** token 过期后重启 Claude Code

token过期时，下次连接 `get-headers.sh` 会自动续期。你只需配置一次凭证。

> 背景：Claude Code原生只支持Authorization Code（浏览器登录）流程，
> 而本项目用的是Client Credentials（M2M）。早期方案靠脚本注入token，
> 现已被 `headersHelper` 取代。历史分析见
> `docs/authorization-code-attempt-postmortem.md`。

---

## 🚀 步骤1: 部署AWS基础设施

### 1.1 克隆并进入项目目录

```bash
git clone https://github.com/readybuilderone/aws-devops-agent-mcp.git
cd aws-devops-agent-mcp
```

### 1.2 安装CDK依赖

```bash
cd cdk
pip install -r requirements.txt
```

### 1.3 部署Stack

```bash
# 如果首次使用CDK，需要bootstrap
cdk bootstrap aws://YOUR_ACCOUNT_ID/us-west-2

# 部署
cdk deploy --region us-west-2
```

**预期输出**（约2-3分钟）：
```
✅  DevOpsAgentMcpStack

Outputs:
DevOpsAgentMcpStack.GatewayUrl = https://devops-agent-mcp-xxxxx.gateway.bedrock-agentcore.us-west-2.amazonaws.com/mcp
DevOpsAgentMcpStack.ClientId = xxxxxxxxxxxxxxxxxx
DevOpsAgentMcpStack.TokenEndpoint = https://xxxxx.auth.us-west-2.amazoncognito.com/oauth2/token
```

---

## ⚡ 推荐路径: 一键设置

`scripts/setup.sh` 会自动完成下面所有步骤（获取凭证、配置OAuth流程、
写 `token-config.sh`、验证token、把MCP服务器加进Claude Code）：

```bash
./scripts/setup.sh
```

成功后直接跳到 [步骤4: 测试](#-步骤4-测试mcp连接)。

下面的步骤2-3是脚本背后的手动流程，便于理解与排查。

---

## 🔐 步骤2: 准备Cognito凭证

`get-headers.sh` 需要一份 `scripts/token-config.sh` 配置文件。
本步骤收集所需的值。

### 2.1 收集Client ID、User Pool ID、Token Endpoint与Scope

```bash
STACK=DevOpsAgentMcpStack
REGION=us-west-2

CLIENT_ID=$(aws cloudformation describe-stacks --stack-name $STACK --region $REGION \
  --query 'Stacks[0].Outputs[?OutputKey==`ClientId`].OutputValue' --output text)

TOKEN_ENDPOINT=$(aws cloudformation describe-stacks --stack-name $STACK --region $REGION \
  --query 'Stacks[0].Outputs[?OutputKey==`TokenEndpoint`].OutputValue' --output text)

# 从Stack资源拿User Pool —— Gateway建的pool名字不含stack名，按名字过滤会查不到
USER_POOL_ID=$(aws cloudformation describe-stack-resources --stack-name $STACK --region $REGION \
  --query "StackResources[?ResourceType=='AWS::Cognito::UserPool'].PhysicalResourceId | [0]" --output text)

# resource server标识符（用于拼scope）
RESOURCE_SERVER=$(aws cognito-idp list-resource-servers --user-pool-id $USER_POOL_ID \
  --max-results 10 --region $REGION \
  --query "ResourceServers[?contains(Identifier, 'Gateway')].Identifier | [0]" --output text)

echo "Client ID:       $CLIENT_ID"
echo "Token Endpoint:  $TOKEN_ENDPOINT"
echo "User Pool ID:    $USER_POOL_ID"
echo "Resource Server: $RESOURCE_SERVER"
```

### 2.2 获取Client Secret

```bash
CLIENT_SECRET=$(aws cognito-idp describe-user-pool-client \
  --user-pool-id $USER_POOL_ID \
  --client-id $CLIENT_ID \
  --region $REGION \
  --query 'UserPoolClient.ClientSecret' \
  --output text)
```

**⚠️ Client Secret是机密，请勿提交到git或分享。**

### 2.3 确认Cognito使用Client Credentials流程

```bash
aws cognito-idp describe-user-pool-client \
  --user-pool-id $USER_POOL_ID \
  --client-id $CLIENT_ID \
  --region $REGION \
  --query 'UserPoolClient.AllowedOAuthFlows' \
  --output json
```

应返回 `["client_credentials"]`。如果不是，运行：

```bash
aws cognito-idp update-user-pool-client \
  --user-pool-id $USER_POOL_ID \
  --client-id $CLIENT_ID \
  --allowed-o-auth-flows client_credentials \
  --allowed-o-auth-scopes "${RESOURCE_SERVER}/read" "${RESOURCE_SERVER}/write" \
  --allowed-o-auth-flows-user-pool-client \
  --region $REGION
```

---

## 🎫 步骤3: 配置 headersHelper

### 3.1 创建token配置文件

```bash
cp scripts/token-config.sh.example scripts/token-config.sh
chmod 600 scripts/token-config.sh   # 含密钥，限制权限
```

编辑 `scripts/token-config.sh`，填入步骤2收集的值：

```bash
CLIENT_ID="<步骤2.1的Client ID>"
CLIENT_SECRET="<步骤2.2的Client Secret>"
TOKEN_ENDPOINT="<步骤2.1的Token Endpoint>"
SCOPE="<RESOURCE_SERVER>/read <RESOURCE_SERVER>/write"
```

> **🔒 安全提示**：`scripts/token-config.sh` 含Client Secret，已被
> `.gitignore` 忽略，**不会**提交到git。

### 3.2 验证脚本能拿到token

```bash
./scripts/get-headers.sh
```

**预期输出**（stdout只有一行JSON）：
```json
{"Authorization": "Bearer eyJ..."}
```

stderr会显示日志，如 `[get-headers] token获取成功 (有效期 3600s, 长度 941)`。

> 若返回 `invalid_client`，多半是 CLIENT_ID/CLIENT_SECRET 不匹配——
> 请重新执行步骤2.2获取最新secret。

### 3.3 把MCP服务器加入Claude Code

```bash
GATEWAY_URL=$(aws cloudformation describe-stacks --stack-name DevOpsAgentMcpStack \
  --region us-west-2 --query 'Stacks[0].Outputs[?OutputKey==`GatewayUrl`].OutputValue' --output text)

claude mcp add-json devops-agent "{
  \"type\": \"http\",
  \"url\": \"$GATEWAY_URL\",
  \"headersHelper\": \"$(pwd)/scripts/get-headers.sh\"
}"
```

> 作为插件分发时，`.claude-plugin/.mcp.json` 已用
> `${CLAUDE_PLUGIN_ROOT}/scripts/get-headers.sh`，无需手动添加。

---

## ✅ 步骤4: 测试MCP连接

### 4.1 验证连接状态

在Claude Code中运行：

```
/mcp
```

应看到 `✓ Connected`（而不是 `! Needs authentication`）。

> 不需要重启Claude Code——`headersHelper` 在连接时即时获取token。

### 4.2 测试echo工具

在Claude Code会话中说：

```
请调用devops_echo工具，消息是"Hello MCP!"
```

**预期响应**：
```json
{
  "message": "Hello MCP!",
  "echo": true
}
```

🎉 **成功！你的MCP服务器已经可以正常工作了！**

---

## 🔧 故障排查

### 问题1: `/mcp` 显示 "Needs authentication" 或连接失败

1. 手动跑一次 `./scripts/get-headers.sh`，确认能输出 `{"Authorization": ...}`。
2. 确认 `.mcp.json` 中 `headersHelper` 指向的路径正确且脚本可执行
   （`chmod +x scripts/get-headers.sh`）。
3. 检查 `token-config.sh` 是否存在且四个变量都已填写。

### 问题2: get-headers.sh 返回 401 / invalid_client

**原因**: Client ID或Client Secret错误/过期。

**解决**: 重新执行步骤2.1-2.2获取最新值，更新 `token-config.sh`。

### 问题3: "invalid_scope" 错误

**原因**: Cognito OAuth flows或scope配置错误。

**解决**: 重新执行步骤2.3，确认flow为 `client_credentials`，
并确认 `SCOPE` 中的resource server标识符与实际一致。

### 问题4: token过期了怎么办？

**不用做任何事。** `get-headers.sh` 会缓存token并在到期前自动续期，
下次连接时透明刷新。这正是 `headersHelper` 相比旧注入方案的核心优势。

### 问题5: headersHelper 超时

Claude Code对 `headersHelper` 有10秒超时。正常情况下Cognito请求 <1s。
若网络很慢可手动跑脚本观察耗时；缓存命中时几乎瞬间返回。

---

## 📚 下一步

1. **查看可用工具**：`列出所有devops-agent的MCP工具`
2. **实现完整功能**：参考 Issue #3 (`devops_list_spaces`)、Issue #4 (`devops_query`)
3. **阅读完整文档**：
   - [INTEGRATION.md](./INTEGRATION.md) - 详细集成指南
   - [aws-mcp-vs-devops-agent.md](./aws-mcp-vs-devops-agent.md) - 架构设计

---

## 🆘 获取帮助

1. **检查日志**：
   ```bash
   # Lambda日志
   aws logs tail /aws/lambda/DevOpsAgentMcpStack-Handler --follow --region us-west-2
   ```
2. **提Issue**：https://github.com/readybuilderone/aws-devops-agent-mcp/issues

---

**祝你使用愉快！🎉**
