"""
RetailIQ local grounded retrieval layer.
Uses Gemini embeddings when GEMINI_API_KEY is configured and a small
NumPy cosine-search index stored locally. No hosted vector database.
"""
import json, os, re
from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from src import config

INDEX_DIR = os.path.join(config.DATA_DIR, "vector_store")
INDEX_FILE = os.path.join(INDEX_DIR, "index.npz")
META_FILE = os.path.join(INDEX_DIR, "metadata.json")

def _clean(v: Any) -> str:
    return str(v).strip() if v is not None else ""

def _embed_gemini(texts: List[str]) -> np.ndarray:
    from google import genai
    if not config.is_gemini_configured():
        raise RuntimeError("Gemini API key is not configured.")
    client = genai.Client(api_key=config.get_gemini_api_key())
    response = client.models.embed_content(
        model=config.GEMINI_EMBEDDING_MODEL,
        contents=texts,
    )
    embeddings = getattr(response, "embeddings", None)
    if embeddings is None:
        raise RuntimeError("Gemini embedding response did not contain embeddings.")
    rows = []
    for item in embeddings:
        values = getattr(item, "values", None)
        if values is None and isinstance(item, dict):
            values = item.get("values")
        if values is None:
            raise RuntimeError("Invalid Gemini embedding response.")
        rows.append(values)
    return np.asarray(rows, dtype=np.float32)

def _lexical_vector(text: str, vocabulary: Dict[str, int]) -> np.ndarray:
    vec = np.zeros(len(vocabulary), dtype=np.float32)
    for token in re.findall(r"[a-z0-9]+", text.lower()):
        if token in vocabulary:
            vec[vocabulary[token]] += 1.0
    norm = np.linalg.norm(vec)
    return vec / norm if norm else vec

def _lexical_matrix(texts: List[str]):
    vocab = {}
    for t in texts:
        for token in set(re.findall(r"[a-z0-9]+", t.lower())):
            if token not in vocab:
                vocab[token] = len(vocab)
    matrix = np.vstack([_lexical_vector(t, vocab) for t in texts]).astype(np.float32)
    return matrix, vocab

