#!/usr/bin/env python3
"""Locally distill short interview-question prompts from public XHS notes.

Authentication is held in macOS Keychain via Python keyring. This intentionally
reads search results and short note descriptions to extract question-like lines; it never
saves full note text, comments, profiles, or media, and never bypasses challenges.
"""
from __future__ import annotations
import argparse, datetime as dt, html, json, os, re, sys, time, unicodedata, urllib.parse
from pathlib import Path

UPSTREAM = Path(os.environ.get("SPIDER_XHS_PATH", Path.home() / ".local/share/archatlas/Spider_XHS"))
if UPSTREAM.is_dir():
    sys.path.insert(0, str(UPSTREAM))

ROOT = Path(__file__).resolve().parents[2]
DATA_PATH = ROOT / "interview-questions" / "data" / "questions.json"
SERVICE = "archatlas-xhs-question-index"
ACCOUNT = os.environ.get("USER", "default")
SEARCHES = {
    "operator": ["CUDA Triton 算子 面试", "GPU 算子优化 面试题"],
    "compiler": ["大模型 编译器 面试题", "torch.compile 编译 面试"],
    "communication": ["NCCL 集合通信 面试题", "RDMA 大模型通信 面试"],
    "framework": ["vLLM Megatron 面试题", "大模型训练推理框架 面试"],
}
KNOWLEDGE_POINT_RULES = [
    ("Pinned/ Pageable Memory", r"pinned memory|pageable memory|pinned|pageable"),
    ("H2D / DMA", r"h2d|host.?to.?device|dma"),
    ("NCCL Collectives", r"nccl|all.?reduce|all.?gather|reduce.?scatter|all.?to.?all|broadcast"),
    ("RDMA / InfiniBand", r"rdma|infiniband|\bib\b|verbs|gpudirect"),
    ("Tensor Parallelism", r"tensor parallel|\btp\b|张量并行"),
    ("Sequence Parallelism", r"sequence parallel|\bsp\b|序列并行|ulysses|ring attention"),
    ("Context Parallelism", r"context parallel|\bcp\b|dcp|上下文并行"),
    ("Expert Parallelism / MoE", r"expert parallel|\bep\b|deep.?ep|expert|moe|专家并行"),
    ("FSDP / ZeRO", r"fsdp|zero.?[123]|fully sharded"),
    ("CUDA / PTX", r"cuda|\bptx\b|\bsass\b|nvcc|kernel"),
    ("Triton", r"triton"),
    ("torch.compile / Inductor", r"torch\.compile|inductor|torchdynamo|aotautograd"),
    ("MLIR / PassManager", r"mlir|passmanager|pass manager|\bscf\b"),
    ("FlashAttention / Attention", r"flash.?attention|online softmax|attention|gqa|mqa"),
    ("KV Cache / PagedAttention", r"kv.?cache|paged.?attention"),
    ("Roofline / Memory Bandwidth", r"roofline|memory.?bound|显存带宽|memory bandwidth"),
    ("Occupancy / Latency Hiding", r"occupancy|active warps|persistent kernel|latency hiding"),
    ("TMA / Asynchronous Pipeline", r"\btma\b|cp\.async|wgmma|tcgen|pipeline|num_stages"),
    ("GEMM / Tiling", r"gemm|tiling|tile scheduling|grouped gemm"),
    ("GEMV / Reduction", r"gemv|reduction|规约"),
    ("FP8 / Quantization", r"mxfp8|fp8|int8|quant|量化|反量化"),
    ("Shared Memory / Data Reuse", r"shared memory|共享内存|data reuse"),
    ("Kubernetes / GPU Scheduling", r"kubernetes|\bk8s\b|gpu scheduling|mig|device plugin"),
    ("vLLM / Inference Serving", r"vllm|sglang|inference serving|continuous batching"),
    ("Checkpointing / Fault Tolerance", r"checkpoint|故障恢复|fault tolerance"),
    ("TCP/IP / Network", r"tcp|network|网络|infini.?band"),
    ("GPU Topology / NUMA", r"topology|numa|nvswitch|pcie|nvlink"),
]
LOW_SIGNAL_PATTERNS = (
    r"你在学校.*(写过|做过)|有没有.*(项目|经验)|做过.*吗",
    r"为什么选择.*(公司|岗位|行业)|最棘手.*(问题|难题)|保持专注",
    r"做过什么优化吗|聊聊你的项目经历|介绍一下你的项目经历",
    r"上来先聊项目|面试官.*(追问|往下追)|八股集中|考的是|回答了.*(功能|接口|开发流程)",
)

