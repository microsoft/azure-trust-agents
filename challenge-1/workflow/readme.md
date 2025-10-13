# Microsoft Agent Framework Tutorial: Building Your First Multi-Agent Workflow

**Expected Duration:** 45 minutes

Welcome to the exciting world of AI agent orchestration! In this tutorial, you'll learn how to build sophisticated workflows using the Microsoft Agent Framework. By the end of this session, you'll have created a complete fraud detection system that demonstrates real-world agent collaboration patterns.

If something isn't working as expected, don't hesitate to ask your coach for help!

## What You'll Build

You're going to create a powerful fraud detection workflow that combines three specialized AI agents:

1. **Customer Data Agent** - Your data detective that retrieves and analyzes customer information
2. **Risk Analyzer Agent** - Your fraud specialist that assesses transaction risk  
3. **Compliance Report Agent** - Your audit expert that generates formal compliance reports

Think of it like an expert team working together - each agent has its specialty, but they communicate seamlessly to solve complex problems that no single agent could handle alone.

## 🚀 Getting Started

### Two Ways to Learn

This tutorial provides two learning paths:

1. **📓 Interactive Notebook**: `sequential_workflow.ipynb` - Perfect for step-by-step learning with rich explanations
2. **🐍 Python Script**: `working_workflow.py` - Complete implementation ready to run

We recommend starting with the notebook to understand the concepts, then exploring the script for production patterns.

## 🧠 Understanding the Microsoft Agent Framework

Before we build our workflow, let's understand the key concepts that make agent orchestration possible.

### The Magic of Executors

Think of **executors** as specialized workers in your AI factory. Each executor:

- **Focuses on one task** - Like a specialist in your team
- **Handles its own AI agent** - Each executor manages its specific AI agent
- **Passes data safely** - Uses structured contracts to share information
- **Can be reused** - Once built, can be used in multiple workflows

```python
@executor
async def customer_data_executor(
    request: AnalysisRequest,
    ctx: WorkflowContext[CustomerDataResponse]
) -> None:
    # Your business logic here
    customer_data = await get_customer_info(request.transaction_id)
    result = CustomerDataResponse(customer_data=customer_data)
    await ctx.send_message(result)  # Pass to next executor
```

### Data Contracts with Pydantic

Just like a legal contract defines what each party will deliver, **Pydantic models** define exactly what data each executor expects and provides:

```python
class AnalysisRequest(BaseModel):
    message: str
    transaction_id: str = "TX1001"  # Default for testing

class CustomerDataResponse(BaseModel):
    customer_data: str
    transaction_id: str
    status: str
    raw_customer: dict = {}  # Extra context for next agent
```

This prevents errors and makes your workflow self-documenting - anyone can see exactly what data flows between agents.

### The Workflow Assembly Line

Think of the **WorkflowBuilder** as setting up an assembly line where each station (executor) performs a specific task:

```python
# Build your assembly line
workflow = (
    WorkflowBuilder()
    .set_start_executor(customer_data_executor)      # Station 1: Get data
    .add_edge(customer_data_executor, risk_analyzer_executor)  # Station 2: Analyze risk
    .add_edge(risk_analyzer_executor, compliance_report_executor)  # Station 3: Generate report
    .build()
)

# Start the production line
final_result = await workflow.run_stream(request)
```

The framework automatically:
- ✅ Validates that data types match between stations
- ✅ Handles errors gracefully if something goes wrong
- ✅ Tracks progress so you can see what's happening
- ✅ Ensures data flows correctly from one agent to the next

## 🏗️ Your Fraud Detection Architecture

Here's what you're building - a three-stage pipeline that processes transactions like a real financial institution:

```
📥 Transaction Request
    ↓
🔍 Customer Data Executor (Retrieves data from Cosmos DB)
    ↓ CustomerDataResponse
⚠️  Risk Analyzer Executor (AI risk assessment)
    ↓ RiskAnalysisResponse  
📋 Compliance Report Executor (Formal audit report)
    ↓ ComplianceAuditResponse ✅
```

### Real-World Data Flow

Let's trace through what happens when you analyze transaction `TX1001`:

