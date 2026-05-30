# DevOps Agent MCP 集成指南

## 部署信息

- **Stack名称**: DevOpsAgentMcpStack
- **区域**: us-west-2
- **状态**: CREATE_COMPLETE ✅
- **Gateway URL**: 见 `cdk deploy` 输出的 `GatewayUrl`（每次部署可能变化）
- **Client ID**: 见 `cdk deploy` 输出的 `ClientId`
- **Token Endpoint**: 见 `cdk deploy` 输出的 `TokenEndpoint`

## 集成到Claude Code

> **当前方案：headersHelper（推荐）。** 完整的分步指南见
> [QUICKSTART.md](./QUICKSTART.md)。本节只说明集成的关键点。

### 配置方法

Claude Code通过 `headersHelper` 机制对接：在MCP配置中指向
`scripts/get-headers.sh`，它在每次连接时自动获取/缓存Cognito token
并输出 `Authorization` header。

**方式A：作为插件（推荐）** —— `.claude-plugin/.mcp.json` 已配置：

```json
{
  "mcpServers": {
    "devops-agent": {
      "type": "http",
      "url": "<GatewayUrl>",
      "headersHelper": "${CLAUDE_PLUGIN_ROOT}/scripts/get-headers.sh"
    }
  }
}
```

**方式B：用CLI手动添加**：

```bash
claude mcp add-json devops-agent "{
  \"type\": \"http\",
  \"url\": \"<GatewayUrl>\",
  \"headersHelper\": \"$(pwd)/scripts/get-headers.sh\"
}"
```

**关键点：**
- ✅ `"type": "http"`（或别名 `"streamable-http"`）
- ✅ 用 `headersHelper` 提供token，**自动刷新、无需重启**
- ✅ 凭证放在 git-ignored 的 `scripts/token-config.sh`
- ❌ 不再需要 `oauth.clientId` / `callbackPort` / 浏览器登录
- ❌ 不再需要手动注入 `~/.claude/.credentials.json`

### 验证配置成功

在Claude Code中运行 `/mcp`，应看到 `devops-agent` 为 `✓ Connected`。
无需重启Claude Code。

## 认证授权机制

### 认证流程

你的DevOps Agent MCP使用**Cognito OAuth2认证**，流程如下：

1. **首次连接**: Claude Code尝试连接Gateway时会收到401未授权响应
2. **自动发现**: Claude Code自动访问 `/.well-known/oauth-protected-resource` 获取OAuth配置
3. **OAuth流程**: Claude Code启动Authorization Code Flow
   - 打开浏览器到Cognito登录页面
   - 用户登录并授权
   - Claude Code获取访问令牌(JWT)
4. **后续请求**: 所有MCP请求都在HTTP头中携带 `Authorization: Bearer <token>`

### ⚠️ 实际采用方案：Client Credentials流程

**重要更新（2025年10月）**: AWS Cognito已支持RFC 8707 Resource Binding，但仅限于Authorization Code流程，**不支持Client Credentials（M2M）场景**。

当前项目采用**Client Credentials**流程，原因：
1. 适合自动化/M2M场景（无需用户交互）
2. Cognito的RFC 8707支持不包含Client Credentials流程
3. 简化token管理（适合CI/CD集成）

**如需完全符合MCP规范（包括RFC 8707）**，参考 [RFC 8707迁移指南](docs/rfc8707-migration.md)。

---

### Client Credentials配置步骤

#### 步骤1: 配置Cognito支持Client Credentials

```bash
aws cognito-idp update-user-pool-client \
  --user-pool-id <USER_POOL_ID> \
  --client-id <CLIENT_ID> \
  --allowed-o-auth-flows client_credentials \
  --allowed-o-auth-scopes \
    "<RESOURCE_SERVER>/read" \
    "<RESOURCE_SERVER>/write" \
  --allowed-o-auth-flows-user-pool-client \
  --region us-west-2
```

#### 步骤2: 获取Access Token

```bash
# 使用Client ID和Client Secret获取token
curl -X POST https://devopsagentmcpstack-gateway-0299de6e.auth.us-west-2.amazoncognito.com/oauth2/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -u "CLIENT_ID:CLIENT_SECRET" \
  -d "grant_type=client_credentials&scope=DevOpsAgentMcpStack-Gateway-0299DE6E/read%20DevOpsAgentMcpStack-Gateway-0299DE6E/write"
```

返回：
```json
{
  "access_token": "eyJraWQ...",
  "expires_in": 3600,
  "token_type": "Bearer"
}
```

#### 步骤3: 通过 headersHelper 提供Token（自动）

不再手动注入 `~/.claude/.credentials.json`。把上面 curl 的逻辑封装在
`scripts/get-headers.sh` 中，由Claude Code在每次连接时调用：

```bash
# scripts/token-config.sh 中填好 CLIENT_ID/CLIENT_SECRET/TOKEN_ENDPOINT/SCOPE 后
./scripts/get-headers.sh
# 输出: {"Authorization": "Bearer eyJ..."}
```

`.mcp.json` 中 `headersHelper` 指向该脚本即可（见上文"配置方法"）。

#### 步骤4: 完成

无需重启。token过期时 `get-headers.sh` 会自动续期（带本地缓存）。

**为什么Authorization Code不行？**
- MCP客户端发送`resource`参数（RFC 8707）
- Cognito不支持此参数
- 导致`invalid_scope`错误

**Client Credentials特性**：
- Token有效期1小时
- 由 `get-headers.sh` 自动刷新（无需手动、无需cron、无需重启）
- 无用户交互，纯M2M认证

---

### 创建Cognito用户（备选方案）

如果将来Cognito支持RFC 8707，可以使用Authorization Code流程：

