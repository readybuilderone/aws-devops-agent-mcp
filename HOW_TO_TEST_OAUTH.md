# 如何测试OAuth Authorization Code流程

**目标**: 完成首次OAuth登录，获取token，验证RFC 8707支持

**预计时间**: 5-10分钟（首次）

**难度**: ⭐ 简单 - 只需点击几次

---

## 📋 前提条件

### 必需条件 ✅

- [ ] 有浏览器的环境（桌面/笔记本）
- [ ] Claude Code已安装（CLI或Desktop app）
- [ ] 网络可以访问localhost:8080
- [ ] 知道Cognito用户密码（username: `admin`）

### 可选检查

运行预检查脚本（确认一切就绪）：

```bash
cd /path/to/aws-devops-agent-mcp
python3 tests/verify_oauth_ready.py
```

如果看到：
```
✅ ALL CHECKS PASSED - Ready for Authorization Code flow!
```

就可以继续了！

---

## 🎯 测试方法

有**3种方法**可以测试，选择最适合你的：

### 方法1: 在Claude Code中直接测试（最简单）✨

**适合**: 日常使用，验证实际工作流程

### 方法2: 使用手动测试脚本（最详细）🔬

**适合**: 想看完整OAuth流程细节，验证RFC 8707

### 方法3: 快速验证（最快）⚡

**适合**: 只想确认能工作，不关心细节

---

## 方法1️⃣: Claude Code直接测试（推荐）

### 步骤1: 启动Claude Code

**在你的桌面/笔记本上**（不是远程服务器）:

```bash
# 如果使用CLI
cd /path/to/aws-devops-agent-mcp
claude

# 或者打开Claude Code Desktop app
# 并在app中打开这个项目文件夹
```

### 步骤2: 调用MCP工具

在Claude Code对话中输入：

```
请调用devops_echo工具，消息是"Testing Authorization Code + RFC 8707"
```

或者英文：

```
Please call the devops_echo tool with message "Testing Authorization Code + RFC 8707"
```

### 步骤3: 浏览器自动打开

**几秒钟后，浏览器会自动打开**，显示类似这样的页面：

```
┌─────────────────────────────────────────────┐
│  🔐 Sign in to your account                 │
│                                             │
│  Username: [____________________]           │
│            ↑ 输入: admin                    │
│                                             │
│  Password: [____________________]           │
│            ↑ 输入你的密码                    │
│                                             │
│            [ Sign In ]  按这里 →            │
└─────────────────────────────────────────────┘
```

**如果浏览器没有自动打开**:
- 检查是否被浏览器弹窗拦截器阻止
- 在Claude Code输出中查找URL，手动复制到浏览器

### 步骤4: 登录

1. **Username**: 输入 `admin`
2. **Password**: 输入你的Cognito密码
3. 点击 **Sign In**

**如果忘记密码**:
```bash
# 重置密码
aws cognito-idp admin-set-user-password \
  --user-pool-id us-west-2_L0273ULfK \
  --username admin \
  --password 'YourNewPassword123!' \
  --permanent \
  --region us-west-2
```

### 步骤5: 自动完成

登录后，你会看到：

```
┌─────────────────────────────────────────────┐
│  ✅ Authentication Successful!              │
│                                             │
│  Redirecting back to Claude Code...        │
│                                             │
│  You can close this window.                │
└─────────────────────────────────────────────┘
```

**浏览器URL会变成**:
```
http://localhost:8080/callback?code=xxx&state=xxx
```

**几秒钟后，Claude Code会显示**:
```json
{
  "message": "Testing Authorization Code + RFC 8707",
  "echo": true
}
```

🎉 **成功！OAuth流程完成！**

### 步骤6: 验证（可选但推荐）

确认token包含RFC 8707的`aud` claim：

```bash
# 在终端运行
cat ~/.claude/.credentials.json | python3 -c "
import json, sys, base64

data = json.load(sys.stdin)
token = data['mcpOAuth']['devops-agent|2cb25a403a411c4b']['accessToken']

# 解码JWT
payload = token.split('.')[1]
payload += '=' * (4 - len(payload) % 4)
claims = json.loads(base64.urlsafe_b64decode(payload))

print('Token claims:')
print(f'  aud: {claims.get(\"aud\", \"MISSING\")}')
print(f'  scope: {claims.get(\"scope\", \"MISSING\")[:50]}...')
print(f'  username: {claims.get(\"username\", \"MISSING\")}')
print()

if 'aud' in claims:
    print('✅ RFC 8707 compliant: aud claim present!')
    print(f'   Audience: {claims[\"aud\"]}')
else:
    print('❌ RFC 8707 NOT compliant: aud claim missing')
"
```

