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

        CfnOutput(self, "GatewayUrl", value=gateway.gateway_url or "")
        CfnOutput(self, "ClientId",
            value=gateway.user_pool_client.user_pool_client_id if gateway.user_pool_client else ""
        )
        CfnOutput(self, "TokenEndpoint", value=gateway.token_endpoint_url or "")
