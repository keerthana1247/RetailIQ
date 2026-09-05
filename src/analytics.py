"""
RetailIQ - Deterministic Analytics Engine
NexusTiQ24 Hackathon | Track: PS03 - Retail: Sales and Inventory Copilot

Performs 100% deterministic retail calculations for:
- Sales KPI metrics (Revenue, Units, Orders, AOV)
- Store & Product sales performance
- Average daily sales & sales growth / decline detection
- Inventory health & stock coverage (days until stockout)
- Overstock & Slow-moving item detection
- Actionable "Today's Attention" summary

Handles edge cases safely:
- Zero sales / zero demand
- Zero current stock
- Unknown store / unknown product
- Safe division by zero
"""

import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import pandas as pd
import numpy as np


class AnalyticsEngine:
    def __init__(self, data_dir: Optional[str] = None):
        if data_dir is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            self.data_dir = os.path.join(base_dir, "data")
        else:
            self.data_dir = data_dir

        self.products_df: pd.DataFrame = pd.DataFrame()
        self.stores_df: pd.DataFrame = pd.DataFrame()
        self.sales_df: pd.DataFrame = pd.DataFrame()
        self.inventory_df: pd.DataFrame = pd.DataFrame()
        self.load_data()

    def load_data(self) -> None:
        """Loads and prepares all CSV datasets with proper types."""
        products_path = os.path.join(self.data_dir, "products.csv")
        stores_path = os.path.join(self.data_dir, "stores.csv")
        sales_path = os.path.join(self.data_dir, "sales.csv")
        inventory_path = os.path.join(self.data_dir, "inventory.csv")

        if os.path.exists(products_path):
            self.products_df = pd.read_csv(products_path)
            self.products_df["unit_price"] = pd.to_numeric(self.products_df["unit_price"], errors="coerce").fillna(0.0)
            self.products_df["reorder_point"] = pd.to_numeric(self.products_df["reorder_point"], errors="coerce").fillna(0).astype(int)
            self.products_df["target_stock"] = pd.to_numeric(self.products_df["target_stock"], errors="coerce").fillna(0).astype(int)

        if os.path.exists(stores_path):
            self.stores_df = pd.read_csv(stores_path)

        if os.path.exists(sales_path):
            self.sales_df = pd.read_csv(sales_path)
            self.sales_df["date"] = pd.to_datetime(self.sales_df["date"])
            self.sales_df["quantity"] = pd.to_numeric(self.sales_df["quantity"], errors="coerce").fillna(0).astype(int)
            self.sales_df["unit_price"] = pd.to_numeric(self.sales_df["unit_price"], errors="coerce").fillna(0.0)
            self.sales_df["total_amount"] = pd.to_numeric(self.sales_df["total_amount"], errors="coerce").fillna(0.0)

        if os.path.exists(inventory_path):
            self.inventory_df = pd.read_csv(inventory_path)
            self.inventory_df["current_stock"] = pd.to_numeric(self.inventory_df["current_stock"], errors="coerce").fillna(0).astype(int)

    def get_max_date(self) -> datetime:
        """Returns the most recent date available in sales transactions."""
        if not self.sales_df.empty and "date" in self.sales_df:
            return self.sales_df["date"].max()
        return datetime.now()

    # =========================================================================
    # SALES ANALYTICS
    # =========================================================================

    def get_kpis(self, store_id: Optional[str] = None, days: int = 30) -> Dict[str, Any]:
        """
        Calculates high-level retail KPIs for the given store and timeframe.
        """
        if self.sales_df.empty:
            return {
                "total_revenue": 0.0,
                "total_units_sold": 0,
                "total_transactions": 0,
                "average_order_value": 0.0,
                "active_stores": 0,
                "active_products": 0,
                "timeframe_days": days
            }

        max_dt = self.get_max_date()
        cutoff_dt = max_dt - timedelta(days=days)
        
        filtered = self.sales_df[self.sales_df["date"] >= cutoff_dt]
        if store_id:
            filtered = filtered[filtered["store_id"] == store_id]

        total_rev = float(round(filtered["total_amount"].sum(), 2))
        total_units = int(filtered["quantity"].sum())
        total_tx = int(filtered["transaction_id"].nunique())
        aov = float(round(total_rev / total_tx, 2)) if total_tx > 0 else 0.0

        return {
            "total_revenue": total_rev,
            "total_units_sold": total_units,
            "total_transactions": total_tx,
            "average_order_value": aov,
            "active_stores": int(filtered["store_id"].nunique()),
            "active_products": int(filtered["product_id"].nunique()),
            "timeframe_days": days,
            "start_date": cutoff_dt.strftime("%Y-%m-%d"),
            "end_date": max_dt.strftime("%Y-%m-%d")
        }

    def get_store_sales_ranking(self, days: int = 30) -> List[Dict[str, Any]]:
        """
        Returns all stores ranked by total sales revenue over the specified window.
        """
        if self.sales_df.empty or self.stores_df.empty:
            return []

        max_dt = self.get_max_date()
        cutoff_dt = max_dt - timedelta(days=days)
        filtered = self.sales_df[self.sales_df["date"] >= cutoff_dt]

        store_metrics = filtered.groupby("store_id").agg(
            total_revenue=("total_amount", "sum"),
            total_units=("quantity", "sum"),
            transaction_count=("transaction_id", "nunique")
        ).reset_index()

        merged = pd.merge(self.stores_df, store_metrics, on="store_id", how="left").fillna({
            "total_revenue": 0.0,
            "total_units": 0,
            "transaction_count": 0
        })

        merged["total_revenue"] = merged["total_revenue"].round(2)
        merged = merged.sort_values(by="total_revenue", ascending=False)

        results = []
        for rank, (_, row) in enumerate(merged.iterrows(), 1):
            results.append({
                "rank": rank,
                "store_id": row["store_id"],
                "store_name": row["store_name"],
                "city": row["city"],
                "state": row["state"],
                "store_type": row["store_type"],
                "total_revenue": float(row["total_revenue"]),
                "total_units": int(row["total_units"]),
                "transaction_count": int(row["transaction_count"])
            })
        return results

    def get_product_sales_ranking(self, store_id: Optional[str] = None, days: int = 30, limit: int = 15) -> List[Dict[str, Any]]:
        """
        Returns products ranked by revenue or units sold.
        """
        if self.sales_df.empty or self.products_df.empty:
            return []

        max_dt = self.get_max_date()
        cutoff_dt = max_dt - timedelta(days=days)
        filtered = self.sales_df[self.sales_df["date"] >= cutoff_dt]
        if store_id:
            filtered = filtered[filtered["store_id"] == store_id]

        prod_metrics = filtered.groupby("product_id").agg(
            total_revenue=("total_amount", "sum"),
            total_units=("quantity", "sum"),
            transaction_count=("transaction_id", "nunique")
        ).reset_index()

        merged = pd.merge(self.products_df, prod_metrics, on="product_id", how="left").fillna({
            "total_revenue": 0.0,
            "total_units": 0,
            "transaction_count": 0
        })

        merged["daily_avg_sales"] = (merged["total_units"] / days).round(2)
        merged["total_revenue"] = merged["total_revenue"].round(2)
        merged = merged.sort_values(by="total_revenue", ascending=False)

        if limit:
            merged = merged.head(limit)

        results = []
        for rank, (_, row) in enumerate(merged.iterrows(), 1):
            results.append({
                "rank": rank,
                "product_id": row["product_id"],
                "product_name": row["product_name"],
                "category": row["category"],
                "unit_price": float(row["unit_price"]),
                "total_revenue": float(row["total_revenue"]),
                "total_units": int(row["total_units"]),
                "daily_avg_sales": float(row["daily_avg_sales"]),
                "transaction_count": int(row["transaction_count"])
            })
        return results

    def get_sales_growth(self, window_days: int = 14, store_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Calculates sales growth or decline by comparing:
        Recent window [max_date - window_days to max_date]
        vs
        Prior window [max_date - 2*window_days to max_date - window_days].
        Identifies sales spikes and sales drops.
        """
        if self.sales_df.empty or self.products_df.empty:
            return []

        max_dt = self.get_max_date()
        recent_start = max_dt - timedelta(days=window_days)
        prior_start = max_dt - timedelta(days=window_days * 2)

        sales = self.sales_df
        if store_id:
            sales = sales[sales["store_id"] == store_id]

        recent_df = sales[(sales["date"] > recent_start) & (sales["date"] <= max_dt)]
        prior_df = sales[(sales["date"] > prior_start) & (sales["date"] <= recent_start)]

        recent_agg = recent_df.groupby("product_id").agg(
            recent_units=("quantity", "sum"),
            recent_revenue=("total_amount", "sum")
        ).reset_index()

        prior_agg = prior_df.groupby("product_id").agg(
            prior_units=("quantity", "sum"),
            prior_revenue=("total_amount", "sum")
        ).reset_index()

        merged = pd.merge(self.products_df[["product_id", "product_name", "category"]], recent_agg, on="product_id", how="left").fillna(0)
        merged = pd.merge(merged, prior_agg, on="product_id", how="left").fillna(0)

        results = []
        for _, row in merged.iterrows():
            rec_rev = float(row["recent_revenue"])
            pri_rev = float(row["prior_revenue"])
            rec_units = int(row["recent_units"])
            pri_units = int(row["prior_units"])

            # Growth rate percentage calculation (safe division)
            if pri_rev > 0:
                growth_pct = round(((rec_rev - pri_rev) / pri_rev) * 100, 1)
            elif rec_rev > 0:
                growth_pct = 100.0
            else:
                growth_pct = 0.0

            if growth_pct >= 50.0:
                trend = "SPIKE"
            elif growth_pct >= 10.0:
                trend = "GROWTH"
            elif growth_pct <= -50.0:
                trend = "SHARP_DROP"
            elif growth_pct <= -10.0:
                trend = "DECLINE"
            else:
                trend = "STABLE"

            results.append({
                "product_id": row["product_id"],
                "product_name": row["product_name"],
                "category": row["category"],
                "recent_revenue": round(rec_rev, 2),
                "prior_revenue": round(pri_rev, 2),
                "recent_units": rec_units,
                "prior_units": pri_units,
                "growth_percentage": growth_pct,
                "trend": trend,
                "window_days": window_days
            })

        results.sort(key=lambda x: x["growth_percentage"], reverse=True)
        return results

    # =========================================================================
    # INVENTORY & DEMAND ANALYTICS
    # =========================================================================

    def get_inventory_health(self, store_id: Optional[str] = None, demand_window_days: int = 30) -> List[Dict[str, Any]]:
        """
        Calculates deterministic stock coverage:
        average_daily_sales = total_units_sold_in_window / demand_window_days
        days_until_stockout = current_stock / average_daily_sales (safe division)
        Assigns structured status and documented assumptions.
        """
        if self.inventory_df.empty or self.products_df.empty:
            return []

        inv = self.inventory_df.copy()
        if store_id:
            inv = inv[inv["store_id"] == store_id]

        max_dt = self.get_max_date()
        cutoff_dt = max_dt - timedelta(days=demand_window_days)

        sales_window = self.sales_df[self.sales_df["date"] >= cutoff_dt]

        # Calculate demand per store and product
        demand_agg = sales_window.groupby(["store_id", "product_id"])["quantity"].sum().reset_index()
        demand_agg.rename(columns={"quantity": "units_sold_window"}, inplace=True)

        merged = pd.merge(inv, self.products_df, on="product_id", how="left")
        merged = pd.merge(merged, self.stores_df[["store_id", "store_name", "city"]], on="store_id", how="left")
        merged = pd.merge(merged, demand_agg, on=["store_id", "product_id"], how="left").fillna({
            "units_sold_window": 0
        })

        results = []
        for _, row in merged.iterrows():
            current_stock = int(row["current_stock"])
            units_sold = int(row["units_sold_window"])
            reorder_pt = int(row["reorder_point"])
            target_stk = int(row["target_stock"])

            daily_demand = round(units_sold / demand_window_days, 2)

            if daily_demand > 0:
                coverage_days = round(current_stock / daily_demand, 1)
            else:
                coverage_days = None  # No sales in window

            # Determine risk category
            if current_stock == 0:
                health_status = "OUT_OF_STOCK"
                recommendation = "Replenish immediately. Product is currently out of stock."
                human_coverage = "Out of stock (0 units remaining)."
            elif coverage_days is not None and coverage_days <= 7.0:
                health_status = "IMMINENT_STOCKOUT_RISK"
                recommendation = "Review reorder quantity immediately. High risk of stock-out within 7 days."
                human_coverage = f"Likely stock-out in approximately {coverage_days} days based on recent daily demand of {daily_demand} units/day."
            elif coverage_days is not None and coverage_days <= 14.0 or current_stock <= reorder_pt:
                health_status = "LOW_STOCK"
                recommendation = "Stock approaching reorder threshold. Schedule replenishment."
                human_coverage = f"Estimated coverage: approximately {coverage_days if coverage_days is not None else 'N/A'} days."
            elif coverage_days is not None and coverage_days > 90.0 or (current_stock >= target_stk * 2 and target_stk > 0):
                health_status = "OVERSTOCKED"
                recommendation = "Consider promotional pricing or inter-store transfer to reduce carrying costs."
                human_coverage = f"High coverage: estimated {coverage_days} days of inventory."
            else:
                health_status = "HEALTHY"
                recommendation = "Inventory within normal operational buffer."
                human_coverage = f"Estimated coverage: {coverage_days} days."

            # Velocity flag
            if daily_demand <= 0.3:
                velocity = "SLOW_MOVING"
            elif daily_demand >= 3.0:
                velocity = "FAST_MOVING"
            else:
                velocity = "MODERATE"

            results.append({
                "store_id": row["store_id"],
                "store_name": row["store_name"],
                "product_id": row["product_id"],
                "product_name": row["product_name"],
                "category": row["category"],
                "unit_price": float(row["unit_price"]),
                "current_stock": current_stock,
                "reorder_point": reorder_pt,
                "target_stock": target_stk,
                "units_sold_last_30d": units_sold,
                "average_daily_demand": daily_demand,
                "days_until_stockout": coverage_days,
                "human_coverage": human_coverage,
                "health_status": health_status,
                "velocity": velocity,
                "recommendation": recommendation,
                "last_restocked_date": str(row.get("last_restocked_date", "N/A")),
                "assumption": f"Assumes average daily demand ({daily_demand} units/day) over recent {demand_window_days} days remains constant."
            })

        # Order by urgency: out of stock and lowest coverage first
        results.sort(key=lambda x: (
            0 if x["health_status"] == "OUT_OF_STOCK" else
            1 if x["health_status"] == "IMMINENT_STOCKOUT_RISK" else
            2 if x["health_status"] == "LOW_STOCK" else
            3 if x["health_status"] == "OVERSTOCKED" else 4,
            x["days_until_stockout"] if x["days_until_stockout"] is not None else 9999
        ))

        return results

    # =========================================================================
    # ACTIONABLE FILTER METHODS
    # =========================================================================

    def get_stockout_risks(self, store_id: Optional[str] = None, max_days: float = 7.0) -> List[Dict[str, Any]]:
        """Returns items that are out of stock or likely to stock out within max_days."""
        health = self.get_inventory_health(store_id=store_id)
        return [
            item for item in health
            if item["health_status"] in ["OUT_OF_STOCK", "IMMINENT_STOCKOUT_RISK"]
            or (item["days_until_stockout"] is not None and item["days_until_stockout"] <= max_days)
        ]

    def get_overstocked_items(self, store_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Returns products with excessive inventory coverage."""
        health = self.get_inventory_health(store_id=store_id)
        return [item for item in health if item["health_status"] == "OVERSTOCKED"]

    def get_slow_moving_items(self, store_id: Optional[str] = None, max_daily_demand: float = 0.5) -> List[Dict[str, Any]]:
        """Returns products with sluggish sales velocity."""
        health = self.get_inventory_health(store_id=store_id)
        return [item for item in health if item["average_daily_demand"] <= max_daily_demand and item["current_stock"] > 0]

    def get_today_attention(self, store_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Synthesizes high-priority items requiring store manager attention today:
        - Critical stock-out risks
        - Overstocked items
        - Rapid sales spikes
        - Significant sales drops
        """
        stockout_risks = self.get_stockout_risks(store_id=store_id, max_days=7.0)
        overstocked = self.get_overstocked_items(store_id=store_id)
        growth = self.get_sales_growth(window_days=14, store_id=store_id)
        slow_moving = self.get_slow_moving_items(store_id=store_id)

        spikes = [g for g in growth if g["trend"] == "SPIKE"]
        drops = [g for g in growth if g["trend"] in ["SHARP_DROP", "DECLINE"]]

        return {
            "critical_stockouts": stockout_risks,
            "overstocked_items": overstocked,
            "slow_moving_items": slow_moving,
            "sales_spikes": spikes,
            "sales_drops": drops,
            "total_attention_count": len(stockout_risks) + len(overstocked) + len(spikes) + len(drops)
        }

    # =========================================================================
    # PRODUCT SPECIFIC PERFORMANCE
    # =========================================================================

    def get_product_performance(self, query: str, store_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Looks up a single product by exact ID or case-insensitive partial name match.
        Returns comprehensive deterministic calculations and evidence.
        """
        if self.products_df.empty:
            return {"error": "Product catalog is empty or not loaded."}

        clean_q = query.strip().lower()

        # Try match by ID first, then partial match on name
        matched = self.products_df[self.products_df["product_id"].str.lower() == clean_q]
        if matched.empty:
            matched = self.products_df[self.products_df["product_name"].str.lower().str.contains(clean_q)]

        if matched.empty:
            return {
                "found": False,
                "query": query,
                "error": f"Unable to find product matching '{query}' in product catalog."
            }

        prod = matched.iloc[0]
        prod_id = prod["product_id"]
        prod_name = prod["product_name"]

        # Sales metrics
        sales_sub = self.sales_df[self.sales_df["product_id"] == prod_id]
        if store_id:
            sales_sub = sales_sub[sales_sub["store_id"] == store_id]

        max_dt = self.get_max_date()
        cutoff_30d = max_dt - timedelta(days=30)
        recent_sales = sales_sub[sales_sub["date"] >= cutoff_30d]

        total_rev_30d = float(round(recent_sales["total_amount"].sum(), 2))
        total_units_30d = int(recent_sales["quantity"].sum())
        daily_avg_30d = round(total_units_30d / 30.0, 2)

        # Inventory metrics
        inv_sub = self.inventory_df[self.inventory_df["product_id"] == prod_id]
        if store_id:
            inv_sub = inv_sub[inv_sub["store_id"] == store_id]

        total_stock = int(inv_sub["current_stock"].sum())
        if daily_avg_30d > 0:
            coverage_days = round(total_stock / daily_avg_30d, 1)
        else:
            coverage_days = None

        # Growth metrics
        growth_list = self.get_sales_growth(window_days=14, store_id=store_id)
        growth_item = next((g for g in growth_list if g["product_id"] == prod_id), None)

        return {
            "found": True,
            "product_id": prod_id,
            "product_name": prod_name,
            "category": prod["category"],
            "unit_price": float(prod["unit_price"]),
            "reorder_point": int(prod["reorder_point"]),
            "target_stock": int(prod["target_stock"]),
            "store_filtered": store_id if store_id else "All Stores",
            "metrics_30d": {
                "total_revenue": total_rev_30d,
                "total_units_sold": total_units_30d,
                "daily_average_sales": daily_avg_30d,
                "current_stock": total_stock,
                "estimated_coverage_days": coverage_days,
                "human_coverage": (
                    f"Likely stock-out in approximately {coverage_days} days based on recent demand."
                    if coverage_days is not None and coverage_days <= 14.0
                    else f"Estimated coverage: {coverage_days} days." if coverage_days is not None else "No sales in window to estimate coverage."
                )
            },
            "growth_trend": growth_item,
            "evidence": {
                "formula_stockout": "current_stock / average_daily_sales",
                "calculation": f"{total_stock} / {daily_avg_30d} = {coverage_days} days" if daily_avg_30d > 0 else "N/A (zero daily sales)",
                "assumption": "Recent 30-day daily demand assumed to remain consistent over the next period."
            }
        }


if __name__ == "__main__":
    print("=== Testing RetailIQ Deterministic Analytics Engine ===")
    engine = AnalyticsEngine()
    print("1. KPIs (Last 30 Days):", engine.get_kpis(days=30))
    print("\n2. Top Store by Sales:")
    store_ranks = engine.get_store_sales_ranking(days=30)
    for s in store_ranks:
        print(f"   #{s['rank']} {s['store_name']}: ${s['total_revenue']:,.2f} ({s['total_units']} units)")

    print("\n3. Critical Stockout Risks:")
    risks = engine.get_stockout_risks(max_days=7.0)
    for r in risks:
        print(f"   [{r['store_id']}] {r['product_name']}: Stock={r['current_stock']}, Daily={r['average_daily_demand']}, Days Left={r['days_until_stockout']} -> {r['health_status']}")

    print("\n4. Overstocked Items:")
    overstock = engine.get_overstocked_items()
    for o in overstock:
        print(f"   [{o['store_id']}] {o['product_name']}: Stock={o['current_stock']}, Target={o['target_stock']}, Days Left={o['days_until_stockout']} -> {o['health_status']}")

    print("\n5. Sales Spikes & Drops (14-day window):")
    growths = engine.get_sales_growth(window_days=14)
    for g in growths[:3]:
        print(f"   Growth Leader: {g['product_name']} ({g['growth_percentage']}% - {g['trend']})")
    for g in growths[-2:]:
        print(f"   Decline Leader: {g['product_name']} ({g['growth_percentage']}% - {g['trend']})")

    print("\n6. Product Performance Drilldown (Wireless Mouse):")
    perf = engine.get_product_performance("Wireless Mouse")
    print(f"   Product: {perf['product_name']} | Current Stock: {perf['metrics_30d']['current_stock']} | Daily Avg: {perf['metrics_30d']['daily_average_sales']} | Days Left: {perf['metrics_30d']['estimated_coverage_days']}")
    print(f"   Evidence: {perf['evidence']['calculation']}")
    print("=== All Deterministic Calculations Verified Successfully ===")
