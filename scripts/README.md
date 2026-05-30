# 脚本工具

本目录包含用于配置和维护DevOps Agent MCP的自动化脚本。

## 📁 文件说明

| 文件 | 用途 | 使用频率 |
|------|------|---------|
| `setup.sh` | 交互式一键设置脚本 | 首次设置 |
| `get-headers.sh` | headersHelper：连接时自动获取/缓存token | 由Claude Code自动调用 |
| `token-config.sh.example` | 配置文件模板 | 参考 |
| `token-config.sh` | 实际凭证（不提交git） | 由setup.sh生成 |

## 🔑 工作原理

本MCP服务器是远程HTTP服务器，由Cognito OAuth（Client Credentials流程）保护，
access token有效期1小时。

Claude Code通过 **`headersHelper`** 机制对接：`.mcp.json` 中
`headersHelper` 指向 `get-headers.sh`。Claude Code在**每次连接时**执行该脚本，
脚本读取 `token-config.sh` 中的凭证，向Cognito换取token并输出
`{"Authorization": "Bearer ..."}`。

token会被缓存到 `${TMPDIR:-/tmp}/devops-agent-mcp-token.cache`，
在到期前（留5分钟余量）直接复用，到期后自动重新获取。

**因此**：无需手动刷新、无需cron、无需注入 `~/.claude/.credentials.json`、
无需token过期后重启Claude Code。

## 🚀 快速使用

### 首次设置

```bash
# 运行交互式设置向导（自动生成 token-config.sh 并注册MCP）
./setup.sh

# 在Claude Code中验证
/mcp        # 应显示 ✓ Connected
```

### 手动配置（不用setup.sh）

```bash
# 1. 准备凭证
cp token-config.sh.example token-config.sh
chmod 600 token-config.sh
# 编辑填入 CLIENT_ID / CLIENT_SECRET / TOKEN_ENDPOINT / SCOPE

# 2. 验证脚本能拿到token
./get-headers.sh        # 应输出 {"Authorization": "Bearer ..."}

# 3. 注册MCP服务器
claude mcp add-json devops-agent "{
  \"type\": \"http\",
  \"url\": \"<GATEWAY_URL>\",
  \"headersHelper\": \"$(pwd)/get-headers.sh\"
}"
```

## 📖 详细说明

### setup.sh

**功能**: 全自动设置MCP服务器连接

**流程**:
1. 检查前提条件（aws / python3 / claude / curl）
2. 从CloudFormation获取Stack输出（GatewayUrl / ClientId / TokenEndpoint）
3. 获取Cognito配置（User Pool ID / Client Secret / resource server scope）
4. 配置OAuth Client Credentials流程
5. 生成 `token-config.sh`（权限600）并验证token获取
6. 用 `headersHelper` 把MCP服务器加入Claude Code

### get-headers.sh

**功能**: Claude Code的headersHelper，输出包含有效token的HTTP header。

**特性**:
- ✅ 读取 `token-config.sh` 凭证，向Cognito换取token
- ✅ token缓存到临时文件，到期前复用（减少token端点调用）
- ✅ 到期自动重新获取，对Claude Code透明
- ✅ 所有日志走stderr，stdout只输出一行JSON
- ✅ 失败时退出非0并在stderr打印原因

**环境变量覆盖**（可选）:
- `TOKEN_CONFIG_FILE` - 自定义凭证文件路径（默认同目录 `token-config.sh`）
- `TOKEN_CACHE_FILE` - 自定义缓存文件路径

**手动测试**:
```bash
./get-headers.sh           # 看stdout的JSON与stderr的日志
```

### token-config.sh

**功能**: 存储Cognito凭证，供 `get-headers.sh` 读取。

**配置项**:
```bash
CLIENT_ID="..."        # Cognito Client ID（CDK输出）
CLIENT_SECRET="..."    # Cognito Client Secret（describe-user-pool-client）
TOKEN_ENDPOINT="..."   # Token端点（CDK输出）
SCOPE="<RS>/read <RS>/write"   # resource server scope
```

**安全注意**:
- ⚠️ 含Client Secret，已在 `.gitignore` 中，**不会**提交git
- ⚠️ 权限应为 `600`（`chmod 600 token-config.sh`）

## 🔧 故障排查

### get-headers.sh 报 invalid_client

**原因**: CLIENT_ID或CLIENT_SECRET错误/过期。

**解决**:
```bash
aws cognito-idp describe-user-pool-client \
  --user-pool-id $USER_POOL_ID \
  --client-id $CLIENT_ID \
  --region us-west-2 \
  --query 'UserPoolClient.ClientSecret' --output text
# 更新 token-config.sh 中的 CLIENT_SECRET
```

### get-headers.sh 报 invalid_scope

**原因**: `SCOPE` 中的resource server标识符与实际不符。

**解决**:
```bash
aws cognito-idp list-resource-servers --user-pool-id $USER_POOL_ID \
  --max-results 10 --region us-west-2 \
  --query 'ResourceServers[].Identifier'
# 用实际标识符更新 SCOPE="<ID>/read <ID>/write"
```

### /mcp 显示 Needs authentication

1. 手动跑 `./get-headers.sh` 确认能输出JSON
2. 确认 `.mcp.json` 中 `headersHelper` 路径正确、脚本可执行
3. 确认 `token-config.sh` 四个变量都已填

## 🔒 安全建议

1. **不要提交凭证**：`token-config.sh` 已在 `.gitignore`
2. **限制文件权限**：`chmod 600 token-config.sh`
3. **定期轮换Client Secret**，并考虑使用AWS Secrets Manager

## 📚 相关文档

- [QUICKSTART.md](../QUICKSTART.md) - 完整设置指南
- [INTEGRATION.md](../INTEGRATION.md) - 集成文档
