
import os
import sys
import re
import json

sys.path.append(
    os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
)

from utils.llm_pick import pick_llm
from utils.database import DatabaseUtil
from Models.schema import AgentSchema

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.graph import StateGraph, START, END


# ==========================================================
# SQL VALIDATION
# ==========================================================

BLOCKED_SQL_KEYWORDS = {
    "INSERT",
    "UPDATE",
    "DELETE",
    "DROP",
    "ALTER",
    "TRUNCATE",
    "CREATE",
    "REPLACE",
    "GRANT",
    "REVOKE",
    "EXECUTE",
    "CALL",
    "DO",
    "COPY",
    "VACUUM",
    "ANALYZE",
    "REFRESH",
    "REINDEX",
    "CLUSTER",
    "COMMENT",
    "SECURITY",
    "INTO",
}


DANGEROUS_POSTGRES_FUNCTIONS = {
    "PG_SLEEP",
    "SET_CONFIG",
    "NEXTVAL",
    "SETVAL",
    "LO_IMPORT",
    "LO_EXPORT",
}


def validate_sql_query(query: str) -> tuple[bool, str, str]:
    """
    Validate generated SQL before execution.

    Returns:
        (is_safe, message, validated_query)

    Note:
        This is a conservative regex-based validation layer.
        It is not a substitute for a read-only database role
        or database-level security controls.
    """

    if not query or not query.strip():
        return False, "The generated SQL query is empty.", ""

    query = query.strip()

    # Remove Markdown SQL code fences.
    query = re.sub(
        r"^```(?:sql)?\s*",
        "",
        query,
        flags=re.IGNORECASE,
    )

    query = re.sub(
        r"\s*```$",
        "",
        query,
    ).strip()

    # Allow one optional trailing semicolon.
    if query.endswith(";"):
        query = query[:-1].strip()

    # Reject multiple SQL statements.
    if ";" in query:
        return (
            False,
            "Multiple SQL statements are not allowed.",
            "",
        )

    # Reject SQL comments.
    if "--" in query or "/*" in query or "*/" in query:
        return (
            False,
            "SQL comments are not allowed.",
            "",
        )

    # Only SELECT and WITH queries are accepted.
    if not re.match(
        r"^(SELECT|WITH)\b",
        query,
        flags=re.IGNORECASE,
    ):
        return (
            False,
            "Only SELECT and WITH queries are permitted.",
            "",
        )

    # Check blocked SQL keywords.
    words = set(
        re.findall(r"\b[A-Za-z_]+\b", query.upper())
    )

    blocked = words.intersection(BLOCKED_SQL_KEYWORDS)

    if blocked:
        return (
            False,
            (
                "Blocked SQL operation detected: "
                f"{', '.join(sorted(blocked))}."
            ),
            "",
        )

    # Reject row-locking clauses.
    if re.search(
        r"\bFOR\s+(UPDATE|SHARE|NO\s+KEY\s+UPDATE|KEY\s+SHARE)\b",
        query,
        flags=re.IGNORECASE,
    ):
        return (
            False,
            "Row-locking queries are not permitted.",
            "",
        )

    # Reject potentially dangerous PostgreSQL functions.
    for function in DANGEROUS_POSTGRES_FUNCTIONS:
        if re.search(
            rf"\b{function}\s*\(",
            query,
            flags=re.IGNORECASE,
        ):
            return (
                False,
                f"Unsafe PostgreSQL function detected: {function}.",
                "",
            )

    # Apply default row limit if one is not specified.
    if not re.search(
        r"\bLIMIT\b",
        query,
        flags=re.IGNORECASE,
    ):
        query += "\nLIMIT 10"

    return (
        True,
        "SQL query passed validation.",
        query,
    )


# ==========================================================
# AI AGENT NODES
# ==========================================================


def curate_ques(state: AgentSchema):
    """
    Clarify the user's database question without changing
    its original business intent.
    """

    user_question = state.user_question

    llm = pick_llm("low")

    prompt = f"""
    You are a database question clarification assistant.

    Rewrite the user's question to make it clear and precise.

    RULES:

    1. Preserve the original meaning and business intent.
    2. Do not invent business definitions.
    3. Do not add filters that the user did not request.
    4. Do not change the requested aggregation.
    5. Preserve requested numbers, dates, and conditions.
    6. If the question is already clear, keep it unchanged.
    7. Do not answer the question.
    8. Return only the rewritten question.

    USER QUESTION:
    {user_question}
    """

    response = llm.invoke(prompt).content

    curated_question = str(response).strip()

    return {
        "curated_ques": curated_question,
        "messages": [
            HumanMessage(content=curated_question)
        ],
    }


