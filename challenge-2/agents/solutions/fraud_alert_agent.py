import os
from agent_framework import ChatAgent, MCPStreamableHTTPTool
from agent_framework.azure import AzureOpenAIChatClient
from azure.identity import AzureCliCredential
import asyncio
import logging
import json

from dotenv import load_dotenv

load_dotenv(override=True)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Enable specific loggers for MCP debugging
logging.getLogger("agent_framework").setLevel(logging.DEBUG)
logging.getLogger("aiohttp.client").setLevel(logging.DEBUG)
logging.getLogger("urllib3.connectionpool").setLevel(logging.DEBUG)

logger = logging.getLogger(__name__)

# Configuration
aoai_endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT")
model_deployment_name = os.environ.get("MODEL_DEPLOYMENT_NAME")
mcp_endpoint = os.environ.get("MCP_SERVER_ENDPOINT")
mcp_subscription_key = os.environ.get("APIM_SUBSCRIPTION_KEY")


async def send_fraud_alert() -> None:
    """Main function to create and test the Simple Alert Agent."""

    try:
        # Create agent with Azure Chat Client
        agent = AzureOpenAIChatClient(
            credential=AzureCliCredential(),
            endpoint=aoai_endpoint,
            deployment_name=model_deployment_name
        ).create_agent(
            name="FraudAlertAgent",
            instructions="""
    You are a helpful agent that can use MCP tools to assist users. 
    Use the available MCP tools to answer questions and perform tasks.

    If you need to send a fraud alert, consider the following enumerations before building the json message:
    - severity (LOW, MEDIUM, HIGH, CRITICAL),
    - status (OPEN, INVESTIGATING, RESOLVED, FALSE_POSITIVE),
    - decision action (ALLOW, BLOCK, MONITOR, INVESTIGATE).

    An example json message to send is: 
    {
      "AlertDto": {
        "alertId": "ALERT_TX2002_20251018",
        "severity": "LOW",
        "status": "OPEN",
        "riskScore": 10,
        "createdAt": "2025-10-18T14:30:00.000000",
        "updatedAt": "2025-10-18T14:30:00.000000",
        "assignedTo": "compliance_monitoring_team",
        "customer": {
          "customerId": "CUST1005",
          "name": "David Sancho",
          "country": "ES",
          "deviceTrustScore": 0.8,
          "hasFraudHistory": false
        },
        "transaction": {
          "transactionId": "TX2002",
          "amount": 9998,
          "currency": "EUR",
          "destinationCountry": "DE",
          "timestamp": "2025-10-16T14:38:48"
        },
        "riskFactors": [
          "Transaction near high amount threshold",
          "Cross-border transaction",
          "Routine monitoring required"
        ],
        "decision": {
          "action": "MONITOR",
          "reasoning": "Low risk transaction that is compliant with AML/KYC regulations. Transaction amount is just below $10,000 threshold. Customer has good standing with no fraud history and high device trust score. Destination country (Germany) is low-risk. Recommended for approval with standard monitoring."
        },
        "notes": [
          "Transaction is compliant and low risk",
          "Amount just below reporting threshold",
          "Customer has clean history",
          "Standard monitoring recommended"
        ]
      }
    }

    Send the alert using the MCP tool without asking for further confirmation.
    If any field is missing, make reasonable assumptions to fill in the required fields.

    """,
            tools=MCPStreamableHTTPTool(
              name="Fraud alert manager MCP",
              url=mcp_endpoint,
              load_prompts=False,
              headers={
                  "Ocp-Apim-Subscription-Key": mcp_subscription_key
              },
            ),
        )

        # Read transaction summary from file
        with open("risk-analyzer-tx-summary.md", "r") as f:
            content = f.read()

        query = f"Please send a fraud alert from this transaction summary: {content}"

        print(f"User: {query}")
        print("Agent: ", end="", flush=True)

        async for chunk in agent.run_stream(query):
            if chunk.text:
                print(chunk.text, end="", flush=True)

        print("\n")
    except Exception as e:
        logger.error(f"An error occurred during the streaming example: {e}")


async def main() -> None:
    await send_fraud_alert()


if __name__ == "__main__":
    asyncio.run(main())
