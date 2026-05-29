#!/bin/bash
#
# DevOps Agent MCP - 一键设置脚本
# 用途: 交互式配置MCP服务器
# 使用: ./setup.sh
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="${SCRIPT_DIR}/token-config.sh"

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
echo "这个脚本将帮助你配置MCP服务器连接"
echo ""

# 检查前提条件
echo -e "${YELLOW}[1/7]${NC} 检查前提条件..."

if ! command -v aws &> /dev/null; then
    echo -e "${RED}✗ AWS CLI未安装${NC}"
    exit 1
fi

if ! command -v python3 &> /dev/null; then
    echo -e "${RED}✗ Python3未安装${NC}"
    exit 1
fi

if ! command -v claude &> /dev/null; then
    echo -e "${RED}✗ Claude Code未安装${NC}"
    exit 1
fi

echo -e "${GREEN}✓ 所有前提条件满足${NC}"
echo ""

# 获取Stack输出
echo -e "${YELLOW}[2/7]${NC} 获取CloudFormation Stack输出..."

STACK_NAME="DevOpsAgentMcpStack"
REGION="us-west-2"

if ! aws cloudformation describe-stacks --stack-name $STACK_NAME --region $REGION &> /dev/null; then
    echo -e "${RED}✗ Stack不存在: $STACK_NAME${NC}"
    echo "请先运行: cd cdk && cdk deploy"
    exit 1
fi

GATEWAY_URL=$(aws cloudformation describe-stacks \
    --stack-name $STACK_NAME \
    --region $REGION \
    --query 'Stacks[0].Outputs[?OutputKey==`GatewayUrl`].OutputValue' \
    --output text)

CLIENT_ID=$(aws cloudformation describe-stacks \
    --stack-name $STACK_NAME \
    --region $REGION \
    --query 'Stacks[0].Outputs[?OutputKey==`ClientId`].OutputValue' \
    --output text)

TOKEN_ENDPOINT=$(aws cloudformation describe-stacks \
    --stack-name $STACK_NAME \
    --region $REGION \
    --query 'Stacks[0].Outputs[?OutputKey==`TokenEndpoint`].OutputValue' \
    --output text)

echo -e "${GREEN}✓ Stack输出获取成功${NC}"
echo "  Gateway URL: $GATEWAY_URL"
echo "  Client ID: $CLIENT_ID"
echo ""

# 获取User Pool ID和Client Secret
echo -e "${YELLOW}[3/7]${NC} 获取Cognito配置..."

USER_POOL_ID=$(aws cognito-idp list-user-pools \
    --max-results 10 \
    --region $REGION \
    --query "UserPools[?contains(Name, 'DevOpsAgentMcpStack')].Id" \
    --output text)

if [ -z "$USER_POOL_ID" ]; then
    echo -e "${RED}✗ 找不到User Pool${NC}"
    exit 1
fi

CLIENT_SECRET=$(aws cognito-idp describe-user-pool-client \
    --user-pool-id $USER_POOL_ID \
    --client-id $CLIENT_ID \
    --region $REGION \
    --query 'UserPoolClient.ClientSecret' \
    --output text)

echo -e "${GREEN}✓ Cognito配置获取成功${NC}"
echo "  User Pool ID: $USER_POOL_ID"
echo ""

# 配置OAuth流程
echo -e "${YELLOW}[4/7]${NC} 配置OAuth Client Credentials流程..."

aws cognito-idp update-user-pool-client \
    --user-pool-id $USER_POOL_ID \
    --client-id $CLIENT_ID \
    --allowed-o-auth-flows client_credentials \
    --allowed-o-auth-scopes \
        "DevOpsAgentMcpStack-Gateway-0299DE6E/read" \
        "DevOpsAgentMcpStack-Gateway-0299DE6E/write" \
    --allowed-o-auth-flows-user-pool-client \
    --region $REGION \
    --output text > /dev/null

echo -e "${GREEN}✓ OAuth配置完成${NC}"
echo ""

# 添加MCP服务器到Claude Code
echo -e "${YELLOW}[5/7]${NC} 配置Claude Code MCP服务器..."

MCP_CONFIG=$(cat <<EOF
{
  "type": "http",
  "url": "$GATEWAY_URL",
  "oauth": {
    "clientId": "$CLIENT_ID"
  }
}
EOF
)

# 检查是否已存在
if claude mcp list 2>&1 | grep -q "devops-agent"; then
    echo "MCP服务器已存在，跳过添加"
else
    echo "$MCP_CONFIG" | claude mcp add-json devops-agent - || true
    echo -e "${GREEN}✓ MCP服务器已添加${NC}"
fi
echo ""

# 获取Hash Key
echo -e "${YELLOW}[6/7]${NC} 查找MCP配置Hash Key..."

CREDENTIALS_FILE="$HOME/.claude/.credentials.json"

if [ ! -f "$CREDENTIALS_FILE" ]; then
    echo -e "${RED}✗ Claude Code credentials文件不存在${NC}"
    echo "请先启动Claude Code一次"
    exit 1
fi

HASH_KEY=$(cat "$CREDENTIALS_FILE" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    keys = [k for k in data.get('mcpOAuth', {}).keys() if k.startswith('devops-agent|')]
    if keys:
        print(keys[0])
    else:
        print('NOT_FOUND')
except:
    print('ERROR')
")

if [ "$HASH_KEY" == "NOT_FOUND" ] || [ "$HASH_KEY" == "ERROR" ]; then
    echo -e "${YELLOW}⚠ 无法自动找到Hash Key${NC}"
    echo "请手动运行: cat ~/.claude/.credentials.json | grep devops-agent"
    read -p "请输入完整的Hash Key (devops-agent|xxxxx): " HASH_KEY
fi

echo -e "${GREEN}✓ Hash Key: $HASH_KEY${NC}"
echo ""

# 保存配置
echo -e "${YELLOW}[7/7]${NC} 保存配置..."

cat > "$CONFIG_FILE" << EOF
#!/bin/bash
#
# DevOps Agent MCP - Token配置文件
# 由setup.sh自动生成于 $(date)
#

CLIENT_ID="$CLIENT_ID"
CLIENT_SECRET="$CLIENT_SECRET"
TOKEN_ENDPOINT="$TOKEN_ENDPOINT"
HASH_KEY="$HASH_KEY"
SCOPE="DevOpsAgentMcpStack-Gateway-0299DE6E/read DevOpsAgentMcpStack-Gateway-0299DE6E/write"
EOF

chmod 600 "$CONFIG_FILE"
echo -e "${GREEN}✓ 配置已保存到: $CONFIG_FILE${NC}"
echo ""

# 获取并注入token
echo "正在获取并注入access token..."
"${SCRIPT_DIR}/refresh-token.sh" --config "$CONFIG_FILE"

echo ""
echo -e "${GREEN}╔═══════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║   ✅ 设置完成！                          ║${NC}"
echo -e "${GREEN}╚═══════════════════════════════════════════╝${NC}"
echo ""
echo "下一步:"
echo "  1. 重启Claude Code (exit 然后 claude)"
echo "  2. 运行 /reload-plugins"
echo "  3. 测试: 请调用devops_echo工具，消息是\"Hello!\""
echo ""
echo "Token将在1小时后过期，届时运行:"
echo "  ${SCRIPT_DIR}/refresh-token.sh"
echo ""
echo "或设置自动刷新 (每50分钟):"
echo "  (crontab -l; echo \"*/50 * * * * ${SCRIPT_DIR}/refresh-token.sh\") | crontab -"
echo ""
