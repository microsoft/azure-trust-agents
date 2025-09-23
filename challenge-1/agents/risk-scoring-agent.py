import asyncio
import os
from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient
from azure.ai.agents.models import AzureAISearchQueryType, AzureAISearchTool
from dotenv import load_dotenv

load_dotenv(override=True)

# Configuration
project_endpoint = os.environ.get("AI_FOUNDRY_PROJECT_ENDPOINT")
model_deployment_name = os.environ.get("MODEL_DEPLOYMENT_NAME")
sc_connection_id = os.environ.get("AZURE_AI_CONNECTION_ID")

project_client = AIProjectClient(
    endpoint=project_endpoint,
    credential=DefaultAzureCredential(exclude_interactive_browser_credential=False)
)

async def main():
    with project_client:
        # Create agent
        scoring_agent = project_client.agents.create_agent(
            model=model_deployment_name,
            name="scoring-agent",
            instructions="""You are the Scoring Agent. 
            Your task is to analyze transactions in real time against the compliance rules provided by the Regulation Agent. 
            You read:
            - "Transactions" container for transaction data,
            - "Rules" container for active obligations.

            For each transaction:
            1. Compare fields against each rule.
            2. If violation occurs, create an Alert in JSON format for the "Alerts" container with:
            - id,
            - txn_id,
            - account_id,
            - risk_score (0–1),
            - triggered_rules (list of rule IDs),
            - features (velocity, geo_mismatch, unusual_behavior),
            - status ("open"),
            - created_at timestamp.
            3. If no violation, ignore the transaction.

            Your output must be strict JSON with no extra commentary.
            """
        )
        print(f"Created scoring agent with ID: {scoring_agent.id}")
        print(f"Agent name: {scoring_agent.name}")
        return scoring_agent

if __name__ == "__main__":
    asyncio.run(main())

