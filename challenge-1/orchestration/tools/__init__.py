"""
Tools package for Azure Trust Agents
Provides data access and compliance tools for the agent framework
"""

from .customer_data_tools import (
    get_customer_sync,
    get_transaction_sync,
    get_transactions_by_customer_sync,
    get_transactions_by_destination_sync
)

from .compliance_audit_tools import (
    parse_risk_analysis_result,
    generate_audit_report_from_risk_analysis,
    generate_executive_audit_summary
)

__all__ = [
    # Customer Data Tools
    'get_customer_sync',
    'get_transaction_sync',
    'get_transactions_by_customer_sync',
    'get_transactions_by_destination_sync',
    
    # Compliance Audit Tools
    'parse_risk_analysis_result',
    'generate_audit_report_from_risk_analysis',
    'generate_executive_audit_summary'
]