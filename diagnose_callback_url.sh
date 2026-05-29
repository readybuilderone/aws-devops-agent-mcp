#!/bin/bash
# 诊断Claude Code使用的实际回调URL

echo "==================================================================="
echo "OAuth Redirect Mismatch 诊断"
echo "==================================================================="
echo ""

# 从错误URL提取的信息
echo "错误信息:"
echo "  Error: redirect_mismatch"
echo "  Client ID: <COGNITO_CLIENT_ID>"
echo ""

# 检查Cognito配置的回调URLs
echo "Cognito配置的回调URLs:"
aws cognito-idp describe-user-pool-client \
  --user-pool-id us-west-2_L0273ULfK \
  --client-id <COGNITO_CLIENT_ID> \
  --region us-west-2 \
  --query 'UserPoolClient.CallbackURLs' \
  --output json | jq -r '.[]' | while read url; do
    echo "  ✓ $url"
done
echo ""

# 检查MCP配置
echo "Claude Code MCP配置:"
cat ~/.claude/.credentials.json | python3 -c "
import json, sys
data = json.load(sys.stdin)
oauth = data.get('mcpOAuth', {})
for key, value in oauth.items():
    if 'devops-agent' in key:
        print(f'  Server: {value.get(\"serverName\")}')
        print(f'  URL: {value.get(\"serverUrl\")}')
        discovery = value.get('discoveryState', {})
        print(f'  Auth Server: {discovery.get(\"authorizationServerUrl\")}')
" 2>/dev/null
echo ""

# 可能的原因
echo "==================================================================="
echo "可能的原因:"
echo "==================================================================="
echo ""
echo "1. Claude Code可能使用了不同的端口或路径"
echo "2. OAuth请求中的redirect_uri参数与Cognito配置不匹配"
echo "3. Claude Code可能使用了URL编码的回调URL"
echo ""

echo "==================================================================="
echo "建议的修复方法:"
echo "==================================================================="
echo ""

echo "方法1: 检查Claude Code使用的实际回调URL"
echo ""
echo "在浏览器中，查看OAuth授权URL的完整内容。"
echo "URL应该包含 redirect_uri=... 参数"
echo ""
echo "请复制完整的OAuth URL（在浏览器地址栏），然后运行："
echo "  echo 'YOUR_FULL_URL' | grep -o 'redirect_uri=[^&]*'"
echo ""

echo "方法2: 添加常见的回调URL变体"
echo ""
echo "运行以下命令添加更多回调URL选项："
echo ""
cat << 'EOFCMD'
aws cognito-idp update-user-pool-client \
  --user-pool-id us-west-2_L0273ULfK \
  --client-id <COGNITO_CLIENT_ID> \
  --allowed-o-auth-flows code \
  --allowed-o-auth-scopes \
    "DevOpsAgentMcpStack-Gateway-0299DE6E/read" \
    "DevOpsAgentMcpStack-Gateway-0299DE6E/write" \
  --callback-urls \
    "http://localhost:8080/callback" \
    "http://127.0.0.1:8080/callback" \
    "http://localhost:8080/" \
    "http://127.0.0.1:8080/" \
    "http://localhost:8080/oauth/callback" \
    "http://127.0.0.1:8080/oauth/callback" \
  --supported-identity-providers COGNITO \
  --allowed-o-auth-flows-user-pool-client \
  --region us-west-2
EOFCMD
echo ""

echo "方法3: 重新配置Claude Code MCP (使用不同的回调端口)"
echo ""
echo "如果以上方法都不行，尝试使用不同的端口："
echo ""
echo "claude mcp remove devops-agent"
echo "claude mcp add-json devops-agent '{"
echo '  "type": "http",'
echo '  "url": "https://devops-agent-mcp-elhze1stwj.gateway.bedrock-agentcore.us-west-2.amazonaws.com/mcp",'
echo '  "oauth": {'
echo '    "clientId": "<COGNITO_CLIENT_ID>",'
echo '    "callbackPort": 3000'
echo "  }"
echo "}'"
echo ""
echo "然后更新Cognito:"
echo "aws cognito-idp update-user-pool-client \\"
echo "  --user-pool-id us-west-2_L0273ULfK \\"
echo "  --client-id <COGNITO_CLIENT_ID> \\"
echo "  --callback-urls \\"
echo '    "http://localhost:3000/callback" \\'
echo '    "http://127.0.0.1:3000/callback" \\'
echo "  --region us-west-2"
echo ""

echo "==================================================================="
echo "下一步:"
echo "==================================================================="
echo ""
echo "1. 提供完整的OAuth URL（浏览器地址栏中的）"
echo "2. 我会帮你找出实际使用的redirect_uri"
echo "3. 然后更新Cognito配置以匹配"
echo ""
