import asyncio
import os
from typing import Annotated
from azure.identity.aio import AzureCliCredential
from agent_framework.azure import AzureAIAgentClient
from agent_framework import ChatAgent
from azure.ai.projects.aio import AIProjectClient
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

def get_customer_data(customer_id: str) -> dict:
    """Get customer data from Cosmos DB"""
    try:
        query = f"SELECT * FROM c WHERE c.customer_id = '{customer_id}'"
        items = list(customers_container.query_items(
            query=query,
            enable_cross_partition_query=True
        ))
        return items[0] if items else {"error": f"Customer {customer_id} not found"}
    except Exception as e:
        return {"error": str(e)}

def get_customer_transactions(customer_id: str) -> list:
    """Get all transactions for a customer from Cosmos DB"""
    try:
        query = f"SELECT * FROM c WHERE c.customer_id = '{customer_id}'"
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
            async with AIProjectClient(
                endpoint=project_endpoint,
                credential=credential
            ) as project_client:
                
                # Create persistent agent
                created_agent = await project_client.agents.create_agent(
                    model=model_deployment_name,
                    name="CustomerDataAgent",
                    instructions="""You are a Data Ingestion Agent responsible for preparing structured input for fraud detection. 
                    You will receive raw transaction records and customer profiles. Your task is to:
                    - Normalize fields (e.g., currency, timestamps, amounts)
                    - Remove or flag incomplete data
                    - Enrich each transaction with relevant customer metadata (e.g., account age, country, device info)
                    - Output a clean JSON object per transaction with unified structure

                You have access to the following functions:
                - get_customer_data: Fetch customer details by customer_id
                - get_customer_transactions: Get all transactions for a customer

                    Use these functions to enrich and validate the transaction data.
                    Ensure the format is consistent and ready for analysis.
                    """
                )
                
                # Wrap agent with tools for usage
                agent = ChatAgent(
                    chat_client=AzureAIAgentClient(
                        project_client=project_client,
                        agent_id=created_agent.id
                    ),
                    tools=[
                        get_customer_data,
                        get_customer_transactions,
                    ],
                    store=True
                )

                # Test the agent with a simple query
                print("\n🧪 Testing the agent with a sample query...")
                try:
                    result = await agent.run("Analyze customer CUST1005 comprehensively.")
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