def build_documents(engine) -> List[Dict[str, Any]]:
    docs = []
    # Product catalog evidence
    for _, r in engine.products_df.iterrows():
        docs.append({
            "id": f"product-{r.product_id}",
            "text": f"Product {r.product_id}: {r.product_name}. Category: {r.category}. "
                     f"Unit price: ${float(r.unit_price):.2f}.",
            "metadata": {"source_type": "product", "product_id": _clean(r.product_id),
                         "category": _clean(r.category)}
        })
    # Store evidence
    for _, r in engine.stores_df.iterrows():
        docs.append({
            "id": f"store-{r.store_id}",
            "text": f"Store {r.store_id}: {r.store_name}. Location: {r.city}, {r.state}.",
            "metadata": {"source_type": "store", "store_id": _clean(r.store_id)}
        })
    # Deterministic inventory evidence
    for item in engine.get_inventory_health(demand_window_days=30):
        status = item["health_status"]
        cov = item["days_until_stockout"]
        cov_str = f"{cov} days" if cov is not None else ("0 days (out of stock)" if status == "OUT_OF_STOCK" else "N/A")

        if status == "OUT_OF_STOCK":
            urgency_label = "URGENT REORDER REQUIRED - OUT OF STOCK"
            urgency_rank = 0
        elif status == "IMMINENT_STOCKOUT_RISK":
            urgency_label = f"URGENT REORDER REQUIRED - IMMINENT STOCKOUT RISK ({cov_str} coverage)"
            urgency_rank = 1
        elif status == "LOW_STOCK":
            urgency_label = f"REORDER SOON - LOW STOCK ({cov_str} coverage)"
            urgency_rank = 2
        elif status == "OVERSTOCKED":
            urgency_label = f"OVERSTOCKED ({cov_str} coverage)"
            urgency_rank = 3
        else:
            urgency_label = f"HEALTHY STOCK ({cov_str} coverage)"
            urgency_rank = 4

        docs.append({
            "id": f"inventory-{item['store_id']}-{item['product_id']}",
            "text": (
                f"Inventory evidence [{urgency_label}]: {item['product_name']} ({item['product_id']}) "
                f"at {item['store_name']} ({item['store_id']}). Current stock: {item['current_stock']} units; "
                f"average daily demand: {item['average_daily_demand']} units/day; days until stockout: {cov_str}; "
                f"health status: {status}; reorder point: {item['reorder_point']}; target stock: {item['target_stock']}. "
                f"Recommendation: {item['recommendation']}"
            ),
            "metadata": {
                "source_type": "inventory",
                "product_id": _clean(item["product_id"]),
                "product_name": _clean(item["product_name"]),
                "store_id": _clean(item["store_id"]),
                "store_name": _clean(item["store_name"]),
                "category": _clean(item.get("category", "")),
                "health_status": status,
                "current_stock": item["current_stock"],
                "days_until_stockout": cov,
                "urgency_rank": urgency_rank
            }
        })
    # Product sales evidence (30d)
    for item in engine.get_product_sales_ranking(days=30, limit=100):
        docs.append({
            "id": f"sales-product-{item['product_id']}",
            "text": (
                f"30-day sales evidence for {item['product_name']} ({item['product_id']}): "
                f"{item['total_units']} units sold, ${item['total_revenue']:.2f} revenue, "
                f"{item['daily_avg_sales']} units/day."
            ),
            "metadata": {"source_type": "sales", "product_id": _clean(item["product_id"]),
                         "category": _clean(item.get("category","")), "window_days": 30}
        })
    # Store sales evidence
    for item in engine.get_store_sales_ranking(days=30):
        docs.append({
            "id": f"sales-store-{item['store_id']}",
            "text": (
                f"30-day store sales evidence for {item['store_name']} ({item['store_id']}): "
                f"{item['total_units']} units sold, ${item['total_revenue']:.2f} revenue, "
                f"{item['transaction_count']} transactions."
            ),
            "metadata": {"source_type": "store_sales", "store_id": _clean(item["store_id"]),
                         "window_days": 30}
        })
    # Growth evidence
    for item in engine.get_sales_growth(window_days=14):
        docs.append({
            "id": f"growth-{item['product_id']}",
            "text": (
                f"14-day sales trend for {item['product_name']} ({item['product_id']}): "
                f"trend {item['trend']}; recent revenue ${item['recent_revenue']:.2f}; "
                f"prior revenue ${item['prior_revenue']:.2f}; growth {item['growth_percentage']}%."
            ),
            "metadata": {"source_type": "sales_trend", "product_id": _clean(item["product_id"]),
                         "window_days": 14, "trend": _clean(item["trend"])}
        })
    return docs

def build_index(engine, force: bool = False) -> Dict[str, Any]:
    os.makedirs(INDEX_DIR, exist_ok=True)
    docs = build_documents(engine)
    if not docs:
        raise RuntimeError("No evidence documents available.")
    texts = [d["text"] for d in docs]
    mode = "gemini"
    try:
        matrix = _embed_gemini(texts)
        if len(matrix) != len(texts):
            raise RuntimeError("Embedding count does not match evidence count.")
    except Exception:
        # Keep the app usable without a key/network; live RAG uses Gemini embeddings.
        matrix, vocab = _lexical_matrix(texts)
        mode = "lexical_fallback"
    np.savez_compressed(INDEX_FILE, embeddings=matrix)
    with open(META_FILE, "w", encoding="utf-8") as f:
        json.dump({"documents": docs, "mode": mode,
                   "vocabulary": locals().get("vocab", {})}, f, ensure_ascii=False)
    return {"documents": len(docs), "mode": mode, "index_file": INDEX_FILE}

