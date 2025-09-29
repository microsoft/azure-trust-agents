import asyncio
import os
from azure.identity.aio import DefaultAzureCredential
from semantic_kernel import Kernel
from semantic_kernel.agents import AzureAIAgent, ChatCompletionAgent, GroupChatOrchestration, RoundRobinGroupChatManager
from semantic_kernel.agents.runtime import InProcessRuntime
from semantic_kernel.connectors.ai.open_ai import AzureChatCompletion
from dotenv import load_dotenv
from tools import CustomerDataPlugin, TransactionDataPlugin, MLPredictionsPlugin

load_dotenv(override=True)

async def get_agents():
    """Load the specialized agents by their IDs from Azure AI Foundry."""
    
    print("🔧 Loading specialized fraud detection agents...")
    
    # Get environment variables
    endpoint = os.environ.get("AI_FOUNDRY_PROJECT_ENDPOINT")
    data_agent_id = os.environ.get("DATA_INGESTION_AGENT_ID")
    transaction_agent_id = os.environ.get("TRANSACTION_ANALYST_AGENT_ID")
    cosmos_endpoint = os.environ.get("COSMOS_ENDPOINT")
    cosmos_key = os.environ.get("COSMOS_KEY")
    azure_openai_endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT")
    azure_openai_key = os.environ.get("AZURE_OPENAI_KEY")
    azure_openai_deployment = os.environ.get("AZURE_OPENAI_DEPLOYMENT_NAME")
    
    if not data_agent_id or not transaction_agent_id:
        raise ValueError(
            "Please set DATA_INGESTION_AGENT_ID and TRANSACTION_ANALYST_AGENT_ID "
            "environment variables with the agent IDs created by running the agent scripts."
        )
    
    if not azure_openai_endpoint or not azure_openai_key or not azure_openai_deployment:
        raise ValueError(
            "Please set AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_KEY, and AZURE_OPENAI_DEPLOYMENT_NAME "
            "environment variables for the ChatCompletionAgent."
        )
    
    # Create Cosmos DB plugin instances for different agents
    customer_plugin = CustomerDataPlugin(
        endpoint=cosmos_endpoint,
        key=cosmos_key,
        database_name="FinancialComplianceDB"
    )
    transaction_plugin = TransactionDataPlugin(
        endpoint=cosmos_endpoint,
        key=cosmos_key,
        database_name="FinancialComplianceDB"
    )
    ml_predictions_plugin = MLPredictionsPlugin(
        endpoint=cosmos_endpoint,
        key=cosmos_key,
        database_name="FinancialComplianceDB"
    )
    
    # Create kernels for each agent with their respective plugins
    data_kernel = Kernel()
    data_kernel.add_plugin(customer_plugin, plugin_name="CustomerData")
    data_kernel.add_plugin(transaction_plugin, plugin_name="TransactionData")
    
    transaction_kernel = Kernel()
    transaction_kernel.add_plugin(ml_predictions_plugin, plugin_name="MLPredictions")
    
    agents = []
    
    async with DefaultAzureCredential() as creds:
        client = AzureAIAgent.create_client(credential=creds, endpoint=endpoint)
        print("✅ Connected to AI Foundry endpoint.")
        
        # Load Data Ingestion Agent with Cosmos DB plugins
        print(f"🔍 Loading Data Ingestion Agent (ID: {data_agent_id})...")
        data_agent_definition = await client.agents.get_agent(agent_id=data_agent_id)
        
        data_agent = AzureAIAgent(
            client=client,
            definition=data_agent_definition,
            description="Agent that ingests and normalizes transaction and customer data.",
            kernel=data_kernel  # Pass kernel with plugins instead of plugins parameter
        )
        
        # Load Transaction Analyst Agent with ML predictions plugin
        print(f"⚠️ Loading Transaction Analyst Agent (ID: {transaction_agent_id})...")
        transaction_agent_definition = await client.agents.get_agent(agent_id=transaction_agent_id)
        
        transaction_agent = AzureAIAgent(
            client=client,
            definition=transaction_agent_definition,
            description="Agent that analyzes transactions for fraud risk.",
            kernel=transaction_kernel  # Pass kernel with plugins instead of plugins parameter
        )
        
        # Create Fraud Decision Approver Agent (ChatCompletionAgent)
        print("🤖 Creating Fraud Decision Approver Agent...")
        approver_agent = ChatCompletionAgent(
            name="FraudDecisionApprover",
            description="Final decision maker on fraud detection based on analysis from data ingestion and transaction analyst agents.",
            instructions=(
                """You are the final decision maker for fraud detection analysis. 
                
                Your role is to:
                1. Review the data provided by the Data Ingestion Agent (customer and transaction details)
                2. Consider the fraud risk analysis from the Transaction Analyst Agent (fraud scores and risk levels)
                3. Make a final determination on whether the transaction is fraudulent
                4. Provide clear reasoning for your decision
                
                Decision Criteria:
                - FRAUD: High fraud score (>0.7) or multiple risk indicators present
                - SUSPICIOUS: Medium fraud score (0.4-0.7) or some risk indicators - recommend further investigation
                - LEGITIMATE: Low fraud score (<0.4) and no significant risk indicators
                
                Always provide:
                - Decision: FRAUD / SUSPICIOUS / LEGITIMATE
                - Risk Level: HIGH / MEDIUM / LOW
                - Reasoning: Specific factors that led to your decision
                - Recommendation: Next steps (block transaction, investigate, approve, etc.)
                
                Base all decisions strictly on the data and analysis provided by the other agents.
                """
            ),
            service=AzureChatCompletion(
                deployment_name=azure_openai_deployment,
                api_key=azure_openai_key,
                endpoint=azure_openai_endpoint,
            ),
        )
        
        agents = [data_agent, transaction_agent, approver_agent]
        
        print("✅ All agents loaded successfully!")
        return agents, client

