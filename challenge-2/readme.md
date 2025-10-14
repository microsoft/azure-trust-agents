# Challenge 2: MCP Server Integration and Container Apps Deployment

**Expected Duration:** 60 minutes

This challenge focuses on two key integration points to enhance your fraud detection system with modern connectivity and deployment patterns.

## Part 1 - Connect to your Alert MCP Server

### Step-by-Step: Connecting to Alert MCP

Now that your fraud detection API is deployed on Azure Container Apps, you can integrate it with the **Model Context Protocol (MCP)** to create a more sophisticated alerting and monitoring system.

#### What is MCP?
The Model Context Protocol enables seamless integration between your fraud detection system and external tools, allowing for:
- **Real-time alerts**: Immediate notifications when fraud patterns are detected
- **Context sharing**: Rich information exchange between systems
- **Tool orchestration**: Coordinated responses across multiple platforms

#### Implementation Steps

**Step 1: Configure Alert MCP Connection**
```python
# Add to your orchestration.py
import json
from mcp_client import MCPClient

class AlertMCPConnector:
    def __init__(self, mcp_endpoint):
        self.client = MCPClient(mcp_endpoint)
        
    async def send_fraud_alert(self, analysis_result):
        alert_payload = {
            "alert_type": "fraud_detection",
            "severity": analysis_result.get("risk_level", "MEDIUM"),
            "customer_id": analysis_result.get("customer_id"),
            "transaction_id": analysis_result.get("transaction_id"),
            "fraud_score": analysis_result.get("fraud_score"),
            "reasoning": analysis_result.get("final_decision", {}).get("reasoning"),
            "timestamp": analysis_result.get("timestamp")
        }
        
        return await self.client.send_notification(alert_payload)
```

**Step 2: Integrate with Existing Orchestrator**
```python
# In your main orchestration function
async def enhanced_fraud_analysis(transaction_id, customer_id):
    # Your existing analysis code...
    analysis_result = await orchestrate_fraud_analysis(transaction_id, customer_id)
    
    # Add MCP Alert integration
    if analysis_result["final_decision"]["risk_level"] in ["HIGH", "CRITICAL"]:
        alert_connector = AlertMCPConnector(os.getenv("ALERT_MCP_ENDPOINT"))
        await alert_connector.send_fraud_alert(analysis_result)
    
    return analysis_result
```

**Step 3: Environment Configuration**
Add to your `.env` file:
```env
ALERT_MCP_ENDPOINT=https://your-alert-mcp-server.com/api/v1
MCP_API_KEY=your_mcp_api_key
```

## Part 2 - Container App + OpenAPI + MCP Server Exposure

### Transforming Your API into an MCP Server

This section shows how to expose your Azure Container Apps deployment as a full-featured MCP server with OpenAPI documentation.

#### MCP Server Architecture

**Enhanced API Structure:**
```
Container App Deployment
├── Fraud Detection API (existing)
├── OpenAPI Specification 
├── MCP Server Interface
└── GitHub Copilot Integration
```

#### Implementation Guide

**Step 1: Add OpenAPI Specification**
Create `openapi_spec.py`:
```python
from fastapi import FastAPI
from pydantic import BaseModel
from typing import Optional, Dict, Any

app = FastAPI(
    title="Fraud Detection MCP Server",
    description="Intelligent fraud detection with persistent memory and MCP integration",
    version="2.0.0"
)

class FraudAnalysisRequest(BaseModel):
    transaction_id: str
    customer_id: str
    context: Optional[Dict[str, Any]] = None

class MCPAlert(BaseModel):
    alert_type: str
    severity: str
    payload: Dict[str, Any]
    destination: Optional[str] = None

@app.post("/mcp/analyze", tags=["MCP Operations"])
async def mcp_fraud_analysis(request: FraudAnalysisRequest):
    """
    Enhanced fraud analysis with MCP context and alerting
    """
    # Your enhanced analysis logic here
    pass

@app.post("/mcp/alert", tags=["MCP Operations"])
async def send_mcp_alert(alert: MCPAlert):
    """
    Send alerts through MCP protocol
    """
    # Alert logic here
    pass
```