def load_index() -> Optional[Dict[str, Any]]:
    if not (os.path.exists(INDEX_FILE) and os.path.exists(META_FILE)):
        return None
    try:
        arr = np.load(INDEX_FILE)["embeddings"]
        with open(META_FILE, encoding="utf-8") as f:
            meta = json.load(f)
        return {"embeddings": arr, **meta}
    except Exception:
        return None

def retrieve(engine, query: str, top_k: int = 5, store_id: Optional[str] = None) -> Dict[str, Any]:
    query = _clean(query)
    if not query:
        return {"query": query, "results": [], "error": "Query cannot be empty."}
    top_k = max(1, min(int(top_k), 10))
    index = load_index()
    if index is None or len(index.get("documents", [])) == 0 or "urgency_rank" not in index["documents"][0].get("metadata", {}):
        build_index(engine, force=True)
        index = load_index()
    mode = index["mode"]
    if mode == "gemini":
        try:
            qv = _embed_gemini([query])[0]
        except Exception:
            qv = None
            mode = "lexical_fallback"
    else:
        qv = None

    if mode != "gemini" or qv is None:
        vocab = index.get("vocabulary", {})
        qv = _lexical_vector(query, vocab)

    mat = index["embeddings"]
    base_scores = mat @ qv
    scores = np.copy(base_scores)

    q_lower = query.lower()
    is_reorder_query = any(w in q_lower for w in [
        "reorder", "re-order", "replenish", "replenishment", "restock", "restocking",
        "stockout", "stock out", "run out", "running out", "runs out", "ran out",
        "out of stock", "low stock", "running low", "low on stock", "shortage", "shortages",
        "urgent", "urgently", "uegently", "urgnt", "immediate attention", "what should i order"
    ])
    is_overstock_query = any(w in q_lower for w in ["overstock", "excess inventory", "too much stock"])
    is_slow_moving_query = any(w in q_lower for w in ["slow moving", "slow-moving", "not selling"])

    for i, doc in enumerate(index["documents"]):
        meta = doc.get("metadata", {})
        source_type = meta.get("source_type")

        # Store filter matching
        if store_id:
            doc_store = meta.get("store_id")
            if doc_store and doc_store != store_id:
                scores[i] -= 10.0
            elif doc_store == store_id:
                scores[i] += 1.0

        if is_reorder_query:
            if source_type == "inventory":
                status = meta.get("health_status")
                cov = meta.get("days_until_stockout")
                cov_val = cov if cov is not None else 0.0
                if status == "OUT_OF_STOCK":
                    scores[i] += 5.0
                elif status == "IMMINENT_STOCKOUT_RISK":
                    # Priority by shortest days until stockout
                    scores[i] += 4.0 - min(cov_val * 0.2, 1.5)
                elif status == "LOW_STOCK":
                    scores[i] += 2.0
                elif status == "OVERSTOCKED":
                    scores[i] -= 2.0
                elif status == "HEALTHY":
                    scores[i] -= 3.0
        elif is_overstock_query:
            if source_type == "inventory":
                if meta.get("health_status") == "OVERSTOCKED":
                    scores[i] += 5.0
                else:
                    scores[i] -= 2.0
        elif is_slow_moving_query:
            if source_type == "inventory":
                if "slow" in doc.get("text", "").lower() or meta.get("health_status") in ("OVERSTOCKED", "HEALTHY"):
                    scores[i] += 3.0

    order = np.argsort(-scores)[:top_k]
    results = []
    for i in order:
        if float(scores[i]) <= -5.0 and len(results) >= top_k:
            continue
        doc = index["documents"][int(i)]
        results.append({"score": round(float(scores[i]), 4), "text": doc["text"],
                        "metadata": doc["metadata"], "id": doc["id"]})
    return {"query": query, "results": results, "mode": mode}

if __name__ == "__main__":
    from src.analytics import AnalyticsEngine
    engine = AnalyticsEngine()
    print(build_index(engine))
    print(retrieve(engine, "products at stockout risk", 5))
