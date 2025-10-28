"""
CHALLENGE 2 WORKFLOW OBSERVABILITY IMPLEMENTATION

This file implements the Challenge 2 workflow architecture with comprehensive observability:

WORKFLOW ARCHITECTURE:
1. Customer Data Executor → Retrieves transaction and customer data from Cosmos DB
2. Risk Analyzer Executor → Performs AI-powered risk analysis 
3. Compliance Report Executor → Generates compliance audit reports (Parallel Path 1)
4. Fraud Alert Executor → Creates fraud alerts via MCP tools (Parallel Path 2)

OBSERVABILITY FEATURES:
- Distributed tracing with OpenTelemetry spans for each executor
- Custom metrics for business KPIs (risk scores, compliance decisions, fraud alerts)
- Business event tracking for workflow steps and decisions
- Cosmos DB instrumentation with performance monitoring  
- Parallel execution monitoring and coordination
- Error tracking and exception recording
- Processing time measurements for AI model calls
- MCP tool usage tracking and performance metrics

TELEMETRY DATA CAPTURED:
- Transaction processing metrics and timings
- Risk assessment scores and recommendations  
- Compliance ratings and regulatory requirements
- Fraud alert creation and severity levels
- Cosmos DB query performance and results
- AI model processing times and responses
- Workflow execution flow and parallel coordination
- Business process completion rates and success metrics

The implementation follows Challenge 2's parallel execution pattern where both 
compliance reports and fraud alerts are generated simultaneously after risk analysis.
"""

import asyncio
import os
import json
import re
from datetime import datetime, timedelta
from collections import Counter
from typing_extensions import Never
from agent_framework import WorkflowBuilder, WorkflowContext, WorkflowOutputEvent, executor, ChatAgent, HostedMCPTool
from agent_framework.azure import AzureAIAgentClient, AzureOpenAIResponsesClient
from azure.identity.aio import AzureCliCredential
from azure.identity import AzureCliCredential as SyncAzureCliCredential
from azure.cosmos import CosmosClient
from dotenv import load_dotenv
from pydantic import BaseModel

# Import our telemetry module
from telemetry import (
    initialize_telemetry,
    get_telemetry_manager,
    send_business_event,
    flush_telemetry,
    get_current_trace_id,
    CosmosDbInstrumentation
)

# Load environment variables
load_dotenv(override=True)

# Initialize Cosmos DB connection
cosmos_endpoint = os.environ.get("COSMOS_ENDPOINT")
cosmos_key = os.environ.get("COSMOS_KEY")
cosmos_client = CosmosClient(cosmos_endpoint, cosmos_key)
database = cosmos_client.get_database_client("FinancialComplianceDB")
customers_container = database.get_container_client("Customers")
transactions_container = database.get_container_client("Transactions")

# Initialize telemetry
telemetry = get_telemetry_manager()
cosmos_instrumentation = CosmosDbInstrumentation(telemetry)

# Request/Response models
class AnalysisRequest(BaseModel):
    message: str
    transaction_id: str = "TX2002"

class CustomerDataResponse(BaseModel):
    customer_data: str
    transaction_data: str
    transaction_id: str
    status: str
    raw_transaction: dict = {}
    raw_customer: dict = {}
    transaction_history: list = []

class RiskAnalysisResponse(BaseModel):
    risk_analysis: str
    risk_score: str
    transaction_id: str
    status: str
    risk_factors: list = []
    recommendation: str = ""
    compliance_notes: str = ""

class ComplianceAuditResponse(BaseModel):
    audit_report_id: str
    audit_conclusion: str
    compliance_rating: str
    risk_score: float = 0.0
    risk_factors_identified: list = []
    compliance_concerns: list = []
    recommendations: list = []
    requires_immediate_action: bool = False
    requires_regulatory_filing: bool = False
    transaction_id: str
    status: str

class FraudAlertResponse(BaseModel):
    alert_id: str
    alert_status: str
    severity: str
    decision_action: str
    alert_created: bool = False
    mcp_server_response: str = ""
    transaction_id: str
    status: str
    created_timestamp: str = ""
    assigned_to: str = ""
    reasoning: str = ""

# Cosmos DB helper functions with telemetry decorators
@cosmos_instrumentation.instrument_transaction_get
def get_transaction_data(transaction_id: str) -> dict:
    """Get transaction data from Cosmos DB."""
    try:
        query = f"SELECT * FROM c WHERE c.transaction_id = '{transaction_id}'"
        items = list(transactions_container.query_items(
            query=query,
            enable_cross_partition_query=True
        ))
        
        return items[0] if items else {"error": f"Transaction {transaction_id} not found"}
        
    except Exception as e:
        return {"error": str(e)}

@cosmos_instrumentation.instrument_customer_get
def get_customer_data(customer_id: str) -> dict:
    """Get customer data from Cosmos DB."""
    try:
        query = f"SELECT * FROM c WHERE c.customer_id = '{customer_id}'"
        items = list(customers_container.query_items(
            query=query,
            enable_cross_partition_query=True
        ))
        
        return items[0] if items else {"error": f"Customer {customer_id} not found"}
        
    except Exception as e:
        return {"error": str(e)}

@cosmos_instrumentation.instrument_transaction_list
def get_customer_transactions(customer_id: str) -> list:
    """Get all transactions for a customer from Cosmos DB."""
    try:
        query = f"SELECT * FROM c WHERE c.customer_id = '{customer_id}'"
        items = list(transactions_container.query_items(
            query=query,
            enable_cross_partition_query=True
        ))
        
        return items
        
    except Exception as e:
        return [{"error": str(e)}]

