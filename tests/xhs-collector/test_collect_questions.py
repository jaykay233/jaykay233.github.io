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

    def test_extracts_short_question_lines_without_persisting_full_note(self):
        text = "面试经验\n1. 什么是 GQA？\n2. 如何实现 FlashAttention？\n我这里整理了大量资料供大家参考"
        found = collector.question_candidates(text)
        self.assertEqual(found, ["什么是 GQA？", "如何实现 FlashAttention？"])
        self.assertNotIn("大量资料", " ".join(found))
        self.assertEqual(collector.question_candidates("◼GPU作用: 并行计算大法好！"), [])
        self.assertEqual(collector.question_candidates("请详细介绍NCCL Broadcast通信原语的实现原理。"), ["请详细介绍NCCL Broadcast通信原语的实现原理。"])

    def test_source_url_validates_identifier_and_encodes_token(self):
        url = collector.source_url({"id": "abc123456", "xsec_token": "tok_123"})
        self.assertEqual(url, "https://www.xiaohongshu.com/explore/abc123456?xsec_token=tok_123")
        encoded = collector.source_url({"id": "abc123456", "xsec_token": "token+/="})
        self.assertEqual(encoded, "https://www.xiaohongshu.com/explore/abc123456?xsec_token=token%2B%2F%3D")
        self.assertEqual(collector.source_url({"id": "bad id"}), "")

    def test_search_title_reader_uses_title_not_description(self):
        self.assertEqual(collector.title_from_item({"note_card": {"display_title": "标题", "desc": "正文不应被读取"}}), "标题")

    def test_static_data_schema_has_only_supported_categories(self):
        data = json.loads((ROOT / "interview-questions/data/questions.json").read_text())
        self.assertEqual(data["schema_version"], 1)
        self.assertGreater(len(data["questions"]), 0)
        self.assertTrue({q["category"] for q in data["questions"]} <= {"operator", "compiler", "communication", "framework"})
        self.assertTrue(all(q.get("question") and q.get("source_url") for q in data["questions"]))

if __name__ == "__main__":
    unittest.main()
