"""Demo data for the presentation: team members, 100+ warehouse items, past orders, label stock lookup."""
import sqlite3
import tempfile
from contextlib import closing
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.packing_catalog import CATALOG, PRESENTATION_SKUS, SAMPLE_ORDERS, TEAM
from app.voice_commands import packing_answer


class DemoDataTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.settings = Settings(camera_autostart=False)

    def client(self):
        return TestClient(create_app(self.settings, state_root=self.temp.name))

    def test_team_catalog_and_orders(self):
        with self.client() as c:
            state = c.get("/api/packing").json()
        self.assertEqual([(u["name"], u["uid"]) for u in state["users"]], list(TEAM))
        products = state["products"]
        self.assertGreaterEqual(len(products), 100)
        self.assertEqual([p["sku"] for p in products[:4]], list(PRESENTATION_SKUS))  # presentation items on top
        self.assertTrue(all(p["bin"] for p in products))  # every item has a warehouse location
        self.assertEqual(len({p["bin"] for p in products}), len(products))
        orders = {o["number"]: o for o in state["orders"]}
        self.assertEqual(orders[123]["customer"], TEAM[0][0])
        self.assertEqual(len(orders), 1 + len(SAMPLE_ORDERS))
        self.assertTrue({"delivered", "shipped", "awaiting_dispatch", "received"} <= {o["state"] for o in orders.values()})
        # past orders never hold stock: only #123 (packing) reserves
        self.assertEqual(sum(p["reserved"] for p in products), 3)
        self.assertTrue(all(o["customer"] in dict(TEAM) for o in orders.values()))

    def test_an_older_store_is_brought_up_to_date_once(self):
        with self.client():
            pass
        db_path = next(Path(self.temp.name).rglob("metadata.sqlite3"))  # the packing store (web/app/store.py)
        with closing(sqlite3.connect(db_path)) as db, db:  # like a store made before this change
            db.execute("UPDATE customers SET name='홍길동' WHERE name=?", (TEAM[0][0],))
            db.execute("INSERT INTO customers(name) VALUES ('김서연')")
            db.execute("DELETE FROM customer_rfid")
            db.execute("DELETE FROM order_items WHERE order_id IN (SELECT id FROM orders WHERE number<>123)")
            db.execute("DELETE FROM orders WHERE number<>123")
            db.execute("DELETE FROM products WHERE sku > 'PK-005'")
            db.execute("UPDATE products SET bin=''")
        for _ in range(2):
            with self.client() as c:
                state = c.get("/api/packing").json()
        names = [u["name"] for u in state["users"]]
        self.assertEqual(sorted(names), sorted(name for name, _ in TEAM))
        self.assertNotIn("홍길동", names)
        self.assertEqual(next(o for o in state["orders"] if o["number"] == 123)["customer"], TEAM[0][0])
        self.assertEqual(len(state["products"]), 5 + len(CATALOG))
        self.assertEqual(len(state["orders"]), 1 + len(SAMPLE_ORDERS))
        self.assertEqual(state["products"][0]["bin"], "A동 01열 1단")

    def test_label_lookup_shows_stock_and_location_without_a_robot_task(self):
        with self.client() as c:
            found = c.get("/api/packing/stock/tag/0b 71 e5 5d")
            self.assertEqual(found.status_code, 200)
            body = found.json()
            self.assertEqual((body["uid"], body["product"]["sku"], body["product"]["stock"]), ("0B71E55D", "PK-001", 10))
            self.assertEqual(body["product"]["bin"], "A동 01열 1단")
            self.assertEqual(body["tag"]["target_box_id"], "BOX-01")
            self.assertEqual(c.get("/api/packing/stock/tag/E75D").json()["product"]["sku"], "PK-002")  # partial read
            toy = c.get("/api/packing/stock/tag/0B71EC5D")
            self.assertEqual(toy.status_code, 404)
            self.assertIn("등록되지 않은 태그", toy.json()["detail"])
            self.assertEqual(c.get("/api/packing/stock/tag/E7").status_code, 422)
            self.assertIsNone(c.get("/api/v1/current-task").json()["task"])  # lookup only, nothing queued

    def test_stock_question_reads_out_only_the_presentation_items(self):
        app = create_app(self.settings, state_root=self.temp.name)
        with TestClient(app):
            text = packing_answer(app.state.pipeline.packing, "query-stock").text
        self.assertIn("쫀득초코칩", text)
        self.assertNotIn("새우깡", text)
        self.assertIn(f"{len(CATALOG) + 1}개 품목", text)


if __name__ == "__main__":
    unittest.main()