# Compliance Report Functions
def parse_risk_analysis_result(risk_analysis_text: str) -> dict:
    """Parses risk analyser output to extract key audit information."""
    try:
        analysis_data = {
            "original_analysis": risk_analysis_text,
            "parsed_elements": {},
            "audit_findings": []
        }
        
        text_lower = risk_analysis_text.lower()
        
        # Extract risk score 
        risk_score_pattern = r'risk\s*score[:\s]*(\d+(?:\.\d+)?)'
        score_match = re.search(risk_score_pattern, text_lower)
        if score_match:
            analysis_data["parsed_elements"]["risk_score"] = float(score_match.group(1))
        else:
            # If no explicit score found, calculate based on content analysis
            calculated_score = 20.0  # Start with baseline low-medium risk
            
            # High-risk countries (moderate increase, not overwhelming)
            if any(country in text_lower for country in ['russia', 'russian', 'iran', 'iranian', 'north korea', 'syria', 'yemen']):
                calculated_score += 40  # Was 80, now more moderate
            elif "high-risk country" in text_lower or "high risk country" in text_lower:
                calculated_score += 35  # Was 75, now more moderate
            elif "sanctions" in text_lower and not any(phrase in text_lower for phrase in ["no sanctions", "sanctions check clear"]):
                calculated_score += 45  # Was 85, now more moderate
            
            # Large amounts increase risk moderately
            if ("large amount" in text_lower or "high amount" in text_lower) and not any(phrase in text_lower for phrase in ["below", "under", "not large"]):
                calculated_score += 15  # Was 20, slightly reduced
                
            # Suspicious patterns (moderate increase)
            if "suspicious" in text_lower and not any(phrase in text_lower for phrase in ["no suspicious", "not suspicious", "no triggering"]):
                calculated_score += 20  # Was 30, now more moderate
                
            # New account or low trust factors
            if "new account" in text_lower or "low.*trust" in text_lower:
                calculated_score += 10
                
            # Past fraud history
            if "past fraud" in text_lower or "fraud history" in text_lower:
                calculated_score += 25
            
            # Final recommendation adjustments (but don't override calculated scores too aggressively)
            if "block" in text_lower or "reject" in text_lower:
                calculated_score = max(calculated_score, 75)  # Was 80, slightly reduced
            elif "high risk" in text_lower and not any(phrase in text_lower for phrase in ["not high risk", "no high risk"]):
                calculated_score = max(calculated_score, 65)  # New moderate adjustment
            elif "medium risk" in text_lower:
                calculated_score = max(calculated_score, 45)  # Was 60, adjusted for medium range
            elif "low risk" in text_lower or "approve" in text_lower:
                calculated_score = min(calculated_score, 30)  # Cap low risk transactions
                
            # Cap at 100 and ensure minimum
            calculated_score = max(10.0, min(100.0, calculated_score))  # Ensure range 10-100
            analysis_data["parsed_elements"]["risk_score"] = calculated_score
        
        # Extract risk level
        risk_level_pattern = r'risk\s*level[:\s]*(\w+)'
        level_match = re.search(risk_level_pattern, text_lower)
        if level_match:
            analysis_data["parsed_elements"]["risk_level"] = level_match.group(1).upper()
        
        # Extract transaction ID
        tx_pattern = r'transaction[:\s]*([A-Z0-9]+)'
        tx_match = re.search(tx_pattern, risk_analysis_text)
        if tx_match:
            analysis_data["parsed_elements"]["transaction_id"] = tx_match.group(1)
        
        # Extract key risk factors mentioned (only if they indicate actual risk)
        risk_factors = []
        
        # Only flag high-risk country if it's actually mentioned as a concern
        if ("high-risk country" in text_lower or "high risk country" in text_lower) and not any(phrase in text_lower for phrase in ["not in", "no high-risk", "not high-risk", "low-risk"]):
            risk_factors.append("HIGH_RISK_JURISDICTION")
            
        # Only flag large amounts if mentioned as problematic
        if ("large amount" in text_lower or "high amount" in text_lower) and not any(phrase in text_lower for phrase in ["below", "under", "not large", "not high"]):
            risk_factors.append("UNUSUAL_AMOUNT")
            
        # Only flag suspicious if it's a concern, not if it says "no suspicious"
        if "suspicious" in text_lower and not any(phrase in text_lower for phrase in ["no suspicious", "not suspicious", "no triggering"]):
            risk_factors.append("SUSPICIOUS_PATTERN")
            
        # Only flag sanctions if there's an actual concern, not if it says "no sanctions"
        if "sanction" in text_lower and any(phrase in text_lower for phrase in ["sanctions concern", "sanctions flag", "sanctions match", "sanctions risk"]) and not any(phrase in text_lower for phrase in ["no sanctions", "sanctions check clear", "no sanctions flag"]):
            risk_factors.append("SANCTIONS_CONCERN")
            
        # Only flag frequency issues if mentioned as problematic
        if ("frequent" in text_lower or "unusual frequency" in text_lower) and not any(phrase in text_lower for phrase in ["not frequent", "normal frequency"]):
            risk_factors.append("FREQUENCY_ANOMALY")
        
        analysis_data["parsed_elements"]["risk_factors"] = risk_factors
        return analysis_data
        
    except Exception as e:
        return {"error": f"Failed to parse risk analysis: {str(e)}"}

def generate_audit_report_from_risk_analysis(risk_analysis_text: str, report_type: str = "TRANSACTION_AUDIT") -> dict:
    """Generate structured audit report from risk analysis text."""
    
    try:
        # Parse the risk analysis
        parsed_data = parse_risk_analysis_result(risk_analysis_text)
        
        if "error" in parsed_data:
            return parsed_data
        
        # Generate audit report ID
        report_id = f"AUDIT_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{report_type}"
        
        # Analyze content for risk factors and compliance issues
        text_upper = risk_analysis_text.upper()
        
        # Risk factor identification
        risk_factors = []
        if "HIGH RISK" in text_upper or "SUSPICIOUS" in text_upper:
            risk_factors.append("High risk transaction pattern detected")
        if "SANCTIONS" in text_upper or "BLACKLIST" in text_upper:
            risk_factors.append("Potential sanctions list match")
        if "FRAUD" in text_upper:
            risk_factors.append("Fraud indicators present")
        if "AML" in text_upper or "MONEY LAUNDERING" in text_upper:
            risk_factors.append("Anti-Money Laundering concerns")
        
        # Compliance concerns
        compliance_concerns = []
        if "REGULATORY" in text_upper or "COMPLIANCE" in text_upper:
            compliance_concerns.append("Regulatory compliance review required")
        if "KYC" in text_upper or "KNOW YOUR CUSTOMER" in text_upper:
            compliance_concerns.append("KYC verification needed")
        if "INVESTIGATION" in text_upper:
            compliance_concerns.append("Further investigation recommended")
        
        # Determine compliance rating
        if "BLOCK" in text_upper or "REJECT" in text_upper:
            compliance_rating = "NON_COMPLIANT"
            requires_immediate_action = True
            requires_regulatory_filing = True
        elif "APPROVE" in text_upper and not risk_factors:
            compliance_rating = "COMPLIANT"
            requires_immediate_action = False
            requires_regulatory_filing = False
        else:
            compliance_rating = "REVIEW_REQUIRED"
            requires_immediate_action = bool(risk_factors)
            requires_regulatory_filing = "SANCTIONS" in text_upper
        
        # Generate audit report structure
        audit_report = {
            "audit_report_id": report_id,
            "generated_timestamp": datetime.now().isoformat(),
            "report_type": report_type,
            "executive_summary": {
                "audit_conclusion": f"Transaction analysis completed with {compliance_rating} status. {len(risk_factors)} risk factors identified.",
                "key_findings": risk_factors[:3],  # Top 3 findings
                "overall_assessment": compliance_rating
            },
            "detailed_findings": {
                "risk_factors_identified": risk_factors,
                "compliance_concerns": compliance_concerns,
                "recommendations": []
            },
            "compliance_status": {
                "compliance_rating": compliance_rating,
                "requires_immediate_action": requires_immediate_action,
                "requires_regulatory_filing": requires_regulatory_filing,
                "next_review_date": (datetime.now().replace(day=1) + timedelta(days=32)).replace(day=1).isoformat()
            },
            "source_analysis": {
                "risk_analysis_summary": risk_analysis_text[:500] + "..." if len(risk_analysis_text) > 500 else risk_analysis_text,
                "parsed_elements": parsed_data.get("parsed_elements", {})
            }
        }
        
        # Generate recommendations based on findings
        if requires_immediate_action:
            audit_report["detailed_findings"]["recommendations"].extend([
                "Immediate transaction review required",
                "Enhanced due diligence procedures",
                "Supervisor approval mandatory"
            ])
        
        if requires_regulatory_filing:
            audit_report["detailed_findings"]["recommendations"].extend([
                "File Suspicious Activity Report (SAR)",
                "Notify relevant regulatory authorities",
                "Maintain detailed transaction records"
            ])
        
        if compliance_rating == "REVIEW_REQUIRED":
            audit_report["detailed_findings"]["recommendations"].extend([
                "Schedule compliance review meeting",
                "Additional customer verification",
                "Monitor for pattern analysis"
            ])
        
        if risk_factors:
            audit_report["detailed_findings"]["recommendations"].extend([
                "Place customer on enhanced monitoring list",
                "Review transaction against internal risk policies"
            ])
        else:
            audit_report["detailed_findings"]["recommendations"].append(
                "Continue standard monitoring procedures"
            )
        
        return audit_report
        
    except Exception as e:
        return {"error": f"Failed to generate audit report: {str(e)}"}

