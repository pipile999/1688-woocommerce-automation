"""Offer-bound retrospective image audit; no 1688 acquisition and no broad writes."""
from __future__ import annotations
import argparse, hashlib, html, json, re, time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from decimal import Decimal
from urllib.parse import urlparse
from . import batch50_upload_publish as u

ROOT=u.ROOT; OUTPUT=u.OUTPUT; RUN=OUTPUT/'strict-reaudit-20260915'

def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))

def save(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix(path.suffix+'.tmp')
    temp.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8');temp.replace(path)

def canonical(url):
    parsed=urlparse(str(url or ''))
    if parsed.hostname not in ('detail.1688.com','m.1688.com'):return None
    match=re.search(r'/(?:offer/)?(\d+)\.html',parsed.path)
    return match.group(1) if match else None

def digest(value):
    return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()

def normalized(value):
    return re.sub(r'\W+','',html.unescape(str(value)).casefold())

def source_skus(source):
    return source.get('skus',source.get('variations',[]))

def identified_offers(parent):
    meta=u.metadata(parent.get('meta_data',[])); found=set()
    if not any(k.startswith('_1688') for k in meta) and not canonical(meta.get('source_url')):
        return found  # An unrelated store product's generic Model attribute is not 1688 provenance.
    for key in ('_1688_source_url','source_url'):
        if canonical(meta.get(key)):found.add(canonical(meta[key]))
    for key in ('_1688_offer_id','_1688_model'):
        match=re.fullmatch(r'(?:Model:\s*)?(\d+)',str(meta.get(key,'')),re.I)
        if match:found.add(match.group(1))
    for attr in parent.get('attributes',[]):
        if str(attr['name']).lower()=='model':
            for v in attr.get('options',[]):
                match=re.fullmatch(r'(?:Model:\s*)?(\d+)',str(v),re.I)
                if match:found.add(match.group(1))
    return found

def all_variations(client,pid):
    results=[];page=1
    while True:
        rows=client.get(f'products/{pid}/variations',{'per_page':100,'page':page,'context':'edit','_':str(time.time())})
        results.extend(rows)
        if len(rows)<100:return results
        page+=1

def fingerprint(source):
    return digest({'offer_id':canonical(source.get('source_url')),'source_url':source.get('source_url'),
                   'title':source.get('title'),'attributes':source.get('attributes'),
                   'skus':source_skus(source),'raw_images':source.get('raw_images')})

def candidate_evidence(offer,parent,source,product,variations):
    reasons=[]; warnings=[];meta=u.metadata(parent.get('meta_data',[]))
    if identified_offers(parent)!={offer}:reasons.append('Model/source metadata conflict')
    if canonical(meta.get('_1688_source_url'))!=offer:reasons.append('backend source URL canonical ID mismatch')
    if canonical(source.get('source_url'))!=offer or str(source.get('offer_id',offer))!=offer:reasons.append('raw source ID mismatch')
    if canonical(product.get('source_url'))!=offer:reasons.append('processed source ID mismatch')
    if normalized(parent['name'])!=normalized(product.get('title')):reasons.append('live title differs from verified local product')
    expected={str(s['sku']):s for s in source_skus(source)}
    processed={str(s['sku']):s for s in source_skus(product)}
    live={str(s['sku']):s for s in variations}
    if expected.keys()!=processed.keys() or expected.keys()!=live.keys():reasons.append('SKU set differs from raw/processed/live source')
    for sku,s in expected.items():
        if sku not in live or sku not in processed:continue
        v=live[sku];vm=u.metadata(v.get('meta_data',[]))
        for key in ('variation_id','spec_id'):
            if s.get(key) is not None and str(s[key])!=str(processed[sku].get(key)):reasons.append(f'processed {key} changed: {sku}')
            if vm.get('_1688_'+key) is not None and s.get(key) is not None and str(vm['_1688_'+key])!=str(s[key]):reasons.append(f'live {key} mismatch: {sku}')
        pa={normalized(k):normalized(v) for k,v in processed[sku].get('attributes',{}).items()}
        va={normalized(a['name']):normalized(a['option']) for a in v.get('attributes',[])}
        if pa!=va:reasons.append(f'variation attributes differ: {sku}')
        price=s.get('source_price',s.get('price'))
        if price is not None and u.money(v['regular_price'])!=u.money(Decimal(str(price))/Decimal('.7')/Decimal('6.7')):
            warnings.append(f'FAIL_PRICE_FORMULA: {sku}; unchanged pending audit')
    return {'product_id':parent['id'],'source_url':meta.get('_1688_source_url'),
            'identity_pass':not reasons,'reasons':reasons,'warnings':warnings,'sku_count':len(variations)}

def inventory():
    u.load_dotenv(ROOT/'.env');client=u.WooCommerceClient();parents=[];page=1
    while True:
        rows=client.get('products',{'per_page':100,'page':page,'status':'any','context':'edit','_':str(time.time())})
        parents.extend(rows)
        print('WooCommerce inventory page',page,'rows',len(rows),flush=True)
        if len(rows)<100:break
        page+=1
    save(RUN/'store-snapshot.json',parents)
    grouped={}
    for parent in parents:
        for offer in identified_offers(parent):grouped.setdefault(offer,[]).append(parent)
    save(RUN/'scope.json',{'created_at':u.utcnow(),'offer_count':len(grouped),'product_count':sum(bool(identified_offers(p)) for p in parents),'offers':sorted(grouped)})
    def inspect(offer,candidates):
        root=OUTPUT/offer;result={'offer_id':offer,'candidate_product_ids':[p['id'] for p in candidates],'duplicate_offer':len(candidates)>1,'stage':'mapping','updated_at':u.utcnow()}
        try:
            source=read(root/'original-product.json');product=read(root/'processed-product.json')
            evidence=[]; snapshots=[]
            for parent in candidates:
                variations=all_variations(client,parent['id']) if parent['type']=='variable' else []
                evidence.append(candidate_evidence(offer,parent,source,product,variations))
                snapshots.append({'parent':parent,'variations':variations})
            result['candidates']=evidence
            valid=[(e,s) for e,s in zip(evidence,snapshots) if e['identity_pass']]
            save(RUN/'offers'/offer/'before.json',snapshots)
            if len(valid)!=1:
                result.update(result='WARNING_DUPLICATE_MAPPING' if len(candidates)>1 else 'WARNING_SOURCE_MAPPING',reason='No uniquely proven source/product mapping; no writes authorized')
            else:
                e,s=valid[0]
                result.update(result='MAPPING_PASS',product_id=e['product_id'],input_1688_url=source['source_url'],canonical_offer_id=offer,
                              source_url=source['source_url'],product_fingerprint=fingerprint(source),warnings=e['warnings'])
                save(RUN/'offers'/offer/'selected-before.json',s)
        except Exception as exc:
            result.update(result='WARNING_SOURCE_MAPPING',reason=f'{type(exc).__name__}: local evidence missing or inconsistent')
        save(RUN/'offers'/offer/'audit.json',result)
        return result
    results=[]
    with ThreadPoolExecutor(max_workers=4) as pool:
        jobs={pool.submit(inspect,o,c):o for o,c in grouped.items()}
        for job in as_completed(jobs):
            result=job.result();results.append(result)
            print('Mapping',len(results),'/',len(grouped),result['offer_id'],result['result'],flush=True)
    save(RUN/'mapping-summary.json',{'checked_products':sum(len(r['candidate_product_ids']) for r in results),
        'offers':len(results),'eligible':sum(r['result']=='MAPPING_PASS' for r in results),
        'duplicate_offers':sum(r['duplicate_offer'] for r in results),'products':sorted(results,key=lambda r:r['offer_id'])})

def main():
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=['inventory']);args=parser.parse_args()
    if args.stage=='inventory':inventory()

if __name__=='__main__':main()
