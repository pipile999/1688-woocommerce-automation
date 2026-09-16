"""Fresh same-offer image inventory, enhanced OCR and real local-model repairs."""
from __future__ import annotations
import argparse, hashlib, json, re, time
from io import BytesIO
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor,as_completed
import requests
import cv2
import numpy as np
from PIL import Image,ImageOps,ImageDraw,ImageFont
from .strict_reaudit import ROOT,OUTPUT,RUN,read,save,digest,canonical
from .strict_cache import StrictCache,cache_key,rules_version,specification_hash
from .image_pipeline import OCRAdapter,VisionClassifierAdapter,InpaintingAdapter,RembgAdapter,adaptive_quality_webp
from . import requality_yesterday_products as old

VERSION='strict-visual-v1'
BRANDS=('cookies','backwoods','raw rolling','zig-zag','zigzag','yideng','yanju','z.c.y.j','zcyj','oreo','smoking brand')

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def phash(path):
    image=ImageOps.exif_transpose(Image.open(path)).convert('L').resize((32,32),Image.Resampling.LANCZOS)
    values=cv2.dct(np.asarray(image,dtype=np.float32))[:8,:8].flatten()[1:]
    return ''.join('1' if v>np.median(values) else '0' for v in values)
def distance(a,b):return sum(x!=y for x,y in zip(a,b))
def contained(root,relative):
    path=(root/relative).resolve()
    if not path.is_relative_to(root.resolve()):raise ValueError('cross-offer directory path')
    return path

def lineage(root,source):
    mapping={};raw={r['filename']:r for r in source.get('raw_images',[])}
    auditpath=root/'image_audit/image-audit.json'
    if auditpath.exists():
        for r in read(auditpath).get('records',[]):
            filename=r.get('filename')
            if filename not in raw:continue
            for out in (r.get('output_file'),r.get('final_filename')):
                if out:mapping[str(out).replace('\\','/')]=filename;mapping[Path(out).name]=filename
    for path in root.glob('quality-audit-*.json'):
        for r in read(path).get('records',[]):
            filename=r.get('source_filename')
            if filename not in raw:continue
            for out in (r.get('relative'),r.get('replacement')):
                if out:mapping[str(out).replace('\\','/')]=filename;mapping[Path(out).name]=filename
    return mapping,raw

def prepare_one(auditpath):
    identity=read(auditpath);offer=identity['offer_id'];folder=auditpath.parent
    if identity['result']!='MAPPING_PASS':return
    root=OUTPUT/offer;source=read(root/'original-product.json');product=read(root/'processed-product.json')
    before=read(folder/'selected-before.json');parent=before['parent']
    lineage_map,raw=lineage(root,source)
    media=read(root/'wordpress-media-map.json') if (root/'wordpress-media-map.json').exists() else {}
    byid={};byurl={}
    for path,m in media.items():
        if not isinstance(m,dict):continue
        if m.get('id'):byid.setdefault(int(m['id']),[]).append(path)
        if m.get('src'):byurl.setdefault(m['src'],[]).append(path)
    required={}
    def add(url,role,attachment=0):
        if not url:return
        r=required.setdefault(url,{'url':url,'roles':[],'attachment_id':attachment})
        if role not in r['roles']:r['roles'].append(role)
        if attachment:r['attachment_id']=attachment
    for n,m in enumerate(parent.get('images',[])):add(m['src'],'featured' if n==0 else 'gallery',m['id'])
    for url in re.findall(r'<img[^>]+src=["\']([^"\']+)',parent.get('description',''),re.I):add(url,'description')
    for v in before['variations']:
        if v.get('image'):add(v['image'].get('src'),'variation',v['image'].get('id',0))
    records=[]
    for index,(url,r) in enumerate(required.items(),1):
        r.update(index=index,source_offer_id=offer,source_url=source['source_url'],woocommerce_product_id=identity['product_id'])
        paths=byid.get(r['attachment_id'],[]) or byurl.get(url,[])
        sources={lineage_map.get(p) or lineage_map.get(Path(p).name) for p in paths};sources.discard(None)
        if len(sources)==1:
            filename=next(iter(sources));r['source_filename']=filename
            r['source_image_url']=raw[filename]['source_url']
            r['raw_path']=str(contained(root,'raw_images/'+filename))
            r['raw_sha256']=sha(r['raw_path'])
            r['main_pool']=r['source_image_url'] in source.get('main_images',[])
            r['lineage_paths']=paths
        else:r['provenance_failure']='Missing or ambiguous same-offer source image lineage'
        target=folder/'remote'/f'{index:03d}.image'
        try:
            response=requests.get(url,timeout=60)
            r['http']={'status':response.status_code,'content_type':response.headers.get('content-type',''),'pass':response.status_code==200 and response.headers.get('content-type','').startswith('image/')}
            if r['http']['pass']:
                target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(response.content)
                with Image.open(target) as image:r['width'],r['height']=image.size
                r.update(current_path=str(target),current_sha256=sha(target),phash=phash(target))
                if paths:
                    hashes={sha(contained(root,p)) for p in paths if contained(root,p).is_file()}
                    r['remote_matches_local_bytes']=r['current_sha256'] in hashes
            else:r['download_failure']='HTTP/image content failure'
        except Exception as exc:r['download_failure']=type(exc).__name__
        records.append(r)
    # Extra main-pool originals are candidates only, not current storefront images.
    represented={r.get('source_filename') for r in records}
    for filename,r in raw.items():
        if filename in represented or r.get('source_url') not in source.get('main_images',[]):continue
        path=contained(root,'raw_images/'+filename)
        if not path.is_file():continue
        with Image.open(path) as image:w,h=image.size
        records.append({'index':len(records)+1,'roles':['raw_main_candidate'],'source_offer_id':offer,'source_url':source['source_url'],
            'woocommerce_product_id':identity['product_id'],'source_image_url':r['source_url'],'source_filename':filename,'raw_path':str(path),
            'raw_sha256':sha(path),'current_path':str(path),'current_sha256':sha(path),'phash':phash(path),'width':w,'height':h,'main_pool':True})
    save(folder/'image-inventory.json',{'offer_id':offer,'product_id':identity['product_id'],'current_image_count':len(required),'records':records})
    print('Image inventory',offer,len(required),'current /',len(records),'including main candidates',flush=True)

