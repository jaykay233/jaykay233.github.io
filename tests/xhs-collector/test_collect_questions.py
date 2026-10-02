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
        self.assertEqual(collector.question_candidates("✅ 1. LoRA低秩适配原理&优势"), ["LoRA 低秩适配原理和优势？"])
        self.assertEqual(collector.question_candidates("请详细介绍NCCL Broadcast通信原语的实现原理。"), ["请详细介绍 NCCL Broadcast 通信原语的实现原理？"])
        self.assertEqual(collector.question_candidates("你在学校写过 CUDA 或者做过 GPU 算子项目吗？"), [])
        self.assertEqual(collector.question_candidates("面试官真正会往下追的是：图怎么捕获，IR 为什么分层？"), [])
        self.assertEqual(collector.question_candidates("上来先聊项目，追问具体参数怎么算的？"), [])
        self.assertEqual(collector.question_candidates("常见追问：怎么组合？"), [])
        self.assertTrue(collector.is_low_signal_question("常见追问：怎么组合？"))

    def test_knowledge_points_require_concrete_concepts(self):
        self.assertIn("NCCL Collectives", collector.extract_knowledge_points("NCCL ReduceScatter 的 Ring 算法是什么？"))
        self.assertIn("Roofline / Memory Bandwidth", collector.extract_knowledge_points("Memory-bound Kernel 如何用 Roofline 判断？"))
        self.assertEqual(collector.extract_knowledge_points("GPU 间为什么需要通信？"), [])

    def test_clean_question_preserves_technical_tokens(self):
        self.assertEqual(collector.clean_question("🔹 all_gather和C++优化!"), "all_gather 和 C++ 优化？")

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
        self.assertTrue(all(q.get("question") and (q.get("source_url") or q.get("source_title")) for q in data["questions"]))
        self.assertTrue(all(q.get("knowledge_points") for q in data["questions"]))
        self.assertFalse(any("你在学校写过 CUDA" in q["question"] for q in data["questions"]))
        self.assertFalse(any("面试官真正会往下追" in q["question"] or "上来先聊项目" in q["question"] or "常见追问" in q["question"] for q in data["questions"]))

if __name__ == "__main__":
    unittest.main()
