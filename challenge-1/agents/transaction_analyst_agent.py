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
MLPredictionsPlugin = tools.MLPredictionsPlugin

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
        # Create AI Search tool
        ai_search = AzureAISearchTool(
            index_connection_id=sc_connection_id,
            index_name="regulations-policies",
            query_type=AzureAISearchQueryType.SIMPLE,
            top_k=5,
        )
        
        # Initialize ML Predictions plugin
        ml_predictions_plugin = MLPredictionsPlugin(
            endpoint=cosmos_endpoint,
            key=cosmos_key,
            database_name="FinancialComplianceDB"
        )
        
        # Create agent with ONLY AI Search tool (ML prediction functions will be provided via Semantic Kernel)
        transaction_agent = project_client.agents.create_agent(
            model=model_deployment_name,
            name="transaction-agent",
            instructions="""You are a Risk Analyser Agent evaluating financial transactions for potential fraud.
            Given a normalized transaction and customer profile, your task is to:
            - Apply fraud detection logic using both ML predictions (if available) and rule-based checks
            - Assign a fraud risk score from 0 to 100
            - Generate human-readable reasoning behind the score (e.g., "Transaction from unusual country", "High amount", "Previous fraud history")

            You have access to the following tools:
            - AI Search: Search regulations and policies for compliance checking

            You will also have access to the following Semantic Kernel functions:
            - get_ml_prediction: Get ML fraud prediction score for a specific transaction (0-1 scale with risk level)
            - get_all_ml_predictions: Get all ML prediction scores for batch analysis

            Please also consider:
            {
            "high_risk_countries": ["NG", "IR", "RU", "KP"],
            "high_amount_threshold_usd": 10000,
            "suspicious_account_age_days": 30,
            "low_device_trust_threshold": 0.5
            }

            Use the get_ml_prediction function to retrieve fraud scores for transactions you're analyzing.
            
            Output should be:
            - risk_score: integer (0-100)
            - risk_level: [Low, Medium, High]
            - reason: a brief explainable summary""",
            tools=ai_search.definitions,  # Only AI Search tool
            tool_resources=ai_search.resources,
        )
        print(f"Created transaction agent with ID: {transaction_agent.id}")
        print(f"Agent name: {transaction_agent.name}")
        return transaction_agent

if __name__ == "__main__":
    asyncio.run(main())

