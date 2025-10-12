# Microsoft Agent Framework Tutorial: Fraud Detection Workflow

This tutorial demonstrates how to use the Microsoft Agent Framework to orchestrate AI agents for fraud detection analysis using pre-existing agents from Azure AI Foundry.

## Overview

The Microsoft Agent Framework enables you to create sophisticated workflows by connecting multiple AI agents together. In this fraud detection scenario, we orchestrate two specialized agents:

1. **Customer Data Agent** - Analyzes customer and transaction data
2. **Risk Analyzer Agent** - Performs fraud risk assessment based on enriched data

## Microsoft Agent Framework Core Components

### 1. **Executors**

Executors are the fundamental building blocks of the framework. They are Python functions decorated with `@executor` that wrap your business logic and AI agent interactions.

```python
@executor
async def customer_data_executor(
    request: AnalysisRequest,
    ctx: WorkflowContext[CustomerDataResponse]
) -> CustomerDataResponse:
    """Customer Data Executor using pre-loaded agent."""
    # Your business logic here
    result = await customer_agent.run(request.message)
    return CustomerDataResponse(...)
```

**Key Characteristics:**
- **Async Functions**: Support asynchronous operations like AI agent calls
- **Type-Safe**: Input and output types are validated at runtime
- **Stateless**: Each execution is independent and can be retried
- **Context Aware**: Receive `WorkflowContext` for framework integration

### 2. **Base Models (Pydantic)**

Base models define the data contracts between executors using Pydantic for validation and serialization.

```python
class AnalysisRequest(BaseModel):
    message: str
    transaction_id: str = "12345"

class CustomerDataResponse(BaseModel):
    customer_data: str
    transaction_data: str
    transaction_id: str
    status: str
```

**Benefits:**
- **Data Validation**: Automatic validation of input/output data
- **Type Safety**: Compile-time and runtime type checking
- **Serialization**: Automatic JSON serialization for data passing
- **Documentation**: Self-documenting API contracts
- **IDE Support**: IntelliSense and auto-completion

### 3. **Workflow & WorkflowBuilder**

The Workflow orchestrates executor execution and manages data flow between them.

```python
# Building a workflow
builder = WorkflowBuilder()
builder.set_start_executor(customer_data_executor)
builder.add_edge(customer_data_executor, risk_analyzer_executor)
workflow = builder.build()

# Executing a workflow
result = await workflow.run(AnalysisRequest(...))
```

**Workflow Features:**
- **Execution Order**: Defines the sequence of executor execution
- **Data Flow**: Manages data passing between executors
- **Validation**: Ensures type compatibility between connected executors
- **Error Handling**: Built-in error propagation and recovery
- **Monitoring**: Tracks execution progress and performance

### 4. **Edges**

Edges define the connections between executors and how data flows through the workflow.

```python
# Direct edge: output of executor1 becomes input of executor2
builder.add_edge(executor1, executor2)

# Conditional edge: execute executor2 only if condition is met
builder.add_conditional_edge(
    source=executor1, 
    condition=lambda result: result.status == "SUCCESS",
    target=executor2
)

# Parallel edges: execute multiple executors simultaneously
builder.add_parallel_edges(executor1, [executor2, executor3, executor4])
```

**Edge Types:**
- **Sequential**: Data flows from one executor to the next
- **Conditional**: Execution depends on runtime conditions
- **Parallel**: Multiple executors run simultaneously
- **Fan-out/Fan-in**: One-to-many or many-to-one data flows

**Type Compatibility:**
```python
# ✅ Compatible: CustomerDataResponse → RiskAnalysisRequest
customer_executor → risk_analyzer_executor

# ❌ Incompatible: Different types will cause validation errors
executor_output_string → executor_expects_integer
```

### 5. **WorkflowContext**

WorkflowContext provides the runtime environment and framework integration for executors.

```python
@executor
async def my_executor(
    request: MyRequest,
    ctx: WorkflowContext[MyResponse]  # Generic type for output validation
) -> MyResponse:
    # Access workflow metadata
    workflow_id = ctx.workflow_id
    execution_id = ctx.execution_id
    
    # Log information
    ctx.logger.info("Starting execution")
    
    # Return validated response
    return MyResponse(...)
```

