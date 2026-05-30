#!/bin/bash
#
# DevOps Agent MCP - headersHelper 脚本
#
# 用途: 在每次MCP连接时被Claude Code调用，输出包含有效access token的
#       HTTP header（JSON格式）。token过期会自动重新获取，无需重启
#       Claude Code、无需cron、无需写入 ~/.claude/.credentials.json。
#
# 配置方式（.mcp.json）:
#   {
#     "mcpServers": {
#       "devops-agent": {
#         "type": "http",
#         "url": "<GATEWAY_URL>",
#         "headersHelper": "${CLAUDE_PLUGIN_ROOT}/scripts/get-headers.sh"
#       }
#     }
#   }
#
# 凭证来自同目录的 token-config.sh（git-ignored，含CLIENT_SECRET）。
#
# 输出: stdout 仅输出一行 JSON，形如 {"Authorization": "Bearer xxx"}
#       任何诊断信息都写到 stderr，避免污染 header 输出。
#
# 注意: Claude Code 对 headersHelper 有 10 秒超时；Cognito token 请求通常 <1s。
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="${TOKEN_CONFIG_FILE:-${SCRIPT_DIR}/token-config.sh}"

# 所有日志走 stderr，stdout 只留给最终的 JSON
log() { echo "[get-headers] $*" >&2; }

if [ ! -f "$CONFIG_FILE" ]; then
    log "错误: 找不到配置文件 $CONFIG_FILE"
    log "请复制 token-config.sh.example 为 token-config.sh 并填入凭证"
    exit 1
fi

# shellcheck source=/dev/null
source "$CONFIG_FILE"

for var in CLIENT_ID CLIENT_SECRET TOKEN_ENDPOINT SCOPE; do
    if [ -z "${!var:-}" ]; then
        log "错误: 配置缺少必需变量 $var"
        exit 1
    fi
done

# --- token 缓存 -----------------------------------------------------------
# Cognito access token 有效期1小时。为避免每次连接都打一次token端点，
# 把token缓存到文件，并在到期前(留5分钟余量)复用。
CACHE_FILE="${TOKEN_CACHE_FILE:-${TMPDIR:-/tmp}/devops-agent-mcp-token.cache}"
CACHE_SKEW=300  # 提前5分钟视为过期

now=$(date +%s)

if [ -f "$CACHE_FILE" ]; then
    # 缓存格式: 第一行=过期时间戳(epoch秒)，第二行=access token
    cached_exp=$(sed -n '1p' "$CACHE_FILE" 2>/dev/null || echo 0)
    cached_token=$(sed -n '2p' "$CACHE_FILE" 2>/dev/null || echo "")
    if [ -n "$cached_token" ] && [ "$cached_exp" -gt "$((now + CACHE_SKEW))" ] 2>/dev/null; then
        log "复用缓存token (剩余 $((cached_exp - now))s)"
        printf '{"Authorization": "Bearer %s"}\n' "$cached_token"
        exit 0
    fi
fi

# --- 获取新token ----------------------------------------------------------
log "正在向Cognito获取新access token..."

# scope中的空格需URL编码为 %20
ENCODED_SCOPE="${SCOPE// /%20}"

RESPONSE=$(curl -sS -X POST "$TOKEN_ENDPOINT" \
    -H "Content-Type: application/x-www-form-urlencoded" \
    -u "$CLIENT_ID:$CLIENT_SECRET" \
    -d "grant_type=client_credentials&scope=${ENCODED_SCOPE}")

# 用python解析，同时拿到token和expires_in
PARSED=$(echo "$RESPONSE" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
except Exception as e:
    print('ERR parse: %s' % e, file=sys.stderr); sys.exit(1)
if 'access_token' in d:
    print(d['access_token'])
    print(d.get('expires_in', 3600))
else:
    print('ERR %s' % d.get('error_description', d.get('error', 'unknown')), file=sys.stderr)
    sys.exit(1)
") || { log "token获取失败: $(echo "$RESPONSE" | head -c 400)"; exit 1; }

ACCESS_TOKEN=$(echo "$PARSED" | sed -n '1p')
EXPIRES_IN=$(echo "$PARSED" | sed -n '2p')

if [ -z "$ACCESS_TOKEN" ]; then
    log "错误: 解析出的token为空"
    exit 1
fi

# 写缓存(原子写 + 限制权限)
exp_ts=$((now + EXPIRES_IN))
umask 077
printf '%s\n%s\n' "$exp_ts" "$ACCESS_TOKEN" > "${CACHE_FILE}.tmp.$$"
mv -f "${CACHE_FILE}.tmp.$$" "$CACHE_FILE"

log "token获取成功 (有效期 ${EXPIRES_IN}s, 长度 ${#ACCESS_TOKEN})"
printf '{"Authorization": "Bearer %s"}\n' "$ACCESS_TOKEN"
