import asyncio
import os
import re
from datetime import datetime
from typing_extensions import Never
from agent_framework import WorkflowBuilder, WorkflowContext, WorkflowOutputEvent, executor, ChatAgent
from agent_framework.azure import AzureAIAgentClient
from azure.identity.aio import AzureCliCredential
from azure.cosmos import CosmosClient
from dotenv import load_dotenv
from pydantic import BaseModel

# Load environment variables
load_dotenv(override=True)

# Initialize Cosmos DB connection
cosmos_endpoint = os.environ.get("COSMOS_ENDPOINT")
cosmos_key = os.environ.get("COSMOS_KEY")
cosmos_client = CosmosClient(cosmos_endpoint, cosmos_key)
database = cosmos_client.get_database_client("FinancialComplianceDB")
customers_container = database.get_container_client("Customers")
transactions_container = database.get_container_client("Transactions")

# Cosmos DB helper functions
def get_transaction_data(transaction_id: str) -> dict:
    """Get transaction data from Cosmos DB"""
    try:
        query = f"SELECT * FROM c WHERE c.transaction_id = '{transaction_id}'"
        items = list(transactions_container.query_items(
            query=query,
            enable_cross_partition_query=True
        ))
        return items[0] if items else {"error": f"Transaction {transaction_id} not found"}
    except Exception as e:
        return {"error": str(e)}

def get_customer_data(customer_id: str) -> dict:
    """Get customer data from Cosmos DB"""
    try:
        query = f"SELECT * FROM c WHERE c.customer_id = '{customer_id}'"
        items = list(customers_container.query_items(
            query=query,
            enable_cross_partition_query=True
        ))
        return items[0] if items else {"error": f"Customer {customer_id} not found"}
    except Exception as e:
        return {"error": str(e)}

def get_customer_transactions(customer_id: str) -> list:
    """Get all transactions for a customer from Cosmos DB"""
    try:
        query = f"SELECT * FROM c WHERE c.customer_id = '{customer_id}'"
        items = list(transactions_container.query_items(
            query=query,
            enable_cross_partition_query=True
        ))
        return items
    except Exception as e:
        return [{"error": str(e)}]

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

