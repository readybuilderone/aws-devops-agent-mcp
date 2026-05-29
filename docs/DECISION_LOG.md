# 技术决策日志

## 2026-05-29: Authorization Code vs Client Credentials认证方案

### 背景

项目当前使用Client Credentials (M2M) OAuth流程，MCP合规度66%。AWS Cognito于2025年10月已支持RFC 8707，但仅限Authorization Code流程，不支持Client Credentials场景。

### 决策问题

是否应该从Client Credentials迁移到Authorization Code + RFC 8707？

### 分析

**当前方案（Client Credentials）**:
- ✅ 无需用户交互，适合自动化
- ✅ Client Credentials是MCP官方支持的M2M方式
- ❌ 不支持RFC 8707（Cognito限制）
- ❌ Token缺少aud claim
- ❌ 需要手动token刷新脚本
- MCP合规度: 66%

**备选方案（Authorization Code + RFC 8707）**:
- ✅ 100% MCP合规
- ✅ 完整RFC 8707支持（token audience binding）
- ✅ 自动token管理（refresh token）
- ✅ 更高安全性
- ⚠️ 需要首次用户登录
- MCP合规度: 100%

**可行性验证**:
- ✅ Cognito User Pool: ESSENTIALS tier（支持RFC 8707）
- ✅ Managed Login: Version 1已启用
- ✅ Cognito Domain: ACTIVE
- ✅ Cognito用户: admin已创建
- ✅ 所有前提条件满足

**成本影响**: 零（Essentials已包含所需功能）

**工作量**: 38分钟（2个命令更新配置 + 文档更新）

**风险**: 极低（可2分钟内回退）

### 决策

**创建Issue #8追踪迁移任务，推荐迁移到Authorization Code方案。**

**理由**:
1. 所有技术前提条件已满足
2. 操作简单（<40分钟），零额外成本
3. 显著提升MCP合规度（66% → 100%）
4. 更好的安全性（RFC 8707 token binding）
5. 更好的用户体验（自动token管理）
6. 风险极低（可随时回退）

**保留Client Credentials作为备选**（适用于CI/CD场景）。

### 相关文档

- Issue #8: 迁移到Authorization Code + RFC 8707以实现100% MCP合规
- `docs/authorization-code-feasibility.md`: 详细可行性分析
- `docs/rfc8707-migration.md`: 完整迁移指南
- `docs/mcp-compliance-analysis.md`: MCP协议符合度评估

### 状态

- [x] 决策已做出
- [x] Issue已创建
- [ ] 等待实施

---

## 架构决策记录模板

每个重要技术决策应包含：
- **日期**: 决策时间
- **背景**: 为什么需要做这个决策
- **决策问题**: 具体要解决什么
- **分析**: 各方案对比
- **决策**: 最终选择及理由
- **相关文档**: 参考资料
- **状态**: 当前进度
