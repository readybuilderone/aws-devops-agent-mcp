# DevOps Agent MCP - 快速开始指南

> **适用人群**: 第一次使用此MCP服务器的新用户  
> **预计时间**: 15-20分钟  
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

**⚠️ 重要：记录这三个输出值**，后面会用到！

---

## 🔧 步骤2: 添加MCP服务器到Claude Code

### 2.1 获取部署输出

如果忘记记录，可以重新查询：

```bash
aws cloudformation describe-stacks \
  --stack-name DevOpsAgentMcpStack \
  --region us-west-2 \
  --query 'Stacks[0].Outputs' \
  --output table
```

### 2.2 使用CLI命令添加MCP服务器

**⚠️ 注意：不要手动创建`.mcp.json`文件，必须使用此命令！**

```bash
claude mcp add-json devops-agent '{
  "type": "http",
  "url": "YOUR_GATEWAY_URL",
  "oauth": {
    "clientId": "YOUR_CLIENT_ID"
  }
}'
```

替换示例：
```bash
claude mcp add-json devops-agent '{
  "type": "http",
  "url": "https://devops-agent-mcp-elhze1stwj.gateway.bedrock-agentcore.us-west-2.amazonaws.com/mcp",
  "oauth": {
    "clientId": "<COGNITO_CLIENT_ID>"
  }
}'
```

**成功提示**：
```
Added http MCP server devops-agent to local config
```

### 2.3 验证MCP服务器已添加

```bash
claude mcp list
```

应该看到：
```
devops-agent: https://devops-agent-mcp-xxxxx... (HTTP) - ! Needs authentication
```

---

## 🔐 步骤3: 配置OAuth认证

由于技术限制，我们使用Client Credentials流程（机器对机器认证，无需用户登录）。

### 3.1 获取User Pool ID

```bash
aws cloudformation describe-stacks \
  --stack-name DevOpsAgentMcpStack \
  --region us-west-2 \
  --query 'Stacks[0].Outputs[?OutputKey==`ClientId`].OutputValue' \
  --output text
```

记录输出的Client ID。

### 3.2 获取Client Secret

```bash
# 先获取User Pool ID
USER_POOL_ID=$(aws cognito-idp list-user-pools \
  --max-results 10 \
  --region us-west-2 \
  --query "UserPools[?contains(Name, 'DevOpsAgentMcpStack')].Id" \
  --output text)

echo "User Pool ID: $USER_POOL_ID"

# 获取Client Secret
CLIENT_ID="YOUR_CLIENT_ID_FROM_STEP_2.2"

aws cognito-idp describe-user-pool-client \
  --user-pool-id $USER_POOL_ID \
  --client-id $CLIENT_ID \
  --region us-west-2 \
  --query 'UserPoolClient.ClientSecret' \
  --output text
```

**⚠️ 记录输出的Client Secret！它只显示一次。**

### 3.3 配置Cognito支持Client Credentials

```bash
# 设置变量
USER_POOL_ID="us-west-2_XXXXXXXX"  # 从3.2获取
CLIENT_ID="xxxxxxxxxxxxxxxxxx"      # 从2.2获取

# 更新OAuth配置
aws cognito-idp update-user-pool-client \
  --user-pool-id $USER_POOL_ID \
  --client-id $CLIENT_ID \
  --allowed-o-auth-flows client_credentials \
  --allowed-o-auth-scopes \
    "DevOpsAgentMcpStack-Gateway-0299DE6E/read" \
    "DevOpsAgentMcpStack-Gateway-0299DE6E/write" \
  --allowed-o-auth-flows-user-pool-client \
  --region us-west-2
```

**成功提示**：
```json
{
    "UserPoolClient": {
        "AllowedOAuthFlows": ["client_credentials"],
        ...
    }
}
```

---

## 🎫 步骤4: 获取并注入Access Token

### 4.1 获取Token Endpoint

从步骤1的输出或重新查询：

```bash
TOKEN_ENDPOINT=$(aws cloudformation describe-stacks \
  --stack-name DevOpsAgentMcpStack \
  --region us-west-2 \
  --query 'Stacks[0].Outputs[?OutputKey==`TokenEndpoint`].OutputValue' \
  --output text)

echo $TOKEN_ENDPOINT
```

### 4.2 获取Access Token

