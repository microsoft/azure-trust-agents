import asyncio
import os
from azure.identity.aio import AzureCliCredential
from agent_framework.azure import AzureAIAgentClient
from agent_framework import ChatAgent
from dotenv import load_dotenv
import json
from typing import Annotated
from pydantic import Field
from azure.cosmos import CosmosClient

load_dotenv(override=True)

# Configuration
project_endpoint = os.environ.get("AI_FOUNDRY_PROJECT_ENDPOINT")
model_deployment_name = os.environ.get("MODEL_DEPLOYMENT_NAME")

# Cosmos DB setup
cosmos_endpoint = os.environ.get("COSMOS_ENDPOINT")
cosmos_key = os.environ.get("COSMOS_KEY")
cosmos_client = CosmosClient(cosmos_endpoint, cosmos_key)
database = cosmos_client.get_database_client("FinancialComplianceDB")
customers_container = database.get_container_client("Customers")
transactions_container = database.get_container_client("Transactions")

def get_customer(
    customer_id: Annotated[str, Field(description="The customer identifier (e.g., 'CUST1001', 'C345')")]
) -> dict:
    """Retrieves customer details by customer ID. Returns information like account creation date, country, device info, and account age."""
    try:
        query = f"SELECT * FROM c WHERE c.customer_id = '{customer_id}'"
        items = list(customers_container.query_items(
            query=query,
            enable_cross_partition_query=True
        ))
        return items[0] if items else {"error": f"Customer {customer_id} not found"}
    except Exception as e:
        return {"error": str(e)}

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

class FinancialComplianceWorkflow:
    """
    A sequential workflow that uses existing agents by ID.
    """
    
    def __init__(self, customer_data_agent_id: str, risk_analyser_agent_id: str):
        self.customer_data_agent_id = customer_data_agent_id
        self.risk_analyser_agent_id = risk_analyser_agent_id
        self.customer_data_agent = None
        self.risk_analyser_agent = None
        self.customer_client = None
        self.risk_client = None
    
    async def load_agents(self, credential):
        """Load existing agents by their IDs with their original tools preserved."""
        # Create clients bound to existing agent IDs - this preserves their tools
        self.customer_client = AzureAIAgentClient(
            project_endpoint=project_endpoint,
            model_deployment_name=model_deployment_name,
            async_credential=credential,
            agent_id=self.customer_data_agent_id
        )
        
        self.risk_client = AzureAIAgentClient(
            project_endpoint=project_endpoint,
            model_deployment_name=model_deployment_name,
            async_credential=credential,
            agent_id=self.risk_analyser_agent_id
        )
        
        # Create ChatAgent instances with the bound clients
        self.customer_data_agent = ChatAgent(
            chat_client=self.customer_client,
            model_id=model_deployment_name,
            tools=[get_customer, get_transaction, get_transactions_by_customer, get_transactions_by_destination],
            store=True
        )
        
        self.risk_analyser_agent = ChatAgent(
            chat_client=self.risk_client,
            model_id=model_deployment_name,
            store=True
        )

    async def run_workflow(self, transaction_id: str, credential) -> dict:
        """Execute the complete workflow for a given transaction."""
        if not self.customer_data_agent or not self.risk_analyser_agent:
            await self.load_agents(credential)
        
        print(f"🚀 Starting workflow for transaction: {transaction_id}")
        
        # Step 1: Customer Data Agent
        print("📊 Step 1: Retrieving customer data...")
        data_result = await self.customer_data_agent.run(
            f"Analyze transaction {transaction_id} and its associated customer comprehensively."
        )
        
        # Step 2: Risk Analyser Agent
        print("🔍 Step 2: Analyzing fraud risk...")
        risk_result = await self.risk_analyser_agent.run(
            f"Analyze this data for fraud risk: {data_result.text}"
        )
        
        return {
            "transaction_id": transaction_id,
            "workflow_status": "completed",
            "step1_customer_data": data_result.text,
            "step2_risk_analysis": risk_result.text,
            "timestamp": "2025-10-10"
        }
    
    async def cleanup(self):
        """Clean up client resources to prevent unclosed session warnings."""
        if self.customer_client:
            await self.customer_client.close()
        if self.risk_client:
            await self.risk_client.close()
          

async def analyze_transaction(transaction_id: str, customer_agent_id: str, risk_agent_id: str):
    """Analyze a transaction using existing agents by ID."""
    print(f"🔍 Analyzing transaction: {transaction_id}")
    
    async with AzureCliCredential() as credential:
        workflow = FinancialComplianceWorkflow(customer_agent_id, risk_agent_id)
        try:
            result = await workflow.run_workflow(transaction_id, credential)
            
            print(f"📋 ANALYSIS COMPLETE for {transaction_id}")
            print(json.dumps(result, indent=2))
            return result
        finally:
            # Clean up resources to prevent unclosed session warnings
            await workflow.cleanup()

if __name__ == "__main__":
    CUSTOMER_DATA_AGENT_ID = os.environ.get("CUSTOMER_DATA_AGENT_ID")
    RISK_ANALYSER_AGENT_ID = os.environ.get("RISK_ANALYSER_AGENT_ID")
    asyncio.run(analyze_transaction("TX1007", CUSTOMER_DATA_AGENT_ID, RISK_ANALYSER_AGENT_ID))
