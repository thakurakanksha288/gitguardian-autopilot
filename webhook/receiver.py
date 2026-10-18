#!/usr/bin/env python3
"""
MIT License - GitGuardian Autopilot
Webhook Receiver for Google Cloud Monitoring Alerts
This Cloud Run service receives alerts from Cloud Monitoring
and triggers the Self-Healing Agent flow in GitLab.
"""
import os
import json
import hmac
import hashlib
import logging
import requests
from datetime import datetime
from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
import uvicorn

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="GitGuardian Alert Webhook Receiver", version="1.0.0")

# Configuration
GITLAB_URL = os.getenv("GITLAB_URL", "https://gitlab.com")
GITLAB_TOKEN = os.getenv("GITLAB_TOKEN", "")
GITLAB_PROJECT_ID = os.getenv("GITLAB_PROJECT_ID", "")
SELF_HEALING_AGENT_ID = os.getenv("SELF_HEALING_AGENT_ID", "")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")

def trigger_gitlab_agent(alert_payload: dict) -> bool:
    """
    Trigger the GitLab Duo self-healing agent with the alert context.
    """
    incident_id = f"INC-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
    
    # Format the alert for the agent
    agent_input = {
        "incident_id": incident_id,
        "alert_name": alert_payload.get("incident", {}).get("policy_name", "Unknown Alert"),
        "severity": alert_payload.get("incident", {}).get("severity", "CRITICAL"),
        "service_name": alert_payload.get("incident", {}).get("resource", {}).get("labels", {}).get("service_name", "task-manager"),
        "condition_name": alert_payload.get("incident", {}).get("condition_name", ""),
        "started_at": alert_payload.get("incident", {}).get("started_at", ""),
        "url": alert_payload.get("incident", {}).get("url", ""),
        "raw_payload": alert_payload
    }
    
    logger.info(f"Triggering self-healing agent for incident: {incident_id}")
    
    # Trigger GitLab Duo Agent via API
    headers = {
        "PRIVATE-TOKEN": GITLAB_TOKEN,
        "Content-Type": "application/json"
    }
    
    # Create a GitLab issue to trigger the agent flow
    issue_data = {
        "title": f"[AUTO-INCIDENT] {agent_input['alert_name']} - {incident_id}",
        "description": f"""
## 🚨 Automatic Incident Response Triggered

**Incident ID:** {incident_id}  
**Alert:** {agent_input['alert_name']}  
**Severity:** {agent_input['severity']}  
**Service:** {agent_input['service_name']}  
**Detected At:** {agent_input['started_at']}  

---
**The GitGuardian Autopilot self-healing agent has been triggered.**  
Monitor this issue for automated updates.

<details>
<summary>Raw Alert Payload</summary>

```json
{json.dumps(alert_payload, indent=2)}
```
</details>
""",
        "labels": "incident,auto-healing,priority::high",
        "assignee_ids": []
    }
    
    response = requests.post(
        f"{GITLAB_URL}/api/v4/projects/{GITLAB_PROJECT_ID}/issues",
        headers=headers,
        json=issue_data,
        timeout=10
    )
    
    if response.status_code == 201:
        issue = response.json()
        logger.info(f"Created incident issue #{issue['iid']}")
        return True
    else:
        logger.error(f"Failed to create issue: {response.status_code} {response.text}")
        return False

@app.get("/health")
def health():
    return {"status": "healthy", "service": "webhook-receiver"}

@app.post("/webhook/cloud-monitoring")
async def receive_alert(request: Request, background_tasks: BackgroundTasks):
    """
    Receive Google Cloud Monitoring alerts and trigger self-healing.
    """
    body = await request.body()
    
    # Verify webhook signature if secret is set
    if WEBHOOK_SECRET:
        signature = request.headers.get("X-Goog-Signature", "")
        expected = hmac.new(
            WEBHOOK_SECRET.encode(),
            body,
            hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(signature, expected):
            raise HTTPException(status_code=401, detail="Invalid signature")
    
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")
    
    logger.info(f"Received alert: {payload.get('incident', {}).get('policy_name', 'Unknown')}")
    
    # Trigger healing in background
    background_tasks.add_task(trigger_gitlab_agent, payload)
    
    return JSONResponse(
        status_code=200,
        content={
            "status": "accepted",
            "message": "Alert received, self-healing agent triggered"
        }
    )

@app.post("/webhook/gitlab")
async def receive_gitlab_webhook(request: Request):
    """
    Receive GitLab webhooks (for MR events, issue events, etc.)
    to trigger the Maintainer Autopilot.
    """
    body = await request.body()
    event_type = request.headers.get("X-Gitlab-Event", "")
    
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")
    
    logger.info(f"Received GitLab event: {event_type}")
    
    return JSONResponse(status_code=200, content={"status": "received", "event": event_type})

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8081))
    uvicorn.run("receiver:app", host="0.0.0.0", port=port, reload=False)
