
# Kitty App API

This is a FastAPI-based chat server using Server-Sent Events (SSE) and MySQL.

## Setup

1.  Install the required packages:
    ```
    pip install -r requirements.txt
    ```

2.  Set up your MySQL database and update the `SQLALCHEMY_DATABASE_URL` in `database.py`.

3.  Run the server:
    ```
    uvicorn main:app --reload
    ```
