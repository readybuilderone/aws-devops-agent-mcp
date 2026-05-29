# RFC 8707迁移指南

## 背景

AWS Cognito于2025年10月24日正式支持RFC 8707 Resource Binding，但存在关键限制：
- ✅ 支持Authorization Code Flow（用户认证）
- ❌ 不支持Client Credentials Flow（M2M）

当前项目使用Client Credentials方案，无法利用RFC 8707。本文档说明如何迁移到完全符合MCP规范的Authorization Code方案。

---

## 方案对比

### 当前方案：Client Credentials（M2M）

**优点**:
- ✅ 无需用户交互
- ✅ 适合自动化脚本
- ✅ Token管理可编程

**缺点**:
- ❌ 不支持RFC 8707（Cognito限制）
- ❌ 无token audience binding
- ❌ 需要手动token注入
- ❌ MCP合规性仅60%

**适用场景**: CI/CD、后台任务、服务间调用

---

### 新方案：Authorization Code + RFC 8707

**优点**:
- ✅ 完全符合MCP规范（100%）
- ✅ 支持RFC 8707 Resource Binding
- ✅ Token包含aud claim
- ✅ Claude Code自动管理token
- ✅ 无需手动脚本

**缺点**:
- ⚠️ 需要用户登录（首次）
- ⚠️ 需要Managed Login（Essentials/Plus计划）
- ⚠️ Token刷新依赖Claude Code

**适用场景**: 开发者工作站、交互式使用、严格合规要求

---

## 迁移步骤

### 前提条件检查

1. **Cognito计划等级**
   ```bash
   # 检查User Pool配置
   aws cognito-idp describe-user-pool \
     --user-pool-id us-west-2_L0273ULfK \
     --region us-west-2 \
     --query 'UserPool.UserPoolTier'
   
   # 需要返回: ESSENTIALS 或 PLUS
   # 如果是 LITE，需要升级计划
   ```

2. **启用Managed Login**
   ```bash
   # 通过AWS Console启用
   # Cognito User Pool → App Integration → Managed Login → Enable
   ```

### 步骤1: 创建Cognito用户

```bash
USER_POOL_ID="us-west-2_L0273ULfK"
CLIENT_ID="<COGNITO_CLIENT_ID>"

# 创建用户
aws cognito-idp admin-create-user \
  --user-pool-id $USER_POOL_ID \
  --username your-username \
  --temporary-password 'TempPass123!' \
  --user-attributes Name=email,Value=you@example.com \
  --region us-west-2

# 设置永久密码
aws cognito-idp admin-set-user-password \
  --user-pool-id $USER_POOL_ID \
  --username your-username \
  --password 'YourSecurePass123!' \
  --permanent \
  --region us-west-2
```

### 步骤2: 配置App Client支持Authorization Code

```bash
# 获取当前Resource Server Identifier
RESOURCE_SERVER=$(aws cognito-idp describe-resource-server \
  --user-pool-id $USER_POOL_ID \
  --identifier "DevOpsAgentMcpStack-Gateway-0299DE6E" \
  --region us-west-2 \
  --query 'ResourceServer.Identifier' \
  --output text)

# 更新App Client配置
aws cognito-idp update-user-pool-client \
  --user-pool-id $USER_POOL_ID \
  --client-id $CLIENT_ID \
  --allowed-o-auth-flows authorization_code \
  --allowed-o-auth-scopes \
    "${RESOURCE_SERVER}/read" \
    "${RESOURCE_SERVER}/write" \
  --allowed-o-auth-flows-user-pool-client \
  --callback-urls "http://localhost:8080/callback" \
  --supported-identity-providers COGNITO \
  --region us-west-2
```

### 步骤3: 配置Claude Code MCP

```bash
# 移除旧配置（如果存在）
claude mcp remove devops-agent

# 添加新配置（支持Authorization Code）
claude mcp add-json devops-agent '{
  "type": "http",
  "url": "https://devops-agent-mcp-elhze1stwj.gateway.bedrock-agentcore.us-west-2.amazonaws.com/mcp",
  "oauth": {
    "clientId": "<COGNITO_CLIENT_ID>",
    "callbackPort": 8080
  }
}'
```

### 步骤4: 启用RFC 8707 Resource Binding

**重要**: Cognito会自动在Authorization Code流程中支持RFC 8707，无需额外配置。

当MCP客户端（Claude Code）发起OAuth请求时：

