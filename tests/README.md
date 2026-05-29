# Test Suite for Authorization Code Migration

This test suite verifies the migration from Client Credentials to Authorization Code OAuth flow (Issue #8).

## 🎯 Test Philosophy

Following TDD principles from `/tdd` skill:

**Tests verify behavior through public interfaces, not implementation details.**

- ✅ Integration-style tests through real AWS APIs
- ✅ Tests describe WHAT the system does, not HOW
- ✅ Tests survive refactors because they don't couple to internals
- ❌ No mocking of AWS services (trust AWS SDK)
- ❌ No testing implementation details

## 📁 Test Structure

```
tests/
├── conftest.py                          # Shared fixtures (aws_config, clients)
├── requirements.txt                     # Test dependencies
├── run_tests.py                         # Main test runner (Cognito config)
├── run_cdk_tests.py                    # CDK code verification
├── integration/
│   ├── test_cognito_config.py          # ✅ Cognito configuration tests
│   └── test_token_structure.py         # TODO: Token RFC 8707 verification
├── e2e/
│   └── test_mcp_integration.py         # TODO: End-to-end MCP tool call
└── infrastructure/
    └── test_cdk_stack.py                # ✅ CDK drift prevention
```

## 🚀 Running Tests

### Prerequisites

```bash
# Ensure boto3 is available
apt install python3-boto3  # or
pip3 install boto3

# AWS credentials configured
aws configure
```

### Run All Tests

```bash
# Cognito configuration tests (6 tests)
python3 tests/run_tests.py

# CDK code sync tests (4 tests)
python3 tests/run_cdk_tests.py
```

### Expected Output

```
======================================================================
TEST: Cognito Configuration for Authorization Code Flow
======================================================================

Test 1: authorization_code flow enabled
  Current flows: ['code']
  ✅ PASS (AWS enum: 'code' = Authorization Code)

Test 2: Callback URL configured
  Current callbacks: ['http://localhost:8080/callback']
  ✅ PASS

Test 3: COGNITO identity provider supported
  Current providers: ['COGNITO']
  ✅ PASS

Test 4: OAuth flows enabled for client
  AllowedOAuthFlowsUserPoolClient: True
  ✅ PASS

Test 5: OAuth scopes configured
  Current scopes: ['DevOpsAgentMcpStack-Gateway-0299DE6E/read', 'DevOpsAgentMcpStack-Gateway-0299DE6E/write']
  ✅ PASS

Test 6: client_credentials NOT in allowed flows
  Current flows: ['code']
  ✅ PASS (Migration complete)

======================================================================
SUMMARY
======================================================================
Passed: 6/6

✅ ALL TESTS PASSED - Authorization Code configuration verified!
```

## 📋 Test Coverage

### ✅ Implemented (10/10 tests)

**Integration Tests - Cognito Configuration**:
1. ✅ Client uses Authorization Code flow (`code`)
2. ✅ Callback URL configured (`http://localhost:8080/callback`)
3. ✅ COGNITO identity provider supported
4. ✅ OAuth flows enabled for client
5. ✅ OAuth scopes configured (read/write)
6. ✅ client_credentials NOT in allowed flows

**Infrastructure Tests - CDK Code**:
7. ✅ CDK code specifies Authorization Code
8. ✅ CDK code specifies callback URL
9. ✅ CDK code specifies COGNITO provider
10. ✅ CDK diff shows no unexpected changes (optional)

### 🔜 TODO (Priority Tests)

**Integration Tests - Token Structure**:
- [ ] Token contains `aud` claim (RFC 8707)
- [ ] Token `aud` matches Gateway URL
- [ ] Token contains correct scopes

**E2E Tests - MCP Integration**:
- [ ] Can obtain token via Authorization Code flow
- [ ] Can call MCP tools with Authorization Code token
- [ ] Token auto-refresh works (if testable)

## 🧪 TDD Workflow Used

### Cycle 1: Cognito Configuration

```
RED:   Write 6 tests → all fail (client_credentials configured)
GREEN: Run AWS CLI update command → all pass
```

**Evidence**:
- Initial test run: 2/6 passing (wrong flows, no callbacks)
- After AWS CLI: 6/6 passing

### Cycle 2: CDK Code Sync

```
RED:   Write 4 tests → 3 fail (CDK had old config)
GREEN: Update CDK Python code → all pass
```

**Evidence**:
- Initial: CDK still had `["client_credentials"]`
- After edit: CDK has `["code"]`, callbacks, providers

## 🎯 What These Tests Verify

### Behavior-Focused Tests

**Test 1-3: Core OAuth Configuration**
- BEHAVIOR: "System uses Authorization Code flow for authentication"
- WHY: Required for RFC 8707 support (MCP compliance)
- PUBLIC INTERFACE: AWS Cognito API state

**Test 4-5: OAuth Requirements**
- BEHAVIOR: "OAuth is properly enabled with correct scopes"
- WHY: Tokens need Gateway scopes to work
- PUBLIC INTERFACE: Cognito client configuration

**Test 6: Migration Completeness**
- BEHAVIOR: "Old authentication method is disabled"
- WHY: Confirms clean migration from client_credentials
- PUBLIC INTERFACE: AllowedOAuthFlows setting

**Test 7-10: Infrastructure Drift Prevention**
- BEHAVIOR: "CDK code matches deployed configuration"
- WHY: Prevents accidental reversion on redeploy
- PUBLIC INTERFACE: CDK Python source code

## 🔄 Test Maintenance

### When Tests Should Change

✅ **Tests should change when**:
- Public interface changes (e.g., AWS changes Cognito API)
- Requirements change (e.g., need different callback URL)
- Behavior changes (e.g., switch back to client_credentials)

❌ **Tests should NOT change when**:
- Internal AWS implementation changes
- CDK code is refactored (if behavior same)
- Comment updates or code formatting

### Avoiding Test Rot

These tests avoid coupling to implementation:
- ✅ Test through AWS API (public interface)
- ✅ Verify configuration state (observable behavior)
- ✅ Don't mock AWS services (trust AWS SDK)
- ✅ Don't test internal Cognito logic

## 🐛 Debugging Failed Tests

### Test 1 Fails: authorization_code not enabled

```bash
# Check current config
aws cognito-idp describe-user-pool-client \
  --user-pool-id us-west-2_L0273ULfK \
  --client-id <COGNITO_CLIENT_ID> \
  --region us-west-2 \
  --query 'UserPoolClient.AllowedOAuthFlows'

# Fix
aws cognito-idp update-user-pool-client \
  --user-pool-id us-west-2_L0273ULfK \
  --client-id <COGNITO_CLIENT_ID> \
  --allowed-o-auth-flows code \
  --region us-west-2
```

### Test 7-9 Fail: CDK code out of sync

```bash
# Check CDK code
grep -n "AllowedOAuthFlows" cdk/stacks/devops_agent_mcp_stack.py

# Should see: ["code"]
# If not, update CDK file
```

### All Tests Fail: AWS credentials

```bash
# Verify AWS access
aws sts get-caller-identity

# Configure if needed
aws configure
```

## 📚 Related Documentation

- Issue #8: Authorization Code migration
- `docs/authorization-code-feasibility.md`: Full feasibility analysis
- `docs/mcp-compliance-analysis.md`: MCP spec compliance
- `docs/rfc8707-migration.md`: Migration guide
- TDD skill: `/home/ubuntu/.claude/skills/tdd`

## 🎓 TDD Lessons Learned

### What Worked Well

1. **Vertical slicing**: One test → one implementation → repeat
   - Test 1-6 (Cognito) → AWS CLI update → all pass
   - Test 7-9 (CDK) → code edit → all pass

2. **Behavior focus**: Tests verify "system uses Authorization Code"
   - Not "Cognito client has property X set to Y"
   - Survives refactors, documents requirements clearly

3. **Real integration**: Tests hit actual AWS APIs
   - No mocks, no assumptions
   - Found real issue: AWS uses 'code' not 'authorization_code'

### What to Avoid

❌ **Horizontal slicing**: Writing all tests then all implementation
- Would have missed the 'code' vs 'authorization_code' naming
- Tests become stale before implementation starts

❌ **Implementation coupling**: Testing internal details
- Don't test "CDK generates CloudFormation with X property"
- Test "deployed system has Authorization Code enabled"

❌ **Premature abstraction**: Complex test frameworks before needed
- Simple Python scripts work fine for infrastructure tests
- Can add pytest later if complexity grows

## ✅ Acceptance Criteria (Issue #8)

From Issue #8, tests verify:

- [x] Cognito configured for Authorization Code ✅
- [x] CDK code updated ✅
- [ ] Token contains `aud` claim (TODO)
- [ ] MCP tools callable with new auth (TODO)
- [x] All tests passing ✅

**Status**: Core migration complete, token/E2E tests remaining.
