"""Evidence-bound English facts, identifiers/prices, and local category selection."""
from __future__ import annotations

import copy
import re
from urllib.parse import urlparse

from .core import calculate_sale_price, extract_offer_id
from .runner_state import ReviewRequired, digest


def canonical(url):
    parsed = urlparse(str(url))
    if parsed.scheme not in ("https", "http") or parsed.hostname not in ("detail.1688.com", "m.1688.com"):
        raise ValueError("Unsupported product source host")
    return extract_offer_id(url)


def english(value):
    return not re.search(r"[\u3400-\u9fff]", str(value))


# Small explicit glossary, not model inference. Unknown types/options are queued.
# Compound type tokens take precedence over generic supplier title keywords.
TYPE_RULES = (
    ("cone filling funnel", ("装填", "漏斗"), ["Herb Accessories"]),
    ("cone storage tube", ("收纳管", "锥形"), ["Pre-roll Packaging"]),
    ("herb grinder", ("烟草", "研磨器"), ["Herb Grinders"]),
)
VALUE_GLOSSARY = {"黑色": "Black", "白色": "White", "红色": "Red", "蓝色": "Blue", "绿色": "Green",
                  "黄色": "Yellow", "紫色": "Purple", "粉色": "Pink", "银色": "Silver", "金色": "Gold",
                  "塑料": "Plastic", "锌合金": "Zinc alloy", "铝合金": "Aluminum alloy", "不锈钢": "Stainless steel"}
NAME_GLOSSARY = {"颜色": "Color", "规格": "Specification", "尺寸": "Size", "材质": "Material"}


def deterministic_pack(source):
    """Known literal source facts only. No network, undocumented translation or AI."""
    title = source["title"]
    matches = [r for r in TYPE_RULES if all(token in title for token in r[1])]
    if len(matches) != 1:
        raise ReviewRequired("UNKNOWN_PRODUCT_TYPE_OR_AMBIGUOUS_ENGLISH_SEMANTICS")
    kind, tokens, categories = matches[0]
    facts = {"product_type": kind}
    evidence = {"product_type": tokens[0]}
    for cn, en in (("锌合金", "zinc alloy"), ("铝合金", "aluminum alloy"), ("不锈钢", "stainless steel"), ("塑料", "plastic")):
        if cn in title:
            facts["material"] = en
            evidence["material"] = cn
            break
    skus = copy.deepcopy(source["skus"])
    for s in skus:
        attrs = {}
        for k, v in s["attributes"].items():
            name, value = NAME_GLOSSARY.get(k, k), VALUE_GLOSSARY.get(str(v), str(v))
            if not english(name) or not english(value):
                raise ReviewRequired("UNKNOWN_SKU_OPTION_TRANSLATION")
            # Do not silently merge two attributes into one English name.
            if name in attrs:
                raise ReviewRequired("ATTRIBUTE_TRANSLATION_COLLISION")
            attrs[name] = value
        s["attributes"] = attrs
    candidates = [kind]
    if facts.get("material"):
        candidates.append(facts["material"] + " " + kind)
    initial = kind.title() + (" - " + facts["material"].title() if facts.get("material") else "")
    return dict(source_fingerprint=digest(source), facts=facts, fact_evidence=evidence,
                translated_skus=skus, current_title=initial, current_primary=kind, category_terms=categories,
                seed_keywords=candidates, keyword_relevance={k: {"supported": True, "specificity": 1} for k in candidates},
                title_options={k: {"title": initial, "source_evidence": evidence} for k in candidates},
                origin="literal_controlled_glossary_not_llm; initial title not a search-demand claim")


def validate_source(source, input_url):
    offer = canonical(input_url)
    if str(source.get("offer_id")) != offer or canonical(source.get("source_url")) != offer:
        raise ValueError("FAIL_SOURCE_OFFER_BINDING")
    if source.get("model") != "Model: " + offer:
        raise ValueError("FAIL_MODEL")
    if not source.get("title") or not source.get("skus") or not source.get("raw_images"):
        raise ValueError("FAIL_REQUIRED_SOURCE_FIELDS")
    skus = source["skus"]
    if len({str(s["sku"]) for s in skus}) != len(skus):
        raise ValueError("FAIL_DUPLICATE_SOURCE_SKU")
    for sku in skus:
        if not sku.get("sku") or not sku.get("variation_id") or not sku.get("attributes"):
            raise ValueError("FAIL_SKU_COMPLETENESS")
        price = calculate_sale_price(sku["source_price"])
        if not price.is_finite() or price <= 0:
            raise ValueError("FAIL_SOURCE_PRICE")
    return dict(offer_id=offer, sku_count=len(skus), model=source["model"])


