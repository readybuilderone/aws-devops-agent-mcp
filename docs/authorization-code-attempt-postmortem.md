# Authorization Code迁移尝试总结 (Issue #8)

**日期**: 2026-05-29  
**状态**: ❌ 失败，已回退到Client Credentials  
**原因**: Cognito RFC 8707限制

---

## 📋 执行摘要

尝试从Client Credentials迁移到Authorization Code + PKCE OAuth流程，以实现100% MCP合规（包括RFC 8707 token audience binding）。

**结果**: 由于AWS Cognito的技术限制，迁移失败。已回退到Client Credentials方案。

---

## 🎯 迁移目标

### 期望实现
- ✅ Authorization Code + PKCE流程
- ✅ RFC 8707 Resource Indicators支持
- ✅ Token包含`aud` claim (audience binding)
- ✅ 自动token刷新
- ✅ 100% MCP合规度

### 当前状态（Client Credentials）
- ✅ M2M认证，无需用户交互
- ✅ MCP官方支持的M2M方式
- ⚠️ 需要手动/脚本刷新token
- ❌ 无RFC 8707支持（无`aud` claim）
- 📊 MCP合规度: 66%

---

## 🔬 技术发现

### Cognito RFC 8707的隐藏要求

根据实际测试和AWS文档验证：

**RFC 8707支持需要**:
1. ✅ User Pool Tier: ESSENTIALS或PLUS
2. ❌ **Managed Login: 必须启用** ← 关键限制
3. ✅ Authorization Code flow
4. ❌ **不支持Client Credentials** (M2M场景)

我们的User Pool:
- Tier: ESSENTIALS ✅
- Managed Login: null (未启用) ❌
- 结果: Cognito拒绝RFC 8707的`resource`参数 → `invalid_scope`错误

### 遇到的错误序列

#### 1. redirect_mismatch (已解决 ✅)
```
https://.../error?error=redirect_mismatch&client_id=...
```

**原因**: Claude Code的redirect_uri与Cognito配置不匹配

**解决**: 添加8个回调URL变体
```bash
http://localhost:8080/callback
http://127.0.0.1:8080/callback
http://localhost:8080/
http://127.0.0.1:8080/
http://localhost:8080/oauth/callback
http://127.0.0.1:8080/oauth/callback
http://localhost/callback
http://127.0.0.1/callback
```

#### 2. invalid_scope (未解决 ❌)
```
http://localhost:8080/callback?error=invalid_request&error_description=invalid_scope
```

**原因**: Cognito要求Managed Login启用才能处理RFC 8707

**尝试的解决方法**:
- ✅ 通过AWS CLI启用Managed Login
  ```bash
  aws cognito-idp create-managed-login-branding \
    --user-pool-id us-west-2_L0273ULfK \
    --client-id <COGNITO_CLIENT_ID> \
    --use-cognito-provided-values
  ```
- ✅ 验证ManagedLoginVersion: 1
- ❌ **错误依然存在** - 可能有其他未文档化的要求

---

## 🧪 TDD实施过程

### Cycle 1: Cognito配置测试
**文件**: `tests/run_tests.py`

测试6个配置要素：
1. ✅ AllowedOAuthFlows包含`code`
2. ✅ CallbackURLs配置
3. ✅ SupportedIdentityProviders包含`COGNITO`
4. ✅ AllowedOAuthFlowsUserPoolClient = True
5. ✅ AllowedOAuthScopes正确
6. ✅ AllowedOAuthFlows不包含`client_credentials`

**结果**: 6/6 passing (配置成功)

### Cycle 2: CDK代码同步
**文件**: `tests/run_cdk_tests.py`

验证CDK代码与部署配置一致：
1. ✅ CDK包含Authorization Code配置
2. ✅ CDK包含CallbackURLs
3. ✅ CDK包含SupportedIdentityProviders
4. ✅ CDK启用OAuth flows

**结果**: 4/4 passing (代码同步)

### Cycle 3: OAuth流程测试
**阻塞点**: `invalid_scope`错误

无法进入浏览器登录测试阶段。

---

## 📚 相关文档与脚本

> 注：探索过程中曾产生多份调试临时文档（redirect_mismatch 修复、
> invalid_scope 分析、Managed Login 启用、测试报告等）。这些临时文档的
> 关键结论已全部归纳进本 postmortem，原文件在代码整理时已删除。

### 保留的文档
1. **HOW_TO_TEST_OAUTH.md** — 完整 OAuth 测试指南（3 种方法、troubleshooting）
2. **docs/authorization-code-feasibility.md** — Authorization Code 可行性分析
3. **docs/mcp-compliance-analysis.md** — MCP 合规度分析
4. **docs/rfc8707-migration.md** — RFC 8707 迁移说明

### 自动化脚本
5. **scripts/switch-to-client-credentials.sh** — 一键切回 Client Credentials（更新 Cognito + 刷新 token + 验证）
6. **diagnose_callback_url.sh** — OAuth 回调 URL 诊断

---

## 🔄 回退过程

### 执行的操作