def prompt_query_context(state: AgentSchema):
    """
    Build the SQL-generation prompt using the actual
    database schema and business definitions.
    """

    curated_question = state.curated_ques

    db = DatabaseUtil.from_env()

    schema_info = db.schema_details("public")

    prompt = f"""
    You are an expert PostgreSQL SQL analyst working
    with a ride-sharing analytics database.

    Your responsibility is to translate natural-language
    questions into accurate PostgreSQL SELECT queries.

    DATABASE SCHEMA:
    {schema_info}

    ==================================================
    DATABASE RELATIONSHIPS
    ==================================================

    1. users.user_id = rides.rider_id

       Connects a ride to its rider.

    2. users.user_id = rides.driver_id

       Can connect a ride to a driver when the corresponding
       users record represents a driver.

       Check users.user_type when driver-specific user
       information is required.

    3. rides.ride_id = payments.ride_id

       Connects rides with their payment records.

    4. rides.ride_id = ratings.ride_id

       Connects rides with their rating records.

    5. rides.driver_id = ratings.driver_id

       Connects ride records and driver ratings.

    6. vehicles.driver_id = rides.driver_id

       Connects vehicles to drivers.

    ==================================================
    BUSINESS DEFINITIONS
    ==================================================

    1. Completed rides:

       Use rides.status = 'completed'.

    2. Driver average rating:

       Use AVG(ratings.rating), grouped by
       ratings.driver_id.

    3. Driver rating count:

       Use COUNT(*) on rating records.

    4. Completed ride count:

       Count rides where rides.status = 'completed'.

    5. Completed ride fare:

       Use SUM(rides.fare) for completed rides.

    6. Payment amount:

       Use payments.amount.

    7. Successfully collected payment amount:

       Use SUM(payments.amount) where
       payments.payment_status = 'completed'.

    8. Rider city:

       Join users to rides using
       users.user_id = rides.rider_id.

       This represents the rider's registered city,
       not necessarily the geographic location of the ride.

    9. Driver identification:

       Use rides.driver_id for driver identifiers.

       Do not assume every user is a driver.

    10. Valid payment status values:

        The actual values in payments.payment_status are:
        'completed', 'failed', and 'refunded'.

        Never invent or use 'successful' as a payment status.

    11. Completed payments:

        A successfully collected payment means a payment row
        where payments.payment_status = 'completed'.

    12. Failed and refunded payments:

        Do not classify failed or refunded payments as
        successfully collected payments. A ride can have a
        payment record without having a completed payment.

    13. Rides without completed payments:

        When counting completed rides without a completed
        payment, check whether a matching completed payment
        exists for each ride. Do not check only whether any
        payment record exists. Use COUNT(DISTINCT rides.ride_id)
        when the requested metric is a distinct ride count.

    ==================================================
    SQL GENERATION RULES
    ==================================================

    1. Generate only SELECT or WITH queries.

    2. Never generate INSERT, UPDATE, DELETE, DROP,
       ALTER, TRUNCATE, CREATE, or other modifying
       operations.

    3. Use only tables and columns in the provided schema.

    4. Use valid PostgreSQL syntax.

    5. Never invent table names or column names.

    6. Use appropriate JOIN conditions.

    7. Avoid unnecessary joins.

    8. Use GROUP BY for aggregate queries.

    9. Use HAVING when filtering aggregated values.

    10. Use WHERE when filtering individual records.

    11. Use DISTINCT when unique values are requested.

    12. Avoid duplicate counting when joining tables.

    13. When joining one-to-many relationships, aggregate
        the many-side records before joining when necessary
        to avoid inflating totals.

    14. For payment-to-ride financial calculations, aggregate
        payment rows by ride_id before joining when multiple
        payment rows could otherwise duplicate ride-level values.

    15. Do not confuse ride fares with collected payments.

    16. Do not include failed or refunded payments in
        successfully collected payment totals.

    17. When counting distinct rides, use
        COUNT(DISTINCT rides.ride_id).

    18. When finding rides without a completed payment, use
        a LEFT JOIN to completed payments aggregated by ride_id,
        then identify unmatched rides. A failed or refunded
        payment is not a completed payment.

    19. Use ORDER BY for ranking requests.

    20. Add deterministic secondary sorting when useful.

    21. Use LIMIT 10 unless the user requests another
        number of records.

    22. Avoid SELECT * unless explicitly requested.

    23. Use ROUND() when the user requests rounded
        monetary values or averages.

    24. Use appropriate aliases for calculated columns.

    25. Do not invent missing business information.

    26. If the requested metric is ambiguous, choose
        only an interpretation supported by the question
        and database schema. Do not silently claim that
        an assumption is a verified business definition.

    ==================================================
    OUTPUT RULES
    ==================================================

    Return only one PostgreSQL SQL query.

    Do not include:
    - Markdown code fences.
    - Explanations.
    - Comments.
    - Multiple alternative queries.

    USER QUESTION:
    {curated_question}

    Generate the PostgreSQL query now.
    """

    return {
        "prompt_query_context": prompt,
    }


