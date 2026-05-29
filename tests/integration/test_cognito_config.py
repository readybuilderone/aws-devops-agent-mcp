"""
Test Cognito User Pool Client configuration for Authorization Code flow.

These tests verify the observable behavior of the Cognito configuration,
not the implementation details.
"""
import pytest


class TestCognitoAuthorizationCodeConfig:
    """
    Verify Cognito client is configured for Authorization Code flow.

    This is the critical behavior for Issue #8: migrating from client_credentials
    to authorization_code to enable RFC 8707 support.
    """

    def test_client_uses_authorization_code_flow(self, user_pool_client_config):
        """
        BEHAVIOR: Cognito client should be configured for authorization_code flow.

        WHY: Authorization Code is required for RFC 8707 support.
        Client Credentials flow does not support the 'resource' parameter.

        NOTE: AWS uses 'code' as the enum value for Authorization Code flow.
        """
        config = user_pool_client_config

        # Assert
        assert 'code' in config['AllowedOAuthFlows'], (
            "Expected 'code' (authorization_code) flow to be enabled. "
            f"Found: {config['AllowedOAuthFlows']}"
        )

    def test_client_has_callback_url(self, user_pool_client_config):
        """
        BEHAVIOR: Cognito client should have callback URL configured.

        WHY: Authorization Code flow requires a callback URL for OAuth redirect.
        Claude Code expects http://localhost:8080/callback.
        """
        config = user_pool_client_config

        # Assert
        assert config['CallbackURLs'] is not None, (
            "CallbackURLs should not be None"
        )
        assert 'http://localhost:8080/callback' in config['CallbackURLs'], (
            f"Expected http://localhost:8080/callback in callbacks. "
            f"Found: {config['CallbackURLs']}"
        )

    def test_client_supports_cognito_identity_provider(self, user_pool_client_config):
        """
        BEHAVIOR: Cognito client should support COGNITO identity provider.

        WHY: Users need to authenticate via Cognito user pool (not federated IdP).
        """
        config = user_pool_client_config

        # Assert
        assert config['SupportedIdentityProviders'] is not None, (
            "SupportedIdentityProviders should not be None"
        )
        assert 'COGNITO' in config['SupportedIdentityProviders'], (
            f"Expected COGNITO in identity providers. "
            f"Found: {config['SupportedIdentityProviders']}"
        )

    def test_oauth_flows_are_enabled(self, user_pool_client_config):
        """
        BEHAVIOR: OAuth flows should be explicitly enabled for the client.

        WHY: AllowedOAuthFlowsUserPoolClient must be True for OAuth to work.
        """
        config = user_pool_client_config

        # Assert
        assert config['AllowedOAuthFlowsUserPoolClient'] is True, (
            "AllowedOAuthFlowsUserPoolClient must be True"
        )

    def test_oauth_scopes_are_configured(self, user_pool_client_config):
        """
        BEHAVIOR: OAuth scopes should include resource server scopes.

        WHY: Scopes define what the token can access. We need read/write scopes
        for the DevOps Agent Gateway resource server.
        """
        config = user_pool_client_config

        # Assert
        assert config['AllowedOAuthScopes'] is not None, (
            "AllowedOAuthScopes should not be None"
        )

        scopes = config['AllowedOAuthScopes']
        # Should have at least read scope
        assert any('read' in scope for scope in scopes), (
            f"Expected a scope containing 'read'. Found: {scopes}"
        )
        # Should have Gateway resource server identifier
        assert any('Gateway' in scope for scope in scopes), (
            f"Expected Gateway resource server scope. Found: {scopes}"
        )


class TestCognitoClientCredentialsNotEnabled:
    """
    Verify that client_credentials flow is NOT enabled.

    This confirms the migration away from the old auth method.
    """

    def test_client_credentials_not_in_allowed_flows(self, user_pool_client_config):
        """
        BEHAVIOR: client_credentials should NOT be in allowed flows.

        WHY: We're migrating away from client_credentials to authorization_code.
        Having both enabled could cause confusion about which flow to use.
        """
        config = user_pool_client_config

        # Assert
        assert 'client_credentials' not in config['AllowedOAuthFlows'], (
            "client_credentials should not be enabled after migration. "
            f"Found: {config['AllowedOAuthFlows']}"
        )
