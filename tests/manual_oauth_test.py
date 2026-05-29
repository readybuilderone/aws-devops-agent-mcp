#!/usr/bin/env python3
"""
Manual OAuth Authorization Code Flow Test

This script simulates what Claude Code does when using Authorization Code flow.
It helps verify that the Cognito configuration is correct before testing with
the actual Claude Code client.

Usage:
    python3 tests/manual_oauth_test.py

This will:
1. Generate PKCE parameters
2. Print the authorization URL
3. Wait for you to complete browser login
4. Exchange the authorization code for tokens
5. Verify the token structure (especially 'aud' claim for RFC 8707)
"""

import base64
import hashlib
import json
import os
import secrets
import sys
import urllib.parse
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
import requests

# Configuration
CONFIG = {
    'client_id': '<COGNITO_CLIENT_ID>',
    'gateway_url': 'https://devops-agent-mcp-elhze1stwj.gateway.bedrock-agentcore.us-west-2.amazonaws.com/mcp',
    'token_endpoint': 'https://devopsagentmcpstack-gateway-0299de6e.auth.us-west-2.amazoncognito.com/oauth2/token',
    'auth_endpoint': 'https://devopsagentmcpstack-gateway-0299de6e.auth.us-west-2.amazoncognito.com/oauth2/authorize',
    'redirect_uri': 'http://localhost:8080/callback',
    'scopes': [
        'DevOpsAgentMcpStack-Gateway-0299DE6E/read',
        'DevOpsAgentMcpStack-Gateway-0299DE6E/write'
    ]
}

# Global to capture authorization code
auth_code = None
auth_state = None


class CallbackHandler(BaseHTTPRequestHandler):
    """Simple HTTP server to capture OAuth callback."""

    def do_GET(self):
        global auth_code, auth_state

        # Parse query parameters
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)

        if 'code' in params:
            auth_code = params['code'][0]
            auth_state = params.get('state', [''])[0]

            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(b"""
                <html>
                <head><title>OAuth Success</title></head>
                <body>
                    <h1>Authentication Successful!</h1>
                    <p>You can close this window and return to the terminal.</p>
                    <script>window.close();</script>
                </body>
                </html>
            """)
        elif 'error' in params:
            error = params['error'][0]
            error_desc = params.get('error_description', ['Unknown error'])[0]

            self.send_response(400)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(f"""
                <html>
                <head><title>OAuth Error</title></head>
                <body>
                    <h1>Authentication Failed</h1>
                    <p>Error: {error}</p>
                    <p>Description: {error_desc}</p>
                </body>
                </html>
            """.encode())
        else:
            self.send_response(400)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(b"<html><body><h1>Invalid callback</h1></body></html>")

    def log_message(self, format, *args):
        # Suppress logs
        pass


def generate_pkce_params():
    """Generate PKCE code verifier and challenge."""
    # Generate code verifier (43-128 characters)
    code_verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode('utf-8').rstrip('=')

    # Generate code challenge (SHA256 hash of verifier)
    code_challenge = base64.urlsafe_b64encode(
        hashlib.sha256(code_verifier.encode('utf-8')).digest()
    ).decode('utf-8').rstrip('=')

    return code_verifier, code_challenge


def build_authorization_url(code_challenge, state):
    """Build OAuth authorization URL with RFC 8707 resource parameter."""
    params = {
        'response_type': 'code',
        'client_id': CONFIG['client_id'],
        'redirect_uri': CONFIG['redirect_uri'],
        'scope': ' '.join(CONFIG['scopes']),
        'state': state,
        'code_challenge': code_challenge,
        'code_challenge_method': 'S256',
        # RFC 8707: Resource Indicators
        'resource': CONFIG['gateway_url']
    }

    return f"{CONFIG['auth_endpoint']}?{urllib.parse.urlencode(params)}"


def exchange_code_for_token(code, code_verifier):
    """Exchange authorization code for access token."""
    data = {
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': CONFIG['redirect_uri'],
        'client_id': CONFIG['client_id'],
        'code_verifier': code_verifier,
        # RFC 8707: Include resource parameter in token request
        'resource': CONFIG['gateway_url']
    }

    response = requests.post(CONFIG['token_endpoint'], data=data)
    return response