**预期输出**:
```
Token claims:
  aud: https://devops-agent-mcp-elhze1stwj.gateway.bedrock-agentcore.us-west-2.amazonaws.com/mcp
  scope: DevOpsAgentMcpStack-Gateway-0299DE6E/read DevOpsAg...
  username: admin

✅ RFC 8707 compliant: aud claim present!
   Audience: https://devops-agent-mcp-elhze1stwj.gateway.bedrock-agentcore.us-west-2.amazonaws.com/mcp
```

### 步骤7: 测试后续调用

**无需重新登录**，再次调用工具：

```
请再次调用devops_echo工具，消息是"Second call - no login needed!"
```

**应该立即返回结果**，不会打开浏览器！

```json
{
  "message": "Second call - no login needed!",
  "echo": true
}
```

✅ **验证完成！自动token管理工作正常！**

---

## 方法2️⃣: 手动测试脚本（详细分析）

### 适合场景
- 想看完整OAuth流程的每一步
- 需要验证PKCE参数
- 想确认RFC 8707 `resource`参数被发送
- 需要详细的token claims分析

### 步骤1: 运行测试脚本

```bash
cd /path/to/aws-devops-agent-mcp
python3 tests/manual_oauth_test.py
```

### 步骤2: 查看输出

脚本会显示：

```
======================================================================
Manual OAuth Authorization Code Flow Test
======================================================================

Step 1: Generating PKCE parameters...
  Code verifier: SaVX9jKL3mR5tY8wP...
  Code challenge: fG3dH7kN2qW6xZ9...
  State: uT4bM8cL5pY...

✅ RFC 8707: 'resource' parameter included
  Resource: https://devops-agent-mcp-elhze1stwj...

Step 3: Starting callback server on http://localhost:8080 ...
  Server started. Waiting for OAuth callback...

Step 4: Opening browser for authentication...
  URL: https://devopsagentmcpstack-gateway-0299de6e.auth.us-west-2...

  Please log in with your Cognito credentials.
  After successful login, you'll be redirected back here.

  Waiting for callback...
```

### 步骤3: 在浏览器中登录

同方法1的步骤3-5

### 步骤4: 查看详细输出

登录后，脚本会显示：

```
  ✅ Authorization code received: abc123def456...
  State matches: True

Step 5: Exchanging authorization code for access token...
  Token endpoint: https://devopsagentmcpstack-gateway-0299de6e.auth...
  Grant type: authorization_code
  PKCE: code_verifier=SaVX9jKL...
  RFC 8707: resource=https://devops-agent-mcp-xxx.../mcp

  ✅ Token received successfully!

Step 6: Verifying token structure (RFC 8707)...
  Access token length: 941
  Token type: Bearer
  Expires in: 3600 seconds
  Has refresh_token: True

  JWT Claims:
    sub: 8f3e9a2c-1b4d-5e6f-7a8b-9c0d1e2f3a4b
    aud: https://devops-agent-mcp-elhze1stwj.../mcp
    scope: DevOpsAgentMcpStack-Gateway-0299DE6E/read DevOpsAg...
    token_use: access
    username: admin
    client_id: <COGNITO_CLIENT_ID>

Step 7: RFC 8707 Compliance Check...
  ✅ 'aud' claim present (RFC 8707 compliant)
     Value: https://devops-agent-mcp-elhze1stwj.../mcp
  ✅ 'aud' matches Gateway URL exactly

Step 8: Testing MCP tool call with token...
  ✅ MCP tool call successful!
     Response: {
       "message": "Testing Authorization Code + RFC 8707",
       "echo": true
     }

======================================================================
SUMMARY
======================================================================

✅ Authorization Code Flow: SUCCESS
✅ Token Obtained: 941 bytes
✅ RFC 8707 'aud' claim: Present
✅ Refresh token: Present

🎉 FULL SUCCESS: 100% MCP Compliant!

Your Cognito is now configured for:
  - Authorization Code flow with PKCE
  - RFC 8707 Resource Indicators (aud claim)
  - Automatic token refresh (refresh_token)

Claude Code will work seamlessly with this configuration.
```

### 步骤5: 查看保存的token

脚本会保存详细信息到：

```bash
cat /tmp/oauth_test_token.json | python3 -m json.tool
```

---

## 方法3️⃣: 快速验证（最简单）

### 一行命令测试

如果只想确认能工作，不关心细节：

```bash
# 确保在有浏览器的环境
echo "请调用devops_echo工具，消息是'Quick test'" | claude
```

然后按照浏览器提示登录即可。

---

## 🔍 预期结果总结

