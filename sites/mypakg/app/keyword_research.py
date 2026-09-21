"""Local keyword proposals; unavailable metrics are never fabricated."""
import hashlib
import json
import time
from pathlib import Path
from .runner_state import save


def normalize(value):
    return ' '.join(value.casefold().split())


class CacheProvider:
    def __init__(self, path='data/keyword-cache.json', ttl=604800):
        self.path, self.ttl = Path(path), ttl
        self.entries = json.loads(self.path.read_text(encoding='utf-8')) if self.path.exists() else {}

    def key(self, keyword, country, language, source):
        return hashlib.sha256(json.dumps([normalize(keyword), country.upper(), language.lower(), source]).encode()).hexdigest()

    def get(self, keyword, country, language, source):
        item = self.entries.get(self.key(keyword, country, language, source))
        return item if item and time.time() - item['timestamp'] < self.ttl else None

    def put(self, item):
        self.entries[self.key(item['keyword'], item['country'], item['language'], item['source'])] = item
        self.path.parent.mkdir(parents=True, exist_ok=True)
        save(self.path, self.entries)


class UnavailableProvider:
    source = 'unconfigured'

    def query(self, keyword, country, language):
        return dict(keyword=keyword, country=country.upper(), language=language.lower(),
                    source=self.source, timestamp=time.time(), volume=None, KD=None,
                    intent=None, parent_topic=None, status='DATA_UNAVAILABLE',
                    reason='Offline test: no external request or credential read',
                    verification='UNVERIFIED_CANDIDATE')


class AhrefsProvider(UnavailableProvider):
    source = 'ahrefs'


class TrendsProvider(UnavailableProvider):
    source = 'google_trends'


class SerpProvider(UnavailableProvider):
    source = 'google_serp'


def query_batch(keywords, providers, cache, country='US', language='en'):
    results = {}
    for keyword in dict.fromkeys(normalize(k) for k in keywords):
        results[keyword] = []
        for provider in providers:
            item = cache.get(keyword, country, language, provider.source)
            if item is None:
                item = provider.query(keyword, country, language)
                # Do not let unavailable/offline responses poison future live queries.
                if item['status'] != 'DATA_UNAVAILABLE':
                    cache.put(item)
            results[keyword].append(item)
    return results


def candidates(facts):
    core = facts['product_type']
    values = [core]
    for field in ('material', 'size', 'structure'):
        if facts.get(field):
            values.append(f"{facts[field]} {core}")
    return list(dict.fromkeys(normalize(v) for v in values))


def select_primary(words, results, mapping, offer_id):
    used = {row['primary_keyword'] for row in mapping if row['offer_id'] != offer_id}
    eligible = [w for w in words if not any(r.get('relevance') == 'REJECT_KEYWORD' for r in results[w])]
    if not eligible:
        raise ValueError('All candidates rejected by SERP relevance')
    # A metric alone cannot establish product relevance; require explicit SERP approval.
    def rank(word):
        rows = results[word]
        relevant = any(r.get('relevance') == 'PASS' for r in rows)
        verified = relevant and any(r.get('verification') == 'VERIFIED_KEYWORD_DATA' for r in rows)
        volume = max((r.get('volume') or 0 for r in rows), default=0) if verified else 0
        return verified, word not in used, volume
    return max(eligible, key=rank)
