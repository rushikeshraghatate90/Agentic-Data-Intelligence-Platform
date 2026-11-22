
import pandas as pd
import pytest
import requests

from utils.etl_tools import ETLTools


@pytest.fixture
def etl(tmp_path):
    """Create an ETL instance using an isolated temporary project directory."""
    instance = ETLTools()
    instance.project_root = tmp_path
    return instance


@pytest.fixture
def sample_dataframe():
    return pd.DataFrame(
        {
            "name": ["Alice", "Bob", "Charlie", "Alice"],
            "age": [25, 30, 35, 25],
            "city": ["Pune", "Mumbai", "Pune", "Pune"],
            "score": [90, None, 85, 90],
        }
    )


@pytest.fixture
def sample_csv(etl, sample_dataframe):
    """Create a sample CSV inside the temporary project directory."""
    path = etl.project_root / "data" / "input.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    sample_dataframe.to_csv(path, index=False)
    return "data/input.csv"


# ---------------------------------------------------------
# PATH VALIDATION
# ---------------------------------------------------------

def test_project_path_inside_root_is_allowed(etl):
    path = etl._resolve_project_path("data/input.csv")

    assert path == etl.project_root / "data" / "input.csv"


def test_project_path_outside_root_is_rejected(etl):
    with pytest.raises(ValueError, match="outside the project"):
        etl._resolve_project_path("../outside.csv")


# ---------------------------------------------------------
# FORMAT VALIDATION
# ---------------------------------------------------------

@pytest.mark.parametrize(
    "file_format",
    ["csv", "json", "parquet", " CSV "],
)
def test_supported_formats_are_accepted(etl, file_format):
    assert etl._validate_format(file_format) == file_format.strip().lower()


def test_unsupported_format_is_rejected(etl):
    with pytest.raises(ValueError, match="Unsupported format"):
        etl._validate_format("xml")


# ---------------------------------------------------------
# DATAFRAME SAVE AND READ
# ---------------------------------------------------------

@pytest.mark.parametrize("file_format", ["csv", "json", "parquet"])
def test_save_and_read_supported_formats(
    etl,
    sample_dataframe,
    file_format,
):
    output_path = etl._save_dataframe(
        df=sample_dataframe,
        output_folder="data/output",
        output_format=file_format,
        filename="test_data",
    )

    assert output_path.exists()
    assert output_path.suffix == f".{file_format}"

    loaded_df = etl._read_dataframe(
        str(output_path.relative_to(etl.project_root))
    )

    assert list(loaded_df.columns) == list(sample_dataframe.columns)
    assert len(loaded_df) == len(sample_dataframe)


def test_read_missing_file_raises_error(etl):
    with pytest.raises(FileNotFoundError, match="Input file not found"):
        etl._read_dataframe("data/missing.csv")


def test_read_unsupported_file_extension(etl):
    path = etl.project_root / "data" / "input.xml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("<data></data>", encoding="utf-8")

    with pytest.raises(ValueError, match="Unsupported input file format"):
        etl._read_dataframe("data/input.xml")


# ---------------------------------------------------------
# API EXTRACTION
# ---------------------------------------------------------

class MockResponse:
    def __init__(self, data):
        self.data = data

    def raise_for_status(self):
        pass

    def json(self):
        return self.data


def test_extract_load_from_results_response(etl, monkeypatch):
    api_data = {
        "results": [
            {"name": "Pikachu", "type": "Electric"},
            {"name": "Bulbasaur", "type": "Grass"},
        ]
    }

    def mock_get(url, timeout):
        assert url == "https://example.com/api"
        assert timeout == (5, 30)
        return MockResponse(api_data)

    monkeypatch.setattr(
        "utils.etl_tools.requests.get",
        mock_get,
    )

    result = etl.extract_load(
        url="https://example.com/api",
        output_folder="data/extract",
        format="csv",
    )

    output_path = etl.project_root / "data" / "extract" / "extracted_data.csv"

    assert "Extraction completed successfully" in result
    assert output_path.exists()

    extracted_df = pd.read_csv(output_path)

    assert len(extracted_df) == 2
    assert list(extracted_df["name"]) == ["Pikachu", "Bulbasaur"]


