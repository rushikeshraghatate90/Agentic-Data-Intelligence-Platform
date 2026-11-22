
import os
from pathlib import Path

import psycopg2
from psycopg2 import sql
from dotenv import load_dotenv

from utils.database import DatabaseUtil


# ============================================================
# CONFIGURATION
# ============================================================

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parent
CSV_DIR = PROJECT_ROOT / "data"

RESET_DATA = (
    os.getenv("RESET_DATA", "false").strip().lower() == "true"
)

TABLES = [
    "users",
    "vehicles",
    "rides",
    "payments",
    "ratings",
]


# ============================================================
# TABLE DEFINITIONS
# ============================================================

CREATE_TABLES_SQL = [

    """
    CREATE SCHEMA IF NOT EXISTS public;
    """,

    """
    CREATE TABLE IF NOT EXISTS public.users (
        user_id INTEGER PRIMARY KEY,
        first_name VARCHAR(100) NOT NULL,
        last_name VARCHAR(100) NOT NULL,
        email VARCHAR(255) NOT NULL UNIQUE,
        phone VARCHAR(50),
        city VARCHAR(100),
        province VARCHAR(50),
        user_type VARCHAR(20) NOT NULL,
        signup_date DATE,
        is_active BOOLEAN
    );
    """,

    """
    CREATE TABLE IF NOT EXISTS public.vehicles (
        vehicle_id INTEGER PRIMARY KEY,
        driver_id INTEGER NOT NULL,
        make VARCHAR(50),
        model VARCHAR(50),
        year INTEGER,
        license_plate VARCHAR(20) UNIQUE,
        color VARCHAR(30),
        is_active BOOLEAN,

        CONSTRAINT fk_vehicle_driver
            FOREIGN KEY (driver_id)
            REFERENCES public.users(user_id)
    );
    """,

    """
    CREATE TABLE IF NOT EXISTS public.rides (
        ride_id INTEGER PRIMARY KEY,
        rider_id INTEGER NOT NULL,
        driver_id INTEGER NOT NULL,
        requested_at TIMESTAMP,
        pickup_time TIMESTAMP,
        dropoff_time TIMESTAMP,
        pickup_latitude DECIMAL(9,6),
        pickup_longitude DECIMAL(9,6),
        dropoff_latitude DECIMAL(9,6),
        dropoff_longitude DECIMAL(9,6),
        distance_km DECIMAL(10,2),
        fare DECIMAL(10,2),
        surge_multiplier DECIMAL(4,2),
        status VARCHAR(30),
        cancellation_reason VARCHAR(100),

        CONSTRAINT fk_ride_rider
            FOREIGN KEY (rider_id)
            REFERENCES public.users(user_id),

        CONSTRAINT fk_ride_driver
            FOREIGN KEY (driver_id)
            REFERENCES public.users(user_id)
    );
    """,

    """
    CREATE TABLE IF NOT EXISTS public.payments (
        payment_id INTEGER PRIMARY KEY,
        ride_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        amount DECIMAL(10,2),
        payment_method VARCHAR(50),
        payment_status VARCHAR(30),
        transaction_id VARCHAR(100) UNIQUE,
        payment_time TIMESTAMP,

        CONSTRAINT fk_payment_ride
            FOREIGN KEY (ride_id)
            REFERENCES public.rides(ride_id),

        CONSTRAINT fk_payment_user
            FOREIGN KEY (user_id)
            REFERENCES public.users(user_id)
    );
    """,

    """
    CREATE TABLE IF NOT EXISTS public.ratings (
        rating_id INTEGER PRIMARY KEY,
        ride_id INTEGER NOT NULL,
        rider_id INTEGER NOT NULL,
        driver_id INTEGER NOT NULL,
        rating INTEGER,
        comment TEXT,
        rated_at TIMESTAMP,

        CONSTRAINT fk_rating_ride
            FOREIGN KEY (ride_id)
            REFERENCES public.rides(ride_id),

        CONSTRAINT fk_rating_rider
            FOREIGN KEY (rider_id)
            REFERENCES public.users(user_id),

        CONSTRAINT fk_rating_driver
            FOREIGN KEY (driver_id)
            REFERENCES public.users(user_id),

        CONSTRAINT chk_rating
            CHECK (rating BETWEEN 1 AND 5)
    );
    """,

    """
    CREATE INDEX IF NOT EXISTS idx_vehicles_driver_id
    ON public.vehicles(driver_id);
    """,

    """
    CREATE INDEX IF NOT EXISTS idx_rides_rider_id
    ON public.rides(rider_id);
    """,

    """
    CREATE INDEX IF NOT EXISTS idx_rides_driver_id
    ON public.rides(driver_id);
    """,

    """
    CREATE INDEX IF NOT EXISTS idx_rides_requested_at
    ON public.rides(requested_at);
    """,

    """
    CREATE INDEX IF NOT EXISTS idx_rides_status
    ON public.rides(status);
    """,

    """
    CREATE INDEX IF NOT EXISTS idx_payments_ride_id
    ON public.payments(ride_id);
    """,

    """
    CREATE INDEX IF NOT EXISTS idx_payments_user_id
    ON public.payments(user_id);
    """,

    """
    CREATE INDEX IF NOT EXISTS idx_ratings_ride_id
    ON public.ratings(ride_id);
    """,

    """
    CREATE INDEX IF NOT EXISTS idx_ratings_driver_id
    ON public.ratings(driver_id);
    """,
]


