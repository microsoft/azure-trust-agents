import asyncio
import os
from typing import Annotated
from azure.identity.aio import AzureCliCredential
from agent_framework.azure import AzureAIAgentClient
from azure.cosmos import CosmosClient
from dotenv import load_dotenv
from pydantic import Field

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


# Customer Data Functions (converted from plugin methods)
def get_customer(
    customer_id: Annotated[str, Field(description="The unique customer identifier (e.g., 'CUST1001')")]
) -> dict:
    """Retrieves customer information by customer ID. Returns details like name, country, account age, device trust score, and past fraud history."""
    try:
        query = f"SELECT * FROM c WHERE c.customer_id = '{customer_id}'"
        items = list(customers_container.query_items(
            query=query,
            enable_cross_partition_query=True
        ))
        return items[0] if items else {"error": f"Customer {customer_id} not found"}
    except Exception as e:
        return {"error": str(e)}

def get_customer_by_country(
    country: Annotated[str, Field(description="Country code (e.g., 'US', 'IN', 'CN')")]
) -> list:
    """Retrieves all customers from a specific country. Useful for analyzing regional patterns."""
    try:
        query = f"SELECT * FROM c WHERE c.country = '{country}'"
        items = list(customers_container.query_items(
            query=query,
            enable_cross_partition_query=True
        ))
        return items
    except Exception as e:
        return [{"error": str(e)}]

def get_transaction(
    transaction_id: Annotated[str, Field(description="The unique transaction identifier (e.g., 'TX1001')")]
) -> dict:
    """Retrieves transaction details by transaction ID. Returns information like amount, currency, destination country, and timestamp."""
    try:
        query = f"SELECT * FROM c WHERE c.transaction_id = '{transaction_id}'"
        items = list(transactions_container.query_items(
            query=query,
            enable_cross_partition_query=True
        ))
        return items[0] if items else {"error": f"Transaction {transaction_id} not found"}
    except Exception as e:
        return {"error": str(e)}

def get_transactions_by_customer(
    customer_id: Annotated[str, Field(description="The customer identifier (e.g., 'CUST1001')")]
) -> list:
    """Retrieves all transactions for a specific customer. Useful for analyzing customer transaction history and patterns."""
    try:
        query = f"SELECT * FROM c WHERE c.customer_id = '{customer_id}'"
        items = list(transactions_container.query_items(
            query=query,
            enable_cross_partition_query=True
        ))
        return items
    except Exception as e:
        return [{"error": str(e)}]

def get_transactions_by_destination(
    destination_country: Annotated[str, Field(description="Destination country code (e.g., 'US', 'IR', 'SY')")]
) -> list:
    """Retrieves all transactions to a specific destination country. Useful for checking sanctions or high-risk destinations."""
    try:
        query = f"SELECT * FROM c WHERE c.destination_country = '{destination_country}'"
        items = list(transactions_container.query_items(
            query=query,
            enable_cross_partition_query=True
        ))
        return items
    except Exception as e:
        return [{"error": str(e)}]


async def main():
    try:
        async with AzureCliCredential() as credential:
            # Create the AzureAIAgentClient
            async with AzureAIAgentClient(
                project_endpoint=project_endpoint,
                model_deployment_name=model_deployment_name,
                async_credential=credential
            ) as client:
                
                agent = client.create_agent(
                    name="DataIngestionAgent",
                    instructions="""You are a Data Ingestion Agent responsible for preparing structured input for fraud detection. 
                    You will receive raw transaction records and customer profiles. Your task is to:
                    - Normalize fields (e.g., currency, timestamps, amounts)
                    - Remove or flag incomplete data
                    - Enrich each transaction with relevant customer metadata (e.g., account age, country, device info)
                    - Output a clean JSON object per transaction with unified structure

                    You have access to the following functions:
                    - get_customer: Fetch customer details by customer_id
                    - get_customer_by_country: Get all customers from a specific country
                    - get_transaction: Fetch transaction details by transaction_id
                    - get_transactions_by_customer: Get all transactions for a customer
                    - get_transactions_by_destination: Get all transactions to a destination country

                    Use these functions to enrich and validate the transaction data.
                    Ensure the format is consistent and ready for analysis.
                    """,
                    tools=[
                        get_customer,
                        get_customer_by_country, 
                        get_transaction,
                        get_transactions_by_customer,
                        get_transactions_by_destination
                    ],
                )

                # Test the agent with a simple query
                print("\n🧪 Testing the agent with a sample query...")
                try:
                    result = await agent.run("Analyze customer CUST1005 comprehensively.", store=True)
                    print(f"✅ Agent response: {result.text}")
                except Exception as test_error:
                    print(f"⚠️  Agent test failed (but agent was still created): {test_error}")
                
                return agent
    except Exception as e:
        print(f"❌ Error creating agent: {e}")
        print("Make sure you have the proper Azure credentials configured.")
        return None

if __name__ == "__main__":
    asyncio.run(main())