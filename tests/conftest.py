"""
Shared test fixtures for AWS DevOps Agent MCP tests.
"""
import os
import pytest
import boto3


@pytest.fixture(scope="session")
def aws_config():
    """AWS configuration from environment or defaults."""
    return {
        'region': os.environ.get('AWS_REGION', 'us-west-2'),
        'user_pool_id': os.environ.get('USER_POOL_ID', 'us-west-2_L0273ULfK'),
        'client_id': os.environ.get('CLIENT_ID', '<COGNITO_CLIENT_ID>'),
        'gateway_url': os.environ.get('GATEWAY_URL',
            'https://devops-agent-mcp-elhze1stwj.gateway.bedrock-agentcore.us-west-2.amazonaws.com/mcp'),
        'stack_name': os.environ.get('STACK_NAME', 'DevOpsAgentMcpStack'),
    }


@pytest.fixture(scope="session")
def cognito_client(aws_config):
    """Boto3 Cognito client."""
    return boto3.client('cognito-idp', region_name=aws_config['region'])


@pytest.fixture(scope="session")
def cloudformation_client(aws_config):
    """Boto3 CloudFormation client."""
    return boto3.client('cloudformation', region_name=aws_config['region'])


@pytest.fixture(scope="session")
def user_pool_client_config(cognito_client, aws_config):
    """The deployed Cognito User Pool Client configuration."""
    response = cognito_client.describe_user_pool_client(
        UserPoolId=aws_config['user_pool_id'],
        ClientId=aws_config['client_id']
    )
    return response['UserPoolClient']


@pytest.fixture(scope="session")
def stack_outputs(cloudformation_client, aws_config):
    """CloudFormation stack outputs."""
    response = cloudformation_client.describe_stacks(
        StackName=aws_config['stack_name']
    )
    outputs = {}
    for output in response['Stacks'][0]['Outputs']:
        outputs[output['OutputKey']] = output['OutputValue']
    return outputs
