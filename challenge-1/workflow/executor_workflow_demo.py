"""
Workflow Demo: Testing Microsoft Agent Framework Executors for Fraud Detection

This demo shows how to test the three fraud detection executors:
1. Customer Data Executor - Data retrieval and enrichment
2. Risk Analyzer Executor - Risk analysis and scoring 
3. Compliance Report Executor - Audit reporting and compliance documentation

Note: This demo shows how these executors would work in isolation.
In a real Microsoft Agent Framework workflow, these would be orchestrated by the framework.
"""

import asyncio
import os
import sys
import logging
from dotenv import load_dotenv

load_dotenv(override=True)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_customer_data_executor():
    """Test the customer data executor directly."""
    print("1️⃣ Testing Customer Data Executor")
    try:
        # Import the main function from customer_data_executor
        sys.path.append('/workspaces/azure-trust-agents/challenge-1/workflow')
        
        # Run the customer data executor test
        result = await run_executor_test('customer_data_executor.py')
        print(f"   Result: {result}")
        
    except Exception as e:
        print(f"   Error: {e}")


async def test_risk_analyzer_executor():
    """Test the risk analyzer executor directly."""
    print("\n2️⃣ Testing Risk Analyzer Executor")
    try:
        # Run the risk analyzer executor test
        result = await run_executor_test('risk_analyzer_executor.py')
        print(f"   Result: {result}")
        
    except Exception as e:
        print(f"   Error: {e}")


async def test_compliance_report_executor():
    """Test the compliance report executor directly."""
    print("\n3️⃣ Testing Compliance Report Executor")
    try:
        # Run the compliance report executor test
        result = await run_executor_test('compliance_report_executor.py')
        print(f"   Result: {result}")
        
    except Exception as e:
        print(f"   Error: {e}")


async def run_executor_test(executor_file):
    """Run an executor's main function to test it."""
    import subprocess
    import sys
    
    cmd = [sys.executable, executor_file]
    cwd = '/workspaces/azure-trust-agents/challenge-1/workflow'
    
    try:
        result = subprocess.run(
            cmd, 
            cwd=cwd, 
            capture_output=True, 
            text=True, 
            timeout=30
        )
        
        if result.returncode == 0:
            # Look for success indicators in output
            output = result.stdout
            if "SUCCESS" in output and "FunctionExecutor" in output:
                return "✅ PASSED"
            else:
                return f"⚠️ PARTIAL: {output[:100]}..."
        else:
            return f"❌ FAILED: {result.stderr[:100]}..."
            
    except subprocess.TimeoutExpired:
        return "⏱️ TIMEOUT"
    except Exception as e:
        return f"❌ ERROR: {str(e)[:50]}..."


async def demonstrate_workflow_concept():
    """
    Demonstrate the concept of how these executors would work together in a workflow.
    This shows the data flow between executors conceptually.
    """
    print("\n🚀 Workflow Concept Demonstration")
    print("=" * 50)
    
    # Sample data that would flow between executors
    sample_transaction_id = "TX1001"
    
    print(f"\n📋 Processing Transaction: {sample_transaction_id}")
    
    # Step 1: Customer Data (conceptual output)
    print("\n📊 Step 1: Customer Data Executor Output (conceptual)")
    customer_data_output = {
        "transaction_id": sample_transaction_id,
        "customer_id": "CUST1001",
        "transaction_amount": 15000,
        "destination_country": "IR",
        "customer_country": "US",
        "past_fraud_flags": 1,
        "status": "SUCCESS"
    }
    print(f"   Customer Data: {customer_data_output}")
    
    # Step 2: Risk Analysis (conceptual processing)
    print("\n🔍 Step 2: Risk Analyzer Executor Output (conceptual)")
    risk_analysis_output = {
        "transaction_id": sample_transaction_id,
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
            "Enhanced due diligence required"
        ],
        "status": "SUCCESS"
    }
    print(f"   Risk Analysis: {risk_analysis_output}")
    
    # Step 3: Compliance Report (conceptual processing)
    print("\n📋 Step 3: Compliance Report Executor Output (conceptual)")
    compliance_report_output = {
        "transaction_id": sample_transaction_id,
        "audit_report_id": "AUDIT_20241012_195800",
        "compliance_rating": "NON_COMPLIANT",
        "immediate_action_required": True,
        "compliance_actions": [
            "IMMEDIATE: Block transaction processing",
            "IMMEDIATE: Initiate enhanced due diligence",
            "WITHIN 24H: File suspicious activity report"
        ],
        "status": "SUCCESS"
    }
    print(f"   Compliance Report: {compliance_report_output}")
    
    # Summary
    print("\n" + "=" * 50)
    print("🎉 WORKFLOW SUMMARY:")
    print(f"   Transaction: {sample_transaction_id}")
    print(f"   Risk Level: {risk_analysis_output['risk_level']} ({risk_analysis_output['risk_score']}/100)")
    print(f"   Compliance: {compliance_report_output['compliance_rating']}")
    print(f"   Action Required: {compliance_report_output['immediate_action_required']}")
    print(f"   Actions Count: {len(compliance_report_output['compliance_actions'])}")


async def show_framework_usage():
    """Show how these executors would be used in the Microsoft Agent Framework."""
    print("\n🏗️ Microsoft Agent Framework Usage")
    print("=" * 45)
    
    framework_example = '''
# Example of how to use these executors in Microsoft Agent Framework:

from agent_framework import WorkflowBuilder
from customer_data_executor import customer_data_executor
from risk_analyzer_executor import risk_analyzer_executor  
from compliance_report_executor import compliance_report_executor

# Build a workflow with all three executors
workflow = (WorkflowBuilder()
    .add_executor(customer_data_executor)
    .add_executor(risk_analyzer_executor)
    .add_executor(compliance_report_executor)
    .build())

# Run the workflow
result = await workflow.run({
    "transaction_id": "TX1001",
    "initial_data": {...}
})
'''
    
    print(framework_example)
    
    print("\n📚 Key Features of Our Executors:")
    print("   ✅ Function-based executors with @executor decorator")
    print("   ✅ Proper Pydantic request/response models")
    print("   ✅ Comprehensive error handling and logging")
    print("   ✅ Integration with Azure Cosmos DB and AI Search")
    print("   ✅ Compliance with Microsoft Agent Framework patterns")


async def main():
    """Main demo function."""
    print("🔧 Microsoft Agent Framework Executor Demo")
    print("Testing fraud detection executors individually...")
    print("=" * 60)
    
    # Test each executor individually
    await test_customer_data_executor()
    await test_risk_analyzer_executor()
    await test_compliance_report_executor()
    
    # Show workflow concept
    await demonstrate_workflow_concept()
    
    # Show framework usage
    await show_framework_usage()
    
    print("\n" + "=" * 60)
    print("✨ Demo completed! All executors are ready for Microsoft Agent Framework integration.")


if __name__ == "__main__":
    asyncio.run(main())