def test_extract_load_from_data_response(etl, monkeypatch):
    api_data = {
        "data": [
            {"id": 1, "name": "Alice"},
            {"id": 2, "name": "Bob"},
        ]
    }

    monkeypatch.setattr(
        "utils.etl_tools.requests.get",
        lambda *args, **kwargs: MockResponse(api_data),
    )

    result = etl.extract_load(
        "https://example.com/api",
        "data/extract",
        "json",
    )

    output_path = etl.project_root / "data" / "extract" / "extracted_data.json"

    assert "Extraction completed successfully" in result
    assert output_path.exists()

    extracted_df = pd.read_json(output_path, lines=True)

    assert len(extracted_df) == 2


def test_extract_load_rejects_invalid_url(etl):
    result = etl.extract_load(
        url="ftp://example.com/data",
        output_folder="data/extract",
        format="csv",
    )

    assert "Only HTTP and HTTPS URLs are supported" in result


def test_extract_load_handles_timeout(etl, monkeypatch):
    def mock_get(*args, **kwargs):
        raise requests.exceptions.Timeout()

    monkeypatch.setattr(
        "utils.etl_tools.requests.get",
        mock_get,
    )

    result = etl.extract_load(
        "https://example.com/api",
        "data/extract",
        "csv",
    )

    assert result == "Extraction failed: API request timed out."


def test_extract_load_handles_request_error(etl, monkeypatch):
    def mock_get(*args, **kwargs):
        raise requests.exceptions.ConnectionError("Connection refused")

    monkeypatch.setattr(
        "utils.etl_tools.requests.get",
        mock_get,
    )

    result = etl.extract_load(
        "https://example.com/api",
        "data/extract",
        "csv",
    )

    assert "Extraction failed:" in result
    assert "Connection refused" in result


def test_extract_load_handles_empty_response(etl, monkeypatch):
    monkeypatch.setattr(
        "utils.etl_tools.requests.get",
        lambda *args, **kwargs: MockResponse({"results": []}),
    )

    result = etl.extract_load(
        "https://example.com/api",
        "data/extract",
        "csv",
    )

    assert result == "The API returned no records."


# ---------------------------------------------------------
# TRANSFORMATION OPERATIONS
# ---------------------------------------------------------

def test_filter_transformation(etl, sample_dataframe):
    result = etl._apply_transformation(
        sample_dataframe,
        {
            "operation": "filter",
            "column": "city",
            "condition": "equals",
            "value": "Pune",
        },
    )

    assert len(result) == 3
    assert all(result["city"] == "Pune")


def test_filter_contains_is_case_insensitive(etl, sample_dataframe):
    result = etl._apply_transformation(
        sample_dataframe,
        {
            "operation": "filter",
            "column": "name",
            "condition": "contains",
            "value": "ali",
        },
    )

    assert len(result) == 2


def test_filter_greater_than(etl, sample_dataframe):
    result = etl._apply_transformation(
        sample_dataframe,
        {
            "operation": "filter",
            "column": "age",
            "condition": "greater_than",
            "value": 25,
        },
    )

    assert result["age"].tolist() == [30, 35]


def test_select_columns(etl, sample_dataframe):
    result = etl._apply_transformation(
        sample_dataframe,
        {
            "operation": "select_columns",
            "columns": ["name", "city"],
        },
    )

    assert list(result.columns) == ["name", "city"]


def test_drop_columns(etl, sample_dataframe):
    result = etl._apply_transformation(
        sample_dataframe,
        {
            "operation": "drop_columns",
            "columns": ["score"],
        },
    )

    assert "score" not in result.columns


def test_rename_columns(etl, sample_dataframe):
    result = etl._apply_transformation(
        sample_dataframe,
        {
            "operation": "rename_columns",
            "mapping": {"name": "customer_name"},
        },
    )

    assert "customer_name" in result.columns
    assert "name" not in result.columns


