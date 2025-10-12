"""
Customer Data Agent Executor for Microsoft Agent Framework.

This executor implements the Customer Data Agent functionality using the 
Microsoft Agent Framework Executor pattern as described in:
https://learn.microsoft.com/en-us/agent-framework/user-guide/workflows/core-concepts/executors
"""

import asyncio
import os
import logging
from typing import Dict, Any, List
from azure.cosmos import CosmosClient
from agent_framework import (
    Executor,
    WorkflowContext,
    executor,
)
from pydantic import Field, BaseModel
from dotenv import load_dotenv

load_dotenv(override=True)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
cosmos_endpoint = os.environ.get("COSMOS_ENDPOINT")
cosmos_key = os.environ.get("COSMOS_KEY")

# Initialize Cosmos DB clients globally for function tools
cosmos_client = CosmosClient(cosmos_endpoint, cosmos_key)
database = cosmos_client.get_database_client("FinancialComplianceDB")
customers_container = database.get_container_client("Customers")
transactions_container = database.get_container_client("Transactions")


# Data Models
class CustomerDataRequest(BaseModel):
    """Request model for customer data operations."""
    transaction_id: str
    customer_id: str | None = None
    include_history: bool = True
    include_destination_analysis: bool = True


class CustomerDataResponse(BaseModel):
    """Response model for customer data operations."""
    transaction_id: str
    transaction_data: Dict[str, Any]
    customer_data: Dict[str, Any]
    transaction_history: List[Dict[str, Any]]
    destination_analysis: List[Dict[str, Any]]
    enriched_data: Dict[str, Any]
    status: str
    message: str


# Customer Data Functions
def get_customer(customer_id: str) -> dict:
    """Retrieves customer information by customer ID."""
    try:
        query = f"SELECT * FROM c WHERE c.customer_id = '{customer_id}'"
        items = list(customers_container.query_items(
            query=query,
            enable_cross_partition_query=True
        ))
        return items[0] if items else {"error": f"Customer {customer_id} not found"}
    except Exception as e:
        return {"error": str(e)}


def get_transaction(transaction_id: str) -> dict:
    """Retrieves transaction details by transaction ID."""
    try:
        query = f"SELECT * FROM c WHERE c.transaction_id = '{transaction_id}'"
        items = list(transactions_container.query_items(
            query=query,
            enable_cross_partition_query=True
        ))
        return items[0] if items else {"error": f"Transaction {transaction_id} not found"}
    except Exception as e:
        return {"error": str(e)}


def get_transactions_by_customer(customer_id: str) -> list:
    """Retrieves all transactions for a specific customer."""
    try:
        query = f"SELECT * FROM c WHERE c.customer_id = '{customer_id}'"
        items = list(transactions_container.query_items(
            query=query,
            enable_cross_partition_query=True
        ))
        return items
    except Exception as e:
        return [{"error": str(e)}]


def get_transactions_by_destination(destination_country: str) -> list:
    """Retrieves all transactions to a specific destination country."""
    try:
        query = f"SELECT * FROM c WHERE c.destination_country = '{destination_country}'"
        items = list(transactions_container.query_items(
            query=query,
            enable_cross_partition_query=True
        ))
        return items
    except Exception as e:
        return [{"error": str(e)}]


@executor
async def customer_data_executor(
    request: CustomerDataRequest,
    ctx: WorkflowContext
) -> CustomerDataResponse:
    """
    Customer Data Agent Executor for comprehensive transaction and customer data retrieval and enrichment.
    
    Args:
        request: Customer data request with transaction ID and options
        ctx: Workflow context
        
    Returns:
        CustomerDataResponse: Enriched transaction and customer data
    """
    logger.info(f"🔍 Starting data retrieval and enrichment for transaction: {request.transaction_id}")
    
    try:
        # Step 1: Retrieve transaction details
        transaction_data = get_transaction(request.transaction_id)
        if "error" in transaction_data:
            return CustomerDataResponse(
                transaction_id=request.transaction_id,
                transaction_data={},
                customer_data={},
                transaction_history=[],
                destination_analysis=[],
                enriched_data={},
                status="ERROR",
                message=f"Transaction not found: {transaction_data['error']}"
            )

        # Extract customer ID from transaction if not provided
        customer_id = request.customer_id or transaction_data.get("customer_id")
        if not customer_id:
            return CustomerDataResponse(
                transaction_id=request.transaction_id,
                transaction_data=transaction_data,
                customer_data={},
                transaction_history=[],
                destination_analysis=[],
                enriched_data={},
                status="ERROR",
                message="Customer ID not found in transaction data"
            )

        # Step 2: Retrieve customer profile
        customer_data = get_customer(customer_id)
        if "error" in customer_data:
            logger.warning(f"Customer data not found for {customer_id}")
            customer_data = {}

        # Step 3: Retrieve transaction history (if requested)
        transaction_history = []
        if request.include_history:
            transaction_history = get_transactions_by_customer(customer_id)
            if isinstance(transaction_history, list) and len(transaction_history) > 0:
                if "error" in transaction_history[0]:
                    transaction_history = []

        # Step 4: Analyze destination country patterns (if requested)
        destination_analysis = []
        if request.include_destination_analysis:
            destination_country = transaction_data.get("destination_country")
            if destination_country:
                destination_analysis = get_transactions_by_destination(destination_country)
                if isinstance(destination_analysis, list) and len(destination_analysis) > 0:
                    if "error" in destination_analysis[0]:
                        destination_analysis = []

        # Step 5: Create enriched dataset
        enriched_data = _create_enriched_dataset(
            transaction_data, 
            customer_data, 
            transaction_history, 
            destination_analysis
        )

        logger.info(f"✅ Data enrichment completed for transaction {request.transaction_id}")
        
        return CustomerDataResponse(
            transaction_id=request.transaction_id,
            transaction_data=transaction_data,
            customer_data=customer_data,
            transaction_history=transaction_history,
            destination_analysis=destination_analysis,
            enriched_data=enriched_data,
            status="SUCCESS",
            message=f"Successfully enriched data for transaction {request.transaction_id} and customer {customer_id}"
        )

    except Exception as e:
        error_msg = f"Error during data retrieval and enrichment: {str(e)}"
        logger.error(error_msg)
        return CustomerDataResponse(
            transaction_id=request.transaction_id,
            transaction_data={},
            customer_data={},
            transaction_history=[],
            destination_analysis=[],
            enriched_data={},
            status="ERROR",
            message=error_msg
        )


