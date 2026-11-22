
import importlib
from types import SimpleNamespace

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage


data_agent_module = importlib.import_module("agents.data_agent")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_state():
    return SimpleNamespace(
        messages=[
            HumanMessage(content="Show me the top five cities.")
        ],
        route_response="",
    )


# ---------------------------------------------------------------------------
# get_user_message()
# ---------------------------------------------------------------------------

def test_get_user_message_returns_latest_user_message():
    state = SimpleNamespace(
        messages=[
            HumanMessage(content="First question"),
            AIMessage(content="First answer"),
            HumanMessage(content="Latest question"),
        ]
    )

    result = data_agent_module.get_user_message(state)

    assert result == "Latest question"


def test_get_user_message_rejects_empty_messages():
    state = SimpleNamespace(messages=[])

    with pytest.raises(ValueError, match="No messages found"):
        data_agent_module.get_user_message(state)


def test_get_user_message_rejects_missing_human_message():
    state = SimpleNamespace(
        messages=[
            AIMessage(content="Assistant response")
        ]
    )

    with pytest.raises(ValueError, match="No user message found"):
        data_agent_module.get_user_message(state)


# ---------------------------------------------------------------------------
# get_final_etl_response()
# ---------------------------------------------------------------------------

def test_get_final_etl_response_returns_final_answer():
    messages = [
        AIMessage(content="Intermediate response"),
        AIMessage(content="Final ETL result"),
    ]

    result = data_agent_module.get_final_etl_response(messages)

    assert result == "Final ETL result"


def test_get_final_etl_response_ignores_empty_messages():
    messages = [
        AIMessage(content=""),
        AIMessage(content="   "),
        AIMessage(content="Valid final answer"),
    ]

    result = data_agent_module.get_final_etl_response(messages)

    assert result == "Valid final answer"


def test_get_final_etl_response_ignores_tool_call_messages():
    messages = [
        AIMessage(
            content="Intermediate tool response",
            additional_kwargs={
                "tool_calls": [
                    {"id": "test-call"}
                ]
            },
        ),
        AIMessage(content="Final response"),
    ]

    result = data_agent_module.get_final_etl_response(messages)

    assert result == "Final response"


def test_get_final_etl_response_handles_no_final_response():
    messages = [
        HumanMessage(content="Extract data"),
        AIMessage(content=""),
    ]

    result = data_agent_module.get_final_etl_response(messages)

    assert result == (
        "The ETL agent completed without returning a final response."
    )


# ---------------------------------------------------------------------------
# build_execution_trace()
# ---------------------------------------------------------------------------

def test_sql_execution_trace():
    trace = data_agent_module.build_execution_trace("sql")

    assert len(trace) == 4
    assert trace[0]["agent"] == "Main Data Agent"
    assert trace[1]["agent"] == "Router"
    assert trace[2]["agent"] == "SQL Analyst"
    assert trace[3]["agent"] == "Main Data Agent"

    assert all(step["status"] == "completed" for step in trace)


def test_etl_execution_trace():
    trace = data_agent_module.build_execution_trace("etl")

    assert len(trace) == 4
    assert trace[0]["agent"] == "Main Data Agent"
    assert trace[1]["agent"] == "Router"
    assert trace[2]["agent"] == "ETL Analyst"
    assert trace[3]["agent"] == "Main Data Agent"

    assert all(step["status"] == "completed" for step in trace)


# ---------------------------------------------------------------------------
# router_node()
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("route", ["sql", "etl"])
def test_router_node_returns_valid_route(
    sample_state,
    monkeypatch,
    route,
):
    def mock_invoke(messages):
        assert isinstance(messages[0], SystemMessage)
        assert isinstance(messages[1], HumanMessage)

        return SimpleNamespace(answer=route.upper())

    # Replace the module-level router instead of modifying
    # the LangChain RunnableSequence's invoke method.
    monkeypatch.setattr(
        data_agent_module,
        "llm_router",
        SimpleNamespace(invoke=mock_invoke),
    )

    result = data_agent_module.router_node(sample_state)

    assert result == {"route_response": route}


def test_router_node_rejects_invalid_route(
    sample_state,
    monkeypatch,
):
    monkeypatch.setattr(
        data_agent_module,
        "llm_router",
        SimpleNamespace(
            invoke=lambda messages: SimpleNamespace(
                answer="unknown"
            )
        ),
    )

    with pytest.raises(ValueError, match="Invalid agent route"):
        data_agent_module.router_node(sample_state)


def test_router_node_rejects_empty_user_messages(
    monkeypatch,
):
    state = SimpleNamespace(messages=[])

    result = SimpleNamespace(answer="sql")

    monkeypatch.setattr(
        data_agent_module,
        "llm_router",
        SimpleNamespace(
            invoke=lambda messages: result
        ),
    )

    with pytest.raises(ValueError, match="No messages found"):
        data_agent_module.router_node(state)


# ---------------------------------------------------------------------------
# route_edge()
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    ("route", "expected_node"),
    [
        ("sql", "sql_node"),
        ("etl", "etl_node"),
        ("SQL", "sql_node"),
        ("ETL", "etl_node"),
    ],
)
def test_route_edge_selects_correct_node(
    route,
    expected_node,
):
    state = SimpleNamespace(route_response=route)

    result = data_agent_module.route_edge(state)

    assert result == expected_node


def test_route_edge_rejects_unsupported_route():
    state = SimpleNamespace(route_response="unknown")

    with pytest.raises(
        ValueError,
        match="Unsupported route response",
    ):
        data_agent_module.route_edge(state)


# ---------------------------------------------------------------------------
# etl_node()
# ---------------------------------------------------------------------------