async def agent_response_callback(message) -> None:
    """Callback to print agent responses during orchestration."""
    print(f"# {message.name}\n{message.content}")

async def orchestrate_fraud_detection(transaction_id: str, customer_id: str):
    """Orchestrate multiple agents to analyze a transaction for fraud."""
    
    print(f"🚀 Starting Fraud Detection Orchestration")
    print(f"Transaction ID: {transaction_id}, Customer ID: {customer_id}")
    print(f"{'='*80}")
    
    # Load our specialized agents
    agents, client = await get_agents()
    
    group_chat_orchestration = GroupChatOrchestration(
        members=agents,
        manager=RoundRobinGroupChatManager(max_rounds=4),
        agent_response_callback=agent_response_callback,
    )
    
    # Create and start runtime
    runtime = InProcessRuntime()
    runtime.start()
    
    try:
        # Create task that instructs agents to analyze the transaction
        task = (
            f"Analyze transaction {transaction_id} for customer {customer_id}. "
            f"First, fetch and normalize the transaction and customer data. "
            f"Then, perform fraud risk analysis and provide a risk score and reasoning."
        )
        
        # Invoke orchestration
        orchestration_result = await group_chat_orchestration.invoke(
            task=task,
            runtime=runtime
        )
        
        # Get result
        result = await orchestration_result.get(timeout=300)  # 5 minute timeout
        
        print(f"\n✅ Fraud Detection Orchestration Complete!")
        print(result)
        return result
        
    except Exception as e:
        print(f"❌ Error during orchestration: {str(e)}")
        raise
        
    finally:
        await runtime.stop_when_idle()
        print(f"\n🧹 Orchestration cleanup complete.")

if __name__ == "__main__":
    # Example usage with real data from your Cosmos DB
    # You can change these to any transaction_id and customer_id from your database
    transaction_id = "TX1001"
    customer_id = "CUST1001"
    
    results = asyncio.run(orchestrate_fraud_detection(transaction_id, customer_id))
    print(f"\n📊 Final Results:")
    print(results)
