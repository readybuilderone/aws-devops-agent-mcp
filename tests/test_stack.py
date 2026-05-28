import aws_cdk as cdk
from aws_cdk import assertions

from cdk.stacks.devops_agent_mcp_stack import DevOpsAgentMcpStack


def _make_template():
    app = cdk.App()
    stack = DevOpsAgentMcpStack(app, "TestStack", agent_space_id="test-space-123")
    return assertions.Template.from_stack(stack)


def test_stack_contains_gateway_with_mcp_protocol():
    template = _make_template()

    template.has_resource_properties("AWS::BedrockAgentCore::Gateway", {
        "ProtocolConfiguration": assertions.Match.object_like({
            "Mcp": assertions.Match.any_value()
        })
    })


def test_stack_contains_lambda_with_python312_and_timeout():
    template = _make_template()

    template.has_resource_properties("AWS::Lambda::Function", {
        "Runtime": "python3.12",
        "Timeout": 60,
    })


def test_stack_has_cfn_outputs():
    template = _make_template()

    outputs = template.to_json()["Outputs"]
    output_keys = set(outputs.keys())
    assert "GatewayUrl" in output_keys
    assert "ClientId" in output_keys
    assert "TokenEndpoint" in output_keys


def test_lambda_has_agent_space_env_var():
    template = _make_template()

    template.has_resource_properties("AWS::Lambda::Function", {
        "Environment": assertions.Match.object_like({
            "Variables": assertions.Match.object_like({
                "DEFAULT_AGENT_SPACE_ID": "test-space-123"
            })
        })
    })