@executor
async def customer_data_executor(
    request: AnalysisRequest,
    ctx: WorkflowContext[CustomerDataResponse]
) -> None:
    """Customer Data Executor - retrieves and analyzes customer and transaction data."""
    
    with telemetry.create_processing_span(
        executor_id="customer_data_executor",
        executor_type="DataRetrieval",
        message_type="AnalysisRequest"
    ) as span:
        
        # Add business context to span
        span.set_attributes({
            "transaction.id": request.transaction_id,
            "executor.name": "customer_data_executor",
            "workflow.step": "data_retrieval",
            "business.process": "fraud_detection"
        })
        
        # Record metric for transaction processing with detailed span
        with telemetry.create_detailed_operation_span("metric_recording", "business_metrics") as metric_span:
            metric_span.set_attributes({
                "metric.type": "transaction_counter",
                "metric.step": "data_retrieval"
            })
            telemetry.record_transaction_processed("data_retrieval", request.transaction_id)
            metric_span.add_event("Transaction processing metric recorded")
        
        # Send business events for comprehensive tracking
        send_business_event("fraud_detection.transaction.started", {
            "transaction_id": request.transaction_id,
            "step": "data_retrieval",
            "executor": "customer_data_executor"
        })
        
        send_business_event("fraud_detection.executor.started", {
            "transaction_id": request.transaction_id,
            "executor_name": "customer_data_executor",
            "executor_type": "DataRetrieval"
        })
        
        try:
            span.add_event("Starting customer data retrieval", {
                "transaction.id": request.transaction_id
            })
            
            # Create sub-span for transaction data retrieval
            with telemetry.tracer.start_as_current_span("executor.process.transaction_data_retrieval") as tx_span:
                tx_span.set_attributes({
                    "data.operation": "transaction_retrieval",
                    "data.source": "cosmos_db"
                })
                
                # Get real data from Cosmos DB (telemetry handled by decorators)
                transaction_data = get_transaction_data(request.transaction_id)
                
                tx_span.add_event("Transaction data retrieved", {
                    "transaction.found": "error" not in transaction_data
                })
            
            if "error" in transaction_data:
                span.set_attribute("executor.success", False)
                span.set_attribute("executor.error", str(transaction_data))
                
                result = CustomerDataResponse(
                    customer_data=f"Error: {transaction_data}",
                    transaction_data="Error in Cosmos DB retrieval",
                    transaction_id=request.transaction_id,
                    status="ERROR"
                )
            else:
                customer_id = transaction_data.get("customer_id")
                
                # Create sub-span for customer data retrieval  
                with telemetry.tracer.start_as_current_span("executor.process.customer_data_retrieval") as cust_span:
                    cust_span.set_attributes({
                        "data.operation": "customer_retrieval",
                        "customer.id": customer_id
                    })
                    
                    customer_data = get_customer_data(customer_id)
                    cust_span.add_event("Customer data retrieved", {
                        "customer.found": "error" not in customer_data
                    })
                
                # Create sub-span for transaction history retrieval
                with telemetry.tracer.start_as_current_span("executor.process.transaction_history_retrieval") as hist_span:
                    hist_span.set_attributes({
                        "data.operation": "transaction_history",
                        "customer.id": customer_id
                    })
                    
                    transaction_history = get_customer_transactions(customer_id)
                    hist_span.add_event("Transaction history retrieved", {
                        "history.count": len(transaction_history) if isinstance(transaction_history, list) else 0
                    })
                
                # Add business metrics and attributes
                span.set_attributes({
                    "customer.id": customer_id,
                    "transaction.amount": transaction_data.get('amount', 0),
                    "transaction.currency": transaction_data.get('currency', ''),
                    "transaction.destination": transaction_data.get('destination_country', ''),
                    "customer.transaction_count": len(transaction_history) if isinstance(transaction_history, list) else 0
                })
                
                # Create comprehensive analysis with fraud risk indicators
                high_amount = transaction_data.get('amount', 0) > 10000
                high_risk_country = transaction_data.get('destination_country') in ['IR', 'RU', 'NG', 'KP']
                new_account = customer_data.get('account_age_days', 0) < 30
                low_device_trust = customer_data.get('device_trust_score', 1.0) < 0.5
                past_fraud = customer_data.get('past_fraud', False)
                
                # Log fraud indicators as events
                fraud_indicators = {
                    "high_amount": high_amount,
                    "high_risk_country": high_risk_country,
                    "new_account": new_account,
                    "low_device_trust": low_device_trust,
                    "past_fraud": past_fraud
                }
                
                span.add_event("Fraud indicators calculated", fraud_indicators)
                span.set_attributes({f"fraud.indicator.{k}": v for k, v in fraud_indicators.items()})
                
                analysis_text = f"""
COSMOS DB DATA ANALYSIS:

Transaction {request.transaction_id}:
- Amount: ${transaction_data.get('amount')} {transaction_data.get('currency')}
- Customer: {customer_id}
- Destination: {transaction_data.get('destination_country')}
- Timestamp: {transaction_data.get('timestamp')}

Customer Profile ({customer_id}):
- Name: {customer_data.get('name')}
- Country: {customer_data.get('country')}
- Account Age: {customer_data.get('account_age_days')} days
- Device Trust Score: {customer_data.get('device_trust_score')}
- Past Fraud: {customer_data.get('past_fraud')}

Transaction History:
- Total Transactions: {len(transaction_history) if isinstance(transaction_history, list) else 0}

FRAUD RISK INDICATORS:
- High Amount: {high_amount}
- High Risk Country: {high_risk_country}
- New Account: {new_account}
- Low Device Trust: {low_device_trust}
- Past Fraud History: {past_fraud}

Ready for risk assessment analysis.
"""
                
                result = CustomerDataResponse(
                    customer_data=analysis_text,
                    transaction_data=f"Workflow analysis for {request.transaction_id}",
                    transaction_id=request.transaction_id,
                    status="SUCCESS",
                    raw_transaction=transaction_data,
                    raw_customer=customer_data,
                    transaction_history=transaction_history if isinstance(transaction_history, list) else []
                )
                
                span.set_attribute("executor.success", True)
                span.add_event("Customer data retrieval completed successfully")
            
            await ctx.send_message(result)
            
        except Exception as e:
            span.set_attribute("executor.success", False)
            span.set_attribute("executor.error", str(e))
            span.record_exception(e)
            
            error_result = CustomerDataResponse(
                customer_data=f"Error retrieving data: {str(e)}",
                transaction_data="Error occurred during data retrieval",
                transaction_id=request.transaction_id,
                status="ERROR"
            )
            await ctx.send_message(error_result)

