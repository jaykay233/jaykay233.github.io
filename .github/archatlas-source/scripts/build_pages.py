#!/usr/bin/env python3
"""Build a GitHub Pages-compatible static copy of the ArchAtlas frontend."""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.server import get_catalog, get_curated_models, get_models, get_modules  # noqa: E402


def build(output: Path) -> None:
    output = output.resolve()
    if output == ROOT or output == ROOT / "data":
        raise ValueError(f"Refusing to overwrite project source: {output}")
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)
    for name in ("index.html", "app.js", "styles.css"):
        source = ROOT / "frontend" / name
        shutil.copy2(source, output / name)

    models = get_models()
    modules = get_modules()
    catalog = get_catalog()
    stats = {
        "models": len(models),
        "curated_models": sum(1 for model in models if model.get("architecture_status") != "pending"),
        "pending_models": sum(1 for model in models if model.get("architecture_status") == "pending"),
        "modules": len([module for module in modules if module["count"] > 0]),
        "families": len({model["family"] for model in models if model.get("architecture_status") != "pending"}),
        "taxonomy_only": len([module for module in modules if module["status"] == "taxonomy-only"]),
        "new_models": sum(1 for model in get_curated_models() if model.get("added_in_snapshot")),
        "snapshot_date": catalog["snapshot_date"],
        "snapshot_source": catalog["snapshot_source"],
        "scope": catalog["scope"],
        "selection_note": catalog["selection_note"],
        "config_review": catalog.get("architecture_review", {}),
        "model_card_review": catalog.get("model_card_review", {}),
        "model_card_interpretation": catalog.get("model_card_interpretation", {}),
    }
    api_dir = output / "api"
    api_dir.mkdir()
    payloads = {
        "models.json": {"total": len(models), "items": models},
        "modules.json": {"total": len(modules), "items": modules},
        "stats.json": stats,
    }
    for filename, payload in payloads.items():
        (api_dir / filename).write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"Built static site at {output} ({len(models)} models, {len(modules)} modules)")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "dist-pages")
    args = parser.parse_args()
    build(args.output)


if __name__ == "__main__":
    main()
