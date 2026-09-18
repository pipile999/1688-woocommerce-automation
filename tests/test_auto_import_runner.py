import copy
from contextlib import nullcontext
import tempfile
import time
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from app.auto_import_runner import Runner, read_tasks
from app.google_keyword_planner import GoogleKeywordPlanner, bounds, score_keywords, recommend_title
from app.runner_content import canonical, priced_skus, select_category, deterministic_pack
from app.runner_state import StageStore, ReviewRequired, ReviewQueue, save
from app.runner_woocommerce import payloads, verify_saved, identity, Store


class LocalRunnerTests(unittest.TestCase):
    def test_checkpoint_reuse_and_change(self):
        with tempfile.TemporaryDirectory() as d:
            store = StageStore(d)
            calls = []
            op = lambda: (calls.append(1) or {"ok": True})
            self.assertEqual(store.run("content", "same", op)[1], "CACHE_MISS")
            self.assertEqual(StageStore(d).run("content", "same", op)[1], "CACHE_HIT")
            self.assertEqual(store.run("content", "changed", op)[1], "CACHE_MISS")
            self.assertEqual(len(calls), 2)

    def test_cached_results_cannot_be_mutated_by_caller(self):
        with tempfile.TemporaryDirectory() as d:
            s = StageStore(d)
            value, _ = s.run("copy", "same", lambda: {"title": "original"})
            value["title"] = "changed"
            s.run("another", "same", lambda: {})
            self.assertEqual(StageStore(d).run("copy", "same", lambda: {})[0]["title"], "original")

    def test_changed_artifact_invalidates_checkpoint(self):
        with tempfile.TemporaryDirectory() as d:
            artifact = Path(d) / "a.json"
            save(artifact, {"a": 1})
            s = StageStore(d)
            op = lambda: {"artifacts": [str(artifact)]}
            s.run("image", "same", op)
            save(artifact, {"a": 2})
            self.assertEqual(s.run("image", "same", op)[1], "CACHE_MISS")

    def test_exact_keyword_market_ttl(self):
        with tempfile.TemporaryDirectory() as d:
            planner = GoogleKeywordPlanner(Path(d) / "cache.json")
            planner.cache.put(dict(keyword="metal grinder", country="US", language="en", timestamp=time.time(),
                                   source="google_keyword_planner_ui", monthly_searches_min=10,
                                   monthly_searches_max=100, competition="LOW", status="VERIFIED_REPORTED_RANGE"))
            with patch.object(planner, "_api_ideas", side_effect=AssertionError("Duplicate query")):
                result = planner.query(["metal grinder", " Metal Grinder "])
                self.assertEqual(len(result), 1)
            self.assertEqual(bounds(result["metal grinder"]), (10, 100))
            planner.country = "GB"
            self.assertIsNone(planner.cached("metal grinder"))
            planner.country = "US"
            planner.cache.ttl = -1
            self.assertIsNone(planner.cached("metal grinder"))

    def test_missing_google_keeps_title_and_no_keys_read(self):
        with tempfile.TemporaryDirectory() as d:
            p = GoogleKeywordPlanner(Path(d) / "c.json", allow_api=False)
            with patch.dict("os.environ", {}, clear=True):
                rows = p.query(["tube", "tube"])
            self.assertEqual(rows["tube"]["status"], "DATA_UNAVAILABLE")
            ranked = score_keywords(rows, {"tube": {"supported": True}}, [], "1")
            self.assertEqual(recommend_title("Existing Tube", ranked, {})["title"], "Existing Tube")
            self.assertEqual(p.keyword_api_queries, 0)

    def test_wrong_serp_and_map_are_hard_exclusions(self):
        rows = {"tube": {"volume": 99999, "serp_match": "REJECT", "status": "VERIFIED_KEYWORD_DATA"},
                "plastic tube": {"volume": 10, "serp_match": "PASS", "status": "VERIFIED_KEYWORD_DATA"}}
        rel = {k: {"supported": True} for k in rows}
        ranked = score_keywords(rows, rel, [{"offer_id": "2", "primary_keyword": "plastic tube"}], "1")
        self.assertFalse(any(r["eligible"] for r in ranked))

    def test_zero_range_is_not_positive_demand(self):
        ranked = score_keywords({"tube": {"monthly_searches_min": 0, "monthly_searches_max": 10,
            "serp_match": "PASS", "status": "VERIFIED_REPORTED_RANGE"}}, {"tube": {"supported": True}}, [], "1")
        self.assertFalse(ranked[0]["eligible"])

    def test_price_always_fresh_and_identifiers_immutable(self):
        source = {"skus": [{"sku": "123", "variation_id": "456", "spec_id": "abc", "source_spec_id": "abc",
                            "attributes": {"颜色": "黑色"}, "source_price": "6.7", "sale_price": "stale"}]}
        approved = copy.deepcopy(source)
        approved["skus"][0]["attributes"] = {"Color": "Black"}
        self.assertEqual(priced_skus(source, approved)[0]["sale_price"], "1.43")
        source["skus"][0]["source_price"] = "13.4"
        self.assertEqual(priced_skus(source, approved)[0]["sale_price"], "2.86")
        approved["skus"][0]["variation_id"] = "wrong"
        with self.assertRaises(ReviewRequired):
            priced_skus(source, approved)

    def test_category_deepest_and_unresolved(self):
        tree = [{"id": 1, "name": "Packaging", "parent": 0}, {"id": 2, "name": "Tubes", "parent": 1}]
        self.assertEqual(select_category(tree, {"product_type": "tube"}, ["Packaging", "Tubes"])["id"], 2)
        with self.assertRaises(ReviewRequired):
            select_category(tree, {"product_type": "grinder"}, ["Grinders"])

    def test_no_cross_host_or_duplicate_input(self):
        with self.assertRaises(ValueError):
            canonical("https://evil1688.com/offer/123.html")
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "tasks.json"
            save(path, [{"source_url": "https://detail.1688.com/offer/123.html"}] * 2)
            with self.assertRaises(ValueError):
                read_tasks(path)

    def test_excel_sequence_selection_and_hyperlink(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "input.xlsx"
            sheet = '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheetData><row r="2"><c r="A2"><v>21</v></c><c r="C2" t="inlineStr"><is><t>https://detail.1688.com/offer/123.html</t></is></c></row><row r="3"><c r="A3"><v>22</v></c><c r="C3" t="inlineStr"><is><t>Link label</t></is></c></row></sheetData><hyperlinks><hyperlink ref="C3" r:id="rId1"/></hyperlinks></worksheet>'
            rels = '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Target="https://detail.1688.com/offer/456.html" TargetMode="External"/></Relationships>'
            with zipfile.ZipFile(path, "w") as z:
                z.writestr("xl/worksheets/sheet1.xml", sheet)
                z.writestr("xl/worksheets/_rels/sheet1.xml.rels", rels)
            selected = read_tasks(path, 22, 22)
            self.assertEqual([r["offer_id"] for r in selected], ["456"])
            self.assertEqual(selected[0]["sequence"], 22)
            with self.assertRaises(ValueError):
                read_tasks(path, 21, 23)

    def test_unknown_product_not_invented(self):
        with self.assertRaises(ReviewRequired):
            deterministic_pack({"title": "神奇新品", "skus": []})

    def test_review_queue_idempotent(self):
        with tempfile.TemporaryDirectory() as d:
            q = ReviewQueue(Path(d) / "queue.json")
            q.add("1", "image", "unknown")
            q.add("1", "image", "unknown")
            self.assertEqual(len(q.items), 1)

    def test_model_source_conflict_not_hidden(self):
        self.assertEqual(identity({"meta_data": [{"key": "_1688_offer_id", "value": "1"},
            {"key": "_1688_source_url", "value": "https://detail.1688.com/offer/2.html"}]}), {"1", "2"})

    def test_one_product_failure_does_not_stop_batch(self):
        from app.auto_import_runner import ROOT
        with tempfile.TemporaryDirectory() as d:
            runner = Runner(ROOT, dry_run=True, run_dir=d)
            tasks = [{"offer_id": str(i), "source_url": f"https://detail.1688.com/offer/{i}.html"} for i in (1, 2)]
            with patch.object(runner, "acquire", side_effect=[ReviewRequired("needs review"), RuntimeError("opaque secret error")]), \
                 patch("app.auto_import_runner.exclusive_lock", return_value=nullcontext()):
                results = runner.run(tasks)
            self.assertEqual(len(results["products"]), 2)
            self.assertEqual(results["products"][1]["reason"], "RuntimeError")
            self.assertEqual(results["review_required"], 1)
            self.assertEqual(results["failures"], 1)


class FakeWoo:
    def __init__(self):
        self.parents, self.variants, self.posts = [], [], []
        self.fail_http = False

    def get(self, path, params=None):
        if path == "products/categories":
            return [{"id": 1, "name": "Tubes", "parent": 0}]
        if path == "products":
            return copy.deepcopy(self.parents)
        if path.endswith("/variations"):
            return copy.deepcopy(self.variants)
        return copy.deepcopy(self.parents[0])

    def post(self, path, payload):
        self.posts.append((path, copy.deepcopy(payload)))
        if path == "products":
            p = copy.deepcopy(payload)
            p.update(id=10, permalink="https://example.invalid/product/tube")
            p["images"] = [dict(i, src="https://example.invalid/full.webp") for i in p["images"]]
            self.parents.append(p)
            return copy.deepcopy(p)
        if path.endswith("/variations"):
            v = copy.deepcopy(payload)
            v["id"] = len(self.variants) + 100
            if v.get("image"):
                v["image"]["src"] = "https://example.invalid/full.webp"
            self.variants.append(v)
            return copy.deepcopy(v)
        self.parents[0].update(payload)
        if "images" in payload:
            self.parents[0]["images"] = [dict(i, src="https://example.invalid/full.webp") for i in payload["images"]]
        return copy.deepcopy(self.parents[0])


class PublicationTests(unittest.TestCase):
    def fixture(self, folder):
        from app.runner_state import file_hash
        path = Path(folder) / "image.json"
        save(path, {"test": "fixture bytes, mocked media transport"})
        sha = file_hash(path)
        p = dict(offer_id="123", source_url="https://detail.1688.com/offer/123.html", model="Model: 123",
                 fingerprint="verified-fixture", title="Plastic Tube", slug="plastic-tube", category={"id": 1},
                 description_overview="Plastic tube.", description_specs={"Material": "Plastic"},
                 short_description="Plastic tube.", seo={"meta_title": "Plastic Tube", "meta_description": "Plastic tube.", "focus_keyword": "plastic tube"},
                 skus=[dict(sku="unchanged", variation_id="original-id", spec_id="spec", source_spec_id="spec",
                            source_price="6.7", sale_price="1.43", stock=None, attributes={"Color": "Black"}, image_url="https://source.invalid/image")])
        images = dict(publication_qa="PASS", records=[dict(source_offer_id="123", source_image_url="https://source.invalid/image",
                       source_url=p["source_url"], image_role="featured", final_path=str(path), final_sha256=sha)])
        return p, images

    def test_publish_only_after_acceptance_and_resume_no_writes(self):
        with tempfile.TemporaryDirectory() as d:
            client = FakeWoo()
            store = Store(client)
            product, images = self.fixture(d)
            with patch("app.runner_woocommerce.wp_request") as media, patch("app.runner_woocommerce.verify_public_image", return_value={"pass": True}):
                media.return_value.json.return_value = {"id": 3, "source_url": "https://example.invalid/full.webp",
                                                       "featured_media": 3, "content": {"rendered": ""}}
                result = store.upload(product, images, Path(d))
                first = len(client.posts)
                second = store.upload(product, images, Path(d))
                self.assertEqual(result["status"], "publish")
                self.assertEqual(second["status"], "publish")
                self.assertEqual(len(client.posts), first)
                self.assertEqual(sum(call.args[1] == "POST" for call in media.call_args_list), 1)
                self.assertEqual(client.posts[-1][1], {"status": "publish"})

    def test_broken_image_never_publishes(self):
        with tempfile.TemporaryDirectory() as d:
            client = FakeWoo()
            store = Store(client)
            product, images = self.fixture(d)
            with patch("app.runner_woocommerce.wp_request") as media, patch("app.runner_woocommerce.verify_public_image", return_value={"pass": False}):
                media.return_value.json.return_value = {"id": 3, "source_url": "https://example.invalid/broken.webp"}
                with self.assertRaises(ReviewRequired):
                    store.upload(product, images, Path(d))
            self.assertEqual(client.parents[0]["status"], "draft")
            self.assertFalse(any(p.get("status") == "publish" for _, p in client.posts))

    def test_duplicate_mapping_no_write(self):
        with tempfile.TemporaryDirectory() as d:
            client = FakeWoo()
            client.parents = [{"id": i, "meta_data": [{"key": "_1688_offer_id", "value": "123"}]} for i in (1, 2)]
            store = Store(client)
            p, imgs = self.fixture(d)
            with self.assertRaisesRegex(ReviewRequired, "DUPLICATE_MAPPING"):
                store.upload(p, imgs, Path(d))
            self.assertEqual(client.posts, [])

    def test_unknown_media_post_outcome_not_retried(self):
        with tempfile.TemporaryDirectory() as d:
            store = Store(FakeWoo())
            p, imgs = self.fixture(d)
            with patch("app.runner_woocommerce.wp_request", side_effect=TimeoutError) as media:
                with self.assertRaises(TimeoutError):
                    store.upload(p, imgs, Path(d))
                with self.assertRaisesRegex(ReviewRequired, "UNCERTAIN_REMOTE_WRITE"):
                    store.upload(p, imgs, Path(d))
                self.assertEqual(media.call_count, 1)


if __name__ == "__main__":
    unittest.main()
