"""
Enhanced Risk Analyzer Agent Executor with LLM Integration for Microsoft Agent Framework.

This executor combines rule-based fraud detection with AI-powered analysis using Azure OpenAI models.
"""

import asyncio
import os
import logging
from typing import Dict, Any, List
from agent_framework import (
    Executor,
    WorkflowContext,
    executor,
    HostedFileSearchTool
)
from pydantic import Field, BaseModel
from dotenv import load_dotenv
import json

# Azure AI Foundry integration
try:
    from azure.identity.aio import AzureCliCredential
    from agent_framework.azure import AzureAIAgentClient
    from agent_framework import ChatAgent
except ImportError:
    AzureCliCredential = None
    AzureAIAgentClient = None
    ChatAgent = None

load_dotenv(override=True)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
project_endpoint = os.environ.get("AI_FOUNDRY_PROJECT_ENDPOINT")
model_deployment_name = os.environ.get("MODEL_DEPLOYMENT_NAME", "gpt-4o-mini")
sc_connection_id = os.environ.get("AZURE_AI_CONNECTION_ID")

# Data Models
class RiskAnalysisRequest(BaseModel):
    """Request model for risk analysis operations."""
    transaction_id: str
    customer_data: Dict[str, Any] = Field(default_factory=dict)
    enriched_data: Dict[str, Any] = Field(default_factory=dict)
    use_ai_analysis: bool = True


class RiskAnalysisResponse(BaseModel):
    """Response model for risk analysis operations."""
    transaction_id: str
    risk_score: int
    risk_level: str
    risk_factors: List[str]
    regulatory_findings: List[str]
    detailed_analysis: Dict[str, Any]
    ai_reasoning: str = ""
    confidence_score: float = 0.0
    status: str
    message: str


# Initialize Azure AI Search tool for regulatory lookup (optional)
try:
    azure_search_endpoint = os.environ.get("AZURE_SEARCH_ENDPOINT")
    azure_search_key = os.environ.get("AZURE_SEARCH_KEY") 
    azure_search_index = os.environ.get("AZURE_SEARCH_INDEX", "regulations")
    
    if azure_search_endpoint and azure_search_key:
        search_tool = HostedFileSearchTool(
            connection_id=azure_search_endpoint,
            index_name=azure_search_index
        )
        logger.info("✅ Initialized Azure AI Search tool for regulatory analysis")
    else:
        search_tool = None
        logger.info("⚠️ Azure AI Search not configured, using fallback regulatory analysis")
except Exception as e:
    search_tool = None
    logger.warning(f"Azure AI Search initialization failed: {e}")

# Initialize Azure AI Foundry client
ai_agent_client = None
if AzureAIAgentClient and project_endpoint:
    try:
        # We'll initialize the client in the function when needed with proper credential
        logger.info("✅ Azure AI Foundry configuration available for AI-powered risk analysis")
    except Exception as e:
        logger.warning(f"Azure AI Foundry initialization failed: {e}")


# Risk Configuration
RISK_CONFIG = {
    "HIGH_RISK_COUNTRIES": ["IR", "KP", "AF", "SY"],
    "SANCTIONS_COUNTRIES": ["IR", "KP", "CU", "SY"],
    "HIGH_AMOUNT_THRESHOLD": 10000,
    "UNUSUAL_AMOUNT_MULTIPLIER": 3.0,
    "MIN_ACCOUNT_AGE_DAYS": 30,
    "MIN_DEVICE_TRUST_SCORE": 0.7
}