CATEGORY_TERMS = {
    "operator": ("算子", "cuda", "triton", "kernel", "内核", "算子优化", "flashattention", "flash attention"),
    "compiler": ("编译器", "编译", "compiler", "torch.compile", "inductor", "算子融合", "图优化"),
    "communication": ("通信", "nccl", "rdma", "allreduce", "all-reduce", "all_gather", "all-gather", "集合通信", "p2p"),
    "framework": ("框架", "vllm", "sglang", "megatron", "deepspeed", "训练框架", "推理框架", "分布式训练"),
}

def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).lower()
    return re.sub(r"[\W_]+", "", text, flags=re.UNICODE)


def clean_plain_text(text: str) -> str:
    """Remove decorative/formatting characters while preserving technical tokens."""
    text = html.unescape(unicodedata.normalize("NFKC", str(text or "")))
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"```|`|\*\*|~~", "", text)
    # Emojis and decorative symbols become spaces; retain common code/token marks.
    keep_symbols = set("+-./_#=<>%")
    text = "".join(
        " " if unicodedata.category(char).startswith("S") and char not in keep_symbols else char
        for char in text
    )
    text = text.replace("&", "和")
    text = re.sub(r"^\s*\d{1,3}[.)、]\s*", "", text)
    text = re.sub(r"(?<=[\u4e00-\u9fff])(?=[A-Za-z0-9])", " ", text)
    text = re.sub(r"(?<=[A-Za-z0-9])(?=[\u4e00-\u9fff])", " ", text)
    text = re.sub(r"(?<=[A-Za-z0-9+#])(?=[\u4e00-\u9fff])", " ", text)
    return re.sub(r"\s+", " ", text).strip(" \t\r\n·-—:：")


def clean_question(text: str) -> str:
    """Render each extracted prompt as one plain-text question ending in ？."""
    text = clean_plain_text(text).replace(",", "，").replace(";", "；").strip(" .。!！?？")
    return f"{text}？" if text else ""

def classify(title: str, fallback: str) -> str:
    value = title.lower()
    scores = {category: sum(value.count(term) for term in terms) for category, terms in CATEGORY_TERMS.items()}
    winner = max(scores, key=scores.get)
    return winner if scores[winner] else fallback

def extract_knowledge_points(text: str) -> list[str]:
    """Attach concrete technical concepts; return empty for generic prompts."""
    value = str(text or "").lower()
    points = []
    for label, pattern in KNOWLEDGE_POINT_RULES:
        if re.search(pattern, value, re.IGNORECASE) and label not in points:
            points.append(label)
    return points[:6]

def title_from_item(item: dict) -> str:
    card = item.get("note_card") or {}
    # This is attribution metadata only; candidate question text is extracted separately.
    title = card.get("display_title") or card.get("title") or item.get("display_title") or item.get("title") or ""
    return re.sub(r"\s+", " ", str(title)).strip()[:180]

def question_candidates(text: str, limit: int = 4) -> list[str]:
    """Extract short question-like lines; never keep or publish the full note body."""
    candidates, seen = [], set()
    for line in re.split(r"[\r\n]+", text or ""):
        line = re.sub(r"<[^>]+>", " ", line)
        line = re.sub(r"^\s*(?:[-*•◼■▪□●○◆▶▸]+|\d{1,3}[.)、])\s*", "", line)
        for part in re.split(r"(?<=[。！？?!])\s*", line):
            part = clean_plain_text(part)
            if not 4 <= len(part) <= 140:
                continue
            explicit_question = re.search(
                r"(什么|为什么|为何|如何|怎么|怎样|是否|能否|可否|有哪些|有什么|区别|介绍|谈谈|比较|解释|说明|简述|讲讲|说说)",
                part,
            )
            topic_prompt = re.search(r"(原理|流程|作用)", part) and not re.search(r"[:：]", part)
            looks_like_question = "?" in part or "？" in part or bool(explicit_question or topic_prompt)
            if not looks_like_question or any(re.search(pattern, part, re.IGNORECASE) for pattern in LOW_SIGNAL_PATTERNS):
                continue
            part = clean_question(part)
            key = normalize(part)
            if key not in seen:
                seen.add(key); candidates.append(part)
            if len(candidates) >= limit:
                return candidates
    return candidates


def source_url(item: dict) -> str:
    note_id = str(item.get("id") or item.get("note_id") or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9_-]{6,100}", note_id): return ""
    token = str(item.get("xsec_token") or "").strip()
    if token and len(token) <= 500:
        query = urllib.parse.urlencode({"xsec_token": token})
        return f"https://www.xiaohongshu.com/explore/{note_id}?{query}"
    return f"https://www.xiaohongshu.com/explore/{note_id}"

def load_existing() -> dict:
    if not DATA_PATH.exists(): return {"schema_version": 1, "questions": []}
    return json.loads(DATA_PATH.read_text(encoding="utf-8"))

