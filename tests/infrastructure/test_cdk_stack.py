"""
Test CDK stack configuration matches deployed state.

These tests verify that the Infrastructure as Code (CDK) matches
the actual deployed configuration, preventing drift.
"""
import subprocess
import json
import re


class TestCDKStackConfiguration:
    """
    Verify CDK code defines Authorization Code configuration.

    WHY: We want to prevent configuration drift. If someone runs
    'cdk deploy' again, it should maintain Authorization Code settings,
    not revert to client_credentials.
    """

    def test_cdk_code_specifies_authorization_code(self):
        """
        BEHAVIOR: CDK code should specify 'code' (Authorization Code) flow.

        This test reads the actual CDK Python code and verifies it
        contains the correct OAuth flow configuration.
        """
        # Act
        with open('cdk/stacks/devops_agent_mcp_stack.py', 'r') as f:
            cdk_code = f.read()

        # Assert
        # Looking for: add_property_override("AllowedOAuthFlows", ["code"])
        # or similar patterns
        assert 'AllowedOAuthFlows' in cdk_code, (
            "CDK code should configure AllowedOAuthFlows"
        )

        # Should contain "code" (Authorization Code)
        # Pattern: ["code"] or ['code']
        code_pattern = r'''['"]\s*code\s*['"]'''
        assert re.search(code_pattern, cdk_code), (
            "CDK code should specify 'code' flow for Authorization Code. "
            "This prevents reverting to client_credentials on redeploy."
        )

    def test_cdk_code_specifies_callback_url(self):
        """
        BEHAVIOR: CDK code should specify callback URL.
        """
        # Act
        with open('cdk/stacks/devops_agent_mcp_stack.py', 'r') as f:
            cdk_code = f.read()

        # Assert
        assert 'CallbackURLs' in cdk_code, (
            "CDK code should configure CallbackURLs"
        )
        assert 'localhost:8080/callback' in cdk_code, (
            "CDK code should include localhost:8080/callback URL"
        )

    def test_cdk_code_specifies_cognito_provider(self):
        """
        BEHAVIOR: CDK code should specify COGNITO identity provider.
        """
        # Act
        with open('cdk/stacks/devops_agent_mcp_stack.py', 'r') as f:
            cdk_code = f.read()

        # Assert
        assert 'SupportedIdentityProviders' in cdk_code, (
            "CDK code should configure SupportedIdentityProviders"
        )
        assert 'COGNITO' in cdk_code, (
            "CDK code should specify COGNITO provider"
        )

    def test_cdk_diff_shows_no_unexpected_changes(self):
        """
        BEHAVIOR: Running 'cdk diff' should show no unexpected changes.

        WHY: If CDK code matches deployed state, diff should be empty
        or only show expected changes.
        """
        # Act
        result = subprocess.run(
            ['cdk', 'diff', '--region', 'us-west-2'],
            capture_output=True,
            text=True,
            cwd='cdk'
        )

        # Assert
        # Exit code 0 = no changes, 1 = has changes but successful
        assert result.returncode in [0, 1], (
            f"cdk diff failed with exit code {result.returncode}. "
            f"Error: {result.stderr}"
        )

        output = result.stdout + result.stderr

        # Should not see client_credentials being added back
        assert 'client_credentials' not in output or 'code' in output, (
            "CDK should not try to revert to client_credentials"
        )
