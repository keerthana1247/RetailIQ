"""
RetailIQ - Unit Tests for Deterministic Analytics Engine
"""

import unittest
import os
import sys

# Ensure src is in python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.analytics import AnalyticsEngine


class TestAnalyticsEngine(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = AnalyticsEngine()

    def test_data_loaded(self):
        self.assertFalse(self.engine.products_df.empty, "Products data should be loaded")
        self.assertFalse(self.engine.stores_df.empty, "Stores data should be loaded")
        self.assertFalse(self.engine.sales_df.empty, "Sales data should be loaded")
        self.assertFalse(self.engine.inventory_df.empty, "Inventory data should be loaded")

    def test_kpi_calculation(self):
        kpis = self.engine.get_kpis(days=30)
        self.assertGreater(kpis["total_revenue"], 0, "Revenue should be greater than 0")
        self.assertGreater(kpis["total_units_sold"], 0, "Units sold should be greater than 0")
        self.assertGreater(kpis["average_order_value"], 0, "AOV should be positive")
        self.assertEqual(kpis["active_stores"], 4, "Should have 4 active stores")

    def test_store_sales_ranking(self):
        ranking = self.engine.get_store_sales_ranking(days=30)
        self.assertEqual(len(ranking), 4)
        # S001 Flagship should be #1
        self.assertEqual(ranking[0]["store_id"], "S001")
        self.assertGreater(ranking[0]["total_revenue"], ranking[1]["total_revenue"])

    def test_stockout_risks_detection(self):
        risks = self.engine.get_stockout_risks(max_days=7.0)
        self.assertGreater(len(risks), 0, "Should detect critical stockout risks")
        risk_product_ids = [r["product_id"] for r in risks]
        self.assertIn("P001", risk_product_ids, "P001 should be flagged as stockout risk")

    def test_sales_spikes_and_drops(self):
        growth = self.engine.get_sales_growth(window_days=14)
        growth_dict = {g["product_id"]: g for g in growth}
        # P003 USB-C Multiport Hub should be SPIKE
        self.assertEqual(growth_dict["P003"]["trend"], "SPIKE")
        # P002 Mechanical Keyboard should be SHARP_DROP or DECLINE
        self.assertIn(growth_dict["P002"]["trend"], ["SHARP_DROP", "DECLINE"])

    def test_product_drilldown_and_evidence(self):
        perf = self.engine.get_product_performance("Wireless Mouse")
        self.assertTrue(perf["found"])
        self.assertEqual(perf["product_id"], "P001")
        self.assertIn("evidence", perf)
        self.assertIn("formula_stockout", perf["evidence"])
        self.assertIn("calculation", perf["evidence"])

    def test_unknown_product_safety(self):
        perf = self.engine.get_product_performance("Nonexistent Quantum Widget")
        self.assertFalse(perf["found"])
        self.assertIn("error", perf)


if __name__ == "__main__":
    unittest.main()