@executor
async def risk_analyzer_executor(
    customer_response: CustomerDataResponse,
    ctx: WorkflowContext[RiskAnalysisResponse]
) -> None:
    """Risk Analyzer Executor - performs AI-powered risk analysis."""
    
    with telemetry.create_processing_span(
        executor_id="risk_analyzer_executor",
        executor_type="RiskAnalysis",
        message_type="CustomerDataResponse"
    ) as span:
        
        # Add business context
        span.set_attributes({
            "transaction.id": customer_response.transaction_id,
            "executor.name": "risk_analyzer_executor",
            "workflow.step": "risk_analysis",
            "business.process": "fraud_detection"
        })
        
        try:
            # Send business event for risk analyzer start
            send_business_event("fraud_detection.risk_analysis.started", {
                "transaction_id": customer_response.transaction_id,
                "executor": "risk_analyzer_executor",
                "step": "ai_risk_assessment"
            })
            
            # Configuration
            project_endpoint = os.environ.get("AI_FOUNDRY_PROJECT_ENDPOINT")
            model_deployment_name = os.environ.get("MODEL_DEPLOYMENT_NAME", "gpt-4o-mini")
            RISK_ANALYSER_AGENT_ID = os.getenv("RISK_ANALYSER_AGENT_ID")
            
            span.set_attributes({
                "ai.model": model_deployment_name,
                "agent.id": RISK_ANALYSER_AGENT_ID or "not_configured"
            })
            
            if not RISK_ANALYSER_AGENT_ID:
                raise ValueError("RISK_ANALYSER_AGENT_ID required")
            
            span.add_event("Starting AI risk analysis", {
                "model": model_deployment_name,
                "agent_id": RISK_ANALYSER_AGENT_ID
            })
            
            # Create sub-span for AI client initialization
            with telemetry.tracer.start_as_current_span("executor.process.ai_client_setup") as client_span:
                client_span.set_attributes({
                    "ai.service": "azure_ai_foundry",
                    "ai.agent_id": RISK_ANALYSER_AGENT_ID or "unknown"
                })
                
                async with AzureCliCredential() as credential:
                    risk_client = AzureAIAgentClient(
                        project_endpoint=project_endpoint,
                        model_deployment_name=model_deployment_name,
                        async_credential=credential,
                        agent_id=RISK_ANALYSER_AGENT_ID
                    )
                    
                    client_span.add_event("AI client initialized successfully")
                
                async with risk_client as client:
                    risk_agent = ChatAgent(
                        chat_client=client,
                        model_id=model_deployment_name,
                        store=True
                    )
                    
                    # Create risk assessment prompt
                    risk_prompt = f"""
Based on the comprehensive fraud analysis provided below, please provide your expert regulatory and compliance risk assessment:

Analysis Data: {customer_response.customer_data}

Please focus on:
1. Validating the risk factors identified in the analysis
2. Assessing the risk score and level from a regulatory perspective
3. Providing additional AML/KYC compliance considerations
4. Checking against sanctions lists and regulatory requirements
5. Final recommendation on transaction approval/blocking/investigation
6. Regulatory reporting requirements if any

Transaction ID: {customer_response.transaction_id}

Provide a structured risk assessment with clear regulatory justification.
"""
                    
                    # Run AI analysis with timing
                    start_time = asyncio.get_event_loop().time()
                    result = await risk_agent.run(risk_prompt)
                    end_time = asyncio.get_event_loop().time()
                    
                    # Record AI processing time
                    processing_time = end_time - start_time
                    span.set_attribute("ai.processing_time_seconds", processing_time)
                    span.add_event("AI analysis completed", {
                        "processing_time": processing_time,
                        "response_length": len(result.text) if result and hasattr(result, 'text') else 0
                    })
                    
                    result_text = result.text if result and hasattr(result, 'text') else "No response from risk agent"
                    
                    # Parse structured risk data
                    risk_factors = []
                    recommendation = "INVESTIGATE"  # Default
                    compliance_notes = ""
                    
                    # Analyze AI response for key indicators
                    if "HIGH RISK" in result_text.upper() or "BLOCK" in result_text.upper():
                        recommendation = "BLOCK"
                        risk_factors.append("High risk transaction identified")
                    elif "LOW RISK" in result_text.upper() or "APPROVE" in result_text.upper():
                        recommendation = "APPROVE"
                    
                    if "IRAN" in result_text.upper() or "SANCTIONS" in result_text.upper():
                        compliance_notes = "Sanctions compliance review required"
                    
                    # Calculate detailed risk score using the same parsing logic as compliance report
                    parsed_risk_data = parse_risk_analysis_result(result_text)
                    
                    if "parsed_elements" in parsed_risk_data and "risk_score" in parsed_risk_data["parsed_elements"]:
                        # Use the detailed parsed risk score (0-100) and convert to 0-10 scale as required by MCP tool
                        detailed_score = parsed_risk_data["parsed_elements"]["risk_score"]
                        risk_score_value = detailed_score / 10.0  # Convert 0-100 to 0-10 scale for MCP tool compatibility
                    else:
                        # If parsing fails, raise an error instead of using fallback
                        raise ValueError("Failed to parse risk score from AI response")
                    
                    # Record business metrics using telemetry manager with detailed tracking
                    with telemetry.create_detailed_operation_span(
                        "risk_score_recording", 
                        "business_metrics",
                        risk_score=risk_score_value,
                        recommendation=recommendation
                    ) as risk_metric_span:
                        risk_metric_span.set_attributes({
                            "metric.type": "risk_score_histogram",
                            "risk.score_value": risk_score_value,
                            "risk.recommendation": recommendation
                        })
                        telemetry.record_risk_score(risk_score_value, customer_response.transaction_id, recommendation)
                        risk_metric_span.add_event("Risk score metric recorded", {
                            "score": risk_score_value,
                            "recommendation": recommendation
                        })
                    
                    # Send comprehensive business events
                    send_business_event("fraud_detection.risk.assessed", {
                        "transaction_id": customer_response.transaction_id,
                        "risk_score": str(risk_score_value),
                        "recommendation": recommendation,
                        "processing_time_seconds": str(processing_time)
                    })
                    
                    send_business_event("fraud_detection.ai_processing.completed", {
                        "transaction_id": customer_response.transaction_id,
                        "executor": "risk_analyzer_executor",
                        "model": model_deployment_name,
                        "processing_time": processing_time,
                        "response_length": len(result_text)
                    })
                    
                    send_business_event("fraud_detection.risk_factors.identified", {
                        "transaction_id": customer_response.transaction_id,
                        "risk_factors_count": len(risk_factors),
                        "recommendation": recommendation
                    })
                    
                    span.set_attributes({
                        "risk.score": risk_score_value,
                        "risk.recommendation": recommendation,
                        "risk.factors_count": len(risk_factors),
                        "executor.success": True
                    })
                    
                    final_result = RiskAnalysisResponse(
                        risk_analysis=result_text,
                        risk_score="Assessed by Risk Agent based on Cosmos DB data",
                        transaction_id=customer_response.transaction_id,
                        status="SUCCESS",
                        risk_factors=risk_factors,
                        recommendation=recommendation,
                        compliance_notes=compliance_notes
                    )
                    
                    await ctx.send_message(final_result)
        
        except Exception as e:
            span.set_attribute("executor.success", False)
            span.set_attribute("executor.error", str(e))
            span.record_exception(e)
            
            error_result = RiskAnalysisResponse(
                risk_analysis=f"Error in risk analysis: {str(e)}",
                risk_score="Unknown",
                transaction_id=customer_response.transaction_id if customer_response else "Unknown",
                status="ERROR"
            )
            await ctx.send_message(error_result)

