
import json
import os
from contextlib import closing
from typing import Any

import psycopg2
from psycopg2 import sql
from dotenv import load_dotenv


load_dotenv()


class DatabaseUtil:
    """
    PostgreSQL database utility.

    Features:
    - Environment-based database configuration
    - Managed database connections
    - Database schema inspection
    - Structured database metadata
    - Live table row counts
    - Optional sample data retrieval
    - Read-only SQL query execution
    - Query timeout
    - Maximum result row limit
    """

    def __init__(self, db_config: dict[str, Any]):
        self.db_config = db_config

    # ---------------------------------------------------------
    # DATABASE CONFIGURATION
    # ---------------------------------------------------------

    @classmethod
    def from_env(cls):
        """
        Load PostgreSQL configuration from environment variables.
        """

        required_variables = [
            "DB_HOST",
            "DB_USER",
            "DB_PASSWORD",
            "DB_NAME",
        ]

        missing_variables = [
            variable
            for variable in required_variables
            if not os.getenv(variable)
        ]

        if missing_variables:
            raise ValueError(
                "Missing database environment variables: "
                + ", ".join(missing_variables)
            )

        db_config = {
            "host": os.getenv("DB_HOST"),
            "port": int(os.getenv("DB_PORT", "5432")),
            "user": os.getenv("DB_USER"),
            "password": os.getenv("DB_PASSWORD"),
            "dbname": os.getenv("DB_NAME"),
            "connect_timeout": 10,
            "application_name": "AI_Data_Agent",
        }

        sslmode = os.getenv("DB_SSLMODE")

        if sslmode:
            db_config["sslmode"] = sslmode

        return cls(db_config)

    # ---------------------------------------------------------
    # DATABASE CONNECTION
    # ---------------------------------------------------------

    def _connect(self, read_only: bool = True):
        """
        Create a new database connection.

        Connections are opened for individual operations
        and closed automatically after execution.
        """

        connection = psycopg2.connect(**self.db_config)

        connection.set_session(
            readonly=read_only,
            autocommit=False,
        )

        return connection

    # ---------------------------------------------------------
    # SCHEMA DETAILS
    # ---------------------------------------------------------

    def schema_details(
        self,
        schema_name: str = "public",
        include_samples: bool = False,
    ) -> str:
        """
        Retrieve database tables, columns, and data types.

        Sample records are optional to avoid unnecessarily
        exposing database contents to the LLM.
        """

        schema_information = [
            f"Database Schema: {schema_name}"
        ]

        try:
            with closing(self._connect()) as connection:

                with connection.cursor() as cursor:

                    cursor.execute(
                        """
                        SELECT table_name
                        FROM information_schema.tables
                        WHERE table_schema = %s
                          AND table_type = 'BASE TABLE'
                        ORDER BY table_name;
                        """,
                        (schema_name,),
                    )

                    tables = cursor.fetchall()

                    if not tables:
                        return (
                            f"No tables found in schema: {schema_name}"
                        )

                    for (table_name,) in tables:

                        schema_information.append(
                            f"\nTable: {table_name}"
                        )

                        cursor.execute(
                            """
                            SELECT column_name, data_type
                            FROM information_schema.columns
                            WHERE table_schema = %s
                              AND table_name = %s
                            ORDER BY ordinal_position;
                            """,
                            (schema_name, table_name),
                        )

                        columns = cursor.fetchall()

                        for column_name, data_type in columns:

                            schema_information.append(
                                f"  Column: {column_name}, "
                                f"Data Type: {data_type}"
                            )

                        if include_samples:

                            sample_query = sql.SQL(
                                "SELECT * FROM {}.{} LIMIT 3"
                            ).format(
                                sql.Identifier(schema_name),
                                sql.Identifier(table_name),
                            )

                            cursor.execute(sample_query)

                            sample_rows = cursor.fetchall()

                            schema_information.append(
                                "  Sample Data:"
                            )

                            for row in sample_rows:
                                schema_information.append(
                                    f"    {row}"
                                )

            return "\n".join(schema_information)

        except psycopg2.Error as error:

            raise RuntimeError(
                f"Unable to retrieve database schema: {error}"
            ) from error

    # ---------------------------------------------------------
    # STRUCTURED DATABASE METADATA
    # ---------------------------------------------------------

    def get_database_metadata(
        self,
        schema_name: str = "public",
    ) -> dict[str, Any]:
        """
        Retrieve structured database metadata for the frontend.

        Returns:
        - Database name
        - Schema name
        - Table names
        - Column names
        - PostgreSQL data types
        - Nullable information
        - Exact live row counts
        - Total tables and records

        This method only reads database information.
        """

        metadata = {
            "database": None,
            "schema": schema_name,
            "status": "connected",
            "tables": [],
            "total_tables": 0,
            "total_records": 0,
        }

        try:

            with closing(self._connect()) as connection:

                with connection.cursor() as cursor:

                    # Get database name.
                    cursor.execute(
                        "SELECT current_database();"
                    )

                    metadata["database"] = cursor.fetchone()[0]

                    # Retrieve all base tables.
                    cursor.execute(
                        """
                        SELECT table_name
                        FROM information_schema.tables
                        WHERE table_schema = %s
                          AND table_type = 'BASE TABLE'
                        ORDER BY table_name;
                        """,
                        (schema_name,),
                    )

                    tables = cursor.fetchall()

                    for (table_name,) in tables:

                        # Retrieve column information.
                        cursor.execute(
                            """
                            SELECT
                                column_name,
                                data_type,
                                is_nullable
                            FROM information_schema.columns
                            WHERE table_schema = %s
                              AND table_name = %s
                            ORDER BY ordinal_position;
                            """,
                            (schema_name, table_name),
                        )

                        columns = cursor.fetchall()

                        column_details = [
                            {
                                "name": column_name,
                                "data_type": data_type,
                                "nullable": is_nullable == "YES",
                            }
                            for (
                                column_name,
                                data_type,
                                is_nullable,
                            ) in columns
                        ]

                        # Safely count rows using quoted identifiers.
                        count_query = sql.SQL(
                            "SELECT COUNT(*) FROM {}.{}"
                        ).format(
                            sql.Identifier(schema_name),
                            sql.Identifier(table_name),
                        )

                        cursor.execute(count_query)

                        row_count = cursor.fetchone()[0]

                        table_metadata = {
                            "name": table_name,
                            "row_count": row_count,
                            "columns": column_details,
                            "column_count": len(column_details),
                        }

                        metadata["tables"].append(
                            table_metadata
                        )

                        metadata["total_records"] += row_count

                    metadata["total_tables"] = len(
                        metadata["tables"]
                    )

            return metadata

        except psycopg2.Error as error:

            raise RuntimeError(
                f"Unable to retrieve database metadata: {error}"
            ) from error

    # ---------------------------------------------------------
    # SQL VALIDATION
    # ---------------------------------------------------------

    @staticmethod
    def _validate_read_only_query(query: str) -> str:
        """
        Basic SQL statement validation.

        PostgreSQL read-only transaction provides an additional
        database-level protection.
        """

        if not isinstance(query, str) or not query.strip():

            raise ValueError(
                "SQL query cannot be empty."
            )

        query = query.strip()

        # Remove one optional trailing semicolon.
        if query.endswith(";"):
            query = query[:-1].rstrip()

        # Reject multiple SQL statements.
        if ";" in query:

            raise ValueError(
                "Multiple SQL statements are not allowed."
            )

        first_keyword = query.split(None, 1)[0].upper()

        if first_keyword not in {"SELECT", "WITH"}:

            raise ValueError(
                "Only SELECT and WITH queries are permitted."
            )

        return query

    # ---------------------------------------------------------
    # SQL EXECUTION
    # ---------------------------------------------------------

    def execute_sql(
        self,
        query: str,
        max_rows: int = 100,
        timeout_ms: int = 10000,
    ) -> str:
        """
        Execute a read-only SQL query.

        Protections:
        - SELECT and WITH statement policy
        - Read-only PostgreSQL transaction
        - Query execution timeout
        - Maximum returned rows
        - No database modification commits
        """

        if (
            not isinstance(max_rows, int)
            or isinstance(max_rows, bool)
            or not 1 <= max_rows <= 1000
        ):

            raise ValueError(
                "max_rows must be an integer between 1 and 1000."
            )

        if (
            not isinstance(timeout_ms, int)
            or isinstance(timeout_ms, bool)
            or not 100 <= timeout_ms <= 60000
        ):

            raise ValueError(
                "timeout_ms must be an integer between 100 and 60000."
            )

        safe_query = self._validate_read_only_query(query)

        try:

            with closing(self._connect()) as connection:

                with connection.cursor() as cursor:

                    # Set query timeout.
                    cursor.execute(
                        "SET LOCAL statement_timeout = %s",
                        (timeout_ms,),
                    )

                    # Execute the validated query.
                    cursor.execute(safe_query, ())

                    if cursor.description is None:

                        raise ValueError(
                            "The query did not return a result set."
                        )

                    column_names = [
                        description[0]
                        for description in cursor.description
                    ]

                    # Fetch one additional row to detect truncation.
                    rows = cursor.fetchmany(max_rows + 1)

                    truncated = len(rows) > max_rows

                    rows = rows[:max_rows]

                    result = {
                        "columns": column_names,
                        "rows": [
                            list(row)
                            for row in rows
                        ],
                        "row_count": len(rows),
                        "truncated": truncated,
                    }

                    return json.dumps(
                        result,
                        default=str,
                        indent=2,
                    )

        except (ValueError, psycopg2.Error):
            raise

        except Exception as error:

            raise RuntimeError(
                f"SQL execution failed: {error}"
            ) from error


