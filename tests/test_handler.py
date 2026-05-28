import sys
import os
from unittest.mock import MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "lambda"))

from handler import lambda_handler


def _make_context(tool_name: str):
    ctx = MagicMock()
    ctx.client_context.custom = {
        "bedrockAgentCoreToolName": f"devops-tools___{tool_name}",
        "bedrockAgentCoreGatewayId": "gw-123",
        "bedrockAgentCoreTargetId": "target-123",
    }
    return ctx


def test_echo_tool_returns_message():
    event = {"message": "hello world"}
    context = _make_context("devops_echo")

    result = lambda_handler(event, context)

    assert result == {"message": "hello world", "echo": True}
