"""Lightweight intent/entity detection for RetailIQ Copilot."""
import re
from typing import Dict, Optional

def understand_query(query: str) -> Dict[str, Optional[str]]:
    q = (query or "").strip().lower()
    if not q:
        return {"intent": "empty", "product_id": None, "store_id": None}
    if any(w in q for w in ["profit", "profitable", "margin"]):
        intent = "profit_unavailable"
    elif any(w in q for w in [
        "stockout", "stock out", "run out", "running out", "runs out", "ran out",
        "replenish", "replenishment", "reorder", "re-order", "reordering",
        "restock", "restocking", "out of stock", "low stock", "running low", "low on stock",
        "order more", "shortage", "shortages",
        "urgent", "urgently", "uegently", "urgnt", "immediate attention"
    ]):
        intent = "stockout"
    elif any(w in q for w in ["overstock", "excess inventory", "too much stock"]):
        intent = "overstock"
    elif any(w in q for w in ["slow moving", "slow-moving", "not selling"]):
        intent = "slow_moving"
    elif any(w in q for w in ["spike", "increased", "increase", "fastest", "selling fast", "growth"]):
        intent = "sales_growth"
    elif any(w in q for w in ["drop", "decline", "decreased", "decrease", "falling"]):
        intent = "sales_decline"
    elif any(w in q for w in ["store", "branch", "location"]) and any(w in q for w in ["best", "top", "perform", "highest", "sales", "revenue", "rank"]):
        intent = "store_performance"
    elif any(w in q for w in ["inventory", "stock", "attention", "risk"]):
        intent = "inventory"
    else:
        intent = "general"
    store_match = re.search(r"\bS\d{3}\b", query or "", re.I)
    product_match = re.search(r"\bP\d{3}\b", query or "", re.I)
    return {"intent": intent,
            "product_id": product_match.group(0).upper() if product_match else None,
            "store_id": store_match.group(0).upper() if store_match else None}