@executor
async def risk_analyzer_executor_with_ai(
    request: RiskAnalysisRequest,
    ctx: WorkflowContext
) -> RiskAnalysisResponse:
    """
    Enhanced Risk Analyzer Agent Executor with LLM integration for comprehensive fraud detection.
    
    Combines rule-based analysis with AI-powered reasoning for more accurate fraud detection.
    
    Args:
        request: Risk analysis request with transaction and customer data
        ctx: Workflow context
        
    Returns:
        RiskAnalysisResponse: Complete risk analysis with AI reasoning
    """
    logger.info(f"🔍 Starting enhanced risk analysis for transaction: {request.transaction_id}")
    
    try:
        # Step 1: Rule-based risk analysis (existing logic)
        rule_based_analysis = await perform_rule_based_analysis(request)
        
        # Step 2: AI-powered analysis (new enhancement)
        ai_analysis = None
        if request.use_ai_analysis and AzureAIAgentClient and project_endpoint:
            ai_analysis = await perform_ai_risk_analysis(request, rule_based_analysis)
        
        # Step 3: Regulatory compliance analysis
        regulatory_findings = await perform_regulatory_analysis(
            request.customer_data, request.enriched_data
        )
        
        # Step 4: Combine analyses for final risk assessment
        final_analysis = combine_rule_based_and_ai_analysis(
            rule_based_analysis, ai_analysis, regulatory_findings
        )
        
        # Step 5: Generate detailed analysis and explanation
        detailed_analysis = create_detailed_analysis(
            request.customer_data,
            request.enriched_data, 
            final_analysis["risk_factors"],
            regulatory_findings
        )
        
        logger.info(f"✅ Enhanced risk analysis completed: {final_analysis['risk_level']} ({final_analysis['risk_score']}/100)")
        
        return RiskAnalysisResponse(
            transaction_id=request.transaction_id,
            risk_score=final_analysis["risk_score"],
            risk_level=final_analysis["risk_level"],
            risk_factors=final_analysis["risk_factors"],
            regulatory_findings=regulatory_findings,
            detailed_analysis=detailed_analysis,
            ai_reasoning=ai_analysis.get("reasoning", "") if ai_analysis else "",
            confidence_score=ai_analysis.get("confidence", 0.0) if ai_analysis else final_analysis.get("confidence", 0.8),
            status="SUCCESS",
            message=f"Enhanced risk analysis completed for transaction {request.transaction_id}"
        )

    except Exception as e:
        error_msg = f"Error during enhanced risk analysis: {str(e)}"
        logger.error(error_msg)
        return RiskAnalysisResponse(
            transaction_id=request.transaction_id,
            risk_score=0,
            risk_level="UNKNOWN",
            risk_factors=[],
            regulatory_findings=[],
            detailed_analysis={},
            ai_reasoning="",
            confidence_score=0.0,
            status="ERROR",
            message=error_msg
        )


async def perform_rule_based_analysis(request: RiskAnalysisRequest) -> Dict[str, Any]:
    """Perform traditional rule-based risk analysis."""
    try:
        risk_score = 0
        risk_factors = []
        
        # Extract data from request
        customer_data = request.customer_data
        enriched_data = request.enriched_data
        
        # Get transaction details
        transaction = enriched_data.get("transaction", {})
        customer = enriched_data.get("customer", {})
        
        transaction_amount = transaction.get("amount", customer_data.get("transaction_amount", 0))
        destination_country = transaction.get("destination_country", customer_data.get("destination_country", ""))
        customer_country = customer.get("country", "")
        
        # Rule 1: High-risk destination countries
        if destination_country in RISK_CONFIG["HIGH_RISK_COUNTRIES"]:
            risk_score += 25
            risk_factors.append("HIGH_RISK_DESTINATION_COUNTRY")
            
        if destination_country in RISK_CONFIG["SANCTIONS_COUNTRIES"]:
            risk_score += 30
            risk_factors.append("SANCTIONS_DESTINATION_COUNTRY")
        
        # Rule 2: Transaction amount analysis
        if transaction_amount > RISK_CONFIG["HIGH_AMOUNT_THRESHOLD"]:
            risk_score += 20
            risk_factors.append("HIGH_TRANSACTION_AMOUNT")
        
        # Rule 3: Customer behavior patterns
        past_fraud_flags = customer.get("past_fraud_flags", customer_data.get("past_fraud_flags", 0))
        if past_fraud_flags > 0:
            risk_score += 25
            risk_factors.append("PREVIOUS_FRAUD_HISTORY")
        
        account_age_days = customer.get("account_age_days", customer_data.get("account_age_days", 365))
        if account_age_days < RISK_CONFIG["MIN_ACCOUNT_AGE_DAYS"]:
            risk_score += 15
            risk_factors.append("NEW_ACCOUNT")
        
        device_trust_score = customer.get("device_trust_score", customer_data.get("device_trust_score", 1.0))
        if device_trust_score < RISK_CONFIG["MIN_DEVICE_TRUST_SCORE"]:
            risk_score += 10
            risk_factors.append("LOW_DEVICE_TRUST")
        
        # Rule 4: Cross-border transaction
        if customer_country and destination_country and customer_country != destination_country:
            risk_score += 10
            risk_factors.append("CROSS_BORDER_TRANSACTION")
        
        # Determine risk level
        if risk_score >= 70:
            risk_level = "HIGH"
        elif risk_score >= 40:
            risk_level = "MEDIUM"
        else:
            risk_level = "LOW"
        
        return {
            "risk_score": min(risk_score, 100),
            "risk_level": risk_level,
            "risk_factors": risk_factors,
            "confidence": 0.8,
            "method": "rule_based"
        }
        
    except Exception as e:
        logger.error(f"Error in rule-based analysis: {e}")
        return {
            "risk_score": 50,
            "risk_level": "MEDIUM",
            "risk_factors": ["ANALYSIS_ERROR"],
            "confidence": 0.3,
            "method": "rule_based",
            "error": str(e)
        }