```http
GET /oauth2/authorize?
  response_type=code
  &client_id=<COGNITO_CLIENT_ID>
  &redirect_uri=http://localhost:8080/callback
  &scope=DevOpsAgentMcpStack-Gateway-0299DE6E/read
  &resource=https://devops-agent-mcp-xxx.gateway.bedrock-agentcore.us-west-2.amazonaws.com/mcp
  &state=xxx
  &code_challenge=xxx
  &code_challenge_method=S256
```

Cognito会：
1. 验证`resource`参数格式（必须是URL）
2. 用户登录后，生成authorization code
3. 交换token时，返回的JWT包含：
   ```json
   {
     "aud": "https://devops-agent-mcp-xxx.gateway.bedrock-agentcore.us-west-2.amazonaws.com/mcp",
     "scope": "DevOpsAgentMcpStack-Gateway-0299DE6E/read DevOpsAgentMcpStack-Gateway-0299DE6E/write",
     "sub": "user-uuid",
     "token_use": "access",
     ...
   }
   ```

### 步骤5: 测试OAuth流程

```bash
# 启动Claude Code
claude

# 尝试调用MCP工具
# Claude Code会自动:
# 1. 检测到需要认证
# 2. 打开浏览器到Cognito Hosted UI
# 3. 你登录后，自动完成OAuth流程
# 4. Token自动保存到 ~/.claude/.credentials.json

# 验证token包含aud claim
cat ~/.claude/.credentials.json | \
  python3 -c "
import json, sys, base64
data = json.load(sys.stdin)
token = data['mcpOAuth']['devops-agent|xxx']['accessToken']
# 解码JWT (注意：生产环境应验证签名)
payload = token.split('.')[1]
# 添加padding
payload += '=' * (4 - len(payload) % 4)
decoded = base64.urlsafe_b64decode(payload)
print(json.dumps(json.loads(decoded), indent=2))
"
```

预期输出应包含：
```json
{
  "aud": "https://devops-agent-mcp-xxx.../mcp",  // ← RFC 8707!
  ...
}
```

### 步骤6: 更新CDK代码（可选）

如果想在CDK中明确配置Authorization Code：

```python
# cdk/stacks/devops_agent_mcp_stack.py

if gateway.user_pool_client:
    cfn_client = gateway.user_pool_client.node.default_child
    
    # 配置Authorization Code Flow (RFC 8707兼容)
    cfn_client.add_property_override("AllowedOAuthFlows", ["authorization_code"])
    cfn_client.add_property_override("AllowedOAuthFlowsUserPoolClient", True)
    cfn_client.add_property_override("CallbackURLs", ["http://localhost:8080/callback"])
    cfn_client.add_property_override("SupportedIdentityProviders", ["COGNITO"])
    
    # RFC 8707自动支持，无需额外配置
    # Token会自动包含aud claim
```

重新部署：
```bash
cd cdk
cdk deploy --region us-west-2
```

---

## 验证RFC 8707生效

### 1. 检查Token结构

```bash
# 获取token
TOKEN=$(cat ~/.claude/.credentials.json | \
  python3 -c "import json,sys; print(json.load(sys.stdin)['mcpOAuth']['devops-agent|xxx']['accessToken'])")

# 解码JWT header和payload
echo $TOKEN | cut -d. -f1 | base64 -d 2>/dev/null | jq .
echo $TOKEN | cut -d. -f2 | base64 -d 2>/dev/null | jq .
```

预期payload包含：
```json
{
  "sub": "user-uuid",
  "aud": "https://devops-agent-mcp-xxx.../mcp",  // ← RFC 8707
  "token_use": "access",
  "scope": "DevOpsAgentMcpStack-Gateway-0299DE6E/read ...",
  "auth_time": 1748518253,
  "iss": "https://cognito-idp.us-west-2.amazonaws.com/us-west-2_xxx",
  "exp": 1748521853,
  "iat": 1748518253
}
```

### 2. 验证Gateway的Token验证

AgentCore Gateway应该验证：
- ✅ JWT签名有效
- ✅ Token未过期
- ✅ **`aud` claim匹配Gateway URL**  ← RFC 8707验证
- ✅ Scope包含所需权限

### 3. 测试工具调用

```bash
# 在Claude Code中
请调用devops_echo工具，消息是"Testing RFC 8707"
```

预期：正常工作，且token包含正确的audience binding。

---

## 回退到Client Credentials

如果遇到问题，可以快速回退：

```bash
# 1. 更新Cognito配置
aws cognito-idp update-user-pool-client \
  --user-pool-id us-west-2_L0273ULfK \
  --client-id <COGNITO_CLIENT_ID> \
  --allowed-o-auth-flows client_credentials \
  --allowed-o-auth-scopes "DevOpsAgentMcpStack-Gateway-0299DE6E/read" "DevOpsAgentMcpStack-Gateway-0299DE6E/write" \
  --allowed-o-auth-flows-user-pool-client \
  --region us-west-2

# 2. 运行原有的token刷新脚本
./scripts/refresh-token.sh

# 3. 重启Claude Code
exit && claude
```

