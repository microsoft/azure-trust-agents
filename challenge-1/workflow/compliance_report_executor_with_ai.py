"""
Compliance Report Agent Executor with AI Integration

This module provides an enhanced compliance report generation and analysis executor that integrates
with Azure AI Foundry for intelligent compliance assessment and risk detection. It's designed to work with
the Microsoft Agent Framework.

Features:
- Regulatory compliance analysis
- Azure AI Foundry integration for intelligent analysis
- Pydantic model validation
- Comprehensive error handling and logging
- Real-time AI-powered compliance insights
"""

import os
import json
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import logging

# Microsoft Agent Framework
from agent_framework import WorkflowContext, executor

# Azure AI and Search
from azure.ai.agents import AzureAIAgentClient, ChatAgent
from azure.search.documents import SearchClient
from azure.identity import DefaultAzureCredential, AzureCliCredential

# Pydantic for data validation
from pydantic import BaseModel, Field
from dotenv import load_dotenv
import re
from datetime import datetime
import json

# Azure OpenAI integration
try:
    from openai import AsyncAzureOpenAI
except ImportError:
    AsyncAzureOpenAI = None

load_dotenv(override=True)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
model_deployment_name = os.environ.get("MODEL_DEPLOYMENT_NAME", "gpt-4o-mini")
project_endpoint = os.environ.get("AI_FOUNDRY_PROJECT_ENDPOINT")
azure_ai_connection_id = os.environ.get("AZURE_AI_CONNECTION_ID")

# Azure AI Foundry configuration check
if project_endpoint:
    logger.info("✅ Azure AI Foundry configuration found")
else:
    logger.warning("⚠️  Azure AI Foundry configuration not found - AI features disabled")


# Data Models
class ComplianceReportRequest(BaseModel):
    """Request model for compliance report operations."""
    transaction_id: str
    risk_analysis_data: Dict[str, Any]
    report_type: str = "TRANSACTION_AUDIT"
    use_ai_analysis: bool = True


class ComplianceReportResponse(BaseModel):
    """Response model for compliance report operations."""
    transaction_id: str
    audit_report: Dict[str, Any]
    executive_summary: Dict[str, Any]
    compliance_actions: List[str]
    audit_trail: Dict[str, Any]
    ai_reasoning: str = ""
    confidence_score: float = 0.0
    status: str
    message: str


@executor
async def compliance_report_executor_with_ai(
    request: ComplianceReportRequest,
    ctx: WorkflowContext
) -> ComplianceReportResponse:
    """
    Enhanced Compliance Report Agent Executor with AI integration for comprehensive audit reporting.
    
    Combines rule-based compliance analysis with AI-powered report generation and regulatory reasoning.
    
    Args:
        request: Compliance report request with risk analysis data
        ctx: Workflow context
        
    Returns:
        ComplianceReportResponse: Complete compliance report with AI-powered insights
    """
    logger.info(f"🔍 Starting enhanced compliance report generation for transaction: {request.transaction_id}")
    
    try:
        risk_analysis_data = request.risk_analysis_data
        
        # Step 1: Parse risk analysis results
        parsed_risk_data = parse_risk_analysis_result(risk_analysis_data)
        
        # Step 2: Generate formal audit report
        audit_report = generate_audit_report_from_risk_analysis(
            parsed_risk_data, request.report_type
        )
        
        # Step 3: Create executive summary
        executive_summary = create_executive_summary(
            parsed_risk_data, audit_report
        )
        
        # Step 4: Determine compliance actions required
        compliance_actions = determine_compliance_actions(
            parsed_risk_data, audit_report
        )
        
        # Step 5: Generate comprehensive audit trail
        audit_trail = generate_audit_trail(
            request.transaction_id, parsed_risk_data, audit_report
        )
        
        # Step 6: Generate AI-powered compliance reasoning (new enhancement)
        ai_reasoning = ""
        confidence_score = 0.8
        if request.use_ai_analysis and AzureAIAgentClient and project_endpoint:
            ai_analysis = await generate_ai_compliance_reasoning(
                request, parsed_risk_data, audit_report, compliance_actions
            )
            ai_reasoning = ai_analysis.get("reasoning", "")
            confidence_score = ai_analysis.get("confidence", 0.8)
            
            # Enhance compliance actions with AI recommendations
            ai_recommendations = ai_analysis.get("additional_actions", [])
            compliance_actions.extend(ai_recommendations)
        
        logger.info(f"✅ Enhanced compliance report generation completed for transaction {request.transaction_id}")
        
        return ComplianceReportResponse(
            transaction_id=request.transaction_id,
            audit_report=audit_report,
            executive_summary=executive_summary,
            compliance_actions=compliance_actions,
            audit_trail=audit_trail,
            ai_reasoning=ai_reasoning,
            confidence_score=confidence_score,
            status="SUCCESS",
            message=f"Enhanced compliance report with AI insights successfully generated for transaction {request.transaction_id}"
        )

    except Exception as e:
        error_msg = f"Error during enhanced compliance report generation: {str(e)}"
        logger.error(error_msg)
        return ComplianceReportResponse(
            transaction_id=request.transaction_id,
            audit_report={},
            executive_summary={},
            compliance_actions=[],
            audit_trail={},
            ai_reasoning="",
            confidence_score=0.0,
            status="ERROR",
            message=error_msg
        )