@executor
async def compliance_report_executor(
    risk_response: RiskAnalysisResponse,
    ctx: WorkflowContext[Never, ComplianceAuditResponse]
) -> None:
    """Compliance Report Executor that generates audit reports from risk analysis results without MCP integration."""
    
    with telemetry.create_processing_span(
        executor_id="compliance_report_executor",
        executor_type="ComplianceReport", 
        message_type="RiskAnalysisResponse"
    ) as span:
        
        # Add business context
        span.set_attributes({
            "transaction.id": risk_response.transaction_id,
            "executor.name": "compliance_report_executor",
            "workflow.step": "compliance_report",
            "business.process": "fraud_detection",
            "risk.recommendation": risk_response.recommendation
        })
        
        try:
            # Send business event for compliance report start
            send_business_event("fraud_detection.compliance_report.started", {
                "transaction_id": risk_response.transaction_id,
                "executor": "compliance_report_executor", 
                "risk_recommendation": risk_response.recommendation
            })
            
            # Configuration
            project_endpoint = os.environ.get("AI_FOUNDRY_PROJECT_ENDPOINT")
            model_deployment_name = os.environ.get("MODEL_DEPLOYMENT_NAME", "gpt-4o-mini")
            COMPLIANCE_REPORT_AGENT_ID = os.getenv("COMPLIANCE_REPORT_AGENT_ID")
            
            span.set_attributes({
                "ai.model": model_deployment_name,
                "agent.id": COMPLIANCE_REPORT_AGENT_ID or "not_configured"
            })
            
            if not COMPLIANCE_REPORT_AGENT_ID:
                raise ValueError("COMPLIANCE_REPORT_AGENT_ID required")
            
            span.add_event("Starting AI Foundry compliance report generation")
            
            # Use AI Foundry Agent Client like Challenge 2
            async with AzureCliCredential() as credential:
                compliance_client = AzureAIAgentClient(
                    project_endpoint=project_endpoint,
                    model_deployment_name=model_deployment_name,
                    async_credential=credential,
                    agent_id=COMPLIANCE_REPORT_AGENT_ID
                )
                
                async with compliance_client as client:
                    compliance_agent = ChatAgent(
                        chat_client=client,
                        model_id=model_deployment_name,
                        store=True
                    )
                    
                    # Create comprehensive compliance report prompt focused on audit reporting only
                    compliance_prompt = f"""Generate a comprehensive compliance audit report based on this risk analysis:

Risk Analysis Result:
{risk_response.risk_analysis}

Transaction ID: {risk_response.transaction_id}
Risk Score: {risk_response.risk_score}
Recommendation: {risk_response.recommendation}
Risk Factors: {risk_response.risk_factors}
Compliance Notes: {risk_response.compliance_notes}

Please provide a structured audit report including:
1. Formal compliance audit report with detailed compliance ratings
2. Risk factor analysis and regulatory implications
3. Executive summary of audit findings
4. Recommendations for management action and compliance measures
5. Compliance status assessment and regulatory filing requirements
6. Detailed audit conclusions with regulatory justification

Focus on regulatory compliance, audit documentation, and actionable compliance recommendations. 
Provide a comprehensive compliance assessment that management can use for regulatory reporting and internal compliance processes."""
                    
                    start_time = asyncio.get_event_loop().time()
                    result = await compliance_agent.run(compliance_prompt)
                    end_time = asyncio.get_event_loop().time()
                    
                    processing_time = end_time - start_time
                    span.set_attribute("ai.compliance_processing_time", processing_time)
                
                result_text = result.text if result and hasattr(result, 'text') else "No response from compliance agent"
                
                # Generate structured audit report locally to ensure consistency
                local_audit = generate_audit_report_from_risk_analysis(risk_response.risk_analysis)
                
                if "error" not in local_audit:
                    # Extract risk score from the correct location in the audit report
                    risk_score = 0.0
                    if "source_analysis" in local_audit and "parsed_elements" in local_audit["source_analysis"]:
                        parsed_elements = local_audit["source_analysis"]["parsed_elements"]
                        risk_score = parsed_elements.get("risk_score", 0.0)
                    
                    # Combine AI-generated insights with structured local audit
                    final_result = ComplianceAuditResponse(
                        audit_report_id=local_audit["audit_report_id"],
                        audit_conclusion=f"{local_audit['executive_summary']['audit_conclusion']} | AI Analysis: {result_text[:300]}...",
                        compliance_rating=local_audit["compliance_status"]["compliance_rating"],
                        risk_score=risk_score,
                        risk_factors_identified=local_audit["detailed_findings"]["risk_factors_identified"],
                        compliance_concerns=local_audit["detailed_findings"]["compliance_concerns"],
                        recommendations=local_audit["detailed_findings"]["recommendations"],
                        requires_immediate_action=local_audit["compliance_status"]["requires_immediate_action"],
                        requires_regulatory_filing=local_audit["compliance_status"]["requires_regulatory_filing"],
                        transaction_id=risk_response.transaction_id,
                        status="SUCCESS"
                    )
                else:
                    # If MCP detection fails, raise an error instead of using fallback
                    raise ValueError("Failed to detect MCP tool usage and no fallback allowed")
                
                # Record compliance decision metric
                telemetry.record_compliance_decision(
                    final_result.compliance_rating,
                    risk_response.transaction_id,
                    immediate_action=str(final_result.requires_immediate_action),
                    mcp_enabled="false"
                )
                
                # Send business event
                send_business_event("fraud_detection.compliance.completed", {
                    "transaction_id": risk_response.transaction_id,
                    "compliance_rating": final_result.compliance_rating,
                    "immediate_action": str(final_result.requires_immediate_action),
                    "regulatory_filing": str(final_result.requires_regulatory_filing),
                    "audit_report_id": final_result.audit_report_id
                })
                
                span.set_attributes({
                    "compliance.rating": final_result.compliance_rating,
                    "compliance.immediate_action": final_result.requires_immediate_action,
                    "compliance.regulatory_filing": final_result.requires_regulatory_filing,
                    "executor.success": True,
                    "ai.enhanced": True
                })
                
                span.add_event("Compliance report generated successfully", {
                    "report_id": final_result.audit_report_id,
                    "compliance_rating": final_result.compliance_rating,
                    "processing_time": processing_time
                })
                
                await ctx.yield_output(final_result)
            
        except Exception as e:
            span.set_attribute("executor.success", False)
            span.set_attribute("executor.error", str(e))
            span.record_exception(e)
            
            error_result = ComplianceAuditResponse(
                audit_report_id="ERROR_REPORT",
                audit_conclusion=f"Error in compliance reporting: {str(e)}",
                compliance_rating="ERROR",
                risk_score=0.0,
                transaction_id=risk_response.transaction_id if risk_response else "Unknown",
                status="ERROR"
            )
            await ctx.yield_output(error_result)

