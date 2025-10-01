import os
from azure.cosmos import CosmosClient
from semantic_kernel.functions import kernel_function

# Customer Data Plugin
class CustomerDataPlugin:
    """Plugin for fetching customer data from Cosmos DB"""
    
    def __init__(self, endpoint: str, key: str, database_name: str = "FinancialComplianceDB"):
        """
        Initialize the Customer Data Plugin
        
        Args:
            endpoint: Cosmos DB endpoint URL
            key: Cosmos DB access key
            database_name: Name of the database (default: FinancialComplianceDB)
        """
        self.client = CosmosClient(endpoint, key)
        self.database = self.client.get_database_client(database_name)
        self.container = self.database.get_container_client("Customers")
    
    @kernel_function(
        name="get_customer",
        description="Retrieves customer information by customer ID. Returns details like name, country, account age, device trust score, and past fraud history."
    )
    def get_customer(self, customer_id: str) -> dict:
        """
        Fetch customer data by customer_id
        
        Args:
            customer_id: The unique customer identifier (e.g., 'CUST1001')
            
        Returns:
            Dictionary containing customer information including:
            - customer_id: Unique customer identifier
            - name: Customer name
            - country: Country code
            - account_age_days: Age of account in days
            - device_trust_score: Trust score for device (0-1)
            - past_fraud: Boolean indicating past fraud history
        """
        try:
            query = f"SELECT * FROM c WHERE c.customer_id = '{customer_id}'"
            items = list(self.container.query_items(
                query=query,
                enable_cross_partition_query=True
            ))
            return items[0] if items else {"error": f"Customer {customer_id} not found"}
        except Exception as e:
            return {"error": str(e)}
    
    @kernel_function(
        name="get_customer_by_country",
        description="Retrieves all customers from a specific country. Useful for analyzing regional patterns."
    )
    def get_customer_by_country(self, country: str) -> list:
        """
        Fetch all customers from a specific country
        
        Args:
            country: Country code (e.g., 'US', 'IN', 'CN')
            
        Returns:
            List of customer dictionaries from the specified country
        """
        try:
            query = f"SELECT * FROM c WHERE c.country = '{country}'"
            items = list(self.container.query_items(
                query=query,
                enable_cross_partition_query=True
            ))
            return items
        except Exception as e:
            return [{"error": str(e)}]


# Transaction Data Plugin
class TransactionDataPlugin:
    """Plugin for fetching transaction data from Cosmos DB"""
    
    def __init__(self, endpoint: str, key: str, database_name: str = "FinancialComplianceDB"):
        """
        Initialize the Transaction Data Plugin
        
        Args:
            endpoint: Cosmos DB endpoint URL
            key: Cosmos DB access key
            database_name: Name of the database (default: FinancialComplianceDB)
        """
        self.client = CosmosClient(endpoint, key)
        self.database = self.client.get_database_client(database_name)
        self.container = self.database.get_container_client("Transactions")
    
    @kernel_function(
        name="get_transaction",
        description="Retrieves transaction details by transaction ID. Returns information like amount, currency, destination country, and timestamp."
    )
    def get_transaction(self, transaction_id: str) -> dict:
        """
        Fetch transaction data by transaction_id
        
        Args:
            transaction_id: The unique transaction identifier (e.g., 'TX1001')
            
        Returns:
            Dictionary containing transaction information including:
            - transaction_id: Unique transaction identifier
            - customer_id: Associated customer ID
            - amount: Transaction amount
            - currency: Currency code
            - destination_country: Destination country code
            - timestamp: Transaction timestamp (ISO format)
        """
        try:
            query = f"SELECT * FROM c WHERE c.transaction_id = '{transaction_id}'"
            items = list(self.container.query_items(
                query=query,
                enable_cross_partition_query=True
            ))
            return items[0] if items else {"error": f"Transaction {transaction_id} not found"}
        except Exception as e:
            return {"error": str(e)}
    
    @kernel_function(
        name="get_transactions_by_customer",
        description="Retrieves all transactions for a specific customer. Useful for analyzing customer transaction history and patterns."
    )
    def get_transactions_by_customer(self, customer_id: str) -> list:
        """
        Fetch all transactions for a specific customer
        
        Args:
            customer_id: The customer identifier (e.g., 'CUST1001')
            
        Returns:
            List of transaction dictionaries for the specified customer
        """
        try:
            query = f"SELECT * FROM c WHERE c.customer_id = '{customer_id}'"
            items = list(self.container.query_items(
                query=query,
                enable_cross_partition_query=True
            ))
            return items
        except Exception as e:
            return [{"error": str(e)}]
    
    @kernel_function(
        name="get_transactions_by_destination",
        description="Retrieves all transactions to a specific destination country. Useful for checking sanctions or high-risk destinations."
    )
    def get_transactions_by_destination(self, destination_country: str) -> list:
        """
        Fetch all transactions to a specific destination country
        
        Args:
            destination_country: Destination country code (e.g., 'US', 'IR', 'SY')
            
        Returns:
            List of transaction dictionaries to the specified destination
        """
        try:
            query = f"SELECT * FROM c WHERE c.destination_country = '{destination_country}'"
            items = list(self.container.query_items(
                query=query,
                enable_cross_partition_query=True
            ))
            return items
        except Exception as e:
            return [{"error": str(e)}]


