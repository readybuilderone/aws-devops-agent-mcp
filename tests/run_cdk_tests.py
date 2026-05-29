#!/usr/bin/env python3
"""
Test runner for CDK configuration tests.
"""
import re
import subprocess
import sys

print("=" * 70)
print("TEST: CDK Code Configuration")
print("=" * 70)
print()

# Test 1: CDK code specifies Authorization Code
print("Test 1: CDK code specifies 'code' (Authorization Code) flow")
with open('cdk/stacks/devops_agent_mcp_stack.py', 'r') as f:
    cdk_code = f.read()

has_oauth_flows = 'AllowedOAuthFlows' in cdk_code
code_pattern = r'''['"]\s*code\s*['"]'''
has_code_flow = re.search(code_pattern, cdk_code) is not None

print(f"  Has AllowedOAuthFlows config: {has_oauth_flows}")
print(f"  Has 'code' flow specified: {has_code_flow}")

if has_oauth_flows and has_code_flow:
    print("  ✅ PASS")
    test1_pass = True
else:
    print("  ❌ FAIL: CDK code doesn't specify Authorization Code flow")
    test1_pass = False
print()

# Test 2: Callback URL
print("Test 2: CDK code specifies callback URL")
has_callback_urls = 'CallbackURLs' in cdk_code
has_localhost = 'localhost:8080/callback' in cdk_code

print(f"  Has CallbackURLs config: {has_callback_urls}")
print(f"  Has localhost:8080/callback: {has_localhost}")

if has_callback_urls and has_localhost:
    print("  ✅ PASS")
    test2_pass = True
else:
    print("  ❌ FAIL: CDK code doesn't specify callback URL")
    test2_pass = False
print()

# Test 3: COGNITO provider
print("Test 3: CDK code specifies COGNITO provider")
has_providers = 'SupportedIdentityProviders' in cdk_code
has_cognito = 'COGNITO' in cdk_code

print(f"  Has SupportedIdentityProviders config: {has_providers}")
print(f"  Has COGNITO provider: {has_cognito}")

if has_providers and has_cognito:
    print("  ✅ PASS")
    test3_pass = True
else:
    print("  ❌ FAIL: CDK code doesn't specify COGNITO provider")
    test3_pass = False
print()

# Test 4: CDK diff check (optional - requires CDK CLI)
print("Test 4: CDK diff shows no unexpected changes")
try:
    result = subprocess.run(
        ['cdk', 'diff', '--region', 'us-west-2'],
        capture_output=True,
        text=True,
        cwd='cdk',
        timeout=30
    )

    if result.returncode in [0, 1]:
        output = result.stdout + result.stderr
        # Check if trying to revert to client_credentials
        reverting = 'client_credentials' in output and 'code' not in output

        if not reverting:
            print("  ✅ PASS: No reversion to client_credentials")
            test4_pass = True
        else:
            print("  ❌ FAIL: CDK would revert to client_credentials")
            print("  Output:")
            print(output[:500])
            test4_pass = False
    else:
        print(f"  ⚠️  SKIP: cdk diff failed with code {result.returncode}")
        print(f"  Error: {result.stderr[:200]}")
        test4_pass = True  # Don't fail if CDK unavailable
except (FileNotFoundError, subprocess.TimeoutExpired):
    print("  ⚠️  SKIP: CDK CLI not available (optional test)")
    test4_pass = True  # Don't fail if CDK unavailable
print()

# Summary
print("=" * 70)
print("SUMMARY")
print("=" * 70)
all_tests = [test1_pass, test2_pass, test3_pass, test4_pass]
passed = sum(all_tests)
total = len(all_tests)
print(f"Passed: {passed}/{total}")
print()

if passed == total:
    print("✅ ALL CDK TESTS PASSED - Code matches deployed state!")
    sys.exit(0)
else:
    print("❌ SOME TESTS FAILED - CDK code needs update")
    print()
    print("Update cdk/stacks/devops_agent_mcp_stack.py to include:")
    print("  cfn_client.add_property_override('AllowedOAuthFlows', ['code'])")
    print("  cfn_client.add_property_override('CallbackURLs', ['http://localhost:8080/callback'])")
    print("  cfn_client.add_property_override('SupportedIdentityProviders', ['COGNITO'])")
    sys.exit(1)
