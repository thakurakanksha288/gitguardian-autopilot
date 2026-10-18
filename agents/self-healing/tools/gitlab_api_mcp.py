#!/usr/bin/env python3
"""
MIT License - GitGuardian Autopilot
MCP Server: GitLab API Tool
Provides GitLab Duo Agent Platform with full GitLab API access.
"""
import json
import sys
import os
import requests
from datetime import datetime
from typing import Any, Optional

GITLAB_URL = os.getenv("GITLAB_URL", "https://gitlab.com")
GITLAB_TOKEN = os.getenv("GITLAB_TOKEN", "")
GITLAB_PROJECT_ID = os.getenv("GITLAB_PROJECT_ID", "")

def gitlab_request(method: str, endpoint: str, data: dict = None, params: dict = None) -> dict:
    """Make an authenticated request to the GitLab API."""
    headers = {
        "PRIVATE-TOKEN": GITLAB_TOKEN,
        "Content-Type": "application/json"
    }
    url = f"{GITLAB_URL}/api/v4{endpoint}"
    
    response = requests.request(
        method=method,
        url=url,
        headers=headers,
        json=data,
        params=params,
        timeout=30
    )
    
    if response.status_code >= 400:
        return {"error": f"GitLab API error {response.status_code}: {response.text}"}
    
    return response.json() if response.content else {"success": True}

def create_issue(title: str, description: str, labels: list = None) -> dict:
    """Create a new GitLab issue."""
    data = {
        "title": title,
        "description": description,
        "labels": ",".join(labels) if labels else ""
    }
    return gitlab_request("POST", f"/projects/{GITLAB_PROJECT_ID}/issues", data=data)

def get_recent_commits(limit: int = 10) -> list:
    """Get recent commits on the default branch."""
    return gitlab_request(
        "GET",
        f"/projects/{GITLAB_PROJECT_ID}/repository/commits",
        params={"per_page": limit, "ref_name": "main"}
    )

def get_commit_diff(commit_sha: str) -> dict:
    """Get the diff for a specific commit."""
    return gitlab_request("GET", f"/projects/{GITLAB_PROJECT_ID}/repository/commits/{commit_sha}/diff")

def create_branch(branch_name: str, ref: str = "main") -> dict:
    """Create a new branch."""
    data = {"branch": branch_name, "ref": ref}
    return gitlab_request("POST", f"/projects/{GITLAB_PROJECT_ID}/repository/branches", data=data)

def commit_file(branch: str, file_path: str, content: str, commit_message: str, action: str = "update") -> dict:
    """Commit a file change to a branch."""
    import base64
    data = {
        "branch": branch,
        "commit_message": commit_message,
        "actions": [{
            "action": action,
            "file_path": file_path,
            "content": content
        }]
    }
    return gitlab_request("POST", f"/projects/{GITLAB_PROJECT_ID}/repository/commits", data=data)

def create_merge_request(title: str, description: str, source_branch: str,
                          target_branch: str = "main", labels: list = None,
                          merge_when_pipeline_succeeds: bool = True) -> dict:
    """Create a new Merge Request."""
    data = {
        "title": title,
        "description": description,
        "source_branch": source_branch,
        "target_branch": target_branch,
        "labels": ",".join(labels) if labels else "",
        "merge_when_pipeline_succeeds": merge_when_pipeline_succeeds,
        "remove_source_branch": True
    }
    return gitlab_request("POST", f"/projects/{GITLAB_PROJECT_ID}/merge_requests", data=data)

def get_pipeline_status(pipeline_id: int) -> dict:
    """Get the status of a CI/CD pipeline."""
    return gitlab_request("GET", f"/projects/{GITLAB_PROJECT_ID}/pipelines/{pipeline_id}")

def post_issue_comment(issue_iid: int, comment: str) -> dict:
    """Post a comment on an issue."""
    data = {"body": comment}
    return gitlab_request("POST", f"/projects/{GITLAB_PROJECT_ID}/issues/{issue_iid}/notes", data=data)

def close_issue(issue_iid: int) -> dict:
    """Close an issue."""
    return gitlab_request("PUT", f"/projects/{GITLAB_PROJECT_ID}/issues/{issue_iid}",
                          data={"state_event": "close"})

def get_open_issues(labels: str = None, limit: int = 20) -> list:
    """Get open issues, optionally filtered by labels."""
    params = {"state": "opened", "per_page": limit}
    if labels:
        params["labels"] = labels
    return gitlab_request("GET", f"/projects/{GITLAB_PROJECT_ID}/issues", params=params)

