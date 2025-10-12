"""
Compliance Audit Report Agent Tools
Tools for parsing risk analysis and generating audit reports
"""

import re
import logging
from typing import Annotated
from datetime import datetime
from pydantic import Field

# Configure logging
logger = logging.getLogger(__name__)

def parse_risk_analysis_result(
    risk_analysis_text: Annotated[str, Field(description="Output text from Risk Analyser Agent containing fraud analysis")]
) -> dict:
    """Parses risk analyser output to extract key audit information."""
    try:
        # Extract key information from risk analysis text
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
        
        # Extract customer ID
        customer_pattern = r'customer[:\s]*([A-Z0-9]+)'
        customer_match = re.search(customer_pattern, risk_analysis_text)
        if customer_match:
            analysis_data["parsed_elements"]["customer_id"] = customer_match.group(1)
        
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
        
        logger.info(f"Parsed risk analysis for transaction {analysis_data['parsed_elements'].get('transaction_id', 'UNKNOWN')}")
        return analysis_data
        
    except Exception as e:
        logger.error(f"Error parsing risk analysis result: {e}")
        return {"error": f"Failed to parse risk analysis: {str(e)}"}

def generate_audit_report_from_risk_analysis(
    risk_analysis_text: Annotated[str, Field(description="Complete output from Risk Analyser Agent")],
    report_type: Annotated[str, Field(description="Type of audit report (e.g., 'TRANSACTION_AUDIT', 'COMPLIANCE_AUDIT', 'REGULATORY_AUDIT')")] = "TRANSACTION_AUDIT"
) -> dict:
    """Generates a formal audit report based on risk analyser findings."""
    try:
        # Parse the risk analysis
        parsed_analysis = parse_risk_analysis_result(risk_analysis_text)
        
        if "error" in parsed_analysis:
            return parsed_analysis
        
        elements = parsed_analysis["parsed_elements"]
        
        # Generate audit report
        audit_report = {
            "audit_report_id": f"AUDIT_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "report_type": report_type,
            "generated_timestamp": datetime.now().isoformat(),
            "auditor": "Compliance Report Agent",
            "source_analysis": "Risk Analyser Agent",
            
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
                "analysis_method": "Automated Risk Assessment",
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
            audit_report["detailed_findings"]["regulatory_implications"].append(
                "Enhanced due diligence procedures required as identified by risk analysis"
            )
            audit_report["compliance_status"]["requires_regulatory_filing"] = True
        
        if "UNUSUAL_AMOUNT" in risk_factors:
            audit_report["detailed_findings"]["compliance_concerns"].append(
                "Transaction amount exceeds normal patterns for customer profile"
            )
            audit_report["detailed_findings"]["regulatory_implications"].append(
                "Additional transaction verification recommended based on risk assessment"
            )
        
        if "SUSPICIOUS_PATTERN" in risk_factors:
            audit_report["detailed_findings"]["compliance_concerns"].append(
                "Suspicious transaction pattern detected requiring investigation"
            )
            audit_report["detailed_findings"]["regulatory_implications"].append(
                "Pattern analysis indicates potential compliance concerns"
            )
            audit_report["compliance_status"]["requires_immediate_action"] = True
        
        if "SANCTIONS_CONCERN" in risk_factors:
            audit_report["detailed_findings"]["compliance_concerns"].append(
                "Potential sanctions-related issues identified in risk analysis"
            )
            audit_report["detailed_findings"]["regulatory_implications"].append(
                "Immediate review required based on sanctions risk indicators"
            )
            audit_report["compliance_status"]["requires_immediate_action"] = True
        
        # Generate recommendations
        if audit_report["compliance_status"]["requires_immediate_action"]:
            audit_report["detailed_findings"]["recommendations"].extend([
                "Freeze transaction pending investigation",
                "Conduct enhanced customer due diligence",
                "File suspicious activity report with regulators",
                "Document all investigation steps for audit trail"
            ])
        elif audit_report["compliance_status"]["requires_enhanced_monitoring"]:
            audit_report["detailed_findings"]["recommendations"].extend([
                "Place customer on enhanced monitoring list",
                "Review transaction against internal risk policies",
                "Consider additional identity verification",
                "Monitor future transactions closely"
            ])
        else:
            audit_report["detailed_findings"]["recommendations"].extend([
                "Continue standard monitoring procedures",
                "File transaction record in compliance database",
                "No immediate action required"
            ])
        
        logger.info(f"Generated audit report {audit_report['audit_report_id']} with {audit_report['compliance_status']['compliance_rating']} rating")
        return audit_report
        
    except Exception as e:
        logger.error(f"Error generating audit report: {e}")
        return {"error": f"Failed to generate audit report: {str(e)}"}

def generate_executive_audit_summary(
    audit_report: Annotated[dict, Field(description="Complete audit report dictionary from generate_audit_report_from_risk_analysis")]
) -> dict:
    """Generates an executive summary from a full audit report."""
    try:
        if "error" in audit_report:
            return audit_report
        
        executive_summary = {
            "summary_id": f"EXEC_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "report_reference": audit_report.get("audit_report_id", "N/A"),
            "generated_timestamp": datetime.now().isoformat(),
            
            "key_metrics": {
                "transaction_id": audit_report["executive_summary"]["transaction_id"],
                "customer_id": audit_report["executive_summary"]["customer_id"],
                "risk_score": audit_report["executive_summary"]["risk_score"],
                "risk_level": audit_report["executive_summary"]["risk_level"],
                "compliance_rating": audit_report["compliance_status"]["compliance_rating"]
            },
            
            "critical_alerts": {
                "immediate_action_required": audit_report["compliance_status"]["requires_immediate_action"],
                "regulatory_filing_required": audit_report["compliance_status"]["requires_regulatory_filing"],
                "enhanced_monitoring_required": audit_report["compliance_status"]["requires_enhanced_monitoring"]
            },
            
            "executive_decision_points": {
                "primary_recommendation": audit_report["executive_summary"]["audit_conclusion"],
                "key_risk_factors": audit_report["detailed_findings"]["risk_factors_identified"],
                "priority_actions": audit_report["detailed_findings"]["recommendations"][:3]  # Top 3 recommendations
            }
        }
        
        logger.info(f"Generated executive summary {executive_summary['summary_id']} for report {audit_report.get('audit_report_id', 'N/A')}")
        return executive_summary
        
    except Exception as e:
        logger.error(f"Error generating executive summary: {e}")
        return {"error": f"Failed to generate executive summary: {str(e)}"}