**Context Features:**
- **Logging**: Structured logging with workflow correlation
- **Metadata**: Access to workflow and execution identifiers
- **Type Safety**: Generic typing for output validation
- **Framework Integration**: Hooks for monitoring and debugging

### 6. **Events**

The framework generates events throughout workflow execution for monitoring and debugging.

```python
# Common event types returned from workflow.run()
[
    ExecutorInvokedEvent(executor_id="customer_data_executor", data=None),
    ExecutorCompletedEvent(executor_id="customer_data_executor", data=CustomerDataResponse(...)),
    ExecutorInvokedEvent(executor_id="risk_analyzer_executor", data=CustomerDataResponse(...)),
    ExecutorCompletedEvent(executor_id="risk_analyzer_executor", data=RiskAnalysisResponse(...))
]
```

**Event Types:**
- **ExecutorInvokedEvent**: Executor started with input data
- **ExecutorCompletedEvent**: Executor finished with output data
- **ExecutorFailedEvent**: Executor encountered an error
- **WorkflowStartedEvent**: Workflow execution began
- **WorkflowCompletedEvent**: Workflow execution finished

**Event Usage:**
```python
workflow_result = await workflow.run(request)

# Access final result
final_event = workflow_result[-1]
if isinstance(final_event, ExecutorCompletedEvent):
    final_data = final_event.data
    print(f"Final result: {final_data}")

# Track execution flow
for event in workflow_result:
    print(f"Event: {event.executor_id} - {type(event).__name__}")
```

## Architecture

```
AnalysisRequest → [Customer Data Executor] → CustomerDataResponse → [Risk Analyzer Executor] → RiskAnalysisResponse
                        ↓                            ↓                         ↓
                 ExecutorInvokedEvent    ExecutorCompletedEvent    ExecutorCompletedEvent
```

### Data Flow Example

1. **Input**: `AnalysisRequest` enters the workflow
2. **Edge 1**: Data flows to `customer_data_executor`
3. **Processing**: Executor calls AI agent and transforms data
4. **Output**: Returns `CustomerDataResponse`
5. **Edge 2**: `CustomerDataResponse` flows to `risk_analyzer_executor`
6. **Processing**: Risk analysis using customer data
7. **Final Output**: `RiskAnalysisResponse` with fraud assessment

### Type Safety Flow

```python
# Framework validates this flow automatically:
AnalysisRequest 
    → customer_data_executor(AnalysisRequest) → CustomerDataResponse
    → risk_analyzer_executor(CustomerDataResponse) → RiskAnalysisResponse
```

If types don't match, you get a clear error:
```
TypeCompatibilityError: Source executor outputs CustomerDataResponse 
but target executor expects AnalysisRequest
```

## Code Structure

### 1. Data Models

```python
class AnalysisRequest(BaseModel):
    message: str
    transaction_id: str = "12345"

class CustomerDataResponse(BaseModel):
    customer_data: str
    transaction_data: str
    transaction_id: str
    status: str

class RiskAnalysisResponse(BaseModel):
    risk_analysis: str
    risk_score: str
    transaction_id: str
    status: str
```

### 2. Executor Functions

Executors are the core building blocks that wrap your AI agents:

```python
@executor
async def customer_data_executor(
    request: AnalysisRequest,
    ctx: WorkflowContext[CustomerDataResponse]
) -> CustomerDataResponse:
    """Customer Data Executor using pre-loaded agent."""
    result = await customer_agent.run(request.message)
    return CustomerDataResponse(
        customer_data=result.text,
        transaction_data=f"Transaction data for {request.transaction_id}",
        transaction_id=request.transaction_id,
        status="SUCCESS"
    )
```

**Key Points:**
- `@executor` decorator registers the function with the framework
- `WorkflowContext[T]` provides type safety for output validation
- Functions are async to support AI agent interactions
- Return types must match the declared WorkflowContext type

### 3. Agent Loading Pattern

```python
# Create Azure AI clients bound to specific agent IDs
customer_client = AzureAIAgentClient(
    project_endpoint=project_endpoint,
    model_deployment_name=model_deployment_name,
    async_credential=credential,
    agent_id=CUSTOMER_DATA_AGENT_ID  # Pre-existing agent ID
)

# Use clients as context managers
async with customer_client as client:
    # Create ChatAgent wrapper
    customer_agent = ChatAgent(
        chat_client=client,
        model_id=model_deployment_name,
        store=True
    )
```

