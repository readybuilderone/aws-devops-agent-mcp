# 脚本工具

本目录包含用于配置和维护DevOps Agent MCP的自动化脚本。

## 📁 文件说明

| 文件 | 用途 | 使用频率 |
|------|------|---------|
| `setup.sh` | 交互式一键设置脚本 | 首次设置 |
| `refresh-token.sh` | Token刷新脚本 | 每小时或自动 |
| `token-config.sh.example` | 配置文件模板 | 参考 |
| `token-config.sh` | 实际配置（不提交git） | 生成后自动使用 |

## 🚀 快速使用

### 首次设置

```bash
# 运行交互式设置向导
./setup.sh

# 设置完成后重启Claude Code
exit
claude
```

### 刷新Token

```bash
# 手动刷新
./refresh-token.sh

# 查看帮助
./refresh-token.sh --help
```

### 自动刷新设置

```bash
# 添加到crontab（每50分钟执行）
(crontab -l 2>/dev/null; echo "*/50 * * * * $(pwd)/refresh-token.sh") | crontab -

# 查看cron任务
crontab -l

# 查看刷新日志
tail -f /tmp/mcp_token_refresh.log
```

## 📖 详细说明

### setup.sh

**功能**: 全自动设置MCP服务器连接

**流程**:
1. 检查前提条件（AWS CLI, Python, Claude Code）
2. 从CloudFormation获取Stack输出
3. 获取Cognito配置（User Pool ID, Client Secret）
4. 配置OAuth Client Credentials流程
5. 添加MCP服务器到Claude Code
6. 自动查找Hash Key
7. 生成`token-config.sh`
8. 获取并注入第一个access token

**使用**:
```bash
./setup.sh
```

**注意事项**:
- 必须先部署CDK Stack
- 需要AWS CLI配置好凭证
- 需要在us-west-2区域有权限

---

### refresh-token.sh

**功能**: 获取新的access token并注入到Claude Code

**依赖**: `token-config.sh` 配置文件

**使用**:
```bash
# 使用默认配置
./refresh-token.sh

# 指定配置文件
./refresh-token.sh --config /path/to/config.sh

# 查看帮助
./refresh-token.sh --help
```

**特性**:
- ✅ 自动备份credentials文件
- ✅ 失败时自动恢复备份
- ✅ 保留最近5个备份
- ✅ 详细的错误提示
- ✅ 支持自定义配置文件路径

**返回码**:
- `0` - 成功
- `1` - 失败（配置错误、网络错误、注入失败等）

**日志输出**:
```
[INFO] 加载配置: token-config.sh
[INFO] 正在获取access token...
[INFO] Token获取成功 (长度: 941)
[INFO] 正在注入token到Claude Code...
[INFO] 已备份credentials到: ~/.claude/.credentials.json.backup.20260529_130000
[INFO] ✅ Token注入成功！
[WARN] 📝 请重启Claude Code以生效
```

---

### token-config.sh

**功能**: 存储MCP配置信息

**生成方式**:
1. 由`setup.sh`自动生成，或
2. 手动复制`token-config.sh.example`并填写

**配置项说明**:

```bash
# Cognito Client ID
# 从CDK输出的ClientId获取
CLIENT_ID="your-client-id-here"

# Cognito Client Secret  
# 运行: aws cognito-idp describe-user-pool-client --user-pool-id <ID> --client-id <ID> --query 'UserPoolClient.ClientSecret'
CLIENT_SECRET="your-client-secret-here"

# Token Endpoint
# 从CDK输出的TokenEndpoint获取
TOKEN_ENDPOINT="https://xxxxx.auth.us-west-2.amazoncognito.com/oauth2/token"

# MCP服务器Hash Key
# 从 ~/.claude/.credentials.json 获取，格式: devops-agent|xxxxxxxx
HASH_KEY="devops-agent|your-hash-here"

# OAuth Scopes（通常不需要修改）
SCOPE="DevOpsAgentMcpStack-Gateway-0299DE6E/read DevOpsAgentMcpStack-Gateway-0299DE6E/write"
```

