#!/usr/bin/env python3
"""
Multi-Transaction Fraud Detection Simulator
Generates multiple transactions to populate Application Insights with rich observability data
"""

import asyncio
import time
import random
import sys
import os
from datetime import datetime

# Add parent directory to path to import workflow_observability
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from workflow_observability import run_fraud_detection_workflow, AnalysisRequest

# Transaction IDs available in the Cosmos DB
AVAILABLE_TRANSACTIONS = [
    "TX1001", "TX1002", "TX1003", "TX1004", "TX1005", "TX1006", "TX1007", 
    "TX1008", "TX1009", "TX1010", "TX1011", "TX1012", "TX1013", "TX1014",
    "TX2001", "TX2002", "TX2003"
]

async def run_multiple_transactions(num_transactions=10, delay_between=2):
    """
    Run fraud detection workflow for multiple transactions
    
    Args:
        num_transactions: Number of transactions to process
        delay_between: Seconds to wait between transactions
    """
    
    print(f"🚀 Starting fraud detection simulation")
    print(f"📊 Processing {num_transactions} transactions with {delay_between}s delay")
    print(f"⏰ Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    results = []
    
    for i in range(num_transactions):
        # Select a random transaction or cycle through them
        transaction_id = AVAILABLE_TRANSACTIONS[i % len(AVAILABLE_TRANSACTIONS)]
        
        print(f"\n🔍 Processing transaction {i+1}/{num_transactions}: {transaction_id}")
        
        try:
            # Create request for this transaction
            request = AnalysisRequest(
                message=f"Fraud analysis batch processing - Transaction {i+1}",
                transaction_id=transaction_id
            )
            
            # Run the workflow
            start_time = time.time()
            result = await run_fraud_detection_workflow_with_request(request)
            end_time = time.time()
            
            processing_time = end_time - start_time
            
            if result:
                print(f"✅ Completed: {result.audit_report_id}")
                print(f"⏱️  Processing time: {processing_time:.2f}s")
                print(f"📋 Compliance: {result.compliance_rating}")
                print(f"📊 Risk Score: {result.risk_score:.2f}")
                
                # Display MCP information
                if hasattr(result, 'mcp_tool_used') and result.mcp_tool_used:
                    print(f"🔧 MCP Tools Used: {', '.join(result.mcp_actions) if result.mcp_actions else 'Yes'}")
                
                results.append({
                    "transaction_id": transaction_id,
                    "audit_report_id": result.audit_report_id,
                    "compliance_rating": result.compliance_rating,
                    "risk_score": getattr(result, 'risk_score', 0.0),
                    "mcp_tool_used": getattr(result, 'mcp_tool_used', False),
                    "mcp_actions": getattr(result, 'mcp_actions', []),
                    "processing_time": processing_time,
                    "status": "SUCCESS"
                })
            else:
                print("❌ Failed: No result returned")
                results.append({
                    "transaction_id": transaction_id,
                    "status": "FAILED",
                    "processing_time": processing_time
                })
            
            # Wait before next transaction (except for the last one)
            if i < num_transactions - 1:
                print(f"⏸️  Waiting {delay_between}s before next transaction...")
                await asyncio.sleep(delay_between)
                
        except Exception as e:
            print(f"❌ Error processing {transaction_id}: {str(e)}")
            results.append({
                "transaction_id": transaction_id,
                "status": "ERROR",
                "error": str(e)
            })
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 SIMULATION SUMMARY")
    print("=" * 60)
    
    successful = len([r for r in results if r.get("status") == "SUCCESS"])
    failed = len([r for r in results if r.get("status") in ["FAILED", "ERROR"]])
    
    print(f"✅ Successful transactions: {successful}")
    print(f"❌ Failed transactions: {failed}")
    print(f"📈 Success rate: {(successful/len(results)*100):.1f}%")
    
    if successful > 0:
        avg_time = sum([r.get("processing_time", 0) for r in results if r.get("status") == "SUCCESS"]) / successful
        print(f"⏱️  Average processing time: {avg_time:.2f}s")
    
    print(f"⏰ Total simulation time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Compliance breakdown
    compliance_ratings = [r.get("compliance_rating") for r in results if r.get("compliance_rating")]
    if compliance_ratings:
        print("\n📋 Compliance Breakdown:")
        for rating in set(compliance_ratings):
            count = compliance_ratings.count(rating)
            print(f"   {rating}: {count} transactions")
    
    # MCP usage statistics
    mcp_usage = [r.get("mcp_tool_used", False) for r in results if r.get("status") == "SUCCESS"]
    if mcp_usage:
        mcp_used_count = sum(mcp_usage)
        print(f"\n🔧 MCP Tool Usage:")
        print(f"   - MCP tools used: {mcp_used_count}/{len(mcp_usage)} transactions ({(mcp_used_count/len(mcp_usage)*100):.1f}%)")
        
        # MCP action breakdown
        all_actions = []
        for r in results:
            if r.get("mcp_actions"):
                all_actions.extend(r["mcp_actions"])
        
        if all_actions:
            print("   - MCP Actions performed:")
            action_counts = {}
            for action in all_actions:
                action_counts[action] = action_counts.get(action, 0) + 1
            for action, count in action_counts.items():
                print(f"     • {action}: {count} times")
    
    # Risk score analytics
    risk_scores = [r.get("risk_score", 0) for r in results if r.get("status") == "SUCCESS" and r.get("risk_score")]
    if risk_scores:
        avg_risk = sum(risk_scores) / len(risk_scores)
        max_risk = max(risk_scores)
        min_risk = min(risk_scores)
        print(f"\n📊 Risk Score Analytics:")
        print(f"   - Average Risk Score: {avg_risk:.2f}")
        print(f"   - Highest Risk Score: {max_risk:.2f}")
        print(f"   - Lowest Risk Score: {min_risk:.2f}")
    
    print("\n🎯 Application Insights Data:")
    print(f"   - {len(results)} transaction traces generated")
    print(f"   - {successful * 3} business events logged (transaction.started, risk.assessed, compliance.completed)")
    print(f"   - Multiple risk scores and compliance decisions for analysis")
    print(f"   - MCP tool usage metrics and action tracking")
    print(f"   - Performance metrics across {num_transactions} workflows")
    
    print("\n📊 Dashboard Ready!")
    print("   Go to Application Insights → Workbooks → Your Dashboard")
    print("   Data should appear within 2-5 minutes")
    
    return results

async def run_fraud_detection_workflow_with_request(request):
    """Modified version that accepts a specific request"""
    from workflow_observability import (
        initialize_telemetry, get_telemetry_manager, get_current_trace_id,
        flush_telemetry, run_fraud_detection_workflow
    )
    
    # Initialize observability
    initialize_telemetry()
    telemetry = get_telemetry_manager()
    
    # Create main application span
    with telemetry.create_workflow_span("fraud_detection_application") as main_span:
        
        trace_id = get_current_trace_id()
        
        main_span.set_attributes({
            "application.name": "fraud_detection_system",
            "application.version": "1.0.0",
            "trace.id": trace_id or "unknown",
            "batch.processing": True
        })
        
        try:
            # Import and modify the workflow function to accept our request
            from workflow_observability import (
                WorkflowBuilder, customer_data_executor, 
                risk_analyzer_executor, compliance_report_executor,
                WorkflowOutputEvent
            )
            
            # Build workflow
            workflow = (
                WorkflowBuilder()
                .set_start_executor(customer_data_executor)
                .add_edge(customer_data_executor, risk_analyzer_executor)
                .add_edge(risk_analyzer_executor, compliance_report_executor)
                .build()
            )
            
            # Execute workflow with our specific request
            final_output = None
            async for event in workflow.run_stream(request):
                if isinstance(event, WorkflowOutputEvent):
                    final_output = event.data
            
            return final_output
            
        except Exception as e:
            main_span.record_exception(e)
            print(f"❌ Workflow execution failed: {str(e)}")
            return None
        
        finally:
            flush_telemetry()

# Quick simulation presets
async def quick_demo(transactions=5):
    """Quick demo with 5 transactions"""
    print("🚀 Quick Demo - 5 transactions with 1s delay")
    return await run_multiple_transactions(num_transactions=transactions, delay_between=1)

async def stress_test(transactions=20):
    """Stress test with 20 transactions"""
    print("💪 Stress Test - 20 transactions with 0.5s delay")
    return await run_multiple_transactions(num_transactions=transactions, delay_between=0.5)

async def business_day_simulation(transactions=50):
    """Simulate a business day with varied timing"""
    print("🏢 Business Day Simulation - 50 transactions with random delays")
    
    for i in range(transactions):
        transaction_id = AVAILABLE_TRANSACTIONS[i % len(AVAILABLE_TRANSACTIONS)]
        
        # Create request
        request = AnalysisRequest(
            message=f"Business day transaction {i+1}",
            transaction_id=transaction_id
        )
        
        print(f"Processing {i+1}/{transactions}: {transaction_id}")
        
        try:
            result = await run_fraud_detection_workflow_with_request(request)
            if result:
                mcp_indicator = "🔧" if getattr(result, 'mcp_tool_used', False) else "📋"
                print(f"✅ {mcp_indicator} {result.compliance_rating} (Risk: {getattr(result, 'risk_score', 0):.1f})")
            else:
                print("❌ Failed")
        except Exception as e:
            print(f"❌ Error: {e}")
        
        # Random delay between 0.5-3 seconds to simulate realistic timing
        delay = random.uniform(0.5, 3.0)
        await asyncio.sleep(delay)
    
    print("🎉 Business day simulation complete!")

if __name__ == "__main__":
    print("🎯 Fraud Detection Multi-Transaction Simulator")
    print("Choose a simulation mode:")
    print("1. Quick Demo (5 transactions)")
    print("2. Standard Test (10 transactions)")
    print("3. Stress Test (20 transactions)")
    print("4. Business Day (50 transactions with random timing)")
    print("5. Custom")
    
    choice = input("Enter choice (1-5): ").strip()
    
    if choice == "1":
        asyncio.run(quick_demo())
    elif choice == "2":
        asyncio.run(run_multiple_transactions(10, 2))
    elif choice == "3":
        asyncio.run(stress_test())
    elif choice == "4":
        asyncio.run(business_day_simulation())
    elif choice == "5":
        try:
            num = int(input("Number of transactions: "))
            delay = float(input("Delay between transactions (seconds): "))
            asyncio.run(run_multiple_transactions(num, delay))
        except ValueError:
            print("Invalid input. Using defaults: 10 transactions, 2s delay")
            asyncio.run(run_multiple_transactions())
    else:
        print("Invalid choice. Running default simulation...")
        asyncio.run(run_multiple_transactions())