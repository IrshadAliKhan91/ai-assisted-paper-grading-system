import os
import subprocess
from pathlib import Path
from urllib.parse import urlparse, unquote

from dotenv import load_dotenv


def _ensure_database_exists():
    """Create the target PostgreSQL database if it doesn't exist yet.

    Alembic can create *tables* but not the database itself, so on a brand-new
    Postgres install `alembic upgrade head` would fail to connect. This connects
    to the maintenance `postgres` database and issues a safe CREATE DATABASE.

    Uses psycopg2.sql.Identifier so the database name can never be SQL-injected
    (this was the old create_db.py f-string vulnerability, C-2).
    SQLite needs no server-side database creation, so it's skipped.
    """
    backend_dir = Path(__file__).parent
    load_dotenv(dotenv_path=backend_dir / ".env")

    url = os.getenv("DATABASE_URL", "")
    if not url or url.startswith("sqlite"):
        print("SQLite or no DATABASE_URL — skipping database creation.")
        return

    parsed = urlparse(url)
    db_name = parsed.path.lstrip("/")
    if not db_name:
        print("DATABASE_URL has no database name — skipping creation.")
        return

    try:
        import psycopg2
        from psycopg2 import sql
        from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
    except ImportError:
        print(
            "psycopg2 is not installed. Run `pip install -r requirements.txt`, "
            "or create the database manually: createdb "
            f"{db_name}"
        )
        return

    conn = psycopg2.connect(
        dbname="postgres",  # maintenance DB that always exists
        user=unquote(parsed.username or "postgres"),
        password=unquote(parsed.password or ""),
        host=parsed.hostname or "localhost",
        port=parsed.port or 5432,
    )
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (db_name,))
            if cur.fetchone():
                print(f"Database '{db_name}' already exists.")
            else:
                cur.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(db_name)))
                print(f"Database '{db_name}' created.")
    finally:
        conn.close()


def create_database():
    try:
        backend_dir = Path(__file__).parent
        python_exe = backend_dir / "venv" / "Scripts" / "python.exe"
        if not python_exe.exists():
            python_exe = "python"  # fallback to PATH

        # 1. Create the database (no-op if it already exists / SQLite).
        _ensure_database_exists()

        # 2. Apply the schema via Alembic migrations.
        print("Running database migrations...")
        subprocess.run(
            [str(python_exe), "-m", "alembic", "upgrade", "head"],
            cwd=str(backend_dir),
            check=True,
        )
        print("Migrations applied successfully.")

        # 3. Seed reference data.
        print("Seeding database...")
        seed_script = backend_dir / "seed_data.py"
        subprocess.run([str(python_exe), str(seed_script)], cwd=str(backend_dir), check=True)
        print("Database setup complete.")

    except Exception as e:
        print(f"Error setting up database: {e}")


if __name__ == "__main__":
    create_database()
