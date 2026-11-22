import streamlit as st
import requests
from datetime import datetime
from pathlib import Path
import os

# ============================================================
# PAGE CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="AI Data Agent",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ============================================================
# MODERN COLORFUL UI/UX WITH CRISP BLACK TEXT (CUSTOM CSS)
# ============================================================

st.markdown(
    """
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

        /* Enforce Crisp Black Text across the entire app */
        html, body, [class*="css"], p, span, div, label, li, h1, h2, h3, h4, h5, h6 {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
            color: #090D16;
        }

        /* Clean Light Background Canvas */
        .stApp {
            background-color: #F4F7FB;
        }

        .block-container {
            padding-top: 1.75rem;
            padding-bottom: 3rem;
            max-width: 1220px;
        }

        /* Sidebar Styling */
        [data-testid="stSidebar"] {
            background-color: #FFFFFF;
            border-right: 1px solid #DCE4F0;
        }
        [data-testid="stSidebar"] * {
            color: #090D16 !important;
        }

        /* Vibrant Royal Blue Hero Banner (White text ONLY inside dark blue banner) */
        .hero-banner {
            background: linear-gradient(120deg, #1E40AF 0%, #2563EB 55%, #3B82F6 100%);
            border-radius: 16px;
            padding: 26px 32px;
            margin-bottom: 1.25rem;
            box-shadow: 0 8px 20px rgba(37, 99, 235, 0.18);
        }
        .hero-banner * {
            color: #FFFFFF !important;
        }
        .hero-title {
            font-size: 2rem;
            font-weight: 800;
            margin: 0 0 6px 0;
            letter-spacing: -0.02em;
        }
        .hero-subtitle {
            font-size: 1rem;
            font-weight: 400;
            margin: 0;
            opacity: 0.95;
        }

        /* Colorful Segmented Pill Navigation Bar */
        div[role="radiogroup"] {
            background-color: #FFFFFF;
            padding: 6px;
            border-radius: 12px;
            border: 1px solid #CBD5E1;
            display: inline-flex;
            gap: 6px;
            width: 100%;
            box-shadow: 0 2px 6px rgba(15, 23, 42, 0.04);
        }
        div[role="radiogroup"] > label {
            flex: 1;
            text-align: center;
            justify-content: center;
            background-color: #F8FAFC;
            border-radius: 8px;
            padding: 9px 16px;
            font-weight: 600;
            color: #090D16 !important;
            transition: all 0.2s ease;
            border: 1px solid transparent !important;
        }
        div[role="radiogroup"] > label:hover {
            background-color: #EFF6FF;
            border-color: #93C5FD !important;
        }
        div[role="radiogroup"] > label[data-checked="true"] {
            background: linear-gradient(135deg, #2563EB 0%, #1D4ED8 100%) !important;
            color: #FFFFFF !important;
            box-shadow: 0 2px 6px rgba(37, 99, 235, 0.25);
        }
        div[role="radiogroup"] > label[data-checked="true"] * {
            color: #FFFFFF !important;
        }
        div[role="radiogroup"] > label > div:first-child {
            display: none !important;
        }

        /* White Card Containers */
        [data-testid="stVerticalBlockBorderWrapper"] {
            background-color: #FFFFFF;
            border-radius: 14px !important;
            border: 1px solid #DCE4F0 !important;
            box-shadow: 0 2px 8px rgba(15, 23, 42, 0.04);
        }

        /* Metric Cards with Colorful Top Accent */
        [data-testid="stMetric"] {
            background-color: #FFFFFF;
            border: 1px solid #DCE4F0;
            border-top: 4px solid #2563EB;
            padding: 16px 20px;
            border-radius: 12px;
            box-shadow: 0 2px 6px rgba(15, 23, 42, 0.04);
        }
        [data-testid="stMetricLabel"] * {
            font-size: 0.85rem !important;
            font-weight: 600 !important;
            color: #1E293B !important;
        }
        [data-testid="stMetricValue"] * {
            font-size: 1.75rem !important;
            font-weight: 800 !important;
            color: #000000 !important;
        }

        /* Primary & Secondary Buttons */
        .stButton > button {
            border-radius: 8px;
            font-weight: 600;
            border: 1px solid #CBD5E1;
            color: #090D16 !important;
            background-color: #FFFFFF;
            transition: all 0.15s ease;
        }
        .stButton > button:hover {
            border-color: #2563EB;
            background-color: #EFF6FF;
            color: #000000 !important;
        }
        .stButton > button[kind="primary"] {
            background: linear-gradient(135deg, #2563EB 0%, #1D4ED8 100%);
            border: none;
            color: #FFFFFF !important;
            box-shadow: 0 3px 8px rgba(37, 99, 235, 0.25);
        }
        .stButton > button[kind="primary"] * {
            color: #FFFFFF !important;
        }
        .stButton > button[kind="primary"]:hover {
            background: linear-gradient(135deg, #1D4ED8 0%, #1E3A8A 100%);
        }

        /* Text Area Input - Black Text on Clean White */
        textarea {
            color: #000000 !important;
            background-color: #FFFFFF !important;
            border: 1.5px solid #CBD5E1 !important;
            border-radius: 10px !important;
            font-weight: 500 !important;
        }
        textarea:focus {
            border-color: #2563EB !important;
            box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.15) !important;
        }

        /* Expanders */
        .streamlit-expanderHeader {
            background-color: #FFFFFF;
            border-radius: 10px;
            font-weight: 700;
            color: #090D16 !important;
            border: 1px solid #DCE4F0;
        }

        /* Colorful Agent Cards in Sidebar */
        .agent-card-main {
            background-color: #EEF2FF;
            border-left: 4px solid #4F46E5;
            border-radius: 8px;
            padding: 10px 12px;
            margin-bottom: 10px;
        }
        .agent-card-sql {
            background-color: #EFF6FF;
            border-left: 4px solid #2563EB;
            border-radius: 8px;
            padding: 10px 12px;
            margin-bottom: 10px;
        }
        .agent-card-etl {
            background-color: #ECFDF5;
            border-left: 4px solid #10B981;
            border-radius: 8px;
            padding: 10px 12px;
            margin-bottom: 10px;
        }
        .agent-card-title {
            font-weight: 700;
            font-size: 0.9rem;
            color: #000000 !important;
            margin-bottom: 2px;
        }
        .agent-card-desc {
            font-size: 0.8rem;
            color: #111827 !important;
            margin: 0;
        }

        /* Colorful Route Badges with Black Text */
        .badge-container {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            margin-top: 8px;
            margin-bottom: 12px;
        }
        .badge {
            display: inline-flex;
            align-items: center;
            padding: 4px 12px;
            border-radius: 9999px;
            font-size: 0.8rem;
            font-weight: 700;
            color: #000000 !important;
        }
        .badge-sql {
            background-color: #BFDBFE;
            border: 1px solid #3B82F6;
        }
        .badge-etl {
            background-color: #A7F3D0;
            border: 1px solid #10B981;
        }
        .badge-specialist {
            background-color: #DDD6FE;
            border: 1px solid #8B5CF6;
        }
        .badge-source {
            background-color: #FDE68A;
            border: 1px solid #F59E0B;
        }

        /* Colorful Sample Prompt Banners */
        .prompt-box-sql {
            background-color: #EFF6FF;
            border: 1px solid #93C5FD;
            border-left: 5px solid #2563EB;
            border-radius: 10px;
            padding: 14px 16px;
            margin-bottom: 10px;
        }
        .prompt-box-etl {
            background-color: #ECFDF5;
            border: 1px solid #6EE7B7;
            border-left: 5px solid #10B981;
            border-radius: 10px;
            padding: 14px 16px;
            margin-bottom: 10px;
        }
    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# APPLICATION CONFIGURATION
# ============================================================

API_URL = os.getenv("API_URL", "http://127.0.0.1:8000").rstrip("/")
API_TIMEOUT = 10
AGENT_TIMEOUT = 120


# ============================================================
# APPLICATION DATA
# ============================================================

SQL_PROMPTS = [
    "Show me the top 5 cities by number of users.",
    "What is the average ride fare for completed rides?",
    "Show the distribution of payment methods.",
    "Find the top 10 vehicles by number of rides.",
    "Calculate the average rating for each driver.",
]

ETL_PROMPTS = [
    (
        "Extract the first 20 Pokémon from "
        "https://pokeapi.co/api/v2/pokemon?limit=20 "
        "and save the results as a CSV file in data/extract/."
    ),
    "Load users.csv and remove duplicate records.",
    (
        "Filter rides with completed status and "
        "save the result as a CSV file."
    ),
    "Load a dataset and show its missing values and data types.",
]

TABLE_DESCRIPTIONS = {
    "users": "Stores user information and city details.",
    "vehicles": "Contains vehicle-related records.",
    "rides": "Contains ride and trip information.",
    "payments": "Stores payment and transaction records.",
    "ratings": "Contains rider and driver rating records.",
}


# ============================================================
# SESSION STATE
# ============================================================

def initialize_session_state():

    defaults = {
        "messages": [],
        "api_status": None,
        "active_page": "Chat",
        "chat_input_widget": "",
        "submission_error": None,
        "database_metadata": None,
        "generated_files": None,
        "workspace_error": None,
        "last_metadata_refresh": None,
    }

    for key, value in defaults.items():

        if key not in st.session_state:
            st.session_state[key] = value


initialize_session_state()


# ============================================================
# API CONNECTION
# ============================================================

def check_api_connection():

    try:

        response = requests.get(
            f"{API_URL}/health",
            timeout=API_TIMEOUT,
        )

        return response.status_code == 200

    except requests.RequestException:
        return False


def ask_agent(question: str):

    response = requests.post(
        f"{API_URL}/ask",
        json={"question": question},
        timeout=AGENT_TIMEOUT,
    )

    response.raise_for_status()

    return response.json()


def fetch_database_metadata():

    response = requests.get(
        f"{API_URL}/metadata",
        timeout=30,
    )

    response.raise_for_status()

    return response.json()


def fetch_generated_files():

    response = requests.get(
        f"{API_URL}/files",
        timeout=API_TIMEOUT,
    )

    response.raise_for_status()

    return response.json()


def download_generated_file(file_id: str):

    response = requests.get(
        f"{API_URL}/files/download/{file_id}",
        timeout=30,
    )

    response.raise_for_status()

    return response.content


# ============================================================
# WORKSPACE DATA REFRESH
# ============================================================

def refresh_workspace():

    st.session_state.workspace_error = None

    try:

        metadata = fetch_database_metadata()

        files_response = fetch_generated_files()

        st.session_state.database_metadata = metadata

        st.session_state.generated_files = (
            files_response.get("files", [])
        )

        st.session_state.last_metadata_refresh = (
            datetime.now().strftime("%d %b %Y, %I:%M:%S %p")
        )

    except requests.RequestException as error:

        st.session_state.workspace_error = (
            f"Unable to retrieve workspace data: {error}"
        )

    except Exception as error:

        st.session_state.workspace_error = (
            f"Unexpected workspace error: {error}"
        )


# ============================================================
# NAVIGATION CALLBACKS
# ============================================================

def navigate_to_prompt(prompt: str):

    st.session_state.chat_input_widget = prompt

    st.session_state.active_page = "Chat"


def clear_conversation():

    st.session_state.messages = []

    st.session_state.chat_input_widget = ""

    st.session_state.submission_error = None


# ============================================================
# CHAT SUBMISSION CALLBACK
# ============================================================

def submit_question():

    question = (
        st.session_state.chat_input_widget.strip()
    )

    if not question:

        st.session_state.submission_error = (
            "Please enter a question before submitting."
        )

        return

    st.session_state.submission_error = None

    st.session_state.messages.append({
        "role": "user",
        "content": question,
    })

    try:

        result = ask_agent(question)

        assistant_message = {
            "role": "assistant",
            "content": result.get(
                "answer",
                "No response received from the agent.",
            ),
            "route": result.get(
                "route",
                "unknown",
            ),
            "selected_agent": result.get(
                "selected_agent",
                "Unknown",
            ),
            "data_source": result.get(
                "data_source",
                "Not specified",
            ),
            "agent_trace": result.get(
                "agent_trace",
                [],
            ),
            "metadata": result.get(
                "metadata",
                {},
            ),
        }

        st.session_state.messages.append(
            assistant_message
        )

        # Refresh workspace after an ETL operation.
        if assistant_message["route"] == "etl":

            try:

                st.session_state.generated_files = (
                    fetch_generated_files().get("files", [])
                )

            except requests.RequestException:
                pass

    except requests.exceptions.Timeout:

        st.session_state.messages.append({
            "role": "assistant",
            "content": (
                "The request timed out. "
                "Please try again."
            ),
        })

    except requests.exceptions.RequestException as error:

        st.session_state.messages.append({
            "role": "assistant",
            "content": f"Backend request failed: {error}",
        })

    except Exception as error:

        st.session_state.messages.append({
            "role": "assistant",
            "content": f"Unexpected error: {error}",
        })

    # Safe: this function runs as a button callback.
    st.session_state.chat_input_widget = ""


# ============================================================
# WORKFLOW VISUALIZATION
# ============================================================

def render_workflow_graph(route: str):

    route = (route or "unknown").lower()

    sql_selected = route == "sql"
    etl_selected = route == "etl"

    sql_color = "#10B981" if sql_selected else "#94A3B8"
    etl_color = "#10B981" if etl_selected else "#94A3B8"

    sql_fill = "#A7F3D0" if sql_selected else "#F1F5F9"
    etl_fill = "#A7F3D0" if etl_selected else "#F1F5F9"

    sql_label = (
        "SQL Analyst\\nSELECTED"
        if sql_selected
        else "SQL Analyst\\nNot selected"
    )

    etl_label = (
        "ETL Analyst\\nSELECTED"
        if etl_selected
        else "ETL Analyst\\nNot selected"
    )

    graph = f"""
    digraph AgentWorkflow {{

        graph [
            rankdir=LR,
            bgcolor="transparent",
            nodesep=0.65,
            ranksep=0.85,
            pad=0.3
        ];

        node [
            shape=box,
            style="rounded,filled",
            fontname="Inter, Arial",
            fontsize=11,
            color="#3B82F6",
            fontcolor="#000000",
            margin="0.22,0.15"
        ];

        edge [
            color="#64748B",
            penwidth=1.8,
            arrowsize=0.75
        ];

        user [
            label="USER REQUEST",
            fillcolor="#BAE6FD",
            color="#0284C7"
        ];

        main [
            label="MAIN DATA AGENT\\nOrchestrator",
            fillcolor="#DDD6FE",
            color="#7C3AED"
        ];

        router [
            label="ROUTER\\nSQL / ETL",
            fillcolor="#FDE68A",
            color="#D97706"
        ];

        sql [
            label="{sql_label}",
            fillcolor="{sql_fill}",
            color="{sql_color}",
            penwidth=2.2
        ];

        etl [
            label="{etl_label}",
            fillcolor="{etl_fill}",
            color="{etl_color}",
            penwidth=2.2
        ];

        result [
            label="FINAL RESPONSE",
            fillcolor="#BBF7D0",
            color="#16A34A"
        ];

        user -> main;
        main -> router;

        router -> sql [
            color="{sql_color}",
            penwidth={2.6 if sql_selected else 1.4}
        ];

        router -> etl [
            color="{etl_color}",
            penwidth={2.6 if etl_selected else 1.4}
        ];

        sql -> result [
            color="{sql_color}",
            penwidth={2.6 if sql_selected else 1.4}
        ];

        etl -> result [
            color="{etl_color}",
            penwidth={2.6 if etl_selected else 1.4}
        ];

        {{rank=same; sql; etl}}
    }}
    """

    st.graphviz_chart(
        graph,
        use_container_width=True,
    )

    if sql_selected:

        st.success(
            "SQL Analyst was selected for this request."
        )

    elif etl_selected:

        st.success(
            "ETL Analyst was selected for this request."
        )

    else:

        st.info(
            "No specialist route was identified."
        )


# ============================================================
# EXECUTION TRACE
# ============================================================

def render_agent_trace(trace):

    if not trace:

        st.info("No execution trace is available.")

        return

    for step in trace:

        status = step.get("status", "unknown")

        if status == "completed":
            status_icon = "✅"
            bg_tint = "#ECFDF5"
            border_tint = "#10B981"

        elif status == "running":
            status_icon = "🔄"
            bg_tint = "#EFF6FF"
            border_tint = "#3B82F6"

        else:
            status_icon = "⏳"
            bg_tint = "#FFFBEB"
            border_tint = "#F59E0B"

        st.markdown(
            f"""
            <div style="background-color:{bg_tint}; border-left:4px solid {border_tint}; border-radius:8px; padding:10px 14px; margin-bottom:8px;">
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <strong style="color:#000000;">Step {step.get('step', '')}: {step.get('agent', 'Agent')}</strong>
                    <span style="font-weight:700; color:#000000;">{status_icon} {status.capitalize()}</span>
                </div>
                <div style="color:#111827; font-size:0.88rem; margin-top:4px;">{step.get('action', '')}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


# ============================================================
# EXECUTION METADATA
# ============================================================

def render_metadata(metadata):

    if not metadata:

        st.markdown("No additional execution metadata available.")

        return

    sql_query = metadata.get("generated_sql_query")

    if sql_query:

        st.markdown("**Generated SQL Query**")

        st.code(
            sql_query,
            language="sql",
        )

    if metadata.get("is_safe") is not None:

        st.markdown(
            f"**SQL Validation:** `{metadata['is_safe']}`"
        )

    if metadata.get("comments"):

        st.markdown(
            f"*{metadata['comments']}*"
        )

    execution_result = metadata.get(
        "sql_query_execution_result"
    )

    if execution_result:

        with st.expander("View SQL Execution Result"):

            st.code(
                str(execution_result),
                language="json",
            )


# ============================================================
# ASSISTANT RESPONSE DETAILS
# ============================================================

def render_assistant_details(message):

    route = message.get(
        "route",
        "unknown",
    )

    selected_agent = message.get(
        "selected_agent",
        "Unknown",
    )

    data_source = message.get(
        "data_source",
        "Not specified",
    )

    trace = message.get(
        "agent_trace",
        [],
    )

    metadata = message.get(
        "metadata",
        {},
    )

    route_lower = route.lower()
    route_class = "badge-sql" if route_lower == "sql" else "badge-etl"

    st.markdown(
        f"""
        <div class="badge-container">
            <span class="badge {route_class}">🔀 Route: {route.upper()}</span>
            <span class="badge badge-specialist">🤖 Specialist: {selected_agent}</span>
            <span class="badge badge-source">🗄️ Source: {data_source}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.expander("🔀 Visual Agent Workflow"):

        render_workflow_graph(route)

    with st.expander("📋 Agent Activity & Execution Trace"):

        render_agent_trace(trace)

    if metadata:

        with st.expander("🔍 Execution Details"):

            render_metadata(metadata)


# ============================================================
# SAMPLE PROMPT COMPONENT
# ============================================================

def render_prompt_section(
    title: str,
    description: str,
    prompts: list,
    key_prefix: str,
):

    st.subheader(title)

    st.markdown(description)

    box_class = "prompt-box-sql" if key_prefix == "sql" else "prompt-box-etl"

    for index, prompt in enumerate(prompts):

        st.markdown(
            f"""
            <div class="{box_class}">
                <strong style="color:#000000; font-size:0.95rem;">{prompt}</strong>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.button(
            "💬 Use this prompt",
            key=f"{key_prefix}_{index}",
            on_click=navigate_to_prompt,
            args=(prompt,),
        )


# ============================================================
# DATABASE WORKSPACE COMPONENTS
# ============================================================

def render_database_metrics(metadata):

    col1, col2, col3, col4 = st.columns(4)

    with col1:

        st.metric(
            "Database Tables",
            f"{metadata.get('total_tables', 0):,}",
        )

    with col2:

        st.metric(
            "Total Records",
            f"{metadata.get('total_records', 0):,}",
        )

    with col3:

        st.metric(
            "Database",
            metadata.get("database", "Unknown"),
        )

    with col4:

        st.metric(
            "Schema",
            metadata.get("schema", "Unknown"),
        )


def render_database_tables(metadata):

    tables = metadata.get("tables", [])

    if not tables:

        st.warning(
            "No database tables were returned by the API."
        )

        return

    st.subheader("Database Tables")

    for table in tables:

        table_name = table.get("name", "Unknown")

        row_count = table.get("row_count", 0)

        columns = table.get("columns", [])

        description = TABLE_DESCRIPTIONS.get(
            table_name,
            "Database table.",
        )

        with st.expander(
            f"🗄️ {table_name}  |  "
            f"{row_count:,} records  |  "
            f"{len(columns)} columns"
        ):

            st.markdown(f"**Description:** {description}")

            metric1, metric2 = st.columns(2)

            with metric1:

                st.metric(
                    "Records",
                    f"{row_count:,}",
                )

            with metric2:

                st.metric(
                    "Columns",
                    len(columns),
                )

            if columns:

                st.markdown("**Column Schema**")

                st.dataframe(
                    [
                        {
                            "Column Name": column.get("name"),
                            "Data Type": column.get("data_type"),
                            "Nullable": (
                                "Yes"
                                if column.get("nullable")
                                else "No"
                            ),
                        }
                        for column in columns
                    ],
                    use_container_width=True,
                    hide_index=True,
                )


# ============================================================
# GENERATED FILE WORKSPACE
# ============================================================

def format_file_size(size_bytes: int):

    if size_bytes < 1024:

        return f"{size_bytes} B"

    if size_bytes < 1024 * 1024:

        return f"{size_bytes / 1024:.2f} KB"

    return f"{size_bytes / (1024 * 1024):.2f} MB"


def render_generated_files(files):

    st.subheader("📁 Generated ETL Files")

    st.markdown(
        "Download CSV files created by the ETL Analyst."
    )

    if not files:

        st.info(
            "No generated CSV files are currently available. "
            "Run an ETL task in Chat to create an output file."
        )

        return

    st.write(
        f"**{len(files)} generated file(s) available**"
    )

    for index, file in enumerate(files):

        filename = file.get(
            "filename",
            "Unknown",
        )

        file_id = file.get(
            "file_id",
            "",
        )

        folder = file.get(
            "folder",
            "unknown",
        )

        size_bytes = file.get(
            "size_bytes",
            0,
        )

        modified_timestamp = file.get(
            "modified_at"
        )

        with st.container(border=True):

            col1, col2 = st.columns([3, 1], vertical_alignment="center")

            with col1:

                st.markdown(
                    f"**📄 {filename}**"
                )

                details = [
                    f"Folder: `data/{folder}/`",
                    f"File size: `{format_file_size(size_bytes)}`",
                ]

                if modified_timestamp is not None:

                    modified_time = datetime.fromtimestamp(
                        modified_timestamp
                    )

                    details.append(
                        f"Last modified: `{modified_time.strftime('%d %b %Y, %I:%M %p')}`"
                    )

                st.markdown(" • ".join(details))

            with col2:

                try:

                    file_content = download_generated_file(
                        file_id
                    )

                    st.download_button(
                        label="⬇️ Download CSV",
                        data=file_content,
                        file_name=filename,
                        mime="text/csv",
                        key=f"download_file_{index}_{file_id}",
                        use_container_width=True,
                    )

                except requests.RequestException:

                    st.error(
                        "Download unavailable."
                    )


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:

    st.markdown("## 🤖 AI Data Agent")

    st.markdown(
        "**Powered by Groq, LangGraph & Supabase**"
    )

    st.divider()

    st.subheader("Backend Status")

    if st.button(
        "🔄 Check API Connection",
        use_container_width=True,
    ):

        st.session_state.api_status = (
            check_api_connection()
        )

    if st.session_state.api_status is None:

        st.info("Check the backend connection.")

    elif st.session_state.api_status:

        st.success("Backend connected")

    else:

        st.error("Backend unavailable")

    st.divider()

    st.subheader("AI Agents")

    st.markdown(
        """
        <div class="agent-card-main">
            <div class="agent-card-title">1. Main Data Agent</div>
            <p class="agent-card-desc">• Coordinates requests<br>• Controls workflow</p>
        </div>
        <div class="agent-card-sql">
            <div class="agent-card-title">2. SQL Analyst</div>
            <p class="agent-card-desc">• Database queries<br>• Aggregations and reports</p>
        </div>
        <div class="agent-card-etl">
            <div class="agent-card-title">3. ETL Analyst</div>
            <p class="agent-card-desc">• API extraction<br>• Data transformation & files</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.divider()

    if st.button(
        "🗑️ Clear Conversation",
        use_container_width=True,
    ):

        clear_conversation()

        st.rerun()

    st.markdown("**AI Data Agent | Version 1.4**")


# ============================================================
# APPLICATION HEADER
# ============================================================

st.markdown(
    """
    <div class="hero-banner">
        <div class="hero-title">🤖 AI Data Agent</div>
        <p class="hero-subtitle">
            Your intelligent multi-agent data workspace. Analyze database records, extract external data, and transform datasets using natural language.
        </p>
    </div>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# APPLICATION NAVIGATION
# ============================================================

pages = [
    "Chat",
    "Documentation",
    "Data Workspace",
    "Agent Architecture",
]

st.radio(
    "Application Navigation",
    pages,
    horizontal=True,
    key="active_page",
    label_visibility="collapsed",
)

page = st.session_state.active_page

st.markdown("<div style='margin-bottom: 1rem;'></div>", unsafe_allow_html=True)


# ============================================================
# CHAT PAGE
# ============================================================

if page == "Chat":

    st.subheader("💬 Ask your Data Agent")

    st.markdown(
        "Ask database questions or provide instructions for extracting and transforming datasets."
    )

    # Display conversation history.
    for message in st.session_state.messages:

        with st.chat_message(message["role"]):

            st.markdown(message["content"])

            if message["role"] == "assistant":

                render_assistant_details(message)

    if not st.session_state.messages:

        st.info(
            "Welcome! Ask your first question below or try one of the quick-start examples."
        )

        col1, col2 = st.columns(2)

        with col1:

            st.markdown(
                f"""
                <div class="prompt-box-sql">
                    <div style="font-weight:700; color:#1D4ED8; margin-bottom:4px;">🗄️ SQL Example</div>
                    <div style="color:#000000; font-weight:500;">{SQL_PROMPTS[0]}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            st.button(
                "Use SQL Example",
                key="quick_sql_btn",
                on_click=navigate_to_prompt,
                args=(SQL_PROMPTS[0],),
                use_container_width=True,
            )

        with col2:

            st.markdown(
                f"""
                <div class="prompt-box-etl">
                    <div style="font-weight:700; color:#047857; margin-bottom:4px;">🔄 ETL Example</div>
                    <div style="color:#000000; font-weight:500;">{ETL_PROMPTS[0]}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            st.button(
                "Use ETL Example",
                key="quick_etl_btn",
                on_click=navigate_to_prompt,
                args=(ETL_PROMPTS[0],),
                use_container_width=True,
            )

    st.divider()

    with st.container(border=True):

        st.subheader("Ask a question")

        st.text_area(
            "Your question",
            key="chat_input_widget",
            height=100,
            placeholder=(
                "Ask a database question or give an ETL instruction..."
            ),
        )

        st.button(
            "🚀 Run Agent",
            type="primary",
            use_container_width=True,
            on_click=submit_question,
        )

    if st.session_state.submission_error:

        st.warning(
            st.session_state.submission_error
        )


# ============================================================
# DOCUMENTATION PAGE
# ============================================================

elif page == "Documentation":

    st.subheader("📚 Documentation & User Guide")

    st.markdown(
        "Welcome to **AI Data Agent**! This guide explains the system, available agents, connected data sources, and example prompts."
    )

    with st.expander(
        "1. Getting Started",
        expanded=True,
    ):

        st.markdown(
            """
            ### How to use the application

1. Ensure the backend is running.
2. Open the Chat page.
3. Enter a question in natural language.
4. The Main Data Agent receives your request.
5. The Router selects a specialist.
6. Review the answer and execution details.

            You do not need to write SQL or Python for supported requests.
            """
        )

    with st.expander("2. Meet the Three AI Agents"):

        col1, col2, col3 = st.columns(3)

        with col1:
            st.markdown(
                """
                <div class="agent-card-main">
                    <div class="agent-card-title" style="font-size:1.05rem;">🧠 Main Data Agent</div>
                    <p class="agent-card-desc" style="font-size:0.9rem; margin-top:6px;">
                        Central orchestrator of the system.<br><br>
                        • Receives user requests.<br>
                        • Coordinates the workflow.<br>
                        • Uses the router to select a specialist.
                    </p>
                </div>
                """,
                unsafe_allow_html=True,
            )

        with col2:
            st.markdown(
                """
                <div class="agent-card-sql">
                    <div class="agent-card-title" style="font-size:1.05rem;">🗄️ SQL Analyst</div>
                    <p class="agent-card-desc" style="font-size:0.9rem; margin-top:6px;">
                        Handles existing database records.<br><br>
                        • Generates SQL queries.<br>
                        • Validates SQL safety.<br>
                        • Executes database queries.<br>
                        • Explains analytical results.
                    </p>
                </div>
                """,
                unsafe_allow_html=True,
            )

        with col3:
            st.markdown(
                """
                <div class="agent-card-etl">
                    <div class="agent-card-title" style="font-size:1.05rem;">🔄 ETL Analyst</div>
                    <p class="agent-card-desc" style="font-size:0.9rem; margin-top:6px;">
                        Handles extraction and transformation.<br><br>
                        • Extracts data from APIs.<br>
                        • Processes CSV and JSON files.<br>
                        • Transforms and cleans datasets.<br>
                        • Saves output files.
                    </p>
                </div>
                """,
                unsafe_allow_html=True,
            )

    with st.expander(
        "3. SQL Analyst – Example Prompts",
        expanded=True,
    ):

        render_prompt_section(
            "Database Analysis",
            "These prompts use the connected Supabase PostgreSQL database.",
            SQL_PROMPTS,
            "sql",
        )

    with st.expander(
        "4. ETL Analyst – Example Prompts",
        expanded=True,
    ):

        render_prompt_section(
            "Data Extraction and Transformation",
            "These prompts demonstrate API extraction and file processing.",
            ETL_PROMPTS,
            "etl",
        )

    with st.expander("5. How Agent Communication Works"):

        st.markdown(
            """
            ```text
                       USER REQUEST
                            |
                            v
                      MAIN DATA AGENT
                            |
                            v
                           ROUTER
                            |
                   +--------+--------+
                   |                 |
                   v                 v
               SQL ANALYST       ETL ANALYST
                   |                 |
                   v                 v
              SUPABASE DB       DATA SOURCES
                   |                 |
                   +--------+--------+
                            |
                            v
                      FINAL RESPONSE
            ```

            The Main Data Agent coordinates the request.
            The Router selects one specialist for each request.

            Both specialist agents do not automatically execute together.
            """
        )

    with st.expander("6. Tips for Writing Better Prompts"):

        st.markdown(
            """
- Clearly identify the information you need.
- Mention filters, sorting, grouping, or limits.
- For ETL, provide the source file or API endpoint.
- Specify the output format and destination.
- Start with one clear task at a time.

            **Example SQL prompt:**
            Show the top 5 cities by user count in descending order.

            **Example ETL prompt:**
            Extract the first 20 Pokémon from the API and save their names and URLs in a CSV file.
            """
        )

    with st.expander("7. Current System Scope and Limitations"):

        st.markdown(
            """
- SQL requests operate on the connected database.
- ETL requests use supported files and data sources.
- The router currently chooses one specialist per request.
- Execution traces are displayed after processing.
- Live streaming status updates are not implemented yet.
- Database metadata is fetched from the live backend.
- Generated CSV files are listed from approved output folders.
            """
        )


# ============================================================
# DATA WORKSPACE PAGE
# ============================================================

elif page == "Data Workspace":

    st.subheader("🗄️ Data Workspace")

    st.markdown(
        "Explore your live Supabase PostgreSQL database and download generated ETL files."
    )

    # --------------------------------------------------------
    # REFRESH CONTROLS
    # --------------------------------------------------------

    col1, col2 = st.columns([3, 1], vertical_alignment="center")

    with col1:

        st.markdown(
            "Database metadata and generated files are retrieved directly from the FastAPI backend."
        )

    with col2:

        if st.button(
            "🔄 Refresh Workspace",
            type="primary",
            use_container_width=True,
        ):

            refresh_workspace()

    # Automatically load workspace data when not available.
    if (
        st.session_state.database_metadata is None
        or st.session_state.generated_files is None
    ):

        with st.spinner(
            "Fetching live database information..."
        ):

            refresh_workspace()

    # --------------------------------------------------------
    # ERROR HANDLING
    # --------------------------------------------------------

    if st.session_state.workspace_error:

        st.error(
            st.session_state.workspace_error
        )

        st.info(
            "Make sure FastAPI is running at "
            f"{API_URL} and try refreshing."
        )

    metadata = st.session_state.database_metadata

    files = st.session_state.generated_files

    # --------------------------------------------------------
    # LIVE DATABASE INFORMATION
    # --------------------------------------------------------

    if metadata:

        st.divider()

        st.subheader("📊 Live Database Overview")

        if metadata.get("status") == "connected":

            st.success(
                "Successfully connected to Supabase PostgreSQL."
            )

        render_database_metrics(metadata)

        if st.session_state.last_metadata_refresh:

            st.markdown(
                f"**Last refreshed:** {st.session_state.last_metadata_refresh}"
            )

        st.divider()

        st.subheader("🔗 Database Connection")

        with st.container(border=True):

            col1, col2 = st.columns(2)

            with col1:

                st.markdown(
                    f"**Database:** `{metadata.get('database', 'Unknown')}`"
                )

                st.markdown(
                    f"**Schema:** `{metadata.get('schema', 'Unknown')}`"
                )

            with col2:

                st.markdown(
                    "**Database provider:** Supabase PostgreSQL"
                )

                st.markdown(
                    "**Metadata source:** Live API response"
                )

        st.divider()

        render_database_tables(metadata)

    else:

        st.warning(
            "Database metadata is currently unavailable."
        )

    # --------------------------------------------------------
    # GENERATED FILES
    # --------------------------------------------------------

    st.divider()

    if files is not None:

        render_generated_files(files)

    else:

        st.info(
            "Generated file information is currently unavailable."
        )

    # --------------------------------------------------------
    # ADDITIONAL DATA SOURCES
    # --------------------------------------------------------

    st.divider()

    st.subheader("Additional Data Sources")

    col1, col2 = st.columns(2)

    with col1:

        st.markdown(
            """
            <div class="prompt-box-sql">
                <strong style="font-size:1rem;">🌐 External APIs</strong><br>
                <span>ETL Analyst can extract data from supported APIs, such as the Pokémon API.</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col2:

        st.markdown(
            """
            <div class="prompt-box-etl">
                <strong style="font-size:1rem;">📂 Local Files</strong><br>
                <span>ETL Analyst can process supported CSV, JSON, and Parquet files.</span>
            </div>
            """,
            unsafe_allow_html=True,
        )


# ============================================================
# AGENT ARCHITECTURE PAGE
# ============================================================

elif page == "Agent Architecture":

    st.subheader("⚙️ Multi-Agent Architecture")

    st.markdown(
        "Understand how the AI agents process a request."
    )

    st.subheader("Agent 1 – Main Data Agent")

    st.markdown(
        """
        <div class="agent-card-main" style="padding:16px 20px;">
            <div class="agent-card-title" style="font-size:1.15rem;">🧠 Main Data Agent</div>
            <p class="agent-card-desc" style="font-size:0.95rem; margin-top:4px;">
                Central orchestrator that receives user requests and coordinates the workflow.<br>
                <strong>Technology:</strong> LangGraph
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.subheader("Router")

    st.markdown(
        """
        <div style="background-color:#FFFBEB; border-left:4px solid #F59E0B; border-radius:8px; padding:16px 20px; margin-bottom:12px;">
            <div class="agent-card-title" style="font-size:1.15rem;">🔀 Request Router</div>
            <p class="agent-card-desc" style="font-size:0.95rem; margin-top:4px;">
                Classifies the request and selects the appropriate specialist.<br>
                <strong>Available routes:</strong> SQL and ETL
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col1, col2 = st.columns(2)

    with col1:

        st.markdown(
            """
            <div class="agent-card-sql" style="padding:16px 20px;">
                <div class="agent-card-title" style="font-size:1.1rem;">🗄️ SQL Analyst</div>
                <p class="agent-card-desc" style="font-size:0.92rem; margin-top:6px;">
                    • Generates SQL queries.<br>
                    • Validates query safety.<br>
                    • Queries Supabase PostgreSQL.<br>
                    • Returns analytical results.
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col2:

        st.markdown(
            """
            <div class="agent-card-etl" style="padding:16px 20px;">
                <div class="agent-card-title" style="font-size:1.1rem;">🔄 ETL Analyst</div>
                <p class="agent-card-desc" style="font-size:0.92rem; margin-top:6px;">
                    • Extracts data.<br>
                    • Transforms datasets.<br>
                    • Cleans and processes files.<br>
                    • Saves output files.
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.divider()

    st.subheader("Technology Stack")

    col1, col2, col3 = st.columns(3)

    with col1:

        with st.container(border=True):
            st.markdown("**AI & Orchestration**")
            st.write("• Groq")
            st.write("• LangChain")
            st.write("• LangGraph")

    with col2:

        with st.container(border=True):
            st.markdown("**Backend & Database**")
            st.write("• FastAPI")
            st.write("• PostgreSQL")
            st.write("• Supabase")

    with col3:

        with st.container(border=True):
            st.markdown("**Frontend & Language**")
            st.write("• Streamlit")
            st.write("• Python")
            st.write("• Pandas")


# ============================================================
# FOOTER
# ============================================================

st.divider()

st.markdown(
    "**AI Data Agent** | Built with Python, Groq, LangGraph, FastAPI, Streamlit and Supabase"
)