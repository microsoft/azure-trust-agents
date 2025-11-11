import asyncio
import os
import json
from datetime import datetime, timedelta
from typing import Annotated, List, Dict, Any, Optional
from azure.identity.aio import AzureCliCredential
from agent_framework import ChatAgent
from agent_framework.azure import AzureAIAgentClient
from azure.ai.projects.aio import AIProjectClient
from dotenv import load_dotenv
from pydantic import Field
import logging

load_dotenv(override=True)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
project_endpoint = os.environ.get("AI_FOUNDRY_PROJECT_ENDPOINT")
model_deployment_name = os.environ.get("MODEL_DEPLOYMENT_NAME")

# Note: This agent focuses on audit reporting based on Risk Analyser output
# Creates specific transaction audit reports and prepares for future MCP alert integration

# Audit Report Functions for Risk Analysis Results
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
        import re
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
    multiple_risk_analyses: Annotated[List[str], Field(description="List of risk analysis outputs from multiple transactions")],
    summary_period: Annotated[str, Field(description="Period covered (e.g., 'Daily', 'Weekly', 'Monthly')")] = "Daily"
) -> dict:
    """Generates executive-level audit summary from multiple risk analyses."""
    try:
        summary = {
            "summary_id": f"EXEC_SUMMARY_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "summary_type": f"{summary_period} Executive Audit Summary",
            "generated_timestamp": datetime.now().isoformat(),
            "period_analyzed": summary_period,
            "transactions_reviewed": len(multiple_risk_analyses),
            
            "risk_distribution": {
                "high_risk_count": 0,
                "medium_risk_count": 0, 
                "low_risk_count": 0,
                "unknown_risk_count": 0
            },
            
            "key_findings": [],
            "regulatory_alerts": [],
            "recommendations": [],
            "compliance_dashboard": {
                "overall_compliance_rating": "PENDING",
                "immediate_actions_required": 0,
                "enhanced_monitoring_required": 0,
                "regulatory_filings_required": 0
            }
        }
        
        # Process each risk analysis
        all_risk_factors = []
        for analysis_text in multiple_risk_analyses:
            parsed = parse_risk_analysis_result(analysis_text)
            
            if "error" not in parsed:
                elements = parsed["parsed_elements"]
                
                # Count risk levels
                risk_level = elements.get("risk_level", "UNKNOWN").upper()
                if "HIGH" in risk_level:
                    summary["risk_distribution"]["high_risk_count"] += 1
                elif "MEDIUM" in risk_level:
                    summary["risk_distribution"]["medium_risk_count"] += 1
                elif "LOW" in risk_level:
                    summary["risk_distribution"]["low_risk_count"] += 1
                else:
                    summary["risk_distribution"]["unknown_risk_count"] += 1
                
                # Collect risk factors
                risk_factors = elements.get("risk_factors", [])
                all_risk_factors.extend(risk_factors)
        
        # Analyze patterns across all transactions
        from collections import Counter
        risk_factor_counts = Counter(all_risk_factors)
        
        # Generate key findings
        if risk_factor_counts:
            most_common_risks = risk_factor_counts.most_common(3)
            for risk_factor, count in most_common_risks:
                summary["key_findings"].append(f"{risk_factor}: {count} occurrences across analyzed transactions")
        
        # Generate audit alerts
        high_risk_pct = (summary["risk_distribution"]["high_risk_count"] / len(multiple_risk_analyses)) * 100
        if high_risk_pct > 20:
            summary["regulatory_alerts"].append(
                f"AUDIT ALERT: {high_risk_pct:.1f}% of transactions classified as high-risk requiring management attention"
            )
        
        if "HIGH_RISK_JURISDICTION" in risk_factor_counts:
            summary["regulatory_alerts"].append(
                f"Pattern identified: {risk_factor_counts['HIGH_RISK_JURISDICTION']} transactions to high-risk jurisdictions"
            )
        
        # Set compliance dashboard
        summary["compliance_dashboard"]["immediate_actions_required"] = summary["risk_distribution"]["high_risk_count"]
        summary["compliance_dashboard"]["enhanced_monitoring_required"] = summary["risk_distribution"]["medium_risk_count"]
        summary["compliance_dashboard"]["regulatory_filings_required"] = len([f for f in all_risk_factors if f in ["SANCTIONS_CONCERN", "HIGH_RISK_JURISDICTION"]])
        
        # Overall compliance rating
        if summary["compliance_dashboard"]["immediate_actions_required"] > 0:
            summary["compliance_dashboard"]["overall_compliance_rating"] = "CRITICAL_ATTENTION_REQUIRED"
        elif summary["compliance_dashboard"]["enhanced_monitoring_required"] > 2:
            summary["compliance_dashboard"]["overall_compliance_rating"] = "ENHANCED_MONITORING_REQUIRED"
        else:
            summary["compliance_dashboard"]["overall_compliance_rating"] = "ACCEPTABLE_RISK_LEVEL"
        
        logger.info(f"Generated executive summary: {len(multiple_risk_analyses)} transactions analyzed, {summary['compliance_dashboard']['overall_compliance_rating']} rating")
        return summary
        
    except Exception as e:
        logger.error(f"Error generating executive summary: {e}")
        return {"error": f"Failed to generate executive summary: {str(e)}"}

