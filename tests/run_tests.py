#!/usr/bin/env python3
"""
Simple test runner for manual testing without pytest.
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import dependencies
try:
    import boto3
except ImportError:
    print("ERROR: boto3 not found. Install with: apt install python3-boto3")
    sys.exit(1)

# Setup
aws_config = {
    'region': 'us-west-2',
    'user_pool_id': 'us-west-2_L0273ULfK',
    'client_id': '<COGNITO_CLIENT_ID>',
}

cognito_client = boto3.client('cognito-idp', region_name=aws_config['region'])

print("=" * 70)
print("TEST: Cognito Configuration for Authorization Code Flow")
print("=" * 70)
print()

# Get current configuration
response = cognito_client.describe_user_pool_client(
    UserPoolId=aws_config['user_pool_id'],
    ClientId=aws_config['client_id']
)
config = response['UserPoolClient']

# Test 1: Authorization Code flow enabled
print("Test 1: authorization_code flow enabled")
print(f"  Current flows: {config['AllowedOAuthFlows']}")
# AWS uses 'code' as the enum value for Authorization Code flow
if 'code' in config['AllowedOAuthFlows']:
    print("  ✅ PASS (AWS enum: 'code' = Authorization Code)")
    test1_pass = True
else:
    print("  ❌ FAIL: 'code' not in AllowedOAuthFlows")
    test1_pass = False
print()

# Test 2: Callback URL configured
print("Test 2: Callback URL configured")
print(f"  Current callbacks: {config.get('CallbackURLs', [])}")
if config.get('CallbackURLs') and 'http://localhost:8080/callback' in config['CallbackURLs']:
    print("  ✅ PASS")
    test2_pass = True
else:
    print("  ❌ FAIL: http://localhost:8080/callback not in CallbackURLs")
    test2_pass = False
print()

# Test 3: COGNITO identity provider
print("Test 3: COGNITO identity provider supported")
print(f"  Current providers: {config.get('SupportedIdentityProviders', [])}")
if config.get('SupportedIdentityProviders') and 'COGNITO' in config['SupportedIdentityProviders']:
    print("  ✅ PASS")
    test3_pass = True
else:
    print("  ❌ FAIL: COGNITO not in SupportedIdentityProviders")
    test3_pass = False
print()

# Test 4: OAuth flows enabled
print("Test 4: OAuth flows enabled for client")
print(f"  AllowedOAuthFlowsUserPoolClient: {config.get('AllowedOAuthFlowsUserPoolClient')}")
if config.get('AllowedOAuthFlowsUserPoolClient') is True:
    print("  ✅ PASS")
    test4_pass = True
else:
    print("  ❌ FAIL: AllowedOAuthFlowsUserPoolClient is not True")
    test4_pass = False
print()

# Test 5: OAuth scopes configured
print("Test 5: OAuth scopes configured")
scopes = config.get('AllowedOAuthScopes', [])
print(f"  Current scopes: {scopes}")
has_read = any('read' in scope for scope in scopes)
has_gateway = any('Gateway' in scope for scope in scopes)
if has_read and has_gateway:
    print("  ✅ PASS")
    test5_pass = True
else:
    print("  ❌ FAIL: Missing read or Gateway scope")
    test5_pass = False
print()

# Test 6: client_credentials NOT enabled
print("Test 6: client_credentials NOT in allowed flows")
print(f"  Current flows: {config['AllowedOAuthFlows']}")
if 'client_credentials' not in config['AllowedOAuthFlows']:
    print("  ✅ PASS (Migration complete)")
    test6_pass = True
else:
    print("  ❌ FAIL: client_credentials still enabled")
    test6_pass = False
print()

# Summary
print("=" * 70)
print("SUMMARY")
print("=" * 70)
all_tests = [test1_pass, test2_pass, test3_pass, test4_pass, test5_pass, test6_pass]
passed = sum(all_tests)
total = len(all_tests)
print(f"Passed: {passed}/{total}")
print()

if passed == total:
    print("✅ ALL TESTS PASSED - Authorization Code configuration verified!")
    sys.exit(0)
else:
    print("❌ SOME TESTS FAILED - Configuration needs update")
    print()
    print("To fix, run:")
    print("  aws cognito-idp update-user-pool-client \\")
    print(f"    --user-pool-id {aws_config['user_pool_id']} \\")
    print(f"    --client-id {aws_config['client_id']} \\")
    print("    --allowed-o-auth-flows authorization_code \\")
    print("    --allowed-o-auth-scopes \\")
    print("      'DevOpsAgentMcpStack-Gateway-0299DE6E/read' \\")
    print("      'DevOpsAgentMcpStack-Gateway-0299DE6E/write' \\")
    print("    --callback-urls 'http://localhost:8080/callback' \\")
    print("    --supported-identity-providers COGNITO \\")
    print("    --allowed-o-auth-flows-user-pool-client \\")
    print("    --region us-west-2")
    sys.exit(1)