def test_sort_transformation(etl, sample_dataframe):
    result = etl._apply_transformation(
        sample_dataframe,
        {
            "operation": "sort",
            "column": "age",
            "ascending": False,
        },
    )

    assert result["age"].tolist() == [35, 30, 25, 25]


def test_drop_duplicates(etl, sample_dataframe):
    result = etl._apply_transformation(
        sample_dataframe,
        {
            "operation": "drop_duplicates",
        },
    )

    assert len(result) == 3


def test_fill_null(etl, sample_dataframe):
    result = etl._apply_transformation(
        sample_dataframe,
        {
            "operation": "fill_null",
            "column": "score",
            "value": 0,
        },
    )

    assert result["score"].isna().sum() == 0
    assert result.loc[1, "score"] == 0


# ---------------------------------------------------------
# TRANSFORMATION VALIDATION
# ---------------------------------------------------------

def test_unsupported_transformation_is_rejected(etl, sample_dataframe):
    with pytest.raises(ValueError, match="Unsupported operation"):
        etl._apply_transformation(
            sample_dataframe,
            {"operation": "execute_python"},
        )


def test_missing_column_is_rejected(etl, sample_dataframe):
    with pytest.raises(ValueError, match="Column not found"):
        etl._apply_transformation(
            sample_dataframe,
            {
                "operation": "filter",
                "column": "salary",
                "condition": "equals",
                "value": 100,
            },
        )


def test_unsupported_filter_condition_is_rejected(etl, sample_dataframe):
    with pytest.raises(ValueError, match="Unsupported filter condition"):
        etl._apply_transformation(
            sample_dataframe,
            {
                "operation": "filter",
                "column": "age",
                "condition": "starts_with",
                "value": "2",
            },
        )


def test_empty_select_columns_is_rejected(etl, sample_dataframe):
    with pytest.raises(ValueError, match="non-empty columns list"):
        etl._apply_transformation(
            sample_dataframe,
            {
                "operation": "select_columns",
                "columns": [],
            },
        )


def test_invalid_transformation_instructions_are_rejected(
    etl,
    sample_dataframe,
):
    with pytest.raises(ValueError, match="JSON object"):
        etl._apply_transformation(
            sample_dataframe,
            ["invalid"],
        )


# ---------------------------------------------------------
# TRANSFORM AND LOAD WORKFLOW
# ---------------------------------------------------------

def test_transform_load_success(etl, sample_csv):
    result = etl.transform_load(
        input_file_path=sample_csv,
        output_folder="data/transform",
        output_format="csv",
        instructions={
            "operation": "filter",
            "column": "city",
            "condition": "equals",
            "value": "Pune",
        },
    )

    output_path = (
        etl.project_root
        / "data"
        / "transform"
        / "transformed_data.csv"
    )

    assert "Transformation completed successfully" in result
    assert output_path.exists()

    transformed_df = pd.read_csv(output_path)

    assert len(transformed_df) == 3
    assert all(transformed_df["city"] == "Pune")


def test_transform_load_handles_invalid_operation(etl, sample_csv):
    result = etl.transform_load(
        input_file_path=sample_csv,
        output_folder="data/transform",
        output_format="csv",
        instructions={
            "operation": "unknown_operation",
        },
    )

    assert "Transformation failed:" in result
    assert "Unsupported operation" in result


def test_transform_load_rejects_unsupported_output_format(
    etl,
    sample_csv,
):
    result = etl.transform_load(
        input_file_path=sample_csv,
        output_folder="data/transform",
        output_format="xml",
        instructions={
            "operation": "drop_duplicates",
        },
    )

    assert "Transformation failed:" in result
    assert "Unsupported format" in result


# ---------------------------------------------------------
# TRANSFORMATION CONTEXT
# ---------------------------------------------------------

def test_transform_load_context_returns_dataframe_information(
    etl,
    sample_csv,
):
    result = etl.transform_load_context(sample_csv)

    assert "Total rows: 4" in result
    assert "Total columns: 4" in result
    assert "name" in result
    assert "age" in result
    assert "Sample records:" in result


def test_transform_load_context_handles_missing_file(etl):
    result = etl.transform_load_context("data/missing.csv")

    assert "Unable to read input data:" in result
