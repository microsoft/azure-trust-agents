import asyncio
import os
import importlib.util
from pathlib import Path
from typing import Annotated
from azure.identity.aio import AzureCliCredential
from agent_framework import ChatAgent, HostedFileSearchTool
from agent_framework.azure import AzureAIAgentClient
from pydantic import Field
from dotenv import load_dotenv

load_dotenv(override=True)

# Configuration
project_endpoint = os.environ.get("AI_FOUNDRY_PROJECT_ENDPOINT")
model_deployment_name = os.environ.get("MODEL_DEPLOYMENT_NAME")
sc_connection_id = os.environ.get("AZURE_AI_CONNECTION_ID")

async def main():
    azure_ai_search_tool = HostedFileSearchTool(
        additional_properties={
            "index_name": "regulations-policies",
            "query_type": "simple",
            "top_k": 5,
        },
    )
    
    try:
        async with AzureCliCredential() as credential:
            # Create the AzureAIAgentClient
            client = AzureAIAgentClient(
                project_endpoint=project_endpoint,
                model_deployment_name=model_deployment_name,
                async_credential=credential
            )
            
            agent = client.create_agent(
                name="RiskAnalyserAgent",
                instructions="""You are a Risk Analyser Agent evaluating financial transactions for potential fraud.
                Given a normalized transaction and customer profile, your task is to:
                - Apply fraud detection logic using rule-based checks and regulatory compliance data
                - Assign a fraud risk score from 0 to 100
                - Generate human-readable reasoning behind the score (e.g., "Transaction from unusual country", "High amount", "Previous fraud history")

                You have access to the following tools:
                - Azure AI Search: Search regulations and policies for compliance checking and fraud detection rules

                Please also consider these risk factors:
                {
                "high_risk_countries": ["NG", "IR", "RU", "KP"],
                "high_amount_threshold_usd": 10000,
                "suspicious_account_age_days": 30,
                "low_device_trust_threshold": 0.5
                }

                Use the Azure AI Search to look up relevant regulations, compliance rules, and fraud detection patterns that apply to the transaction.
                
                Output should be:
                - risk_score: integer (0-100)
                - risk_level: [Low, Medium, High]
                - reason: a brief explainable summary with references to relevant regulations or policies found via search""",
                tools=[azure_ai_search_tool],
            )

            # Test the agent with a simple query
            print("\n🧪 Testing the agent with a sample query...")
            try:
                result = await agent.run("Hello, tell me about the main KYC regulations I should consider for fraud detection?")
                print(f"✅ Agent response: {result.text}")
            except Exception as test_error:
                print(f"⚠️  Agent test failed (but agent was still created): {test_error}")
            
            return agent
    except Exception as e:
        print(f"❌ Error creating agent: {e}")
        print("Make sure you have run 'az login' and have proper Azure credentials configured.")
        return None

if __name__ == "__main__":
    asyncio.run(main())

