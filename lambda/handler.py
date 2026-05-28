import json


DELIMITER = "___"


def lambda_handler(event, context):
    tool_name = _get_tool_name(context)

    if tool_name == "devops_echo":
        return _handle_echo(event)

    return {"error": f"Unknown tool: {tool_name}"}


def _get_tool_name(context):
    original = context.client_context.custom.get("bedrockAgentCoreToolName", "")
    if DELIMITER in original:
        return original[original.index(DELIMITER) + len(DELIMITER):]
    return original


def _handle_echo(event):
    message = event.get("message", "")
    return {"message": message, "echo": True}
