#!/bin/bash
#
# 测试Authorization Code Flow + RFC 8707可行性
#

set -e

# 颜色
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}╔════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║  Authorization Code + RFC 8707 可行性测试             ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════╝${NC}"
echo ""

# 配置
USER_POOL_ID="us-west-2_L0273ULfK"
CLIENT_ID="<COGNITO_CLIENT_ID>"
DOMAIN="devopsagentmcpstack-gateway-0299de6e"
REGION="us-west-2"
GATEWAY_URL="https://devops-agent-mcp-elhze1stwj.gateway.bedrock-agentcore.us-west-2.amazonaws.com/mcp"
CALLBACK_URL="http://localhost:8080/callback"

echo -e "${YELLOW}[1/7]${NC} 检查Cognito User Pool状态..."
POOL_TIER=$(aws cognito-idp describe-user-pool \
  --user-pool-id $USER_POOL_ID \
  --region $REGION \
  --query 'UserPool.UserPoolTier' \
  --output text)

if [ "$POOL_TIER" == "ESSENTIALS" ] || [ "$POOL_TIER" == "PLUS" ]; then
  echo -e "  ${GREEN}✓${NC} User Pool Tier: $POOL_TIER (支持RFC 8707)"
else
  echo -e "  ${RED}✗${NC} User Pool Tier: $POOL_TIER (不支持RFC 8707)"
  echo "  需要: ESSENTIALS 或 PLUS"
  exit 1
fi
echo ""

echo -e "${YELLOW}[2/7]${NC} 检查Managed Login状态..."
MANAGED_LOGIN=$(aws cognito-idp describe-user-pool-domain \
  --domain $DOMAIN \
  --region $REGION \
  --query 'DomainDescription.ManagedLoginVersion' \
  --output text 2>/dev/null || echo "NOT_ENABLED")

if [ "$MANAGED_LOGIN" != "None" ] && [ "$MANAGED_LOGIN" != "NOT_ENABLED" ]; then
  echo -e "  ${GREEN}✓${NC} Managed Login Version: $MANAGED_LOGIN"
else
  echo -e "  ${YELLOW}⚠${NC} Managed Login未启用（但不是RFC 8707的必需条件）"
fi
echo ""

echo -e "${YELLOW}[3/7]${NC} 检查Cognito Domain状态..."
DOMAIN_STATUS=$(aws cognito-idp describe-user-pool-domain \
  --domain $DOMAIN \
  --region $REGION \
  --query 'DomainDescription.Status' \
  --output text)

if [ "$DOMAIN_STATUS" == "ACTIVE" ]; then
  echo -e "  ${GREEN}✓${NC} Domain状态: $DOMAIN_STATUS"
  echo "  ${GREEN}✓${NC} Hosted UI URL: https://$DOMAIN.auth.$REGION.amazoncognito.com"
else
  echo -e "  ${RED}✗${NC} Domain状态: $DOMAIN_STATUS"
  exit 1
fi
echo ""

echo -e "${YELLOW}[4/7]${NC} 检查是否有Cognito用户..."
USER_COUNT=$(aws cognito-idp list-users \
  --user-pool-id $USER_POOL_ID \
  --region $REGION \
  --query 'length(Users)' \
  --output text)

if [ "$USER_COUNT" -gt 0 ]; then
  echo -e "  ${GREEN}✓${NC} 已有 $USER_COUNT 个用户"
  aws cognito-idp list-users \
    --user-pool-id $USER_POOL_ID \
    --region $REGION \
    --query 'Users[*].[Username,UserStatus]' \
    --output text | while read username status; do
    echo "    - $username ($status)"
  done
else
  echo -e "  ${YELLOW}⚠${NC} 没有用户，需要创建"
  echo "  运行: aws cognito-idp admin-create-user --user-pool-id $USER_POOL_ID --username admin ..."
fi
echo ""

echo -e "${YELLOW}[5/7]${NC} 检查当前Client配置..."
CLIENT_INFO=$(aws cognito-idp describe-user-pool-client \
  --user-pool-id $USER_POOL_ID \
  --client-id $CLIENT_ID \
  --region $REGION \
  --query 'UserPoolClient.{Flows:AllowedOAuthFlows,Scopes:AllowedOAuthScopes,Callbacks:CallbackURLs}' \
  --output json)

CURRENT_FLOWS=$(echo "$CLIENT_INFO" | jq -r '.Flows[]' | tr '\n' ' ')
echo "  当前OAuth Flows: $CURRENT_FLOWS"

if echo "$CURRENT_FLOWS" | grep -q "authorization_code"; then
  echo -e "  ${GREEN}✓${NC} Authorization Code已启用"
else
  echo -e "  ${YELLOW}⚠${NC} Authorization Code未启用（当前: $CURRENT_FLOWS）"
  echo "  需要更新配置以启用authorization_code flow"
fi
echo ""

echo -e "${YELLOW}[6/7]${NC} 生成PKCE参数..."
CODE_VERIFIER=$(openssl rand -base64 32 | tr -d "=+/" | cut -c1-43)
CODE_CHALLENGE=$(echo -n "$CODE_VERIFIER" | openssl dgst -sha256 -binary | base64 | tr -d "=+/" | cut -c1-43)
STATE=$(openssl rand -hex 16)
echo -e "  ${GREEN}✓${NC} PKCE参数已生成"
echo ""

