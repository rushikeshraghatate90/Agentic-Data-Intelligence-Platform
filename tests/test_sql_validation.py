import pytest

from agents.sql_analyst import validate_sql_query


def test_valid_select_query():
    query = "SELECT * FROM users LIMIT 5"

    is_safe, message, validated_query = validate_sql_query(query)

    assert is_safe is True
    assert "passed validation" in message.lower()
    assert "LIMIT 5" in validated_query


def test_valid_with_query():
    query = """
    WITH user_counts AS (
        SELECT city, COUNT(*) AS total
        FROM users
        GROUP BY city
    )
    SELECT * FROM user_counts
    """

    is_safe, message, validated_query = validate_sql_query(query)

    assert is_safe is True
    assert "LIMIT 10" in validated_query


@pytest.mark.parametrize(
    "query",
    [
        "DELETE FROM users",
        "DROP TABLE users",
        "UPDATE users SET city = 'Pune'",
        "INSERT INTO users VALUES (1)",
        "TRUNCATE TABLE users",
        "ALTER TABLE users ADD COLUMN test TEXT",
    ],
)
def test_blocked_sql_operations(query):
    is_safe, message, validated_query = validate_sql_query(query)

    assert is_safe is False
    assert validated_query == ""


def test_multiple_statements_rejected():
    query = "SELECT * FROM users; DROP TABLE users"

    is_safe, message, validated_query = validate_sql_query(query)

    assert is_safe is False
    assert "multiple sql statements" in message.lower()
    assert validated_query == ""


def test_empty_query_rejected():
    is_safe, message, validated_query = validate_sql_query("")

    assert is_safe is False
    assert validated_query == ""


@pytest.mark.parametrize(
    "query",
    [
        "SELECT pg_sleep(10)",
        "SELECT nextval('my_sequence')",
        "SELECT set_config('search_path', 'public', false)",
    ],
)
def test_dangerous_postgres_functions_rejected(query):
    is_safe, message, validated_query = validate_sql_query(query)

    assert is_safe is False
    assert validated_query == ""


def test_default_limit_added():
    query = "SELECT city FROM users"

    is_safe, message, validated_query = validate_sql_query(query)

    assert is_safe is True
    assert "LIMIT 10" in validated_query


def test_existing_limit_preserved():
    query = "SELECT city FROM users LIMIT 5"

    is_safe, message, validated_query = validate_sql_query(query)

    assert is_safe is True
    assert "LIMIT 5" in validated_query
    assert "LIMIT 10" not in validated_query


def test_markdown_sql_fences_removed():
    query = """```sql
    SELECT city FROM users LIMIT 5
    ```"""

    is_safe, message, validated_query = validate_sql_query(query)

    assert is_safe is True
    assert "```" not in validated_query
