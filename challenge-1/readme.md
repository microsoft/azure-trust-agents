# Challenge 1: Building Fraud Detection Agents 🤖

**Expected Duration:** 60 minutes

## Introduction

In this challenge, you'll create specialized AI agents for fraud detection and orchestrate them to work together as a team. You'll build two Azure AI agents with different capabilities: a Data Ingestion Agent that fetches and normalizes customer and transaction data, and a Transaction Analyst Agent that performs fraud risk analysis using ML predictions and regulatory compliance checks.

Finally, you'll create a ChatCompletionAgent to serve as the final decision maker and orchestrate all three agents using Semantic Kernel's GroupChatOrchestration to analyze transactions for potential fraud in an automated, intelligent workflow.


## Step-by-Step Guide 📋

### Step 1: Understanding the Plugin Tools 🔧

Before creating your agents, let's explore the tools they'll use to access data. Navigate to the `multi-agents` folder and examine the `tools.py` file:

```bash
cd challenge-1/multi-agents
cat tools.py
```

**What you'll find:**

1. **CustomerDataPlugin** - Provides access to customer information:
   - `get_customer(customer_id)` - Fetch customer details by ID
   - `get_customer_by_country(country)` - Get all customers from a specific country
   
2. **TransactionDataPlugin** - Provides access to transaction data:
   - `get_transaction(transaction_id)` - Fetch transaction details by ID
   - `get_transactions_by_customer(customer_id)` - Get all transactions for a customer
   - `get_transactions_by_destination(destination_country)` - Get transactions to a destination country

3. **MLPredictionsPlugin** - Provides access to ML fraud prediction scores:
   - `get_ml_prediction(transaction_id)` - Get ML fraud score for a specific transaction
   - `get_all_ml_predictions()` - Get all ML prediction scores

**💡 Key Concept:** These plugins are Semantic Kernel functions that connect to your Cosmos DB database. Each function is decorated with `@kernel_function` and uses proper typing with `Annotated` parameters. The agents will use these functions to fetch data during their analysis.

**📝 Task:** Open `tools.py` in your editor and review how each plugin connects to Cosmos DB and retrieves data. Notice the error handling and how results are formatted as JSON strings.

---

### Step 2: Create the Data Ingestion Agent 📥

Now let's create your first agent. This agent will be responsible for fetching and normalizing transaction and customer data.

```bash
cd challenge-1/agents
python data_ingestion_agent.py
```

**What happens:**
- The script connects to Azure AI Foundry using your credentials
- Creates an agent called "data-ingestion-agent" 
- Configures the agent WITHOUT function tools (important for Semantic Kernel integration)
- Returns an agent ID that gets saved to your `.env` file

**Expected Output:**
```
Created data ingestion agent with ID: asst_XXXXXXXXXXXXXXXXX
Agent name: data-ingestion-agent
```

**📝 Task:** 
1. Run the command above
2. Copy the agent ID from the output
3. Open your `.env` file and verify it contains: `DATA_INGESTION_AGENT_ID=asst_XXXXXXXXXXXXXXXXX`

**🔍 Explore the Agent Code:**

Open `data_ingestion_agent.py` and examine:

- **Line 30-38**: How the CustomerDataPlugin and TransactionDataPlugin are initialized with Cosmos DB credentials
- **Line 40-60**: The agent instructions that define its role and behavior
- **Key Point**: Notice the agent is created WITHOUT `tools` parameter - functions will be provided via Semantic Kernel kernel parameter during orchestration

**❓ Question to Consider:** Why do we create the agent without function tools? Because Azure AI agents with pre-defined function tools can't have those tools overridden by Semantic Kernel during orchestration. By creating the agent without tools, we can dynamically provide functions via the kernel parameter.

---

### Step 3: Create the Transaction Analyst Agent ⚠️

Now let's create the second agent that performs fraud risk analysis.

```bash
python transaction_analyst_agent.py
```

**What happens:**
- Connects to Azure AI Foundry
- Creates an agent called "transaction-agent"
- Configures the agent with Azure AI Search tool (for regulatory compliance lookups)
- ML prediction functions will be provided via Semantic Kernel (not registered here)
- Returns an agent ID that gets saved to your `.env` file

**Expected Output:**
```
Created transaction agent with ID: asst_XXXXXXXXXXXXXXXXX
Agent name: transaction-agent
```

**📝 Task:**
1. Run the command above
2. Copy the agent ID from the output
3. Open your `.env` file and verify it contains: `TRANSACTION_ANALYST_AGENT_ID=asst_XXXXXXXXXXXXXXXXX`

**🔍 Explore the Agent Code:**

Open `transaction_analyst_agent.py` and examine:

- **Line 28-35**: Azure AI Search tool configuration for querying regulations and policies
- **Line 37-43**: ML Predictions plugin initialization (functions will be provided via kernel)
- **Line 45-75**: Agent instructions defining fraud detection criteria:
  - High-risk countries: NG, IR, RU, KP
  - High amount threshold: $10,000 USD
  - Suspicious account age: < 30 days
  - Low device trust threshold: < 0.5

**❓ Question to Consider:** Why does this agent have AI Search tool registered directly but ML predictions via kernel? Because Azure AI Search is a built-in Azure AI Agent Service tool with special resource requirements, while ML predictions are custom Semantic Kernel functions that need kernel registration.

---

### Step 4: Verify Your Agents in Azure AI Foundry 🌐

Let's confirm your agents were created successfully in Azure AI Foundry.

