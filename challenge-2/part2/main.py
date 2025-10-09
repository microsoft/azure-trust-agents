"""
FastAPI application for the Fraud Detection Agent Orchestration API.
This serves as the main entry point for containerized deployment on Azure Container Apps.
"""

import asyncio
import logging
import os
from typing import Dict, Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from dotenv import load_dotenv

from orchestration import orchestrate_fraud_detection, initialize_memory
from mem0 import Memory

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv(override=True)

# Global memory instance
memory_instance: Optional[Memory] = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize memory system on startup and cleanup on shutdown."""
    global memory_instance
    
    # Startup
    logger.info("🚀 Starting Fraud Detection API...")
    logger.info("🧠 Initializing Memory System...")
    
    try:
        memory_instance = initialize_memory()
        if memory_instance:
            logger.info("✅ Memory system initialized successfully")
        else:
            logger.warning("⚠️  Memory system not available - running without persistent memory")
    except Exception as e:
        logger.error(f"❌ Memory initialization failed: {str(e)}")
        memory_instance = None
    
    yield
    
    # Shutdown
    logger.info("🧹 Shutting down Fraud Detection API...")

# Create FastAPI app with lifespan events
app = FastAPI(
    title="Fraud Detection Agent Orchestration API",
    description="Multi-agent fraud detection system with persistent memory capabilities",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware for web frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic models for request/response
class FraudAnalysisRequest(BaseModel):
    transaction_id: str = Field(..., description="Unique transaction identifier", example="TX2003")
    customer_id: str = Field(..., description="Unique customer identifier", example="CUST1005")

class FraudAnalysisResponse(BaseModel):
    transaction_id: str
    customer_id: str
    analysis_result: str
    memory_available: bool
    execution_time_ms: Optional[float] = None

class HealthResponse(BaseModel):
    status: str
    memory_available: bool
    environment_check: Dict[str, bool]

class MemorySearchRequest(BaseModel):
    query: str = Field(..., description="Search query for memory", example="customer CUST1005 fraud history")
    user_id: Optional[str] = Field(None, description="User ID to filter memories", example="CUST1005")
    limit: int = Field(5, description="Maximum number of results", ge=1, le=20)

class MemorySearchResponse(BaseModel):
    query: str
    results: list
    count: int

@app.get("/", response_model=Dict[str, str])
async def root():
    """Root endpoint with API information."""
    return {
        "message": "Fraud Detection Agent Orchestration API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health"
    }

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint for container monitoring."""
    
    # Check required environment variables
    required_env_vars = [
        "AI_FOUNDRY_PROJECT_ENDPOINT",
        "DATA_INGESTION_AGENT_ID", 
        "TRANSACTION_ANALYST_AGENT_ID",
        "AZURE_OPENAI_ENDPOINT",
        "AZURE_OPENAI_KEY",
        "AZURE_OPENAI_DEPLOYMENT_NAME",
        "COSMOS_ENDPOINT",
        "COSMOS_KEY"
    ]
    
    env_check = {var: bool(os.environ.get(var)) for var in required_env_vars}
    
    return HealthResponse(
        status="healthy" if all(env_check.values()) else "degraded",
        memory_available=memory_instance is not None,
        environment_check=env_check
    )

@app.post("/analyze", response_model=FraudAnalysisResponse)
async def analyze_fraud(request: FraudAnalysisRequest):
    """
    Analyze a transaction for potential fraud using the multi-agent orchestration system.
    
    This endpoint orchestrates multiple AI agents to perform comprehensive fraud detection:
    - Data Ingestion Agent: Fetches customer and transaction data
    - Transaction Analyst Agent: Performs fraud risk analysis using ML predictions
    - Fraud Decision Approver: Makes final determination with reasoning
    
    The system uses persistent memory to learn from past analyses and improve accuracy.
    """
    
    logger.info(f"📊 Starting fraud analysis for transaction {request.transaction_id}, customer {request.customer_id}")
    
    try:
        import time
        start_time = time.time()
        
        # Run the orchestration
        result = await orchestrate_fraud_detection(
            transaction_id=request.transaction_id,
            customer_id=request.customer_id,
            memory=memory_instance
        )
        
        execution_time = (time.time() - start_time) * 1000  # Convert to milliseconds
        
        logger.info(f"✅ Analysis completed in {execution_time:.2f}ms")
        
        return FraudAnalysisResponse(
            transaction_id=request.transaction_id,
            customer_id=request.customer_id,
            analysis_result=result,
            memory_available=memory_instance is not None,
            execution_time_ms=round(execution_time, 2)
        )
        
    except Exception as e:
        logger.error(f"❌ Analysis failed: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Fraud analysis failed: {str(e)}"
        )

@app.post("/memory/search", response_model=MemorySearchResponse)
async def search_memory(request: MemorySearchRequest):
    """
    Search the memory system for historical fraud analysis context.
    
    This endpoint allows querying the persistent memory for past analyses,
    customer behavior patterns, and fraud detection decisions.
    """
    
    if not memory_instance:
        raise HTTPException(
            status_code=503,
            detail="Memory system not available"
        )
    
    logger.info(f"🔍 Searching memory: '{request.query}' for user: {request.user_id}")
    
    try:
        results = memory_instance.search(
            query=request.query,
            user_id=request.user_id,
            limit=request.limit
        )
        
        return MemorySearchResponse(
            query=request.query,
            results=results.get('results', []),
            count=len(results.get('results', []))
        )
        
    except Exception as e:
        logger.error(f"❌ Memory search failed: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Memory search failed: {str(e)}"
        )

@app.get("/memory/stats")
async def memory_stats():
    """Get memory system statistics and configuration."""
    
    if not memory_instance:
        raise HTTPException(
            status_code=503,
            detail="Memory system not available"
        )
    
    try:
        # Get some basic stats about stored memories
        # Note: This is a simplified version - in production you might want more detailed stats
        return {
            "status": "available",
            "provider": "azure_ai_search",
            "collection": "fraud_detection_memories",
            "embedding_dimensions": 1536
        }
        
    except Exception as e:
        logger.error(f"❌ Memory stats failed: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Memory stats failed: {str(e)}"
        )

@app.post("/analyze/batch")
async def analyze_fraud_batch(
    requests: list[FraudAnalysisRequest],
    background_tasks: BackgroundTasks
):
    """
    Batch analysis endpoint for processing multiple transactions.
    
    This endpoint accepts multiple fraud analysis requests and processes them
    in the background, returning immediately with a job ID for status tracking.
    """
    
    if len(requests) > 10:  # Limit batch size
        raise HTTPException(
            status_code=400,
            detail="Batch size limited to 10 transactions"
        )
    
    # In a production system, you'd want to implement proper job queuing
    # For now, we'll process them sequentially in the background
    
    job_id = f"batch_{int(asyncio.get_event_loop().time())}"
    
    async def process_batch():
        logger.info(f"📦 Processing batch job {job_id} with {len(requests)} transactions")
        
        for request in requests:
            try:
                await analyze_fraud(request)
            except Exception as e:
                logger.error(f"❌ Batch item failed {request.transaction_id}: {str(e)}")
    
    background_tasks.add_task(process_batch)
    
    return {
        "job_id": job_id,
        "status": "submitted",
        "transaction_count": len(requests),
        "message": f"Batch analysis started for {len(requests)} transactions"
    }

if __name__ == "__main__":
    import uvicorn
    
    # Run the FastAPI application
    port = int(os.environ.get("PORT", 8000))
    
    logger.info(f"🚀 Starting Fraud Detection API on port {port}")
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        log_level="info",
        reload=False  # Set to True for development
    )