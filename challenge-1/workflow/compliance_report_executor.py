"""
Compliance Report Agent Executor for Microsoft Agent Framework.

This executor implements the Compliance Report Agent functionality using the 
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
)
from pydantic import Field, BaseModel
from dotenv import load_dotenv
import re
from datetime import datetime

load_dotenv(override=True)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Data Models
class ComplianceReportRequest(BaseModel):
    """Request model for compliance report operations."""
    transaction_id: str
    risk_analysis_data: Dict[str, Any]
    report_type: str = "TRANSACTION_AUDIT"


class ComplianceReportResponse(BaseModel):
    """Response model for compliance report operations."""
    transaction_id: str
    audit_report: Dict[str, Any]
    executive_summary: Dict[str, Any]
    compliance_actions: List[str]
    audit_trail: Dict[str, Any]
    status: str
    message: str


@executor
async def compliance_report_executor(
    request: ComplianceReportRequest,
    ctx: WorkflowContext
) -> ComplianceReportResponse:
    """
    Compliance Report Agent Executor for generating comprehensive audit reports and compliance documentation.
    
    Args:
        request: Compliance report request with risk analysis data
        ctx: Workflow context
        
    Returns:
        ComplianceReportResponse: Complete compliance report and audit documentation
    """
    logger.info(f"🔍 Starting compliance report generation for transaction: {request.transaction_id}")
    
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
        
        logger.info(f"✅ Compliance report generation completed for transaction {request.transaction_id}")
        
        return ComplianceReportResponse(
            transaction_id=request.transaction_id,
            audit_report=audit_report,
            executive_summary=executive_summary,
            compliance_actions=compliance_actions,
            audit_trail=audit_trail,
            status="SUCCESS",
            message=f"Compliance report successfully generated for transaction {request.transaction_id}"
        )

    except Exception as e:
        error_msg = f"Error during compliance report generation: {str(e)}"
        logger.error(error_msg)
        return ComplianceReportResponse(
            transaction_id=request.transaction_id,
            audit_report={},
            executive_summary={},
            compliance_actions=[],
            audit_trail={},
            status="ERROR",
            message=error_msg
        )


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
            "auditor": "Compliance Report Executor",
            "source_analysis": "Risk Analyzer Executor",
            
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
                "analysis_method": "Automated Risk Assessment via Executor Framework",
                "data_sources": ["Transaction Data", "Customer Profile", "Regulatory Database"]
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
                audit_report["executive_summary"]["audit_conclusion"] = "HIGH RISK - Immediate review required"
                audit_report["compliance_status"]["requires_immediate_action"] = True
                audit_report["compliance_status"]["compliance_rating"] = "NON_COMPLIANT"
            elif risk_score >= 40:
                audit_report["executive_summary"]["audit_conclusion"] = "MEDIUM RISK - Enhanced monitoring recommended"
                audit_report["compliance_status"]["requires_enhanced_monitoring"] = True
                audit_report["compliance_status"]["compliance_rating"] = "CONDITIONAL_COMPLIANCE"
            else:
                audit_report["executive_summary"]["audit_conclusion"] = "LOW RISK - Standard monitoring sufficient"
                audit_report["compliance_status"]["compliance_rating"] = "COMPLIANT"
        
        # Add specific findings based on risk factors
        risk_factors = elements.get("risk_factors", [])
        
        if "HIGH_RISK_DESTINATION_COUNTRY" in risk_factors or "SANCTIONS_DESTINATION_COUNTRY" in risk_factors:
            audit_report["detailed_findings"]["compliance_concerns"].append(
                "Transaction involves high-risk jurisdiction requiring enhanced monitoring"
            )
            audit_report["detailed_findings"]["regulatory_implications"].append(
                "Enhanced due diligence procedures required as identified by risk analysis"
            )
            audit_report["compliance_status"]["requires_regulatory_filing"] = True
        
        if "HIGH_TRANSACTION_AMOUNT" in risk_factors or "UNUSUAL_AMOUNT_PATTERN" in risk_factors:
            audit_report["detailed_findings"]["compliance_concerns"].append(
                "Transaction amount exceeds normal patterns for customer profile"
            )
            audit_report["detailed_findings"]["regulatory_implications"].append(
                "Additional transaction verification recommended based on risk assessment"
            )
        
        if "PREVIOUS_FRAUD_HISTORY" in risk_factors:
            audit_report["detailed_findings"]["compliance_concerns"].append(
                "Customer has previous fraud indicators requiring investigation"
            )
            audit_report["detailed_findings"]["regulatory_implications"].append(
                "Enhanced customer due diligence required based on fraud history"
            )
            audit_report["compliance_status"]["requires_immediate_action"] = True
        
        # Process regulatory findings
        regulatory_findings = elements.get("regulatory_findings", [])
        for finding in regulatory_findings:
            if "sanctions" in finding.lower() or "ofac" in finding.lower():
                audit_report["detailed_findings"]["compliance_concerns"].append(
                    "Potential sanctions-related issues identified in risk analysis"
                )
                audit_report["detailed_findings"]["regulatory_implications"].append(
                    "Immediate review required based on sanctions risk indicators"
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
            "Freeze transaction pending investigation",
            "Conduct enhanced customer due diligence",
            "File suspicious activity report with regulators",
            "Document all investigation steps for audit trail"
        ])
    elif compliance_status.get("requires_enhanced_monitoring", False):
        recommendations.extend([
            "Place customer on enhanced monitoring list",
            "Review transaction against internal risk policies",
            "Consider additional identity verification",
            "Monitor future transactions closely"
        ])
    else:
        recommendations.extend([
            "Continue standard monitoring procedures",
            "File transaction record in compliance database",
            "No immediate action required"
        ])
    
    if compliance_status.get("requires_regulatory_filing", False):
        recommendations.append("Prepare regulatory filing documentation")
        
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
                "IMMEDIATE: Block transaction processing",
                "IMMEDIATE: Initiate enhanced due diligence investigation",
                "IMMEDIATE: Notify compliance management team",
                "WITHIN 24H: File suspicious activity report if warranted"
            ])
        
        # Enhanced monitoring actions
        if compliance_status.get("requires_enhanced_monitoring", False):
            actions.extend([
                "WITHIN 2H: Place customer on enhanced monitoring watchlist",
                "WITHIN 24H: Review customer risk profile and transaction history",
                "ONGOING: Monitor all future transactions from this customer"
            ])
        
        # Regulatory filing requirements
        if compliance_status.get("requires_regulatory_filing", False):
            actions.extend([
                "WITHIN 24H: Prepare regulatory filing documentation",
                "WITHIN 48H: Submit required regulatory reports"
            ])
        
        # Specific actions based on risk factors
        if "SANCTIONS_DESTINATION_COUNTRY" in risk_factors:
            actions.append("IMMEDIATE: Verify against current OFAC sanctions lists")
        
        if "PREVIOUS_FRAUD_HISTORY" in risk_factors:
            actions.append("WITHIN 4H: Review customer fraud history and previous investigations")
        
        # Documentation requirements
        actions.extend([
            "ONGOING: Document all investigation steps in audit trail",
            "WITHIN 7 DAYS: Complete compliance case file",
            "MONTHLY: Review effectiveness of compliance actions taken"
        ])
        
        return actions
        
    except Exception as e:
        logger.error(f"Error determining compliance actions: {e}")
        return ["ERROR: Manual review required due to system error"]


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
                "compliance_executor_version": "1.0.0",
                "audit_methodology": "Automated Risk-Based Compliance Assessment"
            },
            "data_sources": [
                "Customer Data Executor - Transaction and customer profile data",
                "Risk Analyzer Executor - Risk scoring and regulatory compliance analysis",
                "Compliance Report Executor - Audit report generation and compliance assessment"
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
                    "Anti-Money Laundering (AML) Requirements"
                ],
                "compliance_framework": "Risk-Based Approach",
                "documentation_standard": "Federal Financial Institutions Examination Council (FFIEC)"
            },
            "audit_certification": {
                "automated_assessment_completed": True,
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
    Main function to test the Compliance Report Agent Executor.
    """
    try:
        print(f"✅ Compliance Report Agent Executor Function Created Successfully")
        print(f"📋 Executor Type: {type(compliance_report_executor)}")
        print(f"📝 Note: This is a Microsoft Agent Framework executor function.")
        
        # Test with sample risk analysis data
        print(f"\n🔍 Testing compliance report generation...")
        
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
        
        # Show usage example
        print(f"\n🚀 USAGE EXAMPLE:")
        print(f"To use this executor in a workflow:")
        print(f"```python")
        print(f"from workflow import compliance_report_executor")
        print(f"from agent_framework import WorkflowBuilder")
        print(f"")
        print(f"workflow = WorkflowBuilder().add_executor(compliance_report_executor).build()")
        print(f"result = await workflow.run(ComplianceReportRequest(...))")
        print(f"```")
        
        return compliance_report_executor
        
    except Exception as e:
        print(f"❌ Error testing Compliance Report Executor: {e}")
        return None


if __name__ == "__main__":
    asyncio.run(main())