@executor
async def fraud_alert_executor(
    risk_response: RiskAnalysisResponse,
    ctx: WorkflowContext[Never, FraudAlertResponse]
) -> None:
    """Fraud Alert Executor using Azure AI Foundry Agent with MCP tool integration."""
    
    with telemetry.create_processing_span(
        executor_id="fraud_alert_executor",
        executor_type="FraudAlert",
        message_type="RiskAnalysisResponse"
    ) as span:
        
        # Add business context
        span.set_attributes({
            "transaction.id": risk_response.transaction_id,
            "executor.name": "fraud_alert_executor",
            "workflow.step": "fraud_alert",
            "business.process": "fraud_detection",
            "risk.recommendation": risk_response.recommendation
        })
        
        try:
            # Send business event for fraud alert start
            send_business_event("fraud_detection.fraud_alert.started", {
                "transaction_id": risk_response.transaction_id,
                "executor": "fraud_alert_executor",
                "risk_recommendation": risk_response.recommendation
            })
            
            # Configuration with validation
            project_endpoint = os.environ.get("AI_FOUNDRY_PROJECT_ENDPOINT")
            model_deployment_name = os.environ.get("MODEL_DEPLOYMENT_NAME")
            mcp_endpoint = os.environ.get("MCP_SERVER_ENDPOINT")
            mcp_subscription_key = os.environ.get("APIM_SUBSCRIPTION_KEY")
            
            # Check for required parameters
            missing_params = []
            if not project_endpoint:
                missing_params.append("AI_FOUNDRY_PROJECT_ENDPOINT")
            if not model_deployment_name:
                missing_params.append("MODEL_DEPLOYMENT_NAME")
            if not mcp_endpoint:
                missing_params.append("MCP_SERVER_ENDPOINT")
            if not mcp_subscription_key:
                missing_params.append("APIM_SUBSCRIPTION_KEY")
            
            span.set_attributes({
                "ai.model": model_deployment_name or "not_configured",
                "mcp.endpoint": mcp_endpoint or "not_configured",
                "config.missing_params": len(missing_params)
            })
            
            # Validate required parameters - fail if any are missing
            if missing_params:
                raise ValueError(f"Missing required parameters for fraud alert executor: {', '.join(missing_params)}")
            
            from azure.ai.projects import AIProjectClient
            from azure.identity import DefaultAzureCredential
            from azure.ai.agents.models import (
                ListSortOrder,
                McpTool,
                RequiredMcpToolCall,
                RunStepActivityDetails,
                SubmitToolApprovalAction,
                ToolApproval,
            )
            import time
            
            span.add_event("Starting MCP-enabled fraud alert processing")
            
            project_client = AIProjectClient(
                endpoint=project_endpoint,
                credential=DefaultAzureCredential(),
            )
            
            # Initialize agent MCP tool
            mcp_tool = McpTool(
                server_label="fraudalertmcp",
                server_url=mcp_endpoint,
            )
            mcp_tool.update_headers("Ocp-Apim-Subscription-Key", mcp_subscription_key)
            
            with project_client:
                agents_client = project_client.agents

                # Create fraud alert agent with MCP tool
                agent = agents_client.create_agent(
                    model=model_deployment_name,
                    name="fraud-alert-agent",
                    instructions="""
You are a Fraud Alert Management Agent that specializes in creating and managing fraud alerts for financial transactions.

Your responsibilities include:
- Analyzing risk assessment results to determine if fraud alerts are needed
- Creating appropriate fraud alerts using the MCP tool with correct severity and status
- Determining proper decision actions (ALLOW, BLOCK, MONITOR, INVESTIGATE)
- Providing clear reasoning for alert decisions

When creating fraud alerts, use these enumerations:
- severity (LOW, MEDIUM, HIGH, CRITICAL)
- status (OPEN, INVESTIGATING, RESOLVED, FALSE_POSITIVE)
- decision action (ALLOW, BLOCK, MONITOR, INVESTIGATE)

Create fraud alerts for transactions that meet any of these criteria:
1. High risk scores (>= 75)
2. Sanctions-related concerns
3. High-risk jurisdictions
4. Suspicious patterns or anomalies
5. Regulatory compliance violations

Always create comprehensive alerts with proper risk factor documentation and clear reasoning.
Send alerts using the MCP tool without asking for further confirmation.
""",
                    tools=mcp_tool.definitions,
                )

                # Create thread for communication
                thread = agents_client.threads.create()
                
                # Create comprehensive message based on risk analysis
                risk_summary = f"""
RISK ANALYSIS SUMMARY FOR TRANSACTION {risk_response.transaction_id}

Risk Analysis Result: {risk_response.risk_analysis}
Risk Score: {risk_response.risk_score}
Recommendation: {risk_response.recommendation}
Risk Factors: {risk_response.risk_factors}
Compliance Notes: {risk_response.compliance_notes}
Status: {risk_response.status}

Please analyze this risk assessment and create an appropriate fraud alert using the MCP tool if any risk factors or compliance concerns are identified. 

Include all relevant transaction details, risk factors, and provide clear reasoning for the alert decision.
"""
                
                message = agents_client.messages.create(
                    thread_id=thread.id,
                    role="user",
                    content=f"Please analyze this risk assessment and create a fraud alert if needed: {risk_summary}",
                )
                
                # Execute agent run with tool approvals
                run = agents_client.runs.create(
                    thread_id=thread.id, 
                    agent_id=agent.id, 
                    tool_resources=mcp_tool.resources
                )

                # Process run with automatic tool approvals
                start_time = asyncio.get_event_loop().time()
                while run.status in ["queued", "in_progress", "requires_action"]:
                    time.sleep(1)
                    run = agents_client.runs.get(thread_id=thread.id, run_id=run.id)

                    if run.status == "requires_action" and isinstance(run.required_action, SubmitToolApprovalAction):
                        tool_calls = run.required_action.submit_tool_approval.tool_calls
                        if not tool_calls:
                            agents_client.runs.cancel(thread_id=thread.id, run_id=run.id)
                            break

                        tool_approvals = []
                        for tool_call in tool_calls:
                            if isinstance(tool_call, RequiredMcpToolCall):
                                try:
                                    tool_approvals.append(
                                        ToolApproval(
                                            tool_call_id=tool_call.id,
                                            approve=True,
                                            headers=mcp_tool.headers,
                                        )
                                    )
                                except Exception as e:
                                    span.add_event("Error approving tool call", {"error": str(e)})

                        if tool_approvals:
                            agents_client.runs.submit_tool_outputs(
                                thread_id=thread.id, run_id=run.id, tool_approvals=tool_approvals
                            )

                end_time = asyncio.get_event_loop().time()
                processing_time = end_time - start_time
                
                # Collect agent response
                messages = agents_client.messages.list(
                    thread_id=thread.id, order=ListSortOrder.ASCENDING)
                
                agent_response = ""
                for msg in messages:
                    if msg.role == "assistant" and msg.text_messages:
                        agent_response = msg.text_messages[-1].text.value
                        break
                
                # Parse agent response to extract alert information
                alert_created = False
                alert_id = "NO_ALERT_CREATED"
                severity = "LOW"
                decision_action = "MONITOR"
                assigned_to = "fraud_monitoring_team"
                reasoning = "Standard monitoring based on risk assessment"
                
                if agent_response:
                    # Check if alert was created
                    if any(keyword in agent_response.lower() for keyword in ['alert created', 'createalert', 'alert id', 'fraud alert']):
                        alert_created = True
                        alert_id = f"ALERT_{risk_response.transaction_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                    
                    # Extract severity if mentioned
                    if "HIGH" in agent_response.upper():
                        severity = "HIGH"
                    elif "CRITICAL" in agent_response.upper():
                        severity = "CRITICAL"
                    elif "MEDIUM" in agent_response.upper():
                        severity = "MEDIUM"
                    
                    # Extract decision action if mentioned
                    if "BLOCK" in agent_response.upper():
                        decision_action = "BLOCK"
                    elif "INVESTIGATE" in agent_response.upper():
                        decision_action = "INVESTIGATE"
                    elif "ALLOW" in agent_response.upper():
                        decision_action = "ALLOW"
                    
                    reasoning = agent_response[:200] + "..." if len(agent_response) > 200 else agent_response
                
                final_result = FraudAlertResponse(
                    alert_id=alert_id,
                    alert_status="OPEN" if alert_created else "NO_ACTION_REQUIRED",
                    severity=severity,
                    decision_action=decision_action,
                    alert_created=alert_created,
                    mcp_server_response=agent_response,
                    transaction_id=risk_response.transaction_id,
                    status="SUCCESS",
                    created_timestamp=datetime.now().isoformat(),
                    assigned_to=assigned_to,
                    reasoning=reasoning
                )
                
                # Record metrics and events
                telemetry.record_fraud_alert_created(
                    alert_id, 
                    severity, 
                    decision_action,
                    risk_response.transaction_id
                )
                
                send_business_event("fraud_detection.alert.processed", {
                    "transaction_id": risk_response.transaction_id,
                    "alert_created": str(alert_created),
                    "alert_id": alert_id,
                    "severity": severity,
                    "decision_action": decision_action,
                    "processing_time_seconds": str(processing_time)
                })
                
                span.set_attributes({
                    "alert.created": alert_created,
                    "alert.id": alert_id,
                    "alert.severity": severity,
                    "alert.decision_action": decision_action,
                    "mcp.processing_time": processing_time,
                    "executor.success": True
                })
                
                span.add_event("Fraud alert processing completed", {
                    "alert_created": str(alert_created),
                    "alert_id": alert_id,
                    "processing_time": processing_time
                })
                
                # Clean up agent (optional - comment out to reuse)
                # agents_client.delete_agent(agent.id)
                
                await ctx.yield_output(final_result)
            
        except Exception as e:
            span.set_attribute("executor.success", False)
            span.set_attribute("executor.error", str(e))
            span.record_exception(e)
            
            error_result = FraudAlertResponse(
                alert_id="ERROR_ALERT",
                alert_status="ERROR",
                severity="UNKNOWN",
                decision_action="ERROR",
                alert_created=False,
                mcp_server_response=f"Error in fraud alert processing: {str(e)}",
                transaction_id=risk_response.transaction_id if risk_response else "Unknown",
                status="ERROR",
                created_timestamp=datetime.now().isoformat(),
                assigned_to="error_handling_team",
                reasoning=f"Error occurred during fraud alert processing: {str(e)}"
            )
            await ctx.yield_output(error_result)

