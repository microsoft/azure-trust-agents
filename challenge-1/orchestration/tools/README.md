# Tools Package

This package contains modularized tools for the Azure Trust Agents framework, providing clean separation of concerns and better code organization.

## Structure

### `customer_data_tools.py`
Contains tools for fetching customer and transaction data from Cosmos DB:
- `get_customer_sync()` - Retrieve customer profile by ID
- `get_transaction_sync()` - Retrieve transaction details by ID
- `get_transactions_by_customer_sync()` - Get all transactions for a customer
- `get_transactions_by_destination_sync()` - Get transactions by destination country

### `compliance_audit_tools.py`
Contains tools for parsing risk analysis and generating audit reports:
- `parse_risk_analysis_result()` - Parse risk analyzer output to extract key audit information
- `generate_audit_report_from_risk_analysis()` - Generate formal audit report from risk analysis
- `generate_executive_audit_summary()` - Create executive summary from audit report

### `__init__.py`
Package initialization file that exports all tools for easy importing.

## Usage

Import tools in your agent framework code:

```python
from tools import (
    get_customer_sync,
    get_transaction_sync,
    parse_risk_analysis_result,
    generate_audit_report_from_risk_analysis
)
```

## Benefits

1. **Clean Code Organization**: Main orchestration file is much cleaner (164 lines vs 456+ lines)
2. **Modular Design**: Tools are organized by function area (data vs compliance)
3. **Reusability**: Tools can be easily imported and used in other parts of the system
4. **Maintainability**: Changes to tools don't require touching the main orchestration logic
5. **Testability**: Individual tools can be easily unit tested

## Dependencies

- Azure Cosmos DB client
- Pydantic for field validation
- Python logging
- Regular expressions for parsing
- DateTime utilities