async def perform_ai_risk_analysis(
    request: RiskAnalysisRequest, 
    rule_based_analysis: Dict[str, Any]
) -> Dict[str, Any]:
    """Perform AI-powered risk analysis using Azure AI Foundry."""
    if not AzureAIAgentClient or not project_endpoint:
        return {"reasoning": "AI analysis unavailable", "confidence": 0.0, "risk_adjustment": 0}
    
    try:
        # Prepare data for AI analysis
        analysis_prompt = create_ai_analysis_prompt(request, rule_based_analysis)
        
        # Create Azure AI Agent Client with proper credentials
        async with AzureCliCredential() as credential:
            client = AzureAIAgentClient(
                project_endpoint=project_endpoint,
                model_deployment_name=model_deployment_name,
                async_credential=credential
            )
            
            # Create AI agent for risk analysis
            agent = client.create_agent(
                name="RiskAnalysisAI",
                instructions="""You are an expert fraud detection AI analyzing financial transactions. 
                Provide detailed reasoning for fraud risk assessment, considering patterns, anomalies, 
                and contextual factors. Return your analysis in JSON format with:
                - reasoning: detailed explanation (string)
                - confidence: confidence score 0.0-1.0 (float)  
                - risk_adjustment: adjustment to rule-based score -20 to +20 (int)
                - additional_factors: any additional risk factors identified (array)
                """
            )
            
            # Run the analysis
            response = await agent.run(analysis_prompt)
            ai_response_text = response.content if hasattr(response, 'content') else str(response)
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


def create_ai_analysis_prompt(
    request: RiskAnalysisRequest, 
    rule_based_analysis: Dict[str, Any]
) -> str:
    """Create a detailed prompt for AI risk analysis."""
    
    customer_data = request.customer_data
    enriched_data = request.enriched_data
    
    prompt = f"""
Analyze this financial transaction for fraud risk:

TRANSACTION DETAILS:
- Transaction ID: {request.transaction_id}
- Amount: {customer_data.get('transaction_amount', 'Unknown')}
- Destination Country: {customer_data.get('destination_country', 'Unknown')}
- Currency: {customer_data.get('currency', 'Unknown')}

CUSTOMER PROFILE:
- Customer ID: {customer_data.get('customer_id', 'Unknown')}
- Customer Country: {customer_data.get('customer_country', 'Unknown')}
- Account Age (days): {customer_data.get('account_age_days', 'Unknown')}
- Past Fraud Flags: {customer_data.get('past_fraud_flags', 0)}
- Device Trust Score: {customer_data.get('device_trust_score', 'Unknown')}

RULE-BASED ANALYSIS RESULTS:
- Risk Score: {rule_based_analysis.get('risk_score', 0)}/100
- Risk Level: {rule_based_analysis.get('risk_level', 'Unknown')}
- Risk Factors: {', '.join(rule_based_analysis.get('risk_factors', []))}

ENRICHED CONTEXT:
{json.dumps(enriched_data, indent=2)[:500]}...

Please analyze this transaction considering:
1. Transaction patterns and anomalies
2. Geographic risk factors
3. Customer behavior indicators  
4. Temporal patterns
5. Amount analysis relative to customer profile
6. Any other fraud indicators

Provide your analysis in JSON format as specified in the system prompt.
"""
    
    return prompt.strip()


