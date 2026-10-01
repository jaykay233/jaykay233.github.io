#!/usr/bin/env python3
"""Fetch model config.json files and add conservative, traceable architecture findings.

The script deliberately does not promote a candidate to a manually verified model.
Only structural properties directly exposed by config.json (or an explicit model
class/config identifier) are emitted. Model-card/paper/code review remains needed
for custom block internals not encoded in the config.
"""
from __future__ import annotations

import concurrent.futures
import json
import random
import re
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
CATALOG = DATA / "discovered_models.json"
CACHE = DATA / "config_evidence_cache.json"
WORKERS = 4

FIELDS = (
    "model_type", "architectures", "num_hidden_layers", "n_layer", "num_layers",
    "max_position_embeddings", "max_sequence_length", "model_max_length",
    "hidden_size", "intermediate_size", "num_attention_heads", "n_head",
    "num_key_value_heads", "num_kv_heads", "num_query_groups", "head_dim",
    "hidden_act", "activation_function", "rms_norm_eps", "layer_norm_eps",
    "rope_theta", "rope_scaling", "partial_rotary_factor", "sliding_window",
    "attention_types", "layer_types", "hybrid_override_pattern",
    "num_experts", "num_local_experts", "n_routed_experts", "moe_intermediate_size",
    "num_experts_per_tok", "num_experts_per_token", "experts_per_token",
    "kv_lora_rank", "q_lora_rank", "qk_nope_head_dim", "qk_rope_head_dim",
    "num_nextn_predict_layers", "mtp_depth", "use_gated_attention",
    "gated_attention", "use_sliding_window", "tie_word_embeddings", "auto_map",
    "n_streams", "mhc_num_streams", "mhc_mix_coeff", "hyper_connection_layers",
)


def nested_configs(config: dict) -> list[dict]:
    values = [config]
    for key in ("text_config", "language_config", "llm_config", "decoder", "model_config"):
        value = config.get(key)
        if isinstance(value, dict):
            values.insert(0, value)
    return values


def config_value(config: dict, names):
    for current in nested_configs(config):
        for name in names:
            value = current.get(name)
            if value is not None:
                return value
    return None


def pick_summary(config: dict):
    summary = {}
    for field in FIELDS:
        value = config_value(config, (field,))
        if value is not None:
            # Avoid copying large auto_map/path structures wholesale.
            if field == "auto_map" and isinstance(value, dict):
                value = {k: v for k, v in value.items() if "CausalLM" in k or "Model" in k}
            summary[field] = value
    # Preserve a few often-useful, implementation-specific config declarations.
    for key, value in config.items():
        if re.search(r"mhc|hyper.?connection|linear.?attn|deltanet|mamba|kda|sparse.?attn|moe|expert|layer.?type", key, re.I):
            if isinstance(value, (str, int, float, bool, list, dict)) and len(json.dumps(value, ensure_ascii=False)) < 4000:
                summary.setdefault(key, value)
    return summary


