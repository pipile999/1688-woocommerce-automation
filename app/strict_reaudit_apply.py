"""Apply only uniquely bound, visually approved retrospective proposals."""
from __future__ import annotations
import argparse,html,json,re,time
from copy import deepcopy
from io import BytesIO
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from PIL import Image,ImageOps
from .strict_reaudit import RUN,ROOT,OUTPUT,read,save,digest,canonical,candidate_evidence,all_variations,identified_offers
from .strict_reaudit_images import phash,distance,sha
from .image_pipeline import adaptive_quality_webp
from . import batch50_upload_publish as u

CHECKPOINT=RUN/'repair-checkpoint.json'

def checkpoint(result):
    entries=read(CHECKPOINT) if CHECKPOINT.exists() else {}
    offer=result['offer_id']
    if entries.get(offer,{}).get('status')=='UPDATED':return
    entries[offer]={'product_id':result['product_id'],'offer_id':offer,
        'status':'UPDATED' if result.get('modified') else 'SKIPPED',
        'timestamp':result.get('verified_at',u.utcnow()),'rest_verified':True}
    save(CHECKPOINT,entries)

def protected(parent,variations):
    fields=('id','name','slug','status','type','sku','regular_price','sale_price','categories','attributes','meta_data')
    # Strip REST metadata row IDs; retain every key/value, not only identity fields.
    result={k:parent.get(k) for k in fields};result['meta_data']={m['key']:m['value'] for m in parent.get('meta_data',[])
        if m['key']!='shopengine_product_views_count' and not
        (m['key']=='_elementor_page_assets' and m['value'] in (None,[],{}))}
    result['variations']={str(v['id']):{k:v.get(k) for k in ('sku','regular_price','sale_price','attributes','manage_stock','stock_quantity')} for v in variations}
    for v in variations:result['variations'][str(v['id'])]['meta_data']={m['key']:m['value'] for m in v.get('meta_data',[])}
    return result

def upload_image(client,offer,record,folder,role):
    assert record['source_offer_id']==offer and canonical(record['source_url'])==offer
    assert record.get('source_image_url') and record.get('raw_sha256') and record.get('visual_qa')=='PASS'
    target=Path(record['final_path']);assert target.resolve().is_relative_to(OUTPUT.resolve())
    if record.get('attachment_id') and target==Path(record['current_path']) and record.get('http',{}).get('pass'):
        return {'id':record['attachment_id'],'src':record['url'],'reused_same_offer_attachment':True}
    cachepath=folder/'uploaded-media.json';cache=read(cachepath) if cachepath.exists() else {}
    checksum=sha(target)
    if checksum in cache:return cache[checksum]
    with Image.open(target) as image:
        if image.format=='WEBP':payload=target.read_bytes()
        else:
            image=ImageOps.exif_transpose(image).convert('RGB')
            payload,quality=adaptive_quality_webp(image,source_dimensions=image.size,source_filesize=target.stat().st_size,max_edge=None,text_sensitive=False)
            destination=folder/'final'/f"{record['index']:03d}.webp";destination.parent.mkdir(exist_ok=True);destination.write_bytes(payload)
            record['final_encoding']=quality
    name=f"{offer}-strict-{record['index']:03d}.webp"
    response=u.wp_request(client,'POST','media',files={'file':(name,BytesIO(payload),'image/webp')},data={'title':role+' '+offer,'alt_text':record.get('alt',role+' product view')},timeout=240).json()
    result={'id':response['id'],'src':response['source_url']}
    cache[checksum]=result;save(cachepath,cache)
    return result

