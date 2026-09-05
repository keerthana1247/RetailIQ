"""Evidence formatting utilities for grounded RetailIQ answers."""
from typing import Any, Dict, List

def compact_evidence(retrieval_results: List[Dict[str, Any]], max_items: int = 8) -> List[Dict[str, Any]]:
    return [
        {"id": x.get("id"), "score": x.get("score"), "text": x.get("text"), "metadata": x.get("metadata", {})}
        for x in retrieval_results[:max_items]
    ]

def product_proof(detail: Dict[str, Any]) -> Dict[str, Any]:
    metrics = detail.get("metrics_30d", {})
    stock = metrics.get("current_stock")
    demand = metrics.get("daily_average_sales")
    coverage = metrics.get("days_until_stockout")
    calculation = f"{stock} / {demand} = {coverage} days" if demand not in (None, 0) else "Coverage unavailable because average daily demand is zero."
    return {
        "product": f"{detail.get('product_name')} ({detail.get('product_id')})",
        "store": detail.get("store_filtered"),
        "metrics": metrics,
        "calculation": calculation,
        "assumption": detail.get("evidence", {}).get("assumption"),
    }

def build_grounding_context(analytics_payload: Any, retrieved: List[Dict[str, Any]]) -> str:
    lines = ["Use ONLY the evidence below. Do not invent numbers or facts."]
    if analytics_payload is not None:
        lines.append(f"DETERMINISTIC ANALYTICS:\n{analytics_payload}")
    if retrieved:
        lines.append("RETRIEVED EVIDENCE:")
        for r in retrieved:
            lines.append(f"- [{r.get('id')}] {r.get('text')}")
    return "\n".join(lines)