def combine_rule_based_and_ai_analysis(
    rule_based: Dict[str, Any], 
    ai_analysis: Dict[str, Any] = None,
    regulatory_findings: List[str] = None
) -> Dict[str, Any]:
    """Combine rule-based and AI analysis results."""
    
    # Start with rule-based analysis
    final_score = rule_based["risk_score"]
    risk_factors = rule_based["risk_factors"].copy()
    
    # Apply AI adjustments if available
    if ai_analysis and "risk_adjustment" in ai_analysis:
        adjustment = ai_analysis["risk_adjustment"]
        final_score = max(0, min(100, final_score + adjustment))
        
        # Add AI-identified factors
        if "additional_factors" in ai_analysis:
            risk_factors.extend(ai_analysis["additional_factors"])
    
    # Add regulatory risk factors
    if regulatory_findings:
        if any("sanctions" in finding.lower() for finding in regulatory_findings):
            final_score = min(100, final_score + 15)
            if "REGULATORY_SANCTIONS_RISK" not in risk_factors:
                risk_factors.append("REGULATORY_SANCTIONS_RISK")
    
    # Determine final risk level
    if final_score >= 70:
        risk_level = "HIGH"
    elif final_score >= 40:
        risk_level = "MEDIUM" 
    else:
        risk_level = "LOW"
    
    # Calculate confidence (weighted average)
    rule_confidence = rule_based.get("confidence", 0.8)
    ai_confidence = ai_analysis.get("confidence", 0.0) if ai_analysis else 0.0
    
    if ai_analysis:
        # Weight: 60% rule-based, 40% AI
        final_confidence = (rule_confidence * 0.6) + (ai_confidence * 0.4)
    else:
        final_confidence = rule_confidence
    
    return {
        "risk_score": final_score,
        "risk_level": risk_level,
        "risk_factors": list(set(risk_factors)),  # Remove duplicates
        "confidence": final_confidence
    }


async def perform_regulatory_analysis(
    customer_data: Dict[str, Any],
    enriched_data: Dict[str, Any]
) -> List[str]:
    """Perform regulatory compliance analysis."""
    regulatory_findings = []
    
    try:
        destination_country = customer_data.get("destination_country", "")
        
        # Check sanctions lists
        if destination_country in RISK_CONFIG["SANCTIONS_COUNTRIES"]:
            if destination_country == "IR":
                regulatory_findings.append("OFAC sanctions regulations apply to Iran")
                regulatory_findings.append("Enhanced due diligence required for Iran transactions")
            elif destination_country == "KP":
                regulatory_findings.append("OFAC sanctions prohibit most North Korea transactions")
                regulatory_findings.append("Transaction may violate sanctions regulations")
        
        # Check high-risk jurisdictions
        if destination_country in RISK_CONFIG["HIGH_RISK_COUNTRIES"]:
            regulatory_findings.append(f"Destination country {destination_country} classified as high-risk jurisdiction")
            regulatory_findings.append("Enhanced monitoring and reporting required")
        
        # Use Azure AI Search for additional regulatory lookup if available
        if search_tool:
            try:
                search_query = f"regulations sanctions {destination_country} compliance requirements"
                # Note: This would require proper search tool integration
                # search_results = await search_tool.search(search_query)
                # Process search results and add to regulatory_findings
                pass
            except Exception as e:
                logger.warning(f"Regulatory search failed: {e}")
        
        return regulatory_findings
        
    except Exception as e:
        logger.error(f"Error in regulatory analysis: {e}")
        return ["Regulatory analysis error - manual review required"]


