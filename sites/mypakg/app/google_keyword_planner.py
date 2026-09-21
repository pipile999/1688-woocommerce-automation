"""Google Planner exact-market cache first; optional official SDK, no LLM.

UI/export evidence is a supported offline source, not an API credential. SDK
reference: https://developers.google.com/google-ads/api/samples/generate-keyword-ideas
"""
from __future__ import annotations

import math
import os
import time
from pathlib import Path

from .keyword_research import CacheProvider, normalize
from .runner_state import read, save

SOURCES = ("google_keyword_planner_api", "google_keyword_planner_ui", "google_keyword_planner_export")


def bounds(row):
    interval = row.get("monthly_searches") or {}
    lo = row.get("monthly_searches_min", interval.get("min"))
    hi = row.get("monthly_searches_max", interval.get("max"))
    if lo is None and row.get("volume") is not None:
        lo = hi = row["volume"]
    return lo, hi


class GoogleKeywordPlanner:
    def __init__(self, cache_path, *, allow_api=False, country="US", language="en", ttl=604800):
        self.cache = CacheProvider(cache_path, ttl)
        self.allow_api, self.country, self.language = allow_api, country.upper(), language.lower()
        self.keyword_api_queries = 0
        self.cache_hits = 0
        self.cost = 0.0  # No calls yet; becomes unknown on an actual remote call.
        self.attempted = {}

    def cached(self, keyword):
        rows = [self.cache.get(keyword, self.country, self.language, s) for s in SOURCES]
        rows = [r for r in rows if r]
        if rows:
            self.cache_hits += 1
            return dict(max(rows, key=lambda r: r["timestamp"]), cache_event="CACHE_HIT")

    def _api_ideas(self, seeds):
        """Read config through the SDK only; never log credentials or API errors."""
        config = os.environ.get("GOOGLE_ADS_CONFIGURATION_FILE_PATH")
        customer = os.environ.get("GOOGLE_ADS_CUSTOMER_ID")
        if not self.allow_api or not config or not customer:
            return [], "DATA_UNAVAILABLE: configure Google Ads SDK file and Customer ID or import Planner evidence"
        if (self.country, self.language) != ("US", "en"):
            return [], "DATA_UNAVAILABLE: API geo/language constants not configured for this market"
        try:
            from google.ads.googleads.client import GoogleAdsClient
            client = GoogleAdsClient.load_from_storage(config)
            service = client.get_service("KeywordPlanIdeaService")
            request = client.get_type("GenerateKeywordIdeasRequest")
            request.customer_id = customer.replace("-", "")
            request.language = "languageConstants/1000"
            request.geo_target_constants.append("geoTargetConstants/2840")
            request.keyword_plan_network = client.enums.KeywordPlanNetworkEnum.GOOGLE_SEARCH
            request.include_adult_keywords = False
            request.keyword_seed.keywords.extend(seeds)
            request.page_size = 1000
            self.keyword_api_queries += 1
            self.cost = None  # API invoice/pricing data unavailable, not estimated.
            response = service.generate_keyword_ideas(request=request, retry=None, timeout=60)
            # Only first page: no hidden auto-pagination charges/queries.
            rows = []
            for idea in response.results:
                if not idea._pb.HasField("keyword_idea_metrics"):
                    continue
                metrics = idea.keyword_idea_metrics
                present = {f.name for f, _ in metrics._pb.ListFields()}
                volume = int(metrics.avg_monthly_searches) if "avg_monthly_searches" in present else None
                rows.append(dict(keyword=normalize(idea.text), country=self.country, language=self.language,
                                 source=SOURCES[0], timestamp=time.time(), volume=volume, KD=None,
                                 competition=metrics.competition.name if "competition" in present else None,
                                 bid_low_micros=int(metrics.low_top_of_page_bid_micros) if "low_top_of_page_bid_micros" in present else None,
                                 bid_high_micros=int(metrics.high_top_of_page_bid_micros) if "high_top_of_page_bid_micros" in present else None,
                                 bid_currency="CUSTOMER_ACCOUNT_CURRENCY_NOT_VERIFIED",
                                 status="VERIFIED_KEYWORD_DATA" if volume is not None else "DATA_UNAVAILABLE",
                                 origin="google_keyword_idea", network="GOOGLE_SEARCH",
                                 evidence_source="Google Ads GenerateKeywordIdeas", include_adult_keywords=False,
                                 monthly_history=[dict(year=m.year, month=m.month.name,
                                                      searches=m.monthly_searches) for m in metrics.monthly_search_volumes]))
            return rows, None
        except Exception as exc:
            return [], "DATA_UNAVAILABLE: " + type(exc).__name__  # Never expose payload/token.

    def query(self, keywords):
        words = list(dict.fromkeys(normalize(w) for w in keywords))
        result, missing = {}, []
        for word in words:
            row = self.cached(word) or self.attempted.get(word)
            if row:
                result[word] = row
            else:
                missing.append(word)
        # Google limits keyword seeds. Dedup across products through cache/attempted.
        for offset in range(0, len(missing), 20):
            batch = missing[offset:offset + 20]
            rows, reason = self._api_ideas(batch)
            for row in rows:
                self.cache.put(row)
                result[row["keyword"]] = row
            for word in batch:
                row = result.get(word) or dict(keyword=word, country=self.country, language=self.language,
                    source=SOURCES[0], timestamp=time.time(), volume=None, KD=None,
                    status="DATA_UNAVAILABLE", reason=reason or "No metric returned for seed")
                self.attempted[word] = result[word] = row
        return result

    def import_evidence(self, path):
        """Normalized JSON export: explicit market, date, source and raw evidence required."""
        rows = read(path)
        if not isinstance(rows, list):
            raise ValueError("Expected a list of normalized Planner export rows")
        for row in rows:
            if not all(row.get(k) for k in ("keyword", "country", "language", "timestamp", "evidence_source")):
                raise ValueError("Planner evidence requires keyword, market, timestamp and source")
            row = dict(row, source="google_keyword_planner_export")
            if row["country"].upper() != self.country or row["language"].lower() != self.language:
                raise ValueError("Planner evidence market mismatch")
            if bounds(row)[0] is None:
                row.update(status="DATA_UNAVAILABLE", volume=None)
            self.cache.put(row)