#### 选项A：通过AWS Console创建用户

1. 打开AWS Console → Cognito → User Pools
2. 找到名为 `DevOpsAgentMcpStack-Gateway-*` 的User Pool
3. 点击"Users"标签 → "Create user"
4. 设置用户名和临时密码
5. 首次登录时会要求修改密码

#### 选项B：通过AWS CLI创建用户

```bash
# 获取User Pool ID
aws cognito-idp list-user-pools --max-results 10 --region us-west-2 \
  --query "UserPools[?contains(Name, 'DevOpsAgentMcpStack')].Id" --output text

# 创建用户（替换 <USER_POOL_ID>）
aws cognito-idp admin-create-user \
  --user-pool-id <USER_POOL_ID> \
  --username your-username \
  --temporary-password 'TempPassword123!' \
  --user-attributes Name=email,Value=your-email@example.com \
  --region us-west-2

# 设置永久密码（可选）
aws cognito-idp admin-set-user-password \
  --user-pool-id <USER_POOL_ID> \
  --username your-username \
  --password 'YourSecurePassword123!' \
  --permanent \
  --region us-west-2
```

### Lambda IAM权限

Lambda函数需要以下IAM权限来调用DevOps Agent API：

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "aidevops:ListAgentSpaces",
        "aidevops:CreateChat",
        "aidevops:SendMessage"
      ],
      "Resource": "*"
    }
  ]
}
```

**注意**: 当前Lambda只有基本执行权限，还需要添加DevOps Agent相关权限。

## 测试连接

### 测试1：验证MCP工具可见

配置完成后，在Claude Code中询问：

```
Claude能看到devops_echo工具吗？
```

### 测试2：调用echo工具

```
请调用devops_echo工具，消息是"Hello DevOps Agent MCP"
```

预期响应：
```json
{
  "message": "Hello DevOps Agent MCP",
  "echo": true
}
```

## ✅ 测试结果

**状态**: 完全成功！

成功调用 `devops_echo` 工具，验证了完整的MCP集成链路：
```json
{
  "message": "Hello from Claude Code! DevOps Agent MCP is working!",
  "echo": true
}
```

**工具名称**: `mcp__devops-agent__devops-tools___devops_echo`

---

## ⚠️ 重要经验教训

### 配置加载方式

1. **`type` 字段必须是 `"http"`**（或别名 `"streamable-http"`）
   - `"type": "url"` 是错误的

2. **认证用 `headersHelper`，不要用 `oauth.clientId` + 浏览器流程**
   - 本Gateway是Client Credentials（M2M），Claude Code原生OAuth走的是
     Authorization Code（浏览器登录），两者不匹配
   - `headersHelper` 在连接时由脚本提供token，自动刷新，无需重启

3. **插件方式下 `.claude-plugin/.mcp.json` 会被加载**
   - 顶层用 `{ "mcpServers": { ... } }` 包裹
   - 路径用 `${CLAUDE_PLUGIN_ROOT}/scripts/get-headers.sh`
   - 也可用 `claude mcp add-json` 在用户/项目级手动添加（路径用绝对路径）

### 正确的工作流程

```bash
# 推荐：一键设置（生成凭证 + 注册MCP）
./scripts/setup.sh

# 或手动添加
claude mcp add-json devops-agent "{ \"type\": \"http\", \"url\": \"<GatewayUrl>\", \"headersHelper\": \"$(pwd)/scripts/get-headers.sh\" }"

# 在Claude Code中验证
/mcp     # devops-agent 应为 ✓ Connected
```

## 下一步

当前Stack部署的是**基础框架**，只有一个测试用的 `devops_echo` 工具。要实现完整的DevOps Agent查询能力，需要：

### 1. 更新Lambda Handler

实现真正的DevOps Agent查询工具：
- `devops_list_spaces`: 列出所有Agent Space
- `devops_query`: 查询系统健康、告警、事件等

### 2. 添加Lambda IAM权限

```python
# 在CDK stack中添加
handler.add_to_role_policy(
    aws_iam.PolicyStatement(
        actions=[
            "aidevops:ListAgentSpaces",
            "aidevops:CreateChat",
            "aidevops:SendMessage",
            "aidevops:ListChats"
        ],
        resources=["*"]
    )
)
```

### 3. 更新工具Schema

在 `devops_agent_mcp_stack.py` 中更新 `TOOL_SCHEMA`，添加：
- `devops_list_spaces`
- `devops_query`（支持context_scope、session_id等参数）

### 4. 配置默认Agent Space

如果你已经有DevOps Agent Space，可以在部署时传入：

```bash
cd cdk
cdk deploy --context agent_space_id=your-agent-space-id
```

或设置环境变量：
```bash
export DEFAULT_AGENT_SPACE_ID=your-agent-space-id
cdk deploy
```

## 故障排查

### 问题1：Claude Code无法连接

- 检查Gateway URL是否正确
- 确认区域是us-west-2
- 手动跑 `./scripts/get-headers.sh` 确认能输出token

### 问题2：认证失败

- 确认Cognito User Pool中有用户
- 尝试重置密码
- 检查Client ID是否正确

### 问题3：工具调用失败

- 查看Lambda日志: `aws logs tail /aws/lambda/DevOpsAgentMcpStack-Handler* --follow --region us-west-2`
- 检查Lambda IAM权限
- 确认Lambda环境变量 `DEFAULT_AGENT_SPACE_ID` 已设置

## 资源链接

- [AWS Agent Toolkit文档](https://docs.aws.amazon.com/agent-toolkit/)
- [MCP协议规范](https://spec.modelcontextprotocol.io/)
- [Bedrock AgentCore文档](https://docs.aws.amazon.com/bedrock/latest/userguide/agentcore.html)