def get_open_mrs(limit: int = 10) -> list:
    """Get open Merge Requests."""
    return gitlab_request(
        "GET",
        f"/projects/{GITLAB_PROJECT_ID}/merge_requests",
        params={"state": "opened", "per_page": limit}
    )

TOOLS = [
    {"name": "create_issue", "description": "Create a GitLab issue with title, description, and labels",
     "parameters": {"type": "object", "properties": {
         "title": {"type": "string"}, "description": {"type": "string"},
         "labels": {"type": "array", "items": {"type": "string"}}},
         "required": ["title", "description"]}},
    {"name": "get_recent_commits", "description": "Get recent commits from the main branch",
     "parameters": {"type": "object", "properties": {
         "limit": {"type": "integer", "default": 10}}}},
    {"name": "get_commit_diff", "description": "Get the diff of a specific commit",
     "parameters": {"type": "object", "properties": {
         "commit_sha": {"type": "string"}}, "required": ["commit_sha"]}},
    {"name": "create_branch", "description": "Create a new git branch",
     "parameters": {"type": "object", "properties": {
         "branch_name": {"type": "string"}, "ref": {"type": "string", "default": "main"}},
         "required": ["branch_name"]}},
    {"name": "commit_file", "description": "Commit a file change to a branch",
     "parameters": {"type": "object", "properties": {
         "branch": {"type": "string"}, "file_path": {"type": "string"},
         "content": {"type": "string"}, "commit_message": {"type": "string"},
         "action": {"type": "string", "enum": ["create", "update", "delete"], "default": "update"}},
         "required": ["branch", "file_path", "content", "commit_message"]}},
    {"name": "create_merge_request", "description": "Create a GitLab Merge Request",
     "parameters": {"type": "object", "properties": {
         "title": {"type": "string"}, "description": {"type": "string"},
         "source_branch": {"type": "string"}, "target_branch": {"type": "string", "default": "main"},
         "labels": {"type": "array", "items": {"type": "string"}},
         "merge_when_pipeline_succeeds": {"type": "boolean", "default": True}},
         "required": ["title", "description", "source_branch"]}},
    {"name": "get_pipeline_status", "description": "Get CI/CD pipeline status",
     "parameters": {"type": "object", "properties": {
         "pipeline_id": {"type": "integer"}}, "required": ["pipeline_id"]}},
    {"name": "post_issue_comment", "description": "Post a comment on a GitLab issue",
     "parameters": {"type": "object", "properties": {
         "issue_iid": {"type": "integer"}, "comment": {"type": "string"}},
         "required": ["issue_iid", "comment"]}},
    {"name": "close_issue", "description": "Close a GitLab issue",
     "parameters": {"type": "object", "properties": {
         "issue_iid": {"type": "integer"}}, "required": ["issue_iid"]}},
    {"name": "get_open_issues", "description": "Get all open issues, optionally filtered by labels",
     "parameters": {"type": "object", "properties": {
         "labels": {"type": "string"}, "limit": {"type": "integer", "default": 20}}}},
    {"name": "get_open_mrs", "description": "Get all open Merge Requests",
     "parameters": {"type": "object", "properties": {
         "limit": {"type": "integer", "default": 10}}}},
]

FUNC_MAP = {
    "create_issue": create_issue,
    "get_recent_commits": get_recent_commits,
    "get_commit_diff": get_commit_diff,
    "create_branch": create_branch,
    "commit_file": commit_file,
    "create_merge_request": create_merge_request,
    "get_pipeline_status": get_pipeline_status,
    "post_issue_comment": post_issue_comment,
    "close_issue": close_issue,
    "get_open_issues": get_open_issues,
    "get_open_mrs": get_open_mrs,
}

def handle_request(request: dict) -> dict:
    tool_name = request.get("name")
    params = request.get("parameters", {})
    
    if tool_name == "list_tools":
        return {"tools": TOOLS}
    
    func = FUNC_MAP.get(tool_name)
    if not func:
        return {"error": f"Unknown tool: {tool_name}"}
    
    try:
        result = func(**params)
        return {"result": result}
    except Exception as e:
        return {"error": str(e)}

if __name__ == "__main__":
    for line in sys.stdin:
        try:
            request = json.loads(line.strip())
            response = handle_request(request)
            print(json.dumps(response), flush=True)
        except Exception as e:
            print(json.dumps({"error": str(e)}), flush=True)
