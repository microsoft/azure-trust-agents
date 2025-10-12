"""
Risk Analyzer Agent Executor for Microsoft Agent Framework.

This executor implements the Risk Analyzer Agent functionality using the 
Microsoft Agent Framework Executor pattern as described in:
https://learn.microsoft.com/en-us/agent-framework/user-guide/workflows/core-concepts/executors
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
import re
from datetime import datetime

load_dotenv(override=True)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
project_endpoint = os.environ.get("AI_FOUNDRY_PROJECT_ENDPOINT")
model_deployment_name = os.environ.get("MODEL_DEPLOYMENT_NAME")
sc_connection_id = os.environ.get("AZURE_AI_CONNECTION_ID")

# Risk Analysis Configuration
RISK_CONFIG = {
    "high_risk_countries": ["NG", "IR", "RU", "KP", "SY", "AF", "MM"],
    "high_amount_threshold_usd": 10000,
    "suspicious_account_age_days": 30,
    "low_device_trust_threshold": 0.5,
    "sanctions_countries": ["IR", "KP", "SY", "RU"],
    "max_risk_score": 100,
    "min_risk_score": 0
}


# Data Models
class RiskAnalysisRequest(BaseModel):
    """Request model for risk analysis operations."""
    transaction_id: str
    enriched_data: Dict[str, Any]
    perform_regulatory_search: bool = True


class RiskAnalysisResponse(BaseModel):
    """Response model for risk analysis operations."""
    transaction_id: str
    risk_score: int
    risk_level: str
    risk_factors: List[str]
    regulatory_findings: List[str]
    detailed_analysis: Dict[str, Any]
    explanation: str
    recommendations: List[str]
    status: str
    message: str


# Initialize Azure AI Search tool for regulatory lookup (optional)
try:
    search_tool = HostedFileSearchTool(
        additional_properties={
            "index_name": "regulations-policies",
            "query_type": "simple",
            "top_k": 5,
        },
    )
    logger.info("✅ Initialized Azure AI Search tool for regulatory analysis")
except Exception as e:
    logger.warning(f"Could not initialize search tool: {e}. Will use rule-based analysis only.")
    search_tool = None


@executor
async def risk_analyzer_executor(
    request: RiskAnalysisRequest,
    ctx: WorkflowContext
) -> RiskAnalysisResponse:
    """
    Risk Analyzer Agent Executor for comprehensive fraud detection and risk assessment.
    
    Args:
        request: Risk analysis request with enriched transaction data
        ctx: Workflow context
        
    Returns:
        RiskAnalysisResponse: Complete risk analysis with score and recommendations
    """
    logger.info(f"🔍 Starting risk analysis for transaction: {request.transaction_id}")
    
    try:
        enriched_data = request.enriched_data
        
        # Extract key data elements
        transaction = enriched_data.get("transaction", {})
        customer = enriched_data.get("customer", {})
        risk_indicators = enriched_data.get("risk_indicators", {})
        
        # Step 1: Calculate base risk score using rule-based analysis
        base_risk_score, risk_factors = calculate_base_risk_score(
            transaction, customer, risk_indicators
        )
        
        # Step 2: Perform regulatory compliance analysis (if requested)
        regulatory_findings = []
        if request.perform_regulatory_search:
            regulatory_findings = await perform_regulatory_analysis(
                transaction, customer, risk_indicators
            )
        
        # Step 3: Adjust risk score based on regulatory findings
        final_risk_score = adjust_risk_score_with_regulatory_findings(
            base_risk_score, regulatory_findings
        )
        
        # Step 4: Determine risk level
        risk_level = determine_risk_level(final_risk_score)
        
        # Step 5: Generate detailed analysis and explanation
        detailed_analysis = create_detailed_analysis(
            transaction, customer, risk_indicators, risk_factors, regulatory_findings
        )
        
        # Step 6: Generate human-readable explanation
        explanation = generate_explanation(
            final_risk_score, risk_level, risk_factors, regulatory_findings
        )
        
        # Step 7: Generate recommendations
        recommendations = generate_recommendations(
            final_risk_score, risk_level, risk_factors, regulatory_findings
        )
        
        logger.info(f"✅ Risk analysis completed for transaction {request.transaction_id}: {risk_level} ({final_risk_score}/100)")
        
        return RiskAnalysisResponse(
            transaction_id=request.transaction_id,
            risk_score=final_risk_score,
            risk_level=risk_level,
            risk_factors=risk_factors,
            regulatory_findings=regulatory_findings,
            detailed_analysis=detailed_analysis,
            explanation=explanation,
            recommendations=recommendations,
            status="SUCCESS",
            message=f"Risk analysis completed: {risk_level} risk with score {final_risk_score}/100"
        )

    except Exception as e:
        error_msg = f"Error during risk analysis: {str(e)}"
        logger.error(error_msg)
        return RiskAnalysisResponse(
            transaction_id=request.transaction_id,
            risk_score=0,
            risk_level="UNKNOWN",
            risk_factors=[],
            regulatory_findings=[],
            detailed_analysis={},
            explanation="",
            recommendations=[],
            status="ERROR",
            message=error_msg
        )


def calculate_base_risk_score(
    transaction: Dict[str, Any],
    customer: Dict[str, Any],
    risk_indicators: Dict[str, Any]
) -> tuple[int, List[str]]:
    """Calculate base risk score using rule-based analysis."""
    risk_score = 0
    risk_factors = []
    
    try:
        # Country-based risk assessment
        destination_country = transaction.get("destination_country", "")
        customer_country = customer.get("country", "")
        
        if destination_country in RISK_CONFIG["high_risk_countries"]:
            risk_score += 30
            risk_factors.append("HIGH_RISK_DESTINATION_COUNTRY")
        
        if destination_country in RISK_CONFIG["sanctions_countries"]:
            risk_score += 40
            risk_factors.append("SANCTIONS_DESTINATION_COUNTRY")
        
        if risk_indicators.get("cross_border_transaction", False):
            risk_score += 10
            risk_factors.append("CROSS_BORDER_TRANSACTION")
        
        # Amount-based risk assessment
        amount = transaction.get("amount", 0)
        if amount > RISK_CONFIG["high_amount_threshold_usd"]:
            risk_score += 20
            risk_factors.append("HIGH_TRANSACTION_AMOUNT")
        
        # Historical pattern analysis
        amount_vs_average = risk_indicators.get("amount_vs_average", 1)
        if amount_vs_average > 5:  # 5x higher than average
            risk_score += 25
            risk_factors.append("UNUSUAL_AMOUNT_PATTERN")
        
        # Customer behavior risk factors
        account_age = risk_indicators.get("account_age_days", 365)
        if account_age < RISK_CONFIG["suspicious_account_age_days"]:
            risk_score += 15
            risk_factors.append("NEW_ACCOUNT_RISK")
        
        device_trust = risk_indicators.get("device_trust_score", 1.0)
        if device_trust < RISK_CONFIG["low_device_trust_threshold"]:
            risk_score += 20
            risk_factors.append("LOW_DEVICE_TRUST")
        
        past_fraud_flags = risk_indicators.get("past_fraud_flags", 0)
        if past_fraud_flags > 0:
            risk_score += 30
            risk_factors.append("PREVIOUS_FRAUD_HISTORY")
        
        # Ensure score is within bounds
        risk_score = max(RISK_CONFIG["min_risk_score"], min(risk_score, RISK_CONFIG["max_risk_score"]))
        
        return risk_score, risk_factors
        
    except Exception as e:
        logger.error(f"Error calculating base risk score: {str(e)}")
        return 50, ["CALCULATION_ERROR"]  # Default medium risk


async def perform_regulatory_analysis(
    transaction: Dict[str, Any],
    customer: Dict[str, Any],
    risk_indicators: Dict[str, Any]
) -> List[str]:
    """Perform regulatory compliance analysis."""
    regulatory_findings = []
    
    try:
        destination_country = transaction.get("destination_country", "")
        amount = transaction.get("amount", 0)
        
        # Simulate regulatory findings based on risk factors
        if destination_country in RISK_CONFIG["sanctions_countries"]:
            regulatory_findings.append(f"OFAC sanctions regulations apply to {destination_country}")
            regulatory_findings.append("Enhanced due diligence required for sanctions jurisdictions")
        
        if amount > 10000:
            regulatory_findings.append("BSA reporting requirements for large transactions")
            regulatory_findings.append("Currency transaction report (CTR) may be required")
        
        if risk_indicators.get("cross_border_transaction", False):
            regulatory_findings.append("Cross-border transaction monitoring requirements")
        
        return regulatory_findings
        
    except Exception as e:
        logger.error(f"Error in regulatory analysis: {str(e)}")
        return ["REGULATORY_ANALYSIS_ERROR"]


def adjust_risk_score_with_regulatory_findings(
    base_score: int,
    regulatory_findings: List[str]
) -> int:
    """Adjust risk score based on regulatory compliance findings."""
    try:
        adjusted_score = base_score
        
        # Increase score for serious regulatory concerns
        for finding in regulatory_findings:
            if "sanctions" in finding.lower() or "ofac" in finding.lower():
                adjusted_score += 15
            elif "enhanced due diligence" in finding.lower():
                adjusted_score += 10
            elif "suspicious activity" in finding.lower():
                adjusted_score += 12
        
        # Ensure score remains within bounds
        return max(RISK_CONFIG["min_risk_score"], min(adjusted_score, RISK_CONFIG["max_risk_score"]))
        
    except Exception as e:
        logger.error(f"Error adjusting risk score: {str(e)}")
        return base_score


def determine_risk_level(risk_score: int) -> str:
    """Determine risk level based on risk score."""
    if risk_score >= 70:
        return "HIGH"
    elif risk_score >= 40:
        return "MEDIUM"
    else:
        return "LOW"


def create_detailed_analysis(
    transaction: Dict[str, Any],
    customer: Dict[str, Any],
    risk_indicators: Dict[str, Any],
    risk_factors: List[str],
    regulatory_findings: List[str]
) -> Dict[str, Any]:
    """Create detailed analysis breakdown."""
    return {
        "transaction_analysis": {
            "transaction_id": transaction.get("transaction_id"),
            "amount": transaction.get("amount"),
            "currency": transaction.get("currency"),
            "destination_country": transaction.get("destination_country"),
            "timestamp": transaction.get("timestamp")
        },
        "customer_analysis": {
            "customer_id": customer.get("customer_id"),
            "country": customer.get("country"),
            "account_age_days": risk_indicators.get("account_age_days"),
            "device_trust_score": risk_indicators.get("device_trust_score"),
            "past_fraud_flags": risk_indicators.get("past_fraud_flags")
        },
        "risk_assessment": {
            "identified_risk_factors": risk_factors,
            "regulatory_compliance_issues": regulatory_findings,
            "cross_border_transaction": risk_indicators.get("cross_border_transaction", False),
            "amount_analysis": {
                "amount_vs_average": risk_indicators.get("amount_vs_average", 1),
                "amount_vs_max": risk_indicators.get("amount_vs_max", 1)
            }
        },
        "analysis_metadata": {
            "analysis_timestamp": datetime.now().isoformat(),
            "risk_config_version": "1.0",
            "regulatory_search_performed": len(regulatory_findings) > 0
        }
    }


def generate_explanation(
    risk_score: int,
    risk_level: str,
    risk_factors: List[str],
    regulatory_findings: List[str]
) -> str:
    """Generate human-readable explanation of risk assessment."""
    try:
        explanation = f"Risk Analysis Complete - Score: {risk_score}/100, Level: {risk_level}\n\n"
        
        if risk_factors:
            explanation += "Key Risk Factors Identified:\n"
            for factor in risk_factors:
                factor_desc = factor.replace("_", " ").title()
                explanation += f"• {factor_desc}\n"
        
        if regulatory_findings:
            explanation += "\nRegulatory Compliance Considerations:\n"
            for finding in regulatory_findings:
                explanation += f"• {finding}\n"
        
        # Add risk level interpretation
        if risk_level == "HIGH":
            explanation += "\nHIGH RISK: Immediate attention and enhanced due diligence required."
        elif risk_level == "MEDIUM":
            explanation += "\nMEDIUM RISK: Additional monitoring and verification recommended."
        else:
            explanation += "\nLOW RISK: Standard processing procedures sufficient."
        
        return explanation
        
    except Exception as e:
        return f"Risk score: {risk_score}/100, Risk level: {risk_level}. Error generating detailed explanation: {str(e)}"


def generate_recommendations(
    risk_score: int,
    risk_level: str,
    risk_factors: List[str],
    regulatory_findings: List[str]
) -> List[str]:
    """Generate actionable recommendations based on risk assessment."""
    recommendations = []
    
    try:
        if risk_level == "HIGH":
            recommendations.extend([
                "BLOCK TRANSACTION - Enhanced due diligence required",
                "Conduct immediate customer verification",
                "Review transaction against internal risk policies",
                "Consider filing suspicious activity report (SAR)"
            ])
        elif risk_level == "MEDIUM":
            recommendations.extend([
                "HOLD TRANSACTION - Additional verification required",
                "Perform enhanced customer due diligence",
                "Monitor future transactions from this customer",
                "Document risk assessment findings"
            ])
        else:
            recommendations.extend([
                "APPROVE TRANSACTION - Standard monitoring sufficient",
                "Continue regular transaction monitoring",
                "No additional action required at this time"
            ])
        
        # Add specific recommendations based on risk factors
        if "SANCTIONS_DESTINATION_COUNTRY" in risk_factors:
            recommendations.append("Verify transaction against OFAC sanctions lists")
        
        if "PREVIOUS_FRAUD_HISTORY" in risk_factors:
            recommendations.append("Review customer's fraud history and risk profile")
        
        if any("BSA" in finding or "CTR" in finding for finding in regulatory_findings):
            recommendations.append("Ensure compliance with BSA reporting requirements")
        
        return recommendations
        
    except Exception as e:
        logger.error(f"Error generating recommendations: {str(e)}")
        return ["Review transaction manually due to analysis error"]


async def main():
    """
    Main function to test the Risk Analyzer Agent Executor.
    """
    try:
        print(f"✅ Risk Analyzer Agent Executor Function Created Successfully")
        print(f"📋 Executor Type: {type(risk_analyzer_executor)}")
        print(f"📝 Note: This is a Microsoft Agent Framework executor function.")
        
        # Test with sample enriched data
        print(f"\n🔍 Testing risk analysis functions...")
        
        # Create test enriched data
        test_enriched_data = {
            "transaction": {
                "transaction_id": "TX1001",
                "customer_id": "CUST1001", 
                "amount": 15000,
                "currency": "USD",
                "destination_country": "IR",
                "timestamp": "2025-01-15T10:30:00Z"
            },
            "customer": {
                "customer_id": "CUST1001",
                "name": "John Smith",
                "country": "US",
                "account_age_days": 25,
                "device_trust_score": 0.3,
                "past_fraud_flags": 1
            },
            "risk_indicators": {
                "cross_border_transaction": True,
                "amount_vs_average": 8.5,
                "amount_vs_max": 2.1,
                "account_age_days": 25,
                "device_trust_score": 0.3,
                "past_fraud_flags": 1
            }
        }
        
        # Test risk scoring functions
        transaction = test_enriched_data["transaction"]
        customer = test_enriched_data["customer"] 
        risk_indicators = test_enriched_data["risk_indicators"]
        
        base_score, risk_factors = calculate_base_risk_score(transaction, customer, risk_indicators)
        print(f"📊 Base Risk Score: {base_score}/100")
        print(f"⚠️  Risk Factors: {len(risk_factors)} identified")
        
        regulatory_findings = await perform_regulatory_analysis(transaction, customer, risk_indicators)
        print(f"📋 Regulatory Findings: {len(regulatory_findings)} items")
        
        final_score = adjust_risk_score_with_regulatory_findings(base_score, regulatory_findings)
        risk_level = determine_risk_level(final_score)
        print(f"🎯 Final Risk Assessment: {risk_level} ({final_score}/100)")
        
        # Show usage example
        print(f"\n🚀 USAGE EXAMPLE:")
        print(f"To use this executor in a workflow:")
        print(f"```python")
        print(f"from workflow import risk_analyzer_executor")
        print(f"from agent_framework import WorkflowBuilder")
        print(f"")
        print(f"workflow = WorkflowBuilder().add_executor(risk_analyzer_executor).build()")
        print(f"result = await workflow.run(RiskAnalysisRequest(...))")
        print(f"```")
        
        return risk_analyzer_executor
        
    except Exception as e:
        print(f"❌ Error testing Risk Analyzer Executor: {e}")
        return None


if __name__ == "__main__":
    asyncio.run(main())