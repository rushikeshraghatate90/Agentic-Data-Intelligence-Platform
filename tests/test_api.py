
import pytest

from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage, HumanMessage

from api import main


@pytest.fixture
def client():
    return TestClient(main.app)


@pytest.fixture
def output_directories(tmp_path, monkeypatch):
    """Use isolated temporary directories for generated files."""
    extract_dir = tmp_path / "extract"
    transform_dir = tmp_path / "transform"

    extract_dir.mkdir()
    transform_dir.mkdir()

    directories = {
        "extract": extract_dir,
        "transform": transform_dir,
    }

    monkeypatch.setattr(
        main,
        "OUTPUT_DIRECTORIES",
        directories,
    )

    return directories


# =========================================================
# ROOT AND HEALTH ENDPOINTS
# =========================================================

def test_root_endpoint(client):
    response = client.get("/")

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "running"
    assert data["message"] == "Welcome to AI Data Agent API"
    assert data["version"] == "1.3.0"
    assert data["docs"] == "/docs"

    assert "health" in data["endpoints"]
    assert "ask" in data["endpoints"]
    assert "metadata" in data["endpoints"]
    assert "files" in data["endpoints"]


def test_health_endpoint(client):
    response = client.get("/health")

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "healthy"
    assert data["service"] == "AI Data Agent"

    assert "Main Data Agent" in data["agents"]
    assert "SQL Analyst" in data["agents"]
    assert "ETL Analyst" in data["agents"]


# =========================================================
# DATABASE METADATA ENDPOINT
# =========================================================

def test_metadata_endpoint_success(client, monkeypatch):
    expected_metadata = {
        "schema": "public",
        "tables": ["users", "rides", "payments"],
    }

    class MockDatabase:
        def get_database_metadata(self, schema_name):
            assert schema_name == "public"
            return expected_metadata

    monkeypatch.setattr(
        main.DatabaseUtil,
        "from_env",
        lambda: MockDatabase(),
    )

    response = client.get("/metadata")

    assert response.status_code == 200
    assert response.json() == expected_metadata


def test_metadata_endpoint_handles_configuration_error(
    client,
    monkeypatch,
):
    def raise_configuration_error():
        raise ValueError("Database configuration is invalid")

    monkeypatch.setattr(
        main.DatabaseUtil,
        "from_env",
        raise_configuration_error,
    )

    response = client.get("/metadata")

    assert response.status_code == 500
    assert "Database configuration is invalid" in response.json()["detail"]


def test_metadata_endpoint_handles_database_unavailable(
    client,
    monkeypatch,
):
    class MockDatabase:
        def get_database_metadata(self, schema_name):
            raise RuntimeError("Database unavailable")

    monkeypatch.setattr(
        main.DatabaseUtil,
        "from_env",
        lambda: MockDatabase(),
    )

    response = client.get("/metadata")

    assert response.status_code == 503
    assert response.json()["detail"] == (
        "Unable to retrieve database metadata."
    )


def test_metadata_endpoint_handles_unexpected_error(
    client,
    monkeypatch,
):
    def raise_unexpected_error():
        raise Exception("Unexpected failure")

    monkeypatch.setattr(
        main.DatabaseUtil,
        "from_env",
        raise_unexpected_error,
    )

    response = client.get("/metadata")

    assert response.status_code == 500
    assert response.json()["detail"] == (
        "An unexpected error occurred while retrieving metadata."
    )


# =========================================================
# GENERATED FILE LIST ENDPOINT
# =========================================================

def test_files_endpoint_lists_generated_csv_files(
    client,
    output_directories,
):
    extract_file = (
        output_directories["extract"] / "extracted_data.csv"
    )
    transform_file = (
        output_directories["transform"] / "transformed_data.csv"
    )

    extract_file.write_text(
        "name,age\nAlice,25\n",
        encoding="utf-8",
    )

    transform_file.write_text(
        "name,age\nBob,30\n",
        encoding="utf-8",
    )

    response = client.get("/files")

    assert response.status_code == 200

    data = response.json()

    assert data["total_files"] == 2

    file_ids = {
        item["file_id"]
        for item in data["files"]
    }

    assert "extract__extracted_data.csv" in file_ids
    assert "transform__transformed_data.csv" in file_ids


def test_files_endpoint_returns_empty_list(
    client,
    output_directories,
):
    response = client.get("/files")

    assert response.status_code == 200
    assert response.json() == {
        "total_files": 0,
        "files": [],
    }


def test_files_endpoint_ignores_non_csv_files(
    client,
    output_directories,
):
    directory = output_directories["extract"]

    (directory / "data.csv").write_text(
        "id\n1\n",
        encoding="utf-8",
    )

    (directory / "data.json").write_text(
        '{"id": 1}',
        encoding="utf-8",
    )

    response = client.get("/files")

    assert response.status_code == 200
    assert response.json()["total_files"] == 1
    assert response.json()["files"][0]["filename"] == "data.csv"


# =========================================================
# GENERATED FILE DOWNLOAD ENDPOINT
# =========================================================

def test_download_extracted_csv(
    client,
    output_directories,
):
    file_path = (
        output_directories["extract"] / "extracted_data.csv"
    )

    expected_content = "name,age\nAlice,25\n"

    file_path.write_text(
        expected_content,
        encoding="utf-8",
    )

    response = client.get(
        "/files/download/extract__extracted_data.csv"
    )

    assert response.status_code == 200

    # Normalize Windows CRLF and Unix LF line endings.
    actual_content = response.text.replace("\r\n", "\n")

    assert actual_content == expected_content
    assert response.headers["content-type"].startswith("text/csv")
    assert (
        "extracted_data.csv"
        in response.headers["content-disposition"]
    )


