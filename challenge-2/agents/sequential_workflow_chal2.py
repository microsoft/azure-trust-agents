import asyncio
import os
import re
from datetime import datetime
from typing_extensions import Never
from agent_framework import WorkflowBuilder, WorkflowContext, WorkflowOutputEvent, executor, ChatAgent
from agent_framework.azure import AzureAIAgentClient
from azure.identity.aio import AzureCliCredential
from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential
from azure.cosmos import CosmosClient
from dotenv import load_dotenv
from pydantic import BaseModel
from azure.ai.agents.models import (
    ListSortOrder,
    McpTool,
    RequiredMcpToolCall,
    RunStepActivityDetails,
    SubmitToolApprovalAction,
    ToolApproval,
)
import time

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
    customer_data: str
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
                transaction_history=transaction_history if isinstance(
                    transaction_history, list) else []
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
            analysis_data["parsed_elements"]["risk_score"] = float(
                score_match.group(1))
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
            analysis_data["parsed_elements"]["risk_level"] = level_match.group(
                1).upper()

        # Extract transaction ID
        tx_pattern = r'transaction[:\s]*([A-Z0-9]+)'
        tx_match = re.search(tx_pattern, risk_analysis_text)
        if tx_match:
            analysis_data["parsed_elements"]["transaction_id"] = tx_match.group(
                1)

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
    ctx: WorkflowContext[RiskAnalysisResponse]
) -> None:
    """Risk Analyzer Executor that processes customer data and sends to parallel executors."""

    try:
        # Configuration
        project_endpoint = os.environ.get("AI_FOUNDRY_PROJECT_ENDPOINT")
        model_deployment_name = os.environ.get(
            "MODEL_DEPLOYMENT_NAME", "gpt-4o-mini")
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
                result_text = result.text if result and hasattr(
                    result, 'text') else "No response from risk agent"

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
                    customer_data=customer_response.customer_data,
                    risk_analysis=result_text,
                    risk_score="Assessed by Risk Agent based on Cosmos DB data",
                    transaction_id=customer_response.transaction_id,
                    status="SUCCESS",
                    risk_factors=risk_factors,
                    recommendation=recommendation,
                    compliance_notes=compliance_notes
                )

                # Send data to both parallel executors (compliance report AND fraud alert)
                await ctx.send_message(final_result)

    except Exception as e:
        error_result = RiskAnalysisResponse(
            customer_data=customer_response.customer_data if customer_response else "No customer data available",
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
        model_deployment_name = os.environ.get(
            "MODEL_DEPLOYMENT_NAME", "gpt-4o-mini")
        COMPLIANCE_REPORT_AGENT_ID = os.getenv("COMPLIANCE_REPORT_AGENT_ID")

        # If no specific compliance agent, we can generate the report locally
        if not COMPLIANCE_REPORT_AGENT_ID:
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
                await ctx.yield_output(error_result)
                return

            # Convert audit report to response model
            final_result = ComplianceAuditResponse(
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

            await ctx.yield_output(final_result)
            return

        # Use Azure AI agent for compliance reporting
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

                # Create compliance report prompt
                compliance_prompt = f"""
Based on the following Risk Analyser Agent output, please generate a comprehensive audit report:

Risk Analysis Result:
{risk_response.risk_analysis}

Transaction ID: {risk_response.transaction_id}
Risk Score: {risk_response.risk_score}
Recommendation: {risk_response.recommendation}
Risk Factors: {risk_response.risk_factors}
Compliance Notes: {risk_response.compliance_notes}

Please provide:
1. Formal audit report with compliance ratings based on the risk analysis
2. Specific required actions and recommendations derived from the findings
3. Executive summary of key audit conclusions
4. Compliance status and regulatory requirements

Focus on translating the risk analysis into clear audit findings and actionable recommendations for management review.
"""

                result = await compliance_agent.run(compliance_prompt)
                result_text = result.text if result and hasattr(
                    result, 'text') else "No response from compliance agent"

                # Generate structured audit report locally and combine with AI response
                local_audit = generate_audit_report_from_risk_analysis(
                    risk_response.risk_analysis)

                if "error" not in local_audit:
                    final_result = ComplianceAuditResponse(
                        audit_report_id=local_audit["audit_report_id"],
                        audit_conclusion=f"{local_audit['executive_summary']['audit_conclusion']} (AI Enhanced: {result_text[:200]}...)",
                        compliance_rating=local_audit["compliance_status"]["compliance_rating"],
                        risk_factors_identified=local_audit["detailed_findings"]["risk_factors_identified"],
                        compliance_concerns=local_audit["detailed_findings"]["compliance_concerns"],
                        recommendations=local_audit["detailed_findings"]["recommendations"],
                        requires_immediate_action=local_audit["compliance_status"]["requires_immediate_action"],
                        requires_regulatory_filing=local_audit["compliance_status"]["requires_regulatory_filing"],
                        transaction_id=risk_response.transaction_id,
                        status="SUCCESS"
                    )
                else:
                    # Fallback if local audit fails
                    final_result = ComplianceAuditResponse(
                        audit_report_id=f"AI_AUDIT_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                        audit_conclusion=result_text[:500] if len(
                            result_text) > 500 else result_text,
                        compliance_rating="AI_GENERATED",
                        transaction_id=risk_response.transaction_id,
                        status="SUCCESS"
                    )

                await ctx.yield_output(final_result)

    except Exception as e:
        error_result = ComplianceAuditResponse(
            audit_report_id="ERROR_REPORT",
            audit_conclusion=f"Error in compliance reporting: {str(e)}",
            compliance_rating="ERROR",
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

    try:

        # Configuration
        project_endpoint = os.environ.get("AI_FOUNDRY_PROJECT_ENDPOINT")
        model_deployment_name = os.environ.get("MODEL_DEPLOYMENT_NAME")
        mcp_endpoint = os.environ.get("MCP_SERVER_ENDPOINT")
        mcp_subscription_key = os.environ.get("APIM_SUBSCRIPTION_KEY")
        FRAUD_ALERT_AGENT_ID = os.getenv("FRAUD_ALERT_AGENT_ID")

        if not FRAUD_ALERT_AGENT_ID:
            raise ValueError("FRAUD_ALERT_AGENT_ID required")

        project_client = AIProjectClient(
            endpoint=project_endpoint,
            credential=DefaultAzureCredential(),
        )

        # Initialize agent MCP tool
        mcp_tool = McpTool(
            server_label="fraudalertmcp",
            server_url=mcp_endpoint,
        )
        mcp_tool.update_headers(
            "Ocp-Apim-Subscription-Key", mcp_subscription_key)

            

        with project_client:
            agents_client = project_client.agents

            agent = agents_client.get_agent(FRAUD_ALERT_AGENT_ID)
            agent.tools.append(mcp_tool)

            # Create thread for communication
            thread = agents_client.threads.create()

            # Create comprehensive message based on risk analysis
            risk_summary = f"""
Customer data: {risk_response.customer_data}

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
            while run.status in ["queued", "in_progress", "requires_action"]:
                time.sleep(1)
                run = agents_client.runs.get(
                    thread_id=thread.id, run_id=run.id)

                if run.status == "requires_action" and isinstance(run.required_action, SubmitToolApprovalAction):
                    tool_calls = run.required_action.submit_tool_approval.tool_calls
                    if not tool_calls:
                        agents_client.runs.cancel(
                            thread_id=thread.id, run_id=run.id)
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
                                print(
                                    f"Error approving tool_call {tool_call.id}: {e}")

                    if tool_approvals:
                        agents_client.runs.submit_tool_outputs(
                            thread_id=thread.id, run_id=run.id, tool_approvals=tool_approvals
                        )

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

                reasoning = agent_response[:200] + \
                    "..." if len(agent_response) > 200 else agent_response

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

            # Clean up agent (optional - comment out to reuse)
            # agents_client.delete_agent(agent.id)

            await ctx.yield_output(final_result)

    except Exception as e:
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
    """Execute the fraud detection workflow using Microsoft Agent Framework with parallel execution."""

    # Build workflow with four executors - parallel execution for compliance and fraud alert
    workflow = (
        WorkflowBuilder()
        .set_start_executor(customer_data_executor)
        .add_edge(customer_data_executor, risk_analyzer_executor)
        # Parallel path 1
        .add_edge(risk_analyzer_executor, compliance_report_executor)
        # Parallel path 2
        .add_edge(risk_analyzer_executor, fraud_alert_executor)
        .build()
    )

    # Create request
    request = AnalysisRequest(
        message="Comprehensive fraud analysis using Microsoft Agent Framework with parallel execution",
        transaction_id="TX1012"  # Russian transaction for testing
    )

    # Execute workflow with streaming
    compliance_output = None
    fraud_alert_output = None

    print("🔄 Executing 4-Executor Fraud Detection Workflow with Parallel Processing...")

    async for event in workflow.run_stream(request):
        # Capture outputs from both parallel executors
        if isinstance(event, WorkflowOutputEvent):
            if isinstance(event.data, ComplianceAuditResponse):
                compliance_output = event.data
            elif isinstance(event.data, FraudAlertResponse):
                fraud_alert_output = event.data

    return compliance_output, fraud_alert_output


async def main():
    """Main function to run the fraud detection workflow."""
    try:
        compliance_result, fraud_alert_result = await run_fraud_detection_workflow()

        print(f"\n🎯 4-EXECUTOR PARALLEL WORKFLOW RESULTS")
        print(f"=" * 60)

        # Display Compliance Report results
        if compliance_result and isinstance(compliance_result, ComplianceAuditResponse):
            print(f"\n📋 COMPLIANCE REPORT EXECUTOR:")
            print(f"   Status: {compliance_result.status}")
            print(f"   Transaction ID: {compliance_result.transaction_id}")
            print(f"   Audit Report ID: {compliance_result.audit_report_id}")
            print(
                f"   Compliance Rating: {compliance_result.compliance_rating}")
            print(f"   Risk Score: {compliance_result.risk_score:.2f}")
            print(
                f"   Conclusion: {compliance_result.audit_conclusion[:100]}...")

            if compliance_result.requires_immediate_action:
                print("   ⚠️  IMMEDIATE ACTION REQUIRED")
            if compliance_result.requires_regulatory_filing:
                print("   📋 REGULATORY FILING REQUIRED")
        else:
            print(f"\n📋 COMPLIANCE REPORT EXECUTOR: ❌ FAILED")

        # Display Fraud Alert results
        if fraud_alert_result and isinstance(fraud_alert_result, FraudAlertResponse):
            print(f"\n🚨 FRAUD ALERT EXECUTOR:")
            print(f"   Status: {fraud_alert_result.status}")
            print(f"   Transaction ID: {fraud_alert_result.transaction_id}")
            print(f"   Alert ID: {fraud_alert_result.alert_id}")
            print(
                f"   Alert Created: {'✅ YES' if fraud_alert_result.alert_created else '❌ NO'}")
            print(f"   Severity: {fraud_alert_result.severity}")
            print(f"   Decision Action: {fraud_alert_result.decision_action}")
            print(f"   Alert Status: {fraud_alert_result.alert_status}")
            print(f"   Assigned To: {fraud_alert_result.assigned_to}")
            print(f"   Reasoning: {fraud_alert_result.reasoning[:100]}...")
            if fraud_alert_result.created_timestamp:
                print(f"   Created At: {fraud_alert_result.created_timestamp}")
        else:
            print(f"\n🚨 FRAUD ALERT EXECUTOR: ❌ FAILED")

        print(f"\n✅ 4-EXECUTOR PARALLEL WORKFLOW COMPLETED")
        print(f"   Architecture: Customer Data → Risk Analyzer → (Compliance Report + Fraud Alert)")

        return compliance_result, fraud_alert_result

    except Exception as e:
        print(f"❌ Workflow execution failed: {str(e)}")
        return None, None

if __name__ == "__main__":
    compliance, fraud_alert = asyncio.run(main())