**📝 Task:**
1. Open your browser and navigate to [Azure AI Foundry](https://ai.azure.com/)
2. Sign in with your Azure credentials
3. Navigate to your project (the name is in your `.env` file as `AI_FOUNDRY_PROJECT_NAME`)
4. Click on **"Agents"** in the left navigation menu
5. You should see both agents listed:
   - **data-ingestion-agent** - Data normalization and enrichment
   - **transaction-agent** - Fraud risk analysis

**🔍 Explore Each Agent:**
- Click on each agent to view its configuration
- Review the instructions you provided
- Check the model deployment (should be gpt-4.1-mini)
- Notice the transaction-agent has AI Search tool connected

---

### Step 5: Understanding the Orchestration Architecture 🎭

Before running the orchestration, let's understand how the three agents will work together.

**📝 Task:** Open `challenge-1/multi-agents/orchestration.py` and explore:

**Key Components:**

1. **Plugin Initialization (Lines 40-58)**:
   ```python
   customer_plugin = CustomerDataPlugin(...)
   transaction_plugin = TransactionDataPlugin(...)
   ml_predictions_plugin = MLPredictionsPlugin(...)
   ```

2. **Kernel Creation (Lines 60-66)**:
   ```python
   data_kernel = Kernel()
   data_kernel.add_plugin(customer_plugin, plugin_name="CustomerData")
   data_kernel.add_plugin(transaction_plugin, plugin_name="TransactionData")
   
   transaction_kernel = Kernel()
   transaction_kernel.add_plugin(ml_predictions_plugin, plugin_name="MLPredictions")
   ```

3. **Agent Loading (Lines 70-88)**:
   - Data Ingestion Agent loaded by ID with `data_kernel`
   - Transaction Analyst Agent loaded by ID with `transaction_kernel`
   - Both use `kernel` parameter (not `plugins`)

4. **ChatCompletionAgent Creation (Lines 90-120)**:
   - FraudDecisionApprover agent created with decision criteria
   - Uses Azure OpenAI directly (not Azure AI Agent Service)
   - Makes final FRAUD/SUSPICIOUS/LEGITIMATE determination

5. **GroupChatOrchestration (Lines 135-142)**:
   - Coordinates all three agents
   - Uses RoundRobinGroupChatManager (agents take turns)
   - Max 4 rounds of conversation


---

### Step 6: Run the Orchestration 🚀

Now let's see all three agents working together to analyze a transaction!

```bash
cd challenge-1/multi-agents
python orchestration.py
```

**What happens:**
1. **Initialization**: Loads both Azure AI agents by ID and creates the ChatCompletionAgent
2. **Data Ingestion Phase**: Data agent fetches TX1001 transaction and CUST1001 customer data
3. **Risk Analysis Phase**: Transaction analyst evaluates fraud risk using ML predictions and rules
4. **Decision Phase**: Approver reviews all data and makes final fraud determination
5. **Output**: Complete fraud analysis with decision, risk level, and reasoning

**Expected Output Structure:**
```
🚀 Starting Fraud Detection Orchestration
Transaction ID: TX1001, Customer ID: CUST1001
================================================================================
🔧 Loading specialized fraud detection agents...
✅ Connected to AI Foundry endpoint.
✅ All agents loaded successfully!

# data-ingestion-agent
[Transaction and customer data fetched from Cosmos DB...]

# transaction-agent
risk_score: 10
risk_level: Low
reason: [Detailed fraud risk analysis...]

# FraudDecisionApprover
Decision: LEGITIMATE
Risk Level: LOW
Reasoning: [Final decision rationale...]
Recommendation: [Next steps...]

✅ Fraud Detection Orchestration Complete!
```

**📝 Task:**
1. Run the orchestration command
2. Watch the agent interactions in real-time
3. Review the final output JSON with complete analysis

---

### Step 7: Test with Different Transactions 🧪

Let's test the system with different risk profiles.

**Test Case 1: Low-Risk Transaction (TX1001)**
```python
transaction_id = "TX1001"
customer_id = "CUST1001"
```

**Test Case 2: High-Risk Transaction (TX1002)**

Open `orchestration.py` and change lines 184-185 to:
```python
transaction_id = "TX1002"  # High-risk: Large amount to Nigeria
customer_id = "CUST1002"   # Customer with fraud history
```

Run the orchestration again:
```bash
python orchestration.py
```

**Expected Difference:**
- Higher fraud risk score (likely 70-85)
- Risk level: High
- Decision: Likely FRAUD or SUSPICIOUS
- Reasoning will mention: high-risk country (NG), past fraud history, low device trust

**📝 Task:**
1. Test TX1002 and compare results with TX1001
2. Review how the agents adapt their analysis based on risk factors
3. Notice how the final decision changes based on the data

**Test Case 3: Create Your Own Scenario**

Choose any transaction from `challenge-0/data/transactions.json`:
- TX1003 - Low amount to China
- TX1004 - Large amount to Iran (high-risk country)
- TX1007 - Transaction to Russia (high-risk country)

**📝 Task:** Test at least one more transaction and analyze the results.

---



## Key Learnings 🎓

After completing this challenge, you should understand:

1. **Azure AI Agent Service**: How to create agents in Azure AI Foundry
2. **Semantic Kernel Plugins**: Building reusable function tools for agents
3. **Kernel Registration**: Why and how to register plugins to kernels
4. **Agent Orchestration**: Coordinating multiple agents with GroupChatOrchestration
5. **ChatCompletionAgent**: Using LLM-based agents for decision making
6. **Multi-Agent Workflows**: Designing agent collaboration patterns


