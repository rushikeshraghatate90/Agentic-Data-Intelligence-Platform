
import json
from pathlib import Path
from typing import Any

import pandas as pd
import requests


class ETLTools:
    """Utilities for extracting, transforming, and loading tabular data."""

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

    def __init__(self):
        self.project_root = Path(__file__).resolve().parent.parent

    # ------------------------------------------------------------------
    # PATH VALIDATION
    # ------------------------------------------------------------------

    def _resolve_project_path(self, path: str) -> Path:
        """
        Resolve a path and prevent access outside the project directory.
        Both relative paths and absolute paths inside the project are allowed.
        """

        resolved_path = (self.project_root / path).resolve()

        if not resolved_path.is_relative_to(self.project_root):
            raise ValueError(
                "Access outside the project directory is not allowed."
            )

        return resolved_path

    # ------------------------------------------------------------------
    # FILE FORMAT VALIDATION
    # ------------------------------------------------------------------

    def _validate_format(self, file_format: str) -> str:
        file_format = file_format.lower().strip()

        if file_format not in self.SUPPORTED_FORMATS:
            raise ValueError(
                f"Unsupported format: {file_format}. "
                f"Supported formats: {', '.join(sorted(self.SUPPORTED_FORMATS))}"
            )

        return file_format

    # ------------------------------------------------------------------
    # SAVE DATAFRAME
    # ------------------------------------------------------------------

    def _save_dataframe(
        self,
        df: pd.DataFrame,
        output_folder: str,
        output_format: str,
        filename: str,
    ) -> Path:

        output_format = self._validate_format(output_format)
        output_path = self._resolve_project_path(output_folder)

        output_path.mkdir(parents=True, exist_ok=True)

        file_path = output_path / f"{filename}.{output_format}"

        if output_format == "csv":
            df.to_csv(file_path, index=False)

        elif output_format == "json":
            df.to_json(
                file_path,
                orient="records",
                lines=True,
            )

        elif output_format == "parquet":
            df.to_parquet(file_path, index=False)

        return file_path

    # ------------------------------------------------------------------
    # EXTRACT AND LOAD
    # ------------------------------------------------------------------

    def extract_load(
        self,
        url: str,
        output_folder: str,
        format: str,
    ) -> str:
        """
        Extract data from an HTTP API and save it as CSV, JSON, or Parquet.
        """

        try:
            output_format = self._validate_format(format)

            if not url.startswith(("https://", "http://")):
                raise ValueError("Only HTTP and HTTPS URLs are supported.")

            response = requests.get(
                url,
                timeout=(5, 30),
            )

            response.raise_for_status()

            data = response.json()

            # Handle common API response structures.
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

            return (
                "Extraction completed successfully.\n"
                f"Records extracted: {len(df)}\n"
                f"Columns: {len(df.columns)}\n"
                f"Saved file: {file_path}"
            )

        except requests.exceptions.Timeout:
            return "Extraction failed: API request timed out."

        except requests.exceptions.RequestException as error:
            return f"Extraction failed: {error}"

        except (ValueError, OSError) as error:
            return f"Extraction failed: {error}"

    # ------------------------------------------------------------------
    # READ INPUT FILE
    # ------------------------------------------------------------------

    def _read_dataframe(self, file_path: str) -> pd.DataFrame:
        """
        Read CSV, JSON, or Parquet files.
        """

        path = self._resolve_project_path(file_path)

        if not path.exists() or not path.is_file():
            raise FileNotFoundError(f"Input file not found: {path}")

        extension = path.suffix.lower()

        if extension == ".csv":
            df = pd.read_csv(path)

        elif extension == ".json":
            try:
                df = pd.read_json(path, lines=True)
            except ValueError:
                df = pd.read_json(path)

        elif extension == ".parquet":
            df = pd.read_parquet(path)

        else:
            raise ValueError(
                f"Unsupported input file format: {extension}"
            )

        return df

    # ------------------------------------------------------------------
    # TRANSFORMATION CONTEXT
    # ------------------------------------------------------------------

    def transform_load_context(self, file_path: str) -> str:
        """
        Return column information and sample records for the LLM.
        """

        try:
            df = self._read_dataframe(file_path)

            context = (
                f"Total rows: {len(df)}\n"
                f"Total columns: {len(df.columns)}\n\n"
                f"Column names:\n{list(df.columns)}\n\n"
                f"Data types:\n{df.dtypes.to_string()}\n\n"
                f"Sample records:\n{df.head(3).to_string(index=False)}"
            )

            return context

        except Exception as error:
            return f"Unable to read input data: {error}"

    # ------------------------------------------------------------------
    # FILE PREVIEW
    # ------------------------------------------------------------------

    def preview_file(
        self,
        file_path: str,
        rows: int = 5,
        columns: list[str] | None = None,
    ) -> str:
        """
        Return a bounded preview of a project file without modifying it.
        """

        try:
            if not isinstance(rows, int) or isinstance(rows, bool):
                raise ValueError("rows must be an integer.")

            if rows < 1 or rows > 20:
                raise ValueError("rows must be between 1 and 20.")

            df = self._read_dataframe(file_path)

            if columns:
                missing_columns = [
                    column for column in columns
                    if column not in df.columns
                ]

                if missing_columns:
                    raise ValueError(
                        f"Unknown column(s): {', '.join(missing_columns)}. "
                        f"Available columns: {', '.join(map(str, df.columns))}"
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

    # ------------------------------------------------------------------
    # VALIDATED PANDAS TRANSFORMATIONS
    # ------------------------------------------------------------------

    def _apply_transformation(
        self,
        df: pd.DataFrame,
        instructions: dict[str, Any],
    ) -> pd.DataFrame:
        """
        Apply only predefined and validated Pandas operations.

        Supported operations:
        filter, select_columns, drop_columns, rename_columns,
        sort, drop_duplicates, fill_null.
        """

        if not isinstance(instructions, dict):
            raise ValueError("Transformation instructions must be a JSON object.")

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

    # ------------------------------------------------------------------
    # TRANSFORM AND LOAD
    # ------------------------------------------------------------------

    def transform_load(
        self,
        input_file_path: str,
        output_folder: str,
        output_format: str,
        instructions: dict[str, Any],
    ) -> str:
        """
        Read input data, apply validated transformations, and save the result.
        """

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

            return (
                "Transformation completed successfully.\n"
                f"Original rows: {original_rows}\n"
                f"Transformed rows: {len(transformed_df)}\n"
                f"Columns: {len(transformed_df.columns)}\n"
                f"Saved file: {file_path}"
            )

        except Exception as error:
            return f"Transformation failed: {error}"


    # ------------------------------------------------------------------
    # LIST GENERATED FILES
    # ------------------------------------------------------------------

    def list_generated_files(self) -> str:
        """
        List generated CSV files from the permitted ETL output folders.

        Only files inside data/extract and data/transform are listed.
        Symbolic links are skipped to prevent exposing unrelated files.
        """

        generated_files = []

        allowed_folders = (
            "data/extract",
            "data/transform",
        )

        try:
            for folder_name in allowed_folders:
                expected_folder = self.project_root / folder_name

                if expected_folder.is_symlink():
                    continue

                folder = self._resolve_project_path(folder_name)

                if not folder.exists() or not folder.is_dir():
                    continue

                for file_path in sorted(folder.iterdir()):
                    if file_path.suffix.lower() != ".csv":
                        continue

                    if file_path.is_symlink():
                        continue

                    resolved_file = file_path.resolve()

                    if not resolved_file.is_relative_to(folder):
                        continue

                    if not resolved_file.is_file():
                        continue

                    generated_files.append(
                        {
                            "filename": resolved_file.name,
                            "folder": folder_name,
                            "path": resolved_file.relative_to(
                                self.project_root
                            ).as_posix(),
                            "size_bytes": resolved_file.stat().st_size,
                        }
                    )

            if not generated_files:
                return "No generated CSV files were found."

            return json.dumps(
                {
                    "total_files": len(generated_files),
                    "files": generated_files,
                },
                indent=2,
            )

        except (OSError, ValueError) as error:
            return f"Unable to list generated files: {error}"


# ----------------------------------------------------------------------
# LOCAL TEST
# ----------------------------------------------------------------------

if __name__ == "__main__":

    etl = ETLTools()

    result = etl.extract_load(
        url="https://pokeapi.co/api/v2/pokemon",
        output_folder="data/extract",
        format="csv",
    )

    print(result)
