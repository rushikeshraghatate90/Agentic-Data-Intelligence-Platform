
import json
from types import SimpleNamespace

import pytest

from agents import sql_analyst


class MockDatabase:
    """Simulate database execution without connecting to Supabase."""

    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error

    def execute_sql(self, query, max_rows, timeout_ms):
        if self.error:
            raise self.error

        return self.result


def create_state(query="SELECT * FROM users LIMIT 5"):
    """Create a minimal state for the SQL execution node."""

    return SimpleNamespace(
        generated_sql_query=query
    )


def test_execute_sql_success_with_list(monkeypatch):
    expected_data = [
        {"city": "Toronto", "user_count": 100},
        {"city": "Montreal", "user_count": 90},
    ]

    mock_db = MockDatabase(result=expected_data)

    monkeypatch.setattr(
        sql_analyst.DatabaseUtil,
        "from_env",
        lambda: mock_db,
    )

    state = create_state()

    result = sql_analyst.execute_sql(state)

    response = json.loads(
        result["sql_query_execution_result"]
    )

    assert response["status"] == "success"

    returned_data = json.loads(response["data"])

    assert returned_data == expected_data


def test_execute_sql_success_with_dictionary(monkeypatch):
    expected_data = {
        "total_users": 1000,
        "active_users": 850,
    }

    mock_db = MockDatabase(result=expected_data)

    monkeypatch.setattr(
        sql_analyst.DatabaseUtil,
        "from_env",
        lambda: mock_db,
    )

    state = create_state()

    result = sql_analyst.execute_sql(state)

    response = json.loads(
        result["sql_query_execution_result"]
    )

    assert response["status"] == "success"

    returned_data = json.loads(response["data"])

    assert returned_data == expected_data


@pytest.mark.parametrize(
    "error",
    [
        ConnectionError("Database connection failed"),
        TimeoutError("Database query timed out"),
        RuntimeError("SQL execution failed"),
    ],
)
def test_execute_sql_handles_database_errors(monkeypatch, error):
    mock_db = MockDatabase(error=error)

    monkeypatch.setattr(
        sql_analyst.DatabaseUtil,
        "from_env",
        lambda: mock_db,
    )

    state = create_state()

    result = sql_analyst.execute_sql(state)

    response = json.loads(
        result["sql_query_execution_result"]
    )

    assert response["status"] == "execution_failed"
    assert response["error"] == str(error)


def test_execute_sql_handles_connection_initialization_error(
    monkeypatch,
):
    def raise_connection_error():
        raise ConnectionError("Unable to initialize database")

    monkeypatch.setattr(
        sql_analyst.DatabaseUtil,
        "from_env",
        raise_connection_error,
    )

    state = create_state()

    result = sql_analyst.execute_sql(state)

    response = json.loads(
        result["sql_query_execution_result"]
    )

    assert response["status"] == "execution_failed"
    assert "Unable to initialize database" in response["error"]


def test_execute_sql_passes_execution_parameters(monkeypatch):
    class ParameterCheckingDatabase:
        def execute_sql(self, query, max_rows, timeout_ms):
            assert query == "SELECT * FROM users LIMIT 5"
            assert max_rows == 100
            assert timeout_ms == 10000

            return [{"user_id": 1}]

    mock_db = ParameterCheckingDatabase()

    monkeypatch.setattr(
        sql_analyst.DatabaseUtil,
        "from_env",
        lambda: mock_db,
    )

    state = create_state()

    result = sql_analyst.execute_sql(state)

    response = json.loads(
        result["sql_query_execution_result"]
    )

    assert response["status"] == "success"
