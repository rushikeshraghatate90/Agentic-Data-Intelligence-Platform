
import json
import os
from contextlib import closing
from pathlib import Path
from typing import Any

import psycopg2
from dotenv import load_dotenv
from psycopg2 import sql


class DatabaseUtil:
    """
    PostgreSQL database utility.

    Features:
    - Explicit environment configuration
    - Project-root .env loading
    - Managed PostgreSQL connections
    - Database schema inspection
    - Structured database metadata
    - Live table row counts
    - Optional sample data retrieval
    - Read-only SQL execution
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
        Load PostgreSQL configuration.

        Local:
            Loads .env from the project root.
            The project .env takes priority.

        Production:
            Uses environment variables configured by the host
            when no project .env file exists.
        """

        project_root = Path(__file__).resolve().parent.parent
        env_file = project_root / ".env"

        if env_file.is_file():
            load_dotenv(
                dotenv_path=env_file,
                override=True,
            )

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

        try:
            port = int(os.getenv("DB_PORT", "5432"))
        except ValueError as error:
            raise ValueError(
                "DB_PORT must be a valid integer."
            ) from error

        if not 1 <= port <= 65535:
            raise ValueError(
                "DB_PORT must be between 1 and 65535."
            )

        db_config = {
            "host": os.getenv("DB_HOST", "").strip(),
            "port": port,
            "user": os.getenv("DB_USER", "").strip(),
            "password": os.getenv("DB_PASSWORD"),
            "dbname": os.getenv("DB_NAME", "").strip(),
            "connect_timeout": 10,
            "application_name": "AI_Data_Agent",
            "sslmode": os.getenv("DB_SSLMODE", "require").strip(),
        }

        return cls(db_config)

    # ---------------------------------------------------------
    # DATABASE CONNECTION
    # ---------------------------------------------------------

    def _connect(self, read_only: bool = True):
        """
        Create a PostgreSQL connection.

        read_only=True:
            Prevents database modifications.

        read_only=False:
            Allows controlled ETL write operations.
        """

        connection = psycopg2.connect(**self.db_config)

        try:
            connection.set_session(
                readonly=read_only,
                autocommit=False,
            )

            return connection

        except Exception:
            connection.close()
            raise

    # ---------------------------------------------------------
    # DATABASE CONNECTION TEST
    # ---------------------------------------------------------

    def test_connection(self) -> dict[str, Any]:
        """Verify authentication and basic database connectivity."""

        try:
            with closing(self._connect()) as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        SELECT
                            current_database(),
                            current_user,
                            version();
                        """
                    )

                    database, user, version = cursor.fetchone()

            return {
                "success": True,
                "database": database,
                "user": user,
                "server_version": version,
            }

        except psycopg2.Error as error:
            raise RuntimeError(
                f"Database connection failed: {error}"
            ) from error

    # ---------------------------------------------------------
    # SCHEMA DETAILS
    # ---------------------------------------------------------

    def schema_details(
        self,
        schema_name: str = "public",
        include_samples: bool = False,
    ) -> str:
        """Retrieve database tables, columns and data types."""

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

                            schema_information.append("  Sample Data:")

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
        """Retrieve structured database metadata."""

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

                    cursor.execute(
                        "SELECT current_database();"
                    )

                    metadata["database"] = cursor.fetchone()[0]

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

                        metadata["tables"].append(table_metadata)
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
        Validate read-only SQL.

        PostgreSQL read-only transactions provide an additional
        database-level protection.
        """

        if not isinstance(query, str) or not query.strip():
            raise ValueError("SQL query cannot be empty.")

        query = query.strip()

        if query.endswith(";"):
            query = query[:-1].rstrip()

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
        - Query timeout
        - Maximum returned rows
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

                    cursor.execute(
                        "SET LOCAL statement_timeout = %s",
                        (timeout_ms,),
                    )

                    cursor.execute(safe_query)

                    if cursor.description is None:
                        raise ValueError(
                            "The query did not return a result set."
                        )

                    column_names = [
                        description[0]
                        for description in cursor.description
                    ]

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

        print("\nDATABASE CONNECTION TEST")
        print("-" * 50)

        connection_result = database.test_connection()
        print(json.dumps(connection_result, indent=2))

        print("\nDATABASE SCHEMA")
        print("-" * 50)

        print(
            database.schema_details(
                schema_name="public",
                include_samples=False,
            )
        )

        print("\nDATABASE QUERY TEST")
        print("-" * 50)

        result = database.execute_sql(
            "SELECT current_database(), current_user"
        )

        print(result)

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

        print("\nDATABASE SUMMARY")
        print("-" * 50)

        print(f"Database: {metadata['database']}")
        print(f"Total Tables: {metadata['total_tables']}")
        print(f"Total Records: {metadata['total_records']}")

        for table in metadata["tables"]:
            print(
                f"{table['name']}: "
                f"{table['row_count']} records, "
                f"{table['column_count']} columns"
            )

    except Exception as error:
        print(f"Database test failed: {error}")
