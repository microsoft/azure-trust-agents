import asyncio
import os
import importlib.util
from pathlib import Path
from typing import Annotated
from azure.identity.aio import AzureCliCredential
from agent_framework import ChatAgent
from agent_framework.azure import AzureAIAgentClient
from azure.ai.projects.aio import AIProjectClient
from azure.ai.projects.models import ConnectionType
from pydantic import Field
from dotenv import load_dotenv

load_dotenv(override=True)

# Configuration
project_endpoint = os.environ.get("AI_FOUNDRY_PROJECT_ENDPOINT")
model_deployment_name = os.environ.get("MODEL_DEPLOYMENT_NAME")
sc_connection_id = os.environ.get("AZURE_AI_CONNECTION_ID")


async def _get_ai_search_connection_id():
    """Retrieve the Azure AI Search connection ID."""
    async with AzureCliCredential() as credential:
        async with AIProjectClient(
            endpoint=project_endpoint,
            credential=credential
        ) as project_client:
            async for connection in project_client.connections.list():
                if connection.type == ConnectionType.AZURE_AI_SEARCH:
                    return connection.id
    raise ValueError("Azure AI Search connection not found in project")


async def _create_agent():
    """Create the agent instance with Azure AI Search tools."""
    # Get the AI Search connection ID
    ai_search_conn_id = await _get_ai_search_connection_id()

    async with AzureCliCredential() as credential:
        async with AIProjectClient(
            endpoint=project_endpoint,
            credential=credential
        ) as project_client:
            # Create persistent agent with Azure AI Search tools
            created_agent = await project_client.agents.create_agent(
                model=model_deployment_name,
                name="RiskAnalyserAgent",
                instructions="""You are a Risk Analyser Agent evaluating financial transactions for potential fraud.
    Given a normalized transaction and customer profile, your task is to:
    - Apply fraud detection logic using rule-based checks and regulatory compliance data
    - Assign a fraud risk score from 0 to 100
    - Generate human-readable reasoning behind the score (e.g., "Transaction from unusual country", "High amount", "Previous fraud history")

    You have access to the following tools:
    - Azure AI Search: Search regulations and policies for compliance checking and fraud detection rules

    Please also consider these risk factors:
    {
    "high_risk_countries": ["NG", "IR", "RU", "KP"],
    "high_amount_threshold_usd": 10000,
    "suspicious_account_age_days": 30,
    "low_device_trust_threshold": 0.5
    }

    Use the Azure AI Search to look up relevant regulations, compliance rules, and fraud detection patterns that apply to the transaction.

    Output should be:
    - risk_score: integer (0-100)
    - risk_level: [Low, Medium, High]
    - reason: a brief explainable summary with references to relevant regulations or policies found via search""",
                tools=[{"type": "azure_ai_search"}],
                tool_resources={
                    "azure_ai_search": {
                        "indexes": [{
                            "index_connection_id": ai_search_conn_id,
                            "index_name": "regulations-policies",
                            "query_type": "simple"
                        }]
                    }
                }
            )

            agent_id = created_agent.id

    # Create ChatAgent with endpoint-based client (not project_client-based)
    # This way the agent manages its own connection lifecycle
    return ChatAgent(
        name="RiskAnalyserAgent",
        description="Risk analysis agent for evaluating financial transactions for potential fraud using regulatory compliance data",
        chat_client=AzureAIAgentClient(
            project_endpoint=project_endpoint,
            model_deployment_name=model_deployment_name,
            async_credential=AzureCliCredential(),
            agent_id=agent_id
        ),
        store=True
    )


# Create the agent at module load time for DevUI to import
agent = asyncio.run(_create_agent())


def main():
    """Launch the Risk Analyser Agent in DevUI."""
    import logging
    from agent_framework.devui import serve

    # Setup logging
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    logger = logging.getLogger(__name__)

    logger.info("Starting Risk Analyser Agent")
    logger.info("Available at: http://localhost:8091")
    logger.info("Entity ID: agent_RiskAnalyserAgent")

    # Launch server with the agent
    serve(entities=[agent], port=8091, auto_open=True)


if __name__ == "__main__":
    main()
