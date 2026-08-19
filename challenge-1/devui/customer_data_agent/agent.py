import asyncio
import os

from agent_framework import Agent
from agent_framework.foundry import FoundryChatClient
from azure.cosmos import CosmosClient
from azure.identity.aio import AzureCliCredential
from dotenv import load_dotenv

load_dotenv(override=True)

# Configuration
project_endpoint = os.environ.get("AI_FOUNDRY_PROJECT_ENDPOINT")
model_deployment_name = os.environ.get("MODEL_DEPLOYMENT_NAME")
cosmos_endpoint = os.environ.get("COSMOS_ENDPOINT")
cosmos_key = os.environ.get("COSMOS_KEY")

# Initialize Cosmos DB clients globally for function tools
cosmos_client = CosmosClient(cosmos_endpoint, cosmos_key)
database = cosmos_client.get_database_client("FinancialComplianceDB")
customers_container = database.get_container_client("Customers")
transactions_container = database.get_container_client("Transactions")

def get_customer_data(customer_id: str) -> dict:
    """Get customer data from Cosmos DB"""
    try:
        items = list(customers_container.query_items(
            query="SELECT * FROM c WHERE c.customer_id = @customer_id",
            parameters=[{"name": "@customer_id", "value": customer_id}],
            enable_cross_partition_query=True
        ))
        return items[0] if items else {"error": f"Customer {customer_id} not found"}
    except Exception as e:
        return {"error": str(e)}

def get_customer_transactions(customer_id: str) -> list:
    """Get all transactions for a customer from Cosmos DB"""
    try:
        items = list(transactions_container.query_items(
            query="SELECT * FROM c WHERE c.customer_id = @customer_id",
            parameters=[{"name": "@customer_id", "value": customer_id}],
            enable_cross_partition_query=True
        ))
        return items
    except Exception as e:
        return [{"error": str(e)}]

def get_transaction_data(transaction_id: str) -> dict:
    """Get transaction data from Cosmos DB"""
    try:
        items = list(transactions_container.query_items(
            query="SELECT * FROM c WHERE c.transaction_id = @transaction_id",
            parameters=[{"name": "@transaction_id", "value": transaction_id}],
            enable_cross_partition_query=True
        ))
        return items[0] if items else {"error": f"Transaction {transaction_id} not found"}
    except Exception as e:
        return {"error": str(e)}

# Create the agent instance following Agent Framework DevUI conventions
agent = Agent(
    FoundryChatClient(
        project_endpoint=project_endpoint,
        model=model_deployment_name,
        credential=AzureCliCredential(),
    ),
    name="CustomerDataAgent",
    description="Data ingestion agent for retrieving and enriching customer and transaction data from Cosmos DB",
    instructions="""You are a Data Ingestion Agent responsible for preparing structured input for fraud detection. 
    You will receive raw transaction records and customer profiles. Your task is to:
    - Normalize fields (e.g., currency, timestamps, amounts)
    - Remove or flag incomplete data
    - Enrich each transaction with relevant customer metadata (e.g., account age, country, device info)
    - Output a clean JSON object per transaction with unified structure

    You have access to the following functions:
    - get_customer_data: Fetch customer details by customer_id
    - get_customer_transactions: Get all transactions for a customer
    - get_transaction_data: Get specific transaction by transaction_id

    Use these functions to enrich and validate the transaction data.
    Ensure the format is consistent and ready for analysis.
    """,
    tools=[
        get_customer_data,
        get_customer_transactions,
        get_transaction_data,
    ],
)


def main():
    """Launch the Customer Data Agent in DevUI."""
    import logging
    from agent_framework.devui import serve

    # Setup logging
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    logger = logging.getLogger(__name__)

    logger.info("Starting Customer Data Agent")
    logger.info("Available at: http://localhost:8090")
    logger.info("Entity ID: agent_CustomerDataAgent")

    # Launch server with the agent
    serve(entities=[agent], port=8090, auto_open=True)


if __name__ == "__main__":
    main()