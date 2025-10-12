"""
Enhanced Risk Analyzer Executor using Agent Registry

This executor uses pre-created agents by ID for better performance and consistency.
Combines rule-based fraud detection with AI analysis using reusable agents.
"""

import os
import json
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import logging

# Microsoft Agent Framework
from agent_framework import WorkflowContext, executor

# Azure services
from azure.cosmos import CosmosClient, exceptions
from azure.search.documents import SearchClient
from azure.identity import DefaultAzureCredential

# Pydantic for data validation
from pydantic import BaseModel, Field

# Import our agent registry
from agent_registry import run_agent_analysis, initialize_agents

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
cosmos_endpoint = os.environ.get("COSMOS_ENDPOINT")
cosmos_key = os.environ.get("COSMOS_KEY") 
cosmos_database_name = os.environ.get("COSMOS_DATABASE_NAME", "FinancialComplianceDB")
cosmos_container_name = os.environ.get("COSMOS_CONTAINER_NAME", "Transactions")

azure_search_endpoint = os.environ.get("AZURE_SEARCH_ENDPOINT")
azure_search_key = os.environ.get("AZURE_SEARCH_KEY")
azure_search_index = os.environ.get("AZURE_SEARCH_INDEX", "regulations")

project_endpoint = os.environ.get("AI_FOUNDRY_PROJECT_ENDPOINT")
model_deployment_name = os.environ.get("MODEL_DEPLOYMENT_NAME", "gpt-4o-mini")

# Initialize Azure services
cosmos_client = CosmosClient(cosmos_endpoint, cosmos_key) if cosmos_endpoint and cosmos_key else None
search_client = SearchClient(
    endpoint=azure_search_endpoint,
    index_name=azure_search_index, 
    credential=DefaultAzureCredential()
) if azure_search_endpoint else None

# Data Models
class RiskAnalysisRequest(BaseModel):
    """Request model for risk analysis with agent support."""
    transaction_id: str
    customer_data: Dict[str, Any] = Field(default_factory=dict)
    enriched_data: Dict[str, Any] = Field(default_factory=dict)
    use_ai_analysis: bool = True
    agent_key: str = "risk_analyzer"  # Which agent to use

class AIAnalysis(BaseModel):
    """AI analysis results from agent."""
    reasoning: str
    confidence: float
    risk_adjustment: int = 0
    additional_factors: List[str] = Field(default_factory=list)

class RiskAnalysisResponse(BaseModel):
    """Response model with agent-powered analysis."""
    transaction_id: str
    risk_score: int
    risk_level: str
    risk_factors: List[str]
    regulatory_findings: List[Dict[str, Any]]
    ai_analysis: Optional[AIAnalysis] = None
    agent_used: Optional[str] = None
    status: str = "SUCCESS"
    message: str = ""

# Risk Analysis Functions
def calculate_rule_based_risk(customer_data: Dict[str, Any]) -> Dict[str, Any]:
    """Calculate risk score using rule-based logic."""
    risk_score = 0
    risk_factors = []
    
    # High-risk countries
    HIGH_RISK_COUNTRIES = ["NG", "IR", "RU", "KP", "AF"]
    destination_country = customer_data.get("destination_country", "")
    if destination_country in HIGH_RISK_COUNTRIES:
        risk_score += 30
        risk_factors.append(f"HIGH_RISK_DESTINATION_COUNTRY_{destination_country}")
    
    # Amount-based risk
    amount = customer_data.get("amount", 0)
    if amount > 50000:
        risk_score += 40
        risk_factors.append("VERY_HIGH_AMOUNT")
    elif amount > 10000:
        risk_score += 25
        risk_factors.append("HIGH_AMOUNT")
    elif amount > 5000:
        risk_score += 15
        risk_factors.append("MEDIUM_AMOUNT")
    
    # Customer history
    days_since_registration = customer_data.get("days_since_registration", 365)
    if days_since_registration < 30:
        risk_score += 20
        risk_factors.append("NEW_CUSTOMER_ACCOUNT")
    
    # Previous fraud history
    if customer_data.get("previous_fraud_alerts", 0) > 0:
        risk_score += 35
        risk_factors.append("PREVIOUS_FRAUD_HISTORY")
    
    # Unusual transaction patterns
    if customer_data.get("transactions_last_24h", 0) > 5:
        risk_score += 15
        risk_factors.append("HIGH_FREQUENCY_TRANSACTIONS")
    
    # Determine risk level
    risk_level = "LOW"
    if risk_score >= 70:
        risk_level = "HIGH"
    elif risk_score >= 40:
        risk_level = "MEDIUM"
    
    return {
        "risk_score": min(risk_score, 100),
        "risk_level": risk_level,
        "risk_factors": risk_factors
    }

