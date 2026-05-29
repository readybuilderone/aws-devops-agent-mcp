#!/bin/bash
# MCP Proxy wrapper for DevOps Agent MCP Gateway
# This script proxies stdio MCP protocol to the remote HTTP gateway

GATEWAY_URL="https://devops-agent-mcp-elhze1stwj.gateway.bedrock-agentcore.us-west-2.amazonaws.com/mcp"
CLIENT_ID="<COGNITO_CLIENT_ID>"

echo "MCP Proxy for DevOps Agent - OAuth authentication required" >&2
echo "Gateway: $GATEWAY_URL" >&2
echo "This feature requires Claude Code to support remote MCP with OAuth" >&2
exit 1
