"""
RetailIQ - AI Sales & Inventory Copilot
NexusTiQ24 Hackathon | Track: PS03 - Retail: Sales and Inventory Copilot
Milestone 5: Integrated Dashboard & Frontend
"""

import os
import sys
from typing import Optional, Dict, Any, List
import uvicorn
from fastapi import FastAPI, Query, HTTPException
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

# Ensure src package is accessible
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")
sys.path.insert(0, BASE_DIR)
from src.analytics import AnalyticsEngine
from src.gemini_client import GeminiClient
from src.retrieval import build_index, retrieve
from src.query_engine import understand_query
from src.evidence import compact_evidence, build_grounding_context

app = FastAPI(
    title="RetailIQ",
    description="AI Sales & Inventory Copilot (NexusTiQ24 PS03)",
    version="1.0.0"
)

# Enable CORS for local testing and future integrations
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount frontend static assets if frontend directory exists
if os.path.exists(FRONTEND_DIR):
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

# Initialize deterministic analytics engine
engine = AnalyticsEngine()

# Initialize Gemini GenAI client
gemini_client = GeminiClient()



@app.get("/", include_in_schema=False)
def serve_dashboard():
    """Serves the main RetailIQ dashboard."""
    index_path = os.path.join(FRONTEND_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {
        "app": "RetailIQ",
        "status": "running",
        "message": "Frontend index.html not found, but backend is running."
    }


@app.get("/api")
def api_info():
    """API metadata and status."""
    return {
        "app": "RetailIQ",
        "track": "PS03 - Retail: Sales and Inventory Copilot",
        "version": "0.5.0",
        "milestone": "Milestone 5 - Frontend Dashboard",
        "status": "running",
        "docs_url": "http://localhost:8000/docs",
        "message": "RetailIQ backend API is operational."
    }


@app.get("/api/health")
def health_check():
    """System health check and loaded dataset verification."""
    return {
        "status": "healthy",
        "python_version": sys.version.split()[0],
        "datasets": {
            "stores_count": len(engine.stores_df),
            "products_count": len(engine.products_df),
            "sales_transactions": len(engine.sales_df),
            "inventory_records": len(engine.inventory_df),
            "date_range": {
                "start": engine.sales_df["date"].min().strftime("%Y-%m-%d") if not engine.sales_df.empty else None,
                "end": engine.sales_df["date"].max().strftime("%Y-%m-%d") if not engine.sales_df.empty else None,
            }
        },
        "gemini": {
            "configured": gemini_client.is_configured(),
            "model": gemini_client.model
        }
    }


@app.get("/api/gemini/status")
def gemini_status():
    """Returns Gemini GenAI configuration and connection availability status."""
    return gemini_client.check_availability()


@app.get("/api/gemini/test")
def gemini_test():
    """
    Development/testing endpoint that sends a fixed micro-prompt to Gemini.
    Does not process or transmit sensitive retail business data.
    """
    result = gemini_client.generate(
        prompt="Respond with exactly: RetailIQ Gemini connection successful."
    )
    return {
        "endpoint": "dev_test",
        "model": gemini_client.model,
        "result": result
    }




class CopilotRequest(BaseModel):
    query: str
    store_id: Optional[str] = None
    days: int = 30


def _analytics_for_intent(intent: str, store_id: Optional[str], days: int) -> Dict[str, Any]:
    if intent == "stockout":
        return {"stockout_risks": engine.get_stockout_risks(store_id=store_id, max_days=7.0)}
    if intent == "overstock":
        return {"overstocked_items": engine.get_overstocked_items(store_id=store_id)}
    if intent == "slow_moving":
        return {"slow_moving_items": engine.get_slow_moving_items(store_id=store_id)}
    if intent == "sales_growth":
        return {"sales_growth": [x for x in engine.get_sales_growth(14, store_id) if x["trend"] == "SPIKE"]}
    if intent == "sales_decline":
        return {"sales_decline": [x for x in engine.get_sales_growth(14, store_id) if x["trend"] in ["DECLINE", "SHARP_DROP"]]}
    if intent == "store_performance":
        return {"store_ranking": engine.get_store_sales_ranking(days=days)}
    if intent == "inventory":
        return {"attention": engine.get_today_attention(store_id=store_id)}
    return {"kpis": engine.get_kpis(store_id=store_id, days=days)}


def _fallback_answer(intent: str, analytics: Dict[str, Any]) -> str:
    if intent == "profit_unavailable":
        return "I can't determine profit or profitability because the available RetailIQ dataset does not contain cost or profit data."
    if intent == "stockout":
        items = analytics.get("stockout_risks", [])
        if not items: return "No stockout risks were identified within the configured 7-day threshold."
        top = items[:3]
        return "Stockout priorities: " + "; ".join(
            f"{x['product_name']} at {x['store_name']} has {x['current_stock']} units and about {x['days_until_stockout']} days of coverage."
            for x in top) + " Prioritize replenishment for the most urgent items."
    if intent == "overstock":
        items = analytics.get("overstocked_items", [])
        if not items: return "No overstocked inventory was identified."
        return "Overstocked items include " + "; ".join(f"{x['product_name']} at {x['store_name']}" for x in items[:5]) + ". Review replenishment and promotion plans."
    if intent == "slow_moving":
        items = analytics.get("slow_moving_items", [])
        if not items: return "No slow-moving items were identified at the configured threshold."
        return "Slow-moving items include " + "; ".join(f"{x['product_name']} at {x['store_name']}" for x in items[:5]) + ". Consider reducing replenishment or using targeted promotions."
    if intent == "store_performance":
        items = analytics.get("store_ranking", [])
        if not items: return "There is not enough store sales data to rank stores."
        x=items[0]
        return f"{x['store_name']} ({x['store_id']}) ranks #1 for the selected period with ${x['total_revenue']:.2f} revenue and {x['total_units']} units sold."
    if intent in ("sales_growth","sales_decline"):
        key="sales_growth" if intent=="sales_growth" else "sales_decline"
        items=analytics.get(key, [])
        if not items: return "No matching major sales trend was identified in the selected comparison window."
        return "; ".join(f"{x['product_name']}: {x['trend']} ({x['growth_percentage']}%)" for x in items[:5])
    return f"RetailIQ has {analytics.get('kpis', {}).get('total_transactions', 0)} transactions and ${analytics.get('kpis', {}).get('total_revenue', 0):.2f} revenue in the selected window."


@app.get("/api/retrieval/search")
def retrieval_search(q: str = Query(..., min_length=1), top_k: int = Query(5, ge=1, le=10)):
    return retrieve(engine, q, top_k)


@app.post("/api/retrieval/rebuild")
def retrieval_rebuild():
    return build_index(engine, force=True)


@app.post("/api/copilot")
def copilot(request: CopilotRequest):
    query = (request.query or "").strip()
    if not query:
        raise HTTPException(status_code=400, detail="Query cannot be empty.")
    if request.days < 1 or request.days > 180:
        raise HTTPException(status_code=400, detail="days must be between 1 and 180.")

    parsed = understand_query(query)
    if parsed["intent"] == "empty":
        raise HTTPException(status_code=400, detail="Query cannot be empty.")

    analytics_payload = _analytics_for_intent(parsed["intent"], request.store_id or parsed["store_id"], request.days)
    retrieval_payload = retrieve(engine, query, top_k=6)
    evidence = compact_evidence(retrieval_payload.get("results", []))

    if parsed["intent"] == "profit_unavailable":
        answer = _fallback_answer(parsed["intent"], analytics_payload)
        return {"answer": answer, "intent": parsed["intent"], "evidence": evidence,
                "assumptions": ["Cost/profit data is not present in the dataset."], "source": "deterministic"}

    if not gemini_client.is_configured():
        answer = _fallback_answer(parsed["intent"], analytics_payload)
        return {"answer": answer, "intent": parsed["intent"], "evidence": evidence,
                "assumptions": ["Business metrics were calculated deterministically in Python.",
                                "Gemini is not configured, so a deterministic fallback response was used."],
                "source": "deterministic_fallback"}

    context = build_grounding_context(analytics_payload, evidence)
    system = (
        "You are RetailIQ, a retail operations copilot. "
        "Answer only from the supplied deterministic analytics and retrieved evidence. "
        "Never invent or recalculate business numbers. If evidence is insufficient, say so. "
        "Keep the answer concise and actionable. Separate findings from recommendations."
    )
    result = gemini_client.generate(
        prompt=f"USER QUESTION:\n{query}\n\n{context}\n\n"
               "Return a concise business answer. Mention exact figures only when present in evidence.",
        system_instruction=system, max_output_tokens=400, temperature=0.2
    )
    if result.get("success") and result.get("text"):
        answer=result["text"]
        source="gemini_grounded"
    else:
        answer=_fallback_answer(parsed["intent"], analytics_payload)
        source="deterministic_fallback"
    assumptions=["Business metrics were calculated deterministically in Python.",
                 "Gemini was constrained to supplied evidence."]
    return {"answer": answer, "intent": parsed["intent"], "evidence": evidence,
            "assumptions": assumptions, "source": source}


@app.get("/api/kpis")
def get_kpis(
    store_id: Optional[str] = Query(None, description="Optional store filter e.g. S001"),
    days: int = Query(30, ge=1, le=180, description="Analysis timeframe in days (default: 30)")
):
    """Retrieve high-level retail KPIs: Revenue, Units Sold, Orders, AOV."""
    return engine.get_kpis(store_id=store_id, days=days)


@app.get("/api/stores")
def get_stores(
    days: int = Query(30, ge=1, le=180, description="Timeframe in days for sales aggregation")
):
    """List all retail stores ranked by total sales revenue."""
    return {
        "timeframe_days": days,
        "stores": engine.get_store_sales_ranking(days=days)
    }


@app.get("/api/products")
def get_products(
    store_id: Optional[str] = Query(None, description="Filter by store ID"),
    days: int = Query(30, ge=1, le=180, description="Timeframe in days"),
    limit: int = Query(20, ge=1, le=100, description="Number of products to return")
):
    """List products ranked by sales revenue and average daily velocity."""
    return {
        "store_id": store_id if store_id else "All Stores",
        "timeframe_days": days,
        "products": engine.get_product_sales_ranking(store_id=store_id, days=days, limit=limit)
    }


@app.get("/api/inventory/health")
def get_inventory_health(
    store_id: Optional[str] = Query(None, description="Filter by store ID"),
    days: int = Query(30, ge=1, le=180, description="Demand window in days")
):
    """Comprehensive stock health: stockout days, coverage, and urgency levels."""
    health_records = engine.get_inventory_health(store_id=store_id, demand_window_days=days)
    return {
        "store_id": store_id if store_id else "All Stores",
        "total_items_monitored": len(health_records),
        "inventory": health_records
    }


@app.get("/api/inventory/stockouts")
def get_stockout_risks(
    store_id: Optional[str] = Query(None, description="Filter by store ID"),
    max_days: float = Query(7.0, ge=0.0, le=60.0, description="Threshold in days until stock-out")
):
    """Identify products at imminent risk of running out of stock."""
    risks = engine.get_stockout_risks(store_id=store_id, max_days=max_days)
    return {
        "store_id": store_id if store_id else "All Stores",
        "threshold_days": max_days,
        "count": len(risks),
        "critical_stockouts": risks
    }


@app.get("/api/inventory/overstocked")
def get_overstocked_items(
    store_id: Optional[str] = Query(None, description="Filter by store ID")
):
    """Identify products with excessive inventory coverage (>90 days or >2x target)."""
    overstocked = engine.get_overstocked_items(store_id=store_id)
    return {
        "store_id": store_id if store_id else "All Stores",
        "count": len(overstocked),
        "overstocked_items": overstocked
    }


@app.get("/api/inventory/slow-moving")
def get_slow_moving_items(
    store_id: Optional[str] = Query(None, description="Filter by store ID"),
    max_daily_demand: float = Query(0.5, ge=0.0, le=5.0, description="Max daily units sold threshold")
):
    """Identify sluggish products with low daily demand."""
    slow_items = engine.get_slow_moving_items(store_id=store_id, max_daily_demand=max_daily_demand)
    return {
        "store_id": store_id if store_id else "All Stores",
        "max_daily_demand_threshold": max_daily_demand,
        "count": len(slow_items),
        "slow_moving_items": slow_items
    }


@app.get("/api/sales/growth")
def get_sales_growth(
    store_id: Optional[str] = Query(None, description="Filter by store ID"),
    window_days: int = Query(14, ge=3, le=60, description="Comparison window in days")
):
    """Detect sales spikes and sharp drops by comparing recent vs prior periods."""
    growth_data = engine.get_sales_growth(window_days=window_days, store_id=store_id)
    spikes = [item for item in growth_data if item["trend"] == "SPIKE"]
    drops = [item for item in growth_data if item["trend"] in ["SHARP_DROP", "DECLINE"]]

    return {
        "store_id": store_id if store_id else "All Stores",
        "window_days": window_days,
        "spikes_count": len(spikes),
        "drops_count": len(drops),
        "spikes": spikes,
        "drops": drops,
        "all_trends": growth_data
    }


@app.get("/api/attention")
def get_today_attention(
    store_id: Optional[str] = Query(None, description="Filter by store ID")
):
    """Unified operational digest for store managers: stockouts, overstock, spikes, and drops."""
    return engine.get_today_attention(store_id=store_id)


@app.get("/api/product/{product_id_or_name}")
def get_product_details(
    product_id_or_name: str,
    store_id: Optional[str] = Query(None, description="Filter by store ID")
):
    """
    Detailed product drill-down with transparent mathematical evidence, formulas, and assumptions.
    """
    result = engine.get_product_performance(query=product_id_or_name, store_id=store_id)
    if not result.get("found", False):
        raise HTTPException(
            status_code=404,
            detail=result.get("error", f"Product '{product_id_or_name}' not found.")
        )
    return result


@app.post("/api/data/reload")
def reload_data():
    """Reloads all CSV data from disk without restarting the server."""
    engine.load_data()
    return {
        "status": "success",
        "message": "Datasets reloaded successfully into memory.",
        "stores_count": len(engine.stores_df),
        "products_count": len(engine.products_df),
        "sales_count": len(engine.sales_df),
        "inventory_count": len(engine.inventory_df)
    }


if __name__ == "__main__":
    print("Starting RetailIQ server on http://localhost:8000 ...")
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