def priced_skus(source, approved):
    """Read source price every time, preserve source identifiers exactly."""
    translated = {str(s["sku"]): s for s in approved.get("skus", [])}
    if set(translated) != {str(s["sku"]) for s in source["skus"]}:
        raise ReviewRequired("SKU_TRANSLATION_SET_MISMATCH")
    result = []
    for s in source["skus"]:
        t = translated[str(s["sku"])]
        for k in ("variation_id", "spec_id", "source_spec_id"):
            if t.get(k) != s.get(k):
                raise ReviewRequired("IMMUTABLE_IDENTIFIER_MISMATCH: " + k)
        if len(t.get("attributes", {})) != len(s["attributes"]) or not english(t.get("attributes")):
            raise ReviewRequired("SKU_TRANSLATION_REQUIRED")
        item = copy.deepcopy(s)
        item["attributes"] = t["attributes"]
        item["sale_price"] = str(calculate_sale_price(s["source_price"]))
        result.append(item)
    return result


def prepare_content(source, evidence, processed=None):
    """A source-hash-bound approved translation pack is reusable without a model.

    A new unfamiliar Chinese product is queued, never translated by deleting
    Chinese characters or pretending a dictionary is a semantic review.
    """
    if not evidence or evidence.get("source_fingerprint") != digest(source):
        raise ReviewRequired("ENGLISH_PRODUCT_FACTS_REQUIRE_SOURCE_BOUND_APPROVAL")
    facts = evidence.get("facts", {})
    if not facts.get("product_type") or not english(facts):
        raise ReviewRequired("ENGLISH_PRODUCT_FACTS_MISSING")
    for value in evidence.get("fact_evidence", {}).values():
        if not value or value not in str(source):
            raise ReviewRequired("PRODUCT_FACT_EVIDENCE_NOT_IN_SOURCE")
    if set(facts) - set(evidence.get("fact_evidence", {})):
        raise ReviewRequired("PRODUCT_FACT_WITHOUT_EVIDENCE")
    translated = evidence.get("translated_skus")
    if translated is None:
        if not processed or evidence.get("processed_fingerprint") != digest(processed):
            raise ReviewRequired("EXISTING_TRANSLATION_PACK_NOT_HASH_BOUND")
        translated = processed["skus"]
    skus = priced_skus(source, {"skus": translated})
    current = evidence.get("current_title", "")
    if not current or not english(current):
        raise ReviewRequired("CURRENT_ENGLISH_TITLE_REQUIRED")
    specs = {key.replace("_", " ").title(): value for key, value in facts.items() if key != "product_type"}
    # A concise neutral page from confirmed facts, no fixed long marketing copy.
    overview = current.rstrip(".") + "."
    return dict(offer_id=str(source["offer_id"]), source_url=source["source_url"], model=source["model"],
                title=current, skus=skus, facts=facts, description_overview=overview,
                description_specs=specs, description_bullets=[], short_description=overview,
                seo=dict(meta_title=current, meta_description=overview, focus_keyword=evidence.get("current_primary", "")),
                slug=re.sub(r"[^a-z0-9]+", "-", current.lower()).strip("-"))


def select_category(tree, facts, category_terms):
    """Pick deepest exact approved type/category-name match, never a title guess."""
    by_id = {int(c["id"]): c for c in tree}
    approved = {t.casefold() for t in category_terms}
    matches = []
    for c in tree:
        if c["name"].casefold() not in approved:
            continue
        path, node, visited = [], c, set()
        while node:
            cid = int(node["id"])
            if cid in visited:
                raise ValueError("Category tree cycle")
            visited.add(cid)
            path.insert(0, node["name"])
            node = by_id.get(int(node.get("parent") or 0))
        matches.append((len(path), c, path))
    if not matches:
        raise ReviewRequired("WARNING: category_unresolved")
    matches.sort(key=lambda r: r[0], reverse=True)
    if len(matches) > 1 and matches[0][0] == matches[1][0]:
        raise ReviewRequired("CATEGORY_MATCH_AMBIGUOUS")
    _, category, path = matches[0]
    return dict(id=int(category["id"]), name=category["name"], selected_category_ids=[int(category["id"])],
                selected_category_names=[category["name"]], category_path=" > ".join(path),
                category_selection_reason="Approved true product type " + facts["product_type"] + "; deepest exact existing category")