@executor
async def customer_data_executor(
    request: AnalysisRequest,
    ctx: WorkflowContext[CustomerDataResponse]
) -> None:
    """Customer Data Executor that retrieves data from Cosmos DB and sends to next executor."""
    
    try:
        # Get real data from Cosmos DB
        transaction_data = get_transaction_data(request.transaction_id)
        
        if "error" in transaction_data:
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
            
            # Create comprehensive analysis
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
- High Amount: {transaction_data.get('amount', 0) > 10000}
- High Risk Country: {transaction_data.get('destination_country') in ['IR', 'RU', 'NG', 'KP', 'YE', 'AF', 'SY', 'SO', 'LY', 'IQ', 'MM', 'BY', 'VE']}
- New Account: {customer_data.get('account_age_days', 0) < 30}
- Low Device Trust: {customer_data.get('device_trust_score', 1.0) < 0.5}
- Past Fraud History: {customer_data.get('past_fraud', False)}

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
        
        # Send data to next executor
        await ctx.send_message(result)
        
    except Exception as e:
        error_result = CustomerDataResponse(
            customer_data=f"Error retrieving data: {str(e)}",
            transaction_data="Error occurred during data retrieval",
            transaction_id=request.transaction_id,
            status="ERROR"
        )
        await ctx.send_message(error_result)

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
            calculated_score = 0.0
            
            # High-risk countries should automatically get high scores
            if any(country in text_lower for country in ['russia', 'russian', 'iran', 'iranian', 'north korea', 'syria', 'yemen']):
                calculated_score += 80
            elif "high-risk country" in text_lower or "high risk country" in text_lower:
                calculated_score += 75
            elif "sanctions" in text_lower:
                calculated_score += 85
            
            # Large amounts increase risk
            if "large amount" in text_lower or "high amount" in text_lower:
                calculated_score += 20
                
            # Suspicious patterns
            if "suspicious" in text_lower and "not suspicious" not in text_lower:
                calculated_score += 30
                
            # Block/High Risk recommendations
            if "block" in text_lower or "high risk" in text_lower:
                calculated_score = max(calculated_score, 80)
            elif "medium risk" in text_lower:
                calculated_score = max(calculated_score, 60)
                
            # Cap at 100
            calculated_score = min(calculated_score, 100)
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
    """Generates a formal audit report based on risk analyser findings."""
    try:
        parsed_analysis = parse_risk_analysis_result(risk_analysis_text)
        
        if "error" in parsed_analysis:
            return parsed_analysis
        
        elements = parsed_analysis["parsed_elements"]
        
        audit_report = {
            "audit_report_id": f"AUDIT_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "report_type": report_type,
            "generated_timestamp": datetime.now().isoformat(),
            "auditor": "Compliance Report Agent",
            "source_analysis": "Risk Analyser Agent",
            
            "executive_summary": {
                "transaction_id": elements.get("transaction_id", "N/A"),
                "risk_score": elements.get("risk_score", "Not specified"),
                "risk_level": elements.get("risk_level", "Not specified"),
                "audit_conclusion": ""
            },
            
            "detailed_findings": {
                "risk_factors_identified": elements.get("risk_factors", []),
                "compliance_concerns": [],
                "regulatory_implications": [],
                "recommendations": []
            },
            
            "compliance_status": {
                "requires_regulatory_filing": False,
                "requires_enhanced_monitoring": False,
                "requires_immediate_action": False,
                "compliance_rating": "PENDING"
            }
        }
        
        # Analyze risk score for audit conclusions
        risk_score = elements.get("risk_score", 0)
        if isinstance(risk_score, (int, float)):
            if risk_score >= 75:
                audit_report["executive_summary"]["audit_conclusion"] = "HIGH RISK - Immediate review required"
                audit_report["compliance_status"]["requires_immediate_action"] = True
                audit_report["compliance_status"]["compliance_rating"] = "NON_COMPLIANT"
            elif risk_score >= 50:
                audit_report["executive_summary"]["audit_conclusion"] = "MEDIUM RISK - Enhanced monitoring recommended"
                audit_report["compliance_status"]["requires_enhanced_monitoring"] = True
                audit_report["compliance_status"]["compliance_rating"] = "CONDITIONAL_COMPLIANCE"
            else:
                audit_report["executive_summary"]["audit_conclusion"] = "LOW RISK - Standard monitoring sufficient"
                audit_report["compliance_status"]["compliance_rating"] = "COMPLIANT"
        
        # Add specific findings based on risk factors
        risk_factors = elements.get("risk_factors", [])
        
        if "HIGH_RISK_JURISDICTION" in risk_factors:
            audit_report["detailed_findings"]["compliance_concerns"].append(
                "Transaction involves high-risk jurisdiction requiring enhanced monitoring"
            )
            audit_report["compliance_status"]["requires_regulatory_filing"] = True
        
        if "SANCTIONS_CONCERN" in risk_factors:
            audit_report["detailed_findings"]["compliance_concerns"].append(
                "Potential sanctions-related issues identified in risk analysis"
            )
            audit_report["compliance_status"]["requires_immediate_action"] = True
        
        # Generate recommendations
        if audit_report["compliance_status"]["requires_immediate_action"]:
            audit_report["detailed_findings"]["recommendations"].extend([
                "Freeze transaction pending investigation",
                "Conduct enhanced customer due diligence",
                "File suspicious activity report with regulators"
            ])
        elif audit_report["compliance_status"]["requires_enhanced_monitoring"]:
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
async def risk_analyzer_executor(
    customer_response: CustomerDataResponse,
    ctx: WorkflowContext[RiskAnalysisResponse]  # Changed: No longer terminal, sends to next executor
) -> None:
    """Risk Analyzer Executor that processes customer data and sends to compliance executor."""
    
    try:
        # Configuration
        project_endpoint = os.environ.get("AI_FOUNDRY_PROJECT_ENDPOINT")
        model_deployment_name = os.environ.get("MODEL_DEPLOYMENT_NAME", "gpt-4o-mini")
        RISK_ANALYSER_AGENT_ID = os.getenv("RISK_ANALYSER_AGENT_ID")
        
        if not RISK_ANALYSER_AGENT_ID:
            raise ValueError("RISK_ANALYSER_AGENT_ID required")
        
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
                
                result = await risk_agent.run(risk_prompt)
                result_text = result.text if result and hasattr(result, 'text') else "No response from risk agent"
                
                # Parse structured risk data
                risk_factors = []
                recommendation = "INVESTIGATE"  # Default
                compliance_notes = ""
                
                if "HIGH RISK" in result_text.upper() or "BLOCK" in result_text.upper():
                    recommendation = "BLOCK"
                    risk_factors.append("High risk transaction identified")
                elif "LOW RISK" in result_text.upper() or "APPROVE" in result_text.upper():
                    recommendation = "APPROVE"
                
                if "IRAN" in result_text.upper() or "SANCTIONS" in result_text.upper():
                    compliance_notes = "Sanctions compliance review required"
                    
                final_result = RiskAnalysisResponse(
                    risk_analysis=result_text,
                    risk_score="Assessed by Risk Agent based on Cosmos DB data",
                    transaction_id=customer_response.transaction_id,
                    status="SUCCESS",
                    risk_factors=risk_factors,
                    recommendation=recommendation,
                    compliance_notes=compliance_notes
                )
                
                # Send data to next executor (compliance report executor)
                await ctx.send_message(final_result)
        
    except Exception as e:
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
    
    try:
        # Import the required modules for OpenAI Responses Client
        from agent_framework import ChatAgent, HostedMCPTool
        from agent_framework.azure import AzureOpenAIResponsesClient
        from azure.identity import AzureCliCredential
        
        # Configuration
        mcp_endpoint = os.environ.get("MCP_SERVER_ENDPOINT")
        mcp_subscription_key = os.environ.get("APIM_SUBSCRIPTION_KEY")
        azure_openai_endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT")
        model_deployment_name = os.environ.get("MODEL_DEPLOYMENT_NAME", "gpt-4o-mini")
        
        # Create OpenAI Responses Client-based compliance agent
        async with ChatAgent(
            chat_client=AzureOpenAIResponsesClient(
                credential=AzureCliCredential(),
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
            
            result = await agent.run(compliance_prompt)
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
                # Combine AI-generated insights with structured local audit
                final_result = ComplianceAuditResponse(
                    audit_report_id=local_audit["audit_report_id"],
                    audit_conclusion=f"{local_audit['executive_summary']['audit_conclusion']} | AI Analysis: {result_text[:300]}...",
                    compliance_rating=local_audit["compliance_status"]["compliance_rating"],
                    risk_score=local_audit["executive_summary"]["risk_score"] if isinstance(local_audit["executive_summary"]["risk_score"], (int, float)) else 0.0,
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
            
            await ctx.yield_output(final_result)
        
    except Exception as e:
        # Fallback to local audit generation if OpenAI client fails
        try:
            local_audit = generate_audit_report_from_risk_analysis(risk_response.risk_analysis)
            
            if "error" not in local_audit:
                fallback_result = ComplianceAuditResponse(
                    audit_report_id=local_audit["audit_report_id"],
                    audit_conclusion=f"{local_audit['executive_summary']['audit_conclusion']} (Fallback Mode)",
                    compliance_rating=local_audit["compliance_status"]["compliance_rating"],
                    risk_score=local_audit["executive_summary"]["risk_score"] if isinstance(local_audit["executive_summary"]["risk_score"], (int, float)) else 0.0,
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
                await ctx.yield_output(fallback_result)
            else:
                raise Exception(f"Both AI and fallback methods failed: {str(e)}")
                
        except Exception as fallback_error:
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
    """Execute the fraud detection workflow using Microsoft Agent Framework."""
    
    # Build workflow with three executors
    workflow = (
        WorkflowBuilder()
        .set_start_executor(customer_data_executor)
        .add_edge(customer_data_executor, risk_analyzer_executor)
        .add_edge(risk_analyzer_executor, compliance_report_executor)  # New edge
        .build()
    )
    
    # Create request
    request = AnalysisRequest(
        message="Comprehensive fraud analysis using Microsoft Agent Framework",
        transaction_id="TX1012"  # Russian transaction for testing
    )
    
    # Execute workflow with streaming
    final_output = None
    
    print("🔄 Executing Fraud Detection Workflow...")
    
    async for event in workflow.run_stream(request):
        # Capture final workflow output
        if isinstance(event, WorkflowOutputEvent):
            final_output = event.data
    
    return final_output

async def main():
    """Main function to run the fraud detection workflow."""
    try:
        result = await run_fraud_detection_workflow()
        
        # Display results
        if result and isinstance(result, ComplianceAuditResponse):
            print(f"\n📋 Compliance Report Executor Results:")
            print(f"   Status: {result.status}")
            print(f"   Transaction ID: {result.transaction_id}")
            print(f"   Audit Report ID: {result.audit_report_id}")
            print(f"   Compliance Rating: {result.compliance_rating}")
            print(f"   Risk Score: {result.risk_score:.2f}")
            print(f"   Conclusion: {result.audit_conclusion[:100]}...")
            
            # Display MCP Tool Usage Information
            if result.mcp_tool_used:
                print(f"   🔧 MCP Tool Used: ✅ YES")
                if result.mcp_actions:
                    print(f"   🔧 MCP Actions: {', '.join(result.mcp_actions)}")
            else:
                print(f"   🔧 MCP Tool Used: ❌ NO")
            
            if result.requires_immediate_action:
                print("   ⚠️  IMMEDIATE ACTION REQUIRED")
            if result.requires_regulatory_filing:
                print("   📋 REGULATORY FILING REQUIRED")
                
            print(f"\n✅ Workflow Completed Successfully")
        else:
            print(f"❌ Workflow failed")
        
        return result
        
    except Exception as e:
        print(f"Workflow execution failed: {str(e)}")
        return None

if __name__ == "__main__":
    result = asyncio.run(main())