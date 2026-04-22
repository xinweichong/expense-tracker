import logging
import os
import uuid
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, Request, Response, HTTPException, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, FileResponse

from src.storage import Storage
from src.web.auth import verify_password, create_session, verify_session
from src.analytics import (
    get_period_comparison,
    get_category_comparison,
    get_top_merchants as get_top_merchants_analytics,
    get_merchant_trend,
    get_spending_velocity,
    get_anomalies,
    check_new_merchants,
    generate_summary,
    load_summary,
)

logger = logging.getLogger(__name__)

SUMMARY_CACHE_DIR = os.environ.get(
    "SUMMARY_CACHE_DIR",
    os.path.join(os.path.dirname(__file__), "..", "data", "summaries")
)


def create_dashboard_app(storage: Storage, password_hash: str) -> FastAPI:
    app = FastAPI(title="Expense Tracker Dashboard")

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
        merchant: Optional[str] = None,  # alias used by frontend
        limit: int = 50,
        offset: int = 0,
        _auth=Depends(require_auth),
    ):
        return storage.query_transactions(
            start_date=start_date,
            end_date=end_date,
            category=category,
            merchant_search=merchant_search or merchant,
            limit=limit,
            offset=offset,
        )

    @app.get("/api/transactions/{tx_id}")
    async def get_transaction(tx_id: int, _auth=Depends(require_auth)):
        tx = storage.get_transaction(tx_id)
        if not tx:
            raise HTTPException(status_code=404, detail="Transaction not found")
        return tx

    @app.post("/api/transactions")
    async def create_transaction(request: Request, _auth=Depends(require_auth)):
        body = await request.json()
        amount = body.get("amount")
        if amount is None:
            raise HTTPException(status_code=400, detail="amount is required")
        try:
            amount = float(amount)
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="amount must be a number")

        tx_type = body.get("type", "expense")
        if tx_type not in ("expense", "income"):
            raise HTTPException(status_code=400, detail="type must be 'expense' or 'income'")

        source = body.get("source", "manual")
        source_id = f"manual_{uuid.uuid4().hex[:12]}"
        merchant = body.get("merchant")
        description = body.get("description")
        category = body.get("category")
        currency = body.get("currency", "SGD")
        exchange_rate = body.get("exchange_rate", 1.0)
        transaction_date = body.get("transaction_date") or datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        try:
            tx_id = storage.insert_transaction(
                source=source,
                source_id=source_id,
                amount=amount,
                merchant=merchant,
                description=description,
                category=category,
                currency=currency,
                exchange_rate=exchange_rate,
                transaction_date=transaction_date,
                tx_type=tx_type,
            )
        except ValueError as e:
            raise HTTPException(status_code=409, detail=str(e))

        return storage.get_transaction(tx_id)

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
        # Auto-learn merchant override when category changes
        if "category" in fields and fields["category"] != tx.get("category"):
            merchant = fields.get("merchant") or tx.get("merchant")
            if merchant:
                storage.set_merchant_override(merchant, fields["category"])
        return storage.get_transaction(tx_id)

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
        color = body.get("color")
        if not name:
            raise HTTPException(status_code=400, detail="Category name is required")
        try:
            storage.add_category(name, keywords, icon, color)
        except ValueError as e:
            raise HTTPException(status_code=409, detail=str(e))
        return {"status": "ok", "name": name}

    @app.put("/api/categories/{name}")
    async def update_category(name: str, request: Request, _auth=Depends(require_auth)):
        body = await request.json()
        try:
            storage.update_category(
                name,
                keywords=body.get("keywords"),
                icon=body.get("icon"),
                color=body.get("color"),
            )
        except ValueError as e:
            status_code = 409 if "already used" in str(e) else 404
            raise HTTPException(status_code=status_code, detail=str(e))
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

    @app.get("/api/analytics/comparison")
    async def analytics_comparison(
        period: str = "month",
        date: Optional[str] = None,
        _auth=Depends(require_auth),
    ):
        overall = get_period_comparison(storage.conn, period, date)
        categories = get_category_comparison(storage.conn, period, date)
        return {"overall": overall, "categories": categories}


    @app.get("/api/analytics/merchants")
    async def analytics_merchants(
        limit: int = 10,
        merchant: Optional[str] = None,
        _auth=Depends(require_auth),
    ):
        top = get_top_merchants_analytics(storage.conn, limit)
        trend = get_merchant_trend(storage.conn, merchant) if merchant else None
        return {"top": top, "trend": trend}


    @app.get("/api/analytics/velocity")
    async def analytics_velocity(_auth=Depends(require_auth)):
        return get_spending_velocity(storage.conn)


    @app.get("/api/analytics/alerts")
    async def analytics_alerts(_auth=Depends(require_auth)):
        return {
            "anomalies": get_anomalies(storage.conn),
            "new_merchants": check_new_merchants(storage.conn),
        }


    @app.get("/api/analytics/summaries")
    async def analytics_summaries(_auth=Depends(require_auth)):
        monthly = load_summary(SUMMARY_CACHE_DIR, "monthly")
        weekly = load_summary(SUMMARY_CACHE_DIR, "weekly")
        return {"monthly": monthly, "weekly": weekly}


    # Serve React SPA

    static_dist = os.path.join(os.path.dirname(__file__), "dist")
    if os.path.isdir(static_dist):
        app.mount(
            "/assets",
            StaticFiles(directory=os.path.join(static_dist, "assets")),
            name="spa_assets",
        )

        @app.get("/{full_path:path}")
        async def serve_spa(full_path: str):
            file_path = os.path.join(static_dist, full_path)
            if os.path.isfile(file_path) and not full_path.startswith("api"):
                return FileResponse(file_path)
            return FileResponse(os.path.join(static_dist, "index.html"))

    return app
