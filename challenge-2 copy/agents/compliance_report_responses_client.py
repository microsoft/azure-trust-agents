# Copyright (c) Microsoft. All rights reserved.

import os
import asyncio

from agent_framework import ChatAgent, HostedMCPTool
from agent_framework.azure import AzureOpenAIResponsesClient
from azure.identity import AzureCliCredential
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
Compliance Report Agent using OpenAI Responses Client with Hosted MCP

This sample demonstrates integrating the Fraud Alert Manager MCP server with
OpenAI Responses Client for compliance reporting and audit workflows.
Adapted from: https://github.com/microsoft/agent-framework/blob/main/python/samples/getting_started/agents/openai/openai_responses_client_with_hosted_mcp.py
"""

# Configuration
mcp_endpoint = os.environ.get("MCP_SERVER_ENDPOINT")
mcp_subscription_key = os.environ.get("APIM_SUBSCRIPTION_KEY")
azure_openai_endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT")
model_deployment_name = os.environ.get("MODEL_DEPLOYMENT_NAME")


async def generate_compliance_report() -> None:
    """Main function to create compliance reports using OpenAI Responses Client with MCP."""
    async with ChatAgent(
        chat_client=AzureOpenAIResponsesClient(
            credential=AzureCliCredential(),
            endpoint=azure_openai_endpoint,
            deployment_name=model_deployment_name
        ),
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
    ) as agent:
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
        result = await agent.run(query)
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
        result2 = await agent.run(query2)
        print(f"{agent.name}: {result2}\n")

        # Test audit trail documentation
        query3 = """Create detailed audit trail documentation for this transaction analysis including:
        - Compliance verification steps
        - Risk assessment methodology
        - Regulatory checks performed  
        - Documentation requirements met
        - Any alerts or reports generated"""
        
        print(f"User: {query3}")
        result3 = await agent.run(query3)
        print(f"{agent.name}: {result3}\n")


async def main() -> None:
    """Main function to run the compliance report agent."""
    # Validate required environment variables
    if not all([mcp_endpoint, azure_openai_endpoint, model_deployment_name]):
        missing = [
            var for var, val in [
                ("MCP_SERVER_ENDPOINT", mcp_endpoint),
                ("AZURE_OPENAI_ENDPOINT", azure_openai_endpoint), 
                ("MODEL_DEPLOYMENT_NAME", model_deployment_name)
            ] if not val
        ]
        raise ValueError(f"Missing required environment variables: {', '.join(missing)}")

    await generate_compliance_report()


if __name__ == "__main__":
    asyncio.run(main())