<div align="center">

# 🤖 Agentic Data Intelligence Platform

**An AI-powered data assistant for natural-language SQL analysis and end-to-end ETL workflows.**

Users submit a request through the React interface. A FastAPI backend invokes a LangGraph Main Data Agent, which routes the task to the SQL Analyst or ETL Analyst and returns the specialist's result to the user.

[![React](https://img.shields.io/badge/Frontend-React-61DAFB?logo=react&logoColor=black)](https://react.dev/)
[![FastAPI](https://img.shields.io/badge/API-FastAPI-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![LangGraph](https://img.shields.io/badge/Orchestration-LangGraph-6B46C1)](https://www.langchain.com/langgraph)
[![LangChain](https://img.shields.io/badge/LLM_Framework-LangChain-1C3C3C)](https://www.langchain.com/)
[![Python](https://img.shields.io/badge/Python-3.12%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![PostgreSQL](https://img.shields.io/badge/Database-PostgreSQL-4169E1?logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![Supabase](https://img.shields.io/badge/Storage-Supabase-3FCF8E?logo=supabase&logoColor=white)](https://supabase.com/)
[![Render](https://img.shields.io/badge/Deployment-Render-46E3B7?logo=render&logoColor=black)](https://render.com/)
[![License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

[🚀 Live Application](https://agentic-data-intelligence-platform-1.onrender.com/)
· [⚡ Backend API](https://agentic-data-intelligence-platform.onrender.com)
· [📚 API Documentation](https://agentic-data-intelligence-platform.onrender.com/docs)
· [💻 GitHub Repository](https://github.com/rushikeshraghatate90/Agentic-Data-Intelligence-Platform)

</div>

---

## 🌐 Live Application

| Service | Description | Link |
|---|---|---|
| 🚀 Stremlit Frontend | User interface for submitting prompts and viewing agent responses | [Open Application](https://agentic-data-intelligence-platform-1.onrender.com/) |
| ⚡ FastAPI Backend | REST API and agent orchestration service | [Open Backend](https://agentic-data-intelligence-platform.onrender.com) |
| 📖 Swagger UI | Interactive API documentation | [Explore API](https://agentic-data-intelligence-platform.onrender.com/docs) |
| ❤️ Health Check | Backend service health endpoint | [Check Status](https://agentic-data-intelligence-platform.onrender.com/health) |
| 💻 Source Code | Project repository | [GitHub](https://github.com/rushikeshraghatate90/Agentic-Data-Intelligence-Platform) |

---

## ✨ Key Features

- 🧭 **Main Data Agent:** Understands the user's request and routes it to the appropriate specialist.
- 🧠 **SQL Analyst:** Uses database schema context to generate and validate SQL for database analysis.
- ⚖️ **LLM-as-a-Judge:** Adds a model-based evaluation step to the SQL workflow.
- 🔄 **ETL Analyst:** Uses a ReAct tool-calling loop to plan and execute multi-step data tasks.
- 📥 **Data Extraction:** Extracts data from PostgreSQL and supported HTTP API sources.
- 🛠️ **Data Transformation:** Filters, selects, drops, renames, sorts, deduplicates, and fills null values in datasets.
- 📂 **File Management:** Previews and lists generated datasets.
- 📤 **Database Loading:** Loads CSV, JSON, and Parquet data into existing PostgreSQL tables using append or explicitly confirmed replace mode.
- ☁️ **Cloud Storage:** Stores generated ETL files in a private Supabase Storage bucket, with local storage available for development.

---

## Application

| Resource | URL |
|---|---|
| React frontend | https://agentic-data-intelligence-platform-1.onrender.com/ |
| FastAPI backend | https://agentic-data-intelligence-platform.onrender.com |
| Backend health check | https://agentic-data-intelligence-platform.onrender.com/health |
| Source code | https://github.com/rushikeshraghatate90/Agentic-Data-Intelligence-Platform |

## Contents

- [System Architecture](#system-architecture)
- [Features](#features)
- [Technology Stack](#technology-stack)
- [Getting Started](#getting-started)
- [Using the Application](#using-the-application)
- [SQL Analyst Guide](#sql-analyst-guide)
- [ETL Analyst Guide](#etl-analyst-guide)
- [Database Loading Safety](#database-loading-safety)
- [Storage and File Formats](#storage-and-file-formats)
- [Configuration Reference](#configuration-reference)
- [Project Structure](#project-structure)
- [Testing](#testing)
- [Deployment](#deployment)
- [Troubleshooting](#troubleshooting)
- [Security Notes](#security-notes)

## System Architecture

![Agentic Data Intelligence Platform — complete system architecture](docs/architecture.png)

### Request lifecycle

1. **Prompt entry:** A user enters a natural-language question or data task in the React frontend.
2. **API request:** React sends the request to the FastAPI REST API.
3. **Orchestration:** FastAPI invokes the Main Data Agent, implemented with LangGraph.
4. **Intent routing:** The Main Data Agent determines whether the request belongs to the SQL workflow or the ETL workflow.
5. **Specialist execution:** The selected specialist performs its workflow and uses the relevant model, database utilities, or ETL tools.
6. **Result hand-off:** The specialist returns its result and execution information to the Main Data Agent.
7. **Response:** The Main Data Agent completes the response flow. FastAPI returns it to React, where it is displayed to the user.

The Main Data Agent is the central orchestrator. The specialist agents focus on their own responsibilities; their results return through the Main Data Agent rather than being sent directly to the frontend.

### Main Data Agent

The Main Data Agent is responsible for understanding the user's request and routing it to a specialist:

- Requests for database analysis are routed to the SQL Analyst.
- Requests for extraction, transformation, file handling, or database loading are routed to the ETL Analyst.

It receives the specialist result and coordinates the final response returned to the user.

### SQL Analyst workflow

The SQL Analyst follows a controlled graph-based process:

1. Curate and interpret the user's database question.
2. Retrieve relevant PostgreSQL schema context, such as table and column information.
3. Use an LLM to generate a query grounded in that schema context.
4. Validate the generated SQL before execution.
5. Stop unsafe queries and return an explanation; execute only queries that pass the safety checks.
6. Use the LLM-as-a-Judge evaluation stage to assess the generated result or response.
7. Return the specialist result to the Main Data Agent.

**LLM-as-a-Judge** is an evaluation component. It is separate from request routing and SQL safety validation. It does not replace deterministic validation, database permissions, or PostgreSQL constraints.

### ETL Analyst workflow: ReAct

The ETL Analyst uses a ReAct-style loop:

1. The LLM node interprets the current task and selects an appropriate tool.
2. The tool node executes the selected operation.
3. The tool result or error is returned to the LLM as an observation.
4. The LLM decides whether another tool call is needed or whether the task is complete.
5. The ETL Analyst returns the completed result to the Main Data Agent.

This loop allows the ETL Analyst to perform multi-step work, using the result of one tool call to decide the next action.

### Data services

- **Supabase PostgreSQL:** Relational database used for schema context, SQL analysis, database extraction, and supported ETL loads.
- **Supabase Storage:** Stores generated ETL files in the private `etl-files` bucket when cloud storage is configured.
- **Local storage:** Available for development and isolated tests.
- **External HTTP APIs:** Can be used as ETL extraction sources.

## Feature Details

### AI-assisted data analysis

- Natural-language request handling.
- Main-agent routing to SQL and ETL specialists.
- Schema-aware SQL generation.
- SQL safety validation before execution.
- LLM-as-a-Judge evaluation in the SQL workflow.

### ETL operations

- Extract records from PostgreSQL.
- Extract data from HTTP APIs.
- Transform datasets with supported Pandas operations.
- Preview supported files.
- List generated extraction and transformation files.
- Load CSV, JSON, or Parquet data into existing PostgreSQL tables.
- Use local storage or Supabase Storage as the ETL file backend.

### Supported transformations

- Filter rows.
- Select columns.
- Drop columns.
- Rename columns.
- Sort rows.
- Remove duplicate rows.
- Fill null values.

## Technology Stack

| Layer | Technology |
|---|---|
| Frontend | React |
| Backend API | FastAPI |
| Agent orchestration | LangGraph |
| LLM integration and tool interfaces | LangChain |
| Language model provider | Groq API |
| Relational database | PostgreSQL |
| Managed database and object storage | Supabase |
| Data processing | Pandas, NumPy |
| Database connectivity | psycopg2 |
| Data models and validation | Pydantic |
| Environment configuration | python-dotenv |
| Automated tests | pytest |
| Deployment | Render |

## Getting Started

### Prerequisites

- Git
- Python version compatible with the dependencies in `requirements.txt`
- Node.js and npm for the React frontend
- A PostgreSQL database or Supabase project
- A Groq API key

### 1. Clone the repository

```bash
git clone https://github.com/rushikeshraghatate90/Agentic-Data-Intelligence-Platform.git
cd Agentic-Data-Intelligence-Platform
```

### 2. Create a Python virtual environment

Windows PowerShell:

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

macOS or Linux:

```bash
python -m venv venv
source venv/bin/activate
```

### 3. Install backend dependencies

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Configure backend environment variables

Create a `.env` file in the backend project root. Add the required values using the variable names below:

```env
GROQ_API_KEY=your_groq_api_key

DB_HOST=your_postgres_host
DB_PORT=5432
DB_NAME=your_database_name
DB_USER=your_database_user
DB_PASSWORD=your_database_password
DB_SSLMODE=require

SUPABASE_URL=your_supabase_project_url
SUPABASE_SECRET_KEY=your_supabase_secret_key

ETL_STORAGE_BACKEND=supabase
```

For local filesystem storage instead of Supabase Storage, set:

```env
ETL_STORAGE_BACKEND=local
```

Do not commit the `.env` file or share real credentials.

### 5. Start the backend

Run the backend using the configured project entry point:

```bash
python main.py
```

### 6. Start the React frontend

Open a second terminal and change to the React frontend directory. Install its packages and start its development server using the package scripts:

```bash
npm install
npm run dev
```

The frontend must be configured to send API requests to the backend URL. For local development, use the local FastAPI address configured by the backend; for the deployed application, use the deployed backend URL shown in the [Application](#application) section.

> The frontend directory and available npm scripts should be taken from the checked-out repository's frontend package configuration.

## Using the Application

1. Open the React frontend.
2. Enter a question or task in the prompt area.
3. Submit the request.
4. The Main Data Agent routes it to the SQL Analyst or ETL Analyst.
5. Review the response and any execution details shown by the interface.

Write requests as clearly as possible. Include the relevant table, file path, output format, destination table, and loading mode when those details matter.

### Choosing the right type of request

| Goal | Include in your prompt |
|---|---|
| Ask a database question | What you want to know, and relevant table or business terms |
| Extract database records | Schema, table, record limit, output format, destination folder |
| Extract from an API | API source details and desired output |
| Transform a file | Input file path, transformation conditions, output format and folder |
| Preview a file | Exact project-relative file path |
| List generated files | Ask to list generated extraction or transformation files |
| Load data into PostgreSQL | Input file, existing destination table, schema, and loading mode |

## SQL Analyst Guide

Use the SQL Analyst for questions that require information from the connected PostgreSQL database.

Example prompts:

```text
Show the number of rides for each vehicle type.
```

```text
Find the top 10 users by total payments.
```

```text
Calculate the average ride duration by vehicle type.
```

The SQL Analyst uses database schema context to generate a relevant query. Generated SQL passes through the SQL safety-validation step before execution. If a query is not allowed, the workflow stops and returns an explanation instead of executing it.

The SQL workflow includes an LLM-as-a-Judge stage for evaluating generated output. This evaluation is additional to SQL validation and should not be treated as a substitute for database-level access controls.

## ETL Analyst Guide

Use the ETL Analyst for data extraction, transformation, file operations, and database loading.

### Extract data from PostgreSQL

Example:

```text
Extract 100 records from public.rides and save them as CSV in data/extract.
```

Specify the schema and table. Include a record limit and output format when required.

Supported output formats:

- CSV
- JSON
- Parquet

### Extract data from an HTTP API

Ask the ETL Analyst to retrieve data from the intended API source and save the result in a supported output format. Provide the endpoint and any required non-secret request details. Do not put API secrets directly into prompts.

### Transform a dataset

Example:

```text
Read data/extract/database_extract.csv, filter records where ride_id is greater than 50, and save the transformed result as CSV in data/transform.
```

Other supported operations include selecting, dropping, renaming, and sorting columns or rows, removing duplicates, and filling null values.

### Preview a generated file

Example:

```text
Preview data/extract/database_extract.csv.
```

### List generated files

Example:

```text
List the generated files in data/extract and data/transform.
```

### Load a dataset into PostgreSQL

Example:

```text
Load data/extract/database_extract.csv into the existing PostgreSQL table etl_load_test using append mode. Use the public schema.
```

The destination table must already exist. The ETL loader does not create or drop destination tables.

## Database Loading Safety

The database-loading tool supports two modes:

### Append mode

Append is the default mode. It inserts input records into the specified existing table while retaining existing records.

- Destination table must already exist.
- Input columns must be compatible with destination columns.
- PostgreSQL constraints remain active.
- Duplicate primary keys or other constraint violations can cause the load to fail.
- Failed database writes are handled transactionally so a failed operation can be rolled back.

### Replace mode

Replace mode is destructive because it removes existing table records before loading the new dataset.

- The user must explicitly authorize replacement.
- The tool requires `confirm_replace=True`.
- Do not use replace mode for production data unless the impact is understood and the user has explicitly approved it.
- The loader does not create or drop the destination table.

## Storage and File Formats

### Supported formats

| Format | File extension | Typical use |
|---|---|---|
| CSV | `.csv` | Tabular data exchange |
| JSON | `.json` | Structured records |
| Parquet | `.parquet` | Columnar analytical data |

### Project-relative ETL paths

The ETL workflow uses paths such as:

```text
data/
├── extract/
└── transform/
```

Example file paths:

```text
data/extract/database_extract.csv
data/transform/transformed_data.csv
```

When `ETL_STORAGE_BACKEND=supabase`, these logical paths are stored in the private `etl-files` Supabase Storage bucket. When `ETL_STORAGE_BACKEND=local`, the files use local project storage.

### Supabase Storage setup

For cloud ETL storage:

1. Create a private Supabase Storage bucket named `etl-files`.
2. Configure `SUPABASE_URL` and `SUPABASE_SECRET_KEY` in the backend environment.
3. Set `ETL_STORAGE_BACKEND=supabase`.
4. Restart or redeploy the backend after changing environment variables.

The Supabase secret key must only be used by trusted backend code.

## Configuration Reference

| Variable | Purpose |
|---|---|
| `GROQ_API_KEY` | Authenticates model requests to Groq |
| `DB_HOST` | PostgreSQL server hostname |
| `DB_PORT` | PostgreSQL server port |
| `DB_NAME` | Database name |
| `DB_USER` | Database username |
| `DB_PASSWORD` | Database password |
| `DB_SSLMODE` | PostgreSQL SSL connection mode |
| `SUPABASE_URL` | Supabase project URL |
| `SUPABASE_SECRET_KEY` | Server-side Supabase credential used by backend storage integration |
| `ETL_STORAGE_BACKEND` | Selects `local` or `supabase` ETL file storage |

Keep credentials in backend environment variables. Never place database passwords or the Supabase secret key in React environment variables or browser-accessible code.

## Project Structure

```text
Agentic-Data-Intelligence-Platform/
│
├── agents/
│   ├── data_agent.py          # Main Data Agent and specialist routing
│   ├── sql_analyst.py         # SQL Analyst graph and workflow
│   └── etl_analyst.py         # ETL Analyst graph and tool registration
│
├── Models/
│   └── schema.py              # Pydantic models and structured schemas
│
├── utils/
│   ├── database.py            # PostgreSQL connection and database utilities
│   ├── etl_tools.py           # ETL extraction, transformation, storage and loading
│   └── llm_pick.py            # LLM configuration and selection
│
├── data/
│   ├── extract/               # Local extraction directory
│   └── transform/             # Local transformation directory
│
├── tests/                     # Automated tests
├── frontend/                  # React application (if located here in the checkout)
├── main.py                    # Backend entry point
├── requirements.txt           # Python dependencies
└── README.md
```

The tree highlights the principal modules. Some repositories may contain additional files for frontend tooling, deployment, configuration, or tests.

## Testing

Run the test suite from the project root:

```bash
pytest -q
```

Compile the ETL modules:

```powershell
python -m py_compile .\utils\etl_tools.py .\agents\etl_analyst.py
```

The test suite has previously completed with 123 passing tests. Run the commands above against your current checkout to verify the current code after changes.

## Deployment

The application is deployed as separate frontend and backend services on Render.

- Configure the React frontend to use the deployed FastAPI backend URL.
- Configure backend environment variables in the Render backend service.
- Set `ETL_STORAGE_BACKEND=supabase` for deployed ETL file storage.
- Keep Groq, PostgreSQL, and Supabase credentials in backend environment variables.
- Use the backend health endpoint to check whether the API service is responding.

After changing backend code or environment variables, deploy the updated backend service. After changing frontend code or its API URL configuration, deploy the frontend service.

## Troubleshooting

| Symptom | What to check |
|---|---|
| Backend health check fails | Check Render deployment status and backend logs |
| LLM request fails | Verify `GROQ_API_KEY` is configured and valid |
| PostgreSQL connection fails | Check host, port, database, username, password, SSL mode, and network access |
| Supabase file operation fails | Check `SUPABASE_URL`, `SUPABASE_SECRET_KEY`, bucket name, bucket privacy, and backend storage setting |
| File not found | Confirm the exact project-relative path and that the file exists in the configured storage backend |
| Unsupported file format | Use CSV, JSON, or Parquet |
| Transformation column error | Check the spelling and case of the column name in the input file |
| Database load reports missing table | Create and verify the destination table separately; the ETL loader does not create it |
| Duplicate key error | Check primary-key and unique constraints in the destination table |
| Replace asks for confirmation | Confirm only when you intend to remove existing rows and load replacement data |

## Security Notes

- Keep `.env` files and credentials out of version control.
- Keep the Supabase Storage bucket private unless public access is specifically required.
- Use the Supabase secret key only in trusted backend code.
- Validate SQL before execution and apply least-privilege database permissions.
- Validate file paths, schema names, table names, and column names.
- Do not automatically create or drop database tables during ETL loading.
- Require explicit authorization for replace-mode operations.
- Use dedicated test tables for database write testing.
- Do not include API keys or passwords in user prompts, screenshots, logs, or source control.
