import asyncio
import os
import json
import re
from datetime import datetime
from collections import Counter
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
    risk_factors_identified: list = []
    compliance_concerns: list = []
    recommendations: list = []
    requires_immediate_action: bool = False
    requires_regulatory_filing: bool = False
    transaction_id: str
    status: str
    
    def to_readable_text(self) -> str:
        """Convert the audit response to readable text for DevUI display."""
        text = f"""
🔍 FRAUD DETECTION WORKFLOW COMPLETE
═══════════════════════════════════════════════════════════════

📋 AUDIT REPORT: {self.audit_report_id}
Transaction ID: {self.transaction_id}
Status: {self.status}

🎯 EXECUTIVE SUMMARY
────────────────────────────────────────────────────────────────
Audit Conclusion: {self.audit_conclusion}
Compliance Rating: {self.compliance_rating}

⚠️ RISK FACTORS IDENTIFIED
────────────────────────────────────────────────────────────────
{chr(10).join(f"• {factor}" for factor in self.risk_factors_identified) if self.risk_factors_identified else "• No specific risk factors identified"}

🚨 COMPLIANCE CONCERNS
────────────────────────────────────────────────────────────────
{chr(10).join(f"• {concern}" for concern in self.compliance_concerns) if self.compliance_concerns else "• No compliance concerns identified"}

📝 RECOMMENDATIONS
────────────────────────────────────────────────────────────────
{chr(10).join(f"• {rec}" for rec in self.recommendations) if self.recommendations else "• No specific recommendations"}

⚡ ACTION REQUIRED
────────────────────────────────────────────────────────────────
Immediate Action Required: {"YES" if self.requires_immediate_action else "NO"}
Regulatory Filing Required: {"YES" if self.requires_regulatory_filing else "NO"}

═══════════════════════════════════════════════════════════════
Workflow completed successfully. All three agents have processed the transaction.
        """
        return text.strip()

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
- High Risk Country: {transaction_data.get('destination_country') in ['IR', 'RU', 'NG', 'KP']}
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
        
        # Extract risk score
        risk_score_pattern = r'risk\s*score[:\s]*(\d+(?:\.\d+)?)'
        score_match = re.search(risk_score_pattern, text_lower)
        if score_match:
            analysis_data["parsed_elements"]["risk_score"] = float(score_match.group(1))
        
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
        
        # Extract key risk factors mentioned
        risk_factors = []
        if "high-risk country" in text_lower or "high risk country" in text_lower:
            risk_factors.append("HIGH_RISK_JURISDICTION")
        if "large amount" in text_lower or "high amount" in text_lower:
            risk_factors.append("UNUSUAL_AMOUNT")
        if "suspicious" in text_lower:
            risk_factors.append("SUSPICIOUS_PATTERN")
        if "sanction" in text_lower:
            risk_factors.append("SANCTIONS_CONCERN")
        if "frequent" in text_lower or "unusual frequency" in text_lower:
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
            if risk_score >= 80:
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
    ctx: WorkflowContext[RiskAnalysisResponse]
) -> None:
    """Risk Analyzer Executor that processes customer data and sends to compliance executor."""
    
    try:
        # Configuration
        project_endpoint = os.environ.get("AI_FOUNDRY_PROJECT_ENDPOINT")
        model_deployment_name = os.environ.get("MODEL_DEPLOYMENT_NAME", "gpt-4o-mini")
        
        async with AzureCliCredential() as credential:
            risk_client = AzureAIAgentClient(
                project_endpoint=project_endpoint,
                model_deployment_name=model_deployment_name,
                async_credential=credential
            )
            
            async with risk_client as client:
                risk_agent = ChatAgent(
                    chat_client=client,
                    model_id=model_deployment_name,
                    name="RiskAnalyzerAgent",
                    instructions="""You are a Risk Analyser Agent evaluating financial transactions for potential fraud.
                    Given a normalized transaction and customer profile, your task is to:
                    - Apply fraud detection logic using rule-based checks and regulatory compliance data
                    - Assign a fraud risk score from 0 to 100
                    - Generate human-readable reasoning behind the score
                    
                    Consider these risk factors:
                    - High-risk countries: ["NG", "IR", "RU", "KP"]
                    - High amount threshold: $10,000 USD
                    - Suspicious account age: < 30 days
                    - Low device trust threshold: < 0.5
                    
                    Output should include:
                    - risk_score: integer (0-100)
                    - risk_level: [Low, Medium, High]
                    - reason: brief explainable summary with regulatory considerations""",
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
    """Compliance Report Executor that generates audit reports from risk analysis results."""
    
    try:
        # Configuration
        project_endpoint = os.environ.get("AI_FOUNDRY_PROJECT_ENDPOINT")
        model_deployment_name = os.environ.get("MODEL_DEPLOYMENT_NAME", "gpt-4o-mini")
        
        # Generate audit report using local functions
        audit_report = generate_audit_report_from_risk_analysis(
            risk_analysis_text=risk_response.risk_analysis,
            report_type="TRANSACTION_AUDIT"
        )
        
        if "error" in audit_report:
            error_result = ComplianceAuditResponse(
                audit_report_id="ERROR_REPORT",
                audit_conclusion=f"Error generating audit report: {audit_report['error']}",
                compliance_rating="ERROR",
                transaction_id=risk_response.transaction_id,
                status="ERROR"
            )
            await ctx.yield_output(error_result.to_readable_text())
            return
        
        # Convert audit report to response model
        audit_response = ComplianceAuditResponse(
            audit_report_id=audit_report["audit_report_id"],
            audit_conclusion=audit_report["executive_summary"]["audit_conclusion"],
            compliance_rating=audit_report["compliance_status"]["compliance_rating"],
            risk_factors_identified=audit_report["detailed_findings"]["risk_factors_identified"],
            compliance_concerns=audit_report["detailed_findings"]["compliance_concerns"],
            recommendations=audit_report["detailed_findings"]["recommendations"],
            requires_immediate_action=audit_report["compliance_status"]["requires_immediate_action"],
            requires_regulatory_filing=audit_report["compliance_status"]["requires_regulatory_filing"],
            transaction_id=risk_response.transaction_id,
            status="SUCCESS"
        )
        
        # Return formatted text for DevUI display
        formatted_result = audit_response.to_readable_text()
        await ctx.yield_output(formatted_result)
        
    except Exception as e:
        error_result = ComplianceAuditResponse(
            audit_report_id="ERROR_REPORT",
            audit_conclusion=f"Error in compliance reporting: {str(e)}",
            compliance_rating="ERROR",
            transaction_id=risk_response.transaction_id if risk_response else "Unknown",
            status="ERROR"
        )
        await ctx.yield_output(error_result.to_readable_text())

# Build workflow with three executors
workflow = (
    WorkflowBuilder(
        name="Fraud Detection Workflow",
        description="3-step fraud detection workflow: Customer Data → Risk Analysis → Compliance Report"
    )
    .set_start_executor(customer_data_executor)
    .add_edge(customer_data_executor, risk_analyzer_executor)
    .add_edge(risk_analyzer_executor, compliance_report_executor)
    .build()
)


def main():
    """Launch the fraud detection workflow in DevUI."""
    import logging
    from agent_framework.devui import serve

    # Setup logging
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    logger = logging.getLogger(__name__)

    logger.info("Starting Fraud Detection Workflow")
    logger.info("Available at: http://localhost:8093")
    logger.info("Entity ID: workflow_fraud_detection")

    # Launch server with the workflow
    serve(entities=[workflow], port=8093, auto_open=True)


if __name__ == "__main__":
    main()