def create_detailed_analysis(
    customer_data: Dict[str, Any],
    enriched_data: Dict[str, Any],
    risk_factors: List[str],
    regulatory_findings: List[str]
) -> Dict[str, Any]:
    """Create detailed analysis breakdown."""
    
    transaction = enriched_data.get("transaction", {})
    customer = enriched_data.get("customer", {})
    
    return {
        "transaction_analysis": {
            "transaction_id": customer_data.get("transaction_id"),
            "amount": customer_data.get("transaction_amount", transaction.get("amount")),
            "currency": transaction.get("currency", "USD"),
            "destination_country": customer_data.get("destination_country"),
            "timestamp": transaction.get("timestamp"),
            "analysis_timestamp": "2024-10-12T20:00:00Z"
        },
        "customer_analysis": {
            "customer_id": customer_data.get("customer_id"),
            "country": customer.get("country"),
            "account_age_days": customer.get("account_age_days", customer_data.get("account_age_days")),
            "device_trust_score": customer.get("device_trust_score", customer_data.get("device_trust_score")),
            "past_fraud_flags": customer.get("past_fraud_flags", customer_data.get("past_fraud_flags", 0))
        },
        "risk_assessment": {
            "total_risk_factors": len(risk_factors),
            "risk_categories": {
                "geographic": len([f for f in risk_factors if "COUNTRY" in f or "BORDER" in f]),
                "behavioral": len([f for f in risk_factors if "FRAUD" in f or "ACCOUNT" in f or "DEVICE" in f]),
                "transaction": len([f for f in risk_factors if "AMOUNT" in f or "TRANSACTION" in f]),
                "regulatory": len(regulatory_findings)
            }
        },
        "explanation": f"Analysis identified {len(risk_factors)} risk factors across multiple categories, with {len(regulatory_findings)} regulatory considerations.",
        "methodology": "Enhanced analysis combining rule-based detection with AI-powered pattern recognition"
    }


async def main():
    """
    Main function to test the Enhanced Risk Analyzer Agent Executor.
    """
    try:
        print(f"✅ Enhanced Risk Analyzer Agent Executor Function Created Successfully")
        print(f"📋 Executor Type: {type(risk_analyzer_executor_with_ai)}")
        print(f"🤖 AI Integration: {'Enabled' if AzureAIAgentClient and project_endpoint else 'Disabled'}")
        print(f"🔍 Regulatory Search: {'Enabled' if search_tool else 'Disabled'}")
        print(f"📝 Note: This is a Microsoft Agent Framework executor function with LLM integration.")
        
        # Test with sample data (high-risk scenario)
        print(f"\n🔍 Testing enhanced risk analysis...")
        
        sample_customer_data = {
            "transaction_id": "TX1001",
            "customer_id": "CUST1001",
            "transaction_amount": 15000,
            "destination_country": "IR", 
            "customer_country": "US",
            "account_age_days": 15,
            "device_trust_score": 0.4,
            "past_fraud_flags": 1,
            "currency": "USD"
        }
        
        # Test the analysis functions
        rule_analysis = await perform_rule_based_analysis(
            RiskAnalysisRequest(
                transaction_id="TX1001",
                customer_data=sample_customer_data,
                enriched_data={"transaction": sample_customer_data, "customer": sample_customer_data}
            )
        )
        print(f"📊 Rule-Based Analysis: {rule_analysis['risk_level']} ({rule_analysis['risk_score']}/100)")
        
        if AzureAIAgentClient and project_endpoint:
            ai_analysis = await perform_ai_risk_analysis(
                RiskAnalysisRequest(transaction_id="TX1001", customer_data=sample_customer_data),
                rule_analysis
            )
            print(f"🤖 AI Analysis: Confidence {ai_analysis.get('confidence', 0.0):.2f}")
            print(f"💭 AI Reasoning: {ai_analysis.get('reasoning', 'No reasoning provided')[:100]}...")
        
        regulatory_findings = await perform_regulatory_analysis(sample_customer_data, {})
        print(f"📋 Regulatory Findings: {len(regulatory_findings)} items")
        
        # Show usage example
        print(f"\n🚀 USAGE EXAMPLE:")
        print(f"```python")
        print(f"from workflow import risk_analyzer_executor_with_ai")
        print(f"from agent_framework import WorkflowBuilder")
        print(f"")
        print(f"workflow = WorkflowBuilder().add_executor(risk_analyzer_executor_with_ai).build()")
        print(f"result = await workflow.run(RiskAnalysisRequest(..., use_ai_analysis=True))")
        print(f"```")
        
        return risk_analyzer_executor_with_ai
        
    except Exception as e:
        print(f"❌ Error testing Enhanced Risk Analyzer Executor: {e}")
        return None


if __name__ == "__main__":
    asyncio.run(main())