async def run_fraud_detection_workflow():
    """Execute the fraud detection workflow with comprehensive observability and parallel execution."""
    
    with telemetry.create_workflow_span(
        "fraud_detection_workflow",
        business_process="financial_compliance"
    ) as workflow_span:
        
        workflow_span.add_event("Building parallel workflow")
        
        # Build workflow with four executors - parallel execution for compliance and fraud alert
        workflow = (
            WorkflowBuilder()
            .set_start_executor(customer_data_executor)
            .add_edge(customer_data_executor, risk_analyzer_executor)
            .add_edge(risk_analyzer_executor, compliance_report_executor)  # Parallel path 1
            .add_edge(risk_analyzer_executor, fraud_alert_executor)       # Parallel path 2
            .build()
        )
        
        # Create request
        request = AnalysisRequest(
            message="Comprehensive fraud analysis using Microsoft Agent Framework with parallel execution and observability",
            transaction_id="TX1012"
        )
        
        workflow_span.set_attributes({
            "workflow.request.transaction_id": request.transaction_id,
            "workflow.request.message": request.message,
            "workflow.architecture": "parallel_execution",
            "workflow.executors_count": 4
        })
        
        workflow_span.add_event("Starting parallel workflow execution")
        
        # Execute workflow with streaming and collect outputs from both parallel paths
        compliance_output = None
        fraud_alert_output = None
        events_processed = 0
        
        async for event in workflow.run_stream(request):
            events_processed += 1
            
            # Log each workflow event
            workflow_span.add_event(f"Workflow event: {type(event).__name__}", {
                "event.type": type(event).__name__,
                "events.processed": events_processed
            })
            
            # Capture outputs from both parallel executors
            if isinstance(event, WorkflowOutputEvent):
                if isinstance(event.data, ComplianceAuditResponse):
                    compliance_output = event.data
                    workflow_span.add_event("Compliance report completed", {
                        "compliance.rating": compliance_output.compliance_rating,
                        "compliance.risk_score": compliance_output.risk_score
                    })
                elif isinstance(event.data, FraudAlertResponse):
                    fraud_alert_output = event.data
                    workflow_span.add_event("Fraud alert completed", {
                        "alert.created": fraud_alert_output.alert_created,
                        "alert.severity": fraud_alert_output.severity,
                        "alert.decision_action": fraud_alert_output.decision_action
                    })
        
        workflow_span.set_attributes({
            "workflow.events_processed": events_processed,
            "workflow.compliance_success": compliance_output is not None,
            "workflow.fraud_alert_success": fraud_alert_output is not None,
            "workflow.parallel_success": compliance_output is not None and fraud_alert_output is not None
        })
        
        return compliance_output, fraud_alert_output