```bash
# 设置变量
CLIENT_ID="xxxxxxxxxxxxxxxxxx"          # 从步骤2.2
CLIENT_SECRET="yyyyyyyyyyyyyyyyyyyyy"   # 从步骤3.2
TOKEN_ENDPOINT="https://xxxxx.auth.us-west-2.amazoncognito.com/oauth2/token"

# 获取token
curl -X POST $TOKEN_ENDPOINT \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -u "$CLIENT_ID:$CLIENT_SECRET" \
  -d "grant_type=client_credentials&scope=DevOpsAgentMcpStack-Gateway-0299DE6E/read%20DevOpsAgentMcpStack-Gateway-0299DE6E/write" \
  | python3 -m json.tool
```

**成功响应**：
```json
{
    "access_token": "eyJraWQiOiJqOXlFUVRNeEt...",
    "expires_in": 3600,
    "token_type": "Bearer"
}
```

**⚠️ 复制完整的`access_token`值！**

### 4.3 找到MCP配置的Hash值

```bash
# 查看credentials文件
cat ~/.claude/.credentials.json | python3 -m json.tool | grep -A5 devops-agent
```

找到类似这样的行：
```json
"devops-agent|2cb25a403a411c4b": {
```

记录完整的key（包括`devops-agent|`后面的hash）。

### 4.4 注入Token

创建一个临时Python脚本：

```bash
cat > inject_token.py << 'EOF'
import json
import sys

if len(sys.argv) != 3:
    print("用法: python3 inject_token.py <hash> <access_token>")
    sys.exit(1)

hash_key = sys.argv[1]  # 例如: devops-agent|2cb25a403a411c4b
token = sys.argv[2]

# 读取credentials
creds_path = '/home/ubuntu/.claude/.credentials.json'
with open(creds_path, 'r') as f:
    creds = json.load(f)

# 注入token
if 'mcpOAuth' not in creds:
    creds['mcpOAuth'] = {}

if hash_key not in creds['mcpOAuth']:
    print(f"错误: 找不到key '{hash_key}'")
    print(f"可用的keys: {list(creds['mcpOAuth'].keys())}")
    sys.exit(1)

creds['mcpOAuth'][hash_key]['accessToken'] = token

# 保存
with open(creds_path, 'w') as f:
    json.dump(creds, f, indent=2)

print(f"✅ Token已注入到 {hash_key}")
print(f"Token长度: {len(token)} 字符")
EOF
```

运行脚本：

```bash
# 替换为你的实际值
HASH_KEY="devops-agent|2cb25a403a411c4b"
ACCESS_TOKEN="eyJraWQiOiJqOXlFUVRNeEt..."

python3 inject_token.py "$HASH_KEY" "$ACCESS_TOKEN"
```

**成功提示**：
```
✅ Token已注入到 devops-agent|2cb25a403a411c4b
Token长度: 941 字符
```

### 4.5 清理临时文件

```bash
rm inject_token.py
```

---

## ✅ 步骤5: 测试MCP连接

### 5.1 重启Claude Code

**重要：必须重启才能加载新的token！**

```bash
exit       # 如果在Claude Code会话中，先退出
claude     # 重新启动
```

### 5.2 验证连接状态

在Claude Code中运行：

```
/mcp
```

或者在shell中：

```bash
claude mcp list
```

应该看到：
```
✓ Connected 状态，而不是 ! Needs authentication
```

示例：
```
devops-agent: https://devops-agent-mcp-xxxxx... (HTTP) - ✓ Connected
```

### 5.3 测试echo工具

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

### 问题1: "Needs authentication" 状态持续存在

**原因**: Token未正确注入或需要重启

**解决方案**:
1. 验证token是否正确注入：
   ```bash
   cat ~/.claude/.credentials.json | python3 -c "import sys, json; data=json.load(sys.stdin); print('Token长度:', len(data['mcpOAuth']['devops-agent|XXX']['accessToken']))"
   ```
2. 确保已重启Claude Code
3. 运行 `/reload-plugins`

### 问题2: Token获取失败 (401 Unauthorized)

**原因**: Client ID或Client Secret错误

**解决方案**:
1. 重新获取Client Secret（步骤3.2）
2. 确保Base64编码正确：
   ```bash
   echo -n "$CLIENT_ID:$CLIENT_SECRET" | base64
   ```