def _create_enriched_dataset(
    transaction_data: Dict[str, Any],
    customer_data: Dict[str, Any],
    transaction_history: List[Dict[str, Any]],
    destination_analysis: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Create a comprehensive enriched dataset for fraud analysis.
    """
    try:
        # Calculate derived metrics
        enriched = {
            "transaction": transaction_data,
            "customer": customer_data,
            "historical_context": {
                "total_transactions": len(transaction_history),
                "transaction_history": transaction_history
            },
            "destination_context": {
                "total_transactions_to_destination": len(destination_analysis),
                "destination_transactions": destination_analysis
            },
            "risk_indicators": {},
            "normalized_fields": {}
        }

        # Calculate risk indicators
        current_amount = transaction_data.get("amount", 0)
        customer_country = customer_data.get("country", "")
        destination_country = transaction_data.get("destination_country", "")
        
        # Historical amount analysis
        if transaction_history:
            amounts = [t.get("amount", 0) for t in transaction_history if t.get("amount")]
            if amounts:
                avg_amount = sum(amounts) / len(amounts)
                max_amount = max(amounts)
                enriched["risk_indicators"]["amount_vs_average"] = current_amount / avg_amount if avg_amount > 0 else 0
                enriched["risk_indicators"]["amount_vs_max"] = current_amount / max_amount if max_amount > 0 else 0

        # Country risk indicators
        enriched["risk_indicators"]["cross_border_transaction"] = customer_country != destination_country
        enriched["risk_indicators"]["customer_country"] = customer_country
        enriched["risk_indicators"]["destination_country"] = destination_country

        # Customer behavior patterns
        if customer_data:
            enriched["risk_indicators"]["account_age_days"] = customer_data.get("account_age_days", 0)
            enriched["risk_indicators"]["device_trust_score"] = customer_data.get("device_trust_score", 0.5)
            enriched["risk_indicators"]["past_fraud_flags"] = customer_data.get("past_fraud_flags", 0)

        # Normalize key fields for analysis
        enriched["normalized_fields"]["transaction_id"] = transaction_data.get("transaction_id")
        enriched["normalized_fields"]["customer_id"] = customer_data.get("customer_id")
        enriched["normalized_fields"]["amount_usd"] = current_amount  # Assuming already in USD
        enriched["normalized_fields"]["timestamp"] = transaction_data.get("timestamp")
        enriched["normalized_fields"]["currency"] = transaction_data.get("currency", "USD")

        return enriched

    except Exception as e:
        logger.error(f"Error creating enriched dataset: {str(e)}")
        return {
            "error": f"Failed to create enriched dataset: {str(e)}",
            "transaction": transaction_data,
            "customer": customer_data
        }


async def main():
    """
    Main function to test the Customer Data Agent Executor.
    """
    try:
        print(f"✅ Customer Data Agent Executor Function Created Successfully")
        print(f"📋 Executor Type: {type(customer_data_executor)}")
        print(f"📝 Note: This is a Microsoft Agent Framework executor function.")
        print(f"🔧 To use in workflows, pass this executor to WorkflowBuilder.")
        
        # For demonstration, let's test the underlying data functions directly
        print(f"\n🔍 Testing underlying data functions...")
        
        # Test basic data retrieval
        transaction_data = get_transaction("TX1001")
        print(f"📊 Transaction Data Test: {'SUCCESS' if 'error' not in transaction_data else 'ERROR'}")
        
        if 'error' not in transaction_data:
            customer_id = transaction_data.get("customer_id")
            if customer_id:
                customer_data = get_customer(customer_id)
                print(f"👤 Customer Data Test: {'SUCCESS' if 'error' not in customer_data else 'ERROR'}")
                
                transaction_history = get_transactions_by_customer(customer_id)
                print(f"📈 Transaction History Test: {'SUCCESS' if isinstance(transaction_history, list) else 'ERROR'}")
                
                destination_country = transaction_data.get("destination_country")
                if destination_country:
                    destination_analysis = get_transactions_by_destination(destination_country)
                    print(f"🌍 Destination Analysis Test: {'SUCCESS' if isinstance(destination_analysis, list) else 'ERROR'}")
        
        # Show how to use in workflow
        print(f"\n🚀 USAGE EXAMPLE:")
        print(f"To use this executor in a workflow:")
        print(f"```python")
        print(f"from workflow import customer_data_executor")
        print(f"from agent_framework import WorkflowBuilder")
        print(f"")
        print(f"workflow = WorkflowBuilder().add_executor(customer_data_executor).build()")
        print(f"result = await workflow.run(CustomerDataRequest(...))")
        print(f"```")
        
        return customer_data_executor
        
    except Exception as e:
        print(f"❌ Error testing Customer Data Executor: {e}")
        return None


if __name__ == "__main__":
    asyncio.run(main())