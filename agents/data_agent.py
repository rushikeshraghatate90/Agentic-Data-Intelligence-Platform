
import os
import sys

sys.path.append(
    os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
)

from langchain_core.messages import (
    AIMessage,
    HumanMessage,
    SystemMessage,
)

from langgraph.graph import StateGraph, START, END

from Models.schema import DataAgentSchema, RouterSchema
from utils.llm_pick import pick_llm

from agents.etl_analyst import etl_analyst
from agents.sql_analyst import sql_analyst


# ==================================================
# LLM CONFIGURATION
# ==================================================

llm = pick_llm("claude")
llm_router = llm.with_structured_output(RouterSchema)


# ==================================================
# HELPER FUNCTIONS
# ==================================================

def get_user_message(state: DataAgentSchema) -> str:
    """Retrieve the latest user message."""

    messages = state.messages

    if not messages:
        raise ValueError("No messages found in the conversation.")

    for message in reversed(messages):
        if isinstance(message, HumanMessage):
            return str(message.content)

    raise ValueError("No user message found in the conversation.")


def get_final_etl_response(messages: list) -> str:
    """Extract only the final user-facing ETL response."""

    for message in reversed(messages):

        if not isinstance(message, AIMessage):
            continue

        content = message.content

        if not isinstance(content, str) or not content.strip():
            continue

        if getattr(message, "tool_calls", None):
            continue

        if message.additional_kwargs.get("tool_calls"):
            continue

        return content.strip()

    return "The ETL agent completed without returning a final response."


def build_execution_trace(route: str) -> list:
    """Build a structured record of the agent workflow."""

    specialist = (
        "SQL Analyst" if route == "sql" else "ETL Analyst"
    )

    return [
        {
            "step": 1,
            "agent": "Main Data Agent",
            "action": "Received and analyzed the user's request.",
            "status": "completed",
        },
        {
            "step": 2,
            "agent": "Router",
            "action": f"Classified the request and selected the {route.upper()} route.",
            "status": "completed",
        },
        {
            "step": 3,
            "agent": specialist,
            "action": (
                "Generated, validated, and executed a database query."
                if route == "sql"
                else "Executed the data extraction and transformation workflow."
            ),
            "status": "completed",
        },
        {
            "step": 4,
            "agent": "Main Data Agent",
            "action": "Received the specialist's result and prepared the final response.",
            "status": "completed",
        },
    ]


# ==================================================
# DATA AGENT NODES
# ==================================================

def router_node(state: DataAgentSchema):
    """Classify the user's request as SQL or ETL."""

    user_message = get_user_message(state)

    system_prompt = """
    You are an intelligent data agent router.

    Classify the user's request into exactly one category:

    1. SQL
    2. ETL

    Choose SQL when the user wants to:
    - Retrieve information from an existing database.
    - Ask questions about database records.
    - Filter, sort, group, or aggregate database data.
    - Calculate totals, averages, counts, or statistics.
    - Perform joins between database tables.
    - Generate reports using existing database records.

    Choose ETL when the user wants to:
    - Extract data from CSV, JSON, Parquet, or APIs.
    - Load external data into files.
    - Transform datasets.
    - Clean or preprocess datasets.
    - Select, rename, filter, or remove columns.
    - Handle missing values or duplicate records.
    - Perform extraction, transformation, and loading.

    Important:
    - Classify according to the user's actual intention.
    - Do not execute the task.
    - Do not generate SQL queries.
    - Do not perform transformations.
    - Return only the structured classification.
    """

    response = llm_router.invoke([
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_message),
    ])

    route = response.answer.lower().strip()

    if route not in {"sql", "etl"}:
        raise ValueError(f"Invalid agent route: {route}")

    return {
        "route_response": route,
    }


def etl_node(state: DataAgentSchema):
    """Execute the ETL Analyst agent."""

    user_message = get_user_message(state)

    response = etl_analyst.invoke({
        "messages": [
            HumanMessage(content=user_message)
        ]
    })

    generated_messages = (
        response.get("messages", [])
        if isinstance(response, dict)
        else [response]
    )

    final_response = get_final_etl_response(
        generated_messages
    )

    trace = build_execution_trace("etl")

    assistant_message = AIMessage(
        content=final_response,
        additional_kwargs={
            "selected_agent": "ETL Analyst",
            "agent_trace": trace,
            "data_source": "User-provided file or external data source",
        },
    )

    return {
        "messages": [assistant_message]
    }