# ============================================================
# CSV CONFIGURATION
# ============================================================

CSV_FILES = {
    "users": {
        "file": "users.csv",
        "columns": [
            "user_id",
            "first_name",
            "last_name",
            "email",
            "phone",
            "city",
            "province",
            "user_type",
            "signup_date",
            "is_active",
        ],
    },

    "vehicles": {
        "file": "vehicles.csv",
        "columns": [
            "vehicle_id",
            "driver_id",
            "make",
            "model",
            "year",
            "license_plate",
            "color",
            "is_active",
        ],
    },

    "rides": {
        "file": "rides.csv",
        "columns": [
            "ride_id",
            "rider_id",
            "driver_id",
            "requested_at",
            "pickup_time",
            "dropoff_time",
            "pickup_latitude",
            "pickup_longitude",
            "dropoff_latitude",
            "dropoff_longitude",
            "distance_km",
            "fare",
            "surge_multiplier",
            "status",
            "cancellation_reason",
        ],
    },

    "payments": {
        "file": "payments.csv",
        "columns": [
            "payment_id",
            "ride_id",
            "user_id",
            "amount",
            "payment_method",
            "payment_status",
            "transaction_id",
            "payment_time",
        ],
    },

    "ratings": {
        "file": "ratings.csv",
        "columns": [
            "rating_id",
            "ride_id",
            "rider_id",
            "driver_id",
            "rating",
            "comment",
            "rated_at",
        ],
    },
}


# ============================================================
# VALIDATE CSV FILES
# ============================================================

def validate_csv_files():
    """Check that every required CSV file exists."""

    missing_files = []

    for table_name, config in CSV_FILES.items():

        file_path = CSV_DIR / config["file"]

        if not file_path.is_file():
            missing_files.append(str(file_path))

    if missing_files:
        raise FileNotFoundError(
            "Required CSV files are missing:\n"
            + "\n".join(missing_files)
        )

    print("All required CSV files found.")


# ============================================================
# CREATE TABLES AND INDEXES
# ============================================================

def create_tables(cursor):
    """Create the database schema, tables, and indexes."""

    print("\nCreating database tables...")

    for statement in CREATE_TABLES_SQL:
        cursor.execute(statement)

    print("Tables and indexes created successfully.")


# ============================================================
# CHECK EXISTING RECORDS
# ============================================================

def get_existing_counts(cursor):
    """Retrieve existing record counts from all five tables."""

    existing_counts = {}

    for table_name in TABLES:

        query = sql.SQL(
            "SELECT COUNT(*) FROM {}.{}"
        ).format(
            sql.Identifier("public"),
            sql.Identifier(table_name),
        )

        cursor.execute(query)

        existing_counts[table_name] = cursor.fetchone()[0]

    return existing_counts


