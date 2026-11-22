
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from langchain_core.messages import HumanMessage, AIMessage

from agents.data_agent import data_agent
from utils.database import DatabaseUtil


# ==================================================
# APPLICATION CONFIGURATION
# ==================================================

BASE_DIR = Path(__file__).resolve().parent.parent

OUTPUT_DIRECTORIES = {
    "extract": BASE_DIR / "data" / "extract",
    "transform": BASE_DIR / "data" / "transform",
}

ALLOWED_FILE_EXTENSION = ".csv"


# ==================================================
# FASTAPI APPLICATION
# ==================================================

app = FastAPI(
    title="AI Data Agent API",
    description=(
        "An intelligent multi-agent data platform powered by "
        "Groq, LangGraph, and Supabase PostgreSQL."
    ),
    version="1.3.0",
)


# ==================================================
# REQUEST AND RESPONSE SCHEMAS
# ==================================================

class AgentRequest(BaseModel):
    question: str = Field(
        ...,
        min_length=3,
        max_length=2000,
        description="Natural language question or ETL instruction.",
    )


class AgentResponse(BaseModel):
    question: str
    route: str
    selected_agent: str
    data_source: str
    answer: str
    agent_trace: list[dict[str, Any]]
    metadata: dict[str, Any]


# ==================================================
# GENERATED FILE HELPERS
# ==================================================

def get_generated_file(file_id: str) -> tuple[Path, str]:
    """
    Resolve a generated CSV using a server-managed file ID.

    Supported IDs:
    - extract__filename.csv
    - transform__filename.csv

    Arbitrary filesystem paths are never accepted.
    """

    if not file_id or "__" not in file_id:
        raise HTTPException(
            status_code=404,
            detail="Generated file not found.",
        )

    folder_name, filename = file_id.split("__", 1)

    if folder_name not in OUTPUT_DIRECTORIES:
        raise HTTPException(
            status_code=404,
            detail="Generated file not found.",
        )

    # Only plain filenames are accepted.
    if (
        not filename
        or filename in {".", ".."}
        or Path(filename).name != filename
        or "/" in filename
        or "\\" in filename
    ):
        raise HTTPException(
            status_code=404,
            detail="Generated file not found.",
        )

    if Path(filename).suffix.lower() != ALLOWED_FILE_EXTENSION:
        raise HTTPException(
            status_code=404,
            detail="Only generated CSV files are available.",
        )

    output_directory = OUTPUT_DIRECTORIES[folder_name].resolve()

    try:
        file_path = (
            output_directory / filename
        ).resolve(strict=True)

        # Prevent path traversal and symlink escapes.
        file_path.relative_to(output_directory)

    except (ValueError, FileNotFoundError):
        raise HTTPException(
            status_code=404,
            detail="Generated file not found.",
        )

    if not file_path.is_file():
        raise HTTPException(
            status_code=404,
            detail="Generated file not found.",
        )

    return file_path, folder_name


# ==================================================
# ROOT ENDPOINT
# ==================================================

@app.get("/")
def root():
    return {
        "message": "Welcome to AI Data Agent API",
        "status": "running",
        "version": app.version,
        "docs": "/docs",
        "endpoints": {
            "health": "/health",
            "ask": "/ask",
            "metadata": "/metadata",
            "files": "/files",
            "file_download": "/files/download/{file_id}",
        },
    }


# ==================================================
# HEALTH CHECK
# ==================================================

@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "service": "AI Data Agent",
        "agents": [
            "Main Data Agent",
            "SQL Analyst",
            "ETL Analyst",
        ],
    }


# ==================================================
# LIVE DATABASE METADATA
# ==================================================

@app.get("/metadata")
def get_database_metadata():
    """
    Retrieve live database metadata from Supabase PostgreSQL.
    """

    try:

        database = DatabaseUtil.from_env()

        metadata = database.get_database_metadata(
            schema_name="public"
        )

        return metadata

    except ValueError as error:

        raise HTTPException(
            status_code=500,
            detail=str(error),
        ) from error

    except RuntimeError as error:

        raise HTTPException(
            status_code=503,
            detail="Unable to retrieve database metadata.",
        ) from error

    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred while retrieving metadata.",
        ) from error


