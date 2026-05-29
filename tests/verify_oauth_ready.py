#!/usr/bin/env python3
"""
Verify OAuth Authorization Code readiness.

This script verifies that everything is configured correctly for
Authorization Code flow, without requiring actual browser interaction.
"""

import json
import sys
import requests
import boto3

print("=" * 70)
print("OAuth Authorization Code Readiness Check")
print("=" * 70)
print()

# Configuration
config = {
    'region': 'us-west-2',
    'user_pool_id': 'us-west-2_L0273ULfK',
    'client_id': '<COGNITO_CLIENT_ID>',
    'gateway_url': 'https://devops-agent-mcp-elhze1stwj.gateway.bedrock-agentcore.us-west-2.amazonaws.com/mcp',
    'auth_endpoint': 'https://devopsagentmcpstack-gateway-0299de6e.auth.us-west-2.amazoncognito.com/oauth2/authorize',
    'token_endpoint': 'https://devopsagentmcpstack-gateway-0299de6e.auth.us-west-2.amazoncognito.com/oauth2/token',
}

all_pass = True

# Test 1: Cognito configuration
print("Test 1: Cognito Client Configuration")
cognito = boto3.client('cognito-idp', region_name=config['region'])
response = cognito.describe_user_pool_client(
    UserPoolId=config['user_pool_id'],
    ClientId=config['client_id']
)
client_config = response['UserPoolClient']

checks = {
    'Authorization Code flow': 'code' in client_config['AllowedOAuthFlows'],
    'Callback URL configured': 'http://localhost:8080/callback' in client_config.get('CallbackURLs', []),
    'COGNITO provider': 'COGNITO' in client_config.get('SupportedIdentityProviders', []),
    'OAuth flows enabled': client_config.get('AllowedOAuthFlowsUserPoolClient') is True,
}

for check, passed in checks.items():
    status = "✅" if passed else "❌"
    print(f"  {status} {check}")
    if not passed:
        all_pass = False
print()

# Test 2: OAuth Discovery
print("Test 2: OAuth Discovery Endpoints")
try:
    # Protected Resource Metadata (RFC 9728)
    resource_metadata_url = f"{config['gateway_url'].rsplit('/mcp', 1)[0]}/.well-known/oauth-protected-resource"
    response = requests.get(resource_metadata_url, timeout=10)

    if response.status_code == 200:
        metadata = response.json()
        print(f"  ✅ Protected Resource Metadata found")
        print(f"     Resource: {metadata.get('resource', 'N/A')[:60]}...")
        print(f"     Auth servers: {len(metadata.get('authorization_servers', []))}")
    else:
        print(f"  ❌ Protected Resource Metadata: HTTP {response.status_code}")
        all_pass = False
except Exception as e:
    print(f"  ❌ Protected Resource Metadata error: {e}")
    all_pass = False

try:
    # Authorization Server Metadata (RFC 8414)
    auth_server_url = config['token_endpoint'].rsplit('/oauth2/token', 1)[0]
    auth_metadata_url = f"{auth_server_url}/.well-known/oauth-authorization-server"
    response = requests.get(auth_metadata_url, timeout=10)

    if response.status_code == 200:
        metadata = response.json()
        print(f"  ✅ Authorization Server Metadata found")
        print(f"     Issuer: {metadata.get('issuer', 'N/A')}")
        print(f"     Grant types: {metadata.get('grant_types_supported', [])}")
        print(f"     PKCE methods: {metadata.get('code_challenge_methods_supported', [])}")

        # Check for RFC 8707 support indicators
        if 'authorization_code' in metadata.get('grant_types_supported', []):
            print(f"  ✅ Authorization Code grant supported")
        if 'S256' in metadata.get('code_challenge_methods_supported', []):
            print(f"  ✅ PKCE S256 method supported")

    else:
        print(f"  ⚠️  Authorization Server Metadata: HTTP {response.status_code}")
except Exception as e:
    print(f"  ⚠️  Authorization Server Metadata error: {e}")
print()