def test_etl_node_returns_formatted_assistant_message(
    sample_state,
    monkeypatch,
):
    mock_response = {
        "messages": [
            AIMessage(content="ETL processing completed.")
        ]
    }

    monkeypatch.setattr(
        data_agent_module,
        "etl_analyst",
        SimpleNamespace(
            invoke=lambda inputs: mock_response
        ),
    )

    result = data_agent_module.etl_node(sample_state)

    assert len(result["messages"]) == 1

    message = result["messages"][0]

    assert isinstance(message, AIMessage)
    assert message.content == "ETL processing completed."
    assert message.additional_kwargs["selected_agent"] == "ETL Analyst"
    assert message.additional_kwargs["data_source"] == (
        "User-provided file or external data source"
    )
    assert len(message.additional_kwargs["agent_trace"]) == 4


def test_etl_node_handles_missing_final_response(
    sample_state,
    monkeypatch,
):
    mock_response = {
        "messages": [
            AIMessage(content="")
        ]
    }

    monkeypatch.setattr(
        data_agent_module,
        "etl_analyst",
        SimpleNamespace(
            invoke=lambda inputs: mock_response
        ),
    )

    result = data_agent_module.etl_node(sample_state)

    assert result["messages"][0].content == (
        "The ETL agent completed without returning a final response."
    )


def test_etl_node_handles_direct_ai_message_response(
    sample_state,
    monkeypatch,
):
    mock_response = AIMessage(
        content="Direct ETL response"
    )

    monkeypatch.setattr(
        data_agent_module,
        "etl_analyst",
        SimpleNamespace(
            invoke=lambda inputs: mock_response
        ),
    )

    result = data_agent_module.etl_node(sample_state)

    assert result["messages"][0].content == "Direct ETL response"
    assert result["messages"][0].additional_kwargs["selected_agent"] == (
        "ETL Analyst"
    )


# ---------------------------------------------------------------------------
# sql_node()
# ---------------------------------------------------------------------------

def test_sql_node_handles_dictionary_response(
    sample_state,
    monkeypatch,
):
    mock_response = {
        "final_answer": "There are five top cities.",
        "generated_sql_query": "SELECT city FROM users LIMIT 5",
        "is_safe": "Yes",
        "comments": "Query validated.",
        "sql_query_execution_result": '{"status": "success"}',
    }

    monkeypatch.setattr(
        data_agent_module,
        "sql_analyst",
        SimpleNamespace(
            invoke=lambda inputs: mock_response
        ),
    )

    result = data_agent_module.sql_node(sample_state)

    message = result["messages"][0]

    assert isinstance(message, AIMessage)
    assert message.content == "There are five top cities."
    assert message.additional_kwargs["selected_agent"] == "SQL Analyst"
    assert message.additional_kwargs["generated_sql_query"] == (
        "SELECT city FROM users LIMIT 5"
    )
    assert message.additional_kwargs["is_safe"] == "Yes"


def test_sql_node_handles_object_response(
    sample_state,
    monkeypatch,
):
    mock_response = SimpleNamespace(
        final_answer="SQL execution completed.",
        generated_sql_query="SELECT COUNT(*) FROM users LIMIT 10",
        is_safe="Yes",
        comments="Valid query.",
        sql_query_execution_result='{"status": "success"}',
    )

    monkeypatch.setattr(
        data_agent_module,
        "sql_analyst",
        SimpleNamespace(
            invoke=lambda inputs: mock_response
        ),
    )

    result = data_agent_module.sql_node(sample_state)

    message = result["messages"][0]

    assert message.content == "SQL execution completed."
    assert message.additional_kwargs["selected_agent"] == "SQL Analyst"
    assert message.additional_kwargs["is_safe"] == "Yes"


def test_sql_node_handles_missing_final_answer(
    sample_state,
    monkeypatch,
):
    mock_response = {
        "final_answer": "",
        "generated_sql_query": "",
        "is_safe": "No",
        "comments": "",
        "sql_query_execution_result": "",
    }

    monkeypatch.setattr(
        data_agent_module,
        "sql_analyst",
        SimpleNamespace(
            invoke=lambda inputs: mock_response
        ),
    )

    result = data_agent_module.sql_node(sample_state)

    assert result["messages"][0].content == (
        "The SQL agent did not return an answer."
    )


def test_sql_node_preserves_sql_execution_metadata(
    sample_state,
    monkeypatch,
):
    mock_response = {
        "final_answer": "Query completed.",
        "generated_sql_query": "SELECT * FROM users LIMIT 10",
        "is_safe": "Yes",
        "comments": "Validated successfully.",
        "sql_query_execution_result": (
            '{"status": "success", "data": []}'
        ),
    }

    monkeypatch.setattr(
        data_agent_module,
        "sql_analyst",
        SimpleNamespace(
            invoke=lambda inputs: mock_response
        ),
    )

    result = data_agent_module.sql_node(sample_state)

    metadata = result["messages"][0].additional_kwargs

    assert metadata["generated_sql_query"] == (
        "SELECT * FROM users LIMIT 10"
    )
    assert metadata["is_safe"] == "Yes"
    assert metadata["comments"] == "Validated successfully."
    assert metadata["sql_query_execution_result"] == (
        '{"status": "success", "data": []}'
    )
    assert metadata["data_source"] == "Supabase PostgreSQL"
    assert len(metadata["agent_trace"]) == 4


# ---------------------------------------------------------------------------
# Data Agent Graph
# ---------------------------------------------------------------------------

def test_data_agent_graph_is_compiled():
    assert data_agent_module.data_agent is not None
    assert callable(data_agent_module.data_agent.invoke)
