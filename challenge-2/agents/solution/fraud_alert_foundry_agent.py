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
mcp_tool = McpTool(
    server_label="fraudalertmcp",  # Label of the MCP server to use
    server_url=mcp_endpoint,
)
mcp_tool.update_headers("Ocp-Apim-Subscription-Key",
                        mcp_subscription_key)

# Create agent with MCP tool and process agent run
with project_client:
    agents_client = project_client.agents

    # Create a new agent.
    # NOTE: To reuse existing agent, fetch it with get_agent(agent_id)
    agent = agents_client.create_agent(
        model=model_deployment_name,
        name="fraud-alert-agent",
        instructions="""
You are a Fraud Alert Management Agent that specializes in creating and managing fraud alerts for financial transactions.

Your responsibilities include:
- Analyzing risk assessment results to determine if fraud alerts are needed
- Creating appropriate fraud alerts using the MCP tool with correct severity and status
- Determining proper decision actions (ALLOW, BLOCK, MONITOR, INVESTIGATE)
- Providing clear reasoning for alert decisions

When creating fraud alerts, use these enumerations:
- severity (LOW, MEDIUM, HIGH, CRITICAL)
- status (OPEN, INVESTIGATING, RESOLVED, FALSE_POSITIVE)
- decision action (ALLOW, BLOCK, MONITOR, INVESTIGATE)

Create fraud alerts for transactions that meet any of these criteria:
1. High risk scores (>= 75)
2. Sanctions-related concerns
3. High-risk jurisdictions
4. Suspicious patterns or anomalies
5. Regulatory compliance violations

Always create comprehensive alerts with proper risk factor documentation and clear reasoning.
Send alerts using the MCP tool without asking for further confirmation.
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
