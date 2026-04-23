import logging
import os
import uuid
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, Request, Response, HTTPException, Depends
from fastapi.staticfiles import StaticFiles
import csv
import io
from fastapi.responses import JSONResponse, FileResponse, StreamingResponse

from src.config import local_now
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
        today = local_now()
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

    @app.get("/api/transactions/export")
    async def export_transactions(
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        category: Optional[str] = None,
        merchant_search: Optional[str] = None,
        merchant: Optional[str] = None,
        _auth=Depends(require_auth),
    ):
        rows = storage.query_transactions(
            start_date=start_date,
            end_date=end_date,
            category=category,
            merchant_search=merchant_search or merchant,
            limit=50_000,
            offset=0,
        )
        output = io.StringIO()
        fieldnames = ["date", "merchant", "amount", "currency", "exchange_rate",
                      "amount_sgd", "type", "category", "source", "description"]
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        for tx in rows:
            writer.writerow({
                "date": (tx.get("transaction_date") or "")[:10],
                "merchant": tx.get("merchant") or "",
                "amount": tx.get("amount") if tx.get("amount") is not None else "",
                "currency": tx.get("currency") or "SGD",
                "exchange_rate": tx.get("exchange_rate") if tx.get("exchange_rate") is not None else 1.0,
                "amount_sgd": round((tx.get("amount") or 0) * (tx.get("exchange_rate") or 1.0), 2),
                "type": tx.get("type") or "expense",
                "category": tx.get("category") or "",
                "source": tx.get("source") or "",
                "description": tx.get("description") or "",
            })
        output.seek(0)
        filename = f"transactions-{local_now().strftime('%Y-%m-%d')}.csv"
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
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
        transaction_date = body.get("transaction_date") or local_now().strftime("%Y-%m-%d %H:%M:%S")

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

    @app.get("/api/apple-wallet/cards")
    async def apple_wallet_cards(_auth=Depends(require_auth)):
        """Return distinct card names known from Apple Wallet transactions.

        Only returns descriptions that have a real card name — i.e. the format
        'Apple Wallet - <something>' where <something> is non-empty.  Used to
        populate the description dropdown in the transaction edit form.
        """
        rows = storage.conn.execute(
            "SELECT DISTINCT description FROM transactions "
            "WHERE source = 'apple_wallet' "
            "AND description LIKE 'Apple Wallet - _%' "
            "ORDER BY description"
        ).fetchall()
        return [r["description"] for r in rows]

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

    VALID_TAGS = {"online", "subscription", "local", "foreign", "business", "cash-equivalent"}

    @app.get("/api/merchant-intelligence")
    async def merchant_intelligence_list(
        sort_by: str = "total_spent",
        tag: Optional[str] = None,
        category: Optional[str] = None,
        search: Optional[str] = None,
        limit: int = 25,
        offset: int = 0,
        _auth=Depends(require_auth),
    ):
        return storage.get_merchant_list(
            sort_by=sort_by,
            tag_filter=tag,
            category_filter=category,
            name_search=search,
            limit=limit,
            offset=offset,
        )

    @app.get("/api/merchant-intelligence/{merchant}/trend")
    async def merchant_trend(merchant: str, _auth=Depends(require_auth)):
        return storage.get_merchant_trend(merchant)

    @app.put("/api/merchant-intelligence/{merchant}/tags")
    async def merchant_set_tags(merchant: str, request: Request, _auth=Depends(require_auth)):
        body = await request.json()
        tags = body.get("tags", [])
        invalid = [t for t in tags if t not in VALID_TAGS]
        if invalid:
            raise HTTPException(status_code=422, detail=f"Invalid tags: {invalid}. Valid: {sorted(VALID_TAGS)}")
        storage.set_merchant_tags(merchant, tags)
        return storage.get_merchant_tags(merchant)

    @app.put("/api/merchant-intelligence/{merchant}/notes")
    async def merchant_set_notes(merchant: str, request: Request, _auth=Depends(require_auth)):
        body = await request.json()
        notes = body.get("notes", "")
        storage.set_merchant_notes(merchant, notes)
        return storage.get_merchant_tags(merchant)

    @app.get("/api/merchant-intelligence/{merchant}")
    async def merchant_intelligence_profile(merchant: str, _auth=Depends(require_auth)):
        profile = storage.get_merchant_profile(merchant)
        if not profile:
            raise HTTPException(status_code=404, detail="Merchant not found")
        return profile

    @app.get("/api/balance")
    async def balance(start_date: Optional[str] = None, end_date: Optional[str] = None, _auth=Depends(require_auth)):
        today = local_now()
        start = start_date or f"{today.year}-{today.month:02d}-01"
        end = end_date or today.strftime("%Y-%m-%d")
        return storage.get_balance(start, end)

    @app.get("/api/income-vs-expense")
    async def income_vs_expense(months: int = 6, _auth=Depends(require_auth)):
        today = local_now()
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
        today = local_now()
        start = start_date or f"{today.year}-{today.month:02d}-01"
        end = end_date or today.strftime("%Y-%m-%d")
        return storage.get_trend(start, end)

    @app.get("/api/trend/by-category")
    async def trend_by_category(start_date: Optional[str] = None, end_date: Optional[str] = None, _auth=Depends(require_auth)):
        today = local_now()
        start = start_date or f"{today.year}-{today.month:02d}-01"
        end = end_date or today.strftime("%Y-%m-%d")
        return storage.get_trend_by_category(start, end)

    @app.get("/api/merchants")
    async def merchants(start_date: Optional[str] = None, end_date: Optional[str] = None, _auth=Depends(require_auth)):
        today = local_now()
        start = start_date or f"{today.year}-{today.month:02d}-01"
        end = end_date or today.strftime("%Y-%m-%d")
        rows = storage.conn.execute(
            "SELECT DISTINCT merchant FROM transactions WHERE DATE(transaction_date) >= ? AND DATE(transaction_date) <= ? AND merchant IS NOT NULL ORDER BY merchant",
            (start, end),
        ).fetchall()
        return [r["merchant"] for r in rows]

    @app.get("/api/insights")
    async def insights(start_date: Optional[str] = None, end_date: Optional[str] = None, _auth=Depends(require_auth)):
        today = local_now()
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
            "anomalies": get_anomalies(storage.conn, multiplier=float(storage.get_setting("anomaly_multiplier", "2.0"))),
            "new_merchants": check_new_merchants(storage.conn),
        }


    @app.get("/api/analytics/summaries")
    async def analytics_summaries(_auth=Depends(require_auth)):
        monthly = load_summary(SUMMARY_CACHE_DIR, "monthly")
        weekly = load_summary(SUMMARY_CACHE_DIR, "weekly")
        return {"monthly": monthly, "weekly": weekly}


    @app.get("/api/settings")
    async def get_settings(_auth=Depends(require_auth)):
        return {
            "anomaly_multiplier": float(storage.get_setting("anomaly_multiplier", "2.0")),
            "velocity_alert_threshold": int(storage.get_setting("velocity_alert_threshold", "110")),
            "budgets_enabled": storage.get_setting("budgets_enabled", "false") == "true",
            "goals_enabled": storage.get_setting("goals_enabled", "false") == "true",
        }

    @app.put("/api/settings")
    async def update_settings(request: Request, _auth=Depends(require_auth)):
        body = await request.json()
        errors = {}
        validated = {}

        if "anomaly_multiplier" in body:
            val = body["anomaly_multiplier"]
            try:
                val = float(val)
            except (TypeError, ValueError):
                errors["anomaly_multiplier"] = "must be a number"
            else:
                if not (1.0 <= val <= 10.0):
                    errors["anomaly_multiplier"] = "must be between 1.0 and 10.0"
                else:
                    validated["anomaly_multiplier"] = str(val)

        if "velocity_alert_threshold" in body:
            val = body["velocity_alert_threshold"]
            try:
                val = int(val)
            except (TypeError, ValueError):
                errors["velocity_alert_threshold"] = "must be an integer"
            else:
                if not (50 <= val <= 300):
                    errors["velocity_alert_threshold"] = "must be between 50 and 300"
                else:
                    validated["velocity_alert_threshold"] = str(val)

        if errors:
            raise HTTPException(status_code=422, detail=errors)

        if "budgets_enabled" in body:
            val = body["budgets_enabled"]
            if not isinstance(val, bool):
                errors["budgets_enabled"] = "must be a boolean"
            else:
                storage.set_setting("budgets_enabled", "true" if val else "false")

        if "goals_enabled" in body:
            val = body["goals_enabled"]
            if not isinstance(val, bool):
                errors["goals_enabled"] = "must be a boolean"
            else:
                storage.set_setting("goals_enabled", "true" if val else "false")

        if errors:
            raise HTTPException(status_code=422, detail=errors)

        # Write all-or-nothing after validation
        for key, value in validated.items():
            storage.set_setting(key, value)

        return {
            "anomaly_multiplier": float(storage.get_setting("anomaly_multiplier", "2.0")),
            "velocity_alert_threshold": int(storage.get_setting("velocity_alert_threshold", "110")),
            "budgets_enabled": storage.get_setting("budgets_enabled", "false") == "true",
            "goals_enabled": storage.get_setting("goals_enabled", "false") == "true",
        }

    # ── Budgets ──────────────────────────────────────────────────────────

    @app.get("/api/budgets")
    async def list_budgets(_auth=Depends(require_auth)):
        return storage.get_budgets()

    @app.post("/api/budgets")
    async def create_budget(request: Request, _auth=Depends(require_auth)):
        body = await request.json()
        amount = body.get("amount")
        period = body.get("period", "monthly")
        category = body.get("category")  # None = overall
        if amount is None:
            raise HTTPException(status_code=400, detail="amount is required")
        try:
            amount = float(amount)
        except (TypeError, ValueError):
            raise HTTPException(status_code=422, detail="amount must be a number")
        if period not in ("monthly", "weekly"):
            raise HTTPException(status_code=422, detail="period must be 'monthly' or 'weekly'")
        try:
            budget_id = storage.create_budget(category=category, amount=amount, period=period)
        except ValueError as e:
            raise HTTPException(status_code=409, detail=str(e))
        row = storage.conn.execute("SELECT * FROM budgets WHERE id = ?", (budget_id,)).fetchone()
        return dict(row)

    @app.get("/api/budgets/progress")
    async def budget_progress(_auth=Depends(require_auth)):
        return storage.get_budget_progress()

    @app.put("/api/budgets/{budget_id}")
    async def update_budget(budget_id: int, request: Request, _auth=Depends(require_auth)):
        body = await request.json()
        amount = body.get("amount")
        if amount is None:
            raise HTTPException(status_code=400, detail="amount is required")
        try:
            amount = float(amount)
        except (TypeError, ValueError):
            raise HTTPException(status_code=422, detail="amount must be a number")
        try:
            storage.update_budget(budget_id, amount=amount)
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))
        row = storage.conn.execute("SELECT * FROM budgets WHERE id = ?", (budget_id,)).fetchone()
        return dict(row)

    @app.delete("/api/budgets/{budget_id}")
    async def delete_budget(budget_id: int, _auth=Depends(require_auth)):
        try:
            storage.delete_budget(budget_id)
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))
        return {"status": "ok"}

    # ── Goals ──────────────────────────────────────────────────────────────

    @app.get("/api/goals")
    async def list_goals(_auth=Depends(require_auth)):
        goals = storage.get_goals()
        results = []
        for g in goals:
            progress = storage.get_goal_progress(g["id"])
            results.append(progress if progress else g)
        return results

    @app.post("/api/goals")
    async def create_goal(request: Request, _auth=Depends(require_auth)):
        body = await request.json()
        name = body.get("name", "").strip()
        target_amount = body.get("target_amount")
        target_date = body.get("target_date")
        if not name:
            raise HTTPException(status_code=400, detail="name is required")
        if target_amount is None:
            raise HTTPException(status_code=400, detail="target_amount is required")
        try:
            target_amount = float(target_amount)
        except (TypeError, ValueError):
            raise HTTPException(status_code=422, detail="target_amount must be a number")
        goal_id = storage.create_goal(
            name=name, target_amount=target_amount, target_date=target_date
        )
        return storage.get_goal_progress(goal_id)

    @app.put("/api/goals/{goal_id}")
    async def update_goal(goal_id: int, request: Request, _auth=Depends(require_auth)):
        body = await request.json()
        allowed = {"name", "target_amount", "target_date", "status"}
        fields = {k: v for k, v in body.items() if k in allowed}
        if not fields:
            raise HTTPException(status_code=400, detail="No valid fields to update")
        try:
            storage.update_goal(goal_id, **fields)
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))
        return storage.get_goal_progress(goal_id)

    @app.delete("/api/goals/{goal_id}")
    async def delete_goal(goal_id: int, _auth=Depends(require_auth)):
        try:
            storage.delete_goal(goal_id)
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))
        return {"status": "ok"}

    @app.post("/api/goals/{goal_id}/contribute")
    async def contribute_to_goal(goal_id: int, request: Request, _auth=Depends(require_auth)):
        body = await request.json()
        amount = body.get("amount")
        note = body.get("note")
        if amount is None:
            raise HTTPException(status_code=400, detail="amount is required")
        try:
            amount = float(amount)
        except (TypeError, ValueError):
            raise HTTPException(status_code=422, detail="amount must be a number")
        today = local_now()
        try:
            storage.add_contribution(
                goal_id,
                amount=amount,
                month=today.strftime("%Y-%m"),
                contributed_date=today.strftime("%Y-%m-%d"),
                source="manual",
                note=note,
            )
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))
        return storage.get_goal_progress(goal_id)

    @app.get("/api/goals/{goal_id}/contributions")
    async def goal_contributions(goal_id: int, _auth=Depends(require_auth)):
        row = storage.conn.execute("SELECT 1 FROM goals WHERE id = ?", (goal_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Goal not found")
        return storage.get_contributions(goal_id)

    @app.put("/api/goals/{goal_id}/contributions/{contribution_id}")
    async def update_contribution(goal_id: int, contribution_id: int, request: Request, _auth=Depends(require_auth)):
        body = await request.json()
        allowed = {"amount", "note", "contributed_date"}
        fields = {k: v for k, v in body.items() if k in allowed}
        if "amount" in fields:
            try:
                fields["amount"] = float(fields["amount"])
            except (TypeError, ValueError):
                raise HTTPException(status_code=422, detail="amount must be a number")
        try:
            storage.update_contribution(contribution_id, **fields)
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))
        return storage.get_goal_progress(goal_id)

    @app.delete("/api/goals/{goal_id}/contributions/{contribution_id}")
    async def delete_contribution(goal_id: int, contribution_id: int, _auth=Depends(require_auth)):
        try:
            storage.delete_contribution(contribution_id)
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))
        return storage.get_goal_progress(goal_id)

    @app.get("/api/savings/overview")
    async def savings_overview(_auth=Depends(require_auth)):
        month = local_now().strftime("%Y-%m")
        return storage.get_savings_overview(month)

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
