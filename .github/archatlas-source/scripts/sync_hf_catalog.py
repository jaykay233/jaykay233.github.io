#!/usr/bin/env python3
"""Index every 2025+ public text-generation repo in configured publisher namespaces.

The owner allowlist defines the first-party scope. This paginates all matching
repositories for those owners; it does not claim to enumerate every Hub user or
community fine-tune. Discovery metadata is not an architecture verification.
"""
from __future__ import annotations

import concurrent.futures
import datetime as dt
import json
import re
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
SNAPSHOT_DATE = dt.date.today().isoformat()
SINCE = "2025-01-01"
SORTS = ("trendingScore", "downloads", "likes", "createdAt", "lastModified")
LIMIT = 1000
PUBLISHERS = {
    "Qwen", "nvidia", "deepseek-ai", "LiquidAI", "zai-org", "inclusionAI",
    "ibm-granite", "openbmb", "google", "tencent", "microsoft", "allenai",
    "XiaomiMiMo", "moonshotai", "MiniMaxAI", "mistralai", "meta-llama",
    "ByteDance", "baidu", "THUDM", "01-ai", "internlm", "CohereForAI",
    "AI21Labs", "BAAI", "StepFun", "stepfun-ai", "NousResearch",
    "HuggingFaceH4", "bigcode", "bigscience", "SalesforceAI", "yandex",
    "CohereLabs", "KimiTeam", "ByteDance-Seed", "ByteDance-Seed-LLM",
    "AmazonNova", "amazon", "Nexusflow", "arcee-ai", "SakanaAI",
    "naver-hyperclovax", "upstage", "LG-AI-Research", "Huawei",
    "TeleAI", "Shanghai_AI_Laboratory", "antgroup", "StepFun-AI",
    "tiiuae", "AIatMeta", "microsoft-phi", "google-gemma",
    # Additional verified publisher / research-lab namespaces with open text models.
    "openai", "openai-community", "HuggingFaceTB", "LGAI-EXAONE",
    "Salesforce", "EleutherAI", "PrimeIntellect", "poolside", "llm-jp",
    "swiss-ai", "skt", "ibm-research", "GSAI-ML", "apple",
}
EXCLUDE = re.compile(
    r"(?:gguf|ggml|mlx|nvfp|fp8|fp4|int4|int8|awq|gptq|exl\d?|bnb|"
    r"\b\d+bit\b|quant|ablit|uncensored|imatrix|lora|adapter|merged|"
    r"eagle3|draft|tokenizer|embedding|reranker|reward-model|classifier|"
    r"moderation|judge|diffusion|audex|transcriber)", re.I,
)
PARAMS = re.compile(r"(?<![A-Za-z0-9])([0-9]+(?:[._][0-9]+)?\s*[BMT])\b", re.I)


def request_json_response(url: str, attempts: int = 8):
    for attempt in range(attempts):
        try:
            req = Request(url, headers={"User-Agent": "ArchAtlas-HF-catalog/1.0"})
            with urlopen(req, timeout=60) as response:
                return json.loads(response.read()), response.headers.get("Link", "")
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            if attempt + 1 == attempts:
                raise
            delay = min(2 ** attempt, 20)
            print(f"WARN: API retry {attempt + 1}/{attempts} after {exc}; sleeping {delay}s", file=sys.stderr, flush=True)
            time.sleep(delay)
    raise RuntimeError("unreachable")


def request_json(url: str, attempts: int = 8):
    return request_json_response(url, attempts)[0]


def next_link(link_header: str):
    match = re.search(r'<([^>]+)>\s*;\s*rel="next"', link_header)
    return match.group(1) if match else None


def retrieve_rankings():
    """Keep rank signals for the most visible repositories across five sorts."""
    union: dict[str, dict] = {}
    for sort in SORTS:
        params = urlencode({"pipeline_tag": "text-generation", "sort": sort,
                            "direction": "-1", "limit": LIMIT, "full": "true"})
        rows = request_json(f"https://huggingface.co/api/models?{params}")
        for rank, row in enumerate(rows, start=1):
            entry = union.setdefault(row["id"], {"id": row["id"], "rankings": {}})
            entry["rankings"][sort] = rank
            for key in ("createdAt", "lastModified", "downloads", "likes", "trendingScore", "pipeline_tag", "tags"):
                if key in row:
                    entry[key] = row[key]
    return union


