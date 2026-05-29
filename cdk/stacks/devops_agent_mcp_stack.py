import os
from constructs import Construct
import aws_cdk as cdk
from aws_cdk import (
    Stack,
    CfnOutput,
    Duration,
    aws_lambda as _lambda,
    aws_bedrockagentcore as agentcore,
)


TOOL_SCHEMA = [
    agentcore.ToolDefinition(
        name="devops_echo",
        description="Echo tool for testing connectivity. Returns the input message.",
        input_schema=agentcore.SchemaDefinition(
            type=agentcore.SchemaDefinitionType.OBJECT,
            properties={
                "message": agentcore.SchemaDefinition(
                    type=agentcore.SchemaDefinitionType.STRING,
                    description="The message to echo back",
                )
            },
            required=["message"],
        ),
    )
]


class DevOpsAgentMcpStack(Stack):
    def __init__(self, scope: Construct, id: str, *, agent_space_id: str = "", **kwargs):
        super().__init__(scope, id, **kwargs)

        handler = _lambda.Function(self, "Handler",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="handler.lambda_handler",
            code=_lambda.Code.from_asset(os.path.join(os.path.dirname(__file__), "..", "..", "lambda")),
            timeout=Duration.seconds(60),
            environment={
                "DEFAULT_AGENT_SPACE_ID": agent_space_id,
            },
        )

        gateway = agentcore.Gateway(self, "Gateway",
            gateway_name="devops-agent-mcp",
            description="DevOps Agent MCP Server for SRE queries",
        )

        gateway.add_lambda_target("DevOpsTools",
            gateway_target_name="devops-tools",
            description="DevOps Agent query tools",
            lambda_function=handler,
            tool_schema=agentcore.ToolSchema.from_inline(TOOL_SCHEMA),
        )

        # Configure Cognito User Pool Client for Authorization Code flow + RFC 8707
        #
        # Background: AWS Cognito added RFC 8707 Resource Indicators support on 2025-10-24,
        # but ONLY for Authorization Code flow, NOT for Client Credentials (M2M).
        #
        # Previous configuration: client_credentials (M2M)
        # - No user interaction required
        # - No RFC 8707 support → no 'aud' claim in tokens
        # - MCP compliance: 66%
        #
        # OAuth Configuration: client_credentials (Machine-to-Machine)
        # - M2M authentication without user interaction
        # - MCP official M2M method
        # - Token management via scripts
        # - MCP compliance: 66% (no RFC 8707 aud claim)
        #
        # Note: Authorization Code with RFC 8707 attempted but failed due to
        # Cognito limitation requiring Managed Login. See docs for details.
        #
        if gateway.user_pool_client:
            # Get the CloudFormation resource
            cfn_client = gateway.user_pool_client.node.default_child

            # Configure Client Credentials flow for M2M
            cfn_client.add_property_override("AllowedOAuthFlows", ["client_credentials"])
            cfn_client.add_property_override("AllowedOAuthFlowsUserPoolClient", True)

            # Scopes are already configured by Gateway as:
            # - {ResourceServerIdentifier}/read
            # - {ResourceServerIdentifier}/write
            # No need to override unless you want different scopes

        CfnOutput(self, "GatewayUrl", value=gateway.gateway_url or "")
        CfnOutput(self, "ClientId",
            value=gateway.user_pool_client.user_pool_client_id if gateway.user_pool_client else ""
        )
        CfnOutput(self, "TokenEndpoint", value=gateway.token_endpoint_url or "")

        # Output instructions for token management
        CfnOutput(self, "SetupInstructions",
            value="Run ./scripts/setup.sh to configure MCP connection with Client Credentials flow",
            description="Quick setup command"
        )
