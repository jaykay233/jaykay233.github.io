#!/usr/bin/env python3
"""Dependency-free API server for the architecture graph demo."""
from __future__ import annotations

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"
DATA = ROOT / "data"


def load_json(filename: str):
    with (DATA / filename).open(encoding="utf-8") as f:
        return json.load(f)


def get_curated_models():
    return load_json("models.json")


def get_models():
    """Return curated architecture records plus unverified discovery candidates."""
    curated = get_curated_models()
    discovered = load_json("discovered_models.json")

    def canonical_hub_id(model):
        if model.get("hub_id"):
            return model["hub_id"].strip("/").casefold()
        for source in model.get("sources", []):
            url = source.get("url", "")
            marker = "huggingface.co/"
            if marker in url:
                path = url.split(marker, 1)[1].split("?", 1)[0].strip("/")
                parts = path.split("/")
                if len(parts) >= 2:
                    return "/".join(parts[:2]).casefold()
        return ""

    known_hubs = {hub for model in curated if (hub := canonical_hub_id(model))}
    seen_ids = {model["id"] for model in curated}
    interpretation_path = DATA / "model_card_interpretations.json"
    interpretations = json.loads(interpretation_path.read_text(encoding="utf-8")) if interpretation_path.exists() else {}
    pending = []
    for model in discovered:
        hub = canonical_hub_id(model)
        if model["id"] in seen_ids or (hub and hub in known_hubs):
            continue
        model["architecture_status"] = "pending"
        if model["id"] in interpretations:
            model["model_card_interpretation"] = interpretations[model["id"]]
        ranks = model.get("rankings", {})
        valid_ranks = [rank for rank in ranks.values() if isinstance(rank, (int, float)) and 1 <= rank <= 1000]
        # Average normalized percentile over the HF rankings this repo appeared in.
        # A rank of 1 maps to 100, rank 1000 maps to 0.1; missing lists do not count.
        model["popularity_score"] = round(sum((1001 - rank) / 10 for rank in valid_ranks) / len(valid_ranks), 1) if valid_ranks else 0.0
        model["popularity_signals"] = len(valid_ranks)
        pending.append(model)
        seen_ids.add(model["id"])
        if hub:
            known_hubs.add(hub)
    for model in curated:
        model["popularity_score"] = 0.0
        model["popularity_signals"] = 0
    return curated + pending


def get_catalog():
    catalog = load_json("catalog.json")
    discovery_path = DATA / "discovery_metadata.json"
    if discovery_path.exists():
        discovery = json.loads(discovery_path.read_text(encoding="utf-8"))
        catalog["snapshot_date"] = discovery.get("snapshot_date", catalog["snapshot_date"])
        catalog["discovery_sample"] = discovery
    review_path = DATA / "architecture_review_summary.json"
    if review_path.exists():
        catalog["architecture_review"] = json.loads(review_path.read_text(encoding="utf-8"))
    card_review_path = DATA / "model_card_review_summary.json"
    if card_review_path.exists():
        catalog["model_card_review"] = json.loads(card_review_path.read_text(encoding="utf-8"))
    interpretation_path = DATA / "model_card_interpretations.json"
    if interpretation_path.exists():
        interpretations = json.loads(interpretation_path.read_text(encoding="utf-8"))
        catalog["model_card_interpretation"] = {
            "reviewed_models": len(interpretations),
            "interpretation": "model-card claims have been interpreted; implementation/code verification is still pending",
        }
    return catalog


def get_modules():
    models = get_models()
    modules = load_json("modules.json")
    counts = {}
    for model in models:
        for module_id in model.get("modules", []):
            counts[module_id] = counts.get(module_id, 0) + 1
    for module in modules:
        module["count"] = counts.get(module["id"], 0)
        if module["count"] and module.get("status") == "taxonomy-only":
            module["status"] = "verified"
    return modules