**Step 2: MCP Server Implementation**
Create `mcp_server.py`:
```python
import asyncio
from mcp import Server, types
from orchestration import enhanced_fraud_analysis

server = Server("fraud-detection-mcp")

@server.call_tool()
async def analyze_fraud(transaction_id: str, customer_id: str) -> types.TextContent:
    """Analyze transaction for fraud using persistent memory"""
    result = await enhanced_fraud_analysis(transaction_id, customer_id)
    
    return types.TextContent(
        type="text",
        text=f"Fraud Analysis Complete:\n"
             f"Risk Level: {result['final_decision']['risk_level']}\n"
             f"Fraud Score: {result.get('fraud_score', 'N/A')}\n"
             f"Reasoning: {result['final_decision']['reasoning']}"
    )

@server.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="analyze_fraud",
            description="Analyze transactions for fraud with memory-enhanced detection",
            inputSchema={
                "type": "object",
                "properties": {
                    "transaction_id": {"type": "string"},
                    "customer_id": {"type": "string"}
                },
                "required": ["transaction_id", "customer_id"]
            }
        )
    ]
```

**Step 3: Docker Configuration Update**
Update your `Dockerfile`:
```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Copy requirements
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copy application files
COPY . .

# Expose ports for both API and MCP server
EXPOSE 8000 8080

# Start both services
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"] & \
    ["python", "mcp_server.py", "--port", "8080"]
```

### GitHub Copilot Integration Hints

#### Where to Add MCP Server in Your Orchestration

**🎯 Integration Points in `orchestration.py`:**

1. **At the top of your file** (imports section):
```python
# Add these imports for MCP integration
from mcp_server import server as mcp_server
from alert_mcp_connector import AlertMCPConnector
```

2. **In your main orchestration function** (after analysis completion):
```python
async def orchestrate_fraud_analysis(transaction_id: str, customer_id: str):
    # ... existing orchestration logic ...
    
    # 🚀 ADD MCP INTEGRATION HERE
    # Send results through MCP if high-risk detected
    if final_result["risk_level"] in ["HIGH", "CRITICAL"]:
        await notify_mcp_subscribers(final_result)
    
    return final_result
```

3. **Before the main execution block** (new function):
```python
# 🎯 ADD THIS FUNCTION FOR MCP NOTIFICATIONS
async def notify_mcp_subscribers(analysis_result):
    """Send fraud analysis results to MCP subscribers"""
    mcp_payload = {
        "type": "fraud_alert",
        "data": analysis_result,
        "timestamp": datetime.utcnow().isoformat()
    }
    # Broadcast to MCP clients
    await mcp_server.broadcast_notification(mcp_payload)
```

#### GitHub Copilot Enhancement Tips

**💡 Copilot-Friendly Code Structure:**
```python
# Use clear, descriptive function names for better Copilot suggestions
async def generate_fraud_alert_for_mcp(analysis_result: Dict) -> Dict:
    """
    Generate MCP-compatible fraud alert from analysis result
    GitHub Copilot will understand this pattern and suggest relevant code
    """
    # Copilot will suggest alert structure based on function name and docstring
    pass

# Add type hints for better Copilot understanding
def integrate_with_github_copilot_workspace(
    mcp_endpoint: str, 
    analysis_context: Dict[str, Any]
) -> None:
    """
    Integration point for GitHub Copilot workspace features
    This function name helps Copilot understand the integration intent
    """
    pass
```

**🔧 Suggested File Structure for Copilot:**
```
challenge-2/
├── orchestration.py           # Main orchestration (add MCP calls here)
├── mcp_server.py             # New: MCP server implementation  
├── alert_connector.py        # New: Alert MCP integration
├── copilot_integration.py    # New: GitHub Copilot specific features
└── requirements.txt          # Update with MCP dependencies
```

**🎯 Key Integration Points:**
- **Line ~85** in `orchestration.py`: After `final_result` is created
- **Line ~12** in `orchestration.py`: Import section for MCP modules
- **New file**: `mcp_server.py` for MCP protocol implementation
- **Container Apps**: Environment variables for MCP endpoints

This setup transforms your fraud detection system into a comprehensive MCP-enabled service that integrates seamlessly with GitHub Copilot's workspace features and external alerting systems.

````
