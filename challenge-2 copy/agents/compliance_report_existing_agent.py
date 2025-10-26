# Copyright (c) Microsoft. All rights reserved.

import os
import asyncio
from typing import Any

from agent_framework import ChatAgent, HostedMCPTool
from agent_framework.azure import AzureAIAgentClient
from azure.identity.aio import AzureCliCredential
from dotenv import load_dotenv
import logging

# Load environment variables
load_dotenv(override=True)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

"""
Compliance Report Agent using existing Azure AI Agent with Hosted MCP

This uses your existing COMPLIANCE_REPORT_AGENT_ID from the portal and adds MCP tools.
"""

# Configuration
azure_ai_project_endpoint = os.environ.get("AI_FOUNDRY_PROJECT_ENDPOINT")
azure_ai_model_deployment_name = os.environ.get("MODEL_DEPLOYMENT_NAME")
mcp_endpoint = os.environ.get("MCP_SERVER_ENDPOINT")
mcp_subscription_key = os.environ.get("APIM_SUBSCRIPTION_KEY")
existing_agent_id = os.environ.get("COMPLIANCE_REPORT_AGENT_ID")


async def run_existing_agent_with_mcp() -> None:
    """Use the existing compliance agent from the portal with MCP tools."""
    async with (
        AzureCliCredential() as credential,
        AzureAIAgentClient(
            async_credential=credential,
            project_endpoint=azure_ai_project_endpoint,
            model_deployment_name=azure_ai_model_deployment_name
        ) as chat_client,
    ):
        # Use ChatAgent with the existing agent ID
        async with ChatAgent(
            chat_client=chat_client,
            assistant_id=existing_agent_id
        ) as agent:
            # Create MCP tool
            mcp_tool = HostedMCPTool(
                name="Fraud Alert Manager MCP",
                url=mcp_endpoint,
                description="Manages fraud alerts and escalations for financial transactions",
                approval_mode="never_require",
                headers={
                    "Ocp-Apim-Subscription-Key": mcp_subscription_key
                } if mcp_subscription_key else {}
            )
            
            # Read transaction summary from file
            with open("risk-analyzer-tx-summary.md", "r") as f:
                content = f.read()

            # Test with the existing agent + MCP tools
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

            print(f"🤖 Using existing agent: {existing_agent_id}")
            print(f"🔧 Adding MCP tools to the conversation")
            print(f"📝 User: Generate compliance report with MCP integration...")
            
            # Run the agent with MCP tools
            result = await agent.run(query, tools=[mcp_tool])
            print(f"\n🎯 {agent.name}: {result}")

            # Test MCP tool usage for retrieving alerts
            query2 = """Please retrieve ALL existing fraud alerts using the Fraud Alert Manager MCP 
            tool to show current compliance status. Use the MCP tool to get alerts."""
            
            print(f"\n📊 User: {query2}")
            result2 = await agent.run(query2, tools=[mcp_tool])
            print(f"📈 {agent.name}: {result2}")


async def main() -> None:
    """Main function."""
    # Validate required environment variables
    if not all([azure_ai_project_endpoint, azure_ai_model_deployment_name, mcp_endpoint, existing_agent_id]):
        missing = [
            var for var, val in [
                ("AI_FOUNDRY_PROJECT_ENDPOINT", azure_ai_project_endpoint),
                ("MODEL_DEPLOYMENT_NAME", azure_ai_model_deployment_name), 
                ("MCP_SERVER_ENDPOINT", mcp_endpoint),
                ("COMPLIANCE_REPORT_AGENT_ID", existing_agent_id)
            ] if not val
        ]
        raise ValueError(f"Missing required environment variables: {', '.join(missing)}")

    print("=== Using Existing Azure AI Agent with MCP Tools ===\n")
    print(f"🆔 Agent ID: {existing_agent_id}")
    print(f"🌐 Portal: {azure_ai_project_endpoint.replace('/api/projects/', '/projects/')}")
    print(f"🔧 MCP Endpoint: {mcp_endpoint}\n")
    
    await run_existing_agent_with_mcp()


if __name__ == "__main__":
    asyncio.run(main())