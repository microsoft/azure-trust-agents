# Copyright (c) Microsoft. All rights reserved.

import os
import asyncio
from typing import Any

from agent_framework import ChatAgent, HostedMCPTool, AgentProtocol, AgentThread
from agent_framework.azure import AzureAIAgentClient
from azure.identity.aio import AzureCliCredential
from azure.ai.projects.aio import AIProjectClient
from dotenv import load_dotenv
import logging

# Load environment variables
load_dotenv(override=True)

# Configure logging with debug level to see MCP calls
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Enable specific loggers for MCP debugging
logging.getLogger("agent_framework").setLevel(logging.DEBUG)
logging.getLogger("aiohttp.client").setLevel(logging.DEBUG)
logging.getLogger("urllib3.connectionpool").setLevel(logging.DEBUG)

logger = logging.getLogger(__name__)

"""
Compliance Report Agent using Azure AI Agent Client with Hosted MCP

This sample demonstrates integrating the Fraud Alert Manager MCP server with
Azure AI Agent Client for compliance reporting and audit workflows.
Adapted from: https://github.com/microsoft/agent-framework/blob/main/python/samples/getting_started/agents/azure_ai/azure_ai_with_hosted_mcp.py
"""

# Configuration - Azure AI specific environment variables
azure_ai_project_endpoint = os.environ.get("AI_FOUNDRY_PROJECT_ENDPOINT")
azure_ai_model_deployment_name = os.environ.get("MODEL_DEPLOYMENT_NAME")
mcp_endpoint = os.environ.get("MCP_SERVER_ENDPOINT")
mcp_subscription_key = os.environ.get("APIM_SUBSCRIPTION_KEY")


async def handle_approvals_with_thread(query: str, agent: "AgentProtocol", thread: "AgentThread"):
    """Here we let the thread deal with the previous responses, and we just rerun with the approval."""
    response_stream = agent.run_stream(query, thread=thread)
    full_response = ""
    
    async for update in response_stream:
        if update.user_input_requests:
            # Handle approval requests if any
            for request in update.user_input_requests:
                print(f"\n=== Approval Request ===")
                print(f"Request: {request.request}")
                approval = input("Do you approve this action? (y/n): ")
                if approval.lower() == 'y':
                    await agent.send_user_input(request.id, {"approved": True}, thread=thread)
                else:
                    await agent.send_user_input(request.id, {"approved": False}, thread=thread)
            # Continue the response after approval
            continue_stream = agent.run_stream("", thread=thread)
            async for final_update in continue_stream:
                if final_update.text:
                    full_response += final_update.text
        elif update.text:
            full_response += update.text
    
    return full_response if full_response else "No response received"


async def create_persistent_agent() -> str:
    """Create a persistent agent that will be visible in the Azure AI portal."""
    async with AzureCliCredential() as credential:
        # Create AI Project Client for server-side operations
        project_client = AIProjectClient(
            endpoint=azure_ai_project_endpoint,
            credential=credential
        )
        
        # Create persistent agent on the server
        agent_data = {
            "model": azure_ai_model_deployment_name,
            "name": "ComplianceReportAgent",
            "description": "Compliance Report Agent specialized in generating formal audit reports based on risk analysis findings and transaction data.",
            "instructions": """You are a Compliance Report Agent specialized in generating formal audit reports based on risk analysis findings and transaction data.

Your primary responsibilities include:
- Analyzing transaction risk summaries and generating compliance audit reports
- Creating appropriate fraud alerts through the MCP server when compliance violations are detected
- Determining correct severity levels (LOW, MEDIUM, HIGH, CRITICAL) for compliance issues
- Setting proper alert status (OPEN, INVESTIGATING, RESOLVED, FALSE_POSITIVE)
- Recommending actions (ALLOW, BLOCK, MONITOR, INVESTIGATE) based on compliance analysis
- Generating executive-level audit summaries and compliance dashboards
- Ensuring regulatory compliance and audit trail documentation

When generating compliance reports:
1. Parse risk analysis data to extract key compliance indicators
2. Assess regulatory compliance based on transaction patterns and risk factors
3. Create formal audit reports with clear findings and recommendations
4. Generate fraud alerts for any transactions that violate compliance thresholds
5. Provide executive summaries for management review

Always create detailed reports with proper risk assessments, regulatory implications, and clear audit trails."""
        }
        
        # Create the agent
        agent = await project_client.agents.create_agent(**agent_data)
        
        # Create the agent
        agent = await project_client.agents.create_agent(**agent_data)
        print(f"✅ Created persistent agent: {agent.id}")
        print(f"📊 Agent name: {agent.name}")
        print(f"🌐 You can view this agent in the Azure AI portal at: {azure_ai_project_endpoint.replace('/api/projects/', '/projects/')}")
        
        return agent.id