def prepare():
    paths=sorted((RUN/'offers').glob('*/audit.json'))
    with ThreadPoolExecutor(max_workers=5) as pool:
        jobs={pool.submit(prepare_one,p):p for p in paths if read(p).get('result')=='MAPPING_PASS' and not (p.parent/'image-inventory.json').exists()}
        for job in as_completed(jobs):
            try:job.result()
            except Exception as exc:
                p=jobs[job];save(p.parent/'prepare-error.json',{'error':type(exc).__name__,'stage':'image inventory','offer_id':p.parent.name})
                print('Image inventory FAIL',p.parent.name,type(exc).__name__,flush=True)

def png(image):
    stream=BytesIO();image.save(stream,format='PNG');return stream.getvalue()

class Models:
    def __init__(self):
        self.ocr=OCRAdapter();self.clip=VisionClassifierAdapter();self.lama=None;self.rembg=None
        self.cache=StrictCache(RUN/'exact-ai.sqlite',RUN/'cache-events.jsonl')
        self.version=rules_version()+':'+VERSION
    def analyze(self,path,source):
        keyargs={'offer_id':str(source['offer_id']),'source_url':source['source_url'],'image_hash':sha(path),'spec_hash':specification_hash(source),'rules_ver':self.version}
        key=cache_key(**keyargs);cached=self.cache.lookup(key=key,offer_id=keyargs['offer_id'])
        if cached:return {**cached,'cache_event':'CACHE_HIT','executed_this_call':False}
        image=ImageOps.exif_transpose(Image.open(path)).convert('RGB');base=self.ocr.analyze(png(image))
        gray=cv2.cvtColor(np.asarray(image),cv2.COLOR_RGB2GRAY)
        enhanced=Image.fromarray(cv2.createCLAHE(clipLimit=3.0,tileGridSize=(8,8)).apply(gray)).convert('RGB')
        second=self.ocr.analyze(png(enhanced));classified=self.clip.classify(png(image))
        detections=[]
        for mode,result in [('original',base),('clahe',second)]:
            detections += [{'text':d.text,'score':d.score,'polygon':d.polygon,'view':mode} for d in result.detections]
        result={'sha256':keyargs['image_hash'],'width':image.width,'height':image.height,
            'ocr_text':list(dict.fromkeys(d['text'] for d in detections)),'detections':detections,
            'text_coverage':max(base.text_coverage,second.text_coverage),'classification':{'label':classified.label,'confidence':classified.confidence,'scores':classified.scores},
            'paddleocr_actually_executed':True,'openclip_actually_executed':True,'enhanced_watermark_detection':{'executed':True,'method':'grayscale CLAHE clipLimit=3, 8x8 tiles + real PaddleOCR'},
            'visual_qa':'pending','executed_at':old.utcnow()}
        self.cache.store(key=key,**keyargs,result=result)
        return {**result,'cache_event':'CACHE_MISS','executed_this_call':True}

