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
        audit_agent = project_client.agents.create_agent(
            model=model_deployment_name,
            name="audit-agent",
            instructions="""You are the Audit Agent. 
            Your task is to create compliance audit reports for alerts. 
            You read:
            - "Alerts" container for open cases,
            - "Rules" container for the rules triggered,
            - "Case Explanations" index for precedent justifications.

            For each Alert:
            1. Retrieve the transaction and rules that triggered it.
            2. Generate a structured report in JSON for the "AuditReports" container:
            - id,
            - txn_reference,
            - decision (Flagged, Cleared, Escalated),
            - explanation (list of plain-language sentences),
            - citations (list of regulation + clause),
            - provenance (model version, rule set, run_at timestamp),
            - analyst_actions (manual follow-up steps).
            3. Create a natural-language summary for the "Case Explanations" index.

            All outputs must be JSON. Explanations must cite the regulation and clause numbers.
            """
        )
        print(f"Created audit agent with ID: {audit_agent.id}")
        print(f"Agent name: {audit_agent.name}")
        return audit_agent

if __name__ == "__main__":
    asyncio.run(main())

