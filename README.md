# Azure Trust and Compliance Multi-Agents Hack 🤖

Welcome to the Automated Compliance Agents Hackathon! 🏦 Today, you'll dive into the world of intelligent agent systems powered by Azure AI to revolutionize regulatory compliance in financial services. Get ready for a hands-on, high-impact day of learning and innovation!

## Introduction 

Get ready to transform compliance with AI using the revolutionary **Microsoft Agent Framework**! In this hackathon, you'll master the latest enterprise-grade agent technology to build intelligent compliance systems that parse regulations, monitor transactions, and generate transparent audit trails—just like real compliance teams, but faster and more accurate. 

Using sequential orchestration, MCP integration, and Agent-to-Agent communication, your specialized agents will collaborate seamlessly to automate complex regulatory workflows in minutes, not months. From data ingestion through risk analysis to compliance reporting, you'll create a production-ready multi-agent system with full observability that redefines how financial institutions stay compliant and build trust. 

## Learning Objectives 🎯

By participating in this hackathon, you will learn how to:

- **Master Microsoft Agent Framework** using the new enterprise-grade SDK for building, orchestrating, and deploying sophisticated AI agents with sequential workflows and multi-agent systems.
- **Build Specialized Compliance Agents** (Customer Data, Risk Analyzer, Compliance Reporter) with advanced prompt engineering, tool integration, and persistent memory capabilities.
- **Implement MCP Integration** using Model Context Protocol (MCP) servers to connect agents with external compliance systems, alert mechanisms, and enterprise tools seamlessly.
- **Deploy Agent-to-Agent Communication** leveraging A2A protocols for advanced multi-agent interactions and distributed compliance workflows.
- **Apply Responsible AI & Observability** using OpenTelemetry monitoring, GitHub Actions evaluation, Azure AI Foundry tracking, and Log Analytics integration for production-ready agent systems.

## Architecture 🏗️

The Azure Trust and Compliance Multi-Agents system leverages the **Microsoft Agent Framework** to create a sophisticated, enterprise-ready compliance monitoring solution.

### **Agent Framework Details**

#### **1. Customer Data Agent**
- **Purpose**: Fetches and normalizes transaction and customer data
- **Data Sources**: Azure Cosmos DB
- **Capabilities**: Customer profiling, transaction history analysis, risk pattern detection
- **Output**: Structured customer and transaction data for downstream agents

#### **2. Risk Analyzer Agent**
- **Purpose**: Evaluates fraud risk against regulatory policies
- **Data Sources**: Azure AI Search (regulatory knowledge base)
- **Capabilities**: KYC compliance analysis, risk-based assessment, ongoing monitoring
- **Output**: Risk scores, compliance flags, regulatory assessment

#### **3. Compliance Report Agent**
- **Purpose**: Generates formal audit reports and compliance documentation
- **Integration**: MCP Alert Server, A2A communication
- **Capabilities**: Executive summaries, detailed findings, actionable recommendations
- **Output**: Audit reports, compliance ratings, regulatory filing requirements

### **Technology Stack**

| Component | Technology | Purpose |
|-----------|------------|---------|
| **Agent Runtime** | Microsoft Agent Framework | Enterprise-grade agent orchestration |
| **API Gateway** | Azure API Management (Basic v2) | API security and management |
| **Data Storage** | Azure Cosmos DB | Transaction and customer data persistence |
| **Search & Knowledge** | Azure AI Search | Regulatory document processing |
| **AI Platform** | Azure AI Foundry + GPT-4o-mini | Agent management and AI capabilities |
| **Integration** | Model Context Protocol (MCP) | Enterprise system connectivity |
| **Monitoring** | OpenTelemetry + Log Analytics | Full observability and tracking |
| **Evaluation** | GitHub Actions | Automated testing and validation |
| **Deployment** | Container Apps | Scalable containerized deployment |

## Data Flow 🔄

This project implements an end-to-end AI-driven compliance monitoring workflow using the **Microsoft Agent Framework**. The system processes high-risk transactions flagged by ML models through a sophisticated multi-agent pipeline:

**Agent Framework Architecture:**
```
High-Risk TX Input → [Customer Data Agent] → [Risk Analyzer Agent] → [Compliance Report Agent] → Audit Output
                      ↓ Cosmos DB          ↓ Azure AI Search      ↓ MCP Alert Server
                   Transaction Data      Regulatory Rules        Real-time Alerts
```

**Key Components:**
- **Sequential Orchestration**: Agents work in coordinated sequence using the Agent Framework's orchestration capabilities
- **MCP Integration**: Model Context Protocol servers enable seamless integration with existing enterprise alert systems
- **A2A Communication**: Agent-to-Agent communication protocols for advanced multi-agent interactions
- **Persistent Memory**: Azure Cosmos DB maintains context and builds comprehensive audit trails
- **Real-time Alerts**: Automated compliance notifications through integrated alert systems

The pipeline ensures continuous monitoring of flagged events, rapid response to high-risk activities, and robust compliance reporting with full observability.

### **Data Flow Sequence**
1. **Trigger**: ML model flags high-risk transaction
2. **Data Gathering**: Customer Data Agent retrieves comprehensive customer and transaction context
3. **Risk Analysis**: Risk Analyzer Agent evaluates against regulatory requirements
4. **Report Generation**: Compliance Report Agent creates audit documentation
5. **Alert Distribution**: MCP Server routes alerts to enterprise systems
6. **A2A Communication**: Agents collaborate for complex multi-step workflows
7. **Observability**: OpenTelemetry tracks all interactions for monitoring and evaluation



## Requirements 📋
To successfully complete this hackathon, you will need the following:

- GitHub account to access the repository and run GitHub Codespaces and Github Copilot. 
- Be familiar with Python programming, including handling JSON data and making API calls.​ 
- Be familiar with Generative AI Solutions and Azure  Services. 
- An active Azure subscription, with Owner rights. 
- Ability to provision resources in **Sweden Central** or [another supported region](https://learn.microsoft.com/en-us/azure/ai-foundry/openai/concepts/models?tabs=global-standard%2Cstandard-chat-completions#global-standard-model-availability). 

## Challenges 🚩

### 🎯 Challenge Roadmap

| Challenge | Title | Description | Duration |
|-----------|-------|-------------|----------|
| **00** 🏗️ | **[Setup & Data Ingestion](challenge-0/readme.md)** | Set up your development environment, deploy Azure resources (APIM Basic v2), configure environment variables, and ingest sample data using fraud-api | ⏱️ **30 mins** |
| **01** 🤖 | **[Microsoft Agent Framework](challenge-1/readme.md)** | Learn the Agent Framework, create 2 core agents, build a 3rd auditing agent, implement sequential orchestration, and create sequential workflows | ⏱️ **60 mins** |
| **02** 🔗 | **[Connect to Alert MCP Server](challenge-2/readme.md)** | Step-by-step connection to your Alert MCP, deploy Container App with OpenAPI, expose as MCP Server, and integrate with orchestration using GitHub Copilot | ⏱️ **60 mins** |
| **03** 🤝 | **[Agent-to-Agent Communication](challenge-3/readme.md)** | Implement A2A (Agent-to-Agent) communication by calling the Report Agent through the A2A Server for advanced multi-agent interactions | ⏱️ **60 mins** |
| **04** ✅ | **[Responsible AI & Observability](challenge-4/readme.md)** | Implement Responsible AI practices, OpenTelemetry monitoring, GitHub Actions evaluation, and full integration with Log Analytics | ⏱️ **60 mins** |