### 首次OAuth成功后，你应该看到：

✅ **浏览器行为**:
- 自动打开Cognito登录页
- 登录后显示"Authentication Successful"
- 重定向到localhost:8080/callback

✅ **Claude Code行为**:
- 自动捕获authorization code
- 自动交换token
- 自动保存到credentials.json
- 工具调用自动完成

✅ **Token特征**:
- 包含`aud` claim（RFC 8707）
- 包含`refresh_token`（自动刷新）
- 有效期1小时
- 包含read/write scopes

✅ **后续调用**:
- 无需重新登录
- 无需浏览器
- token自动刷新
- 完全透明

---

## ❌ 常见问题排查

### 问题1: 浏览器没有自动打开

**原因**: 可能被弹窗拦截器阻止

**解决**:
1. 在Claude Code输出中查找OAuth URL
2. 手动复制URL到浏览器
3. 或者允许Claude Code弹出窗口

**查找URL的方法**:
```bash
# 在Claude Code日志中查找
grep -r "oauth2/authorize" ~/.claude/logs/
```

### 问题2: 登录后显示错误

**错误示例**: `invalid_scope` 或 `invalid_request`

**可能原因**:
- Cognito配置不正确

**验证配置**:
```bash
python3 tests/run_tests.py
# 应该显示 6/6 tests passing
```

**如果测试失败**，重新运行配置更新：
```bash
aws cognito-idp update-user-pool-client \
  --user-pool-id us-west-2_L0273ULfK \
  --client-id <COGNITO_CLIENT_ID> \
  --allowed-o-auth-flows code \
  --allowed-o-auth-scopes \
    "DevOpsAgentMcpStack-Gateway-0299DE6E/read" \
    "DevOpsAgentMcpStack-Gateway-0299DE6E/write" \
  --callback-urls "http://localhost:8080/callback" \
  --supported-identity-providers COGNITO \
  --allowed-o-auth-flows-user-pool-client \
  --region us-west-2
```

### 问题3: 用户名或密码错误

**错误**: "Incorrect username or password"

**解决 - 重置密码**:
```bash
aws cognito-idp admin-set-user-password \
  --user-pool-id us-west-2_L0273ULfK \
  --username admin \
  --password 'NewSecurePassword123!' \
  --permanent \
  --region us-west-2
```

### 问题4: localhost:8080连接失败

**错误**: "Cannot connect to localhost:8080"

**可能原因**:
- 端口被占用
- 防火墙阻止

**检查端口**:
```bash
# Linux/Mac
lsof -i :8080

# Windows
netstat -ano | findstr :8080
```

**如果端口被占用**，停止占用的进程或使用不同端口：
```bash
# 使用不同端口（需要重新配置Cognito callback URL）
claude mcp remove devops-agent
claude mcp add-json devops-agent '{
  "type": "http",
  "url": "https://devops-agent-mcp-elhze1stwj.../mcp",
  "oauth": {
    "clientId": "<COGNITO_CLIENT_ID>",
    "callbackPort": 8081
  }
}'

# 然后更新Cognito callback URL
aws cognito-idp update-user-pool-client \
  --user-pool-id us-west-2_L0273ULfK \
  --client-id <COGNITO_CLIENT_ID> \
  --callback-urls "http://localhost:8081/callback" \
  --region us-west-2
```

### 问题5: Token没有aud claim

**检查**:
```bash
cat ~/.claude/.credentials.json | python3 -c "
import json, sys, base64
data = json.load(sys.stdin)
token = data['mcpOAuth']['devops-agent|2cb25a403a411c4b']['accessToken']
payload = token.split('.')[1] + '=' * (4 - len(token.split('.')[1]) % 4)
claims = json.loads(base64.urlsafe_b64decode(payload))
print('aud' in claims)
"
```

**如果返回False**:

**原因**: Cognito User Pool tier不支持RFC 8707

**检查tier**:
```bash
aws cognito-idp describe-user-pool \
  --user-pool-id us-west-2_L0273ULfK \
  --region us-west-2 \
  --query 'UserPool.UserPoolTier'
```

**需要**: ESSENTIALS 或 PLUS

**如果是LITE**: 需要升级User Pool tier（通过AWS Console）

---

## ✅ 验证清单

测试完成后，验证以下项目：

- [ ] 浏览器成功打开到Cognito登录页
- [ ] 登录成功（无错误）
- [ ] 重定向到localhost:8080/callback
- [ ] Claude Code显示工具调用结果
- [ ] Token存在于~/.claude/.credentials.json
- [ ] Token包含`aud` claim
- [ ] Token包含`refresh_token`
- [ ] 第二次调用无需重新登录
- [ ] 工具结果正确（echo返回消息）

