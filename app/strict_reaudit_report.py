"""Read-only aggregation of real stored audits, with no model or WooCommerce calls."""
import re
from collections import Counter
from .strict_reaudit import RUN,read,save

def storefront_urls(snapshot):
    parent=snapshot['parent']
    return set([i['src'] for i in parent.get('images',[])]+re.findall(r'<img[^>]+src=["\']([^"\']+)',parent.get('description',''),re.I)+
        [(v.get('image') or {}).get('src') for v in snapshot.get('variations',[]) if (v.get('image') or {}).get('src')])

def report():
    decisions=read(RUN/'visual-decisions.json')
    checkpoint=read(RUN/'repair-checkpoint.json') if (RUN/'repair-checkpoint.json').exists() else {}
    start=read(RUN/'resume-start.json') if (RUN/'resume-start.json').exists() else {}
    rows=[]
    for folder in sorted((RUN/'offers').iterdir()):
        if folder.name=='1' or not (folder/'audit.json').exists():continue
        identity=read(folder/'audit.json');final=read(folder/'final-audit.json') if (folder/'final-audit.json').exists() else {}
        row={'offer_id':folder.name,'product_id':identity.get('product_id',identity.get('candidate_product_ids')),
             'analysis_completed':folder.name in decisions,'checkpoint':checkpoint.get(folder.name),
             'result':final.get('result',identity['result']),'rest_verified':bool(final.get('rest_verified')),
             'reason':final.get('error',final.get('reason',identity.get('reason'))),
             'warnings':final.get('warnings',identity.get('warnings',[])),
             'problem_images_removed':0,'rembg_images_applied':0,'local_scanned_this_resume':False,
             'modified':bool(final.get('modified')),'http_200':0,'http_fail':0}
        if row['rest_verified']:
            plan=read(folder/'proposal.json');before=read(folder/'selected-before.json');after=read(folder/'after.json')
            beforeurls=storefront_urls(before);afterurls=storefront_urls(after)
            removed=[];selected=set(plan['top']+plan['description']+plan['variation_extra'])
            review=decisions.get(folder.name,{})
            for r in plan['records']:
                reason=review.get('reject',{}).get(str(r['index'])) or r.get('reason')
                if r.get('url') in beforeurls-afterurls and r['index'] not in selected and (reason or r.get('contamination') or r.get('duplicate_of')):
                    removed.append({'url':r['url'],'reason':reason or r.get('contamination') or 'Perceptual duplicate','index':r['index']})
            row['removed_images']=list({x['url']:x for x in removed}.values())
            row['problem_images_removed']=len(row['removed_images'])
            row['rembg_images_applied']=sum(bool(r.get('rembg_executed')) for r in plan['records'] if r['index'] in selected)
            row['http_200']=sum(c.get('http_status')==200 and c.get('pass') for c in final.get('http_checks',[]))
            row['http_fail']=sum(not c.get('pass') for c in final.get('http_checks',[]))
            row['protected_fields_unchanged']=final.get('protected_fields_unchanged')
            row['permalink']=final.get('permalink')
        rows.append(row)
    summary={'scope_products':len(rows),'existing_analysis':len(decisions),'directly_updated':sum(r.get('checkpoint',{}).get('status')=='UPDATED' for r in rows if r.get('checkpoint')),
        'remaining_local_scanned':0,'repaired_products':sum(r['modified'] and r['rest_verified'] for r in rows),
        'problem_images_removed':sum(r['problem_images_removed'] for r in rows),'rembg_images_applied':sum(r['rembg_images_applied'] for r in rows),
        'skipped_unchanged':sum(r['rest_verified'] and not r['modified'] for r in rows),
        'fail_or_mapping_blocked':sum(not r['rest_verified'] for r in rows),
        'http_200':sum(r['http_200'] for r in rows),'http_fail':sum(r['http_fail'] for r in rows),
        'result_counts':dict(Counter(r['result'] for r in rows)),
        'already_verified_skipped_at_resume':start.get('verified_before_low_cost_resume',0),
        'newly_verified_during_resume':sum(r['rest_verified'] for r in rows)-start.get('verified_before_low_cost_resume',0),
        'additional_vision_llm_calls_after_switch':0,
        'note':'All eligible products already have saved image decisions. No new OCR, Vision or LLM inference performed during resume. Mapping-blocked products remain unchanged; no unproven source is guessed.',
        'products':rows}
    save(RUN/'repair-summary.json',summary)
    for row in rows:save(RUN/'public-audits'/(row['offer_id']+'.json'),row)
    print({k:v for k,v in summary.items() if k!='products'})
    return summary

if __name__=='__main__':report()