def filter_models(query: str = "", module: str = "", family: str = ""):
    models = get_models()
    q = query.strip().casefold()
    family_q = family.strip().casefold()
    results = []
    for model in models:
        searchable = " ".join([
            model.get("name", ""), model.get("organization", ""),
            model.get("family", ""), model.get("architecture_type", ""),
            model.get("summary", ""), *model.get("modules", []),
            str(model.get("config_summary", {})), *model.get("candidate_modules", []),
        ]).casefold()
        if q and q not in searchable:
            continue
        if module and module not in model.get("modules", []):
            continue
        if family_q and family_q not in model.get("family", "").casefold():
            continue
        results.append(model)
    return results


class Handler(BaseHTTPRequestHandler):
    server_version = "ArchAtlasDemo/0.1"

    def send_json(self, payload, status=200):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def send_file(self, path: Path):
        if not path.is_file():
            self.send_error(404, "Not found")
            return
        suffix = path.suffix.lower()
        content_type = {
            ".html": "text/html; charset=utf-8",
            ".css": "text/css; charset=utf-8",
            ".js": "text/javascript; charset=utf-8",
            ".svg": "image/svg+xml",
        }.get(suffix, "application/octet-stream")
        body = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):  # noqa: N802
        parsed = urlparse(self.path)
        path = unquote(parsed.path)
        params = parse_qs(parsed.query)

        if path == "/api/health":
            return self.send_json({"ok": True, "service": "arch-atlas-demo"})
        if path == "/api/stats":
            models = get_models()
            modules = get_modules()
            catalog = get_catalog()
            return self.send_json({
                "models": len(models),
                "curated_models": sum(1 for m in models if m.get("architecture_status") != "pending"),
                "pending_models": sum(1 for m in models if m.get("architecture_status") == "pending"),
                "modules": len([m for m in modules if m["count"] > 0]),
                "families": len({m["family"] for m in models if m.get("architecture_status") != "pending"}),
                "taxonomy_only": len([m for m in modules if m["status"] == "taxonomy-only"]),
                "new_models": sum(1 for m in get_curated_models() if m.get("added_in_snapshot")),
                "snapshot_date": catalog["snapshot_date"],
                "snapshot_source": catalog["snapshot_source"],
                "scope": catalog["scope"],
                "selection_note": catalog["selection_note"],
                "config_review": catalog.get("architecture_review", {}),
                "model_card_review": catalog.get("model_card_review", {}),
                "model_card_interpretation": catalog.get("model_card_interpretation", {}),
            })
        if path == "/api/models":
            results = filter_models(
                query=params.get("q", [""])[0],
                module=params.get("module", [""])[0],
                family=params.get("family", [""])[0],
            )
            return self.send_json({"total": len(results), "items": results})
        if path.startswith("/api/models/"):
            model_id = path.removeprefix("/api/models/")
            model = next((m for m in get_models() if m["id"] == model_id), None)
            if not model:
                return self.send_json({"error": "model_not_found", "id": model_id}, 404)
            return self.send_json(model)
        if path == "/api/modules":
            modules = get_modules()
            q = params.get("q", [""])[0].strip().casefold()
            category = params.get("category", [""])[0].strip().casefold()
            if q:
                modules = [m for m in modules if q in (m["name"] + " " + m["description"] + " " + m["category"]).casefold()]
            if category:
                modules = [m for m in modules if category in m["category"].casefold()]
            return self.send_json({"total": len(modules), "items": modules})
        if path.startswith("/api/modules/"):
            module_id = path.removeprefix("/api/modules/")
            module = next((m for m in get_modules() if m["id"] == module_id), None)
            if not module:
                return self.send_json({"error": "module_not_found", "id": module_id}, 404)
            related = [m for m in get_models() if module_id in m.get("modules", [])]
            return self.send_json({**module, "models": related})

        if path == "/" or path == "/index.html":
            return self.send_file(FRONTEND / "index.html")
        if path in ("/styles.css", "/app.js"):
            return self.send_file(FRONTEND / path.lstrip("/"))
        self.send_error(404, "Not found")

    def log_message(self, fmt, *args):
        print(f"[{self.log_date_time_string()}] {self.address_string()} {fmt % args}")


def main():
    parser = argparse.ArgumentParser(description="Run the ArchAtlas demo API and frontend")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    httpd = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"ArchAtlas demo running at http://{args.host}:{args.port}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping server…")
    finally:
        httpd.server_close()


if __name__ == "__main__":
    main()
