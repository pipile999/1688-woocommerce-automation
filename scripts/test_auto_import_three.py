"""Replay exactly the three researched products. No credentials or network.

Uses existing, user-confirmed research and translated artifacts, explicitly
binding them to the current source bytes. This is not an approval generator for
other products and does not rerun image models or claim live HTTP acceptance.
"""
import json
import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.auto_import_runner import Runner
from app.runner_state import read, save, digest, file_hash

SAMPLES = {
    "972743663599": ({"product_type": "cone filling funnel", "material": "plastic"},
                     {"product_type": "漏斗", "material": "塑料"}),
    "991366391366": ({"product_type": "cone storage tube", "material": "plastic", "size": "115 mm"},
                     {"product_type": "收纳管", "material": "塑料", "size": "115MM"}),
    "977271484514": ({"product_type": "herb grinder", "material": "zinc alloy", "size": "50 x 40 mm", "structure": "4-layer"},
                     {"product_type": "研磨器", "material": "锌合金", "size": "50*40mm", "structure": "四层"}),
}


def main():
    # Minimal public facts snapshot, no credentials/full private REST metadata.
    cases = read(ROOT / "data/runner-three-test-cases.json")
    out = ROOT / "output/auto-runner/three-product-test"
    tasks, before = [], {}
    for offer, (facts, evidence) in SAMPLES.items():
        folder = ROOT / "output" / offer
        raw = read(folder / "original-product.json")
        processed = read(folder / "processed-product.json")
        recommendation = cases[offer]
        primary = recommendation["current_primary"]
        words = recommendation["seeds"]
        relevance = {w: {"supported": w in recommendation["supported_keywords"], "specificity": 1.2 if w == recommendation["primary_keyword"] else 1.0,
                         "b2b_supported": False, "source_evidence": evidence} for w in words if w}
        pack = dict(source_fingerprint=digest(raw), processed_fingerprint=digest(processed),
                    facts=facts, fact_evidence=evidence, current_title=recommendation["current_title"],
                    current_primary=primary, seed_keywords=words,
                    keyword_relevance=relevance, title_options={recommendation["primary_keyword"]:
                        {"title": recommendation["recommended_title"], "source_evidence": evidence}},
                    category_terms=[processed["category"]["name"]], category_snapshot=[dict(processed["category"], parent=0)],
                    approval_source="Existing three-product research, source facts and reviewed translations; local test only")
        path = out / "evidence" / (offer + ".json")
        save(path, pack)
        tasks.append(dict(offer_id=offer, source_url=raw["source_url"], evidence_file=str(path)))
        protected = [folder / "original-product.json", folder / "processed-product.json"]
        protected += [folder / f for f in processed["images"] + processed["description_images"]]
        before.update({str(p): file_hash(p) for p in protected})
    save(out / "tasks.json", tasks)
    with patch("socket.socket", side_effect=AssertionError("No network allowed in local test")), \
         patch("app.woocommerce.WooCommerceClient", side_effect=AssertionError("No store initialization allowed")):
        first = Runner(ROOT, dry_run=True, run_dir=out / "run").run(tasks)
        second = Runner(ROOT, dry_run=True, run_dir=out / "run").run(tasks)
    unchanged = all(file_hash(p) == h for p, h in before.items())
    report = dict(first_run=first, resume=second, existing_artifacts_unchanged=unchanged,
                  network_forbidden=True, woocommerce_initialized=False, woo_writes=0,
                  local_models_executed=False, live_publication_test="NOT_EXECUTED")
    save(out / "test-report.json", report)
    print(json.dumps(dict(products=[{"offer": r["offer_id"], "status": r["status"], "reason": r.get("reason"),
                                     "sku_count": r.get("sku_count"), "images": r.get("image_count"),
                                     "title": r.get("keyword_decision"), "stages": r["stages"]} for r in second["products"]],
                          unchanged=unchanged, llm_calls=second["llm_calls"], vision_calls=second["vision_calls"],
                          queries=second["keyword_api_queries"], live_store_test="NOT_EXECUTED"), ensure_ascii=False, indent=2))
    return 0 if unchanged and first["successes"] == second["successes"] == 3 else 1


if __name__ == "__main__":
    raise SystemExit(main())