async def main():
    """Main function to create and test the Compliance Audit Report Agent."""
    
    try:
        async with AzureCliCredential() as credential:
            async with AIProjectClient(
                endpoint=project_endpoint,
                credential=credential
            ) as project_client:
                
                # Create persistent agent
                created_agent = await project_client.agents.create_agent(
                    model=model_deployment_name,
                    name="ComplianceAuditReportAgent",
                    instructions="""You are a Compliance Audit Report Agent specialized in generating formal audit reports based on risk analysis findings from the Risk Analyser Agent.

Your primary responsibilities include:

1. **Risk Analysis Processing**:
   - Parse and interpret outputs from Risk Analyser Agent
   - Extract key risk indicators, scores, and findings
   - Structure risk data for audit reporting

2. **Audit Report Generation**:
   - Generate formal audit reports from risk analysis results
   - Create transaction-specific audit findings
   - Provide compliance ratings and risk assessments

3. **Executive Reporting**:
   - Create executive-level audit summaries
   - Generate compliance dashboards and metrics
   - Provide period-based audit overviews

4. **Audit Documentation**:
   - Provide comprehensive audit trails and documentation
   - Ensure reports meet internal audit standards
   - Structure findings for management review

**Input Sources**:
- Risk Analyser Agent output text
- Fraud detection analysis results
- Transaction risk assessments
- Customer risk profiles

**Available Tools**:
- Risk analysis parsing and structuring
- Audit report generation from risk findings
- Executive summary generation for multiple analyses

**Output Format Guidelines**:
- Generate formal audit reports suitable for internal review
- Include specific compliance ratings and risk levels based on risk analysis findings
- Provide clear recommendations and required actions
- Maintain professional audit documentation standards
- Include proper audit trails and timestamps
- Focus on translating risk findings into actionable audit conclusions

You must ensure all audit reports are comprehensive, accurate, and suitable for internal audit review. Regulatory compliance details are handled by the Risk Analyser Agent."""
                )
                
                # Wrap agent with tools for usage
                agent = ChatAgent(
                    chat_client=AzureAIAgentClient(
                        project_client=project_client,
                        agent_id=created_agent.id
                    ),
                    tools=[
                        parse_risk_analysis_result,
                        generate_audit_report_from_risk_analysis,
                        generate_executive_audit_summary
                    ],
                    store=True
                )

                print(f"✅ Created Compliance Audit Report Agent: {created_agent.id}")

                # Test the agent with a sample risk analysis output
                print(f"\n🔍 Testing Compliance Audit Report Agent...")

                sample_risk_analysis = """Risk Analysis Complete for Transaction TX1001:

Customer: C1001 (John Smith)
Transaction Amount: $15,000 USD
Destination Country: IR (Iran)
Risk Score: 85/100
Risk Level: HIGH

Key Risk Factors:
- Transaction to high-risk jurisdiction (Iran)
- Amount exceeds customer's normal transaction pattern
- Destination country on EU sanctions watchlist
- Customer has previous suspicious activity flags

Fraud Detection Assessment:
The transaction exhibits multiple high-risk characteristics requiring immediate attention. The combination of high-risk destination, unusual amount, and customer history creates significant compliance concerns.

Recommendation: BLOCK TRANSACTION - Enhanced due diligence required before processing."""

                test_prompt = f"""Based on the following Risk Analyser Agent output, please generate a comprehensive audit report:

{sample_risk_analysis}

Please provide:
1. Formal audit report with compliance ratings based on the risk analysis
2. Specific required actions and recommendations derived from the findings
3. Executive summary of key audit conclusions
4. Audit trail documentation

Focus on translating the risk analysis into clear audit findings and actionable recommendations for management review."""

                result = await agent.run(test_prompt)

                print(f"\n📋 COMPLIANCE AUDIT REPORT AGENT RESPONSE:")
                print("="*60)
                print(result.text)

                return agent
    except Exception as e:
        print(f"❌ Error creating Compliance Report Agent: {e}")
        return None

if __name__ == "__main__":
    asyncio.run(main())