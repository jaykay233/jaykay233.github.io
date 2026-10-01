import json
import shutil
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.request import urlopen
from http.server import ThreadingHTTPServer

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.server import Handler  # noqa: E402
from scripts.build_pages import build as build_pages  # noqa: E402


class ApiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)

    def get_json(self, path):
        with urlopen(self.base + path) as response:
            return json.loads(response.read())

    def test_health_and_stats_include_curated_and_pending_records(self):
        self.assertTrue(self.get_json("/api/health")["ok"])
        stats = self.get_json("/api/stats")
        self.assertEqual(stats["models"], stats["curated_models"] + stats["pending_models"])
        self.assertEqual(stats["curated_models"], 20)
        discovered = json.loads((ROOT / "data" / "discovered_models.json").read_text(encoding="utf-8"))
        self.assertEqual(stats["pending_models"], len(discovered))
        curated = json.loads((ROOT / "data" / "models.json").read_text(encoding="utf-8"))
        self.assertEqual(stats["new_models"], sum(1 for model in curated if model.get("added_in_snapshot")))
        metadata = json.loads((ROOT / "data" / "discovery_metadata.json").read_text(encoding="utf-8"))
        self.assertEqual(stats["snapshot_date"], metadata["snapshot_date"])
        self.assertEqual(stats["taxonomy_only"], 1)
        self.assertIn("全量", stats["scope"])
        review = json.loads((ROOT / "data" / "architecture_review_summary.json").read_text(encoding="utf-8"))
        self.assertEqual(stats["config_review"]["config_status"], review["config_status"])
        self.assertEqual(stats["config_review"]["with_structural_findings"], review["with_structural_findings"])
        self.assertEqual(stats["model_card_review"]["selected_representatives"], 100)
        self.assertEqual(stats["model_card_review"]["status"]["ok"], 94)
        self.assertEqual(stats["model_card_interpretation"]["reviewed_models"], 7)

    def test_model_search_and_confirmed_module_filter(self):
        results = self.get_json("/api/models?q=deepseek&module=mla")
        self.assertEqual(results["total"], 1)
        self.assertEqual(results["items"][0]["id"], "deepseek-v2")
        pending = self.get_json("/api/models?module=mla")
        self.assertTrue(all(item.get("architecture_status") != "pending" for item in pending["items"]))

    def test_pending_candidate_is_a_discovery_record_not_an_architecture(self):
        model = self.get_json("/api/models/hf-xiaomimimo-mimo-v2-6-flash-mopd")
        self.assertEqual(model["architecture_status"], "pending")
        self.assertIsNone(model["architecture"])
        self.assertEqual(model["modules"], [])
        self.assertEqual(model["hub_id"], "XiaomiMiMo/MiMo-V2.6-Flash-MOPD")
        self.assertIn("model_type", model["config_summary"])
        self.assertGreaterEqual(model["popularity_score"], 0)
        self.assertGreaterEqual(model["popularity_signals"], 1)
        results = self.get_json("/api/models?module=mhc")
        self.assertEqual(results["total"], 3)

    def test_config_and_model_card_evidence_stay_unverified(self):
        model = self.get_json("/api/models/hf-qwen-qwen3-next-80b-a3b-instruct")
        self.assertEqual(model["architecture_status"], "pending")
        self.assertEqual(model["modules"], [])
        self.assertIn("gated-deltanet", model["candidate_modules"])
        self.assertEqual(model["config_review"]["status"], "reviewed")
        self.assertTrue(any(item["confidence"] == "family-config-inference" for item in model["config_review"]["findings"]))
        self.assertEqual(model["model_card_evidence"]["status"], "ok")
        self.assertTrue(model["model_card_evidence"]["source"].endswith("/README.md"))
        self.assertEqual(model["model_card_interpretation"]["status"], "model-card-interpreted")
        self.assertGreaterEqual(len(model["model_card_interpretation"]["claims"]), 4)
        stats = self.get_json("/api/stats")
        self.assertEqual(stats["curated_models"], 20)
        discovered = json.loads((ROOT / "data" / "discovered_models.json").read_text(encoding="utf-8"))
        self.assertEqual(stats["pending_models"], len(discovered))

    def test_mhc_links_only_primary_source_verified_models_and_ihc_stays_unverified(self):
        mhc = self.get_json("/api/modules/mhc")
        self.assertEqual(mhc["count"], 3)
        self.assertEqual({m["id"] for m in mhc["models"]}, {"deepseek-v4-pro", "deepseek-v4-flash", "xing4-29b-a4b"})
        self.assertEqual(mhc["status"], "verified")
        ihc = self.get_json("/api/modules/ihc")
        self.assertEqual(ihc["count"], 0)
        self.assertEqual(ihc["status"], "taxonomy-only")

    def test_catalog_is_unique_and_candidates_are_from_2025_onward(self):
        models = self.get_json("/api/models")["items"]
        modules = self.get_json("/api/modules")["items"]
        module_ids = {module["id"] for module in modules}
        self.assertTrue(all(set(model["modules"]) <= module_ids for model in models))
        self.assertEqual(len({model["id"] for model in models}), len(models))
        candidates = [m for m in models if m.get("architecture_status") == "pending"]
        self.assertGreaterEqual(len(candidates), 200)
        self.assertTrue(all(m["hub_created"] >= "2025-01-01" for m in candidates))
        self.assertTrue(all(not m["modules"] and m["architecture"] is None for m in candidates))
        hubs = [m["hub_id"].casefold() for m in candidates]
        self.assertEqual(len(hubs), len(set(hubs)))

    def test_frontend_is_served(self):
        with urlopen(self.base + "/") as response:
            self.assertIn(b"ArchAtlas", response.read())
        with urlopen(self.base + "/app.js") as response:
            body = response.read()
            self.assertEqual(response.headers.get("Cache-Control"), "no-store")
            self.assertIn(b"renderPendingDetail", body)
            self.assertIn(b"sort: 'popular'", body)
            self.assertIn("待拆解".encode(), body)
            self.assertIn("模型卡证据摘录".encode(), body)
            self.assertIn("配置证据初筛".encode(), body)
            self.assertIn("模型卡模块解读".encode(), body)
            self.assertIn("getModuleAssociations".encode(), body)
            self.assertIn("已核验关联模型".encode(), body)
            self.assertIn("候选关联".encode(), body)
            self.assertIn("module-model-search".encode(), body)
            self.assertIn("热门优先".encode(), body)
            self.assertIn("最新优先".encode(), body)

    def test_static_pages_build_contains_data_and_uses_relative_assets(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "archatlas"
            build_pages(output)
            html = (output / "index.html").read_text(encoding="utf-8")
            app = (output / "app.js").read_text(encoding="utf-8")
            models = json.loads((output / "api" / "models.json").read_text(encoding="utf-8"))
            modules = json.loads((output / "api" / "modules.json").read_text(encoding="utf-8"))
            stats = json.loads((output / "api" / "stats.json").read_text(encoding="utf-8"))
            self.assertIn('href="styles.css?', html)
            self.assertIn('src="app.js?', html)
            self.assertIn("api/${path.replace", app)
            self.assertIn("hostname.endsWith('github.io')", app)
            self.assertEqual(stats["models"], len(models["items"]))
            self.assertEqual(stats["modules"], len([m for m in modules["items"] if m["count"] > 0]))
            self.assertGreater(len(models["items"]), 1000)


if __name__ == "__main__":
    unittest.main()