def retrieve_publisher_repositories(publisher: str):
    """Paginate this publisher's whole public text-generation catalog back to SINCE."""
    params = urlencode({"author": publisher, "pipeline_tag": "text-generation",
                        "sort": "createdAt", "direction": "-1", "limit": LIMIT,
                        "full": "true"})
    url = f"https://huggingface.co/api/models?{params}"
    records = {}
    scanned = 0
    pages = 0
    while url:
        rows, link_header = request_json_response(url)
        pages += 1
        scanned += len(rows)
        for row in rows:
            created = (row.get("createdAt") or "")[:10]
            if created and created < SINCE:
                continue
            repo_id = row.get("id", "")
            if "/" not in repo_id or EXCLUDE.search(repo_id.split("/", 1)[1]):
                continue
            records[repo_id] = row
        # The API is ordered newest-first; after an all-old page, no later page can qualify.
        if rows and all((row.get("createdAt") or "")[:10] < SINCE for row in rows):
            break
        url = next_link(link_header)
    return publisher, records, scanned, pages

def extract_candidate(record: dict, hub: dict):
    repo_id = record["id"]
    owner, name = repo_id.split("/", 1)
    created = (hub.get("createdAt") or record.get("createdAt") or "")[:10]
    if created < SINCE:
        return None
    if owner.casefold() not in {p.casefold() for p in PUBLISHERS}:
        return None
    if EXCLUDE.search(name):
        return None
    card = hub.get("cardData") or {}
    config = hub.get("config") or {}
    safetensors = hub.get("safetensors") or {}
    total = safetensors.get("total")
    if isinstance(total, (int, float)) and total > 0:
        # safetensors.total is tensor count, not parameter count; do not expose as parameters.
        total = None
    match = PARAMS.search(name.replace("_", " "))
    param_label = match.group(1).replace(" ", "") if match else "未标注"
    model_type = config.get("model_type")
    architectures = config.get("architectures") or []
    layers = next((config.get(k) for k in ("num_hidden_layers", "n_layer", "num_layers") if config.get(k)), None)
    context = next((config.get(k) for k in ("max_position_embeddings", "max_sequence_length", "model_max_length") if config.get(k)), None)
    experts = next((config.get(k) for k in ("n_routed_experts", "num_experts", "num_local_experts") if config.get(k)), None)
    top_k = next((config.get(k) for k in ("num_experts_per_tok", "num_experts_per_token") if config.get(k)), None)
    model_id = "hf-" + re.sub(r"[^a-z0-9]+", "-", repo_id.casefold()).strip("-")
    tags = hub.get("tags") or []
    license_from_tags = next((tag.split(":", 1)[1] for tag in tags if tag.startswith("license:")), None)
    return {
        "id": model_id,
        "hub_id": repo_id,
        "name": name,
        "organization": owner,
        "family": name,
        "parameters": param_label,
        "release": created[:7] if created else "未知",
        "hub_created": created,
        "hub_updated": (hub.get("lastModified") or record.get("lastModified") or "")[:10],
        "downloads_snapshot": hub.get("downloads", record.get("downloads", 0)),
        "likes_snapshot": hub.get("likes", record.get("likes", 0)),
        "rankings": record.get("rankings", {}),
        "added_in_snapshot": True,
        "architecture_type": "待拆解" + (f" · {model_type}" if model_type else ""),
        "architecture_status": "pending",
        "license": card.get("license") or license_from_tags or "未声明",
        "summary": "从 Hugging Face 第一方发布者命名空间完整分页发现；目前只收录仓库元数据，架构模块尚待逐条核验。",
        "modules": [],
        "architecture": None,
        "config_summary": {
            "model_type": model_type,
            "architectures": architectures,
            "num_hidden_layers": layers,
            "context_length": context,
            "num_experts": experts,
            "top_k_experts": top_k,
        },
        "sources": [
            {"label": "Hugging Face 官方模型仓库", "url": f"https://huggingface.co/{repo_id}"},
            {"label": "配置文件", "url": f"https://huggingface.co/{repo_id}/blob/main/config.json"},
        ],
        "evidence": f"仓库创建时间 {created or '未提供'}；仓库元数据来自 Hugging Face Hub API。以上是发现记录，不代表已核实模型架构。",
        "confidence": "discovered-only",
    }