def contamination(analysis):
    bad=old.prohibited_text(analysis['ocr_text'])
    bad += [f'brand/identity: {t}' for t in analysis['ocr_text'] if any(b in t.lower() for b in BRANDS)]
    return list(dict.fromkeys(bad))

def parameter_card(analysis):
    text=' '.join(analysis['ocr_text']).lower()
    count=sum(k in text for k in ['material','dimensions','weight','packaging','产品信息','产品名称','产品材质','产品尺寸','装箱'])
    return count>=3 or ('product information' in text and count>=1)

def analyze_all(min_offer='',max_offer='~'):
    models=Models();paths=sorted((RUN/'offers').glob('*/image-inventory.json'))
    paths=[p for p in paths if min_offer<=p.parent.name<=max_offer]
    for n,path in enumerate(paths,1):
        inventory=read(path);offer=inventory['offer_id'];source=read(OUTPUT/offer/'original-product.json')
        auditpath=path.parent/'image-model-audit.json';previous=read(auditpath) if auditpath.exists() else {'records':[]}
        done={r['index']:r for r in previous['records']};records=[]
        for record in inventory['records']:
            prior=done.get(record['index'])
            if prior and prior.get('current_sha256')==record.get('current_sha256') and prior.get('rules_version')==models.version:
                records.append(prior);continue
            r=dict(record);r['rules_version']=models.version
            try:
                if not r.get('current_path'):raise RuntimeError('Current storefront image unavailable')
                analysis=models.analyze(r['current_path'],source);r['analysis']=analysis
                r['contamination']=contamination(analysis);r['parameter_card']=parameter_card(analysis)
                r['decision']='review';r['visual_qa']='pending'
                if r.get('provenance_failure'):r['decision']='provenance_fail'
                if r['parameter_card']:r['decision']='parameter_to_html_or_crop'
                elif r['contamination']:r['decision']='repair_or_reject'
                elif analysis['classification']['label'] in old.BLOCK_CLASSES:r['decision']='reject_non_product'
                if r.get('raw_path'):
                    r['quality']=old.current_quality(Path(r['current_path']),Path(r['raw_path']),'detail' if 'description' in r['roles'] else 'main')[0]
            except Exception as exc:r.update(decision='FAIL',error=type(exc).__name__,visual_qa='not_executed')
            records.append(r)
            save(auditpath,{'offer_id':offer,'product_id':inventory['product_id'],'rules_version':models.version,'records':records})
            print('AI',n,'/',len(paths),offer,r['index'],'/',len(inventory['records']),r['decision'],flush=True)
        save(auditpath,{'offer_id':offer,'product_id':inventory['product_id'],'rules_version':models.version,'records':records,'completed_at':old.utcnow()})

def mask_for(analysis,size):
    mask=Image.new('L',size,0);draw=ImageDraw.Draw(mask)
    for detection in analysis['detections']:
        if old.prohibited_text([detection['text']]) or any(b in detection['text'].lower() for b in BRANDS):
            points=np.asarray(detection['polygon'],dtype=int)
            x0,y0=points.min(axis=0)-6;x1,y1=points.max(axis=0)+6
            draw.rectangle((max(0,x0),max(0,y0),min(size[0]-1,x1),min(size[1]-1,y1)),fill=255)
    return mask

def confirmed_specs(analysis):
    # Conservative complete single-line facts; never publish dangling OCR numerals.
    result={}
    labels={'material':'Material','材质':'Material','dimensions':'Dimensions','尺寸':'Dimensions','weight':'Weight','重量':'Weight','packaging quantity':'Packaging Quantity','装箱数量':'Packaging Quantity'}
    for d in analysis['detections']:
        if d['score']<.90:continue
        text=d['text'].strip()
        for label,key in labels.items():
            match=re.fullmatch(re.escape(label)+r'\s*[:：]\s*(.+)',text,re.I)
            if not match:continue
            value=match.group(1).strip()
            materials={'塑料':'Plastic','锌合金':'Zinc alloy','铝合金':'Aluminum alloy','不锈钢':'Stainless steel','硅胶':'Silicone','玻璃':'Glass'}
            value=materials.get(value,value)
            valid=(key=='Material' and value.lower() in ['plastic','zinc alloy','aluminum alloy','stainless steel','silicone','glass','metal','wood'])
            valid |= key in ('Dimensions','Weight','Packaging Quantity') and bool(re.fullmatch(r'[\d.]+(?:\s*[x×*]\s*[\d.]+){0,2}\s*(?:mm|cm|g|kg|pcs|pieces)',value,re.I))
            if valid:result[key]={'value':value,'ocr_evidence':text,'confidence':d['score'],'polygon':d['polygon']}
    return result

