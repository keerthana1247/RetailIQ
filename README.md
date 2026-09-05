TRACK_ID=PS03

# RetailIQ — Retail Sales & Inventory Copilot

RetailIQ is a FastAPI-based retail intelligence dashboard and grounded AI copilot for the NexusTiQ24 PS03 challenge. It combines deterministic Python analytics with local evidence retrieval and Gemini for natural-language explanations.

## What it does

- Executive sales KPIs: revenue, units, transactions and AOV
- Store performance ranking
- Product performance and drill-down
- Inventory health and stockout coverage
- Overstock and slow-moving detection
- Sales spikes and declines
- Today's Attention operational digest
- AI Copilot for natural-language retail questions
- Local retrieval using Gemini `gemini-embedding-001`
- Grounded Gemini responses using supplied evidence
- Evidence and mathematical proof for inventory calculations
- Safe deterministic fallback when Gemini is unavailable
- Profit questions are explicitly declined because cost/profit data is not in the dataset

## Architecture

User → Frontend → FastAPI → Query Understanding → Deterministic Python Analytics → Local Retrieval → Evidence → Gemini → Grounded Response → Frontend

Python calculates business metrics. Gemini does not calculate or invent business numbers.

## Tech stack

- Python
- FastAPI
- Pandas / NumPy
- Google GenAI Python SDK
- Gemini `gemini-3.5-flash-lite`
- Gemini `gemini-embedding-001`
- Local NumPy cosine-similarity vector store
- HTML/CSS/JavaScript frontend

No hosted vector database is required.

## Data

The application uses synthetic CSV data in `data/`:

- `products.csv`
- `stores.csv`
- `sales.csv`
- `inventory.csv`

Cost/profit fields are intentionally absent, so profit cannot be reliably calculated.

## Setup

Create a Python virtual environment if desired, then:

```bash
pip install -r requirements.txt
```

Create `.env` in the project root:

```text
GEMINI_API_KEY=your_actual_key_here
```

Never commit `.env`.

## Run

The complete application is served with one command:

```bash
python app.py
```

Open:

```text
http://localhost:8000
```

API documentation:

```text
http://localhost:8000/docs
```

## Retrieval

The first retrieval request builds a local index when needed.

Test:

```text
/api/retrieval/search?q=products%20at%20stockout%20risk&top_k=5
```

To rebuild:

```text
POST /api/retrieval/rebuild
```

When Gemini is configured, the index uses `gemini-embedding-001`. If Gemini is unavailable, a lightweight lexical fallback keeps local development usable.

## Copilot

Endpoint:

```text
POST /api/copilot
```

Example body:

```json
{
  "query": "Which products are at risk of stockout?",
  "store_id": "S001",
  "days": 30
}
```

Example questions:

- Which products are likely to stock out soon?
- Which store needs attention today?
- Which products are selling fastest?
- What changed in the last 14 days?
- Show me overstocked products.
- Which products are slow-moving?
- Which store has the highest sales?
- What is the most profitable product?

The last question is intentionally answered as unsupported because the dataset has no cost/profit data.

## Main API endpoints

- `GET /api/health`
- `GET /api/kpis`
- `GET /api/stores`
- `GET /api/products`
- `GET /api/inventory/health`
- `GET /api/inventory/stockouts`
- `GET /api/inventory/overstocked`
- `GET /api/inventory/slow-moving`
- `GET /api/sales/growth`
- `GET /api/attention`
- `GET /api/product/{product_id_or_name}`
- `GET /api/retrieval/search`
- `POST /api/retrieval/rebuild`
- `POST /api/copilot`
- `GET /api/gemini/status`
- `GET /api/gemini/test`

## Testing

Run:

```bash
python -m unittest discover -s tests
```

The test suite covers analytics, API behavior, Gemini configuration/error handling, retrieval, query understanding and Copilot behavior.

## Grounding and trust

RetailIQ follows a strict rule:

> If the available data does not support an answer, RetailIQ does not guess.

Business numbers originate from deterministic Python calculations. Retrieved evidence is supplied to Gemini as grounding context. Responses expose evidence and assumptions to make recommendations auditable.

## Deployment

The application is designed as a single Python web service. Use:

```bash
python app.py
```

The frontend and API are served from the same FastAPI process.

## Future improvements

- More advanced semantic retrieval filters
- Larger production datasets
- Role-based access
- Persistent database storage
- Automated inventory purchase-order workflows
- More detailed forecasting
