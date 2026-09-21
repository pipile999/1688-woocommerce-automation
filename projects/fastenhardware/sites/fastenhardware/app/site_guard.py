"""Fixed site boundary. No CLI or environment override of site identity."""
from pathlib import Path
import json, os, re

SITE = 'fastenhardware'
DOMAIN = 'https://fastenhardware.com'
SKILL = 'fastenhardware-1688-product-import'
ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = ROOT.parents[1] / '03_products' / 'skills' / SKILL
PATHS = {
    'credentials': '.env', 'wordpress_credentials': '.env',
    'category_cache': 'data/category-cache.json',
    'keyword_cache': 'data/keyword-cache.json', 'keyword_map': 'data/keyword-map.json',
    'product_map': 'data/product-map.json', 'offer_product_map': 'data/offer-product-map.json',
    'image_cache': 'output/auto-runner/cache', 'checkpoint': 'output/auto-runner',
    'batch_reports': 'reports', 'audit': 'audit', 'source_url_map': 'data/source-url-map.json',
    'raw_evidence': 'output', 'google_credentials': 'private/google-ads.yaml'
}

def stop(reason):
    raise ValueError('HARD STOP: '+reason)

def assert_site(site_url):
    if site_url != DOMAIN: stop('SITE_URL_MISMATCH')

def contained(path):
    path=Path(path).absolute()
    if not path.resolve().is_relative_to(ROOT.resolve()): stop('CROSS_SITE_PATH')
    for part in [path,*path.parents]:
        if part == ROOT.parent: break
        if part.is_symlink() or (hasattr(part,'is_junction') and part.is_junction()): stop('LINKED_SITE_DATA')
    if path.is_file() and path.stat().st_nlink > 1: stop('HARDLINKED_SITE_DATA')
    return path

def preflight():
    profile=json.loads(contained(ROOT/'site-profile.json').read_text(encoding='utf-8'))
    if profile != {'site':SITE,'site_url':DOMAIN,'skill':SKILL}: stop('PROFILE_MISMATCH')
    for key in ('WOOCOMMERCE_URL','WORDPRESS_URL','WP_URL','SITE_URL'):
        if key in os.environ: assert_site(os.environ[key])
    for rel in PATHS.values(): contained(ROOT/rel)
    if not (SKILL_DIR/'SKILL.md').is_file(): stop('SITE_SKILL_MISSING')
    return {'site':SITE,'site_url':DOMAIN,'skill':SKILL,
            'paths':{k:str(ROOT/v) for k,v in PATHS.items()},
            'credentials_loaded':False,'network_calls':0,'product_operations':0}

def load_credentials():
    preflight()
    from dotenv import dotenv_values
    values=dotenv_values(contained(ROOT/'.env'))
    assert_site(values.get('WOOCOMMERCE_URL'))
    required=('WOOCOMMERCE_CONSUMER_KEY','WOOCOMMERCE_CONSUMER_SECRET',
              'WORDPRESS_USERNAME','WORDPRESS_APPLICATION_PASSWORD')
    if any(not values.get(k) for k in required): stop('SITE_CREDENTIALS_NOT_CONFIGURED')
    # Consume only this site's local file; never fall back to inherited credentials.
    for key in (*required,'WOOCOMMERCE_URL'):
        os.environ[key]=values[key]
    for key in ('GOOGLE_ADS_CONFIGURATION_FILE_PATH','GOOGLE_APPLICATION_CREDENTIALS'):
        os.environ.pop(key,None)
    ads=contained(ROOT/'private/google-ads.yaml')
    if ads.is_file(): os.environ['GOOGLE_ADS_CONFIGURATION_FILE_PATH']=str(ads)

def endpoint(base_url, namespace, method, path):
    assert_site(base_url)
    if method.upper() not in ('GET','POST','PUT','PATCH'): stop('HTTP_METHOD_FORBIDDEN')
    patterns={'wc':r'products(?:/categories(?:/\d+)?|/\d+(?:/variations(?:/\d+)?)?)?',
              'wp':r'(?:media(?:/\d+)?|product/\d+)'}
    if not re.fullmatch(patterns[namespace],path): stop('NON_PRODUCT_ENDPOINT')
    if namespace=='wp' and path.startswith('product/') and method.upper()!='GET': stop('WP_PRODUCT_WRITE_FORBIDDEN')