def sql_node(state: DataAgentSchema):
    """Execute the SQL Analyst agent."""

    user_message = get_user_message(state)

    input_schema = {
        "messages": [],
        "user_question": user_message,
        "curated_ques": "",
        "prompt_query_context": "",
        "generated_sql_query": "",
        "is_safe": "No",
        "comments": "",
        "sql_query_execution_result": "",
        "final_answer": "",
    }

    response = sql_analyst.invoke(input_schema)

    if isinstance(response, dict):

        final_answer = response.get("final_answer", "")

        metadata = {
            "generated_sql_query": response.get(
                "generated_sql_query", ""
            ),
            "is_safe": response.get(
                "is_safe", "No"
            ),
            "comments": response.get(
                "comments", ""
            ),
            "sql_query_execution_result": response.get(
                "sql_query_execution_result", ""
            ),
        }

    else:

        final_answer = getattr(
            response, "final_answer", ""
        )

        metadata = {
            "generated_sql_query": getattr(
                response, "generated_sql_query", ""
            ),
            "is_safe": getattr(
                response, "is_safe", "No"
            ),
            "comments": getattr(
                response, "comments", ""
            ),
            "sql_query_execution_result": getattr(
                response, "sql_query_execution_result", ""
            ),
        }

    # Attach execution trace to the final response.
    metadata.update({
        "selected_agent": "SQL Analyst",
        "agent_trace": build_execution_trace("sql"),
        "data_source": "Supabase PostgreSQL",
    })

    assistant_message = AIMessage(
        content=str(
            final_answer or "The SQL agent did not return an answer."
        ),
        additional_kwargs=metadata,
    )

    return {
        "messages": [assistant_message]
    }


# ==================================================
# ROUTING LOGIC
# ==================================================

def route_edge(state: DataAgentSchema) -> str:
    """Route the request to the selected agent."""

    route = state.route_response.lower()

    if route == "sql":
        return "sql_node"

    if route == "etl":
        return "etl_node"

    raise ValueError(
        f"Unsupported route response: {route}"
    )


# ==================================================
# LANGGRAPH CONSTRUCTION
# ==================================================

data_agent_graph = StateGraph(DataAgentSchema)

data_agent_graph.add_node("router_node", router_node)
data_agent_graph.add_node("sql_node", sql_node)
data_agent_graph.add_node("etl_node", etl_node)

data_agent_graph.add_edge(START, "router_node")

data_agent_graph.add_conditional_edges(
    "router_node",
    route_edge,
    {
        "sql_node": "sql_node",
        "etl_node": "etl_node",
    },
)

data_agent_graph.add_edge("sql_node", END)
data_agent_graph.add_edge("etl_node", END)

data_agent = data_agent_graph.compile()


# ==================================================
# LOCAL TESTING
# ==================================================

if __name__ == "__main__":

    test_queries = [
        "Show me the top 5 cities by number of users.",
        (
            "Extract the first 20 Pokémon from "
            "https://pokeapi.co/api/v2/pokemon?limit=20 "
            "and save the results as a CSV file "
            "in data/extract/."
        ),
    ]

    for query in test_queries:

        print("\n" + "=" * 60)
        print("USER QUERY")
        print("=" * 60)
        print(query)

        response = data_agent.invoke({
            "messages": [
                HumanMessage(content=query)
            ],
            "route_response": "",
        })

        route = response["route_response"].upper()

        print("\nSELECTED ROUTE")
        print("=" * 60)
        print(route)

        print("\nAGENT RESPONSE")
        print("=" * 60)

        for message in reversed(response["messages"]):

            if isinstance(message, AIMessage):

                print(message.content)

                metadata = message.additional_kwargs

                print("\nEXECUTION TRACE")
                print("=" * 60)

                for step in metadata.get("agent_trace", []):
                    print(
                        f'{step["step"]}. '
                        f'{step["agent"]}: '
                        f'{step["action"]} '
                        f'[{step["status"]}]'
                    )

                print("\nSELECTED AGENT:")
                print(metadata.get("selected_agent"))

                print("\nDATA SOURCE:")
                print(metadata.get("data_source"))

                if route == "SQL":

                    print("\nSQL METADATA:")
                    for key in [
                        "generated_sql_query",
                        "is_safe",
                        "comments",
                        "sql_query_execution_result",
                    ]:
                        print(f"{key}: {metadata.get(key)}")

                break

        print("\n")