def repair_record(record,source,folder,models):
    r=dict(record);r['spec_evidence']={};r['inpainting_executed']=False;r['rembg_executed']=False
    if r.get('provenance_failure') or not r.get('raw_path'):
        r.update(final_decision='reject',reason='Unproven source lineage; no cross-product substitution');return r
    if r.get('decision') in ('FAIL','reject_non_product'):
        r.update(final_decision='reject',reason=r.get('decision'));return r
    if r.get('parameter_card'):
        original=models.analyze(r['raw_path'],source)
        r['spec_evidence']=confirmed_specs(original)
        r.update(final_decision='reject',reason='Parameter card removed; only complete confirmed facts eligible for HTML',parameter_to_html=bool(r['spec_evidence']))
        return r
    if not r.get('contamination') and r.get('quality',{}).get('sharpness_quality_check')!='FAIL':
        with Image.open(r['current_path']) as im:already_webp=im.format=='WEBP'
        if already_webp:
            r.update(final_decision='candidate',final_path=r['current_path']);return r
    raw=ImageOps.exif_transpose(Image.open(r['raw_path'])).convert('RGB');analysis=models.analyze(r['raw_path'],source)
    if parameter_card(analysis):
        r.update(final_decision='reject',reason='Original parameter layout requires HTML rather than block inpainting',spec_evidence=confirmed_specs(analysis));return r
    if analysis['classification']['label'] in old.BLOCK_CLASSES:
        r.update(final_decision='reject',reason='Non-product original');return r
    pollution=contamination(analysis);master=raw;method='native_original_reencode'
    if pollution:
        mask=mask_for(analysis,raw.size)
        if not mask.getbbox():r.update(final_decision='reject',reason='No reliable repair mask');return r
        if models.rembg is None:models.rembg=RembgAdapter(ROOT/'models/rembg')
        cutout=models.rembg.cutout(png(raw));overlap=old.text_product_overlap(cutout,mask)
        r['product_overlap']=overlap;r['segmentation_actually_executed']=True
        if overlap['unsafe']:
            r.update(final_decision='reject',reason='Mark covers product core; cannot repair without changing genuine structure');return r
        mask_path=folder/'masks'/f"{r['index']:03d}.png";mask_path.parent.mkdir(exist_ok=True);mask.save(mask_path)
        r['mask_path']=str(mask_path)
        if analysis['text_coverage']>.07:
            master,details=models.rembg.on_neutral_square(png(raw),canvas_size=max(600,min(1200,max(raw.size))),background=(255,255,255))
            r['rembg_executed']=True;r['rembg_details']=details;method='rembg_neutral_background'
        else:
            if models.lama is None:models.lama=InpaintingAdapter(ROOT/'models/lama/lama_fp32.onnx')
            master=Image.open(BytesIO(models.lama.inpaint(png(raw),mask))).convert('RGB')
            r['inpainting_executed']=True;method='precise_mask_lama'
    destination=folder/'repaired'/f"{r['index']:03d}.webp";destination.parent.mkdir(exist_ok=True)
    masterpath=folder/'masters'/f"{r['index']:03d}.png";masterpath.parent.mkdir(exist_ok=True);master.save(masterpath)
    payload,quality=adaptive_quality_webp(master,source_dimensions=raw.size,source_filesize=Path(r['raw_path']).stat().st_size,max_edge=None,text_sensitive=False)
    destination.write_bytes(payload);final=models.analyze(destination,source)
    r.update(repair_method=method,optimization=quality,final_analysis=final,final_path=str(destination),visual_qa='pending')
    if contamination(final) or final['classification']['label'] in old.BLOCK_CLASSES:r.update(final_decision='reject',reason='Repair failed final enhanced OCR/classification')
    else:r['final_decision']='candidate'
    return r

