import importlib.util
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "xhs-collector"))
import collect_questions as collector

class CollectorTests(unittest.TestCase):
    def test_classifies_four_categories(self):
        self.assertEqual(collector.classify("Triton 算子优化", "framework"), "operator")
        self.assertEqual(collector.classify("torch.compile 编译器", "operator"), "compiler")
        self.assertEqual(collector.classify("NCCL 集合通信", "framework"), "communication")
        self.assertEqual(collector.classify("vLLM 推理框架", "operator"), "framework")

    def test_source_url_validates_identifier_and_token(self):
        url = collector.source_url({"id": "abc123456", "xsec_token": "tok_123"})
        self.assertEqual(url, "https://www.xiaohongshu.com/explore/abc123456?xsec_token=tok_123")
        self.assertEqual(collector.source_url({"id": "bad id"}), "")

    def test_reads_title_only_not_note_body(self):
        self.assertEqual(collector.title_from_item({"note_card": {"display_title": "标题", "desc": "正文不应被读取"}}), "标题")

    def test_static_data_schema_is_valid_and_empty_until_real_collection(self):
        data = json.loads((ROOT / "interview-questions/data/questions.json").read_text())
        self.assertEqual(data["schema_version"], 1)
        self.assertEqual(data["questions"], [])

if __name__ == "__main__":
    unittest.main()