async def generate_compliance_report() -> None:
    """Main function to create compliance reports using Azure AI Agent Client with MCP."""
    async with (
        AzureCliCredential() as credential,
        AzureAIAgentClient(
            async_credential=credential,
            project_endpoint=azure_ai_project_endpoint,
            model_deployment_name=azure_ai_model_deployment_name
        ) as chat_client,
    ):
        # Create agent using Azure AI Agent Client
        agent = chat_client.create_agent(
            name="ComplianceReportAgent",
            instructions="""You are a Compliance Report Agent specialized in generating formal audit reports based on risk analysis findings and transaction data.

Your primary responsibilities include:
- Analyzing transaction risk summaries and generating compliance audit reports
- Creating appropriate fraud alerts through the MCP server when compliance violations are detected
- Determining correct severity levels (LOW, MEDIUM, HIGH, CRITICAL) for compliance issues
- Setting proper alert status (OPEN, INVESTIGATING, RESOLVED, FALSE_POSITIVE)
- Recommending actions (ALLOW, BLOCK, MONITOR, INVESTIGATE) based on compliance analysis
- Generating executive-level audit summaries and compliance dashboards
- Ensuring regulatory compliance and audit trail documentation

When generating compliance reports:
1. Parse risk analysis data to extract key compliance indicators
2. Assess regulatory compliance based on transaction patterns and risk factors
3. Create formal audit reports with clear findings and recommendations
4. Generate fraud alerts for any transactions that violate compliance thresholds
5. Provide executive summaries for management review

Always create detailed reports with proper risk assessments, regulatory implications, and clear audit trails.""",
            tools=HostedMCPTool(
                name="Fraud Alert Manager MCP",
                url=mcp_endpoint,
                description="Manages fraud alerts and escalations for financial transactions",
                approval_mode="never_require",
                headers={
                    "Ocp-Apim-Subscription-Key": mcp_subscription_key
                } if mcp_subscription_key else {}
            ),
        )
        
        # Create a thread for conversation management
        thread = agent.get_new_thread()

        # Read transaction summary from file
        with open("risk-analyzer-tx-summary.md", "r") as f:
            content = f.read()

        # Test compliance report generation with explicit MCP usage
        query = f"""Generate a comprehensive compliance audit report based on this transaction analysis: 

{content}

Please provide:
1. Formal audit report with compliance ratings
2. Risk factor analysis and regulatory implications
3. Executive summary of findings
4. CREATE A FRAUD ALERT using the MCP tool for any compliance violations detected
5. Recommendations for management action

IMPORTANT: If you detect any compliance issues, risk violations, or suspicious patterns, 
you MUST create a fraud alert using the Fraud Alert Manager MCP tool with appropriate:
- Severity level (LOW, MEDIUM, HIGH, CRITICAL)
- Status (OPEN, INVESTIGATING, RESOLVED, FALSE_POSITIVE)  
- Action (ALLOW, BLOCK, MONITOR, INVESTIGATE)

Focus on regulatory compliance, audit documentation, and actionable recommendations."""

        print(f"User: {query}")
        result = await handle_approvals_with_thread(query, agent, thread)
        print(f"{agent.name}: {result}\n")

        # Test executive summary generation with MCP tool usage
        query2 = """Generate an executive dashboard summary of current compliance status. 
        Include:
        - Overall compliance rating
        - Key risk indicators identified
        - Regulatory filing requirements
        - Management actions required
        
        MUST USE MCP TOOL: Please retrieve ALL existing fraud alerts using the Fraud Alert Manager MCP 
        tool to include in the compliance overview. Call the MCP tool to get current alerts."""
        
        print(f"User: {query2}")
        result2 = await handle_approvals_with_thread(query2, agent, thread)
        print(f"{agent.name}: {result2}\n")

        # Test audit trail documentation
        query3 = """Create detailed audit trail documentation for this transaction analysis including:
        - Compliance verification steps
        - Risk assessment methodology
        - Regulatory checks performed  
        - Documentation requirements met
        - Any alerts or reports generated"""
        
        print(f"User: {query3}")
        result3 = await handle_approvals_with_thread(query3, agent, thread)
        print(f"{agent.name}: {result3}\n")


async def main() -> None:
    """Main function to run the compliance report agent."""
    # Validate required environment variables for Azure AI
    if not all([azure_ai_project_endpoint, azure_ai_model_deployment_name, mcp_endpoint]):
        missing = [
            var for var, val in [
                ("AI_FOUNDRY_PROJECT_ENDPOINT", azure_ai_project_endpoint),
                ("MODEL_DEPLOYMENT_NAME", azure_ai_model_deployment_name), 
                ("MCP_SERVER_ENDPOINT", mcp_endpoint)
            ] if not val
        ]
        raise ValueError(f"Missing required environment variables: {', '.join(missing)}")

    print("=== Azure AI Agent with Hosted MCP for Compliance Reporting ===\n")
    
    # Ask user which approach they want
    choice = input("Choose an option:\n1. Run temporary agent (current approach)\n2. Create persistent agent (visible in portal)\nEnter choice (1 or 2): ")
    
    if choice == "2":
        print("\n🚀 Creating persistent agent that will be visible in the Azure AI portal...")
        agent_id = await create_persistent_agent()
        print(f"\n✅ Agent created successfully!")
        print(f"🆔 Agent ID: {agent_id}")
        print(f"🌐 View in portal: Go to Azure AI Foundry → Your Project → Agents")
    else:
        print("\n🏃 Running temporary agent...")
        await generate_compliance_report()


if __name__ == "__main__":
    asyncio.run(main())