---

## 成本影响

| 项目 | Client Credentials | Authorization Code + RFC 8707 |
|------|-------------------|------------------------------|
| Cognito认证 | 免费层 (1000次/月) | 免费层 (1000次/月) |
| Managed Login | 不需要 | **需要Essentials ($0.0055/MAU)或Plus** |
| 其他AWS服务 | 相同 | 相同 |
| **额外成本** | $0 | **~$0.0055/用户/月** |

**注意**: 
- 如果只有1-2个用户使用，额外成本可忽略不计（<$0.02/月）
- 需要验证当前User Pool是否支持Managed Login（Essentials/Plus）

---

## FAQ

### Q1: 我必须迁移到Authorization Code吗？

**A**: 不必须。取决于你的需求：

| 场景 | 推荐方案 |
|------|---------|
| 开发者交互式使用 | Authorization Code + RFC 8707 |
| CI/CD自动化 | Client Credentials（当前方案） |
| 严格MCP合规 | Authorization Code + RFC 8707 |
| 简单快速集成 | Client Credentials（当前方案） |

### Q2: RFC 8707对安全性的实际影响是什么？

**A**: 

**有RFC 8707（Authorization Code方案）**:
```
Token A: aud=https://gateway-a.com/mcp
→ Gateway A: ✅ 接受
→ Gateway B: ❌ 拒绝（aud不匹配）
```

**无RFC 8707（Client Credentials方案）**:
```
Token: scope=DevOpsAgentMcpStack-Gateway-0299DE6E/read
→ Gateway A: ✅ 接受（验证scope）
→ 其他Cognito Resource Server: ⚠️ 理论上可能接受相同scope
```

**实际风险**: 低到中等
- 如果只有一个Resource Server，风险很低
- 如果Cognito管理多个服务，存在token误用风险

### Q3: Claude Code是否自动支持RFC 8707？

**A**: 是的！根据MCP规范：

> *"MCP clients **MUST** implement Resource Indicators for OAuth 2.0 as defined in RFC 8707"*

Claude Code会自动在OAuth请求中加入`resource`参数。你只需要：
1. 配置Authorization Code流程
2. Cognito会自动处理`resource`参数
3. 返回的token自动包含`aud` claim

### Q4: 多个开发者如何共享MCP连接？

**Authorization Code方案**:
- ✅ 每个开发者独立登录
- ✅ 各自管理token
- ✅ 可以设置不同权限（scope）

**Client Credentials方案**:
- ⚠️ 共享Client Secret（安全风险）
- ⚠️ 无法区分用户
- ✅ 更简单（适合小团队）

---

## 推荐方案

### 如果你是...

**个人开发者/小团队** (1-5人):
→ **保持Client Credentials方案**
- 简单、无需登录
- 成本低
- 安全风险可接受

**企业团队/严格合规**:
→ **迁移到Authorization Code + RFC 8707**
- 完全符合MCP规范
- 更好的安全性（audience binding）
- 用户级审计
- 多租户支持

**CI/CD自动化**:
→ **Client Credentials方案**
- 无法使用Authorization Code（需要用户交互）
- M2M场景不支持RFC 8707（Cognito限制）

---

## 相关资源

- [AWS Cognito Resource Binding文档](https://docs.aws.amazon.com/cognito/latest/developerguide/resource-binding.html)
- [RFC 8707: Resource Indicators for OAuth 2.0](https://datatracker.ietf.org/doc/html/rfc8707)
- [MCP OAuth规范](https://spec.modelcontextprotocol.io/)
- [Cognito Managed Login定价](https://aws.amazon.com/cognito/pricing/)

---

## 总结

AWS Cognito现在支持RFC 8707，但仅限于**用户认证场景**（Authorization Code Flow）。

**当前项目状态**:
- ✅ 使用Client Credentials（M2M）方案可工作
- ❌ 无法使用RFC 8707（Cognito限制）
- ⚠️ MCP合规性60%，但实际可用

**完全符合MCP规范的路径**:
1. 升级Cognito到Essentials/Plus计划
2. 启用Managed Login
3. 创建Cognito用户
4. 切换到Authorization Code流程
5. Cognito自动支持RFC 8707
6. Token自动包含`aud` claim
7. MCP合规性100% ✅

**决策建议**: 如果当前方案满足需求，无需迁移。如果需要严格MCP合规或企业级安全，考虑迁移。
