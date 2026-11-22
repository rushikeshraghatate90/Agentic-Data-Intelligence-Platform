
import io
import json
import logging
import os
import re
from contextlib import closing
from pathlib import Path
from typing import Any

import pandas as pd
import requests
from psycopg2 import sql
from psycopg2.extras import execute_values

from dotenv import load_dotenv
from supabase import Client, create_client

from utils.database import DatabaseUtil


logger = logging.getLogger(__name__)


class ETLTools:
    """
    ETL utilities for API, PostgreSQL and local file operations.

    EXTRACT:
        - External HTTP APIs
        - Supabase PostgreSQL tables

    TRANSFORM:
        - Validated Pandas transformations

    LOAD:
        - CSV, JSON and Parquet files
        - Existing Supabase PostgreSQL tables
    """

    SUPPORTED_FORMATS = {"csv", "json", "parquet"}

    ALLOWED_OPERATIONS = {
        "filter",
        "select_columns",
        "drop_columns",
        "rename_columns",
        "sort",
        "drop_duplicates",
        "fill_null",
    }

    MAX_EXTRACTION_ROWS = 10000
    MAX_PREVIEW_ROWS = 20
    MAX_UPLOAD_ROWS = 10000

    STORAGE_BUCKET = "etl-files"

    def __init__(self, storage_backend: str | None = None):
        # Load local .env values without overwriting variables supplied by Render.
        load_dotenv(self.project_root_env_path(), override=False)
        self.project_root = Path(__file__).resolve().parent.parent

        backend = storage_backend or os.getenv("ETL_STORAGE_BACKEND", "local")
        backend = backend.strip().lower()
        if backend not in {"local", "supabase"}:
            raise ValueError("ETL_STORAGE_BACKEND must be 'local' or 'supabase'.")

        self.storage_backend = backend
        self._supabase: Client | None = None

    @staticmethod
    def project_root_env_path() -> Path:
        """Return the project-root .env path without exposing its contents."""
        return Path(__file__).resolve().parent.parent / ".env"

    def _get_supabase_client(self) -> Client:
        """Create the Supabase client lazily, only when cloud storage is used."""
        if self._supabase is not None:
            return self._supabase

        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_SECRET_KEY")
        if not supabase_url or not supabase_key:
            raise RuntimeError(
                "Supabase Storage requires SUPABASE_URL and SUPABASE_SECRET_KEY."
            )

        self._supabase = create_client(supabase_url, supabase_key)
        return self._supabase

    def _storage_object_path(self, project_relative_path: str) -> str:
        """Validate and normalize a project-relative path for Storage."""
        resolved = self._resolve_project_path(project_relative_path)
        return resolved.relative_to(self.project_root).as_posix()

    @staticmethod
    def _serialize_dataframe(df: pd.DataFrame, output_format: str) -> bytes:
        """Serialize a DataFrame to bytes for a Supabase Storage upload."""
        buffer = io.BytesIO()
        if output_format == "csv":
            return df.to_csv(index=False).encode("utf-8")
        if output_format == "json":
            return df.to_json(
                orient="records", lines=True, date_format="iso"
            ).encode("utf-8")
        if output_format == "parquet":
            df.to_parquet(buffer, index=False)
            return buffer.getvalue()
        raise ValueError(f"Unsupported output format: {output_format}")

    @staticmethod
    def _dataframe_from_bytes(content: bytes, extension: str) -> pd.DataFrame:
        """Deserialize CSV, JSON or Parquet content downloaded from Storage."""
        buffer = io.BytesIO(content)
        if extension == ".csv":
            return pd.read_csv(buffer)
        if extension == ".json":
            try:
                return pd.read_json(buffer, lines=True)
            except ValueError:
                buffer.seek(0)
                return pd.read_json(buffer)
        if extension == ".parquet":
            return pd.read_parquet(buffer)
        raise ValueError(f"Unsupported input file format: {extension}")

    # ==============================================================
    # PATH VALIDATION
    # ==============================================================

    def _resolve_project_path(self, path: str) -> Path:
        """Resolve a project-relative path safely."""

        if not isinstance(path, str) or not path.strip():
            raise ValueError("A valid project-relative path is required.")

        resolved_path = (self.project_root / path).resolve()

        if not resolved_path.is_relative_to(self.project_root):
            raise ValueError(
                "Access outside the project directory is not allowed."
            )

        return resolved_path

    # ==============================================================
    # FILE FORMAT VALIDATION
    # ==============================================================

    def _validate_format(self, file_format: str) -> str:
        if not isinstance(file_format, str):
            raise ValueError("File format must be a string.")

        file_format = file_format.lower().strip()

        if file_format not in self.SUPPORTED_FORMATS:
            raise ValueError(
                f"Unsupported format: {file_format}. "
                f"Supported formats: {', '.join(sorted(self.SUPPORTED_FORMATS))}"
            )

        return file_format

    # ==============================================================
    # DATABASE IDENTIFIER VALIDATION
    # ==============================================================

    @staticmethod
    def _validate_identifier(identifier: str, name: str) -> str:
        """Validate PostgreSQL identifiers before using them."""

        if not isinstance(identifier, str):
            raise ValueError(f"{name} must be a string.")

        identifier = identifier.strip()

        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,62}", identifier):
            raise ValueError(f"Invalid PostgreSQL {name}: {identifier}")

        return identifier

    def _get_database_columns(
        self,
        database: DatabaseUtil,
        schema_name: str,
        table_name: str,
    ) -> list[str]:
        """Retrieve actual columns from an existing PostgreSQL table."""

        schema_name = self._validate_identifier(schema_name, "schema")
        table_name = self._validate_identifier(table_name, "table")

        query = """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = %s
              AND table_name = %s
            ORDER BY ordinal_position;
        """

        with closing(database._connect(read_only=True)) as connection:
            with connection.cursor() as cursor:
                cursor.execute(query, (schema_name, table_name))
                columns = [row[0] for row in cursor.fetchall()]

        if not columns:
            raise ValueError(
                f"Table '{schema_name}.{table_name}' does not exist "
                "or has no accessible columns."
            )

        return columns

    # ==============================================================
    # SAVE DATAFRAME
    # ==============================================================

    def _save_dataframe(
        self,
        df: pd.DataFrame,
        output_folder: str,
        output_format: str,
        filename: str,
    ) -> Path:
        """Save a DataFrame in CSV, JSON or Parquet format."""

        output_format = self._validate_format(output_format)

        if not isinstance(filename, str) or not re.fullmatch(
            r"[A-Za-z0-9_-]{1,100}", filename
        ):
            raise ValueError("Invalid output filename.")

        output_path = self._resolve_project_path(output_folder)
        file_path = output_path / f"{filename}.{output_format}"

        if self.storage_backend == "local":
            output_path.mkdir(parents=True, exist_ok=True)
            if output_format == "csv":
                df.to_csv(file_path, index=False)
            elif output_format == "json":
                df.to_json(
                    file_path,
                    orient="records",
                    lines=True,
                    date_format="iso",
                )
            else:
                df.to_parquet(file_path, index=False)
            return file_path

        object_path = self._storage_object_path(file_path.relative_to(self.project_root).as_posix())
        content = self._serialize_dataframe(df, output_format)
        content_types = {
            "csv": "text/csv",
            "json": "application/x-ndjson",
            "parquet": "application/octet-stream",
        }
        self._get_supabase_client().storage.from_(self.STORAGE_BUCKET).upload(
            object_path,
            content,
            file_options={
                "content-type": content_types[output_format],
                "upsert": "true",
            },
        )
        # Return the logical project path for compatibility with existing callers.
        return file_path

    # ==============================================================
    # EXTRACT: EXTERNAL API
    # ==============================================================

    def extract_load(
        self,
        url: str,
        output_folder: str,
        format: str,
    ) -> str:
        """Extract JSON data from an HTTP API and save it."""

        try:
            output_format = self._validate_format(format)

            if not isinstance(url, str) or not url.startswith(
                ("https://", "http://")
            ):
                raise ValueError("Only HTTP and HTTPS URLs are supported.")

            response = requests.get(
                url,
                timeout=(5, 30),
            )

            response.raise_for_status()
            data = response.json()

            if isinstance(data, dict) and "results" in data:
                records = data["results"]

            elif isinstance(data, dict) and "data" in data:
                records = data["data"]

            else:
                records = data

            if isinstance(records, list):
                df = pd.json_normalize(records)

            elif isinstance(records, dict):
                df = pd.json_normalize(records)

            else:
                raise ValueError(
                    "The API response must contain a JSON object or list."
                )

            if df.empty:
                return "The API returned no records."

            file_path = self._save_dataframe(
                df=df,
                output_folder=output_folder,
                output_format=output_format,
                filename="extracted_data",
            )

            # Preserve the existing test and caller response contract.
            return (
                "Extraction completed successfully.\n"
                f"Records extracted: {len(df)}\n"
                f"Columns: {len(df.columns)}\n"
                f"Saved file: {file_path}"
            )

        except requests.exceptions.Timeout:
            return "Extraction failed: API request timed out."

        except requests.exceptions.RequestException as error:
            logger.exception("API extraction failed")
            return f"Extraction failed: {error}"

        except (ValueError, OSError) as error:
            return f"Extraction failed: {error}"

    # ==============================================================
    # EXTRACT: SUPABASE POSTGRESQL
    # ==============================================================

    def extract_database_to_file(
        self,
        table_name: str,
        output_folder: str = "data/extract",
        output_format: str = "csv",
        schema_name: str = "public",
        limit: int = 100,
        order_by: str | None = None,
        ascending: bool = True,
        columns: list[str] | None = None,
        filename: str = "database_extract",
    ) -> str:
        """
        Extract records from an existing Supabase PostgreSQL table.

        Only SELECT queries are executed.

        Args:
            table_name: Existing database table.
            output_folder: Project-relative output directory.
            output_format: csv, json or parquet.
            schema_name: PostgreSQL schema.
            limit: Maximum number of records.
            order_by: Optional ordering column.
            ascending: Sort direction.
            columns: Optional selected columns.
            filename: Output filename without extension.
        """

        try:
            output_format = self._validate_format(output_format)

            if (
                not isinstance(limit, int)
                or isinstance(limit, bool)
                or not 1 <= limit <= self.MAX_EXTRACTION_ROWS
            ):
                raise ValueError(
                    f"limit must be between 1 and {self.MAX_EXTRACTION_ROWS}."
                )

            if not isinstance(ascending, bool):
                raise ValueError("ascending must be a boolean.")

            schema_name = self._validate_identifier(
                schema_name, "schema"
            )

            table_name = self._validate_identifier(
                table_name, "table"
            )

            database = DatabaseUtil.from_env()

            available_columns = self._get_database_columns(
                database,
                schema_name,
                table_name,
            )

            selected_columns = (
                columns if columns is not None else available_columns
            )

            if not isinstance(selected_columns, list) or not selected_columns:
                raise ValueError("Provide at least one column to extract.")

            if len(selected_columns) != len(set(selected_columns)):
                raise ValueError("Duplicate column names are not allowed.")

            for column in selected_columns:
                if column not in available_columns:
                    raise ValueError(
                        f"Unknown column '{column}' in table '{table_name}'."
                    )

            if order_by is not None and order_by not in available_columns:
                raise ValueError(f"Unknown ordering column: {order_by}")

            query = sql.SQL("SELECT {} FROM {}.{}").format(
                sql.SQL(", ").join(
                    sql.Identifier(column)
                    for column in selected_columns
                ),
                sql.Identifier(schema_name),
                sql.Identifier(table_name),
            )

            if order_by:
                query += sql.SQL(" ORDER BY {} {}").format(
                    sql.Identifier(order_by),
                    sql.SQL("ASC" if ascending else "DESC"),
                )

            query += sql.SQL(" LIMIT %s")

            with closing(database._connect(read_only=True)) as connection:
                with connection.cursor() as cursor:
                    cursor.execute(query, (limit,))

                    records = cursor.fetchall()

                    result_columns = [
                        description[0]
                        for description in cursor.description
                    ]

            df = pd.DataFrame(
                records,
                columns=result_columns,
            )

            if df.empty:
                return (
                    f"No records found in {schema_name}.{table_name}."
                )

            file_path = self._save_dataframe(
                df=df,
                output_folder=output_folder,
                output_format=output_format,
                filename=filename,
            )

            relative_path = file_path.relative_to(
                self.project_root
            ).as_posix()

            return (
                "Database extraction completed successfully.\n"
                "Database: Supabase PostgreSQL\n"
                f"Table: {schema_name}.{table_name}\n"
                f"Records extracted: {len(df)}\n"
                f"Columns extracted: {len(df.columns)}\n"
                f"Output format: {output_format}\n"
                f"Saved file: {relative_path}"
            )

        except Exception as error:
            logger.exception("Database extraction failed")
            return f"Database extraction failed: {error}"

    # ==============================================================
    # LOAD: FILE INTO SUPABASE POSTGRESQL
    # ==============================================================

    def load_dataframe_to_database(
        self,
        input_file_path: str,
        table_name: str,
        schema_name: str = "public",
        if_exists: str = "append",
        confirm_replace: bool = False,
    ) -> str:
        """
        Load a local dataset into an existing PostgreSQL table.

        append:
            Insert records without deleting existing data.

        replace:
            Delete existing records and insert the new records.
            Requires confirm_replace=True.

        This method never creates or drops tables.
        """

        try:
            if if_exists not in {"append", "replace"}:
                raise ValueError(
                    "if_exists must be 'append' or 'replace'."
                )

            if not isinstance(confirm_replace, bool):
                raise ValueError("confirm_replace must be a boolean.")

            if if_exists == "replace" and confirm_replace is not True:
                raise ValueError(
                    "Replacing table data requires confirm_replace=True."
                )

            schema_name = self._validate_identifier(
                schema_name, "schema"
            )

            table_name = self._validate_identifier(
                table_name, "table"
            )

            df = self._read_dataframe(input_file_path)

            if df.empty:
                return "Database loading cancelled: input file is empty."

            if len(df) > self.MAX_UPLOAD_ROWS:
                raise ValueError(
                    f"Upload is limited to {self.MAX_UPLOAD_ROWS} rows."
                )

            if not all(isinstance(column, str) for column in df.columns):
                raise ValueError("All DataFrame column names must be strings.")

            if len(df.columns) != len(set(df.columns)):
                raise ValueError("Duplicate DataFrame column names found.")

            database = DatabaseUtil.from_env()

            available_columns = self._get_database_columns(
                database,
                schema_name,
                table_name,
            )

            missing_columns = [
                column
                for column in df.columns
                if column not in available_columns
            ]

            if missing_columns:
                raise ValueError(
                    "Input contains columns not present in the target table: "
                    + ", ".join(missing_columns)
                )

            records = [
                tuple(
                    None if pd.isna(value) else value
                    for value in row
                )
                for row in df.itertuples(index=False, name=None)
            ]

            insert_query = sql.SQL(
                "INSERT INTO {}.{} ({}) VALUES %s"
            ).format(
                sql.Identifier(schema_name),
                sql.Identifier(table_name),
                sql.SQL(", ").join(
                    sql.Identifier(column)
                    for column in df.columns
                ),
            )

            # The connection context commits on success and rolls back
            # on failure. closing() ensures the connection is closed.
            with closing(database._connect(read_only=False)) as connection:
                with connection:
                    with connection.cursor() as cursor:

                        if if_exists == "replace":
                            cursor.execute(
                                sql.SQL("DELETE FROM {}.{}").format(
                                    sql.Identifier(schema_name),
                                    sql.Identifier(table_name),
                                )
                            )

                        execute_values(
                            cursor,
                            insert_query.as_string(connection),
                            records,
                            page_size=500,
                        )

            return (
                "Database loading completed successfully.\n"
                f"Target table: {schema_name}.{table_name}\n"
                f"Records loaded: {len(records)}\n"
                f"Loading policy: {if_exists}\n"
                f"Source file: {input_file_path}"
            )

        except Exception as error:
            logger.exception("Database loading failed")
            return f"Database loading failed: {error}"

    # ==============================================================
    # READ INPUT FILE
    # ==============================================================

    def _read_dataframe(self, file_path: str) -> pd.DataFrame:
        """Read CSV, JSON or Parquet files from the project directory."""

        path = self._resolve_project_path(file_path)
        extension = path.suffix.lower()

        if extension not in {".csv", ".json", ".parquet"}:
            raise ValueError(
                f"Unsupported input file format: {extension}"
            )

        if self.storage_backend == "local":
            if not path.exists() or not path.is_file():
                raise FileNotFoundError(
                    f"Input file not found: {file_path}"
                )
            if extension == ".csv":
                return pd.read_csv(path)
            if extension == ".json":
                try:
                    return pd.read_json(path, lines=True)
                except ValueError:
                    return pd.read_json(path)
            return pd.read_parquet(path)

        object_path = path.relative_to(self.project_root).as_posix()
        try:
            content = self._get_supabase_client().storage.from_(
                self.STORAGE_BUCKET
            ).download(object_path)
        except Exception as error:
            message = str(error).lower()
            if "not found" in message or "404" in message:
                raise FileNotFoundError(
                    f"Input file not found in Supabase Storage: {file_path}"
                ) from error
            raise

        if not isinstance(content, bytes):
            content = bytes(content)
        return self._dataframe_from_bytes(content, extension)

    # ==============================================================
    # TRANSFORMATION CONTEXT
    # ==============================================================

    def transform_load_context(self, file_path: str) -> str:
        """Return dataset information for the transformation planner."""

        try:
            df = self._read_dataframe(file_path)

            return (
                f"Total rows: {len(df)}\n"
                f"Total columns: {len(df.columns)}\n\n"
                f"Column names:\n{list(df.columns)}\n\n"
                f"Data types:\n{df.dtypes.to_string()}\n\n"
                f"Sample records:\n"
                f"{df.head(3).to_string(index=False)}"
            )

        except Exception as error:
            return f"Unable to read input data: {error}"

    # ==============================================================
    # FILE PREVIEW
    # ==============================================================

    def preview_file(
        self,
        file_path: str,
        rows: int = 5,
        columns: list[str] | None = None,
    ) -> str:
        """Return a bounded preview of a project data file."""

        try:
            if (
                not isinstance(rows, int)
                or isinstance(rows, bool)
                or not 1 <= rows <= self.MAX_PREVIEW_ROWS
            ):
                raise ValueError(
                    f"rows must be between 1 and {self.MAX_PREVIEW_ROWS}."
                )

            df = self._read_dataframe(file_path)

            if columns:
                missing_columns = [
                    column
                    for column in columns
                    if column not in df.columns
                ]

                if missing_columns:
                    raise ValueError(
                        "Unknown columns: "
                        + ", ".join(missing_columns)
                    )

                df = df.loc[:, columns]

            preview = df.head(rows)

            return (
                f"File: {file_path}\n"
                f"Total rows: {len(self._read_dataframe(file_path))}\n"
                f"Total columns in preview: {len(df.columns)}\n"
                f"Showing: {len(preview)} row(s)\n\n"
                f"{preview.to_string(index=False)}"
            )

        except Exception as error:
            return f"Unable to preview file: {error}"

    # ==============================================================
    # VALIDATED PANDAS TRANSFORMATIONS
    # ==============================================================

    def _apply_transformation(
        self,
        df: pd.DataFrame,
        instructions: dict[str, Any],
    ) -> pd.DataFrame:
        """Apply only predefined and validated Pandas transformations."""

        if not isinstance(instructions, dict):
            raise ValueError(
                "Transformation instructions must be a JSON object."
            )

        operation = instructions.get("operation")

        if operation not in self.ALLOWED_OPERATIONS:
            raise ValueError(f"Unsupported operation: {operation}")

        if operation == "filter":

            column = instructions.get("column")
            condition = instructions.get("condition")
            value = instructions.get("value")

            if column not in df.columns:
                raise ValueError(f"Column not found: {column}")

            series = df[column]

            if condition == "equals":
                mask = series == value

            elif condition == "not_equals":
                mask = series != value

            elif condition == "contains":
                mask = series.astype("string").str.contains(
                    str(value),
                    case=False,
                    na=False,
                    regex=False,
                )

            elif condition == "greater_than":
                mask = series > value

            elif condition == "less_than":
                mask = series < value

            elif condition == "is_null":
                mask = series.isna()

            elif condition == "not_null":
                mask = series.notna()

            else:
                raise ValueError(
                    f"Unsupported filter condition: {condition}"
                )

            df = df.loc[mask].copy()

        elif operation == "select_columns":

            columns = instructions.get("columns", [])

            if not isinstance(columns, list) or not columns:
                raise ValueError("Provide a non-empty columns list.")

            missing = set(columns) - set(df.columns)

            if missing:
                raise ValueError(f"Columns not found: {sorted(missing)}")

            df = df[columns].copy()

        elif operation == "drop_columns":

            columns = instructions.get("columns", [])

            if not isinstance(columns, list) or not columns:
                raise ValueError("Provide columns to remove.")

            missing = set(columns) - set(df.columns)

            if missing:
                raise ValueError(f"Columns not found: {sorted(missing)}")

            df = df.drop(columns=columns)

        elif operation == "rename_columns":

            mapping = instructions.get("mapping", {})

            if not isinstance(mapping, dict) or not mapping:
                raise ValueError("Provide a valid column mapping.")

            missing = set(mapping.keys()) - set(df.columns)

            if missing:
                raise ValueError(f"Columns not found: {sorted(missing)}")

            df = df.rename(columns=mapping)

        elif operation == "sort":

            column = instructions.get("column")
            ascending = instructions.get("ascending", True)

            if column not in df.columns:
                raise ValueError(f"Column not found: {column}")

            if not isinstance(ascending, bool):
                raise ValueError("'ascending' must be true or false.")

            df = df.sort_values(
                by=column,
                ascending=ascending,
            )

        elif operation == "drop_duplicates":

            subset = instructions.get("subset")

            if subset is not None:
                if not isinstance(subset, list):
                    raise ValueError("'subset' must be a list of columns.")

                missing = set(subset) - set(df.columns)

                if missing:
                    raise ValueError(f"Columns not found: {sorted(missing)}")

            df = df.drop_duplicates(subset=subset)

        elif operation == "fill_null":

            column = instructions.get("column")

            if column not in df.columns:
                raise ValueError(f"Column not found: {column}")

            if "value" not in instructions:
                raise ValueError("Provide a value for filling nulls.")

            df[column] = df[column].fillna(instructions["value"])

        return df

    # ==============================================================
    # TRANSFORM AND LOAD TO FILE
    # ==============================================================

    def transform_load(
        self,
        input_file_path: str,
        output_folder: str,
        output_format: str,
        instructions: dict[str, Any],
    ) -> str:
        """Read, transform and save a dataset."""

        try:
            output_format = self._validate_format(output_format)

            df = self._read_dataframe(input_file_path)
            original_rows = len(df)

            transformed_df = self._apply_transformation(
                df.copy(),
                instructions,
            )

            file_path = self._save_dataframe(
                df=transformed_df,
                output_folder=output_folder,
                output_format=output_format,
                filename="transformed_data",
            )

            relative_path = file_path.relative_to(
                self.project_root
            ).as_posix()

            return (
                "Transformation completed successfully.\n"
                f"Original rows: {original_rows}\n"
                f"Transformed rows: {len(transformed_df)}\n"
                f"Columns: {len(transformed_df.columns)}\n"
                f"Saved file: {relative_path}"
            )

        except Exception as error:
            logger.exception("Data transformation failed")
            return f"Transformation failed: {error}"

    # ==============================================================
    # LIST GENERATED FILES
    # ==============================================================

    def list_generated_files(self) -> str:
        """List generated CSV files from local storage or Supabase Storage."""

        generated_files = []
        allowed_folders = ("data/extract", "data/transform")

        try:
            if self.storage_backend == "supabase":
                bucket = self._get_supabase_client().storage.from_(
                    self.STORAGE_BUCKET
                )
                for folder_name in allowed_folders:
                    entries = bucket.list(folder_name)
                    for entry in entries or []:
                        name = entry.get("name") if isinstance(entry, dict) else None
                        if not name or not name.lower().endswith(".csv"):
                            continue
                        metadata = entry.get("metadata") or {}
                        object_path = f"{folder_name}/{name}"
                        generated_files.append({
                            "filename": name,
                            "folder": folder_name,
                            "path": object_path,
                            "size_bytes": metadata.get("size") or entry.get("size"),
                        })
            else:
                for folder_name in allowed_folders:
                    expected_folder = self.project_root / folder_name
                    if expected_folder.is_symlink():
                        continue
                    folder = self._resolve_project_path(folder_name)
                    if not folder.exists() or not folder.is_dir():
                        continue
                    for file_path in sorted(folder.iterdir()):
                        if file_path.suffix.lower() != ".csv" or file_path.is_symlink():
                            continue
                        resolved_file = file_path.resolve()
                        if not resolved_file.is_relative_to(folder) or not resolved_file.is_file():
                            continue
                        generated_files.append({
                            "filename": resolved_file.name,
                            "folder": folder_name,
                            "path": resolved_file.relative_to(self.project_root).as_posix(),
                            "size_bytes": resolved_file.stat().st_size,
                        })

            if not generated_files:
                return "No generated CSV files were found."

            return json.dumps(
                {"total_files": len(generated_files), "files": generated_files},
                indent=2,
            )

        except Exception as error:
            logger.exception("Unable to list generated files")
            return f"Unable to list generated files: {error}"



# ==============================================================
# LOCAL TEST
# ==============================================================

if __name__ == "__main__":

    etl = ETLTools()

    print("\nSUPABASE DATABASE EXTRACTION")
    print("-" * 50)

    result = etl.extract_database_to_file(
        table_name="rides",
        schema_name="public",
        limit=100,
        order_by="ride_id",
        ascending=True,
        output_folder="data/extract",
        output_format="csv",
        filename="database_extract",
    )

    print(result)
