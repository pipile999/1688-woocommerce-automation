"""Synchronize verified remote results to offer-local artifacts without new store writes."""
import shutil
from pathlib import Path
from PIL import Image
from .strict_reaudit import RUN,OUTPUT,read,save
from .strict_reaudit_images import sha

def sync_one(folder):
    final=read(folder/'final-audit.json')
    if not final.get('rest_verified') or (folder/'local-sync.json').exists():return
    plan=read(folder/'proposal.json');after=read(folder/'after.json');offer=plan['offer_id'];root=OUTPUT/offer
    productpath=root/'processed-product.json';product=read(productpath)
    save(folder/'processed-before.json',product)
    records={r['index']:r for r in plan['records']};mapping={};newrecords=[]
    provenance=read(folder/'upload-provenance.json');bysha={r['final_sha256']:r for r in provenance}
    media=read(root/'wordpress-media-map.json') if (root/'wordpress-media-map.json').exists() else {}
    remote={i['id']:i['src'] for i in after['parent']['images']}
    for v in after['variations']:
        if v.get('image'):remote[v['image']['id']]=v['image']['src']
    for value in read(folder/'uploaded-media.json').values() if (folder/'uploaded-media.json').exists() else []:remote[value['id']]=value['src']
    for index in plan['top']+plan['description']+plan['variation_extra']:
        r=records[index];source=Path(r['final_path']);checksum=sha(source)
        assert checksum==r['visual_review_sha256']
        with Image.open(source) as image:assert image.format=='WEBP','Final accepted asset must already be WebP'
        relative=f'strict_quality_images/{index:03d}-{checksum[:12]}.webp';target=root/relative
        target.parent.mkdir(exist_ok=True);shutil.copy2(source,target)
        mapping[index]=relative;p=bysha[checksum]
        url=remote.get(p['attachment_id']) or r.get('url')
        assert url,'Uploaded asset URL missing'
        media[relative]={'id':p['attachment_id'],'src':url}
        newrecords.append({'relative':relative,'replacement':relative,'source_filename':r['source_filename'],
            'raw_sha256':r['raw_sha256'],'source_image_url':r['source_image_url'],'source_offer_id':offer,
            'decision':'repair' if r.get('repair_method') else 'keep','visual_qa':'PASS','final_sha256':checksum})
    product['images']=[mapping[i] for i in plan['top']]
    product['featured_image']=product['images'][0]
    product['description_images']=[mapping[i] for i in plan['description']]
    byid={media[v]['id']:v for v in mapping.values()}
    product['variation_image_map']={str(v['sku']):byid.get((v.get('image') or {}).get('id')) for v in after['variations']}
    product['woocommerce_uploaded']=True;product['woocommerce_product_id']=plan['product_id'];product['woocommerce_status']=after['parent']['status']
    product['verified_description_html']=after['parent']['description']
    product.setdefault('processing',{})['strict_reaudit_20260915']={'rest_verified':True,'visual_qa':'PASS','audit':str(folder/'final-audit.json')}
    save(productpath,product);save(root/'wordpress-media-map.json',media)
    save(root/'quality-audit-strict-20260915.json',{'offer_id':offer,'product_id':plan['product_id'],'records':newrecords,'final_audit':final})
    save(folder/'local-sync.json',{'done':True,'image_count':len(mapping),'raw_originals_unchanged':True})

def main():
    for folder in sorted((RUN/'offers').iterdir()):
        if (folder/'final-audit.json').exists():
            try:sync_one(folder)
            except Exception as exc:print('Local sync error',folder.name,type(exc).__name__,str(exc),flush=True)

if __name__=='__main__':main()
