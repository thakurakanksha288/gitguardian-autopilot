#!/usr/bin/env python3
"""
MIT License - GitGuardian Autopilot
MCP Server: Google Cloud Logging Tool
Provides GitLab Duo Agent Platform with access to Cloud Logging for incident investigation.
"""
import json
import sys
from datetime import datetime, timedelta, timezone
from typing import Any

# MCP protocol implementation
def mcp_response(result: Any) -> str:
    return json.dumps({"result": result})

def mcp_error(message: str) -> str:
    return json.dumps({"error": message})

def query_logs(service_name: str, minutes: int = 30, severity: str = "ERROR") -> dict:
    """
    Query Cloud Logging for errors from a specific service.
    
    Args:
        service_name: The Cloud Run service name to query
        minutes: How many minutes back to look (default: 30)
        severity: Log severity filter (ERROR, WARNING, CRITICAL)
    
    Returns:
        dict with log_entries, error_summary, stack_traces
    """
    try:
        from google.cloud import logging as cloud_logging
        import os
        
        project_id = os.getenv("GCP_PROJECT_ID", "gitguardian-autopilot")
        client = cloud_logging.Client(project=project_id)
        
        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(minutes=minutes)
        
        filter_str = f"""
            resource.type="cloud_run_revision"
            resource.labels.service_name="{service_name}"
            severity>="{severity}"
            timestamp>="{start_time.isoformat()}"
            timestamp<="{end_time.isoformat()}"
        """
        
        entries = list(client.list_entries(
            filter_=filter_str,
            order_by=cloud_logging.DESCENDING,
            max_results=50
        ))
        
        log_entries = []
        stack_traces = []
        
        for entry in entries:
            payload = entry.payload
            if isinstance(payload, dict):
                message = payload.get("message", str(payload))
            else:
                message = str(payload)
            
            log_entries.append({
                "timestamp": entry.timestamp.isoformat() if entry.timestamp else None,
                "severity": entry.severity,
                "message": message,
                "resource": dict(entry.resource.labels) if entry.resource else {}
            })
            
            if "Traceback" in message or "Error" in message:
                stack_traces.append(message)
        
        # Find most common error
        error_types = {}
        for trace in stack_traces:
            lines = trace.split("\n")
            for line in lines:
                if "Error:" in line or "Exception:" in line:
                    error_type = line.strip()
                    error_types[error_type] = error_types.get(error_type, 0) + 1
        
        most_common_error = max(error_types.items(), key=lambda x: x[1])[0] if error_types else "Unknown"
        
        return {
            "log_entries": log_entries[:20],  # Return top 20
            "total_errors": len(entries),
            "stack_traces": stack_traces[:5],  # Return top 5 unique traces
            "most_common_error": most_common_error,
            "time_range": {
                "start": start_time.isoformat(),
                "end": end_time.isoformat()
            }
        }
        
    except ImportError:
        # Fallback for environments without google-cloud-logging
        return {
            "log_entries": [],
            "total_errors": 0,
            "stack_traces": ["google-cloud-logging package not installed"],
            "most_common_error": "Unable to query - missing dependency",
            "time_range": {}
        }
    except Exception as e:
        return {"error": str(e), "log_entries": [], "stack_traces": []}

def get_error_rate(service_name: str, minutes: int = 60) -> dict:
    """
    Get error rate metrics for a service over a time period.
    
    Args:
        service_name: Cloud Run service name
        minutes: Time window in minutes
    
    Returns:
        dict with error_count, total_requests, error_rate_percent
    """
    try:
        from google.cloud import monitoring_v3
        import os
        
        project_id = os.getenv("GCP_PROJECT_ID", "gitguardian-autopilot")
        client = monitoring_v3.MetricServiceClient()
        project_name = f"projects/{project_id}"
        
        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(minutes=minutes)
        
        interval = monitoring_v3.TimeInterval(
            end_time={"seconds": int(end_time.timestamp())},
            start_time={"seconds": int(start_time.timestamp())},
        )
        
        # Query request count by response code
        results = client.list_time_series(
            request={
                "name": project_name,
                "filter": f'metric.type="run.googleapis.com/request_count" AND resource.labels.service_name="{service_name}"',
                "interval": interval,
                "view": monitoring_v3.ListTimeSeriesRequest.TimeSeriesView.FULL,
            }
        )
        
        total_requests = 0
        error_requests = 0
        
        for result in results:
            response_code = result.metric.labels.get("response_code_class", "")
            count = sum(point.value.int64_value for point in result.points)
            total_requests += count
            if response_code in ["5xx", "4xx"]:
                error_requests += count
        
        error_rate = (error_requests / total_requests * 100) if total_requests > 0 else 0
        
        return {
            "service_name": service_name,
            "time_window_minutes": minutes,
            "total_requests": total_requests,
            "error_requests": error_requests,
            "error_rate_percent": round(error_rate, 2)
        }
        
    except Exception as e:
        return {"error": str(e), "error_rate_percent": 0}

# MCP tool definitions
TOOLS = [
    {
        "name": "query_logs",
        "description": "Query Google Cloud Logging for errors and stack traces from a Cloud Run service",
        "parameters": {
            "type": "object",
            "properties": {
                "service_name": {
                    "type": "string",
                    "description": "The Cloud Run service name to query logs for"
                },
                "minutes": {
                    "type": "integer",
                    "description": "How many minutes back to search (default: 30)",
                    "default": 30
                },
                "severity": {
                    "type": "string",
                    "description": "Minimum log severity to include (ERROR, WARNING, CRITICAL)",
                    "default": "ERROR"
                }
            },
            "required": ["service_name"]
        }
    },
    {
        "name": "get_error_rate",
        "description": "Get the error rate percentage for a Cloud Run service",
        "parameters": {
            "type": "object",
            "properties": {
                "service_name": {
                    "type": "string",
                    "description": "The Cloud Run service name"
                },
                "minutes": {
                    "type": "integer",
                    "description": "Time window in minutes (default: 60)",
                    "default": 60
                }
            },
            "required": ["service_name"]
        }
    }
]

def handle_request(request: dict) -> dict:
    """Handle an MCP tool call request."""
    tool_name = request.get("name")
    params = request.get("parameters", {})
    
    if tool_name == "query_logs":
        result = query_logs(
            service_name=params["service_name"],
            minutes=params.get("minutes", 30),
            severity=params.get("severity", "ERROR")
        )
        return {"result": result}
    elif tool_name == "get_error_rate":
        result = get_error_rate(
            service_name=params["service_name"],
            minutes=params.get("minutes", 60)
        )
        return {"result": result}
    elif tool_name == "list_tools":
        return {"tools": TOOLS}
    else:
        return {"error": f"Unknown tool: {tool_name}"}

if __name__ == "__main__":
    # MCP server main loop - reads JSON from stdin, writes JSON to stdout
    for line in sys.stdin:
        try:
            request = json.loads(line.strip())
            response = handle_request(request)
            print(json.dumps(response), flush=True)
        except json.JSONDecodeError as e:
            print(json.dumps({"error": f"Invalid JSON: {e}"}), flush=True)
        except Exception as e:
            print(json.dumps({"error": str(e)}), flush=True)