**Why This Pattern:**
- `AzureAIAgentClient` connects to existing agents by ID (no creation needed)
- Context managers ensure proper resource cleanup
- `ChatAgent` provides the `.run()` interface for agent interaction

### 4. Workflow Construction

```python
# Build workflow with proper data flow
builder = WorkflowBuilder()
builder.set_start_executor(customer_data_executor)
builder.add_edge(customer_data_executor, risk_analyzer_executor)
workflow = builder.build()

# Execute workflow
result = await workflow.run(AnalysisRequest(...))
```

**Workflow Features:**
- Type validation ensures output/input compatibility
- Sequential execution with data passing between executors
- Built-in error handling and logging
- Event-driven result tracking

## Environment Setup

Required environment variables:

```bash
# Azure AI Foundry Configuration
AI_FOUNDRY_PROJECT_ENDPOINT=https://your-project.cognitiveservices.azure.com/
MODEL_DEPLOYMENT_NAME=gpt-4o-mini

# Pre-existing Agent IDs (from Azure AI Foundry)
CUSTOMER_DATA_AGENT_ID=asst_xxxxxxxxxxxxxxxxxxxxxxxx
RISK_ANALYSER_AGENT_ID=asst_xxxxxxxxxxxxxxxxxxxxxxxx
```

## Running the Tutorial

```bash
# Install dependencies
pip install agent-framework azure-identity python-dotenv

# Run the tutorial
python tutorial.py
```

## Expected Output

```
✅ Connected to DataIngestionAgent (ID: asst_xxx...)
✅ Connected to RiskAnalyserAgent (ID: asst_xxx...)

🧪 Testing DataIngestionAgent...
✅ DataIngestionAgent response: [Customer analysis response...]

🧪 Testing RiskAnalyserAgent...
✅ RiskAnalyserAgent response: [Risk assessment response...]

✅ Workflow built successfully with loaded agents!

🧪 Testing workflow...
✅ Workflow completed: [ExecutorInvokedEvent(...), ExecutorCompletedEvent(...)]

📊 Final Risk Analysis:
   Transaction ID: TX1001
   Risk Score: High Risk
   Status: SUCCESS
   Analysis: [Detailed fraud risk assessment...]
```

## Microsoft Agent Framework Benefits

### 1. **Type Safety**
- Pydantic models ensure data integrity
- Compile-time validation of executor connections
- Clear contracts between workflow stages

### 2. **Scalability**
- Reusable executor functions
- Easy to add new agents to existing workflows
- Parallel execution support (not shown in this example)

### 3. **Enterprise Ready**
- Built-in logging and monitoring
- Error handling and recovery
- Azure integration for authentication and security

### 4. **Agent Reusability**
- Connect to existing Azure AI Foundry agents
- No need to recreate or duplicate agent logic
- Consistent agent behavior across workflows

## Advanced Patterns

### Parallel Execution
```python
# Execute multiple agents in parallel
builder.add_parallel_executors([executor1, executor2, executor3])
```

### Conditional Logic
```python
# Add conditional branching
builder.add_conditional_edge(source_executor, condition_func, target_executor)
```

### Error Handling
```python
# Custom error handling in executors
try:
    result = await agent.run(prompt)
    return SuccessResponse(...)
except Exception as e:
    return ErrorResponse(error=str(e), status="FAILED")
```

## Best Practices

1. **Use Descriptive Models**: Create specific Pydantic models for each data flow
2. **Global Agent Storage**: Store agent instances globally for executor access
3. **Proper Context Management**: Always use `async with` for Azure clients
4. **Type Annotations**: Include `WorkflowContext[T]` for better validation
5. **Error Boundaries**: Handle exceptions within executors to maintain workflow stability

## Troubleshooting

### Common Issues

**"Type incompatibility between executors"**
- Ensure output type of source executor matches input type of target executor
- Check Pydantic model definitions

**"'AzureAIAgentClient' object has no attribute 'run'"**
- Use `ChatAgent` wrapper around the client
- Don't call `.run()` directly on `AzureAIAgentClient`

**"Agent ID not found"**
- Verify agent IDs exist in Azure AI Foundry
- Check environment variable names and values

This tutorial demonstrates the power of the Microsoft Agent Framework for creating robust, type-safe, and scalable AI agent workflows while leveraging existing Azure AI Foundry agents.