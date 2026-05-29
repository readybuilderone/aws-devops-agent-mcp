# CDK部署指南

本目录包含AWS CDK (Python)代码，用于部署DevOps Agent MCP Server基础设施。

## 架构组件

- **AgentCore Gateway** - Remote MCP endpoint with built-in OAuth
- **Cognito User Pool** - OAuth authentication (Client Credentials flow)
- **Lambda Function** - MCP tool implementation
- **Resource Server** - OAuth scopes definition

## 快速部署

```bash
# 1. 安装依赖
cd cdk
pip install -r requirements.txt

# 2. Bootstrap (首次使用CDK)
cdk bootstrap aws://YOUR_ACCOUNT_ID/us-west-2

# 3. 部署
cdk deploy --region us-west-2
```

## 重要配置

### Cognito OAuth配置

Stack已配置为使用**Client Credentials流程**（机器对机器认证）：

```python
# 在 devops_agent_mcp_stack.py 中
cfn_client.add_property_override("AllowedOAuthFlows", ["client_credentials"])
cfn_client.add_property_override("AllowedOAuthFlowsUserPoolClient", True)
```

**为什么使用Client Credentials?**

经过测试发现，MCP OAuth规范（RFC 8707）与AWS Cognito不兼容：
- MCP客户端发送`resource`参数
- Cognito不支持RFC 8707 Resource Indicators  
- Authorization Code流程导致`invalid_scope`错误

详见：[INTEGRATION.md](../INTEGRATION.md) 和 [Issue #7](https://github.com/readybuilderone/aws-devops-agent-mcp/issues/7)

### OAuth Scopes

Gateway自动创建Resource Server，提供以下scopes：
- `{ResourceServerIdentifier}/read` - 读取权限
- `{ResourceServerIdentifier}/write` - 写入权限

Resource Server Identifier格式: `{StackName}-Gateway-{UniqueId}`

示例: `DevOpsAgentMcpStack-Gateway-0299DE6E`

## Stack输出

部署后，Stack会输出以下值：

| 输出 | 说明 | 用途 |
|------|------|------|
| `GatewayUrl` | MCP endpoint URL | Claude Code MCP配置 |
| `ClientId` | Cognito Client ID | OAuth认证 |
| `TokenEndpoint` | Token获取端点 | 获取access token |
| `SetupInstructions` | 快速设置命令 | 提示 |

获取输出：
```bash
aws cloudformation describe-stacks \
  --stack-name DevOpsAgentMcpStack \
  --region us-west-2 \
  --query 'Stacks[0].Outputs'
```

## 更新Lambda代码

快速部署Lambda变更（不重新创建资源）：

```bash
cdk deploy --hotswap
```

**注意**: `--hotswap`仅用于开发，生产环境应使用完整部署。

## 自定义配置

### 修改Agent Space ID

```bash
# 通过context传递
cdk deploy --context agent_space_id=your-space-id

# 或设置环境变量
export DEFAULT_AGENT_SPACE_ID=your-space-id
cdk deploy
```

### 修改工具定义

编辑 `stacks/devops_agent_mcp_stack.py` 中的 `TOOL_SCHEMA`：

```python
TOOL_SCHEMA = [
    agentcore.ToolDefinition(
        name="your_tool_name",
        description="Tool description",
        input_schema=agentcore.SchemaDefinition(
            type=agentcore.SchemaDefinitionType.OBJECT,
            properties={
                "param": agentcore.SchemaDefinition(
                    type=agentcore.SchemaDefinitionType.STRING,
                    description="Parameter description",
                )
            },
            required=["param"],
        ),
    )
]
```

### 修改Lambda配置

```python
handler = _lambda.Function(self, "Handler",
    runtime=_lambda.Runtime.PYTHON_3_12,
    handler="handler.lambda_handler",
    code=_lambda.Code.from_asset("../lambda"),
    timeout=Duration.seconds(60),          # 调整超时
    memory_size=512,                        # 调整内存
    environment={
        "DEFAULT_AGENT_SPACE_ID": agent_space_id,
        "LOG_LEVEL": "INFO",                # 添加环境变量
    },
)
```

## 故障排查

### 问题1: Bootstrap失败

**错误**: `This stack uses assets, so the toolkit stack must be deployed`

**解决**:
```bash
cdk bootstrap aws://YOUR_ACCOUNT_ID/us-west-2
```

### 问题2: OAuth配置未生效

**原因**: 手动修改了Cognito配置，但CDK代码未同步

**解决**: CDK代码已更新，重新部署：
```bash
cdk deploy --region us-west-2
```

### 问题3: Gateway创建失败

**可能原因**: 
- Region不支持AgentCore
- IAM权限不足

**检查**:
```bash
# 检查AgentCore可用性
aws bedrock list-foundation-models --region us-west-2

# 检查IAM权限
aws sts get-caller-identity
```

### 问题4: Client Secret轮换

**背景**: Cognito Client Secret在创建后无法查看

**获取方式**:
```bash
aws cognito-idp describe-user-pool-client \
  --user-pool-id <POOL_ID> \
  --client-id <CLIENT_ID> \
  --region us-west-2 \
  --query 'UserPoolClient.ClientSecret'
```

**如果忘记**: 必须重新创建客户端或更新secret（需手动操作）

## 清理资源

```bash
# 删除整个Stack
cdk destroy

# 确认删除
> Are you sure you want to delete: DevOpsAgentMcpStack (y/n)? y
```

**注意**: 
- Cognito User Pool可能需要手动删除
- CloudWatch Logs会保留（除非手动删除）

## 开发工作流

### 1. 修改Lambda代码

```bash
# 编辑 ../lambda/handler.py
nano ../lambda/handler.py

# 快速部署
cdk deploy --hotswap

# 测试
aws lambda invoke \
  --function-name DevOpsAgentMcpStack-Handler \
  --region us-west-2 \
  response.json
```

### 2. 查看Lambda日志

```bash
aws logs tail /aws/lambda/DevOpsAgentMcpStack-Handler \
  --follow \
  --region us-west-2
```

### 3. 测试Gateway端点

```bash
# 获取access token
TOKEN=$(curl -s -X POST $TOKEN_ENDPOINT \
  -u "$CLIENT_ID:$CLIENT_SECRET" \
  -d "grant_type=client_credentials&scope=..." \
  | jq -r '.access_token')

# 测试MCP endpoint
curl -X POST $GATEWAY_URL \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"tools/list","id":1}'
```

## 成本估算

**估算成本** (us-west-2, 2024年价格):

| 服务 | 用量 | 月成本 |
|------|------|--------|
| Lambda | 1000次调用/月, 512MB, 3s avg | ~$0.20 |
| Cognito | 1000次认证/月 | 免费层 |
| AgentCore Gateway | 按请求计费 | ~$0.50 |
| CloudWatch Logs | 1GB日志 | ~$0.50 |
| **总计** | | **~$1.20/月** |

实际成本取决于使用量。

## 相关文档

- [QUICKSTART.md](../QUICKSTART.md) - 新手设置指南
- [INTEGRATION.md](../INTEGRATION.md) - 集成和认证详情
- [../scripts/README.md](../scripts/README.md) - 自动化脚本
- [AWS CDK文档](https://docs.aws.amazon.com/cdk/)
- [AgentCore Gateway文档](https://docs.aws.amazon.com/bedrock/latest/userguide/agentcore.html)