1. **Customer Data Stage**: 
   - Pulls Alice Johnson's profile from Cosmos DB
   - Finds $5,200 transaction to Iran
   - Identifies risk factors (high-risk country, unusual amount)

2. **Risk Analysis Stage**:
   - AI agent analyzes the enriched data
   - Applies regulatory knowledge (sanctions, AML rules)
   - Recommends "BLOCK" with compliance reasoning

3. **Compliance Report Stage**:
   - Generates formal audit documentation
   - Creates actionable recommendations
   - Flags regulatory filing requirements

## 📚 Learning with the Interactive Notebook

The `sequential_workflow.ipynb` notebook is your hands-on learning environment. It's structured to teach you step-by-step:

### Section 1-3: Setup and Data Access
- Import the framework and connect to your data
- Set up Cosmos DB connections
- Create helper functions for data retrieval

### Section 4: Data Models
- Define your data contracts using Pydantic
- Learn why type safety matters in agent workflows

### Section 5-8: Building Your Agents
- **Customer Data Executor**: Your data retrieval specialist
- **Risk Analyzer Executor**: Your AI-powered risk assessor  
- **Compliance Report Executor**: Your audit documentation generator

### Section 9-11: Workflow Orchestration
- Connect your agents with edges
- Execute the complete workflow
- Display comprehensive results

Each section includes detailed explanations and real code you can run immediately.

## 🎯 Key Learning Objectives

By completing this tutorial, you'll master:

### 1. **Agent Communication Patterns**
- How agents pass structured data between each other
- The difference between intermediate and terminal executors
- Using `ctx.send_message()` vs `ctx.yield_output()`

### 2. **Type-Safe Workflows**
- Creating Pydantic models for bulletproof data contracts
- Understanding workflow validation and error prevention
- Building maintainable, self-documenting agent systems

### 3. **Real-World Integration**
- Connecting to Azure AI Foundry agents
- Working with live data from Cosmos DB
- Handling authentication and resource management

### 4. **Production Patterns**
- Error handling and graceful degradation
- Logging and monitoring workflow execution
- Building reusable, composable agent components

## 🚀 Let's Get Started!

### Option 1: Interactive Learning (Recommended)

Open the Jupyter notebook and follow along:

```bash
# Navigate to the tutorial directory
cd challenge-1/tutorial

# Open the interactive notebook
code sequential_workflow.ipynb
```

Run each cell step by step, reading the explanations and seeing the results in real-time.

### Option 2: Run the Complete Implementation

If you want to see the full workflow in action immediately:

```bash
# Run the complete implementation
python working_workflow.py
```

## Expected Results

When everything works correctly, you'll see output like this:

```
Audit Report ID: AUDIT_20241013_143022
Transaction: TX1001
Status: SUCCESS
Compliance Rating: NON_COMPLIANT
Audit Conclusion: HIGH RISK - Immediate review required (AI Enhanced: Based on comprehensive analysis...)
Risk Factors: ['HIGH_RISK_JURISDICTION', 'UNUSUAL_AMOUNT']
Compliance Concerns: ['Transaction involves high-risk jurisdiction requiring enhanced monitoring']
Recommendations: ['Freeze transaction pending investigation', 'Conduct enhanced customer due diligence', 'File suspicious activity report with regulators']
⚠️  IMMEDIATE ACTION REQUIRED
📋 REGULATORY FILING REQUIRED
```

This shows your three-agent workflow successfully:
- ✅ Retrieved real transaction data (Alice Johnson, $5,200 to Iran)
- ✅ Performed AI-powered risk analysis 
- ✅ Generated formal compliance documentation
- ✅ Provided actionable recommendations

## 🔍 Deep Dive: Understanding the Implementation

### The Three-Agent Architecture

Your workflow creates a sophisticated processing pipeline:

#### 🗃️ Customer Data Executor (Data Specialist)
```python
@executor
async def customer_data_executor(request, ctx) -> None:
    # Retrieves transaction TX1001 from Cosmos DB
    transaction_data = get_transaction_data(request.transaction_id)
    customer_data = get_customer_data(transaction_data.customer_id)
    
    # Creates comprehensive analysis with risk indicators
    analysis = create_fraud_analysis(transaction_data, customer_data)
    
    # Passes structured data to next agent
    await ctx.send_message(CustomerDataResponse(...))
```