def test_download_transformed_csv(
    client,
    output_directories,
):
    file_path = (
        output_directories["transform"] / "transformed_data.csv"
    )

    expected_content = "name,age\nBob,30\n"

    file_path.write_text(
        expected_content,
        encoding="utf-8",
    )

    response = client.get(
        "/files/download/transform__transformed_data.csv"
    )

    assert response.status_code == 200

    # Normalize Windows CRLF and Unix LF line endings.
    actual_content = response.text.replace("\r\n", "\n")

    assert actual_content == expected_content
    assert response.headers["content-type"].startswith("text/csv")
    assert (
        "transformed_data.csv"
        in response.headers["content-disposition"]
    )


@pytest.mark.parametrize(
    "file_id",
    [
        "invalid.csv",
        "unknown__data.csv",
        "extract__missing.csv",
        "extract__data.json",
        "../outside.csv",
        "extract__../outside.csv",
        "extract__..",
        "",
    ],
)
def test_download_rejects_invalid_file_ids(
    client,
    output_directories,
    file_id,
):
    response = client.get(
        f"/files/download/{file_id}"
    )

    assert response.status_code == 404


# =========================================================
# DATA AGENT ENDPOINT
# =========================================================

def test_ask_endpoint_success(client, monkeypatch):
    question = "Show me the top five cities by user count."

    agent_message = AIMessage(
        content="Toronto has the highest user count.",
        additional_kwargs={
            "selected_agent": "SQL Analyst",
            "data_source": "Supabase PostgreSQL",
            "agent_trace": [
                {"step": "SQL generation"},
                {"step": "SQL execution"},
            ],
            "generated_sql_query": "SELECT city FROM users LIMIT 5",
            "is_safe": True,
        },
    )

    def mock_invoke(payload):
        messages = payload["messages"]

        assert isinstance(messages[0], HumanMessage)
        assert messages[0].content == question
        assert payload["route_response"] == ""

        return {
            "messages": [
                messages[0],
                agent_message,
            ],
            "route_response": "sql_analyst",
        }

    monkeypatch.setattr(
        main.data_agent,
        "invoke",
        mock_invoke,
    )

    response = client.post(
        "/ask",
        json={"question": question},
    )

    assert response.status_code == 200

    data = response.json()

    assert data["question"] == question
    assert data["route"] == "sql_analyst"
    assert data["selected_agent"] == "SQL Analyst"
    assert data["data_source"] == "Supabase PostgreSQL"

    assert data["answer"] == "Toronto has the highest user count."

    assert len(data["agent_trace"]) == 2

    assert data["metadata"]["is_safe"] is True
    assert "generated_sql_query" in data["metadata"]


def test_ask_endpoint_handles_missing_agent_message(
    client,
    monkeypatch,
):
    def mock_invoke(payload):
        return {
            "messages": payload["messages"],
            "route_response": "sql_analyst",
        }

    monkeypatch.setattr(
        main.data_agent,
        "invoke",
        mock_invoke,
    )

    response = client.post(
        "/ask",
        json={"question": "Show all users"},
    )

    assert response.status_code == 500
    assert (
        "did not return an assistant message"
        in response.json()["detail"]
    )


def test_ask_endpoint_handles_agent_exception(
    client,
    monkeypatch,
):
    def mock_invoke(payload):
        raise RuntimeError("Agent service unavailable")

    monkeypatch.setattr(
        main.data_agent,
        "invoke",
        mock_invoke,
    )

    response = client.post(
        "/ask",
        json={"question": "Show all users"},
    )

    assert response.status_code == 500
    assert "Agent execution failed" in response.json()["detail"]
    assert "Agent service unavailable" in response.json()["detail"]


def test_ask_endpoint_handles_empty_agent_answer(
    client,
    monkeypatch,
):
    agent_message = AIMessage(
        content="   ",
        additional_kwargs={},
    )

    monkeypatch.setattr(
        main.data_agent,
        "invoke",
        lambda payload: {
            "messages": [
                payload["messages"][0],
                agent_message,
            ],
            "route_response": "unknown",
        },
    )

    response = client.post(
        "/ask",
        json={"question": "Show all users"},
    )

    assert response.status_code == 200

    data = response.json()

    assert data["answer"] == (
        "The agent completed without returning an answer."
    )

    assert data["selected_agent"] == "Unknown"
    assert data["data_source"] == "Not specified"


# =========================================================
# REQUEST VALIDATION
# =========================================================

@pytest.mark.parametrize(
    "question",
    [
        "",
        "Hi",
        "a" * 2001,
    ],
)
def test_ask_endpoint_rejects_invalid_questions(
    client,
    question,
):
    response = client.post(
        "/ask",
        json={"question": question},
    )

    assert response.status_code == 422


def test_ask_endpoint_rejects_missing_question(client):
    response = client.post(
        "/ask",
        json={},
    )

    assert response.status_code == 422


def test_ask_endpoint_rejects_non_string_question(client):
    response = client.post(
        "/ask",
        json={"question": 12345},
    )

    assert response.status_code == 422
