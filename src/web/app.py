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

    @app.get("/api/transactions/{tx_id}")
    async def get_transaction(tx_id: int, _auth=Depends(require_auth)):
        tx = storage.get_transaction(tx_id)
        if not tx:
            raise HTTPException(status_code=404, detail="Transaction not found")
        return tx

    @app.put("/api/transactions/{tx_id}")
    async def update_transaction(tx_id: int, request: Request, _auth=Depends(require_auth)):
        tx = storage.get_transaction(tx_id)
        if not tx:
            raise HTTPException(status_code=404, detail="Transaction not found")
        body = await request.json()
        allowed = {"merchant", "amount", "currency", "exchange_rate", "category", "description", "transaction_date", "type"}
        fields = {k: v for k, v in body.items() if k in allowed}
        if not fields:
            raise HTTPException(status_code=400, detail="No valid fields to update")
        storage.update_transaction(tx_id, **fields)
        return {"status": "ok"}

    @app.delete("/api/transactions/{tx_id}")
    async def delete_transaction(tx_id: int, _auth=Depends(require_auth)):
        tx = storage.get_transaction(tx_id)
        if not tx:
            raise HTTPException(status_code=404, detail="Transaction not found")
        storage.delete_transaction(tx_id)
        return {"status": "ok"}

    @app.get("/api/categories")
    async def categories(_auth=Depends(require_auth)):
        return storage.get_categories()

    @app.post("/api/categories")
    async def create_category(request: Request, _auth=Depends(require_auth)):
        body = await request.json()
        name = body.get("name", "").strip()
        keywords = body.get("keywords", "")
        icon = body.get("icon", "📌")
        if not name:
            raise HTTPException(status_code=400, detail="Category name is required")
        try:
            storage.add_category(name, keywords, icon)
        except ValueError as e:
            raise HTTPException(status_code=409, detail=str(e))
        return {"status": "ok", "name": name}

    @app.put("/api/categories/{name}")
    async def update_category(name: str, request: Request, _auth=Depends(require_auth)):
        body = await request.json()
        keywords = body.get("keywords", "")
        try:
            storage.update_category(name, keywords)
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))
        return {"status": "ok", "name": name}

    @app.delete("/api/categories/{name}")
    async def delete_category(name: str, _auth=Depends(require_auth)):
        try:
            count = storage.delete_category(name)
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))
        return {"status": "ok", "reassigned": count}

    @app.get("/api/merchant-overrides")
    async def merchant_overrides(_auth=Depends(require_auth)):
        overrides = storage.get_merchant_overrides()
        return [{"merchant": m, "category": c} for m, c in overrides.items()]

    @app.delete("/api/merchant-overrides/{merchant}")
    async def remove_merchant_override(merchant: str, _auth=Depends(require_auth)):
        storage.remove_merchant_override(merchant)
        return {"status": "ok"}

    @app.get("/api/balance")
    async def balance(start_date: Optional[str] = None, end_date: Optional[str] = None, _auth=Depends(require_auth)):
        today = datetime.now()
        start = start_date or f"{today.year}-{today.month:02d}-01"
        end = end_date or today.strftime("%Y-%m-%d")
        return storage.get_balance(start, end)

    @app.get("/api/income-vs-expense")
    async def income_vs_expense(months: int = 6, _auth=Depends(require_auth)):
        today = datetime.now()
        results = []
        for i in range(months):
            m = today.month - i
            y = today.year
            while m <= 0:
                m += 12
                y -= 1
            m_start = f"{y}-{m:02d}-01"
            if m == 12:
                m_end = f"{y+1}-01-01"
            else:
                m_end = f"{y}-{m+1:02d}-01"
            b = storage.get_balance(m_start, m_end)
            results.append({"month": m_start[:7], "income": b["income"], "expenses": b["expenses"]})
        return list(reversed(results))

    @app.get("/api/trend")
    async def trend(start_date: Optional[str] = None, end_date: Optional[str] = None, _auth=Depends(require_auth)):
        today = datetime.now()
        start = start_date or f"{today.year}-{today.month:02d}-01"
        end = end_date or today.strftime("%Y-%m-%d")
        return storage.get_trend(start, end)

    @app.get("/api/merchants")
    async def merchants(start_date: Optional[str] = None, end_date: Optional[str] = None, _auth=Depends(require_auth)):
        today = datetime.now()
        start = start_date or f"{today.year}-{today.month:02d}-01"
        end = end_date or today.strftime("%Y-%m-%d")
        rows = storage.conn.execute(
            "SELECT DISTINCT merchant FROM transactions WHERE DATE(transaction_date) >= ? AND DATE(transaction_date) <= ? AND merchant IS NOT NULL ORDER BY merchant",
            (start, end),
        ).fetchall()
        return [r["merchant"] for r in rows]

    @app.get("/api/insights")
    async def insights(start_date: Optional[str] = None, end_date: Optional[str] = None, _auth=Depends(require_auth)):
        today = datetime.now()
        start = start_date or f"{today.year}-{today.month:02d}-01"
        end = end_date or today.strftime("%Y-%m-%d")
        return {
            "merchants": storage.get_merchant_ranking(start, end),
            "average_daily": storage.get_average_daily(start, end),
        }

    @app.get("/api/recurring")
    async def recurring(_auth=Depends(require_auth)):
        rows = storage.conn.execute(
            "SELECT * FROM recurring_transactions ORDER BY avg_amount DESC"
        ).fetchall()
        return [dict(r) for r in rows]

    @app.get("/settings", response_class=HTMLResponse)
    async def settings_page():
        return (STATIC_DIR / "settings.html").read_text()

    return app