async def perform_regulatory_analysis(customer_data: Dict[str, Any], enriched_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Perform regulatory compliance checks."""
    findings = []
    
    # OFAC sanctions check
    customer_name = customer_data.get("customer_name", "").upper()
    destination_country = customer_data.get("destination_country", "")
    
    # Simulated OFAC check
    SANCTIONED_ENTITIES = ["SANCTIONED PERSON", "BLOCKED ENTITY", "DESIGNATED INDIVIDUAL"]
    for entity in SANCTIONED_ENTITIES:
        if entity in customer_name:
            findings.append({
                "regulation": "OFAC_SANCTIONS",
                "severity": "CRITICAL", 
                "description": f"Customer name matches OFAC sanctioned entity: {entity}",
                "action_required": "IMMEDIATE_BLOCK"
            })
    
    # Country-based sanctions
    SANCTIONED_COUNTRIES = ["IR", "KP", "RU"]
    if destination_country in SANCTIONED_COUNTRIES:
        findings.append({
            "regulation": "COUNTRY_SANCTIONS",
            "severity": "HIGH",
            "description": f"Transaction to sanctioned country: {destination_country}",
            "action_required": "ENHANCED_DUE_DILIGENCE"
        })
    
    # BSA reporting requirements
    amount = customer_data.get("amount", 0)
    if amount >= 10000:
        findings.append({
            "regulation": "BSA_REPORTING", 
            "severity": "MEDIUM",
            "description": f"Transaction amount ${amount:,.2f} requires BSA reporting",
            "action_required": "CTR_FILING_REQUIRED"
        })
    
    # Search regulatory documents if available
    if search_client:
        try:
            search_query = f"fraud detection {destination_country} sanctions compliance"
            results = search_client.search(search_query, top=3)
            
            for result in results:
                findings.append({
                    "regulation": "REGULATORY_GUIDANCE",
                    "severity": "INFO",
                    "description": f"Relevant regulation found: {result.get('title', 'N/A')[:100]}...",
                    "action_required": "REVIEW_GUIDANCE"
                })
        except Exception as e:
            logger.warning(f"Regulatory search failed: {e}")
    
    return findings

async def perform_ai_risk_analysis_with_agent(
    request: RiskAnalysisRequest, 
    rule_based_analysis: Dict[str, Any]
) -> Dict[str, Any]:
    """Perform AI-powered risk analysis using agent registry."""
    if not project_endpoint:
        return {"reasoning": "AI analysis unavailable - no project endpoint", "confidence": 0.0, "risk_adjustment": 0}
    
    try:
        # Create analysis prompt
        analysis_prompt = f"""
        Analyze this financial transaction for fraud risk:
        
        Transaction Details:
        - Transaction ID: {request.transaction_id}
        - Customer Data: {json.dumps(request.customer_data, indent=2)}
        - Rule-based Analysis: {json.dumps(rule_based_analysis, indent=2)}
        
        Please provide a JSON response with your fraud risk assessment including reasoning, confidence score, and any risk adjustments to the rule-based score.
        """
        
        # Use agent registry to run analysis
        ai_response_text = await run_agent_analysis(request.agent_key, analysis_prompt)
        logger.info(f"AI Analysis Response: {ai_response_text[:200]}...")
        
        # Try to parse JSON response
        try:
            ai_analysis = json.loads(ai_response_text)
        except json.JSONDecodeError:
            # Fallback parsing if not valid JSON
            ai_analysis = {
                "reasoning": ai_response_text,
                "confidence": 0.7,
                "risk_adjustment": 0,
                "additional_factors": []
            }
        
        return ai_analysis
        
    except Exception as e:
        logger.error(f"Error in AI risk analysis: {e}")
        return {
            "reasoning": f"AI analysis failed: {str(e)}",
            "confidence": 0.0,
            "risk_adjustment": 0,
            "additional_factors": []
        }

def create_ai_analysis_prompt(request: RiskAnalysisRequest, rule_analysis: Dict[str, Any]) -> str:
    """Create structured prompt for AI analysis."""
    return f"""
    Financial Transaction Fraud Analysis Request:
    
    Transaction ID: {request.transaction_id}
    
    Customer Profile:
    {json.dumps(request.customer_data, indent=2)}
    
    Rule-Based Analysis Results:
    - Risk Score: {rule_analysis['risk_score']}/100
    - Risk Level: {rule_analysis['risk_level']}  
    - Risk Factors: {rule_analysis['risk_factors']}
    
    Please analyze this transaction and provide detailed fraud risk assessment in JSON format.
    """

@executor
async def risk_analyzer_executor_with_agent_registry(
    request: RiskAnalysisRequest,
    ctx: WorkflowContext
) -> RiskAnalysisResponse:
    """
    Enhanced Risk Analyzer Executor using Agent Registry.
    
    Combines rule-based fraud detection with AI analysis using pre-created agents
    for better performance and consistency.
    """
    
    try:
        logger.info(f"🔍 Starting risk analysis for transaction {request.transaction_id}")
        
        # Step 1: Rule-based risk analysis
        rule_analysis = calculate_rule_based_risk(request.customer_data)
        logger.info(f"📊 Rule-based risk score: {rule_analysis['risk_score']}/100 ({rule_analysis['risk_level']})")
        
        # Step 2: Regulatory compliance analysis
        regulatory_findings = await perform_regulatory_analysis(
            request.customer_data, 
            request.enriched_data
        )
        logger.info(f"📋 Found {len(regulatory_findings)} regulatory findings")
        
        # Step 3: AI-powered analysis using agent registry
        ai_analysis_data = None
        agent_used = None
        
        if request.use_ai_analysis and project_endpoint:
            try:
                ai_result = await perform_ai_risk_analysis_with_agent(request, rule_analysis)
                ai_analysis_data = AIAnalysis(**ai_result)
                agent_used = request.agent_key
                
                # Apply AI risk adjustment
                adjusted_score = rule_analysis['risk_score'] + ai_result.get('risk_adjustment', 0)
                rule_analysis['risk_score'] = max(0, min(100, adjusted_score))
                
                logger.info(f"🤖 AI analysis complete. Confidence: {ai_analysis_data.confidence:.2f}")
                
            except Exception as e:
                logger.error(f"AI analysis failed: {e}")
                ai_analysis_data = AIAnalysis(
                    reasoning=f"AI analysis failed: {str(e)}",
                    confidence=0.0,
                    risk_adjustment=0
                )
        
        return RiskAnalysisResponse(
            transaction_id=request.transaction_id,
            risk_score=rule_analysis['risk_score'],
            risk_level=rule_analysis['risk_level'],
            risk_factors=rule_analysis['risk_factors'],
            regulatory_findings=regulatory_findings,
            ai_analysis=ai_analysis_data,
            agent_used=agent_used,
            status="SUCCESS",
            message=f"Risk analysis completed. Score: {rule_analysis['risk_score']}/100"
        )
        
    except Exception as e:
        error_msg = f"Risk analysis failed: {str(e)}"
        logger.error(error_msg)
        return RiskAnalysisResponse(
            transaction_id=request.transaction_id,
            risk_score=0,
            risk_level="UNKNOWN",
            risk_factors=[],
            regulatory_findings=[],
            status="ERROR",
            message=error_msg
        )

async def test_agent_registry_executor():
    """Test the agent registry executor."""
    try:
        print("🧪 Testing Risk Analyzer Executor with Agent Registry")
        
        # Initialize agents first
        await initialize_agents()
        
        # Test data
        sample_customer_data = {
            "customer_id": "CUST123456",
            "customer_name": "John Smith",
            "amount": 15000,
            "destination_country": "NG",
            "days_since_registration": 15,
            "previous_fraud_alerts": 0,
            "transactions_last_24h": 2
        }
        
        # Create test request
        request = RiskAnalysisRequest(
            transaction_id="TX1001",
            customer_data=sample_customer_data,
            use_ai_analysis=True,
            agent_key="risk_analyzer"
        )
        
        # Mock workflow context
        class MockContext:
            def __init__(self):
                pass
        
        ctx = MockContext()
        
        # Execute analysis
        result = await risk_analyzer_executor_with_agent_registry(request, ctx)
        
        print(f"📊 Analysis Results:")
        print(f"   Transaction ID: {result.transaction_id}")
        print(f"   Risk Score: {result.risk_score}/100")
        print(f"   Risk Level: {result.risk_level}")
        print(f"   Risk Factors: {len(result.risk_factors)} identified")
        print(f"   Regulatory Findings: {len(result.regulatory_findings)} items")
        print(f"   Agent Used: {result.agent_used}")
        
        if result.ai_analysis:
            print(f"   AI Confidence: {result.ai_analysis.confidence:.2f}")
            print(f"   AI Reasoning: {result.ai_analysis.reasoning[:100]}...")
        
        print(f"   Status: {result.status}")
        
        return result
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(test_agent_registry_executor())