def generate_sql(state: AgentSchema):
    """
    Generate SQL using the medium Groq model.
    """

    prompt = state.prompt_query_context

    llm = pick_llm("medium")

    response = llm.invoke(prompt).content

    generated_query = str(response).strip()

    return {
        "generated_sql_query": generated_query,
    }


def is_safe_sql(state: AgentSchema):
    """
    Validate generated SQL before database execution.
    """

    sql_query = state.generated_sql_query

    is_safe, message, validated_query = validate_sql_query(
        sql_query
    )

    if is_safe:
        return {
            "is_safe": "Yes",
            "comments": message,
            "generated_sql_query": validated_query,
        }

    return {
        "is_safe": "No",
        "comments": message,
    }


def canceled_sql(state: AgentSchema):
    """
    Stop execution when SQL validation fails.
    """

    final_answer = (
        "The generated SQL query was not executed because "
        f"it failed validation. Reason: {state.comments}"
    )

    return {
        "final_answer": final_answer,
        "sql_query_execution_result": json.dumps({
            "status": "validation_failed",
            "message": state.comments,
        }),
        "messages": [
            AIMessage(content=final_answer)
        ],
    }


def execute_sql(state: AgentSchema):
    """
    Execute the validated SQL query against Supabase.
    """

    sql_query = state.generated_sql_query

    try:
        db = DatabaseUtil.from_env()

        execution_result = db.execute_sql(
            sql_query,
            max_rows=100,
            timeout_ms=10000,
        )

        if isinstance(execution_result, (dict, list)):
            execution_result = json.dumps(
                execution_result,
                indent=2,
                default=str,
            )
        else:
            execution_result = str(execution_result)

        result = {
            "status": "success",
            "data": execution_result,
        }

    except Exception as error:
        result = {
            "status": "execution_failed",
            "error": str(error),
        }

    return {
        "sql_query_execution_result": json.dumps(
            result,
            indent=2,
            default=str,
        ),
    }


def represent_final_answer(state: AgentSchema):
    """
    Convert database results into a concise user-facing
    answer without inventing values.
    """

    execution_result = state.sql_query_execution_result

    curated_question = state.curated_ques

    try:
        result_data = json.loads(execution_result)
    except (json.JSONDecodeError, TypeError):
        result_data = {
            "status": "success",
            "data": execution_result,
        }

    # Handle SQL execution failures without asking the LLM
    # to interpret an error as a successful result.
    if result_data.get("status") == "execution_failed":

        error_message = result_data.get(
            "error",
            "Unknown database error.",
        )

        final_answer = (
            "The SQL query could not be executed. "
            f"Database error: {error_message}"
        )

        return {
            "final_answer": final_answer,
            "messages": [
                AIMessage(content=final_answer)
            ],
        }

    # Handle validation failures.
    if result_data.get("status") == "validation_failed":

        final_answer = (
            "The SQL query was rejected during validation "
            "and was not executed."
        )

        return {
            "final_answer": final_answer,
            "messages": [
                AIMessage(content=final_answer)
            ],
        }

    llm = pick_llm("low")

    prompt = f"""
    You are a helpful and accurate SQL data analyst.

    Answer the user's question using only the database
    execution result provided below.

    USER QUESTION:
    {curated_question}

    DATABASE EXECUTION RESULT:
    {result_data.get("data", "")}

    INSTRUCTIONS:

    1. Use only actual values from the database result.

    2. Never invent numbers, records, or database details.

    3. If the result is empty, clearly explain that
       no matching records were found.

    4. If the result contains an error, do not pretend
       that the query succeeded.

    5. Present tabular results in a readable Markdown table
       when appropriate.

    6. Format monetary values consistently to two
       decimal places when appropriate.

    7. Format averages to two decimal places when
       appropriate.

    8. Preserve the meaning and units of the original data.

    9. Do not change the sorting or ranking of results.

    10. Do not display SQL code unless the user asks for it.

    11. Give a concise and clear answer.

    Provide the final answer.
    """

    try:
        response = llm.invoke(prompt).content
        final_answer = str(response).strip()

    except Exception as error:
        final_answer = (
            "The SQL query executed, but the final answer "
            f"could not be formatted: {error}"
        )

    return {
        "final_answer": final_answer,
        "messages": [
            AIMessage(content=final_answer)
        ],
    }