**全部打勾**: 🎉 **100% MCP合规达成！**

---

## 📊 成功后的状态

### Token结构（应该看到）

```json
{
  "sub": "admin-user-uuid",
  "aud": "https://devops-agent-mcp-xxx.../mcp",  ← RFC 8707!
  "scope": "DevOpsAgentMcpStack-Gateway-0299DE6E/read write",
  "token_use": "access",
  "username": "admin",
  "client_id": "<COGNITO_CLIENT_ID>",
  "exp": 1780063853,
  "iat": 1780060253
}
```

### Credentials文件（应该看到）

```json
{
  "mcpOAuth": {
    "devops-agent|2cb25a403a411c4b": {
      "serverName": "devops-agent",
      "serverUrl": "https://devops-agent-mcp-xxx.../mcp",
      "accessToken": "eyJraWQ...",  ← 有值!
      "refreshToken": "xxx",         ← 有值!
      "discoveryState": {
        "authorizationServerUrl": "https://cognito-idp...",
        "oauthMetadataFound": true
      }
    }
  }
}
```

### MCP合规度

```
Before OAuth test: 66%
After OAuth test:  100%  🎉

✅ RFC 8707: Token audience binding
✅ Authorization Code + PKCE
✅ Automatic token refresh
✅ No manual token management needed
```

---

## 🚀 测试后的使用

### 日常使用（无需特殊操作）

现在你可以：

1. **随时调用MCP工具**:
   ```
   请调用devops_echo工具，消息是"日常使用"
   ```

2. **Token自动管理**:
   - Token过期前自动刷新
   - 无需手动操作
   - 无需重启Claude Code

3. **完全透明**:
   - 不会再打开浏览器
   - 不需要脚本
   - 就像本地工具一样

### 不再需要的东西

❌ **不再需要**:
- `./scripts/refresh-token.sh` - 不需要手动刷新
- `./scripts/setup.sh` - 一次性设置已完成
- Cron任务 - token自动刷新
- 手动重启Claude Code - 永远不需要

✅ **只需要**:
- 使用Claude Code调用工具
- 其他一切自动完成

---

## 📚 下一步

### 测试完成后

1. **更新Issue #8**:
   ```bash
   gh issue comment 8 --body "✅ OAuth测试完成！Token包含aud claim，RFC 8707验证通过。"
   ```

2. **运行完整验证**:
   ```bash
   python3 tests/verify_token_structure.py
   ```

3. **测试自动刷新**（可选）:
   - 等待token过期（1小时）
   - 再次调用工具
   - 验证自动刷新工作

4. **更新文档**（如果需要）:
   - QUICKSTART.md
   - README.md
   - 标记项目为100% MCP合规

---

## 💡 小贴士

### 最佳实践

1. **首次测试**: 使用方法1（Claude Code直接）- 最真实
2. **深入分析**: 使用方法2（手动脚本）- 看到所有细节
3. **快速验证**: 使用方法3（一行命令）- 最快

### 推荐顺序

1. 先运行预检查: `python3 tests/verify_oauth_ready.py`
2. 首次OAuth: 方法1（Claude Code）
3. 详细验证: 方法2（手动脚本）
4. 日常使用: 直接调用工具

### 时间分配

- **准备**: 1分钟（预检查）
- **首次OAuth**: 2分钟（登录）
- **详细验证**: 5分钟（手动脚本）
- **总计**: ~10分钟

---

## 🎓 学到的东西

完成测试后，你将理解：

1. **OAuth Authorization Code流程**:
   - PKCE如何保护
   - authorization code交换
   - token获取过程

2. **RFC 8707 Resource Indicators**:
   - `resource`参数作用
   - `aud` claim重要性
   - token audience binding

3. **自动token管理**:
   - refresh token机制
   - 自动刷新工作原理
   - 为什么不需要手动管理

4. **MCP OAuth集成**:
   - 客户端如何检测认证
   - OAuth discovery机制
   - 为什么这比Client Credentials好

---

## ✅ 总结

**测试目标**: ✅ 完成首次OAuth，获取RFC 8707 token

**推荐方法**: 方法1（Claude Code直接）

**关键步骤**: 
1. 启动Claude Code
2. 调用MCP工具
3. 浏览器登录
4. 自动完成

**预计时间**: 2-5分钟

**成功标志**: 
- Token包含`aud` claim
- 第二次调用无需登录
- 100% MCP合规

**需要帮助**: 查看"常见问题排查"章节

---

**准备好了吗？开始测试吧！** 🚀

选择一个方法，按照步骤操作，有任何问题随时查看排查指南。
