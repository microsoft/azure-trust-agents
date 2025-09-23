# Challenge 1: Document Processing and Vectorized Search

**Expected Duration:** 60 minutes

## Introduction
This challenge guides you through building a compliance automation system using Azure AI Agent Service and Semantic Kernel. You will create and orchestrate three specialized agents to parse regulations, score transaction risks, and generate audit trails—enabling transparent, real-time compliance for financial institutions.

## What are we building?
In this challenge, we will create 3 specialized agents that form the backbone of our compliance automation and banking AI agent ecosystem:

| Agent                        | Goal                                                      | Datasource                                                                 | Tool                        |
|------------------------------|-----------------------------------------------------------|----------------------------------------------------------------------------|-----------------------------|
| Regulation Parsing Agent     | Extract enforceable rules from regulations and policies    | Regulatory documents, bank policies                                        | Cosmos DB, Azure AI Search |
| Transaction Risk Scoring Agent | Score transactions for risk and compliance in real time   | Live transaction data, rules from Cosmos DB                                | Cosmos DB                 |
| Audit Trail & Explanation Agent | Generate transparent, regulator-ready case files          | Alerts, risk scores, rules from Cosmos DB, citations from AI Search        | Cosmos DB, Azure AI Search |



## Exercise Guide 

### Part 1 - Creation of your Agents