### 问题3: "invalid_scope" 错误

**原因**: Cognito OAuth flows配置错误

**解决方案**:
重新运行步骤3.3，确保配置为`client_credentials`：
```bash
aws cognito-idp describe-user-pool-client \
  --user-pool-id $USER_POOL_ID \
  --client-id $CLIENT_ID \
  --region us-west-2 \
  --query 'UserPoolClient.AllowedOAuthFlows'
```

应该返回：`["client_credentials"]`

### 问题4: Token过期（1小时后）

**原因**: Access token有效期为3600秒（1小时）

**解决方案**:
重新运行步骤4.2-4.4获取新token并注入。

**自动化建议**（高级）:
创建一个刷新脚本，设置cron任务每50分钟运行一次。

### 问题5: 找不到hash key

**原因**: MCP服务器配置key与实际不匹配

**解决方案**:
```bash
# 查看所有可用的keys
cat ~/.claude/.credentials.json | python3 -c "import sys, json; data=json.load(sys.stdin); print(list(data.get('mcpOAuth', {}).keys()))"
```

使用输出中显示的实际key。

---

## 📚 下一步

现在你的MCP服务器已经运行，可以：

1. **查看可用工具**：
   ```
   列出所有devops-agent的MCP工具
   ```

2. **实现完整功能**：
   - 参考Issue #3: 实现`devops_list_spaces`
   - 参考Issue #4: 实现`devops_query`

3. **阅读完整文档**：
   - [INTEGRATION.md](./INTEGRATION.md) - 详细集成指南
   - [aws-mcp-vs-devops-agent.md](./aws-mcp-vs-devops-agent.md) - 架构设计
   - Issue #7 - 测试报告和经验教训

---

## 💡 提示

### 保存配置脚本

建议将你的配置保存为脚本，方便下次使用：

```bash
cat > refresh_token.sh << 'EOF'
#!/bin/bash
set -e

# 配置变量（替换为你的实际值）
CLIENT_ID="xxxxxxxxxxxxxxxxxx"
CLIENT_SECRET="yyyyyyyyyyyyyyyyyyyyy"
TOKEN_ENDPOINT="https://xxxxx.auth.us-west-2.amazoncognito.com/oauth2/token"
HASH_KEY="devops-agent|2cb25a403a411c4b"

# 获取新token
echo "🔄 获取新token..."
RESPONSE=$(curl -s -X POST $TOKEN_ENDPOINT \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -u "$CLIENT_ID:$CLIENT_SECRET" \
  -d "grant_type=client_credentials&scope=DevOpsAgentMcpStack-Gateway-0299DE6E/read%20DevOpsAgentMcpStack-Gateway-0299DE6E/write")

ACCESS_TOKEN=$(echo $RESPONSE | python3 -c "import sys, json; print(json.load(sys.stdin)['access_token'])")

# 注入token
echo "💉 注入token..."
python3 << PYEOF
import json

with open('~/.claude/.credentials.json', 'r') as f:
    creds = json.load(f)

creds['mcpOAuth']['$HASH_KEY']['accessToken'] = '$ACCESS_TOKEN'

with open('~/.claude/.credentials.json', 'w') as f:
    json.dump(creds, f, indent=2)
PYEOF

echo "✅ Token已刷新！"
echo "📝 请重启Claude Code以生效"
EOF

chmod +x refresh_token.sh
```

使用：
```bash
./refresh_token.sh
```

### 设置Token自动刷新

```bash
# 编辑crontab
crontab -e

# 添加（每50分钟刷新一次）
*/50 * * * * /path/to/refresh_token.sh >> /tmp/mcp_token_refresh.log 2>&1
```

---

## 🆘 获取帮助

如果遇到问题：

1. **检查日志**：
   ```bash
   # Lambda日志
   aws logs tail /aws/lambda/DevOpsAgentMcpStack-Handler --follow --region us-west-2
   
   # Claude Code会话日志
   tail -f ~/.claude/sessions/*.log
   ```

2. **提Issue**：
   https://github.com/readybuilderone/aws-devops-agent-mcp/issues

3. **查看已知问题**：
   - Issue #7: 集成测试报告和常见问题

---

**祝你使用愉快！🎉**