# ML Predictions Plugin
class MLPredictionsPlugin:
    """Plugin for fetching ML prediction scores from Cosmos DB"""
    
    def __init__(self, endpoint: str, key: str, database_name: str = "FinancialComplianceDB"):
        """
        Initialize the ML Predictions Plugin
        
        Args:
            endpoint: Cosmos DB endpoint URL
            key: Cosmos DB access key
            database_name: Name of the database (default: FinancialComplianceDB)
        """
        self.client = CosmosClient(endpoint, key)
        self.database = self.client.get_database_client(database_name)
        self.container = self.database.get_container_client("Mlpredictions")
    
    @kernel_function(
        name="get_ml_prediction",
        description="Retrieves ML fraud prediction score for a specific transaction. Score ranges from 0 (low risk) to 1 (high risk)."
    )
    def get_ml_prediction(self, transaction_id: str) -> dict:
        """
        Fetch ML prediction score for a transaction
        
        Args:
            transaction_id: The transaction identifier (e.g., 'TX1001')
            
        Returns:
            Dictionary containing the ML prediction score (0-1 scale where higher means more likely fraud)
            Example: {"TX1001": 0.12} means 12% fraud probability
        """
        try:
            # The ML predictions data is stored as key-value pairs
            # We need to query for items that contain this transaction_id
            query = "SELECT * FROM c"
            items = list(self.container.query_items(
                query=query,
                enable_cross_partition_query=True
            ))
            
            # Find the prediction for this transaction
            for item in items:
                if transaction_id in item:
                    return {
                        "transaction_id": transaction_id,
                        "fraud_score": item[transaction_id],
                        "risk_level": "HIGH" if item[transaction_id] > 0.7 else "MEDIUM" if item[transaction_id] > 0.4 else "LOW"
                    }
            
            return {"error": f"ML prediction for transaction {transaction_id} not found"}
        except Exception as e:
            return {"error": str(e)}
    
    @kernel_function(
        name="get_all_ml_predictions",
        description="Retrieves all ML prediction scores. Useful for batch analysis or finding high-risk transactions."
    )
    def get_all_ml_predictions(self) -> dict:
        """
        Fetch all ML prediction scores
        
        Returns:
            Dictionary mapping transaction IDs to their fraud scores
        """
        try:
            query = "SELECT * FROM c"
            items = list(self.container.query_items(
                query=query,
                enable_cross_partition_query=True
            ))
            
            # Merge all prediction items into a single dictionary
            all_predictions = {}
            for item in items:
                # Remove system fields like 'id', '_rid', etc.
                for key, value in item.items():
                    if not key.startswith('_') and key != 'id':
                        all_predictions[key] = value
            
            return all_predictions
        except Exception as e:
            return {"error": str(e)}
