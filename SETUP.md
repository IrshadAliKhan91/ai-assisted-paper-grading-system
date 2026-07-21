# FairMark Setup Guide - AI Paper Checking System

This guide outlines the steps to set up the FairMark project on a new PC or laptop.

## Prerequisites

Before starting, ensure you have the following installed:

1.  **Python** (3.10 or higher recommended) - [Download Python](https://www.python.org/downloads/)
2.  **Node.js** (LTS version recommended) - [Download Node.js](https://nodejs.org/)
3.  **PostgreSQL** (Active and running) - [Download PostgreSQL](https://www.postgresql.org/download/)
    *   *During installation, remember the password you set for the `postgres` user.*

---

## Step 1: Clone or Copy the Project

Copy the entire project folder to your new machine.
Open a terminal (Command Prompt or PowerShell) and navigate to the project root directory:

```powershell
cd path\to\FairMark-Ai-Based-Paper-Checking-System
```

---

## Step 2: Database Setup

1.  **Start PostgreSQL**: Ensure your PostgreSQL service is running.
2.  **Create `.env` file**: 
    Navigate to the `backend` folder and create a file named `.env`.
    Add the following content (update with your actual PostgreSQL password context):

    ```env
    # Format: postgresql://user:password@host/dbname
    DATABASE_URL=postgresql://postgres:YOUR_PASSWORD_HERE@localhost/FairMark_db
    ```
    *Replace `YOUR_PASSWORD_HERE` with your actual Postgres password.*

3.  **Run the Database Setup Script**:
    With PostgreSQL running, run the setup script. It will (1) create the
    `FairMark_db` database if it doesn't exist, (2) apply the schema via Alembic
    migrations, and (3) seed reference data:

    ```powershell
    python backend/create_db.py
    ```
    *If successful, you will see "Database ... created" (or "already exists"),
    "Migrations applied successfully", and "Database setup complete".*

    > **Note:** The PostgreSQL driver (`psycopg2-binary`) is installed by
    > `pip install -r requirements.txt` in Step 3. If you run `create_db.py`
    > before installing requirements, either install it first or create the
    > database manually with `createdb FairMark_db`.

---

## Step 3: Backend Setup (FastAPI)

1.  **Navigate to backend directory**:
    ```powershell
    cd backend
    ```

2.  **Create a Virtual Environment** (Recommended):
    ```powershell
    python -m venv venv
    ```

3.  **Activate Virtual Environment**:
    *   Windows: `.\venv\Scripts\activate`
    *   Mac/Linux: `source venv/bin/activate`

4.  **Install Dependencies**:
    ```powershell
    pip install -r requirements.txt
    ```

5.  **Run the Backend Server**:
    start the server using `uvicorn`. It will run on `http://localhost:8000`.
    ```powershell
    uvicorn app.main:app --reload
    ```
    *Keep this terminal window open.*

---

## Step 4: Frontend Setup (React)

1.  **Open a new terminal window** and navigate to the frontend app directory:
    ```powershell
    cd frontend\my-app
    ```

2.  **Install Node Modules**:
    ```powershell
    npm install
    ```
    *This might take a few minutes.*

3.  **Start the Frontend Development Server**:
    ```powershell
    npm start
    ```
    *This will open the application in your browser, typically at `http://localhost:3000`.*

---

## Troubleshooting

-   **Database Connection Error**: Double-check your `.env` file password and ensure PostgreSQL service is running.
-   **Module Not Found**: Ensure you have activated the virtual environment and installed requirements.
-   **Port Confilcts**: If port 8000 or 3000 is busy, kill the process using that port or verify no other instances are running.
