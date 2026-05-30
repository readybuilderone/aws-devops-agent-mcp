#!/bin/bash
#
# DevOps Agent MCP - 一键设置脚本
# 用途: 交互式配置MCP服务器（headersHelper自动刷新token方案）
# 使用: ./setup.sh
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="${SCRIPT_DIR}/token-config.sh"
HEADERS_HELPER="${SCRIPT_DIR}/get-headers.sh"

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}"
cat << 'EOF'
╔═══════════════════════════════════════════╗
║   DevOps Agent MCP - 设置向导            ║
╚═══════════════════════════════════════════╝
EOF
echo -e "${NC}"

echo ""
echo "这个脚本会配置MCP服务器连接（token自动刷新，无需重启/cron）"
echo ""

# 检查前提条件
echo -e "${YELLOW}[1/6]${NC} 检查前提条件..."

for cmd in aws python3 claude curl; do
    if ! command -v "$cmd" &> /dev/null; then
        echo -e "${RED}✗ 未安装: $cmd${NC}"
        exit 1
    fi
done

echo -e "${GREEN}✓ 所有前提条件满足${NC}"
echo ""

# 获取Stack输出
echo -e "${YELLOW}[2/6]${NC} 获取CloudFormation Stack输出..."

STACK_NAME="DevOpsAgentMcpStack"
REGION="us-west-2"

if ! aws cloudformation describe-stacks --stack-name $STACK_NAME --region $REGION &> /dev/null; then
    echo -e "${RED}✗ Stack不存在: $STACK_NAME${NC}"
    echo "请先运行: cd cdk && cdk deploy"
    exit 1
fi

get_output() {
    aws cloudformation describe-stacks \
        --stack-name $STACK_NAME --region $REGION \
        --query "Stacks[0].Outputs[?OutputKey=='$1'].OutputValue" \
        --output text
}

GATEWAY_URL=$(get_output GatewayUrl)
CLIENT_ID=$(get_output ClientId)
TOKEN_ENDPOINT=$(get_output TokenEndpoint)

echo -e "${GREEN}✓ Stack输出获取成功${NC}"
echo "  Gateway URL: $GATEWAY_URL"
echo "  Client ID: $CLIENT_ID"
echo ""

# 获取User Pool ID、Client Secret与Scope
echo -e "${YELLOW}[3/6]${NC} 获取Cognito配置..."

# 直接从Stack资源拿User Pool（Gateway建的pool名字不含stack名，按名字过滤不可靠）
USER_POOL_ID=$(aws cloudformation describe-stack-resources \
    --stack-name $STACK_NAME \
    --region $REGION \
    --query "StackResources[?ResourceType=='AWS::Cognito::UserPool'].PhysicalResourceId | [0]" \
    --output text)

if [ -z "$USER_POOL_ID" ] || [ "$USER_POOL_ID" == "None" ]; then
    echo -e "${RED}✗ 在Stack资源中找不到User Pool${NC}"
    exit 1
fi

CLIENT_SECRET=$(aws cognito-idp describe-user-pool-client \
    --user-pool-id $USER_POOL_ID \
    --client-id $CLIENT_ID \
    --region $REGION \
    --query 'UserPoolClient.ClientSecret' \
    --output text)

# 动态发现resource server标识符，拼出scope（避免硬编码）
RESOURCE_SERVER=$(aws cognito-idp list-resource-servers \
    --user-pool-id $USER_POOL_ID \
    --max-results 10 \
    --region $REGION \
    --query "ResourceServers[?contains(Identifier, 'Gateway')].Identifier | [0]" \
    --output text)

if [ -z "$RESOURCE_SERVER" ] || [ "$RESOURCE_SERVER" == "None" ]; then
    echo -e "${YELLOW}⚠ 无法自动发现resource server，使用默认scope格式${NC}"
    RESOURCE_SERVER="DevOpsAgentMcpStack-Gateway"
fi

SCOPE="${RESOURCE_SERVER}/read ${RESOURCE_SERVER}/write"

echo -e "${GREEN}✓ Cognito配置获取成功${NC}"
echo "  User Pool ID: $USER_POOL_ID"
echo "  Scope: $SCOPE"
echo ""

# 配置OAuth流程
echo -e "${YELLOW}[4/6]${NC} 配置OAuth Client Credentials流程..."

aws cognito-idp update-user-pool-client \
    --user-pool-id $USER_POOL_ID \
    --client-id $CLIENT_ID \
    --allowed-o-auth-flows client_credentials \
    --allowed-o-auth-scopes "${RESOURCE_SERVER}/read" "${RESOURCE_SERVER}/write" \
    --allowed-o-auth-flows-user-pool-client \
    --region $REGION \
    --output text > /dev/null

echo -e "${GREEN}✓ OAuth配置完成${NC}"
echo ""

# 保存token配置（供get-headers.sh使用）
echo -e "${YELLOW}[5/6]${NC} 保存凭证配置..."

cat > "$CONFIG_FILE" << EOF
#!/bin/bash
#
# DevOps Agent MCP - Token配置文件
# 由setup.sh自动生成
#

CLIENT_ID="$CLIENT_ID"
CLIENT_SECRET="$CLIENT_SECRET"
TOKEN_ENDPOINT="$TOKEN_ENDPOINT"
SCOPE="$SCOPE"
EOF

chmod 600 "$CONFIG_FILE"
chmod +x "$HEADERS_HELPER"
echo -e "${GREEN}✓ 凭证已保存到: $CONFIG_FILE (权限600)${NC}"

# 先验证一次token能成功获取
echo "  验证token获取..."
if "$HEADERS_HELPER" > /dev/null 2>/tmp/get-headers-check.log; then
    echo -e "${GREEN}✓ Token获取成功${NC}"
else
    echo -e "${RED}✗ Token获取失败:${NC}"
    cat /tmp/get-headers-check.log
    rm -f /tmp/get-headers-check.log
    exit 1
fi
rm -f /tmp/get-headers-check.log
echo ""

# 配置Claude Code MCP服务器（headersHelper指向绝对路径）
echo -e "${YELLOW}[6/6]${NC} 配置Claude Code MCP服务器..."

# 已存在旧条目（可能是旧的oauth/clientId方式或旧URL）时先移除，
# 否则 add-json 不会覆盖，连接会沿用旧配置而失败。
if claude mcp get devops-agent &> /dev/null; then
    echo "检测到已有 devops-agent 配置，移除后用 headersHelper 重新注册..."
    claude mcp remove devops-agent -s local &> /dev/null || true
fi

claude mcp add-json devops-agent "{
  \"type\": \"http\",
  \"url\": \"$GATEWAY_URL\",
  \"headersHelper\": \"$HEADERS_HELPER\"
}" || true
echo -e "${GREEN}✓ MCP服务器已注册${NC}"
echo ""

echo -e "${GREEN}╔═══════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║   ✅ 设置完成！                          ║${NC}"
echo -e "${GREEN}╚═══════════════════════════════════════════╝${NC}"
echo ""
echo "下一步:"
echo "  1. 在Claude Code中运行 /mcp 查看连接状态（应为 ✓ Connected）"
echo "  2. 测试: 请调用devops_echo工具，消息是\"Hello!\""
echo ""
echo "💡 token由 get-headers.sh 在每次连接时自动获取并缓存，过期会自动刷新。"
echo "   无需手动刷新、无需cron、无需重启Claude Code。"
echo ""