**安全注意**:
- ⚠️ 此文件包含敏感信息（Client Secret）
- ⚠️ 已添加到`.gitignore`，不会提交到git
- ⚠️ 文件权限自动设置为`600`（仅所有者可读写）

**手动创建**:
```bash
# 复制模板
cp token-config.sh.example token-config.sh

# 编辑配置
nano token-config.sh

# 设置权限
chmod 600 token-config.sh
```

---

## 🔧 故障排查

### 问题1: setup.sh找不到Stack

**症状**:
```
✗ Stack不存在: DevOpsAgentMcpStack
```

**解决**:
```bash
# 检查Stack是否部署
aws cloudformation list-stacks --region us-west-2 | grep DevOpsAgentMcpStack

# 如果未部署，运行
cd ../cdk
cdk deploy --region us-west-2
```

### 问题2: refresh-token.sh报token解析失败

**症状**:
```
[ERROR] Token解析失败
ERROR: invalid_client
```

**原因**: Client ID或Client Secret错误

**解决**:
```bash
# 重新获取Client Secret
aws cognito-idp describe-user-pool-client \
  --user-pool-id $USER_POOL_ID \
  --client-id $CLIENT_ID \
  --region us-west-2 \
  --query 'UserPoolClient.ClientSecret'

# 更新token-config.sh中的CLIENT_SECRET
```

### 问题3: Token注入后仍然"Needs authentication"

**症状**: `claude mcp list`仍显示需要认证

**原因**: 未重启Claude Code

**解决**:
```bash
# 1. 退出Claude Code
exit

# 2. 重新启动
claude

# 3. 重新加载插件
/reload-plugins

# 4. 验证状态
/mcp
```

### 问题4: 找不到Hash Key

**症状**:
```
ERROR: 找不到key: devops-agent|xxxxx
```

**解决**:
```bash
# 查看所有可用的keys
cat ~/.claude/.credentials.json | \
  python3 -c "import sys,json; print(list(json.load(sys.stdin).get('mcpOAuth',{}).keys()))"

# 更新token-config.sh中的HASH_KEY为实际的key
```

### 问题5: Cron任务不执行

**检查**:
```bash
# 查看cron日志
tail -f /var/log/syslog | grep CRON

# 或查看脚本输出
tail -f /tmp/mcp_token_refresh.log

# 测试cron表达式
# 访问: https://crontab.guru/#*/50_*_*_*_*
```

**常见原因**:
- 脚本路径不是绝对路径
- 脚本没有执行权限
- cron环境变量缺失（PATH等）

**解决**:
```bash
# 使用绝对路径
SCRIPT_PATH="$(pwd)/refresh-token.sh"
(crontab -l 2>/dev/null; echo "*/50 * * * * $SCRIPT_PATH >> /tmp/mcp_token_refresh.log 2>&1") | crontab -
```

---

## 📝 开发

### 修改脚本

```bash
# 编辑脚本
nano refresh-token.sh

# 测试
./refresh-token.sh

# 提交（注意不要提交token-config.sh）
git add refresh-token.sh
git commit -m "feat: improve token refresh script"
```

### 添加新脚本

```bash
# 创建脚本
cat > new-script.sh << 'EOF'
#!/bin/bash
# 你的脚本内容
EOF

# 添加执行权限
chmod +x new-script.sh

# 更新本README
```

---

## 🔒 安全建议

1. **不要提交配置文件**
   - `token-config.sh`已在`.gitignore`中
   - 不要将Client Secret放入代码

2. **定期轮换凭证**
   - 定期更新Client Secret
   - 考虑使用AWS Secrets Manager

3. **限制文件权限**
   ```bash
   chmod 600 token-config.sh
   chmod 700 *.sh
   ```

4. **审计日志**
   ```bash
   # 查看token获取历史
   grep "Token获取成功" /tmp/mcp_token_refresh.log
   ```

---

## 📚 相关文档

- [QUICKSTART.md](../QUICKSTART.md) - 完整设置指南
- [INTEGRATION.md](../INTEGRATION.md) - 集成文档
- Issue #7 - 测试报告和经验教训
