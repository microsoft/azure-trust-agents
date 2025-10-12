import asyncio
import os
from typing import Annotated, List
from azure.identity.aio import AzureCliCredential
from agent_framework.azure import AzureAIAgentClient
from agent_framework import SequentialBuilder, ChatAgent
from dotenv import load_dotenv
import logging

# Import tools from our tools package
from tools import (
    get_customer_sync,
    get_transaction_sync, 
    get_transactions_by_customer_sync,
    get_transactions_by_destination_sync,
    parse_risk_analysis_result,
    generate_audit_report_from_risk_analysis
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv(override=True)

# Configuration
project_endpoint = os.environ.get("AI_FOUNDRY_PROJECT_ENDPOINT")
model_deployment_name = os.environ.get("MODEL_DEPLOYMENT_NAME")

async def sequential_builder_demo():
    """
    Sequential orchestration using SequentialBuilder pattern with loaded agents.    
    """
    # Get agent IDs from environment
    risk_agent_id = os.environ.get("RISK_ANALYSER_AGENT_ID")
    customer_agent_id = os.environ.get("CUSTOMER_DATA_AGENT_ID")
    compliance_agent_id = os.environ.get("COMPLIANCE_REPORT_AGENT_ID")

    async with AzureCliCredential() as credential:
        # Create separate clients for each agent (bound to existing agent IDs)
        customer_client = AzureAIAgentClient(
            project_endpoint=project_endpoint,
            model_deployment_name=model_deployment_name,
            async_credential=credential,
            agent_id=customer_agent_id
        )
        
        risk_client = AzureAIAgentClient(
            project_endpoint=project_endpoint,
            model_deployment_name=model_deployment_name,
            async_credential=credential,
            agent_id=risk_agent_id
        )
        
        compliance_client = AzureAIAgentClient(
            project_endpoint=project_endpoint,
            model_deployment_name=model_deployment_name,
            async_credential=credential,
            agent_id=compliance_agent_id
        )
        
        try:            
            customer_tools = [get_customer_sync, get_transaction_sync, get_transactions_by_customer_sync, get_transactions_by_destination_sync]
            async with customer_client as client1:
                async with risk_client as client2:
                    async with compliance_client as client3:
                        # Create Customer Data Agent without tools to avoid thread issues in SequentialBuilder
                        # The agent will be instructed to use available tools through natural language
                        data_agent = ChatAgent(
                            chat_client=client1,
                            model_id=model_deployment_name,
                            store=True
                        )
                        data_agent.name = "Customer Data Agent"
                        data_agent.id = customer_agent_id                        
                        # Create Risk Analyzer Agent 
                        risk_agent = ChatAgent(
                            chat_client=client2,
                            model_id=model_deployment_name,
                            store=True
                        )
                        risk_agent.name = "Risk Analyzer Agent"  
                        risk_agent.id = risk_agent_id                        
                        compliance_tools = [parse_risk_analysis_result, generate_audit_report_from_risk_analysis]
                        compliance_agent = ChatAgent(
                            chat_client=client3,
                            model_id=model_deployment_name,
                            tools=compliance_tools,
                            store=True
                        )
                        compliance_agent.name = "Compliance Report Agent"
                        compliance_agent.id = compliance_agent_id
                        print(f"✅ Created: Compliance Report Agent with audit tools")
                    
                        # Build sequential workflow using SequentialBuilder (Microsoft docs pattern)
                        print(f"\n🔧 Building sequential workflow with SequentialBuilder...")
                        workflow = SequentialBuilder().participants([data_agent, risk_agent, compliance_agent]).build()
                        print(f"✅ Sequential workflow built successfully with 3 agents")
                    
                        transaction_id = "TX1001"
                        print(f"🎯 Analyzing transaction: {transaction_id}")
                        
                        # Run the sequential workflow
                        initial_prompt = f"""Transaction Analysis Request: {transaction_id}
                                
                        Please perform comprehensive fraud detection analysis of transaction {transaction_id}:

                        1. First agent (Customer Data Agent): 
                        - Fetch transaction details using get_transaction
                        - Get customer profile using get_customer
                        - Retrieve transaction history using get_transactions_by_customer
                        - Normalize and structure all data for fraud analysis
                        - Pass enriched data to next agent

                        2. Second agent (Risk Analyzer Agent):
                        - Receive enriched data from previous agent
                        - Use Azure AI Search for regulatory compliance lookup
                        - Apply fraud detection rules and scoring
                        - Calculate risk score (0-100) and risk level
                        - Provide explainable reasoning with regulatory references
                        - Pass complete risk analysis to next agent

                        3. Third agent (Compliance Report Agent):
                        - Receive complete risk analysis from previous agent
                        - Parse risk analysis using parse_risk_analysis_result
                        - Generate formal audit report using generate_audit_report_from_risk_analysis
                        - Provide compliance recommendations and regulatory implications
                        - Create executive summary with audit conclusions

                        Execute this sequential workflow for comprehensive fraud detection and compliance reporting."""
                        
                        workflow_result = await workflow.run(initial_prompt)
                        print(f"✅ Sequential workflow completed")
                        
                        # Results
                        print(f"\n📋 Sequential Workflow Results")
                        print("="*60)
                        # Handle different possible result formats
                        if hasattr(workflow_result, 'content'):
                            result_text = str(workflow_result.content)
                        elif hasattr(workflow_result, 'message'):
                            result_text = str(workflow_result.message)
                        elif hasattr(workflow_result, 'response'):
                            result_text = str(workflow_result.response)
                        else:
                            result_text = str(workflow_result)
                        
                        result_preview = result_text[:800] + "..." if len(result_text) > 800 else result_text
                        print(f"🎯 WORKFLOW RESULT: {result_preview}")
    
                
                        return workflow_result
            
        except Exception as agent_error:
            print(f"❌ Error with SequentialBuilder: {agent_error}")
        finally:
            # Clean up clients (they are already closed by the async context managers)
            pass

async def main():
    await sequential_builder_demo()


if __name__ == "__main__":
    asyncio.run(main())