# ==========================================================
# LANGGRAPH WORKFLOW
# ==========================================================

sql_agent_graph = StateGraph(AgentSchema)


# Register nodes.
sql_agent_graph.add_node(
    "curate_ques",
    curate_ques,
)

sql_agent_graph.add_node(
    "prompt_query_context",
    prompt_query_context,
)

sql_agent_graph.add_node(
    "generate_sql",
    generate_sql,
)

sql_agent_graph.add_node(
    "is_safe_sql",
    is_safe_sql,
)

sql_agent_graph.add_node(
    "canceled_sql",
    canceled_sql,
)

sql_agent_graph.add_node(
    "execute_sql",
    execute_sql,
)

sql_agent_graph.add_node(
    "represent_final_answer",
    represent_final_answer,
)


# Register workflow edges.
sql_agent_graph.add_edge(
    START,
    "curate_ques",
)

sql_agent_graph.add_edge(
    "curate_ques",
    "prompt_query_context",
)

sql_agent_graph.add_edge(
    "prompt_query_context",
    "generate_sql",
)

sql_agent_graph.add_edge(
    "generate_sql",
    "is_safe_sql",
)


# Conditional routing.
def is_safe_sql_edge(state: AgentSchema):

    if state.is_safe == "Yes":
        return "execute_sql"

    return "canceled_sql"


sql_agent_graph.add_conditional_edges(
    "is_safe_sql",
    is_safe_sql_edge,
    {
        "execute_sql": "execute_sql",
        "canceled_sql": "canceled_sql",
    },
)


# Finish paths.
sql_agent_graph.add_edge(
    "canceled_sql",
    END,
)

sql_agent_graph.add_edge(
    "execute_sql",
    "represent_final_answer",
)

sql_agent_graph.add_edge(
    "represent_final_answer",
    END,
)


# Compile the graph.
sql_analyst = sql_agent_graph.compile()


# ==========================================================
# LOCAL TESTING
# ==========================================================

if __name__ == "__main__":

    input_schema = {
        "messages": [],
        "user_question": (
            "Show the top 5 drivers by average rating. "
            "Include driver ID, average rating, and "
            "total number of ratings. "
            "Sort by average rating in descending order."
        ),
        "curated_ques": "",
        "prompt_query_context": "",
        "generated_sql_query": "",
        "is_safe": "No",
        "comments": "",
        "sql_query_execution_result": "",
        "final_answer": "",
    }

    print("\nStarting SQL Analyst Agent...\n")

    response = sql_agent_graph.compile().invoke(
        input_schema
    )

    print("\nCURATED QUESTION")
    print("=" * 60)
    print(response.get("curated_ques", ""))

    print("\nGENERATED SQL")
    print("=" * 60)
    print(response.get("generated_sql_query", ""))

    print("\nSQL VALIDATION")
    print("=" * 60)
    print("Safe:", response.get("is_safe", "No"))
    print("Comments:", response.get("comments", ""))

    print("\nEXECUTION RESULT")
    print("=" * 60)
    print(
        response.get(
            "sql_query_execution_result",
            "",
        )
    )

    print("\nFINAL ANSWER")
    print("=" * 60)
    print(response.get("final_answer", ""))