# Test 3: Claude Code MCP Configuration
print("Test 3: Claude Code MCP Configuration")
try:
    credentials_path = '/home/ubuntu/.claude/.credentials.json'
    with open(credentials_path, 'r') as f:
        creds = json.load(f)

    mcp_oauth = creds.get('mcpOAuth', {})
    devops_keys = [k for k in mcp_oauth.keys() if k.startswith('devops-agent|')]

    if devops_keys:
        key = devops_keys[0]
        server_config = mcp_oauth[key]

        print(f"  ✅ MCP OAuth config found: {key}")
        print(f"     Server URL: {server_config.get('serverUrl', 'N/A')[:60]}...")
        print(f"     Auth server: {server_config.get('discoveryState', {}).get('authorizationServerUrl', 'N/A')[:60]}...")
        print(f"     OAuth metadata: {server_config.get('discoveryState', {}).get('oauthMetadataFound', False)}")

        # Check if token exists
        has_token = server_config.get('accessToken') and len(server_config.get('accessToken', '')) > 0
        print(f"     Has token: {has_token}")

        if not has_token:
            print()
            print("  ℹ️  No access token yet (expected before first OAuth flow)")
            print("     Token will be obtained automatically on first MCP tool call")

    else:
        print(f"  ❌ No devops-agent OAuth config found")
        all_pass = False
except FileNotFoundError:
    print(f"  ❌ Claude credentials file not found")
    all_pass = False
except Exception as e:
    print(f"  ❌ Error reading credentials: {e}")
    all_pass = False
print()

# Test 4: Cognito User exists
print("Test 4: Cognito User Pool")
try:
    response = cognito.list_users(
        UserPoolId=config['user_pool_id'],
        Limit=10
    )
    users = response.get('Users', [])
    confirmed_users = [u for u in users if u['UserStatus'] == 'CONFIRMED']

    print(f"  Total users: {len(users)}")
    print(f"  Confirmed users: {len(confirmed_users)}")

    if confirmed_users:
        print(f"  ✅ At least one confirmed user exists")
        for user in confirmed_users:
            print(f"     - {user['Username']} ({user['UserStatus']})")
    else:
        print(f"  ⚠️  No confirmed users found")
        print(f"     You'll need to create a user for login")
except Exception as e:
    print(f"  ❌ Error listing users: {e}")
    all_pass = False
print()

# Test 5: Cognito User Pool Tier (RFC 8707 requirement)
print("Test 5: Cognito User Pool Tier (RFC 8707 Requirement)")
try:
    response = cognito.describe_user_pool(UserPoolId=config['user_pool_id'])
    pool = response['UserPool']

    tier = pool.get('UserPoolTier', 'UNKNOWN')
    print(f"  User Pool Tier: {tier}")

    if tier in ['ESSENTIALS', 'PLUS']:
        print(f"  ✅ Tier supports RFC 8707 Resource Indicators")
    elif tier == 'LITE':
        print(f"  ❌ LITE tier does NOT support RFC 8707")
        print(f"     Need to upgrade to ESSENTIALS or PLUS")
        all_pass = False
    else:
        print(f"  ⚠️  Unknown tier: {tier}")

    # Check Managed Login
    managed_login = pool.get('ManagedLoginVersion')
    if managed_login:
        print(f"  ✅ Managed Login: Version {managed_login}")
    else:
        print(f"  ℹ️  Managed Login: Not enabled (optional)")

except Exception as e:
    print(f"  ❌ Error checking pool tier: {e}")
    all_pass = False
print()

# Summary
print("=" * 70)
print("READINESS SUMMARY")
print("=" * 70)
print()

if all_pass:
    print("✅ ALL CHECKS PASSED - Ready for Authorization Code flow!")
    print()
    print("Next steps:")
    print("1. In Claude Code, call any MCP tool")
    print("2. Browser will automatically open to Cognito login")
    print("3. Log in with your Cognito credentials")
    print("4. After successful login, token will be saved automatically")
    print("5. Subsequent tool calls will work without re-login")
    print()
    print("Example:")
    print("  > 请调用devops_echo工具，消息是'Testing Authorization Code'")
    print()
else:
    print("❌ SOME CHECKS FAILED - Review errors above")
    print()
    print("Common fixes:")
    print("- Run tests/run_tests.py to verify Cognito configuration")
    print("- Ensure User Pool tier is ESSENTIALS or PLUS")
    print("- Create a confirmed Cognito user if needed")
    print()

sys.exit(0 if all_pass else 1)
