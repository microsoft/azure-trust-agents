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
        # Create AI Search tool
        ai_search = AzureAISearchTool(
            index_connection_id=sc_connection_id,
            index_name="regulations-policies",
            query_type=AzureAISearchQueryType.SIMPLE,
            top_k=5,
        )

        # Create agent
        regulation_agent = project_client.agents.create_agent(
            model=model_deployment_name,
            name="regulation-agent",
            instructions="""You are the Regulation Agent. 
            Your task is to read new regulations and convert them into structured compliance rules. 
            You search the "Regulations Policies" index for relevant AML, KYC, or financial directives.

            Rules must be output in JSON format with:
            - id (regulation:clause format)
            - regulation_id
            - jurisdiction  
            - effective_date
            - clause_id
            - requirement (plain text)
            - mapped_feature (transaction attribute this applies to)
            - threshold (numeric or list)
            - action ("alert" or "block")

            Do not summarize text — always map it into machine-usable compliance obligations.
            Output each rule as a JSON code block.""",
            tools=ai_search.definitions,
            tool_resources=ai_search.resources,
        )
        print(f"Created regulation agent with ID: {regulation_agent.id}")
        print(f"Agent name: {regulation_agent.name}")
        return regulation_agent

if __name__ == "__main__":
    asyncio.run(main())

