# Import necessary libraries

import asyncio
import os
from pathlib import Path

from agent_framework import Agent
from agent_framework.foundry import FoundryChatClient
from azure.identity.aio import AzureCliCredential
from dotenv import load_dotenv

load_dotenv(override=True)

project_endpoint = os.environ.get("AI_FOUNDRY_PROJECT_ENDPOINT")
model_deployment_name = os.environ.get("MODEL_DEPLOYMENT_NAME")
mcp_endpoint = os.environ.get("MCP_SERVER_ENDPOINT")
mcp_subscription_key = os.environ.get("APIM_SUBSCRIPTION_KEY")

# Resolve the transaction summary next to this script rather than the caller's cwd
TX_SUMMARY_PATH = Path(__file__).resolve().parent.parent / "risk-analyzer-tx-summary.md"

INSTRUCTIONS = """
You are a Fraud Alert Management Agent that specializes in creating and managing fraud alerts for financial transactions.

Your responsibilities include:
- Analyzing risk assessment results to determine if fraud alerts are needed
- Creating appropriate fraud alerts using the MCP tool with correct severity and status
- Determining proper decision actions (ALLOW, BLOCK, MONITOR, INVESTIGATE)
- Providing clear reasoning for alert decisions

When creating fraud alerts, use these enumerations:
- severity (LOW, MEDIUM, HIGH, CRITICAL)
- status (OPEN, INVESTIGATING, RESOLVED, FALSE_POSITIVE)
- decision action (ALLOW, BLOCK, MONITOR, INVESTIGATE)

Create fraud alerts for transactions that meet any of these criteria:
1. High risk scores (>= 75)
2. Sanctions-related concerns
3. High-risk jurisdictions
4. Suspicious patterns or anomalies
5. Regulatory compliance violations

Always create comprehensive alerts with proper risk factor documentation and clear reasoning.
Send alerts using the MCP tool without asking for further confirmation.
"""


def _validate_config() -> None:
    missing = [
        name
        for name, value in (
            ("AI_FOUNDRY_PROJECT_ENDPOINT", project_endpoint),
            ("MODEL_DEPLOYMENT_NAME", model_deployment_name),
            ("MCP_SERVER_ENDPOINT", mcp_endpoint),
            ("APIM_SUBSCRIPTION_KEY", mcp_subscription_key),
        )
        if not value
    ]
    if missing:
        raise ValueError(f"Missing required environment variables: {', '.join(missing)}")


async def main():
    _validate_config()

    async with AzureCliCredential() as credential:
        chat_client = FoundryChatClient(
            project_endpoint=project_endpoint,
            model=model_deployment_name,
            credential=credential,
        )

        # TODO (Challenge 2): initialize the hosted MCP tool and assign it to `mcp_tool`.
        # Hint: chat_client.get_mcp_tool(name=..., url=..., headers={...}, approval_mode="never_require")
        mcp_tool = None

        if mcp_tool is None:
            raise NotImplementedError(
                "Challenge 2: create the MCP tool with chat_client.get_mcp_tool(...) — see the hint above."
            )

        agent = Agent(
            chat_client,
            name="fraud-alert-agent",
            instructions=INSTRUCTIONS,
            tools=[mcp_tool],
        )

        print(f"MCP Server at {mcp_endpoint}")

        content = TX_SUMMARY_PATH.read_text(encoding="utf-8")
        result = await agent.run(
            f"Please send a fraud alert from this transaction summary: {content}"
        )

        print("\nConversation:")
        print("-" * 50)
        print(result.text)
        print("-" * 50)

        return result


if __name__ == "__main__":
    asyncio.run(main())