async def main():
    """Main function with observability setup and parallel workflow execution."""
    
    # Initialize observability first
    initialize_telemetry()
    
    # Create main application span
    with telemetry.create_workflow_span("fraud_detection_application") as main_span:
        
        trace_id = get_current_trace_id()
        print(f"🔍 Starting Challenge 3 fraud detection workflow with observability")
        print(f"📊 Trace ID: {trace_id}")
        
        main_span.set_attributes({
            "application.name": "fraud_detection_system_challenge2",
            "application.version": "2.0.0",
            "application.architecture": "parallel_execution",
            "trace.id": trace_id or "unknown"
        })
        
        try:
            main_span.add_event("Starting parallel workflow execution")
            compliance_result, fraud_alert_result = await run_fraud_detection_workflow()
            
            # Record results in telemetry
            main_span.set_attributes({
                "result.compliance_success": compliance_result is not None,
                "result.fraud_alert_success": fraud_alert_result is not None,
                "result.parallel_success": compliance_result is not None and fraud_alert_result is not None
            })
            
            if compliance_result:
                main_span.set_attributes({
                    "compliance.audit_report_id": compliance_result.audit_report_id,
                    "compliance.transaction_id": compliance_result.transaction_id,
                    "compliance.rating": compliance_result.compliance_rating,
                    "compliance.risk_score": compliance_result.risk_score,
                    "compliance.immediate_action": compliance_result.requires_immediate_action,
                    "compliance.regulatory_filing": compliance_result.requires_regulatory_filing
                })
            
            if fraud_alert_result:
                main_span.set_attributes({
                    "fraud_alert.alert_id": fraud_alert_result.alert_id,
                    "fraud_alert.transaction_id": fraud_alert_result.transaction_id,
                    "fraud_alert.created": fraud_alert_result.alert_created,
                    "fraud_alert.severity": fraud_alert_result.severity,
                    "fraud_alert.decision_action": fraud_alert_result.decision_action,
                    "fraud_alert.status": fraud_alert_result.alert_status
                })
            
            print(f"\n🎯 4-EXECUTOR PARALLEL WORKFLOW RESULTS WITH OBSERVABILITY")
            print(f"=" * 70)
            
            # Display Compliance Report results
            if compliance_result and isinstance(compliance_result, ComplianceAuditResponse):
                print(f"\n📋 COMPLIANCE REPORT EXECUTOR:")
                print(f"   Status: {compliance_result.status}")
                print(f"   Transaction ID: {compliance_result.transaction_id}")
                print(f"   Audit Report ID: {compliance_result.audit_report_id}")
                print(f"   Compliance Rating: {compliance_result.compliance_rating}")
                print(f"   Risk Score: {compliance_result.risk_score:.2f}")
                print(f"   Conclusion: {compliance_result.audit_conclusion[:100]}...")
                
                if compliance_result.requires_immediate_action:
                    print("   ⚠️  IMMEDIATE ACTION REQUIRED")
                if compliance_result.requires_regulatory_filing:
                    print("   📋 REGULATORY FILING REQUIRED")
            else:
                print(f"\n� COMPLIANCE REPORT EXECUTOR: ❌ FAILED")
            
            # Display Fraud Alert results
            if fraud_alert_result and isinstance(fraud_alert_result, FraudAlertResponse):
                print(f"\n🚨 FRAUD ALERT EXECUTOR:")
                print(f"   Status: {fraud_alert_result.status}")
                print(f"   Transaction ID: {fraud_alert_result.transaction_id}")
                print(f"   Alert ID: {fraud_alert_result.alert_id}")
                print(f"   Alert Created: {'✅ YES' if fraud_alert_result.alert_created else '❌ NO'}")
                print(f"   Severity: {fraud_alert_result.severity}")
                print(f"   Decision Action: {fraud_alert_result.decision_action}")
                print(f"   Alert Status: {fraud_alert_result.alert_status}")
                print(f"   Assigned To: {fraud_alert_result.assigned_to}")
                if fraud_alert_result.created_timestamp:
                    print(f"   Created At: {fraud_alert_result.created_timestamp}")
            else:
                print(f"\n� FRAUD ALERT EXECUTOR: ❌ FAILED")
            
            main_span.add_event("Parallel workflow results displayed successfully")
            
            return compliance_result, fraud_alert_result
            
        except Exception as e:
            main_span.set_attribute("application.error", str(e))
            main_span.record_exception(e)
            print(f"❌ Parallel workflow execution failed: {str(e)}")
            return None, None
        
        finally:
            flush_telemetry()
            print(f"\n🔍 Trace completed: {trace_id}")

if __name__ == "__main__":
    compliance, fraud_alert = asyncio.run(main())