# ============================================================
# CLEAR EXISTING DATA
# ============================================================

def clear_existing_data(cursor):
    """
    Clear existing records only when RESET_DATA=true.
    """

    if not RESET_DATA:
        return

    print("\nRESET_DATA=true")
    print("Clearing existing records...")

    cursor.execute(
        """
        TRUNCATE TABLE
            public.ratings,
            public.payments,
            public.rides,
            public.vehicles,
            public.users
        CASCADE;
        """
    )

    print("Existing records cleared.")


# ============================================================
# LOAD CSV DATA
# ============================================================

def load_csv(cursor, table_name, config):
    """
    Load CSV records using PostgreSQL COPY FROM STDIN.
    """

    file_path = CSV_DIR / config["file"]
    columns = config["columns"]

    copy_query = sql.SQL(
        """
        COPY {} ({})
        FROM STDIN
        WITH (
            FORMAT CSV,
            HEADER TRUE,
            DELIMITER ',',
            NULL ''
        )
        """
    ).format(
        sql.Identifier("public", table_name),
        sql.SQL(", ").join(
            sql.Identifier(column)
            for column in columns
        ),
    )

    print(f"\nLoading {config['file']}...")

    with open(
        file_path,
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as csv_file:

        cursor.copy_expert(
            copy_query.as_string(cursor.connection),
            csv_file,
        )

    print(f"{config['file']} loaded successfully.")


# ============================================================
# VERIFY RECORD COUNTS
# ============================================================

def verify_records(cursor):
    """Print record counts for all database tables."""

    print("\nDATABASE RECORD COUNTS")
    print("=" * 45)

    record_counts = {}

    for table_name in TABLES:

        query = sql.SQL(
            "SELECT COUNT(*) FROM {}.{}"
        ).format(
            sql.Identifier("public"),
            sql.Identifier(table_name),
        )

        cursor.execute(query)

        count = cursor.fetchone()[0]

        record_counts[table_name] = count

        print(f"{table_name:<15} {count:>12,}")

    print("=" * 45)

    return record_counts


# ============================================================
# MAIN EXECUTION
# ============================================================

def main():

    connection = None

    try:

        print("AI DATA AGENT - DATABASE SETUP")
        print("=" * 45)

        # Step 1: Validate CSV files.
        validate_csv_files()

        # Step 2: Load Supabase configuration.
        database = DatabaseUtil.from_env()

        print("\nConnecting to PostgreSQL...")

        connection = psycopg2.connect(
            **database.db_config
        )

        connection.autocommit = False

        print("Connected to PostgreSQL successfully.")

        with connection.cursor() as cursor:

            # Step 3: Create tables and indexes.
            create_tables(cursor)

            # Step 4: Check existing records.
            existing_counts = get_existing_counts(cursor)

            print("\nEXISTING DATABASE RECORDS")
            print("=" * 45)

            for table_name, count in existing_counts.items():
                print(f"{table_name:<15} {count:>12,}")

            has_existing_data = any(
                count > 0
                for count in existing_counts.values()
            )

            # Step 5: Prevent accidental duplicate loading.
            if has_existing_data and not RESET_DATA:

                raise RuntimeError(
                    "Existing records were found in the database. "
                    "No records were deleted or loaded. "
                    "Set RESET_DATA=true only if you intentionally "
                    "want to replace all existing records."
                )

            # Step 6: Optional reset.
            clear_existing_data(cursor)

            # Step 7: Load CSV files in foreign-key order.
            for table_name, config in CSV_FILES.items():

                load_csv(
                    cursor,
                    table_name,
                    config,
                )

            # Step 8: Verify imported records.
            verify_records(cursor)

        # Step 9: Commit the transaction.
        connection.commit()

        print("\nData loaded successfully!")
        print("Transaction committed.")

    except Exception as error:

        if connection is not None:
            connection.rollback()

        print("\nDATABASE SETUP FAILED")
        print(f"Error: {error}")
        print("Transaction rolled back.")

        raise

    finally:

        if connection is not None:
            connection.close()

        print("\nDatabase connection closed.")


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()
