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
  "url": "https://devops-agent-mcp-xxxxx.gateway.bedrock-agentcore.us-west-2.amazonaws.com/mcp",
  "oauth": {
    "clientId": "YOUR_CLIENT_ID"
  }
}'
```

**成功提示**：
```
Added http MCP server devops-agent to local config
```

> **💡 关于`oauth.clientId`的作用**
>
> 这个配置**不是**让你走浏览器登录。它的作用是让Claude Code在
> `~/.claude/.credentials.json` 中为本服务器创建一个OAuth条目
> （key形如 `devops-agent|<hash>`）。
>
> 由于Claude Code原生只支持Authorization Code（浏览器登录）流程，而本项目
> 使用的是Client Credentials（M2M）流程，我们会在步骤3-4中用脚本**直接获取
> 并注入token**到这个条目里，从而绕过浏览器登录。
>
> 详见 `docs/authorization-code-attempt-postmortem.md`。

### 2.3 验证MCP服务器已添加

```bash
claude mcp list
```

应该看到：
```
devops-agent: https://devops-agent-mcp-xxxxx... (HTTP) - ! Needs authentication
```

---

## 🔐 步骤3: 准备Cognito凭证

由于Claude Code原生不支持Client Credentials，我们手动获取token后注入。本步骤
收集所需凭证。

> **💡 提示**：步骤3-4可以用一键脚本 `./scripts/setup.sh` 全部自动完成。
> 下面是脚本背后的手动步骤，便于理解和排查。

### 3.1 收集Client ID、User Pool ID和Token Endpoint

```bash
# Client ID (从CDK输出)
CLIENT_ID=$(aws cloudformation describe-stacks \
  --stack-name DevOpsAgentMcpStack \
  --region us-west-2 \
  --query 'Stacks[0].Outputs[?OutputKey==`ClientId`].OutputValue' \
  --output text)

# User Pool ID
USER_POOL_ID=$(aws cognito-idp list-user-pools \
  --max-results 10 \
  --region us-west-2 \
  --query "UserPools[?contains(Name, 'DevOpsAgentMcpStack')].Id" \
  --output text)

# Token Endpoint (从CDK输出)
TOKEN_ENDPOINT=$(aws cloudformation describe-stacks \
  --stack-name DevOpsAgentMcpStack \
  --region us-west-2 \
  --query 'Stacks[0].Outputs[?OutputKey==`TokenEndpoint`].OutputValue' \
  --output text)

echo "Client ID:      $CLIENT_ID"
echo "User Pool ID:   $USER_POOL_ID"
echo "Token Endpoint: $TOKEN_ENDPOINT"
```

### 3.2 获取Client Secret

```bash
CLIENT_SECRET=$(aws cognito-idp describe-user-pool-client \
  --user-pool-id $USER_POOL_ID \
  --client-id $CLIENT_ID \
  --region us-west-2 \
  --query 'UserPoolClient.ClientSecret' \
  --output text)

echo "Client Secret: $CLIENT_SECRET"
```

**⚠️ Client Secret是机密，请勿提交到git或分享。**

### 3.3 确认Cognito使用Client Credentials流程

App Client默认应已配置为 `client_credentials`。验证：

```bash
aws cognito-idp describe-user-pool-client \
  --user-pool-id $USER_POOL_ID \
  --client-id $CLIENT_ID \
  --region us-west-2 \
  --query 'UserPoolClient.AllowedOAuthFlows' \
  --output json
```

应返回 `["client_credentials"]`。如果不是，运行以下命令修正
（请先用实际的resource server标识符替换scope中的占位符——
可在CDK输出或 `aws cognito-idp list-resource-servers` 中查到）：

```bash
aws cognito-idp update-user-pool-client \
  --user-pool-id $USER_POOL_ID \
  --client-id $CLIENT_ID \
  --allowed-o-auth-flows client_credentials \
  --allowed-o-auth-scopes \
    "<RESOURCE_SERVER_ID>/read" \
    "<RESOURCE_SERVER_ID>/write" \
  --allowed-o-auth-flows-user-pool-client \
  --region us-west-2
```

---

## 🎫 步骤4: 获取并注入Access Token

本项目提供了 `scripts/refresh-token.sh` 来自动完成"获取token → 注入到
Claude Code"的全过程。你只需创建一份配置文件。

### 4.1 找到MCP配置的Hash Key

步骤2.2添加MCP服务器后，Claude Code会在credentials中创建一个OAuth条目。
找到它的key：

```bash
cat ~/.claude/.credentials.json \
  | python3 -c "import sys, json; print('\n'.join(k for k in json.load(sys.stdin).get('mcpOAuth', {}) if 'devops-agent' in k))"
```

输出形如 `devops-agent|2cb25a403a411c4b`，记录完整的key。

> 如果没有任何输出，说明MCP条目还没创建——请确认步骤2.2成功执行，
> 并至少启动过一次Claude Code。

### 4.2 创建token配置文件

复制模板并填入步骤3收集的值：

```bash
cp scripts/token-config.sh.example scripts/token-config.sh
chmod 600 scripts/token-config.sh   # 含密钥，限制权限
```

编辑 `scripts/token-config.sh`，填入：

```bash
CLIENT_ID="<步骤3.1的Client ID>"
CLIENT_SECRET="<步骤3.2的Client Secret>"
TOKEN_ENDPOINT="<步骤3.1的Token Endpoint>"
HASH_KEY="<步骤4.1的Hash Key, 形如 devops-agent|xxxx>"
SCOPE="<RESOURCE_SERVER_ID>/read <RESOURCE_SERVER_ID>/write"
```

> **🔒 安全提示**：`scripts/token-config.sh` 含Client Secret，已被
> `.gitignore` 忽略，**不会**提交到git。请勿手动取消忽略。

### 4.3 运行刷新脚本

```bash
./scripts/refresh-token.sh
```

脚本会自动：
1. 用Client Credentials向Token Endpoint请求access token
2. 备份 `~/.claude/.credentials.json`
3. 把token注入到 `mcpOAuth[HASH_KEY].accessToken`

**成功提示**：
```
[INFO] Token获取成功 (长度: 941)
[INFO] ✅ Token注入成功！
[WARN] 📝 请重启Claude Code以生效
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
重新运行刷新脚本即可：

```bash
./scripts/refresh-token.sh
```

然后重启Claude Code。自动化方法见下方"设置Token自动刷新"。

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

### Token刷新

配置一次 `scripts/token-config.sh` 后，每次token过期只需重新运行：

```bash
./scripts/refresh-token.sh
```

然后重启Claude Code即可。无需重新填写任何凭证。

### 设置Token自动刷新

用cron每50分钟自动刷新（token有效期1小时）：

```bash
# 添加到crontab（使用绝对路径）
(crontab -l 2>/dev/null; echo "*/50 * * * * $(pwd)/scripts/refresh-token.sh >> /tmp/mcp_token_refresh.log 2>&1") | crontab -
```

> 注意：自动刷新会更新credentials文件，但Claude Code需要重启才会加载新token。
> 对于长时间运行的会话，过期后手动重启一次即可。

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
