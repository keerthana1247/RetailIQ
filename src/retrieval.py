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
        docs.append({
            "id": f"inventory-{item['store_id']}-{item['product_id']}",
            "text": (
                f"Inventory evidence for {item['product_name']} ({item['product_id']}) "
                f"at {item['store_name']} ({item['store_id']}): current stock "
                f"{item['current_stock']} units; average daily demand "
                f"{item['average_daily_demand']} units/day; days until stockout "
                f"{item['days_until_stockout'] if item['days_until_stockout'] is not None else 'N/A'}; "
                f"health status {item['health_status']}; reorder point {item['reorder_point']}."
            ),
            "metadata": {"source_type": "inventory", "product_id": _clean(item["product_id"]),
                         "store_id": _clean(item["store_id"]), "category": _clean(item.get("category",""))}
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

def retrieve(engine, query: str, top_k: int = 5) -> Dict[str, Any]:
    query = _clean(query)
    if not query:
        return {"query": query, "results": [], "error": "Query cannot be empty."}
    top_k = max(1, min(int(top_k), 10))
    index = load_index()
    if index is None or len(index["documents"]) == 0:
        build_index(engine)
        index = load_index()
    mode = index["mode"]
    if mode == "gemini":
        try:
            qv = _embed_gemini([query])[0]
        except Exception:
            # If the stored Gemini index exists but the live embedding call fails,
            # return a safe empty result rather than silently changing semantics.
            return {"query": query, "results": [], "error": "Semantic retrieval is temporarily unavailable."}
    else:
        vocab = index.get("vocabulary", {})
        qv = _lexical_vector(query, vocab)
    mat = index["embeddings"]
    scores = mat @ qv
    order = np.argsort(-scores)[:top_k]
    results = []
    for i in order:
        if float(scores[i]) <= 0:
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
