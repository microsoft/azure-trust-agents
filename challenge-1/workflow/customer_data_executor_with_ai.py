"""
Customer Data Agent Executor with AI Integration

This module provides an enhanced customer data retrieval and analysis executor that integrates
with Azure AI Foundry for intelligent insights and risk assessment. It's designed to work with
the Microsoft Agent Framework.

Features:
- Azure Cosmos DB integration for customer data retrieval
- Azure AI Foundry integration for intelligent analysis
- Pydantic model validation
- Comprehensive error handling and logging
- Real-time AI-powered customer insights
"""

import os
import json
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import logging

# Microsoft Agent Framework
from agents import Agent
from agents.executor import FunctionExecutor, executor

# Azure AI and Database
from azure.ai.agents import AzureAIAgentClient, ChatAgent
from azure.identity import AzureCliCredential
from azure.cosmos import CosmosClient, exceptions
from azure.identity import DefaultAzureCredential

# Pydantic for data validation
from pydantic import BaseModel, Field

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
import json

# Azure OpenAI integration
try:
    from openai import AsyncAzureOpenAI
except ImportError:
    AsyncAzureOpenAI = None

load_dotenv(override=True)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
cosmos_endpoint = os.environ.get("COSMOS_ENDPOINT")
cosmos_key = os.environ.get("COSMOS_KEY")
model_deployment_name = os.environ.get("MODEL_DEPLOYMENT_NAME", "gpt-4o-mini")
project_endpoint = os.environ.get("AI_FOUNDRY_PROJECT_ENDPOINT")
azure_ai_connection_id = os.environ.get("AZURE_AI_CONNECTION_ID")

# Initialize Cosmos DB clients globally
cosmos_client = CosmosClient(cosmos_endpoint, cosmos_key)
database = cosmos_client.get_database_client("FinancialComplianceDB")
customers_container = database.get_container_client("Customers")
transactions_container = database.get_container_client("Transactions")

# Azure AI Foundry configuration check
if project_endpoint:
    logger.info("✅ Azure AI Foundry configuration found")
else:
    logger.warning("⚠️  Azure AI Foundry configuration not found - AI features disabled")


# Data Models
class CustomerDataRequest(BaseModel):
    """Request model for customer data operations."""
    transaction_id: str
    customer_id: str | None = None
    include_history: bool = True
    include_destination_analysis: bool = True
    use_ai_insights: bool = True


class CustomerDataResponse(BaseModel):
    """Response model for customer data operations."""
    transaction_id: str
    transaction_data: Dict[str, Any]
    customer_data: Dict[str, Any]
    transaction_history: List[Dict[str, Any]]
    destination_analysis: List[Dict[str, Any]]
    enriched_data: Dict[str, Any]
    ai_insights: str = ""
    confidence_score: float = 0.0
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
async def customer_data_executor_with_ai(
    request: CustomerDataRequest,
    ctx: WorkflowContext
) -> CustomerDataResponse:
    """
    Enhanced Customer Data Agent Executor with AI insights for comprehensive data analysis.
    
    Combines traditional data retrieval with AI-powered pattern analysis and insights.
    
    Args:
        request: Customer data request with transaction ID and options
        ctx: Workflow context
        
    Returns:
        CustomerDataResponse: Enriched transaction and customer data with AI insights
    """
    logger.info(f"🔍 Starting enhanced data retrieval and enrichment for transaction: {request.transaction_id}")
    
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
                ai_insights="",
                confidence_score=0.0,
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
                ai_insights="",
                confidence_score=0.0,
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

        # Step 6: Generate AI insights (new enhancement)
        ai_insights = ""
        confidence_score = 0.8
        if request.use_ai_insights and AzureAIAgentClient and project_endpoint:
            ai_analysis = await generate_ai_insights(
                transaction_data, customer_data, transaction_history, destination_analysis
            )
            ai_insights = ai_analysis.get("insights", "")
            confidence_score = ai_analysis.get("confidence", 0.8)

        logger.info(f"✅ Enhanced data enrichment completed for transaction {request.transaction_id}")
        
        return CustomerDataResponse(
            transaction_id=request.transaction_id,
            transaction_data=transaction_data,
            customer_data=customer_data,
            transaction_history=transaction_history,
            destination_analysis=destination_analysis,
            enriched_data=enriched_data,
            ai_insights=ai_insights,
            confidence_score=confidence_score,
            status="SUCCESS",
            message=f"Successfully enriched data with AI insights for transaction {request.transaction_id} and customer {customer_id}"
        )

    except Exception as e:
        error_msg = f"Error during enhanced data retrieval and enrichment: {str(e)}"
        logger.error(error_msg)
        return CustomerDataResponse(
            transaction_id=request.transaction_id,
            transaction_data={},
            customer_data={},
            transaction_history=[],
            destination_analysis=[],
            enriched_data={},
            ai_insights="",
            confidence_score=0.0,
            status="ERROR",
            message=error_msg
        )