# ---------------------------------------------------------
# LOCAL TESTING
# ---------------------------------------------------------

if __name__ == "__main__":

    try:

        database = DatabaseUtil.from_env()

        # Test 1: Schema details.
        print("\nDATABASE SCHEMA")
        print("-" * 50)

        schema = database.schema_details(
            schema_name="public",
            include_samples=False,
        )

        print(schema)

        # Test 2: Database connection.
        print("\nDATABASE QUERY TEST")
        print("-" * 50)

        result = database.execute_sql(
            "SELECT current_database(), current_user"
        )

        print(result)

        # Test 3: Live structured metadata.
        print("\nLIVE DATABASE METADATA")
        print("-" * 50)

        metadata = database.get_database_metadata(
            schema_name="public"
        )

        print(
            json.dumps(
                metadata,
                indent=2,
                default=str,
            )
        )

        # Test 4: Display summary.
        print("\nDATABASE SUMMARY")
        print("-" * 50)

        print(
            f"Database: {metadata['database']}"
        )

        print(
            f"Total Tables: {metadata['total_tables']}"
        )

        print(
            f"Total Records: {metadata['total_records']}"
        )

        for table in metadata["tables"]:

            print(
                f"{table['name']}: "
                f"{table['row_count']} records, "
                f"{table['column_count']} columns"
            )

    except Exception as error:

        print(f"Database test failed: {error}")
