"""
Agent Registry - Create and manage reusable AI agents by ID

This module creates agents once and stores their IDs for reuse across executors.
This approach provides better performance, consistency, and resource management.
"""

import os
import json
import asyncio
from typing import Dict, Optional
from agent_framework.azure import AzureAIAgentClient
from azure.identity.aio import AzureCliCredential
import logging

logger = logging.getLogger(__name__)

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Configuration
project_endpoint = os.environ.get("AI_FOUNDRY_PROJECT_ENDPOINT")
model_deployment_name = os.environ.get("MODEL_DEPLOYMENT_NAME", "gpt-4o-mini")
azure_ai_connection_id = os.environ.get("AZURE_AI_CONNECTION_ID")

# Pre-existing Agent IDs from .env (already created!)
EXISTING_AGENT_IDS = {
    "risk_analyzer": os.environ.get("RISK_ANALYSER_AGENT_ID"),
    "customer_insights": os.environ.get("CUSTOMER_DATA_AGENT_ID"), 
    "compliance_analysis": os.environ.get("COMPLIANCE_REPORT_AGENT_ID")
}

# Store agent IDs (in production, use persistent storage like Azure Storage or Cosmos DB)
AGENT_IDS_FILE = "/tmp/agent_ids.json"

class AgentRegistry:
    """Registry for managing reusable AI agents."""
    
    def __init__(self):
        self.agent_ids: Dict[str, str] = self._load_agent_ids()
        self.client: Optional[AzureAIAgentClient] = None
    
    def _load_agent_ids(self) -> Dict[str, str]:
        """Load agent IDs from persistent storage."""
        try:
            if os.path.exists(AGENT_IDS_FILE):
                with open(AGENT_IDS_FILE, 'r') as f:
                    return json.load(f)
        except Exception as e:
            logger.warning(f"Could not load agent IDs: {e}")
        return {}
    
    def _save_agent_ids(self):
        """Save agent IDs to persistent storage."""
        try:
            with open(AGENT_IDS_FILE, 'w') as f:
                json.dump(self.agent_ids, f)
        except Exception as e:
            logger.error(f"Could not save agent IDs: {e}")
    
    async def get_client(self) -> AzureAIAgentClient:
        """Get or create Azure AI client."""
        if not self.client:
            async with AzureCliCredential() as credential:
                self.client = AzureAIAgentClient(
                    project_endpoint=project_endpoint,
                    model_deployment_name=model_deployment_name,
                    async_credential=credential
                )
        return self.client
    
    async def get_or_create_agent(self, agent_key: str, agent_name: str = None, instructions: str = None) -> str:
        """Get existing agent ID or create new agent and return ID."""
        
        # First, check if we have a pre-existing agent ID from environment
        if agent_key in EXISTING_AGENT_IDS and EXISTING_AGENT_IDS[agent_key]:
            agent_id = EXISTING_AGENT_IDS[agent_key]
            self.agent_ids[agent_key] = agent_id
            logger.info(f"✅ Using pre-existing agent '{agent_key}' with ID: {agent_id}")
            return agent_id
        
        # Check if we already have this agent in our registry
        if agent_key in self.agent_ids:
            logger.info(f"✅ Using cached agent '{agent_key}' with ID: {self.agent_ids[agent_key]}")
            return self.agent_ids[agent_key]
        
        # Create new agent (only if agent_name and instructions provided)
        if not agent_name or not instructions:
            raise ValueError(f"Agent '{agent_key}' not found and no name/instructions provided to create new agent")
        
        try:
            client = await self.get_client()
            
            agent = client.create_agent(
                name=agent_name,
                instructions=instructions
            )
            
            agent_id = agent.id
            self.agent_ids[agent_key] = agent_id
            self._save_agent_ids()
            
            logger.info(f"🆕 Created new agent '{agent_key}' with ID: {agent_id}")
            return agent_id
            
        except Exception as e:
            logger.error(f"Failed to create agent '{agent_key}': {e}")
            raise
    
    async def run_agent(self, agent_id: str, prompt: str) -> str:
        """Run an agent by ID with the given prompt."""
        try:
            client = await self.get_client()
            
            # Get agent by ID and run
            agent = client.get_agent(agent_id)
            response = await agent.run(prompt)
            
            # Handle response based on actual response structure
            if hasattr(response, 'content'):
                return response.content
            elif hasattr(response, 'message') and hasattr(response.message, 'content'):
                return response.message.content
            else:
                return str(response)
                
        except Exception as e:
            logger.error(f"Failed to run agent {agent_id}: {e}")
            raise
    
    async def list_agents(self) -> Dict[str, str]:
        """List all registered agents."""
        return self.agent_ids.copy()
    
    async def cleanup(self):
        """Cleanup resources."""
        if self.client:
            # Close client if it has a close method
            if hasattr(self.client, 'close'):
                await self.client.close()