async def generate_ai_insights(
    transaction_data: Dict[str, Any],
    customer_data: Dict[str, Any], 
    transaction_history: List[Dict[str, Any]],
    destination_analysis: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """Generate AI-powered insights about customer behavior and transaction patterns."""
    if not AzureAIAgentClient or not project_endpoint:
        return {"insights": "AI insights unavailable", "confidence": 0.0}
    
    try:
        # Create analysis prompt
        insights_prompt = create_insights_prompt(
            transaction_data, customer_data, transaction_history, destination_analysis
        )
        
        # Call Azure OpenAI
        # Create Azure AI Agent Client with proper credentials
        async with AzureCliCredential() as credential:
            client = AzureAIAgentClient(
                project_endpoint=project_endpoint,
                model_deployment_name=model_deployment_name,
                async_credential=credential
            )
            
            # Create AI agent for customer insights
            agent = client.create_agent(
                name="CustomerInsightsAI",
                instructions="""You are an expert financial analyst specializing in customer insights and risk assessment. 
                Analyze customer data comprehensively to provide actionable insights for financial institutions.
                Return your analysis in JSON format with:
                - risk_indicators: array of risk factors
                - recommendations: actionable recommendations  
                - insights: key customer insights
                - confidence: confidence score 0.0-1.0
                """
            )
            
            # Run the analysis
            response = await agent.run(insights_prompt)
            ai_response_text = response.content if hasattr(response, 'content') else str(response)
            logger.info(f"AI Insights Response: {ai_response_text[:200]}...")
            
            # Try to parse JSON response
            try:
                ai_insights = json.loads(ai_response_text)
            except json.JSONDecodeError:
                # Fallback parsing if not valid JSON
                ai_insights = {
                    "insights": ai_response_text,
                    "confidence": 0.7,
                    "key_patterns": [],
                "recommendations": []
            }
        
        return ai_insights
        
    except Exception as e:
        logger.error(f"Error generating AI insights: {e}")
        return {
            "insights": f"AI insights generation failed: {str(e)}",
            "confidence": 0.0,
            "key_patterns": [],
            "recommendations": []
        }


def create_insights_prompt(
    transaction_data: Dict[str, Any],
    customer_data: Dict[str, Any], 
    transaction_history: List[Dict[str, Any]],
    destination_analysis: List[Dict[str, Any]]
) -> str:
    """Create a detailed prompt for AI insights generation."""
    
    prompt = f"""
Analyze this customer's financial data and transaction patterns:

CURRENT TRANSACTION:
{json.dumps(transaction_data, indent=2)[:800]}

CUSTOMER PROFILE:
{json.dumps(customer_data, indent=2)[:600]}

TRANSACTION HISTORY SUMMARY:
- Total Transactions: {len(transaction_history)}
- Transaction History: {json.dumps(transaction_history[:5], indent=2)[:1000]}...

DESTINATION ANALYSIS:
- Transactions to Same Destination: {len(destination_analysis)}
- Pattern Analysis: {json.dumps(destination_analysis[:3], indent=2)[:800]}...

Please analyze:
1. Customer behavior patterns and trends
2. Transaction frequency and amount patterns  
3. Geographic preferences and risks
4. Seasonal or temporal patterns
5. Anomalies or unusual behaviors
6. Risk indicators for fraud detection
7. Opportunities for enhanced customer service

Provide actionable insights that would be valuable for fraud detection, customer service, and business intelligence.
"""
    
    return prompt.strip()


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
        enriched["normalized_fields"]["amount_usd"] = current_amount
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
    Main function to test the Enhanced Customer Data Agent Executor.
    """
    try:
        print(f"✅ Enhanced Customer Data Agent Executor Function Created Successfully")
        print(f"📋 Executor Type: {type(customer_data_executor_with_ai)}")
        print(f"🤖 AI Integration: {'Enabled' if AzureAIAgentClient and project_endpoint else 'Disabled'}")
        print(f"📝 Note: This is a Microsoft Agent Framework executor function with LLM integration.")
        
        # For demonstration, let's test the underlying data functions directly
        print(f"\n🔍 Testing enhanced data functions...")
        
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
                
                # Test AI insights generation if available
                if AzureAIAgentClient and project_endpoint:
                    ai_insights = await generate_ai_insights(
                        transaction_data, customer_data, transaction_history[:3], []
                    )
                    print(f"🤖 AI Insights Test: {'SUCCESS' if ai_insights.get('confidence', 0) > 0 else 'ERROR'}")
                    print(f"💭 AI Sample Insight: {ai_insights.get('insights', 'No insights')[:100]}...")
        
        # Show usage example
        print(f"\n🚀 USAGE EXAMPLE:")
        print(f"```python")
        print(f"from workflow import customer_data_executor_with_ai")
        print(f"from agent_framework import WorkflowBuilder")
        print(f"")
        print(f"workflow = WorkflowBuilder().add_executor(customer_data_executor_with_ai).build()")
        print(f"result = await workflow.run(CustomerDataRequest(..., use_ai_insights=True))")
        print(f"```")
        
        return customer_data_executor_with_ai
        
    except Exception as e:
        print(f"❌ Error testing Enhanced Customer Data Executor: {e}")
        return None


if __name__ == "__main__":
    asyncio.run(main())