echo -e "${YELLOW}[7/7]${NC} 测试RFC 8707参数支持..."
RESOURCE_SERVER=$(aws cognito-idp list-resource-servers \
  --user-pool-id $USER_POOL_ID \
  --region $REGION \
  --query 'ResourceServers[0].Identifier' \
  --output text)

SCOPES=$(echo "$CLIENT_INFO" | jq -r '.Scopes[]' | tr '\n' ' ')
SCOPE_PARAM=$(echo "$SCOPES" | sed 's/ /%20/g')

# 构建Authorization URL（带RFC 8707 resource参数）
AUTH_URL="https://$DOMAIN.auth.$REGION.amazoncognito.com/oauth2/authorize"
AUTH_URL="${AUTH_URL}?response_type=code"
AUTH_URL="${AUTH_URL}&client_id=$CLIENT_ID"
AUTH_URL="${AUTH_URL}&redirect_uri=$CALLBACK_URL"
AUTH_URL="${AUTH_URL}&scope=$SCOPE_PARAM"
AUTH_URL="${AUTH_URL}&resource=$(echo $GATEWAY_URL | sed 's/:/%3A/g' | sed 's/\//%2F/g')"
AUTH_URL="${AUTH_URL}&state=$STATE"
AUTH_URL="${AUTH_URL}&code_challenge=$CODE_CHALLENGE"
AUTH_URL="${AUTH_URL}&code_challenge_method=S256"

echo -e "  ${GREEN}✓${NC} Authorization URL已生成（含RFC 8707 resource参数）"
echo ""

echo -e "${BLUE}╔════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║  可行性评估结果                                        ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════╝${NC}"
echo ""

# 评估结果
FEASIBLE=true
WARNINGS=()
BLOCKERS=()

# 检查阻塞因素
if [ "$POOL_TIER" != "ESSENTIALS" ] && [ "$POOL_TIER" != "PLUS" ]; then
  FEASIBLE=false
  BLOCKERS+=("User Pool Tier不支持RFC 8707")
fi

if [ "$DOMAIN_STATUS" != "ACTIVE" ]; then
  FEASIBLE=false
  BLOCKERS+=("Cognito Domain未激活")
fi

if [ "$USER_COUNT" -eq 0 ]; then
  WARNINGS+=("需要创建Cognito用户")
fi

if ! echo "$CURRENT_FLOWS" | grep -q "authorization_code"; then
  WARNINGS+=("需要更新Client配置启用authorization_code")
fi

# 输出结果
if [ "$FEASIBLE" = true ]; then
  echo -e "${GREEN}✅ Authorization Code + RFC 8707 方案 完全可行！${NC}"
  echo ""

  if [ ${#WARNINGS[@]} -gt 0 ]; then
    echo -e "${YELLOW}⚠️  需要完成以下准备工作:${NC}"
    for warning in "${WARNINGS[@]}"; do
      echo "  • $warning"
    done
    echo ""
  fi

  echo "下一步操作："
  echo ""
  echo "1. 更新Client配置启用Authorization Code:"
  echo "   ${BLUE}aws cognito-idp update-user-pool-client \\${NC}"
  echo "     ${BLUE}--user-pool-id $USER_POOL_ID \\${NC}"
  echo "     ${BLUE}--client-id $CLIENT_ID \\${NC}"
  echo "     ${BLUE}--allowed-o-auth-flows authorization_code \\${NC}"
  echo "     ${BLUE}--allowed-o-auth-scopes $SCOPES \\${NC}"
  echo "     ${BLUE}--callback-urls \"$CALLBACK_URL\" \\${NC}"
  echo "     ${BLUE}--supported-identity-providers COGNITO \\${NC}"
  echo "     ${BLUE}--allowed-o-auth-flows-user-pool-client \\${NC}"
  echo "     ${BLUE}--region $REGION${NC}"
  echo ""

  echo "2. 配置Claude Code使用Authorization Code:"
  echo "   ${BLUE}claude mcp remove devops-agent${NC}"
  echo "   ${BLUE}claude mcp add-json devops-agent '{${NC}"
  echo "     ${BLUE}\"type\": \"http\",${NC}"
  echo "     ${BLUE}\"url\": \"$GATEWAY_URL\",${NC}"
  echo "     ${BLUE}\"oauth\": {${NC}"
  echo "       ${BLUE}\"clientId\": \"$CLIENT_ID\",${NC}"
  echo "       ${BLUE}\"callbackPort\": 8080${NC}"
  echo "     ${BLUE}}${NC}"
  echo "   ${BLUE}}'${NC}"
  echo ""

  echo "3. 测试OAuth流程:"
  echo "   启动Claude Code，调用MCP工具时会自动触发OAuth登录"
  echo "   浏览器会打开: https://$DOMAIN.auth.$REGION.amazoncognito.com"
  echo "   登录后，Claude Code会自动获取包含aud claim的token"
  echo ""

  echo "测试Authorization URL（包含RFC 8707 resource参数）:"
  echo "${BLUE}$AUTH_URL${NC}"
  echo ""

else
  echo -e "${RED}❌ Authorization Code + RFC 8707 方案 不可行${NC}"
  echo ""
  echo -e "${RED}阻塞因素:${NC}"
  for blocker in "${BLOCKERS[@]}"; do
    echo "  • $blocker"
  done
  exit 1
fi