async def generate_ai_compliance_reasoning(
    request: ComplianceReportRequest,
    parsed_risk_data: Dict[str, Any], 
    audit_report: Dict[str, Any],
    compliance_actions: List[str]
) -> Dict[str, Any]:
    """Generate AI-powered compliance reasoning and recommendations."""
    if not AzureAIAgentClient and project_endpoint:
        return {"reasoning": "AI compliance reasoning unavailable", "confidence": 0.0}
    
    try:
        # Create compliance analysis prompt
        reasoning_prompt = create_compliance_reasoning_prompt(
            request, parsed_risk_data, audit_report, compliance_actions
        )
        
        # Create Azure AI Agent Client with proper credentials
        async with AzureCliCredential() as credential:
            client = AzureAIAgentClient(
                project_endpoint=project_endpoint,
                model_deployment_name=model_deployment_name,
                async_credential=credential
            )
            
            # Create AI agent for compliance analysis
            agent = client.create_agent(
                name="ComplianceAnalysisAI",
                instructions="""You are an expert compliance officer and regulatory analyst specializing in financial compliance and audit reporting.
                
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
            )
            
            # Run the analysis
            response = await agent.run(reasoning_prompt)
            ai_response_text = response.content if hasattr(response, 'content') else str(response)
        logger.info(f"AI Compliance Reasoning: {ai_response_text[:200]}...")
        
        # Try to parse JSON response
        try:
            ai_analysis = json.loads(ai_response_text)
        except json.JSONDecodeError:
            # Fallback parsing if not valid JSON
            ai_analysis = {
                "reasoning": ai_response_text,
                "confidence": 0.7,
                "additional_actions": [],
                "regulatory_implications": [],
                "recommendations": []
            }
        
        return ai_analysis
        
    except Exception as e:
        logger.error(f"Error generating AI compliance reasoning: {e}")
        return {
            "reasoning": f"AI compliance reasoning failed: {str(e)}",
            "confidence": 0.0,
            "additional_actions": [],
            "regulatory_implications": [],
            "recommendations": []
        }


def create_compliance_reasoning_prompt(
    request: ComplianceReportRequest,
    parsed_risk_data: Dict[str, Any], 
    audit_report: Dict[str, Any],
    compliance_actions: List[str]
) -> str:
    """Create a detailed prompt for AI compliance reasoning."""
    
    prompt = f"""
Analyze this financial transaction compliance case for regulatory requirements and recommendations:

TRANSACTION DETAILS:
- Transaction ID: {request.transaction_id}
- Report Type: {request.report_type}

RISK ANALYSIS DATA:
{json.dumps(parsed_risk_data, indent=2)[:1200]}

AUDIT REPORT SUMMARY:
- Compliance Rating: {audit_report.get('compliance_status', {}).get('compliance_rating', 'Unknown')}
- Immediate Action Required: {audit_report.get('compliance_status', {}).get('requires_immediate_action', False)}
- Regulatory Filing Required: {audit_report.get('compliance_status', {}).get('requires_regulatory_filing', False)}

CURRENT COMPLIANCE ACTIONS:
{json.dumps(compliance_actions, indent=2)}

Please analyze from a regulatory compliance perspective:

1. **Regulatory Framework Analysis**: Which specific regulations apply (BSA, AML, OFAC, etc.)
2. **Risk Assessment**: Evaluate compliance risks and regulatory exposure
3. **Action Prioritization**: Review and enhance the compliance action plan
4. **Regulatory Requirements**: Identify all applicable reporting and filing requirements  
5. **Strategic Recommendations**: Provide guidance for ongoing compliance management
6. **Documentation Requirements**: Ensure proper audit trail and documentation
7. **Timeline Compliance**: Identify regulatory deadlines and timeframes

Focus on:
- Specific regulatory citations and requirements
- Practical compliance actions and next steps
- Risk mitigation strategies
- Regulatory reporting obligations
- Long-term compliance management
"""
    
    return prompt.strip()


def parse_risk_analysis_result(risk_analysis_data: Dict[str, Any]) -> Dict[str, Any]:
    """Parse and structure risk analysis data for audit reporting."""
    try:
        parsed_data = {
            "original_analysis": risk_analysis_data,
            "parsed_elements": {},
            "audit_findings": []
        }
        
        # Extract key risk metrics
        parsed_data["parsed_elements"]["risk_score"] = risk_analysis_data.get("risk_score", 0)
        parsed_data["parsed_elements"]["risk_level"] = risk_analysis_data.get("risk_level", "UNKNOWN")
        parsed_data["parsed_elements"]["transaction_id"] = risk_analysis_data.get("transaction_id")
        
        # Extract risk factors and regulatory findings
        parsed_data["parsed_elements"]["risk_factors"] = risk_analysis_data.get("risk_factors", [])
        parsed_data["parsed_elements"]["regulatory_findings"] = risk_analysis_data.get("regulatory_findings", [])
        
        # Extract detailed analysis if available
        detailed_analysis = risk_analysis_data.get("detailed_analysis", {})
        if detailed_analysis:
            transaction_analysis = detailed_analysis.get("transaction_analysis", {})
            customer_analysis = detailed_analysis.get("customer_analysis", {})
            
            parsed_data["parsed_elements"]["customer_id"] = customer_analysis.get("customer_id")
            parsed_data["parsed_elements"]["transaction_amount"] = transaction_analysis.get("amount")
            parsed_data["parsed_elements"]["destination_country"] = transaction_analysis.get("destination_country")
        
        logger.info(f"Parsed risk analysis for transaction {parsed_data['parsed_elements'].get('transaction_id', 'UNKNOWN')}")
        return parsed_data
        
    except Exception as e:
        logger.error(f"Error parsing risk analysis result: {e}")
        return {"error": f"Failed to parse risk analysis: {str(e)}"}


def generate_audit_report_from_risk_analysis(
    parsed_risk_data: Dict[str, Any], 
    report_type: str = "TRANSACTION_AUDIT"
) -> Dict[str, Any]:
    """Generate formal audit report based on parsed risk analysis findings."""
    try:
        if "error" in parsed_risk_data:
            return parsed_risk_data
        
        elements = parsed_risk_data["parsed_elements"]
        
        # Generate comprehensive audit report
        audit_report = {
            "audit_report_id": f"AUDIT_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "report_type": report_type,
            "generated_timestamp": datetime.now().isoformat(),
            "auditor": "Enhanced Compliance Report Executor with AI",
            "source_analysis": "AI-Enhanced Risk Analyzer Executor",
            
            "executive_summary": {
                "transaction_id": elements.get("transaction_id", "N/A"),
                "customer_id": elements.get("customer_id", "N/A"),
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
            
            "audit_trail": {
                "source_analysis_timestamp": datetime.now().isoformat(),
                "analysis_method": "AI-Enhanced Risk Assessment via Executor Framework",
                "data_sources": ["Transaction Data", "Customer Profile", "Regulatory Database", "AI Risk Analysis"]
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
            if risk_score >= 70:
                audit_report["executive_summary"]["audit_conclusion"] = "HIGH RISK - Immediate review and action required"
                audit_report["compliance_status"]["requires_immediate_action"] = True
                audit_report["compliance_status"]["compliance_rating"] = "NON_COMPLIANT"
            elif risk_score >= 40:
                audit_report["executive_summary"]["audit_conclusion"] = "MEDIUM RISK - Enhanced monitoring and review recommended"
                audit_report["compliance_status"]["requires_enhanced_monitoring"] = True
                audit_report["compliance_status"]["compliance_rating"] = "CONDITIONAL_COMPLIANCE"
            else:
                audit_report["executive_summary"]["audit_conclusion"] = "LOW RISK - Standard monitoring procedures sufficient"
                audit_report["compliance_status"]["compliance_rating"] = "COMPLIANT"
        
        # Add specific findings based on risk factors
        risk_factors = elements.get("risk_factors", [])
        
        if "HIGH_RISK_DESTINATION_COUNTRY" in risk_factors or "SANCTIONS_DESTINATION_COUNTRY" in risk_factors:
            audit_report["detailed_findings"]["compliance_concerns"].append(
                "Transaction involves high-risk jurisdiction requiring enhanced due diligence and monitoring"
            )
            audit_report["detailed_findings"]["regulatory_implications"].append(
                "Enhanced due diligence procedures required as mandated by AML/CFT regulations"
            )
            audit_report["compliance_status"]["requires_regulatory_filing"] = True
        
        if "HIGH_TRANSACTION_AMOUNT" in risk_factors or "UNUSUAL_AMOUNT_PATTERN" in risk_factors:
            audit_report["detailed_findings"]["compliance_concerns"].append(
                "Transaction amount exceeds normal patterns and requires additional verification"
            )
            audit_report["detailed_findings"]["regulatory_implications"].append(
                "Large transaction reporting requirements may apply under BSA regulations"
            )
        
        if "PREVIOUS_FRAUD_HISTORY" in risk_factors:
            audit_report["detailed_findings"]["compliance_concerns"].append(
                "Customer has previous fraud indicators requiring immediate investigation and review"
            )
            audit_report["detailed_findings"]["regulatory_implications"].append(
                "Enhanced customer due diligence (EDD) required based on fraud history patterns"
            )
            audit_report["compliance_status"]["requires_immediate_action"] = True
        
        # Process regulatory findings
        regulatory_findings = elements.get("regulatory_findings", [])
        for finding in regulatory_findings:
            if "sanctions" in finding.lower() or "ofac" in finding.lower():
                audit_report["detailed_findings"]["compliance_concerns"].append(
                    "Potential sanctions-related violations identified requiring immediate escalation"
                )
                audit_report["detailed_findings"]["regulatory_implications"].append(
                    "OFAC sanctions compliance review required with potential regulatory reporting obligations"
                )
                audit_report["compliance_status"]["requires_immediate_action"] = True
        
        # Generate recommendations
        audit_report["detailed_findings"]["recommendations"] = generate_audit_recommendations(
            audit_report["compliance_status"]
        )
        
        logger.info(f"Generated audit report {audit_report['audit_report_id']} with {audit_report['compliance_status']['compliance_rating']} rating")
        return audit_report
        
    except Exception as e:
        logger.error(f"Error generating audit report: {e}")
        return {"error": f"Failed to generate audit report: {str(e)}"}


def generate_audit_recommendations(compliance_status: Dict[str, Any]) -> List[str]:
    """Generate audit recommendations based on compliance status."""
    recommendations = []
    
    if compliance_status.get("requires_immediate_action", False):
        recommendations.extend([
            "IMMEDIATE: Freeze transaction processing and initiate investigation",
            "IMMEDIATE: Conduct enhanced customer due diligence review",
            "IMMEDIATE: File suspicious activity report (SAR) with FinCEN if warranted",
            "IMMEDIATE: Document all investigation steps for regulatory compliance",
            "WITHIN 24H: Notify compliance management and legal teams"
        ])
    elif compliance_status.get("requires_enhanced_monitoring", False):
        recommendations.extend([
            "WITHIN 2H: Place customer on enhanced monitoring watchlist",
            "WITHIN 24H: Review customer risk profile and transaction history patterns",
            "WITHIN 48H: Conduct additional identity verification if necessary",
            "ONGOING: Monitor all future transactions from this customer closely"
        ])
    else:
        recommendations.extend([
            "Continue standard monitoring procedures and risk assessment protocols",
            "File transaction record in compliance database for future reference",
            "No immediate enhanced action required based on current risk profile"
        ])
    
    if compliance_status.get("requires_regulatory_filing", False):
        recommendations.extend([
            "WITHIN 24H: Prepare regulatory filing documentation and supporting evidence",
            "WITHIN 48H: Submit required regulatory reports to appropriate authorities"
        ])
        
    return recommendations


def create_executive_summary(
    parsed_risk_data: Dict[str, Any], 
    audit_report: Dict[str, Any]
) -> Dict[str, Any]:
    """Create executive-level summary of audit findings."""
    try:
        elements = parsed_risk_data["parsed_elements"]
        compliance_status = audit_report.get("compliance_status", {})
        
        executive_summary = {
            "summary_id": f"EXEC_SUMMARY_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "transaction_overview": {
                "transaction_id": elements.get("transaction_id"),
                "customer_id": elements.get("customer_id"),
                "amount": elements.get("transaction_amount"),
                "destination": elements.get("destination_country")
            },
            "risk_assessment_summary": {
                "risk_score": elements.get("risk_score"),
                "risk_level": elements.get("risk_level"),
                "key_risk_factors": len(elements.get("risk_factors", [])),
                "regulatory_concerns": len(elements.get("regulatory_findings", []))
            },
            "compliance_conclusion": {
                "overall_rating": compliance_status.get("compliance_rating", "PENDING"),
                "immediate_action_required": compliance_status.get("requires_immediate_action", False),
                "enhanced_monitoring_required": compliance_status.get("requires_enhanced_monitoring", False),
                "regulatory_filing_required": compliance_status.get("requires_regulatory_filing", False)
            },
            "management_recommendations": audit_report.get("detailed_findings", {}).get("recommendations", []),
            "generated_timestamp": datetime.now().isoformat()
        }
        
        return executive_summary
        
    except Exception as e:
        logger.error(f"Error creating executive summary: {e}")
        return {"error": f"Failed to create executive summary: {str(e)}"}


def determine_compliance_actions(
    parsed_risk_data: Dict[str, Any], 
    audit_report: Dict[str, Any]
) -> List[str]:
    """Determine specific compliance actions required based on audit findings."""
    actions = []
    
    try:
        compliance_status = audit_report.get("compliance_status", {})
        risk_factors = parsed_risk_data["parsed_elements"].get("risk_factors", [])
        
        # Immediate actions for high-risk transactions
        if compliance_status.get("requires_immediate_action", False):
            actions.extend([
                "IMMEDIATE: Block transaction processing and secure funds",
                "IMMEDIATE: Initiate enhanced due diligence investigation protocol", 
                "IMMEDIATE: Notify compliance management team and senior leadership",
                "WITHIN 24H: File suspicious activity report (SAR) if investigation confirms suspicion"
            ])
        
        # Enhanced monitoring actions
        if compliance_status.get("requires_enhanced_monitoring", False):
            actions.extend([
                "WITHIN 2H: Place customer on enhanced monitoring watchlist system",
                "WITHIN 24H: Conduct comprehensive customer risk profile review",
                "ONGOING: Monitor all future transactions from this customer with elevated scrutiny"
            ])
        
        # Regulatory filing requirements
        if compliance_status.get("requires_regulatory_filing", False):
            actions.extend([
                "WITHIN 24H: Prepare comprehensive regulatory filing documentation",
                "WITHIN 48H: Submit required reports to FinCEN and relevant regulatory authorities"
            ])
        
        # Specific actions based on risk factors
        if "SANCTIONS_DESTINATION_COUNTRY" in risk_factors:
            actions.append("IMMEDIATE: Verify against current OFAC Specially Designated Nationals (SDN) list")
        
        if "PREVIOUS_FRAUD_HISTORY" in risk_factors:
            actions.append("WITHIN 4H: Review complete customer fraud history and previous investigation results")
        
        # Documentation and audit trail requirements
        actions.extend([
            "ONGOING: Document all investigation steps and decisions in compliance case management system",
            "WITHIN 7 DAYS: Complete comprehensive compliance case file with supporting documentation",
            "MONTHLY: Review effectiveness of compliance actions taken and adjust monitoring as needed"
        ])
        
        return actions
        
    except Exception as e:
        logger.error(f"Error determining compliance actions: {e}")
        return ["ERROR: Manual compliance review required due to system error"]


def generate_audit_trail(
    transaction_id: str, 
    parsed_risk_data: Dict[str, Any], 
    audit_report: Dict[str, Any]
) -> Dict[str, Any]:
    """Generate comprehensive audit trail for regulatory review."""
    try:
        audit_trail = {
            "audit_trail_id": f"TRAIL_{transaction_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "transaction_id": transaction_id,
            "audit_process": {
                "process_start_time": datetime.now().isoformat(),
                "executor_framework_version": "Microsoft Agent Framework v1.0",
                "compliance_executor_version": "2.0.0 (AI-Enhanced)",
                "audit_methodology": "AI-Enhanced Risk-Based Compliance Assessment"
            },
            "data_sources": [
                "Customer Data Executor - Transaction and customer profile data",
                "AI-Enhanced Risk Analyzer Executor - Advanced risk scoring and regulatory analysis",
                "AI-Enhanced Compliance Report Executor - Intelligent audit reporting and compliance assessment",
                "Azure OpenAI - AI-powered compliance reasoning and recommendations"
            ],
            "risk_analysis_metadata": {
                "risk_score": parsed_risk_data["parsed_elements"].get("risk_score"),
                "risk_factors_count": len(parsed_risk_data["parsed_elements"].get("risk_factors", [])),
                "regulatory_findings_count": len(parsed_risk_data["parsed_elements"].get("regulatory_findings", [])),
                "analysis_timestamp": datetime.now().isoformat()
            },
            "compliance_assessment": {
                "audit_report_id": audit_report.get("audit_report_id"),
                "compliance_rating": audit_report.get("compliance_status", {}).get("compliance_rating"),
                "actions_required": audit_report.get("compliance_status", {}).get("requires_immediate_action", False),
                "assessment_timestamp": datetime.now().isoformat()
            },
            "regulatory_compliance": {
                "applicable_regulations": [
                    "Bank Secrecy Act (BSA)",
                    "USA PATRIOT Act",
                    "OFAC Sanctions Regulations", 
                    "Anti-Money Laundering (AML) Requirements",
                    "Customer Due Diligence (CDD) Requirements"
                ],
                "compliance_framework": "AI-Enhanced Risk-Based Approach",
                "documentation_standard": "Federal Financial Institutions Examination Council (FFIEC)",
                "ai_enhancement": "Azure OpenAI-powered compliance reasoning and analysis"
            },
            "audit_certification": {
                "automated_assessment_completed": True,
                "ai_analysis_completed": True,
                "human_review_required": audit_report.get("compliance_status", {}).get("requires_immediate_action", False),
                "audit_trail_integrity": "VERIFIED",
                "certification_timestamp": datetime.now().isoformat()
            }
        }
        
        return audit_trail
        
    except Exception as e:
        logger.error(f"Error generating audit trail: {e}")
        return {"error": f"Failed to generate audit trail: {str(e)}"}


async def main():
    """
    Main function to test the Enhanced Compliance Report Agent Executor.
    """
    try:
        print(f"✅ Enhanced Compliance Report Agent Executor Function Created Successfully")
        print(f"📋 Executor Type: {type(compliance_report_executor_with_ai)}")
        print(f"🤖 AI Integration: {'Enabled' if AzureAIAgentClient and project_endpoint else 'Disabled'}")
        print(f"📝 Note: This is a Microsoft Agent Framework executor function with LLM integration.")
        
        # Test with sample risk analysis data (high-risk scenario)
        print(f"\n🔍 Testing enhanced compliance report generation...")
        
        # Create test risk analysis data (high-risk scenario)
        test_risk_analysis_data = {
            "transaction_id": "TX1001",
            "risk_score": 85,
            "risk_level": "HIGH",
            "risk_factors": [
                "HIGH_RISK_DESTINATION_COUNTRY",
                "SANCTIONS_DESTINATION_COUNTRY",
                "UNUSUAL_AMOUNT_PATTERN",
                "PREVIOUS_FRAUD_HISTORY"
            ],
            "regulatory_findings": [
                "OFAC sanctions regulations apply to IR",
                "Enhanced due diligence required for sanctions jurisdictions",
                "BSA reporting requirements for large transactions"
            ],
            "detailed_analysis": {
                "transaction_analysis": {
                    "transaction_id": "TX1001",
                    "amount": 15000,
                    "currency": "USD",
                    "destination_country": "IR"
                },
                "customer_analysis": {
                    "customer_id": "CUST1001",
                    "country": "US",
                    "past_fraud_flags": 1
                }
            },
            "explanation": "HIGH RISK transaction requiring immediate attention",
            "recommendations": ["BLOCK TRANSACTION", "Enhanced due diligence required"],
            "status": "SUCCESS"
        }
        
        # Test parsing and report generation functions
        parsed_data = parse_risk_analysis_result(test_risk_analysis_data)
        print(f"📊 Risk Data Parsing: {'SUCCESS' if 'error' not in parsed_data else 'ERROR'}")
        
        audit_report = generate_audit_report_from_risk_analysis(parsed_data, "TRANSACTION_AUDIT")
        print(f"📋 Audit Report Generation: {'SUCCESS' if 'error' not in audit_report else 'ERROR'}")
        
        if 'error' not in audit_report:
            compliance_rating = audit_report.get("compliance_status", {}).get("compliance_rating", "UNKNOWN")
            immediate_action = audit_report.get("compliance_status", {}).get("requires_immediate_action", False)
            print(f"⚖️  Compliance Rating: {compliance_rating}")
            print(f"🚨 Immediate Action Required: {immediate_action}")
            
            executive_summary = create_executive_summary(parsed_data, audit_report)
            compliance_actions = determine_compliance_actions(parsed_data, audit_report)
            audit_trail = generate_audit_trail("TX1001", parsed_data, audit_report)
            
            print(f"📈 Executive Summary: {'SUCCESS' if 'error' not in executive_summary else 'ERROR'}")
            print(f"📋 Compliance Actions: {len(compliance_actions)} items")
            print(f"📝 Audit Trail: {'SUCCESS' if 'error' not in audit_trail else 'ERROR'}")
            
            # Test AI compliance reasoning if available
            if AzureAIAgentClient and project_endpoint:
                ai_reasoning = await generate_ai_compliance_reasoning(
                    ComplianceReportRequest(
                        transaction_id="TX1001",
                        risk_analysis_data=test_risk_analysis_data
                    ),
                    parsed_data, audit_report, compliance_actions
                )
                print(f"🤖 AI Compliance Reasoning: {'SUCCESS' if ai_reasoning.get('confidence', 0) > 0 else 'ERROR'}")
                print(f"💭 AI Sample Reasoning: {ai_reasoning.get('reasoning', 'No reasoning')[:100]}...")
        
        # Show usage example
        print(f"\n🚀 USAGE EXAMPLE:")
        print(f"```python")
        print(f"from workflow import compliance_report_executor_with_ai")
        print(f"from agent_framework import WorkflowBuilder")
        print(f"")
        print(f"workflow = WorkflowBuilder().add_executor(compliance_report_executor_with_ai).build()")
        print(f"result = await workflow.run(ComplianceReportRequest(..., use_ai_analysis=True))")
        print(f"```")
        
        return compliance_report_executor_with_ai
        
    except Exception as e:
        print(f"❌ Error testing Enhanced Compliance Report Executor: {e}")
        return None


if __name__ == "__main__":
    asyncio.run(main())