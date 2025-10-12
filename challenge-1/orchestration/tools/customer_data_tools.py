"""
Customer Data Agent Tools
Tools for fetching customer and transaction data from Cosmos DB
"""

import os
import logging
from typing import Annotated, List
from azure.cosmos import CosmosClient
from pydantic import Field
from dotenv import load_dotenv

# Configure logging
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv(override=True)

# Configuration
cosmos_endpoint = os.environ.get("COSMOS_ENDPOINT")
cosmos_key = os.environ.get("COSMOS_KEY")

# Initialize Cosmos DB clients
cosmos_client = CosmosClient(cosmos_endpoint, cosmos_key)
database = cosmos_client.get_database_client("FinancialComplianceDB")
customers_container = database.get_container_client("Customers")
transactions_container = database.get_container_client("Transactions")

# Synchronous tool functions for agent framework compatibility
def get_customer_sync(
    customer_id: Annotated[str, Field(description="The customer identifier (e.g., 'CUST1001', 'C345')")]
) -> dict:
    """Synchronous wrapper for get_customer that works with agent framework"""
    try:
        # Input validation
        if not customer_id or not customer_id.strip():
            return {"error": "Customer ID cannot be empty"}
        
        query = f"SELECT * FROM c WHERE c.customer_id = '{customer_id.strip()}'"
        items = list(customers_container.query_items(
            query=query,
            enable_cross_partition_query=True
        ))
        
        if items:
            logger.info(f"Retrieved customer data for {customer_id}")
            return items[0]
        else:
            logger.warning(f"No customer found with ID: {customer_id}")
            return {"error": f"Customer {customer_id} not found"}
            
    except Exception as e:
        logger.error(f"Error retrieving customer {customer_id}: {e}")
        return {"error": f"Failed to retrieve customer: {str(e)}"}

def get_transaction_sync(
    transaction_id: Annotated[str, Field(description="The transaction identifier (e.g., 'TX1001', 'TXN2023001')")]
) -> dict:
    """Synchronous wrapper for get_transaction that works with agent framework"""
    try:
        # Input validation
        if not transaction_id or not transaction_id.strip():
            return {"error": "Transaction ID cannot be empty"}
        
        query = f"SELECT * FROM t WHERE t.transaction_id = '{transaction_id.strip()}'"
        items = list(transactions_container.query_items(
            query=query,
            enable_cross_partition_query=True
        ))
        
        if items:
            logger.info(f"Retrieved transaction data for {transaction_id}")
            return items[0]
        else:
            logger.warning(f"No transaction found with ID: {transaction_id}")
            return {"error": f"Transaction {transaction_id} not found"}
            
    except Exception as e:
        logger.error(f"Error retrieving transaction {transaction_id}: {e}")
        return {"error": f"Failed to retrieve transaction: {str(e)}"}

def get_transactions_by_customer_sync(
    customer_id: Annotated[str, Field(description="The customer identifier to get all transactions for")]
) -> List[dict]:
    """Synchronous wrapper for get_transactions_by_customer that works with agent framework"""
    try:
        # Input validation
        if not customer_id or not customer_id.strip():
            return [{"error": "Customer ID cannot be empty"}]
        
        query = f"SELECT * FROM t WHERE t.customer_id = '{customer_id.strip()}'"
        items = list(transactions_container.query_items(
            query=query,
            enable_cross_partition_query=True
        ))
        
        logger.info(f"Retrieved {len(items)} transactions for customer {customer_id}")
        return items if items else [{"message": f"No transactions found for customer {customer_id}"}]
        
    except Exception as e:
        logger.error(f"Error retrieving transactions for customer {customer_id}: {e}")
        return [{"error": f"Failed to retrieve customer transactions: {str(e)}"}]

def get_transactions_by_destination_sync(
    destination_country: Annotated[str, Field(description="The destination country to filter transactions by")]
) -> List[dict]:
    """Synchronous wrapper for get_transactions_by_destination that works with agent framework"""
    try:
        # Input validation
        if not destination_country or not destination_country.strip():
            return [{"error": "Destination country cannot be empty"}]
        
        query = f"SELECT * FROM t WHERE t.destination_country = '{destination_country.strip()}'"
        items = list(transactions_container.query_items(
            query=query,
            enable_cross_partition_query=True
        ))
        
        logger.info(f"Retrieved {len(items)} transactions for destination {destination_country}")
        return items if items else [{"message": f"No transactions found for destination {destination_country}"}]
        
    except Exception as e:
        logger.error(f"Error retrieving transactions for destination {destination_country}: {e}")
        return [{"error": f"Failed to retrieve destination transactions: {str(e)}"}]