def description(parent,plan,media):
    from bs4 import BeautifulSoup
    soup=BeautifulSoup(parent.get('description',''),'html.parser')
    existing_urls=[image.get('src') for image in soup.find_all('img')]
    target_urls=[media[index]['src'] for index in plan['description']]
    original_description=parent.get('description','')
    for figure in list(soup.find_all('figure')):
        if figure.find('img'):figure.decompose()
    for image in list(soup.find_all('img')):image.decompose()
    added_specs={};existing_text=soup.get_text(' ',strip=True)
    for r in plan['records']:
        for key,evidence in r.get('spec_evidence',{}).items():
            if evidence['value'] in existing_text:continue
            if key in added_specs and added_specs[key]!=evidence['value']:added_specs.pop(key,None);continue
            added_specs[key]=evidence['value']
    body=str(soup)
    # Do not rewrite already-correct HTML merely to apply our wrapper/template.
    if not added_specs and existing_urls==target_urls:
        return original_description,{}
    if added_specs:
        rows=''.join(f'<tr><th>{html.escape(k)}</th><td>{html.escape(v)}</td></tr>' for k,v in added_specs.items())
        body+='<h2>Specifications</h2><table>'+rows+'</table>'
    if plan['description']:
        body+='<div class="verified-product-details">'
        for index in plan['description']:
            body+=f'<figure><img src="{html.escape(media[index]["src"],quote=True)}" alt="{html.escape(plan["title"],quote=True)}" style="max-width:100%;height:auto;" loading="lazy"></figure>'
        body+='</div>'
    return body,added_specs

