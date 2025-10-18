# Import necessary libraries

import os
import time
from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential
from azure.ai.agents.models import (
    ListSortOrder,
    McpTool,
    RequiredMcpToolCall,
    RunStepActivityDetails,
    SubmitToolApprovalAction,
    ToolApproval,
)
from dotenv import load_dotenv

load_dotenv(override=True)

project_endpoint = os.environ.get("AI_FOUNDRY_PROJECT_ENDPOINT")
model_deployment_name = os.environ.get("MODEL_DEPLOYMENT_NAME")
mcp_endpoint = os.environ.get("MCP_SERVER_ENDPOINT")
mcp_subscription_key = os.environ.get("APIM_SUBSCRIPTION_KEY")

project_client = AIProjectClient(
    endpoint=project_endpoint,
    credential=DefaultAzureCredential(),
)
# Initialize agent MCP tool
mcp_tool = < PLACEHOLDER FOR MCP TOOL >

# Create agent with MCP tool and process agent run
with project_client:
    agents_client = project_client.agents

    # Create a new agent.
    # NOTE: To reuse existing agent, fetch it with get_agent(agent_id)
    agent = agents_client.create_agent(
        model=model_deployment_name,
        name="fraud-alert-agent",
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
        tools=mcp_tool.definitions,
    )

    print(f"Created agent, ID: {agent.id}")
    print(f"MCP Server at {mcp_tool.server_url}")

    # Create thread for communication
    thread = agents_client.threads.create()
    print(f"Created thread, ID: {thread.id}")

    # Create message to thread
    # read content from file risk-analyzer-tx-summary
    with open("risk-analyzer-tx-summary.md", "r") as f:
        content = f.read()
    message = agents_client.messages.create(
        thread_id=thread.id,
        role="user",
        content=f"Please send a fraud alert from this transaction summary: {content}",
    )
    print(f"Created message, ID: {message.id}")
    # mcp_tool.set_approval_mode("never")  # Uncomment to disable approval requirement
    run = agents_client.runs.create(
        thread_id=thread.id, agent_id=agent.id, tool_resources=mcp_tool.resources)
    print(f"Created run, ID: {run.id}")

    while run.status in ["queued", "in_progress", "requires_action"]:
        time.sleep(1)
        run = agents_client.runs.get(thread_id=thread.id, run_id=run.id)

        if run.status == "requires_action" and isinstance(run.required_action, SubmitToolApprovalAction):
            tool_calls = run.required_action.submit_tool_approval.tool_calls
            if not tool_calls:
                print("No tool calls provided - cancelling run")
                agents_client.runs.cancel(thread_id=thread.id, run_id=run.id)
                break

            tool_approvals = []
            for tool_call in tool_calls:
                if isinstance(tool_call, RequiredMcpToolCall):
                    try:
                        print(f"Approving tool call: {tool_call}")
                        tool_approvals.append(
                            ToolApproval(
                                tool_call_id=tool_call.id,
                                approve=True,
                                headers=mcp_tool.headers,
                            )
                        )
                    except Exception as e:
                        print(f"Error approving tool_call {tool_call.id}: {e}")

            print(f"tool_approvals: {tool_approvals}")
            if tool_approvals:
                agents_client.runs.submit_tool_outputs(
                    thread_id=thread.id, run_id=run.id, tool_approvals=tool_approvals
                )

        print(f"Current run status: {run.status}")

    print(f"Run completed with status: {run.status}")
    if run.status == "failed":
        print(f"Run failed: {run.last_error}")

    # Display run steps and tool calls
    run_steps = agents_client.run_steps.list(
        thread_id=thread.id, run_id=run.id)

    # Loop through each step
    for step in run_steps:
        print(f"Step {step['id']} status: {step['status']}")

        # Check if there are tool calls in the step details
        step_details = step.get("step_details", {})
        tool_calls = step_details.get("tool_calls", [])

        if tool_calls:
            print("  MCP Tool calls:")
            for call in tool_calls:
                print(f"    Tool Call ID: {call.get('id')}")
                print(f"    Type: {call.get('type')}")

        if isinstance(step_details, RunStepActivityDetails):
            for activity in step_details.activities:
                for function_name, function_definition in activity.tools.items():
                    print(
                        f'  The function {function_name} with description "{function_definition.description}" will be called.:'
                    )
                    if len(function_definition.parameters) > 0:
                        print("  Function parameters:")
                        for argument, func_argument in function_definition.parameters.properties.items():
                            print(f"      {argument}")
                            print(f"      Type: {func_argument.type}")
                            print(
                                f"      Description: {func_argument.description}")
                    else:
                        print("This function has no parameters")

        print()  # add an extra newline between steps

    # Fetch and log all messages
    messages = agents_client.messages.list(
        thread_id=thread.id, order=ListSortOrder.ASCENDING)
    print("\nConversation:")
    print("-" * 50)
    for msg in messages:
        if msg.text_messages:
            last_text = msg.text_messages[-1]
            print(f"{msg.role.upper()}: {last_text.text.value}")
            print("-" * 50)

    # Clean-up and delete the agent once the run is finished.
    # NOTE: Comment out this line if you plan to reuse the agent later.
    # agents_client.delete_agent(agent.id)
    # print("Deleted agent")
