import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Request, Response, HTTPException, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse

from src.storage import Storage
from src.web.auth import verify_password, create_session, verify_session

logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).parent / "static"


def create_dashboard_app(storage: Storage, password_hash: str) -> FastAPI:
    app = FastAPI(title="Expense Tracker Dashboard")

    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    @app.post("/api/login")
    async def login(request: Request):
        body = await request.json()
        password = body.get("password", "")
        if not verify_password(password, password_hash):
            raise HTTPException(status_code=401, detail="Invalid password")
        token = create_session()
        response = JSONResponse({"status": "ok"})
        response.set_cookie(
            key="session",
            value=token,
            httponly=True,
            max_age=86400 * 30,
        )
        return response

    async def require_auth(request: Request):
        session = request.cookies.get("session")
        if not session or not verify_session(session):
            raise HTTPException(status_code=401, detail="Not authenticated")

    @app.get("/", response_class=HTMLResponse)
    async def index():
        return (STATIC_DIR / "index.html").read_text()

    @app.get("/api/summary")
    async def summary(
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        _auth=Depends(require_auth),
    ):
        today = datetime.now()
        start = start_date or f"{today.year}-{today.month:02d}-01"
        end = end_date or today.strftime("%Y-%m-%d")
        return storage.get_spending_summary(start_date=start, end_date=end)

    @app.get("/api/transactions")
    async def transactions(
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        category: Optional[str] = None,
        merchant_search: Optional[str] = None,
        limit: int = 50,
        _auth=Depends(require_auth),
    ):
        return storage.query_transactions(
            start_date=start_date,
            end_date=end_date,
            category=category,
            merchant_search=merchant_search,
            limit=limit,
        )

    @app.get("/api/categories")
    async def categories(_auth=Depends(require_auth)):
        return storage.get_categories()

    return app
