import os, tempfile, unittest
from pathlib import Path

from src.analytics import AnalyticsEngine
from src import retrieval
from src.query_engine import understand_query

class RetrievalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = AnalyticsEngine()
        cls.old_dir = retrieval.INDEX_DIR
        cls.tmp = tempfile.TemporaryDirectory()
        retrieval.INDEX_DIR = cls.tmp.name
        retrieval.INDEX_FILE = os.path.join(cls.tmp.name, "index.npz")
        retrieval.META_FILE = os.path.join(cls.tmp.name, "metadata.json")

    @classmethod
    def tearDownClass(cls):
        retrieval.INDEX_DIR = cls.old_dir
        cls.tmp.cleanup()

    def test_documents_have_metadata(self):
        docs = retrieval.build_documents(self.engine)
        self.assertGreater(len(docs), 0)
        self.assertTrue(all("id" in d and "text" in d and "metadata" in d for d in docs))

    def test_build_and_load_index(self):
        result = retrieval.build_index(self.engine)
        self.assertGreater(result["documents"], 0)
        self.assertTrue(os.path.exists(retrieval.INDEX_FILE))
        self.assertIsNotNone(retrieval.load_index())

    def test_retrieve(self):
        result = retrieval.retrieve(self.engine, "products at stockout risk", 5)
        self.assertIn("results", result)
        self.assertLessEqual(len(result["results"]), 5)

    def test_empty_query(self):
        result = retrieval.retrieve(self.engine, "", 5)
        self.assertEqual(result["results"], [])
        self.assertIn("error", result)

    def test_query_understanding(self):
        self.assertEqual(understand_query("Which products are at stockout risk?")["intent"], "stockout")
        self.assertEqual(understand_query("What is the most profitable product?")["intent"], "profit_unavailable")
        self.assertEqual(understand_query("How is S001 performing?")["store_id"], "S001")

if __name__ == "__main__":
    unittest.main()
