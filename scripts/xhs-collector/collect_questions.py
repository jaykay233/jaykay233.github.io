#!/usr/bin/env python3
"""Locally collect public XHS search-result titles into the static question index.

Authentication is held in macOS Keychain via Python keyring. This intentionally
reads only search-result titles and source identifiers; it does not open notes,
collect comments/profiles/media, or attempt to bypass platform challenges.
"""
from __future__ import annotations
import argparse, datetime as dt, json, os, re, sys, time, unicodedata
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
CATEGORY_TERMS = {
    "operator": ("算子", "cuda", "triton", "kernel", "内核", "算子优化", "flashattention", "flash attention"),
    "compiler": ("编译器", "编译", "compiler", "torch.compile", "inductor", "算子融合", "图优化"),
    "communication": ("通信", "nccl", "rdma", "allreduce", "all-reduce", "all_gather", "all-gather", "集合通信", "p2p"),
    "framework": ("框架", "vllm", "sglang", "megatron", "deepspeed", "训练框架", "推理框架", "分布式训练"),
}

def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).lower()
    return re.sub(r"[\W_]+", "", text, flags=re.UNICODE)

def classify(title: str, fallback: str) -> str:
    value = title.lower()
    scores = {category: sum(value.count(term) for term in terms) for category, terms in CATEGORY_TERMS.items()}
    winner = max(scores, key=scores.get)
    return winner if scores[winner] else fallback

def title_from_item(item: dict) -> str:
    card = item.get("note_card") or {}
    # Use only title-like fields from search results; never publish note body text.
    title = card.get("display_title") or card.get("title") or item.get("display_title") or item.get("title") or ""
    return re.sub(r"\s+", " ", str(title)).strip()[:180]

def source_url(item: dict) -> str:
    note_id = str(item.get("id") or item.get("note_id") or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9_-]{6,100}", note_id): return ""
    token = str(item.get("xsec_token") or "").strip()
    if token and re.fullmatch(r"[A-Za-z0-9._~-]{1,500}", token):
        return f"https://www.xiaohongshu.com/explore/{note_id}?xsec_token={token}"
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
    for category, queries in SEARCHES.items():
        for query in queries:
            ok, message, items = api.search_some_note(query, 5, sort_type_choice=0, note_type=0)
            if not ok:
                raise RuntimeError(f"搜索失败（{query}）：{message}。若出现验证或风控，请停止采集并按平台要求处理，不要尝试绕过。")
            for item in items:
                if item.get("model_type") not in (None, "note"): continue
                title, url = title_from_item(item), source_url(item)
                if len(title) < 5 or not url: continue
                key = normalize(title)
                if not key: continue
                results.setdefault(key, {"id": str(item.get("id") or item.get("note_id")), "title": title,
                    "category": classify(title, category), "tags": [], "source_url": url,
                    "first_seen": dt.date.today().isoformat(), "query": query})
            time.sleep(2.0)  # low frequency; stop rather than work around blocks
    return list(results.values())

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--login", action="store_true", help="二维码登录并保存会话到 Keychain；随后采集一次")
    args = parser.parse_args()
    try:
        fresh, old = collect(get_auth(args.login)), load_existing()
        old_by_key = {normalize(row.get("title", "")): row for row in old.get("questions", [])}
        merged, today = {}, dt.date.today().isoformat()
        for row in fresh:
            prior = old_by_key.get(normalize(row["title"]))
            if prior: row["first_seen"] = prior.get("first_seen", today)
            merged[normalize(row["title"])] = row
        for key, row in old_by_key.items(): merged.setdefault(key, row)
        payload = {"schema_version": 1, "updated_at": today,
            "source": "xiaohongshu public search result titles; locally collected",
            "questions": sorted(merged.values(), key=lambda x: (x.get("category", ""), x.get("title", "").lower()))}
        DATA_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"采集完成：本次发现 {len(fresh)} 条，索引总数 {len(payload['questions'])} 条。")
        return 0
    except Exception as exc:
        print(f"采集未完成：{exc}", file=sys.stderr)
        return 1

if __name__ == "__main__": raise SystemExit(main())