# Global registry instance
agent_registry = AgentRegistry()

# Pre-defined agent configurations
AGENT_CONFIGS = {
    "risk_analyzer": {
        "name": "RiskAnalyzerAI",
        "instructions": """You are an expert fraud detection AI analyzing financial transactions. 
        Provide detailed reasoning for fraud risk assessment, considering patterns, anomalies, 
        and contextual factors. Return your analysis in JSON format with:
        - reasoning: detailed explanation (string)
        - confidence: confidence score 0.0-1.0 (float)
        - risk_adjustment: adjustment to rule-based score -20 to +20 (int)
        - additional_factors: any additional risk factors identified (array)
        """
    },
    "customer_insights": {
        "name": "CustomerInsightsAI", 
        "instructions": """You are an expert financial analyst specializing in customer insights and risk assessment. 
        Analyze customer data comprehensively to provide actionable insights for financial institutions.
        Return your analysis in JSON format with:
        - risk_indicators: array of risk factors
        - recommendations: actionable recommendations  
        - insights: key customer insights
        - confidence: confidence score 0.0-1.0
        """
    },
    "compliance_analysis": {
        "name": "ComplianceAnalysisAI",
        "instructions": """You are an expert compliance officer and regulatory analyst specializing in financial compliance and audit reporting.
        
        Analyze the provided compliance data and generate:
        - Detailed regulatory reasoning and justification
        - Risk assessment from a compliance perspective  
        - Additional compliance actions and recommendations
        - Regulatory implications and requirements
        
        Return your analysis in JSON format with:
        - reasoning: detailed compliance reasoning (string)
        - confidence: confidence score 0.0-1.0 (float)
        - additional_actions: extra compliance actions needed (array)
        - regulatory_implications: key regulatory concerns (array)
        - recommendations: strategic compliance recommendations (array)
        """
    }
}

async def initialize_agents():
    """Initialize all pre-configured agents using existing IDs where available."""
    logger.info("🚀 Initializing AI agents...")
    
    for agent_key, config in AGENT_CONFIGS.items():
        try:
            agent_id = await agent_registry.get_or_create_agent(
                agent_key,
                config["name"], 
                config["instructions"]
            )
            logger.info(f"✅ Agent '{agent_key}' ready with ID: {agent_id}")
        except Exception as e:
            logger.error(f"❌ Failed to initialize agent '{agent_key}': {e}")
    
    return agent_registry

async def get_agent_id(agent_key: str) -> str:
    """Get agent ID by key."""
    # First try to get existing agent ID
    if agent_key in EXISTING_AGENT_IDS and EXISTING_AGENT_IDS[agent_key]:
        return EXISTING_AGENT_IDS[agent_key]
    
    # Fall back to creating new agent if config exists
    if agent_key not in AGENT_CONFIGS:
        raise ValueError(f"Unknown agent key: {agent_key}")
    
    config = AGENT_CONFIGS[agent_key]
    return await agent_registry.get_or_create_agent(
        agent_key,
        config["name"], 
        config["instructions"]
    )

async def run_agent_analysis(agent_key: str, prompt: str) -> str:
    """Run analysis using agent by key."""
    agent_id = await get_agent_id(agent_key)
    return await agent_registry.run_agent(agent_id, prompt)

# Test function
async def test_agent_registry():
    """Test the agent registry functionality."""
    print("🧪 Testing Agent Registry")
    
    try:
        # Initialize agents
        registry = await initialize_agents()
        
        # Test risk analysis
        test_prompt = "Analyze this transaction: Amount: $15000, Destination: Nigeria, Customer: New account (1 month old)"
        
        result = await run_agent_analysis("risk_analyzer", test_prompt)
        print(f"🤖 Risk Analysis Result: {result[:200]}...")
        
        # List all agents
        agents = await registry.list_agents()
        print(f"📋 Registered Agents: {list(agents.keys())}")
        
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False

if __name__ == "__main__":
    asyncio.run(test_agent_registry())