# ==================================================
# GENERATED FILE LIST
# ==================================================

@app.get("/files")
def list_generated_files():
    """
    List generated CSV files from the permitted output folders.

    Only files inside:
    - data/extract/
    - data/transform/

    are included.
    """

    files = []

    try:

        for folder_name, directory in OUTPUT_DIRECTORIES.items():

            if not directory.exists():
                continue

            resolved_directory = directory.resolve()

            for file_path in directory.glob("*.csv"):

                try:

                    resolved_file = file_path.resolve(strict=True)

                    # Prevent symlink escapes.
                    resolved_file.relative_to(resolved_directory)

                    if not resolved_file.is_file():
                        continue

                    stat = resolved_file.stat()

                    files.append({
                        "file_id": (
                            f"{folder_name}__{resolved_file.name}"
                        ),
                        "filename": resolved_file.name,
                        "folder": folder_name,
                        "path": (
                            f"data/{folder_name}/{resolved_file.name}"
                        ),
                        "extension": ".csv",
                        "size_bytes": stat.st_size,
                        "modified_at": stat.st_mtime,
                        "download_url": (
                            f"/files/download/"
                            f"{folder_name}__{resolved_file.name}"
                        ),
                    })

                except (ValueError, FileNotFoundError, OSError):
                    continue

        files.sort(
            key=lambda item: item["modified_at"],
            reverse=True,
        )

        return {
            "total_files": len(files),
            "files": files,
        }

    except OSError as error:

        raise HTTPException(
            status_code=500,
            detail="Unable to list generated files.",
        ) from error


# ==================================================
# GENERATED CSV DOWNLOAD
# ==================================================

@app.get("/files/download/{file_id}")
def download_generated_file(file_id: str):
    """
    Download a generated CSV file.

    Only files from the approved output directories
    can be downloaded.
    """

    file_path, _ = get_generated_file(file_id)

    return FileResponse(
        path=str(file_path),
        media_type="text/csv",
        filename=file_path.name,
    )


# ==================================================
# DATA AGENT ENDPOINT
# ==================================================

@app.post("/ask", response_model=AgentResponse)
def ask_agent(request: AgentRequest):

    try:

        # Execute the main Data Agent.
        response = data_agent.invoke({
            "messages": [
                HumanMessage(content=request.question)
            ],
            "route_response": "",
        })

        route = response.get(
            "route_response",
            "unknown",
        )

        # Find the final assistant message.
        final_message = None

        for message in reversed(
            response.get("messages", [])
        ):

            if isinstance(message, AIMessage):
                final_message = message
                break

        if final_message is None:

            raise ValueError(
                "The agent did not return an assistant message."
            )

        # Extract the final answer.
        answer = final_message.content

        if not isinstance(answer, str):
            answer = str(answer)

        if not answer.strip():

            answer = (
                "The agent completed without returning an answer."
            )

        # Extract structured execution information.
        message_metadata = (
            final_message.additional_kwargs or {}
        )

        selected_agent = message_metadata.get(
            "selected_agent",
            "Unknown",
        )

        data_source = message_metadata.get(
            "data_source",
            "Not specified",
        )

        agent_trace = message_metadata.get(
            "agent_trace",
            [],
        )

        # Keep SQL-specific information separate from the trace.
        metadata = {
            key: message_metadata.get(key)
            for key in [
                "generated_sql_query",
                "is_safe",
                "comments",
                "sql_query_execution_result",
            ]
            if key in message_metadata
        }

        return AgentResponse(
            question=request.question,
            route=route,
            selected_agent=selected_agent,
            data_source=data_source,
            answer=answer,
            agent_trace=agent_trace,
            metadata=metadata,
        )

    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail=f"Agent execution failed: {str(error)}",
        ) from error


# ==================================================
# LOCAL SERVER
# ==================================================

if __name__ == "__main__":

    import uvicorn

    uvicorn.run(
        "api.main:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
    )
