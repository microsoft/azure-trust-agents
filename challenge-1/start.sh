#!/bin/bash

# Fraud Detection Orchestration Startup Script

echo "🚀 Fraud Detection Orchestration System"
echo "======================================="

# Check if we're in the right directory
if [ ! -d "orchestration" ]; then
    echo "❌ Error: Must run from challenge-1 directory"
    echo "Expected structure: challenge-1/orchestration/"
    exit 1
fi

# Check for Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Error: Python 3 is required but not installed"
    exit 1
fi

echo "✅ Environment check passed"

# Function to run different modes
run_mode() {
    case $1 in
        "demo")
            echo "🎬 Running orchestration demo..."
            python3 orchestration/demo.py
            ;;
        "api")
            echo "🌐 Starting FastAPI server..."
            echo "API will be available at: http://localhost:8000"
            echo "API docs at: http://localhost:8000/docs"
            cd orchestration && python3 -m uvicorn api:app --host 0.0.0.0 --port 8000 --reload
            ;;
        "cli")
            echo "💻 Starting CLI interface..."
            python3 orchestration/main.py interactive
            ;;
        "maf")
            echo "🤖 Running Microsoft Agent Framework orchestration demo..."
            python3 orchestration/demo_maf.py
            ;;
        "analyze")
            if [ -z "$2" ] || [ -z "$3" ]; then
                echo "❌ Usage: ./start.sh analyze <transaction_id> <customer_id>"
                exit 1
            fi
            echo "🔍 Analyzing transaction $2 for customer $3..."
            python3 orchestration/main.py analyze "$2" "$3"
            ;;
        *)
            echo "Usage: ./start.sh <mode>"
            echo ""
            echo "Available modes:"
            echo "  demo         - Run orchestration demo with sample data"
            echo "  api          - Start FastAPI web server"
            echo "  cli          - Start interactive CLI interface"  
            echo "  maf          - Run Microsoft Agent Framework orchestration demo"
            echo "  analyze <tx> <customer> - Analyze specific transaction"
            echo ""
            echo "Examples:"
            echo "  ./start.sh demo"
            echo "  ./start.sh api"
            echo "  ./start.sh maf"
            echo "  ./start.sh analyze TX1001 CUST1001"
            ;;
    esac
}

# Check if environment is configured
if [ ! -f ".env" ]; then
    echo "⚠️  Warning: .env file not found"
    echo "Create .env file with your Azure credentials:"
    echo ""
    echo "AI_FOUNDRY_PROJECT_ENDPOINT=https://your-project.cognitiveservices.azure.com/"
    echo "MODEL_DEPLOYMENT_NAME=gpt-4o"
    echo "COSMOS_ENDPOINT=https://your-cosmos.documents.azure.com:443/"
    echo "COSMOS_KEY=your-cosmos-key"
    echo "DATA_INGESTION_AGENT_ID=your-data-agent-id"
    echo "TRANSACTION_ANALYST_AGENT_ID=your-analyst-agent-id"
    echo ""
fi

# Install dependencies if needed
if [ ! -d "orchestration/__pycache__" ] && [ "$1" != "--skip-install" ]; then
    echo "📦 Installing dependencies..."
    pip3 install -r orchestration/requirements.txt
fi

# Run the requested mode
run_mode "$1" "$2" "$3"