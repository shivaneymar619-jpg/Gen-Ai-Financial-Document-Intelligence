"""Dev launcher for the FinDocAI full-stack app.

Usage:  python run.py          # serves on http://localhost:8000
"""
import uvicorn

if __name__ == "__main__":
    uvicorn.run("backend.app.main:app", host="0.0.0.0", port=8000, reload=True)