def score_keywords(rows, relevance, mapping, offer_id):
    """Local decision scores, NOT a forecast of organic rank or search volume."""
    owners = {normalize(x.get("primary_keyword") or ""): str(x.get("offer_id"))
              for x in mapping if str(x.get("offer_id")) != str(offer_id)}
    results = []
    for word, row in rows.items():
        rel = relevance.get(word, {})
        match = row.get("serp_match", row.get("relevance", "NOT_CHECKED"))
        if isinstance(match, dict):
            match = match.get("match", "NOT_CHECKED")
        lo, hi = bounds(row)
        verified = row.get("status") != "DATA_UNAVAILABLE" and lo is not None
        allowed = bool(rel.get("supported")) and match == "PASS" and verified and lo > 0
        rejection = None
        if not rel.get("supported"):
            rejection = "UNCONFIRMED_PRODUCT_RELEVANCE"
        elif match != "PASS":
            rejection = "SERP_" + str(match)
        elif not verified or lo <= 0:
            rejection = "NO_CONFIRMED_POSITIVE_DEMAND"
        elif word in owners:
            rejection = "KEYWORD_MAP_CONFLICT"
            allowed = False
        commercial = 1.2 if rel.get("b2b_supported") and any(t in word.split() for t in ("bulk", "wholesale", "supplier")) else 1.0
        # Ads competition is only a commercial-market tie factor, never organic KD.
        competition = {"LOW": 1.05, "MEDIUM": 1.0, "HIGH": .95}.get(row.get("competition"), 1.0)
        demand = 1 + math.log10(max(1, lo or 0)) / 5
        score = float(rel.get("specificity", 1)) * commercial * demand * competition if allowed else 0
        results.append(dict(keyword=word, score=round(score, 5), eligible=allowed, reason=rejection,
                            evidence=row, monthly_searches_min=lo, monthly_searches_max=hi,
                            organic_difficulty="DATA_UNAVAILABLE", product_evidence=rel))
    return sorted(results, key=lambda r: (-r["score"], r["keyword"]))


def recommend_title(current_title, ranked, title_options, current_primary=None):
    """Only select an evidenced exact title option; no inferred facts/brand guesses."""
    chosen = next((r for r in ranked if r["eligible"] and r["keyword"] in title_options), None)
    current = next((r for r in ranked if r["keyword"] == normalize(current_primary or "")), None)
    result = dict(title=current_title, action="KEEP_CURRENT_TITLE", primary_keyword=current_primary,
                  reason="No sufficient verified improvement", llm_calls=0)
    if not chosen:
        return result
    if current and current["eligible"] and chosen["score"] < current["score"] * 1.15:
        return result
    option = title_options[chosen["keyword"]]
    if not option.get("source_evidence") or not option.get("title"):
        return result
    if option["title"] == current_title:
        return dict(result, primary_keyword=chosen["keyword"], reason="Existing title already matches evidence")
    return dict(result, title=option["title"], primary_keyword=chosen["keyword"],
                action="PROPOSE_CHANGE", reason="Verified relevance, positive US demand, SERP and map; local score improvement")
