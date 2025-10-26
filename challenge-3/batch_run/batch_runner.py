#!/usr/bin/env python3
"""
Simple Batch Runner for Fraud Detection with MCP Integration
Quick way to generate multiple transactions for observability and MCP tool testing
"""

import asyncio
import sys
import os

# Add parent directory to path to import workflow_observability
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from multi_transaction_simulator import quick_demo, stress_test, business_day_simulation, run_multiple_transactions

async def main():
    if len(sys.argv) > 1:
        arg = sys.argv[1].lower()
        
        if arg == "quick":
            await quick_demo()
        elif arg == "stress":
            await stress_test()
        elif arg == "business":
            await business_day_simulation()
        elif arg.isdigit():
            num_transactions = int(arg)
            print(f"🚀 Running {num_transactions} transactions...")
            await run_multiple_transactions(num_transactions, delay_between=1)
        else:
            print("Usage: python batch_runner.py [quick|stress|business|<number>]")
            return
    else:
        # Default: run 10 transactions
        print("🚀 Running default simulation (10 transactions)...")
        await run_multiple_transactions(10, delay_between=1)

if __name__ == "__main__":
    asyncio.run(main())