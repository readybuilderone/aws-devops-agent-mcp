#!/usr/bin/env python3
import os
import aws_cdk as cdk
from stacks.devops_agent_mcp_stack import DevOpsAgentMcpStack

app = cdk.App()

agent_space_id = app.node.try_get_context("agent_space_id") or os.environ.get("DEFAULT_AGENT_SPACE_ID", "")

DevOpsAgentMcpStack(app, "DevOpsAgentMcpStack",
    agent_space_id=agent_space_id,
)

app.synth()
