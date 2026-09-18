import tempfile
import unittest
from pathlib import Path
from app.keyword_research import CacheProvider, AhrefsProvider, query_batch, select_primary
from app.seo_title_builder import build_title


class KeywordTests(unittest.TestCase):
    def test_offline_missing_metrics(self):
        with tempfile.TemporaryDirectory() as d:
            rows = query_batch(['Tube', ' tube '], [AhrefsProvider()], CacheProvider(Path(d)/'c.json'))
            self.assertEqual(len(rows), 1)
            self.assertIsNone(rows['tube'][0]['volume'])
            self.assertEqual(rows['tube'][0]['status'], 'DATA_UNAVAILABLE')

    def test_cache_market_and_ttl(self):
        import time
        with tempfile.TemporaryDirectory() as d:
            c = CacheProvider(Path(d)/'c.json')
            c.put(dict(keyword='tube', country='US', language='en', source='fixture', timestamp=time.time()))
            self.assertIsNotNone(c.get(' TUBE ', 'US', 'en', 'fixture'))
            self.assertIsNone(c.get('tube', 'GB', 'en', 'fixture'))
            c.ttl = -1
            self.assertIsNone(c.get('tube', 'US', 'en', 'fixture'))

    def test_reject_and_mapping(self):
        rows = {'tube': [{'relevance': 'REJECT_KEYWORD', 'volume': 99999}], 'plastic tube': []}
        self.assertEqual(select_primary(list(rows), rows, [], '1'), 'plastic tube')
        rows['tube'] = []
        self.assertEqual(select_primary(list(rows), rows, [{'offer_id':'2','primary_keyword':'tube'}], '1'), 'plastic tube')

    def test_no_invented_title(self):
        with self.assertRaises(ValueError):
            build_title({'product_type':'tube'}, 'steel tube')


if __name__ == '__main__':
    unittest.main()