def main():
    print("Fetching ranking signals and paginating first-party publisher catalogs…", flush=True)
    ranked = retrieve_rankings()
    publishers = sorted({owner for owner in PUBLISHERS}, key=str.casefold)
    repository_rows = {}
    scanned_total = pages_total = 0
    failed_publishers = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        futures = {pool.submit(retrieve_publisher_repositories, publisher): publisher for publisher in publishers}
        for i, future in enumerate(concurrent.futures.as_completed(futures), start=1):
            publisher = futures[future]
            try:
                owner, records, scanned, pages = future.result()
                repository_rows.update(records)
                scanned_total += scanned
                pages_total += pages
                print(f"  {owner}: {len(records)} matching repos from {scanned} scanned ({pages} pages) [{i}/{len(futures)}]", flush=True)
            except Exception as exc:
                failed_publishers.append(publisher)
                print(f"ERROR: publisher crawl failed for {publisher}: {exc}", file=sys.stderr, flush=True)

    # Do not silently replace a complete snapshot with a partial crawl.
    if failed_publishers:
        raise RuntimeError("Incomplete publisher crawl; no files written. Failed: " + ", ".join(failed_publishers))

    # Attach sampled ranking positions where available; all other matching repos stay in the catalog.
    for repo_id, row in repository_rows.items():
        ranking = ranked.get(repo_id)
        row["rankings"] = ranking.get("rankings", {}) if ranking else {}
    ids = sorted(repository_rows, key=lambda repo_id: (
        repository_rows[repo_id].get("createdAt", ""), repo_id.casefold()), reverse=True)
    print(f"Crawled {scanned_total} public first-party repos; {len(ids)} eligible 2025+ repos after exclusions.", flush=True)

    # Preserve previously fetched config summaries without re-hitting one detail endpoint
    # per model. The paginated list response is sufficient for a transparent discovery record.
    previous = json.loads((DATA / "discovered_models.json").read_text(encoding="utf-8")) if (DATA / "discovered_models.json").exists() else []
    previous_by_hub = {m.get("hub_id", "").casefold(): m for m in previous if m.get("hub_id")}
    card_cache_path = DATA / "model_card_evidence_cache.json"
    card_cache = json.loads(card_cache_path.read_text(encoding="utf-8")) if card_cache_path.exists() else {}

    manual = json.loads((DATA / "models.json").read_text(encoding="utf-8"))
    manual_hubs = {m.get("hub_id", "").casefold() for m in manual if m.get("hub_id")}
    # Older authored records predate hub_id; match their source URLs where possible.
    manual_hubs.update(
        "/".join(source["url"].split("huggingface.co/", 1)[1].split("?", 1)[0].strip("/").split("/")[:2]).casefold()
        for m in manual for source in m.get("sources", [])
        if "huggingface.co/" in source.get("url", "")
    )
    candidates = []
    for repo_id in ids:
        if repo_id.casefold() in manual_hubs:
            continue
        candidate = extract_candidate(repository_rows[repo_id], repository_rows[repo_id])
        if candidate:
            old_record = previous_by_hub.get(repo_id.casefold())
            if old_record:
                # Keep already retrieved config/model-class metadata for existing entries.
                for key in ("config_summary", "license", "confidence", "model_card_evidence"):
                    if key in old_record:
                        candidate[key] = old_record[key]
                candidate["architecture_type"] = old_record.get("architecture_type", candidate["architecture_type"])
                candidate["summary"] = old_record.get("summary", candidate["summary"])
                candidate["evidence"] = old_record.get("evidence", candidate["evidence"])
            cached_card = card_cache.get(candidate["id"])
            if cached_card:
                candidate["model_card_evidence"] = cached_card
            candidates.append(candidate)
    candidates.sort(key=lambda x: (x.get("hub_created", ""), x.get("downloads_snapshot", 0)), reverse=True)
    ids_seen = set()
    unique = []
    for candidate in candidates:
        hub_key = candidate["hub_id"].casefold()
        if candidate["id"] in ids_seen or hub_key in ids_seen:
            continue
        ids_seen.add(candidate["id"])
        ids_seen.add(hub_key)
        unique.append(candidate)

    (DATA / "discovered_models.json").write_text(json.dumps(unique, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    metadata = {
        "snapshot_date": SNAPSHOT_DATE,
        "snapshot_source": "Hugging Face Hub API, paginated by every configured first-party publisher namespace; trending/download/like rank signals sampled separately",
        "since": SINCE,
        "scope": "All public text-generation repositories returned by the Hugging Face Hub API for the configured official publisher and research-lab namespaces, created on/after the start date, after explicit quantization/conversion/derivative name exclusions. This is not every Hub namespace, and each candidate still requires model/architecture review.",
        "publisher_count": len(publishers),
        "publishers": publishers,
        "scanned_public_repositories": scanned_total,
        "pages_fetched": pages_total,
        "eligible_repositories_before_manual_dedup": len(ids),
        "pending_architecture_models": len(unique),
        "config_detail_policy": "Preserves config summaries already collected; does not issue one detail request per new repo to avoid rate limits. New discovery records may have unknown config fields until individually reviewed.",
        "selection_note": "Repository coverage is exhaustive within the configured publisher namespaces and API filters at snapshot time, not all Hugging Face users, publishers, or community fine-tunes. The allowlist is curated and can be expanded. Some returned text-generation repos may be checkpoints, research artifacts, or non-base variants; candidates are not confirmed architecture records until reviewed.",
    }
    (DATA / "discovery_metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Saved {len(unique)} pending models to data/discovered_models.json")


if __name__ == "__main__":
    main()
