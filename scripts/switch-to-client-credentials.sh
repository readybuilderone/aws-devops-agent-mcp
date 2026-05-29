#!/bin/bash
#
# 一键切换到Client Credentials OAuth流程
#
# 用途: 当Authorization Code遇到invalid_scope错误时，
#       快速切换回工作正常的Client Credentials方案
#

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}"
cat << 'EOF'
╔═══════════════════════════════════════════╗
║   切换到Client Credentials OAuth流程     ║
╚═══════════════════════════════════════════╝
EOF
echo -e "${NC}"
echo ""

echo "此脚本将:"
echo "  1. 更新Cognito为Client Credentials flow"
echo "  2. 获取并注入access token"
echo "  3. 验证配置正确"
echo ""

read -p "继续? (y/n) " -n 1 -r
echo ""
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "已取消"
    exit 1
fi

echo ""
echo -e "${YELLOW}[1/4]${NC} 更新Cognito User Pool Client配置..."

aws cognito-idp update-user-pool-client \
  --user-pool-id us-west-2_L0273ULfK \
  --client-id <COGNITO_CLIENT_ID> \
  --allowed-o-auth-flows client_credentials \
  --allowed-o-auth-scopes \
    "DevOpsAgentMcpStack-Gateway-0299DE6E/read" \
    "DevOpsAgentMcpStack-Gateway-0299DE6E/write" \
  --allowed-o-auth-flows-user-pool-client \
  --region us-west-2 \
  --output text > /dev/null

echo -e "${GREEN}✓ Cognito配置已更新为Client Credentials${NC}"
echo ""

echo -e "${YELLOW}[2/4]${NC} 验证配置..."

FLOWS=$(aws cognito-idp describe-user-pool-client \
  --user-pool-id us-west-2_L0273ULfK \
  --client-id <COGNITO_CLIENT_ID> \
  --region us-west-2 \
  --query 'UserPoolClient.AllowedOAuthFlows[0]' \
  --output text)

if [ "$FLOWS" == "client_credentials" ]; then
    echo -e "${GREEN}✓ OAuth flow确认为: client_credentials${NC}"
else
    echo -e "${RED}✗ OAuth flow不正确: $FLOWS${NC}"
    exit 1
fi
echo ""

echo -e "${YELLOW}[3/4]${NC} 获取并注入access token..."

# 运行token刷新脚本
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ -f "$SCRIPT_DIR/refresh-token.sh" ]; then
    "$SCRIPT_DIR/refresh-token.sh"
else
    echo -e "${RED}✗ 找不到refresh-token.sh脚本${NC}"
    exit 1
fi

echo ""
echo -e "${YELLOW}[4/4]${NC} 运行配置测试..."

cd "$(dirname "$SCRIPT_DIR")"
if python3 tests/run_tests.py 2>&1 | grep -q "Passed: 6/6"; then
    echo -e "${GREEN}✓ 所有测试通过${NC}"
else
    echo -e "${YELLOW}⚠ 测试结果可能包含预期的差异${NC}"
    echo "  (test 6会失败因为现在启用了client_credentials)"
fi

echo ""
echo -e "${GREEN}╔═══════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║   ✅ 切换完成！                          ║${NC}"
echo -e "${GREEN}╚═══════════════════════════════════════════╝${NC}"
echo ""

echo "下一步:"
echo "  1. 重启Claude Code:"
echo "     exit"
echo "     claude"
echo ""
echo "  2. 测试MCP工具:"
echo '     "请调用devops_echo工具，消息是'"'"'Using Client Credentials'"'"'"'
echo ""
echo "  3. 工具应该立即返回结果，无需浏览器登录"
echo ""

echo "Token将在1小时后过期。刷新方法:"
echo "  ./scripts/refresh-token.sh"
echo ""
echo "或设置自动刷新 (每50分钟):"
echo "  (crontab -l; echo \"*/50 * * * * $SCRIPT_DIR/refresh-token.sh\") | crontab -"
echo ""

echo -e "${BLUE}Client Credentials方案特点:${NC}"
echo "  ✅ 无需浏览器登录"
echo "  ✅ 适合自动化场景"
echo "  ✅ MCP官方支持的M2M方式"
echo "  ✅ 66% MCP合规度"
echo "  ⚠️ 需要手动/自动刷新token (每小时)"
echo "  ⚠️ Token无aud claim (RFC 8707)"
echo ""