#### ⚠️ Risk Analyzer Executor (AI Risk Specialist)  
```python
@executor
async def risk_analyzer_executor(customer_response, ctx) -> None:
    # Uses your Azure AI agent for expert analysis
    risk_agent = ChatAgent(client, model_id="gpt-4o-mini")
    
    # Sends enriched data for AI analysis
    result = await risk_agent.run(create_risk_prompt(customer_response))
    
    # Passes risk assessment to compliance agent
    await ctx.send_message(RiskAnalysisResponse(...))
```

#### 📋 Compliance Report Executor (Audit Specialist)
```python
@executor  
async def compliance_report_executor(risk_response, ctx) -> None:
    # Generates formal audit documentation
    audit_report = generate_audit_report(risk_response)
    
    # Creates actionable recommendations
    final_report = ComplianceAuditResponse(
        audit_conclusion="HIGH RISK - Immediate review required",
        compliance_rating="NON_COMPLIANT",
        recommendations=["Freeze transaction", "File regulatory report"]
    )
    
    # Final output of the workflow
    await ctx.yield_output(final_report)
```

## 🎓 What Makes This Powerful

### Real-World Data Processing
Your agents work with actual financial data:
- **Customer profiles** from Alice Johnson, Bob Chen, Carlos Rodriguez
- **Transaction records** with amounts, destinations, timestamps  
- **Risk indicators** like account age, device trust scores, fraud history

### AI-Powered Decision Making
The Risk Analyzer agent applies sophisticated reasoning:
- **Regulatory knowledge** about sanctions and high-risk countries
- **Pattern recognition** for unusual transaction behaviors
- **Compliance expertise** for AML/KYC requirements

### Production-Ready Patterns
Your implementation demonstrates enterprise practices:
- **Type safety** prevents data corruption between agents
- **Error handling** ensures graceful failure recovery
- **Structured logging** enables debugging and monitoring
- **Modular design** allows easy agent replacement or enhancement



## 🚀 Next Steps and Advanced Patterns

Congratulations! You've built a sophisticated multi-agent workflow. Here are some ways to extend your learning:

### 🔄 Add More Agents
```python
# Add a notification agent for alerts
builder.add_edge(compliance_report_executor, notification_executor)

# Add parallel processing for multiple risk models
builder.add_parallel_edges(customer_data_executor, [
    risk_analyzer_executor,
    ml_model_executor,
    rules_engine_executor
])
```

### 🎯 [Conditional Logic](https://learn.microsoft.com/en-us/agent-framework/user-guide/workflows/core-concepts/edges?pivots=programming-language-python#conditional-edges)
```python
# Route based on risk level
builder.add_conditional_edge(
    risk_analyzer_executor,
    condition=lambda result: result.recommendation == "BLOCK",
    target=immediate_alert_executor
)
```

### 📊 Enhanced Monitoring
```python
# Add comprehensive logging
async def monitored_executor(request, ctx):
    ctx.logger.info(f"Processing transaction {request.transaction_id}")
    start_time = time.time()
    
    result = await process_transaction(request)
    
    ctx.logger.info(f"Completed in {time.time() - start_time:.2f}s")
    await ctx.send_message(result)
```

## 🎯 Key Takeaways

✅ **Agent Orchestration**: You can combine multiple AI agents to solve complex problems  
✅ **Type Safety**: Pydantic models prevent errors and make workflows self-documenting  
✅ **Real Integration**: Your agents work with live Azure services and data  
✅ **Production Patterns**: Error handling, logging, and monitoring are built-in  
✅ **Composability**: Executors can be reused and combined in different workflows

## 🎉 Conclusion

You've just built a production-ready, multi-agent fraud detection system using the Microsoft Agent Framework! This workflow demonstrates enterprise patterns that scale to handle real-world complexity.

Your agents can now:
- 🔍 **Investigate** transactions using multiple data sources
- 🧠 **Reason** about complex fraud patterns using AI
- 📋 **Document** findings for regulatory compliance
- ⚡ **Scale** to process thousands of transactions

Ready for the next challenge? Let's see what other amazing agent workflows you can build!