def propose_all(models=None):
    models=models or Models()
    for path in sorted((RUN/'offers').glob('*/image-model-audit.json')):
        data=read(path)
        if not data.get('completed_at'):continue
        folder=path.parent;offer=data['offer_id'];source=read(OUTPUT/offer/'original-product.json')
        inventory=read(folder/'image-inventory.json')
        if (folder/'proposal.json').exists():continue
        records=[]
        for r in data['records']:
            try:records.append(repair_record(r,source,folder,models))
            except Exception as exc:records.append({**r,'final_decision':'reject','reason':'Repair model error: '+type(exc).__name__})
        candidates=[];duplicates=[]
        for r in records:
            if r.get('final_decision')!='candidate':continue
            finalpath=Path(r['final_path'])
            with Image.open(finalpath) as im:r['final_width'],r['final_height']=im.size
            r['final_phash']=phash(finalpath)
            # Minimum native detail width; a small image is not inflated into a fake HD image.
            if max(r['final_width'],r['final_height'])<500:r.update(final_decision='reject',reason='Insufficient useful native resolution');continue
            same=next((c for c in candidates if c.get('raw_sha256')==r.get('raw_sha256') or distance(c['final_phash'],r['final_phash'])<=5),None)
            if same:
                duplicates.append({'removed':r['index'],'kept':same['index'],'distance':distance(same['final_phash'],r['final_phash'])})
                r.update(final_decision='duplicate',duplicate_of=same['index']);continue
            candidates.append(r)
        top=[r for r in candidates if r.get('main_pool') and r['final_width']==r['final_height'] and r['final_width']>=600 and (r.get('final_analysis') or r['analysis'])['text_coverage']<.05]
        top.sort(key=lambda r:('featured' not in r['roles'],-r['final_width']*r['final_height']))
        top=top[:5]
        rest=[r for r in candidates if r not in top]
        rest.sort(key=lambda r:('description' not in r['roles'],'variation' in r['roles'],-r['final_width']*r['final_height']))
        details=rest[:10-len(top)]
        if not details and len(top)>1:details=[top.pop()]
        selected=top+details
        # Keep reliable existing variant images separately; any >10 needs per-variant audit justification.
        variants=[r for r in candidates if 'variation' in r['roles'] and r not in selected]
        plan={'offer_id':offer,'product_id':data['product_id'],'title':read(OUTPUT/offer/'processed-product.json')['title'],
              'records':records,'top':[r['index'] for r in top],'description':[r['index'] for r in details],
              'variation_extra':[r['index'] for r in variants],'duplicate_pairs':duplicates,
              'variant_exception_reason':'Existing distinct SKU/color image bindings preserved after QA' if len(selected+variants)>10 else None,
              'warnings':[],'failures':[],'visual_qa':'pending','created_at':old.utcnow()}
        if not top:plan['failures'].append('No clean square supplier-main candidate')
        if any(r.get('provenance_failure') for r in records if 'raw_main_candidate' not in r['roles']):plan['failures'].append('IMAGE_PROVENANCE_UNRESOLVED')
        if not details:plan['warnings'].append('insufficient_distinct_detail_material')
        save(folder/'proposal.json',plan)
        contact_sheet(plan,folder)
        print('Proposal ready',offer,len(top),'top',len(details),'detail',len(variants),'variant',len(plan['failures']),'FAIL',flush=True)

def contact_sheet(plan,folder):
    selected=set(plan['top']+plan['description']+plan['variation_extra'])
    images=[r for r in plan['records'] if r['index'] in selected]
    for page,start in enumerate(range(0,len(images),12),1):
        batch=images[start:start+12];canvas=Image.new('RGB',(1600,90+((len(batch)+3)//4)*440),'#eeeeee');draw=ImageDraw.Draw(canvas)
        draw.text((12,12),str(plan['offer_id'])+' '+plan['title'],fill='black')
        for n,r in enumerate(batch):
            im=Image.open(r['final_path']).convert('RGB');im.thumbnail((390,390))
            x=(n%4)*400+(400-im.width)//2;y=90+(n//4)*440
            canvas.paste(im,(x,y));role='TOP' if r['index'] in plan['top'] else 'DETAIL' if r['index'] in plan['description'] else 'VARIANT'
            draw.text(((n%4)*400+5,y+395),f"{r['index']} {role} raw {r.get('source_filename')} {r['final_width']}x{r['final_height']}",fill='black')
        canvas.save(folder/f'contact-{page}.jpg',quality=94)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=['prepare','analyze','propose']);parser.add_argument('--min-offer',default='');parser.add_argument('--max-offer',default='~');parser.add_argument('--watch',action='store_true');args=parser.parse_args()
    if args.stage=='prepare':prepare()
    elif args.stage=='analyze':analyze_all(args.min_offer,args.max_offer)
    else:
        models=Models()
        while True:
            propose_all(models)
            inventories=list((RUN/'offers').glob('*/image-inventory.json'))
            if not args.watch or all((p.parent/'proposal.json').exists() for p in inventories):break
            time.sleep(15)

if __name__=='__main__':main()
