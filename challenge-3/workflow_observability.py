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
    mcp_tool_used: bool = False
    mcp_actions: list = []

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
        
        # Extract risk score - try multiple patterns
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

def generate_audit_report_from_risk_analysis(risk_analysis_text: str, report_type: str = "STANDARD") -> dict:
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
        
        # Record metric for transaction processing
        telemetry.record_transaction_processed("data_retrieval", request.transaction_id)
        
        # Send business event
        send_business_event("fraud_detection.transaction.started", {
            "transaction_id": request.transaction_id,
            "step": "data_retrieval",
            "executor": "customer_data_executor"
        })
        
        try:
            span.add_event("Starting customer data retrieval", {
                "transaction.id": request.transaction_id
            })
            
            # Get real data from Cosmos DB (telemetry handled by decorators)
            transaction_data = get_transaction_data(request.transaction_id)
            
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
                customer_data = get_customer_data(customer_id)
                transaction_history = get_customer_transactions(customer_id)
                
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
            
            async with AzureCliCredential() as credential:
                risk_client = AzureAIAgentClient(
                    project_endpoint=project_endpoint,
                    model_deployment_name=model_deployment_name,
                    async_credential=credential,
                    agent_id=RISK_ANALYSER_AGENT_ID
                )
                
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
                        # Use the detailed parsed risk score (0-100) and convert to 0-1 scale
                        detailed_score = parsed_risk_data["parsed_elements"]["risk_score"]
                        risk_score_value = detailed_score / 100.0  # Convert 0-100 to 0-1 scale
                    else:
                        # Fallback to simple calculation if parsing fails
                        risk_score_value = 0.5  # Default medium risk
                        if recommendation == "BLOCK":
                            risk_score_value = 0.9
                        elif recommendation == "APPROVE":
                            risk_score_value = 0.1
                    
                    # Record business metrics using telemetry manager
                    telemetry.record_risk_score(risk_score_value, customer_response.transaction_id, recommendation)
                    
                    # Send business event
                    send_business_event("fraud_detection.risk.assessed", {
                        "transaction_id": customer_response.transaction_id,
                        "risk_score": str(risk_score_value),
                        "recommendation": recommendation,
                        "processing_time_seconds": str(processing_time)
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
    """Compliance Report Executor using OpenAI Responses Client that generates audit reports from risk analysis results."""
    
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
            # Configuration
            mcp_endpoint = os.environ.get("MCP_SERVER_ENDPOINT")
            mcp_subscription_key = os.environ.get("APIM_SUBSCRIPTION_KEY")
            azure_openai_endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT")
            model_deployment_name = os.environ.get("MODEL_DEPLOYMENT_NAME", "gpt-4o-mini")
            
            span.add_event("Starting MCP-enabled compliance report generation")
            
            # Create OpenAI Responses Client-based compliance agent
            async with ChatAgent(
                chat_client=AzureOpenAIResponsesClient(
                    credential=SyncAzureCliCredential(),
                    endpoint=azure_openai_endpoint,
                    deployment_name=model_deployment_name
                ),
                name="ComplianceReportAgent",
                instructions="""You are a Compliance Report Agent specialized in generating formal audit reports based on risk analysis findings and transaction data.

Your primary responsibilities include:
- Analyzing transaction risk summaries and generating compliance audit reports
- Creating appropriate fraud alerts through the MCP server when compliance violations are detected
- Determining correct severity levels (LOW, MEDIUM, HIGH, CRITICAL) for compliance issues
- Setting proper alert status (OPEN, INVESTIGATING, RESOLVED, FALSE_POSITIVE)
- Recommending actions (ALLOW, BLOCK, MONITOR, INVESTIGATE) based on compliance analysis
- Generating executive-level audit summaries and compliance dashboards
- Ensuring regulatory compliance and audit trail documentation

When generating compliance reports:
1. Parse risk analysis data to extract key compliance indicators
2. Assess regulatory compliance based on transaction patterns and risk factors
3. Create formal audit reports with clear findings and recommendations
4. Generate fraud alerts for any transactions that violate compliance thresholds
5. Provide executive summaries for management review

Always create detailed reports with proper risk assessments, regulatory implications, and clear audit trails.""",
                tools=HostedMCPTool(
                    name="Fraud Alert Manager MCP",
                    url=mcp_endpoint,
                    description="Manages fraud alerts and escalations for financial transactions",
                    approval_mode="never_require",
                    headers={
                        "Ocp-Apim-Subscription-Key": mcp_subscription_key
                    } if mcp_subscription_key else {}
                ),
            ) as agent:
                
                # Create comprehensive compliance report prompt with explicit MCP usage
                compliance_prompt = f"""Generate a comprehensive compliance audit report based on this risk analysis:

Risk Analysis Result:
{risk_response.risk_analysis}

Transaction ID: {risk_response.transaction_id}
Risk Score: {risk_response.risk_score}
Recommendation: {risk_response.recommendation}
Risk Factors: {risk_response.risk_factors}
Compliance Notes: {risk_response.compliance_notes}

Please provide a structured audit report including:
1. Formal audit report with compliance ratings
2. Risk factor analysis and regulatory implications
3. Executive summary of findings
4. CREATE A FRAUD ALERT using the MCP tool for any compliance violations detected
5. Recommendations for management action
6. Compliance status and regulatory filing requirements

IMPORTANT: If you detect any compliance issues, risk violations, or suspicious patterns, 
you MUST create a fraud alert using the Fraud Alert Manager MCP tool with appropriate:
- Severity level (LOW, MEDIUM, HIGH, CRITICAL)
- Status (OPEN, INVESTIGATING, RESOLVED, FALSE_POSITIVE)  
- Action (ALLOW, BLOCK, MONITOR, INVESTIGATE)

Additionally, MUST USE MCP TOOL: Please retrieve ALL existing fraud alerts using the 
Fraud Alert Manager MCP tool to include in your compliance analysis.

Focus on regulatory compliance, audit documentation, and actionable recommendations. Return your response in a structured format that I can parse."""
                
                start_time = asyncio.get_event_loop().time()
                result = await agent.run(compliance_prompt)
                end_time = asyncio.get_event_loop().time()
                
                processing_time = end_time - start_time
                span.set_attribute("ai.compliance_processing_time", processing_time)
                
                result_text = result.text if result and hasattr(result, 'text') else "No response from compliance agent"
                
                # Check for MCP tool usage indicators in the AI response
                mcp_tool_used = False
                mcp_actions = []
                
                if result_text:
                    # Look for common MCP tool usage patterns in the response
                    if any(keyword in result_text.lower() for keyword in ['createalert', 'create alert', 'fraud alert created', 'alert id', 'alert created', 'new alert']):
                        mcp_tool_used = True
                        mcp_actions.append("Alert Creation")
                    
                    if any(keyword in result_text.lower() for keyword in ['getallalerts', 'get all alerts', 'existing alerts', 'retrieved alerts', 'found alerts', 'alert retrieval']):
                        mcp_tool_used = True
                        mcp_actions.append("Alert Retrieval")
                    
                    # Check for general MCP tool usage indicators
                    if any(keyword in result_text.lower() for keyword in ['mcp tool', 'fraud alert manager', 'tool used', 'using tool']):
                        mcp_tool_used = True
                        if "Alert Creation" not in mcp_actions and "Alert Retrieval" not in mcp_actions:
                            mcp_actions.append("General MCP Usage")
                
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
                        status="SUCCESS",
                        mcp_tool_used=mcp_tool_used,
                        mcp_actions=mcp_actions
                    )
                else:
                    # Fallback using AI response only
                    final_result = ComplianceAuditResponse(
                        audit_report_id=f"AI_AUDIT_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                        audit_conclusion=result_text[:500] if len(result_text) > 500 else result_text,
                        compliance_rating="AI_GENERATED",
                        risk_score=0.0,
                        transaction_id=risk_response.transaction_id,
                        status="SUCCESS",
                        mcp_tool_used=mcp_tool_used,
                        mcp_actions=mcp_actions
                    )
                
                # Record compliance decision metric with MCP usage
                telemetry.record_compliance_decision(
                    final_result.compliance_rating,
                    risk_response.transaction_id,
                    immediate_action=str(final_result.requires_immediate_action),
                    mcp_enabled=str(mcp_tool_used)
                )
                
                # Send business event with MCP information
                send_business_event("fraud_detection.compliance.completed", {
                    "transaction_id": risk_response.transaction_id,
                    "compliance_rating": final_result.compliance_rating,
                    "immediate_action": str(final_result.requires_immediate_action),
                    "regulatory_filing": str(final_result.requires_regulatory_filing),
                    "audit_report_id": final_result.audit_report_id,
                    "mcp_tool_used": str(mcp_tool_used),
                    "mcp_actions": ",".join(mcp_actions) if mcp_actions else ""
                })
                
                span.set_attributes({
                    "compliance.rating": final_result.compliance_rating,
                    "compliance.immediate_action": final_result.requires_immediate_action,
                    "compliance.regulatory_filing": final_result.requires_regulatory_filing,
                    "mcp.tool_used": mcp_tool_used,
                    "mcp.actions_count": len(mcp_actions),
                    "executor.success": True,
                    "ai.enhanced": True
                })
                
                span.add_event("MCP-enabled compliance report generated successfully", {
                    "report_id": final_result.audit_report_id,
                    "compliance_rating": final_result.compliance_rating,
                    "mcp_tool_used": str(mcp_tool_used),
                    "processing_time": processing_time
                })
                
                await ctx.yield_output(final_result)
            
        except Exception as e:
            # Fallback to local audit generation if OpenAI client fails
            try:
                span.add_event("Falling back to local audit generation due to error", {
                    "error": str(e)
                })
                
                local_audit = generate_audit_report_from_risk_analysis(risk_response.risk_analysis)
                
                if "error" not in local_audit:
                    # Extract risk score from the correct location in the audit report
                    fallback_risk_score = 0.0
                    if "source_analysis" in local_audit and "parsed_elements" in local_audit["source_analysis"]:
                        parsed_elements = local_audit["source_analysis"]["parsed_elements"]
                        fallback_risk_score = parsed_elements.get("risk_score", 0.0)
                    
                    fallback_result = ComplianceAuditResponse(
                        audit_report_id=local_audit["audit_report_id"],
                        audit_conclusion=f"{local_audit['executive_summary']['audit_conclusion']} (Fallback Mode)",
                        compliance_rating=local_audit["compliance_status"]["compliance_rating"],
                        risk_score=fallback_risk_score,
                        risk_factors_identified=local_audit["detailed_findings"]["risk_factors_identified"],
                        compliance_concerns=local_audit["detailed_findings"]["compliance_concerns"],
                        recommendations=local_audit["detailed_findings"]["recommendations"],
                        requires_immediate_action=local_audit["compliance_status"]["requires_immediate_action"],
                        requires_regulatory_filing=local_audit["compliance_status"]["requires_regulatory_filing"],
                        transaction_id=risk_response.transaction_id,
                        status="SUCCESS_FALLBACK",
                        mcp_tool_used=False,
                        mcp_actions=[]
                    )
                    
                    span.set_attributes({
                        "compliance.rating": fallback_result.compliance_rating,
                        "executor.success": True,
                        "executor.fallback": True
                    })
                    
                    await ctx.yield_output(fallback_result)
                else:
                    raise Exception(f"Both AI and fallback methods failed: {str(e)}")
                    
            except Exception as fallback_error:
                span.set_attribute("executor.success", False)
                span.set_attribute("executor.error", str(e))
                span.set_attribute("fallback.error", str(fallback_error))
                span.record_exception(e)
                
                error_result = ComplianceAuditResponse(
                    audit_report_id="ERROR_REPORT",
                    audit_conclusion=f"Error in compliance reporting: {str(e)} | Fallback error: {str(fallback_error)}",
                    compliance_rating="ERROR",
                    risk_score=0.0,
                    transaction_id=risk_response.transaction_id if risk_response else "Unknown",
                    status="ERROR",
                    mcp_tool_used=False,
                    mcp_actions=[]
                )
                await ctx.yield_output(error_result)

async def run_fraud_detection_workflow():
    """Execute the fraud detection workflow with comprehensive observability."""
    
    with telemetry.create_workflow_span(
        "fraud_detection_workflow",
        business_process="financial_compliance"
    ) as workflow_span:
        
        workflow_span.add_event("Building workflow")
        
        # Build workflow with three executors
        workflow = (
            WorkflowBuilder()
            .set_start_executor(customer_data_executor)
            .add_edge(customer_data_executor, risk_analyzer_executor)
            .add_edge(risk_analyzer_executor, compliance_report_executor)
            .build()
        )
        
        # Create request
        request = AnalysisRequest(
            message="Comprehensive fraud analysis using Microsoft Agent Framework with observability",
            transaction_id="TX1012"
        )
        
        workflow_span.set_attributes({
            "workflow.request.transaction_id": request.transaction_id,
            "workflow.request.message": request.message
        })
        
        workflow_span.add_event("Starting workflow execution")
        
        # Execute workflow with streaming and collect all events
        final_output = None
        events_processed = 0
        
        async for event in workflow.run_stream(request):
            events_processed += 1
            
            # Log each workflow event
            workflow_span.add_event(f"Workflow event: {type(event).__name__}", {
                "event.type": type(event).__name__,
                "events.processed": events_processed
            })
            
            # Capture final workflow output
            if isinstance(event, WorkflowOutputEvent):
                final_output = event.data
                workflow_span.add_event("Workflow completed successfully", {
                    "output.type": type(final_output).__name__
                })
        
        workflow_span.set_attributes({
            "workflow.events_processed": events_processed,
            "workflow.success": final_output is not None
        })
        
        return final_output

async def main():
    """Main function with observability setup and workflow execution."""
    
    # Initialize observability first
    initialize_telemetry()
    
    # Create main application span
    with telemetry.create_workflow_span("fraud_detection_application") as main_span:
        
        trace_id = get_current_trace_id()
        print(f"🔍 Starting fraud detection workflow")
        print(f"📊 Trace ID: {trace_id}")
        
        main_span.set_attributes({
            "application.name": "fraud_detection_system",
            "application.version": "1.0.0",
            "trace.id": trace_id or "unknown"
        })
        
        try:
            main_span.add_event("Starting workflow execution")
            result = await run_fraud_detection_workflow()
            
            # Display results with enhanced observability
            if result and isinstance(result, ComplianceAuditResponse):
                main_span.set_attributes({
                    "result.audit_report_id": result.audit_report_id,
                    "result.transaction_id": result.transaction_id,
                    "result.compliance_rating": result.compliance_rating,
                    "result.risk_score": result.risk_score,
                    "result.requires_immediate_action": result.requires_immediate_action,
                    "result.requires_regulatory_filing": result.requires_regulatory_filing,
                    "result.mcp_tool_used": result.mcp_tool_used,
                    "result.mcp_actions_count": len(result.mcp_actions)
                })
                
                print(f"\n✅ Workflow completed successfully!")
                print(f"📋 Audit Report ID: {result.audit_report_id}")
                print(f"🔢 Transaction: {result.transaction_id}")
                print(f"📊 Status: {result.status}")
                print(f"🔍 Compliance Rating: {result.compliance_rating}")
                print(f"📈 Risk Score: {result.risk_score:.2f}")
                print(f"📄 Conclusion: {result.audit_conclusion[:100]}...")
                
                # Display MCP Tool Usage Information
                if result.mcp_tool_used:
                    print(f"🔧 MCP Tool Used: ✅ YES")
                    if result.mcp_actions:
                        print(f"🔧 MCP Actions: {', '.join(result.mcp_actions)}")
                else:
                    print(f"🔧 MCP Tool Used: ❌ NO")
                
                if result.requires_immediate_action:
                    print("⚠️  IMMEDIATE ACTION REQUIRED")
                if result.requires_regulatory_filing:
                    print("📋 REGULATORY FILING REQUIRED")
                
                main_span.add_event("Results displayed successfully")
            else:
                main_span.set_attribute("result.success", False)
                print("❌ No valid result returned from workflow")
            
            return result
            
        except Exception as e:
            main_span.set_attribute("application.error", str(e))
            main_span.record_exception(e)
            print(f"❌ Workflow execution failed: {str(e)}")
            return None
        
        finally:
            # Flush telemetry before finishing
            flush_telemetry()
            print(f"🔍 Trace completed: {trace_id}")
            print("📊 Check Application Insights or configured observability backend for detailed traces")
            print("📋 Custom events should appear in Application Insights within 2-5 minutes")

if __name__ == "__main__":
    result = asyncio.run(main())