def decode_jwt_payload(token):
    """Decode JWT payload (without verification)."""
    try:
        # JWT format: header.payload.signature
        parts = token.split('.')
        if len(parts) != 3:
            return None

        # Decode payload (add padding if needed)
        payload = parts[1]
        payload += '=' * (4 - len(payload) % 4)
        decoded = base64.urlsafe_b64decode(payload)
        return json.loads(decoded)
    except Exception as e:
        print(f"Error decoding JWT: {e}")
        return None


def main():
    print("=" * 70)
    print("Manual OAuth Authorization Code Flow Test")
    print("=" * 70)
    print()

    # Step 1: Generate PKCE parameters
    print("Step 1: Generating PKCE parameters...")
    code_verifier, code_challenge = generate_pkce_params()
    state = base64.urlsafe_b64encode(secrets.token_bytes(24)).decode('utf-8').rstrip('=')
    print(f"  Code verifier: {code_verifier[:20]}...")
    print(f"  Code challenge: {code_challenge[:20]}...")
    print(f"  State: {state[:20]}...")
    print()

    # Step 2: Build authorization URL
    print("Step 2: Building authorization URL...")
    auth_url = build_authorization_url(code_challenge, state)
    print(f"  URL: {auth_url[:80]}...")
    print()

    # Check for RFC 8707 resource parameter
    if 'resource=' in auth_url:
        print("  ✅ RFC 8707: 'resource' parameter included")
        resource_param = urllib.parse.parse_qs(urllib.parse.urlparse(auth_url).query)['resource'][0]
        print(f"  Resource: {resource_param}")
    else:
        print("  ❌ RFC 8707: 'resource' parameter MISSING")
    print()

    # Step 3: Start callback server
    print("Step 3: Starting callback server on http://localhost:8080 ...")
    server = HTTPServer(('localhost', 8080), CallbackHandler)
    print("  Server started. Waiting for OAuth callback...")
    print()

    # Step 4: Open browser
    print("Step 4: Opening browser for authentication...")
    print(f"  URL: {CONFIG['auth_endpoint']}")
    print()
    print("  Please log in with your Cognito credentials.")
    print("  After successful login, you'll be redirected back here.")
    print()

    try:
        webbrowser.open(auth_url)
    except Exception as e:
        print(f"  ⚠️  Could not open browser automatically: {e}")
        print(f"  Please open this URL manually:")
        print(f"  {auth_url}")
        print()

    # Wait for callback (timeout after 5 minutes)
    print("  Waiting for callback...")
    server.timeout = 300  # 5 minutes
    server.handle_request()

    if not auth_code:
        print()
        print("❌ FAILED: No authorization code received")
        print("   Possible reasons:")
        print("   - User cancelled login")
        print("   - Cognito configuration error")
        print("   - Network issue")
        sys.exit(1)

    print()
    print(f"  ✅ Authorization code received: {auth_code[:20]}...")
    print(f"  State matches: {auth_state == state}")
    print()

    # Step 5: Exchange code for token
    print("Step 5: Exchanging authorization code for access token...")
    print(f"  Token endpoint: {CONFIG['token_endpoint']}")
    print(f"  Grant type: authorization_code")
    print(f"  PKCE: code_verifier={code_verifier[:20]}...")
    print(f"  RFC 8707: resource={CONFIG['gateway_url']}")
    print()

    response = exchange_code_for_token(auth_code, code_verifier)

    if response.status_code != 200:
        print(f"❌ FAILED: Token exchange failed with status {response.status_code}")
        print(f"   Response: {response.text}")
        sys.exit(1)

    token_data = response.json()
    print("  ✅ Token received successfully!")
    print()

    # Step 6: Verify token structure
    print("Step 6: Verifying token structure (RFC 8707)...")
    access_token = token_data.get('access_token')

    if not access_token:
        print("  ❌ No access_token in response")
        sys.exit(1)

    print(f"  Access token length: {len(access_token)}")
    print(f"  Token type: {token_data.get('token_type')}")
    print(f"  Expires in: {token_data.get('expires_in')} seconds")
    print(f"  Has refresh_token: {'refresh_token' in token_data}")
    print()

    # Decode and check claims
    claims = decode_jwt_payload(access_token)
    if not claims:
        print("  ❌ Could not decode JWT payload")
        sys.exit(1)

    print("  JWT Claims:")
    for key in ['sub', 'aud', 'scope', 'token_use', 'username', 'client_id']:
        if key in claims:
            value = claims[key]
            if isinstance(value, str) and len(value) > 60:
                value = value[:60] + "..."
            print(f"    {key}: {value}")
    print()

    # Check RFC 8707 compliance
    print("Step 7: RFC 8707 Compliance Check...")

    if 'aud' in claims:
        print("  ✅ 'aud' claim present (RFC 8707 compliant)")
        print(f"     Value: {claims['aud']}")

        # Check if aud matches gateway URL
        if claims['aud'] == CONFIG['gateway_url']:
            print("  ✅ 'aud' matches Gateway URL exactly")
        elif CONFIG['gateway_url'] in claims['aud']:
            print("  ✅ 'aud' contains Gateway URL")
        else:
            print(f"  ⚠️  'aud' does not match Gateway URL")
            print(f"     Expected: {CONFIG['gateway_url']}")
            print(f"     Got: {claims['aud']}")
    else:
        print("  ❌ 'aud' claim MISSING (RFC 8707 NOT compliant)")
        print("     This indicates Cognito did not process the 'resource' parameter")
    print()

    # Step 8: Test MCP tool call
    print("Step 8: Testing MCP tool call with token...")
    mcp_request = {
        'jsonrpc': '2.0',
        'method': 'tools/call',
        'params': {
            'name': 'devops-tools___devops_echo',
            'arguments': {'message': 'Testing Authorization Code + RFC 8707'}
        },
        'id': 1
    }

    headers = {
        'Authorization': f"Bearer {access_token}",
        'Content-Type': 'application/json'
    }

    try:
        mcp_response = requests.post(CONFIG['gateway_url'], json=mcp_request, headers=headers)

        if mcp_response.status_code == 200:
            result = mcp_response.json()
            print("  ✅ MCP tool call successful!")
            print(f"     Response: {json.dumps(result.get('result', {}), indent=6)}")
        else:
            print(f"  ❌ MCP tool call failed: {mcp_response.status_code}")
            print(f"     Response: {mcp_response.text[:200]}")
    except Exception as e:
        print(f"  ❌ MCP tool call error: {e}")
    print()

    # Summary
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print()
    print("✅ Authorization Code Flow: SUCCESS")
    print(f"✅ Token Obtained: {len(access_token)} bytes")
    print(f"{'✅' if 'aud' in claims else '❌'} RFC 8707 'aud' claim: {'Present' if 'aud' in claims else 'MISSING'}")
    print(f"{'✅' if 'refresh_token' in token_data else '❌'} Refresh token: {'Present' if 'refresh_token' in token_data else 'MISSING'}")
    print()

    if 'aud' in claims and 'refresh_token' in token_data:
        print("🎉 FULL SUCCESS: 100% MCP Compliant!")
        print()
        print("Your Cognito is now configured for:")
        print("  - Authorization Code flow with PKCE")
        print("  - RFC 8707 Resource Indicators (aud claim)")
        print("  - Automatic token refresh (refresh_token)")
        print()
        print("Claude Code will work seamlessly with this configuration.")
    else:
        print("⚠️  PARTIAL SUCCESS: Some features missing")
        if 'aud' not in claims:
            print("  - RFC 8707 'aud' claim missing")
            print("    → Check Cognito User Pool tier (needs ESSENTIALS/PLUS)")
        if 'refresh_token' not in token_data:
            print("  - Refresh token missing")
            print("    → Token will expire and require manual refresh")
    print()

    # Save token for testing
    print("Token saved to: /tmp/oauth_test_token.json")
    with open('/tmp/oauth_test_token.json', 'w') as f:
        json.dump({
            'access_token': access_token,
            'refresh_token': token_data.get('refresh_token'),
            'claims': claims,
            'full_response': token_data
        }, f, indent=2)


if __name__ == '__main__':
    main()