def get_auth(login: bool):
    try:
        import keyring
        from xhs_utils.xhs_pc.auth import XHSPcAuth
    except ImportError as exc:
        raise RuntimeError("依赖未安装；请按 interview-questions/README.md 安装采集器") from exc
    if login:
        auth = XHSPcAuth.from_qrcode_login(show_in_terminal=True)
        session = {
            "cookies": auth.cookies, "b1": auth.b1, "dsl": auth.dsl, "user_id": auth.user_id,
            "host_cookies": auth.host_cookies_snapshot(), "local_storage": auth.local_storage,
            "session_storage": auth.session_storage, "web_build": auth.web_build,
            "web_profile_fields": auth.web_profile_fields,
        }
        keyring.set_password(SERVICE, ACCOUNT, json.dumps(session, ensure_ascii=False))
        print("登录成功：会话已保存到 macOS Keychain，不会写入仓库。")
        return auth
    secret = keyring.get_password(SERVICE, ACCOUNT)
    if not secret:
        raise RuntimeError("未找到本机小红书会话。先运行：python scripts/xhs-collector/collect_questions.py --login")
    try:
        session = json.loads(secret)
    except json.JSONDecodeError:
        # Migrate an older cookie-only keychain entry if one exists.
        session = {"cookies": secret}
    return XHSPcAuth.from_cookie(session.pop("cookies"), **session)

def collect(auth) -> list[dict]:
    from apis.xhs_pc_apis import XHS_Apis
    api = XHS_Apis(auth)
    results: dict[str, dict] = {}
    seen_notes = set()
    for category, queries in SEARCHES.items():
        for query in queries:
            ok, message, items = api.search_some_note(query, 5, sort_type_choice=0, note_type=0)
            if not ok:
                raise RuntimeError(f"搜索失败（{query}）：{message}。若出现验证或风控，请停止采集并按平台要求处理，不要尝试绕过。")
            # Detail fetches are capped to three results per query and only used
            # locally to distill question-like lines; note text is never saved.
            inspected = 0
            for item in items:
                if item.get("model_type") not in (None, "note"): continue
                note_id = str(item.get("id") or item.get("note_id") or "")
                if not note_id or note_id in seen_notes: continue
                url = source_url(item)
                source_title = title_from_item(item)
                if not url or len(source_title) < 3: continue
                seen_notes.add(note_id)
                ok, message, detail = api.get_note_info(url)
                if not ok:
                    raise RuntimeError(f"读取公开笔记失败（{source_title}）：{message}。如遇验证/限流请停止，不要绕过。")
                try:
                    note = detail["data"]["items"][0]
                    card = note.get("note_card") or {}
                    description = str(card.get("desc") or card.get("description") or "")
                except (KeyError, IndexError, TypeError):
                    description = ""
                for question in question_candidates(description):
                    key = normalize(question)
                    if not key: continue
                    knowledge_points = extract_knowledge_points(question)
                    if not knowledge_points:
                        continue
                    results.setdefault(key, {
                        "id": note_id, "question": question,
                        "category": classify(question + " " + source_title, category),
                        "knowledge_points": knowledge_points,
                        "source_title": clean_plain_text(source_title), "source_url": url,
                        "first_seen": dt.date.today().isoformat(),
                    })
                inspected += 1
                time.sleep(2.0)
                if inspected >= 3: break
            time.sleep(2.0)
    return list(results.values())

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--login", action="store_true", help="二维码登录并保存会话到 Keychain；随后采集一次")
    args = parser.parse_args()
    try:
        fresh, old = collect(get_auth(args.login)), load_existing()
        for row in old.get("questions", []):
            row["question"] = clean_question(row.get("question", ""))
            row["source_title"] = clean_plain_text(row.get("source_title", ""))
            row["knowledge_points"] = row.get("knowledge_points") or extract_knowledge_points(row["question"])
        old_by_key = {normalize(row.get("question", "")): row for row in old.get("questions", [])}
        merged, today = {}, dt.date.today().isoformat()
        for row in fresh:
            prior = old_by_key.get(normalize(row["question"]))
            if prior:
                row["first_seen"] = prior.get("first_seen", today)
                row["knowledge_points"] = prior.get("knowledge_points") or row.get("knowledge_points", [])
            merged[normalize(row["question"])] = row
        for key, row in old_by_key.items(): merged.setdefault(key, row)
        payload = {"schema_version": 1, "updated_at": today,
            "source": "short question prompts distilled locally from public notes; source links retained",
            "questions": sorted(merged.values(), key=lambda x: (x.get("category", ""), x.get("question", "").lower()))}
        DATA_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"采集完成：本次发现 {len(fresh)} 条，索引总数 {len(payload['questions'])} 条。")
        return 0
    except Exception as exc:
        print(f"采集未完成：{exc}", file=sys.stderr)
        return 1

if __name__ == "__main__": raise SystemExit(main())