def fetch_config(repo_id: str):
    url = f"https://huggingface.co/{repo_id}/resolve/main/config.json"
    for attempt in range(7):
        try:
            req = Request(url, headers={"User-Agent": "ArchAtlas-architecture-audit/1.0"})
            with urlopen(req, timeout=35) as response:
                config = json.loads(response.read())
            if not isinstance(config, dict):
                return {"status": "invalid-json", "url": url}
            return {"status": "ok", "url": url, "config": pick_summary(config)}
        except HTTPError as exc:
            if exc.code == 404:
                return {"status": "not-found", "url": url}
            if exc.code not in (408, 425, 429, 500, 502, 503, 504):
                return {"status": f"http-{exc.code}", "url": url}
            retry_after = exc.headers.get("Retry-After") if exc.headers else None
        except (URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
            retry_after = None
            if attempt == 6:
                return {"status": "error", "url": url, "error": str(exc)[:200]}
        delay = float(retry_after) if retry_after and retry_after.isdigit() else min(2 ** attempt, 30)
        time.sleep(delay + random.random() * 0.5)
    return {"status": "error", "url": url, "error": "retry limit"}


def int_value(config: dict, *keys):
    value = config_value(config, keys)
    return value if isinstance(value, (int, float)) else None


def add_finding(findings, module_id, statement, basis, confidence="direct-config"):
    if not any(item["module_id"] == module_id for item in findings):
        findings.append({
            "module_id": module_id,
            "statement": statement,
            "basis": basis,
            "confidence": confidence,
        })


def analyze_config(config: dict):
    findings = []
    model_type = str(config_value(config, ("model_type",)) or "").casefold()
    architectures = config_value(config, ("architectures",)) or []
    if isinstance(architectures, str):
        architectures = [architectures]
    arch_names = " ".join(map(str, architectures)).casefold()
    identity = f"{model_type} {arch_names}"
    num_heads = int_value(config, "num_attention_heads", "n_head")
    kv_heads = int_value(config, "num_key_value_heads", "num_kv_heads", "num_query_groups")
    experts = int_value(config, "n_routed_experts", "num_local_experts", "num_experts")
    top_k = int_value(config, "num_experts_per_tok", "num_experts_per_token", "experts_per_token")
    layers = int_value(config, "num_hidden_layers", "n_layer", "num_layers")
    model_type_direct = f"model_type={model_type}" if model_type else None
    arch_direct = f"architectures={', '.join(map(str, architectures))}" if architectures else None

    if "causallm" in arch_names or "forcausallm" in arch_names or model_type in {
        "llama", "qwen2", "qwen3", "qwen3_moe", "mistral", "mixtral", "gemma",
        "gemma2", "gemma3", "phi3", "phi4", "granite", "granitemoe", "olmo",
        "olmo2", "olmo3", "deepseek_v2", "deepseek_v3", "deepseek_v32", "deepseek_v4",
        "glm4", "glm4_moe", "glm_moe_dsa", "minicpm", "minicpm3", "minicpm4",
        "minicpm5", "internlm2", "internlm3", "baichuan", "command-r", "cohere",
        "falcon", "jais", "mpt", "stablelm", "xverse", "yi", "llama4",
    }:
        add_finding(findings, "decoder-only", "配置声明为因果语言模型/decoder-only 主干。", model_type_direct or arch_direct or "causal LM class")

    mla_marked = bool(config_value(config, ("kv_lora_rank", "q_lora_rank", "qk_nope_head_dim", "qk_rope_head_dim"))) or any(x in model_type for x in ("deepseek_v2", "deepseek_v3", "deepseek_v32", "deepseek_v4", "kimi_k2", "bailing_hybrid"))
    if num_heads and kv_heads and 0 < kv_heads < num_heads and not mla_marked:
        add_finding(findings, "gqa", f"num_attention_heads={num_heads}、num_key_value_heads={kv_heads}，KV 头少于 Query 头。", f"num_attention_heads={num_heads}; num_key_value_heads={kv_heads}")

    rope_theta = config_value(config, ("rope_theta", "rope_scaling", "partial_rotary_factor"))
    if rope_theta is not None or any(x in model_type for x in ("llama", "qwen", "mistral", "deepseek", "glm", "olmo", "granite", "phi3")):
        basis = "rope_theta/rope_scaling/partial_rotary_factor declared in config" if rope_theta is not None else (model_type_direct or arch_direct)
        add_finding(findings, "rope", "配置字段或已识别模型类型表明使用 RoPE/旋转位置编码。", str(basis), "direct-config" if rope_theta is not None else "family-config-inference")

    norm_eps = config_value(config, ("rms_norm_eps",))
    if norm_eps is not None or any(x in model_type for x in ("llama", "qwen", "mistral", "deepseek", "gemma", "olmo", "granite", "phi3", "glm")):
        basis = f"rms_norm_eps={norm_eps}" if norm_eps is not None else (model_type_direct or arch_direct)
        add_finding(findings, "rmsnorm", "配置包含 RMSNorm 参数或对应模型类型。", str(basis), "direct-config" if norm_eps is not None else "family-config-inference")

    if experts and experts > 1 and top_k and top_k > 0:
        add_finding(findings, "moe-ffn", f"配置声明 {experts} 个专家、每 token 选择 top-{top_k}。", f"expert_count={experts}; experts_per_token={top_k}")
    elif any(x in model_type for x in ("moe", "mixtral", "deepseek_v2", "deepseek_v3", "deepseek_v32", "deepseek_v4", "kimi_k2", "glm_moe", "bailing_moe")):
        add_finding(findings, "moe-ffn", "模型类型标识 MoE 专家结构；专家数量与路由配置仍需查验。", model_type_direct or arch_direct, "family-config-inference")

    sliding = config_value(config, ("sliding_window",))
    if isinstance(sliding, (int, float)) and sliding > 0:
        add_finding(findings, "sliding-window", f"配置声明 sliding_window={sliding}。", f"sliding_window={sliding}")

    kv_rank = int_value(config, "kv_lora_rank")
    q_rank = int_value(config, "q_lora_rank")
    if kv_rank or "mla" in model_type or (q_rank and ("deepseek" in model_type or "bailing" in model_type)):
        add_finding(findings, "mla", "配置包含 MLA latent-rank 字段或 model_type 标记。", f"kv_lora_rank={kv_rank}; q_lora_rank={q_rank}; {model_type_direct}", "direct-config" if kv_rank or q_rank else "family-config-inference")

    nextn = int_value(config, "num_nextn_predict_layers", "mtp_depth")
    if nextn and nextn > 0:
        add_finding(findings, "mtp", f"配置声明 {nextn} 个 next-token prediction 层。", f"num_nextn_predict_layers/mtp_depth={nextn}")

    layer_types = config_value(config, ("layer_types", "attention_types", "hybrid_override_pattern"))
    if isinstance(layer_types, (list, str)) and layer_types:
        unique = set(layer_types) if isinstance(layer_types, list) else set(re.findall(r"[A-Za-z][A-Za-z0-9_-]*", layer_types))
        if len(unique) > 1 or any(x in identity for x in ("hybrid", "nemotron_h", "qwen3_next", "lfm2", "mamba")):
            preview = list(layer_types)[:12] if isinstance(layer_types, list) else str(layer_types)[:120]
            add_finding(findings, "hybrid-attention", "配置声明混合层类型/层布局。", f"layer layout={preview}")

    explicit_map = (
        (("deltanet", "gateddeltanet", "qwen3_next", "qwen3_5", "hybrid_qwen3"), "gated-deltanet", "config/model class identifies a Gated DeltaNet / linear-attention family"),
        (("kimi_linear", "kda"), "kda", "config/model class identifies Kimi Delta Attention"),
        (("mamba2", "jamba"), "mamba2", "model_type identifies a Mamba-2 sequence-mixing family"),
        (("lfm2", "gatedconv"), "gated-conv", "config/model class identifies LFM2 gated-convolution family"),
        (("glm_moe_dsa", "deepseek_v32"), "deepseek-sparse-attention", "model_type identifies a DSA family implementation"),
    )
    for tokens, module_id, basis in explicit_map:
        if any(token in identity for token in tokens):
            add_finding(findings, module_id, basis + "（需以模型卡/实现确认具体版本细节）。", model_type_direct or arch_direct, "family-config-inference")

    hybrid_families = ("nemotron_h", "bailing_hybrid", "granitemoehybrid", "qwen3_next", "qwen3_5", "hybrid_qwen3", "lfm2", "falcon_h1", "jamba", "olmo_hybrid", "minicpm_sala")
    if any(token in identity for token in hybrid_families):
        add_finding(findings, "hybrid-attention", "模型类型属于混合序列混合/注意力家族；实际层间布局须以配置层表和模型卡为准。", model_type_direct or arch_direct, "family-config-inference")

    gated_attn = config_value(config, ("use_gated_attention", "gated_attention"))
    if gated_attn is True:
        add_finding(findings, "gated-attention", "配置显式启用 gated attention。", "use_gated_attention/gated_attention=true")

    return findings, {"layers": layers, "num_attention_heads": num_heads, "num_key_value_heads": kv_heads,
                      "num_experts": experts, "top_k_experts": top_k}


def main():
    models = json.loads(CATALOG.read_text(encoding="utf-8"))
    cache = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}
    todo = [m for m in models if m.get("hub_id") and m["hub_id"] not in cache]
    print(f"Fetching config.json for {len(todo)} uncached models ({len(cache)} cached)…", flush=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=WORKERS) as pool:
        futures = {pool.submit(fetch_config, m["hub_id"]): m for m in todo}
        for i, future in enumerate(concurrent.futures.as_completed(futures), 1):
            model = futures[future]
            cache[model["hub_id"]] = future.result()
            if i % 25 == 0 or i == len(todo):
                CACHE.write_text(json.dumps(cache, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
                print(f"  fetched {i}/{len(todo)} configs", flush=True)
    CACHE.write_text(json.dumps(cache, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")

    statuses = {}
    module_findings = {}
    confidence_findings = {}
    analyzed = tagged = 0
    for model in models:
        result = cache.get(model.get("hub_id", ""), {"status": "not-fetched"})
        statuses[result.get("status", "unknown")] = statuses.get(result.get("status", "unknown"), 0) + 1
        if result.get("status") != "ok":
            model["config_review"] = {"status": result.get("status"), "source": result.get("url")}
            continue
        config = result.get("config", {})
        findings, stats = analyze_config(config)
        model_type = config.get("model_type")
        architectures = config.get("architectures") or []
        model["config_summary"] = {
            **model.get("config_summary", {}),
            "model_type": model_type,
            "architectures": architectures,
            "num_hidden_layers": stats["layers"],
            "context_length": config_value(config, ("max_position_embeddings", "max_sequence_length", "model_max_length")),
            "num_attention_heads": stats["num_attention_heads"],
            "num_key_value_heads": stats["num_key_value_heads"],
            "num_experts": stats["num_experts"],
            "top_k_experts": stats["top_k_experts"],
            "hidden_act": config_value(config, ("hidden_act", "activation_function")),
            "rms_norm_eps": config_value(config, ("rms_norm_eps",)),
            "rope_theta": config_value(config, ("rope_theta",)),
            "sliding_window": config_value(config, ("sliding_window",)),
        }
        model["summary"] = "已读取 Hugging Face config.json，并标注配置可支持的架构线索；自定义模块内部细节仍需依据模型卡、论文与实现代码人工核验。"
        model["evidence"] = f"结构线索来自 {result['url']} 的 config.json；此证据仅覆盖配置显式字段/模型类，不据此推断未声明的模块顺序或实现细节。"
        model["confidence"] = "config-evidence-pending-manual-review"
        model["config_review"] = {
            "status": "reviewed",
            "source": result["url"],
            "evidence_scope": "config.json only; does not establish undocumented custom block internals",
            "findings": findings,
        }
        # Keep the unverified architecture boundary: these are evidence-backed
        # candidate findings, not manually curated final module assignments.
        model["candidate_modules"] = list(dict.fromkeys(item["module_id"] for item in findings))
        if findings:
            model["architecture_type"] = "配置证据待人工复核 · " + (model_type or "Causal LM")
            tagged += 1
            for finding in findings:
                module_findings[finding["module_id"]] = module_findings.get(finding["module_id"], 0) + 1
                confidence_findings[finding["confidence"]] = confidence_findings.get(finding["confidence"], 0) + 1
        analyzed += 1

    CATALOG.write_text(json.dumps(models, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    summary = {"models": len(models), "config_status": statuses, "analyzed": analyzed, "with_structural_findings": tagged, "without_config": len(models)-analyzed, "module_findings": dict(sorted(module_findings.items(), key=lambda item: (-item[1], item[0]))), "finding_confidence": confidence_findings}
    (DATA / "architecture_review_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
