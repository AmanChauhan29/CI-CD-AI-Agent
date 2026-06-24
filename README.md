# AI-Powered CI/CD Auto-Remediation Agent

## Overview
The AI-Powered CI/CD Auto-Remediation Agent is an event-driven platform that automatically detects failed GitHub Actions workflows, analyzes failure logs, generates remediation plans using an LLM, applies fixes, creates pull requests, verifies pipeline execution, and automatically merges successful remediations.
The goal of the system is to reduce manual intervention in CI/CD failures and provide a self-healing software delivery workflow.

## Problem Statement
Modern CI/CD pipelines frequently fail due to:
- Missing dependencies
- Test failures
- Build failures
- Workflow misconfigurations
- Environment issues

Engineers spend significant time:
- Downloading workflow logs
- Finding root causes
- Implementing fixes
- Creating pull requests
- Verifying remediation

This project automates the entire process.

## High Level Architecture
```
GitHub Actions Failure
          |
          v
     GitHub Webhook
          |
          v
      FastAPI API
          |
          v
      Local Queue
          |
          v
     Worker Thread
          |
          v
  Remediation Engine
          |
          +----------------+
          |                |
          v                v
      SQLite DB       GitHub API
          |                |
          |                |
          v                v
    Incident Store     Repository
                        Operations
```

## Event Flow
### Step 1: Workflow Failure
A GitHub Actions workflow fails.
Example:
```
Run Tests
pytest tests/
Failure:
pytest: command not found
```
GitHub emits a `workflow_run` event.

### Step 2: Webhook Trigger
GitHub sends a webhook payload to:
`POST /github/webhook`
Example:
```json
{
  "workflow_run": {
    "id": 28089485578,
    "conclusion": "failure"
  }
}
```

### Step 3: Queue Event
The webhook service validates the payload and pushes an event into an in-memory queue.
Example:
```python
event_queue.put({
    "run_id": 28089485578
})
```
Purpose:
- Immediate webhook response
- Decoupled processing
- Prevent GitHub timeout issues

### Step 4: Worker Processing
A background worker continuously consumes events.
```python
while True:
    event = event_queue.get()
```
The worker extracts:
```python
run_id = event["run_id"]
engine.process(run_id)
```

## Remediation Engine
The Remediation Engine is the core orchestration layer.
`RemediationEngine.process(run_id)` responsibilities:
- Download workflow logs
- Classify failures
- Create incidents
- Analyze root cause
- Generate patches
- Apply patches
- Create pull requests
- Verify fixes
- Merge successful remediations

## Component Breakdown
### 1. Log Collection
- Downloads GitHub Actions logs.
- Component: `GitHubClient`
- Operation: `download_workflow_logs(run_id)`

### 2. Failure Classification
- Classifies failures using rule-based patterns.
- Examples:
  - `dependency_failure`
  - `test_failure`
  - `docker_failure`
  - `unknown_failure`
- Output:
```json
{
  "category": "dependency_failure",
  "confidence": 0.9
}
```

### 3. Incident Management
- Stores failure metadata in SQLite.
- Table: `incidents`
- Stored Information:
  - Workflow Run ID
  - Failure Category
  - Status
  - Timestamp

### 4. Repository Context Collection
- Clones repository and collects context.
- Collected Data:
  - Workflow files
  - Project type
  - Requirements file
  - Repository structure
- Purpose: Provide context to the LLM.

### 5. Root Cause Analysis
- Uses Hugging Face LLM.
- Input:
```json
{
  "incident": "...",
  "repository_context": "..."
}
```
- Output:
```json
{
  "root_cause": "...",
  "suggested_fix": "...",
  "confidence": 85
}
```

### 6. Patch Generation
- LLM generates structured patch plans.
- Example:
```json
{
  "patches": [
    {
      "file": "requirements.txt",
      "action": "append",
      "content": "pytest==7.4.0"
    }
  ]
}
```

### 7. Patch Validation
- Validates generated patches before application.
- Checks:
  - Dangerous file modifications
  - Oversized patches
  - Invalid actions
  - Unsupported operations
- Purpose: Prevent unsafe repository changes.

### 8. Patch Application
- Applies validated changes to repository files.
- Component: `PatchApplier`
- Supported Operations:
  - Create
  - Modify
  - Append

### 9. Patch Quality Verification
- Evaluates generated patches.
- Checks:
  - Relevance
  - Safety
  - Consistency
  - Command sanity
- Purpose: Prevent low-quality fixes.

### 10. Git Operations
- Automates repository operations.
- Component: `GitService`
- Operations:
  - Create branch
  - Commit changes
  - Push branch
- Example:
`fix/dependency_failure-28089485578`

### 11. Pull Request Automation
- Creates GitHub pull requests automatically.
- Component: `PullRequestService`
- Generated Information:
  - PR Title
  - PR Description
  - Root Cause
  - Suggested Fix

### 12. Workflow Verification
After PR creation:
- Wait for workflow execution
- Monitor status
- Verify success
Example:
`Workflow Status: success`

### 13. Auto Merge
- If verification succeeds: PR -> Merge
- If verification fails: PR remains open

## Database Design
SQLite is currently used.

### incidents
Stores workflow failures.
- Fields:
  - `id`
  - `run_id`
  - `category`
  - `status`
  - `created_at`

### analyses
Stores LLM analysis.
- Fields:
  - `incident_id`
  - `root_cause`
  - `suggested_fix`
  - `confidence`

## Current Tech Stack
- Backend:
  - Python
  - FastAPI
- CI/CD Integration:
  - GitHub Actions
  - GitHub REST API
- AI Layer:
  - Hugging Face Inference API
- Storage:
  - SQLite
- Architecture:
  - Webhooks
  - Background Workers
  - Event-Driven Processing
- Version Control:
  - Git
  - GitHub Pull Requests

## Future Enhancements
- Knowledge Base
  - Store successful remediations and reuse historical fixes.
- Multi-Repository Support
  - Support multiple repositories through a single agent.
- MCP Integration
  - Future integration with:
    - GitHub MCP
    - Jenkins MCP
    - GitLab MCP
  - For dynamic tool discovery and execution.
- Dashboard
  - Provide analytics:
    - Failure frequency
    - Resolution rate
    - Mean time to remediation
    - Success percentage

## Project Status
Current Version:
Event-driven autonomous CI/CD remediation platform capable of detecting failed GitHub Actions workflows, generating fixes, validating patches, creating pull requests, verifying pipeline execution, and automatically merging successful remediations.
