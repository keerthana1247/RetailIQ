"""
RetailIQ - Unit and Integration Tests for FastAPI Backend Endpoints
"""

import unittest
import os
import sys

# Ensure project root is in python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import app


class TestFastAPIEndpoints(unittest.TestCase):
    def test_dashboard_endpoint(self):
        res = app.serve_dashboard()
        # Should return FileResponse pointing to index.html
        self.assertTrue(hasattr(res, "path"))
        self.assertTrue(res.path.endswith("index.html"))

    def test_api_info_endpoint(self):
        res = app.api_info()
        self.assertEqual(res["app"], "RetailIQ")
        self.assertEqual(res["status"], "running")

    def test_health_endpoint(self):
        res = app.health_check()
        self.assertEqual(res["status"], "healthy")
        self.assertIn("datasets", res)
        self.assertEqual(res["datasets"]["stores_count"], 4)
        self.assertEqual(res["datasets"]["products_count"], 15)
        self.assertGreater(res["datasets"]["sales_transactions"], 0)

    def test_kpis_endpoint(self):
        res = app.get_kpis(store_id=None, days=30)
        self.assertGreater(res["total_revenue"], 0)
        self.assertGreater(res["total_units_sold"], 0)
        self.assertGreater(res["average_order_value"], 0)

    def test_stores_endpoint(self):
        res = app.get_stores(days=30)
        self.assertEqual(len(res["stores"]), 4)
        self.assertEqual(res["stores"][0]["store_id"], "S001")

    def test_products_endpoint(self):
        res = app.get_products(store_id=None, days=30, limit=10)
        self.assertEqual(len(res["products"]), 10)

    def test_inventory_health_endpoint(self):
        res = app.get_inventory_health(store_id=None, days=30)
        self.assertEqual(res["total_items_monitored"], 60)

    def test_stockout_risks_endpoint(self):
        res = app.get_stockout_risks(store_id=None, max_days=7.0)
        self.assertGreater(res["count"], 0)
        for item in res["critical_stockouts"]:
            self.assertTrue(item["days_until_stockout"] is None or item["days_until_stockout"] <= 7.0 or item["current_stock"] == 0)

    def test_overstocked_endpoint(self):
        res = app.get_overstocked_items(store_id=None)
        self.assertGreater(res["count"], 0)

    def test_slow_moving_endpoint(self):
        res = app.get_slow_moving_items(store_id=None, max_daily_demand=0.5)
        self.assertGreater(res["count"], 0)

    def test_sales_growth_endpoint(self):
        res = app.get_sales_growth(store_id=None, window_days=14)
        self.assertGreater(res["spikes_count"], 0)
        self.assertGreater(res["drops_count"], 0)

    def test_attention_endpoint(self):
        res = app.get_today_attention(store_id=None)
        self.assertIn("critical_stockouts", res)
        self.assertIn("overstocked_items", res)
        self.assertIn("sales_spikes", res)
        self.assertIn("sales_drops", res)

    def test_product_drilldown_endpoint(self):
        res = app.get_product_details("Wireless Mouse", store_id=None)
        self.assertEqual(res["product_id"], "P001")
        self.assertIn("evidence", res)

    def test_unknown_product_404(self):
        with self.assertRaises(app.HTTPException) as ctx:
            app.get_product_details("NonExistentItem999")
        self.assertEqual(ctx.exception.status_code, 404)


if __name__ == "__main__":
    unittest.main()
