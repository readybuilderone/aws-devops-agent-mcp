#!/bin/bash
#
# DevOps Agent MCP - Token刷新脚本
# 用途: 自动获取新的access token并注入到Claude Code
# 使用: ./refresh-token.sh [--config CONFIG_FILE]
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="${SCRIPT_DIR}/token-config.sh"

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 日志函数
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 解析命令行参数
while [[ $# -gt 0 ]]; do
    case $1 in
        --config)
            CONFIG_FILE="$2"
            shift 2
            ;;
        -h|--help)
            echo "用法: $0 [--config CONFIG_FILE]"
            echo ""
            echo "选项:"
            echo "  --config FILE    指定配置文件路径 (默认: token-config.sh)"
            echo "  -h, --help       显示帮助信息"
            exit 0
            ;;
        *)
            log_error "未知选项: $1"
            exit 1
            ;;
    esac
done

# 检查配置文件
if [ ! -f "$CONFIG_FILE" ]; then
    log_error "配置文件不存在: $CONFIG_FILE"
    log_info "请先创建配置文件，示例："
    echo ""
    cat << 'EOF'
# token-config.sh
CLIENT_ID="your-client-id"
CLIENT_SECRET="your-client-secret"
TOKEN_ENDPOINT="https://xxxxx.auth.us-west-2.amazoncognito.com/oauth2/token"
HASH_KEY="devops-agent|xxxxx"
SCOPE="DevOpsAgentMcpStack-Gateway-0299DE6E/read DevOpsAgentMcpStack-Gateway-0299DE6E/write"
EOF
    exit 1
fi

# 加载配置
log_info "加载配置: $CONFIG_FILE"
source "$CONFIG_FILE"

# 验证必需变量
REQUIRED_VARS=("CLIENT_ID" "CLIENT_SECRET" "TOKEN_ENDPOINT" "HASH_KEY" "SCOPE")
for var in "${REQUIRED_VARS[@]}"; do
    if [ -z "${!var}" ]; then
        log_error "配置文件缺少必需变量: $var"
        exit 1
    fi
done

# 获取token
log_info "正在获取access token..."

RESPONSE=$(curl -s -X POST "$TOKEN_ENDPOINT" \
    -H "Content-Type: application/x-www-form-urlencoded" \
    -u "$CLIENT_ID:$CLIENT_SECRET" \
    -d "grant_type=client_credentials&scope=$(echo $SCOPE | sed 's/ /%20/g')" \
    2>&1)

# 检查curl是否成功
if [ $? -ne 0 ]; then
    log_error "Token请求失败"
    echo "$RESPONSE"
    exit 1
fi

# 解析token
ACCESS_TOKEN=$(echo "$RESPONSE" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    if 'access_token' in data:
        print(data['access_token'])
    elif 'error' in data:
        print(f\"ERROR: {data.get('error_description', data['error'])}\", file=sys.stderr)
        sys.exit(1)
    else:
        print('ERROR: 未知的响应格式', file=sys.stderr)
        sys.exit(1)
except Exception as e:
    print(f'ERROR: 解析失败 - {e}', file=sys.stderr)
    sys.exit(1)
" 2>&1)

if [ $? -ne 0 ] || [ -z "$ACCESS_TOKEN" ]; then
    log_error "Token解析失败"
    echo "$ACCESS_TOKEN"
    exit 1
fi

TOKEN_LENGTH=${#ACCESS_TOKEN}
log_info "Token获取成功 (长度: ${TOKEN_LENGTH})"

# 注入token
log_info "正在注入token到Claude Code..."

CREDENTIALS_FILE="$HOME/.claude/.credentials.json"

if [ ! -f "$CREDENTIALS_FILE" ]; then
    log_error "Claude Code credentials文件不存在: $CREDENTIALS_FILE"
    log_warn "请先运行Claude Code并配置MCP服务器"
    exit 1
fi

# 备份credentials文件
BACKUP_FILE="${CREDENTIALS_FILE}.backup.$(date +%Y%m%d_%H%M%S)"
cp "$CREDENTIALS_FILE" "$BACKUP_FILE"
log_info "已备份credentials到: $BACKUP_FILE"

# 注入token
python3 << PYEOF
import json
import sys

try:
    with open('$CREDENTIALS_FILE', 'r') as f:
        creds = json.load(f)

    if 'mcpOAuth' not in creds:
        print('ERROR: credentials文件中没有mcpOAuth字段', file=sys.stderr)
        sys.exit(1)

    if '$HASH_KEY' not in creds['mcpOAuth']:
        print(f'ERROR: 找不到key: $HASH_KEY', file=sys.stderr)
        print(f'可用的keys: {list(creds["mcpOAuth"].keys())}', file=sys.stderr)
        sys.exit(1)

    # 注入token
    creds['mcpOAuth']['$HASH_KEY']['accessToken'] = '$ACCESS_TOKEN'

    # 保存
    with open('$CREDENTIALS_FILE', 'w') as f:
        json.dump(creds, f, indent=2)

    print('SUCCESS')
except Exception as e:
    print(f'ERROR: {e}', file=sys.stderr)
    sys.exit(1)
PYEOF

if [ $? -eq 0 ]; then
    log_info "✅ Token注入成功！"
    log_warn "📝 请重启Claude Code以生效"

    # 清理旧备份（保留最近5个）
    ls -t "${CREDENTIALS_FILE}.backup."* 2>/dev/null | tail -n +6 | xargs -r rm
    log_info "已清理旧备份文件"
else
    log_error "Token注入失败，正在恢复备份..."
    cp "$BACKUP_FILE" "$CREDENTIALS_FILE"
    exit 1
fi

echo ""
log_info "完成！下次token将在1小时后过期"
log_info "建议设置cron任务自动刷新: */50 * * * * $0"
