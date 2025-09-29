import asyncio
import os
import importlib.util
from pathlib import Path
from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient
from azure.ai.agents.models import AzureAISearchQueryType, AzureAISearchTool, FunctionTool
from dotenv import load_dotenv

load_dotenv(override=True)

# Load tools module directly
tools_path = Path(__file__).parent.parent / 'multi-agents' / 'tools.py'
spec = importlib.util.spec_from_file_location("tools", tools_path)
tools = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tools)
CustomerDataPlugin = tools.CustomerDataPlugin
TransactionDataPlugin = tools.TransactionDataPlugin

# Configuration
project_endpoint = os.environ.get("AI_FOUNDRY_PROJECT_ENDPOINT")
model_deployment_name = os.environ.get("MODEL_DEPLOYMENT_NAME")
sc_connection_id = os.environ.get("AZURE_AI_CONNECTION_ID")
cosmos_endpoint = os.environ.get("COSMOS_ENDPOINT")
cosmos_key = os.environ.get("COSMOS_KEY")

project_client = AIProjectClient(
    endpoint=project_endpoint,
    credential=DefaultAzureCredential(exclude_interactive_browser_credential=False)
)

async def main():
    with project_client:
        # Initialize Cosmos DB plugins
        customer_plugin = CustomerDataPlugin(
            endpoint=cosmos_endpoint,
            key=cosmos_key,
            database_name="FinancialComplianceDB"
        )
        transaction_plugin = TransactionDataPlugin(
            endpoint=cosmos_endpoint,
            key=cosmos_key,
            database_name="FinancialComplianceDB"
        )
        
        # Create agent WITHOUT function tools (tools will be provided via Semantic Kernel)
        data_agent = project_client.agents.create_agent(
            model=model_deployment_name,
            name="data-ingestion-agent",
            instructions="""You are a Data Ingestion Agent responsible for preparing structured input for fraud detection. 
            You will receive raw transaction records and customer profiles. Your task is to:
            - Normalize fields (e.g., currency, timestamps, amounts)
            - Remove or flag incomplete data
            - Enrich each transaction with relevant customer metadata (e.g., account age, country, device info)
            - Output a clean JSON object per transaction with unified structure

            You will have access to the following Semantic Kernel functions:
            - get_customer: Fetch customer details by customer_id
            - get_customer_by_country: Get all customers from a specific country
            - get_transaction: Fetch transaction details by transaction_id
            - get_transactions_by_customer: Get all transactions for a customer
            - get_transactions_by_destination: Get all transactions to a destination country

            Use these functions to enrich and validate the transaction data.
            Ensure the format is consistent and ready for analysis.

            """
            # NOTE: No tools parameter - functions will be provided via Semantic Kernel kernel parameter
        )
        print(f"Created data ingestion agent with ID: {data_agent.id}")
        print(f"Agent name: {data_agent.name}")
        return data_agent

if __name__ == "__main__":
    asyncio.run(main())

