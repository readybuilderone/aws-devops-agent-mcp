# DevOps Agent MCP 集成指南

## 部署信息

- **Stack名称**: DevOpsAgentMcpStack
- **区域**: us-west-2
- **状态**: CREATE_COMPLETE ✅
- **Gateway URL**: https://devops-agent-mcp-elhze1stwj.gateway.bedrock-agentcore.us-west-2.amazonaws.com/mcp
- **Client ID**: <COGNITO_CLIENT_ID>
- **Token Endpoint**: https://devopsagentmcpstack-gateway-0299de6e.auth.us-west-2.amazoncognito.com/oauth2/token

## 集成到Claude Code

### ✅ 已配置完成

**⚠️ 重要发现：必须使用CLI命令添加MCP服务器，手动编辑文件不会生效！**

### 正确的配置方法

使用 `claude mcp add-json` 命令添加MCP服务器：

```bash
claude mcp add-json devops-agent '{
  "type": "http",
  "url": "https://devops-agent-mcp-elhze1stwj.gateway.bedrock-agentcore.us-west-2.amazonaws.com/mcp",
  "oauth": {
    "clientId": "<COGNITO_CLIENT_ID>",
    "callbackPort": 8080
  }
}'
```

**关键点：**
- ✅ 使用 `claude mcp add-json` CLI命令
- ✅ `"type": "http"` (不是 "url")
- ✅ 包含 `callbackPort` 字段
- ❌ 不要手动创建/编辑 `.mcp.json` 文件（会被忽略）

### 验证配置成功

配置成功后，运行 `/reload-plugins` 会看到MCP认证工具可用：
- `mcp__devops-agent__authenticate`
- `mcp__devops-agent__complete_authentication`

### OAuth认证流程

首次调用MCP工具时：
1. Claude Code调用 `authenticate` 工具获取授权URL
2. 自动打开浏览器到Cognito登录页
3. 使用凭证登录：
   - 用户名：`admin`
   - 密码：`DevOpsAgent2026!`
4. 登录成功后回调到 `localhost:8080`
5. Claude Code调用 `complete_authentication` 完成认证
6. 后续请求自动携带access token

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
  --user-pool-id us-west-2_L0273ULfK \
  --client-id <COGNITO_CLIENT_ID> \
  --allowed-o-auth-flows client_credentials \
  --allowed-o-auth-scopes \
    "DevOpsAgentMcpStack-Gateway-0299DE6E/read" \
    "DevOpsAgentMcpStack-Gateway-0299DE6E/write" \
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

#### 步骤3: 注入Token到Claude Code

```python
import json

with open('~/.claude/.credentials.json', 'r') as f:
    creds = json.load(f)

# 找到devops-agent对应的key
creds['mcpOAuth']['devops-agent|<hash>']['accessToken'] = '<access_token>'

with open('~/.claude/.credentials.json', 'w') as f:
    json.dump(creds, f, indent=2)
```

#### 步骤4: 重启Claude Code会话

```bash
exit    # 退出
claude  # 重新启动
/reload-plugins  # 重新加载
```

**为什么Authorization Code不行？**
- MCP客户端发送`resource`参数（RFC 8707）
- Cognito不支持此参数
- 导致`invalid_scope`错误

**Client Credentials限制**：
- Token有效期1小时
- 需要手动刷新
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

### 为什么手动编辑 .mcp.json 不起作用？

经过深度研究和多次测试，发现了关键问题：

1. **Claude Code不会自动扫描项目中的 `.mcp.json` 文件**
   - 即使创建了 `.claude-plugin/plugin.json` 和 `.mcp.json`
   - 即使设置了 `enableAllProjectMcpServers: true`
   - 仍然不会被加载

2. **必须使用 `claude mcp add-json` CLI命令**
   - 这个命令会将配置写入Claude Code的内部配置存储
   - 配置被持久化到 `~/.claude/` 的某个位置
   - 只有通过CLI添加的MCP服务器才会被加载

3. **`type` 字段必须是 `"http"`**
   - 官方文档明确指出使用 `"http"` 或别名 `"streamable-http"`
   - `"type": "url"` 是错误的（虽然在某些示例中看到过）

4. **OAuth配置需要 `callbackPort`**
   - 虽然某些示例省略了这个字段
   - 但完整配置应包含 `callbackPort: 8080`

### 正确的工作流程

```bash
# 1. 通过CLI添加MCP服务器
claude mcp add-json <server-name> '<json-config>'

# 2. 重新加载插件（在Claude Code会话中）
/reload-plugins

# 3. 验证工具可用
# 系统会显示: mcp__<server-name>__<tool-name>
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
- 运行 `/reload-mcp` 重新加载

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