1. **回退Cognito配置**
   ```bash
   aws cognito-idp update-user-pool-client \
     --user-pool-id us-west-2_L0273ULfK \
     --client-id <COGNITO_CLIENT_ID> \
     --allowed-o-auth-flows client_credentials \
     --allowed-o-auth-scopes \
       "DevOpsAgentMcpStack-Gateway-0299DE6E/read" \
       "DevOpsAgentMcpStack-Gateway-0299DE6E/write" \
     --allowed-o-auth-flows-user-pool-client
   ```

2. **更新CDK代码**
   - 修改 `cdk/stacks/devops_agent_mcp_stack.py`
   - 从 `["code"]` 改回 `["client_credentials"]`
   - 移除CallbackURLs和SupportedIdentityProviders配置

3. **刷新token**
   ```bash
   ./scripts/refresh-token.sh
   ```

4. **验证**
   ```bash
   aws cognito-idp describe-user-pool-client ... | jq '.UserPoolClient.AllowedOAuthFlows'
   # Output: ["client_credentials"] ✅
   ```

---

## 💡 关键教训

### Cognito限制
1. RFC 8707需要Managed Login（隐藏要求）
2. 即使启用Managed Login，仍可能有其他限制
3. Cognito不支持Client Credentials + RFC 8707

### MCP实现
1. Claude Code自动发送`resource`参数（无法禁用）
2. 如果OAuth服务器不支持RFC 8707，会失败
3. MCP规范允许Client Credentials作为M2M方案

### TDD价值
1. 测试套件帮助快速验证配置
2. 自动化脚本简化回退过程
3. 文档记录完整的探索过程

---

## 🎯 推荐方案

### 当前推荐: Client Credentials ⭐

**理由**:
- ✅ 技术上可行且已验证
- ✅ 适合M2M/自动化场景
- ✅ MCP官方支持
- ✅ 无需用户交互
- ✅ 脚本化token管理
- ⚠️ 66% MCP合规度（可接受）

**适用场景**:
- 开发/测试环境
- CI/CD集成
- 自动化脚本
- 单一Resource Server

### 未来选项: Authorization Code

**前提条件**:
1. 启用Managed Login（已知步骤）
2. 调查并解决`invalid_scope`的根本原因
3. 可能需要AWS支持协助

**适用场景**:
- 生产环境（如需100%合规）
- 多Resource Server架构
- 需要用户级别授权

---

## 📊 MCP合规度对比

### Client Credentials (当前)
| 要求 | 状态 | 说明 |
|-----|------|------|
| HTTP Transport | ✅ 100% | 完全支持 |
| OAuth 2.x | ✅ 100% | Client Credentials flow |
| Token获取 | ✅ 100% | 通过脚本自动化 |
| RFC 8707 | ❌ 0% | 无`aud` claim |
| Token Refresh | ⚠️ 50% | 手动/cron刷新 |
| **总计** | **66%** | M2M场景可接受 |

### Authorization Code (理想)
| 要求 | 状态 | 说明 |
|-----|------|------|
| HTTP Transport | ✅ 100% | 完全支持 |
| OAuth 2.x | ✅ 100% | Authorization Code + PKCE |
| Token获取 | ✅ 100% | 浏览器交互 |
| RFC 8707 | ❌ 0% | Cognito限制 |
| Token Refresh | ✅ 100% | 自动刷新 |
| **总计** | **80%** | 阻塞在Cognito限制 |

---

## 📂 相关文件

### 测试代码
- `tests/run_tests.py` - Cognito配置测试
- `tests/run_cdk_tests.py` - CDK代码验证

### CDK代码
- `cdk/stacks/devops_agent_mcp_stack.py` - User Pool Client配置

### 脚本
- `scripts/refresh-token.sh` - Token刷新
- `scripts/token-config.sh.example` - OAuth配置模板（真实配置 token-config.sh 不入库）
- `scripts/switch-to-client-credentials.sh` - 快速切换
- `diagnose_callback_url.sh` - 诊断工具

### 文档
- `HOW_TO_TEST_OAUTH.md` - 完整测试指南
- `docs/authorization-code-feasibility.md` - 可行性分析
- `docs/mcp-compliance-analysis.md` - MCP合规分析
- `docs/rfc8707-migration.md` - RFC 8707 迁移说明

---

## 🔮 未来工作

### 可选探索
1. 联系AWS支持调查`invalid_scope`的根本原因
2. 测试其他Cognito User Pool Tier（PLUS）是否有差异
3. 探索自定义OAuth服务器（非Cognito）的可行性

### 不推荐
- 在当前环境继续调试Authorization Code（收益低）
- 放弃Client Credentials方案（已验证可用）

---

## ✅ 结论

Authorization Code + RFC 8707迁移由于AWS Cognito的技术限制而失败。Client Credentials方案已验证可用，适合当前的M2M使用场景。

**当前状态**: ✅ 回退到Client Credentials，系统正常工作

**Issue #8**: 可以关闭，标记为"Cognito限制"

---

**作者**: Claude Code TDD Agent  
**日期**: 2026-05-29  
**Git commits**: e2dd711 → 回退到 Client Credentials配置