def apply_one(client,planpath):
    plan=read(planpath);folder=planpath.parent;offer=plan['offer_id'];identity=read(folder/'audit.json')
    if CHECKPOINT.exists() and read(CHECKPOINT).get(offer,{}).get('status')=='UPDATED':return
    if (folder/'final-audit.json').exists():
        previous=read(folder/'final-audit.json')
        if previous.get('rest_verified'):
            checkpoint(previous);return
        history=folder/'previous-attempts';history.mkdir(exist_ok=True)
        save(history/(str(time.time_ns())+'.json'),previous)
    result={'offer_id':offer,'product_id':plan['product_id'],'modified':False,'warnings':list(plan['warnings']),'failures':list(plan['failures'])}
    try:
        assert identity['result']=='MAPPING_PASS','Identity not uniquely proven'
        assert plan['visual_qa']=='PASS','Final visual inspection pending'
        assert not plan['failures'],'Proposal has hard failures'
        indices=plan['top']+plan['description']+plan['variation_extra'];records={r['index']:r for r in plan['records']}
        assert 0<len(plan['top'])<=5 and len(plan['top']+plan['description'])<=10
        for index in indices:
            r=records[index];assert r.get('visual_qa')=='PASS' and not r.get('provenance_failure')
            assert r['source_offer_id']==offer and r['woocommerce_product_id']==plan['product_id']
            assert sha(r['final_path'])==r['visual_review_sha256'],'Image changed after visual approval'
        for a in plan['top']:
            r=records[a];assert r['main_pool'] and r['final_width']==r['final_height'] and r['final_width']>=600
            for b in plan['description']:assert distance(records[a]['final_phash'],records[b]['final_phash'])>5,'Perceptual top/detail duplicate'
        pid=plan['product_id'];before=client.get(f'products/{pid}',{'context':'edit','_':str(time.time())});variations=all_variations(client,pid) if before['type']=='variable' else []
        source=read(OUTPUT/offer/'original-product.json');product=read(OUTPUT/offer/'processed-product.json')
        evidence=candidate_evidence(offer,before,source,product,variations);assert evidence['identity_pass'],'Live identity changed since scan'
        initial=read(folder/'selected-before.json');snapshot=protected(before,variations)
        assert snapshot==protected(initial['parent'],initial['variations']),'Protected live data changed concurrently'
        if evidence['warnings']:result['warnings']+=evidence['warnings']
        media={};provenance=[]
        for index in indices:
            r=records[index];role='featured' if index==plan['top'][0] else 'gallery' if index in plan['top'] else 'description' if index in plan['description'] else 'variation'
            r['alt']=plan['title']+' - '+role
            media[index]=upload_image(client,offer,r,folder,role)
            provenance.append({k:r[k] for k in ('source_offer_id','source_url','source_image_url','woocommerce_product_id','raw_sha256')}|{'image_role':role,'attachment_id':media[index]['id'],'final_sha256':sha(r['final_path'])})
        new_description,specs=description(before,plan,media)
        payload={'images':[{'id':media[i]['id']} for i in plan['top']],'description':new_description}
        save(folder/'upload-provenance.json',provenance);save(folder/'intended-patch.json',payload)
        old_to_index={r['attachment_id']:r['index'] for r in plan['records'] if r.get('attachment_id')}
        updates=[];expected_variant_images={}
        for v in variations:
            oldid=(v.get('image') or {}).get('id',0);index=old_to_index.get(oldid)
            if index in media:newid=media[index]['id']
            else:
                duplicate=next((r for r in plan['records'] if r['index']==index),{}).get('duplicate_of')
                newid=media[duplicate]['id'] if duplicate in media else 0
            # An unavailable exact image is cleared, never replaced with a different color.
            if oldid!=newid:updates.append({'id':v['id'],'image':{'id':newid}})
            if not newid:result['warnings'].append('Dedicated variant image removed as unverified/unclean: '+str(v['sku']))
            expected_variant_images[v['id']]=newid
        oldtop=[i['id'] for i in before.get('images',[])];newtop=[media[i]['id'] for i in plan['top']]
        write_required=oldtop!=newtop or before.get('description','')!=new_description or bool(updates)
        result['modified']=write_required
        result['write_required_this_attempt']=write_required
        if write_required:
            client.post(f'products/{pid}',payload)
            for start in range(0,len(updates),100):
                response=client.post(f'products/{pid}/variations/batch',{'update':updates[start:start+100]})
                assert all(v.get('id') and not v.get('error') for v in response.get('update',[])),'Variation update error'
        after=client.get(f'products/{pid}',{'context':'edit','_':str(time.time())});aftervs=all_variations(client,pid) if before['type']=='variable' else []
        assert protected(after,aftervs)==snapshot,'Protected fields changed'
        assert [i['id'] for i in after['images']]==newtop,'Top images not stored'
        urls=re.findall(r'<img[^>]+src=["\']([^"\']+)',after.get('description',''),re.I)
        assert urls==[media[i]['src'] for i in plan['description']],'Description images not stored'
        for v in aftervs:
            expected=expected_variant_images[v['id']];actual=(v.get('image') or {}).get('id',0)
            assert actual==expected or (expected==0 and actual in (0,newtop[0])),'Variation attachment mismatch'
        allurls=list(dict.fromkeys([i['src'] for i in after['images']]+urls+[(v.get('image') or {}).get('src') for v in aftervs if (v.get('image') or {}).get('src')]))
        with ThreadPoolExecutor(max_workers=5) as pool:checks=list(pool.map(u.image_check,allurls))
        assert all(c['pass'] for c in checks),'HTTP image gate failed'
        save(folder/'after.json',{'parent':after,'variations':aftervs})
        # Count actual differences from the original batch baseline, including a
        # prior successful write whose HTTP verification was interrupted.
        result['modified']=([i['id'] for i in initial['parent'].get('images',[])]!=newtop or
            initial['parent'].get('description','')!=after.get('description','') or
            {v['id']:(v.get('image') or {}).get('id',0) for v in initial['variations']}!=
            {v['id']:(v.get('image') or {}).get('id',0) for v in aftervs})
        result.update(rest_verified=True,protected_fields_unchanged=True,http_checks=checks,top_count=len(plan['top']),description_count=len(plan['description']),
            gallery_reduced=max(0,len(oldtop)-len(newtop)),duplicate_images_removed=len(plan['duplicate_pairs']),
            description_supplemented=not re.search(r'<img\b',before.get('description',''),re.I) and bool(plan['description']),
            rembg_redone=sum(bool(records[i].get('rembg_executed')) for i in indices),
            logo_watermark_removed=sum(bool(r.get('contamination')) and (r.get('final_decision')!='candidate' or bool(r.get('repair_method'))) for r in plan['records'] if 'raw_main_candidate' not in r['roles']),
            parameter_to_html=len(specs),parameter_dimension_redone=sum(bool(records[i].get('dimension_rebuilt')) for i in indices),
            status=after['status'],permalink=after['permalink'],verified_at=u.utcnow())
        result['result']='WARNING' if result['warnings'] else 'PASS'
        checkpoint(result)
    except Exception as exc:
        result.update(result='FAIL',rest_verified=False,error=str(exc) if isinstance(exc,AssertionError) else type(exc).__name__)
    save(folder/'final-audit.json',result);print('REST audit',offer,result['result'],'modified',result['modified'],flush=True)

def main():
    u.load_dotenv(ROOT/'.env');client=u.WooCommerceClient()
    for path in sorted((RUN/'offers').glob('*/proposal.json')):
        if read(path).get('visual_qa')=='PASS':apply_one(client,path)

if __name__=='__main__':main()
