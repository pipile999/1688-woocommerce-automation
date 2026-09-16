"""Persist actual agent visual-review decisions; never auto-approve model-only results."""
from pathlib import Path
from .strict_reaudit import RUN,read,save
from .strict_reaudit_images import sha,contact_sheet
from . import batch50_upload_publish as u

def main():
    decisions=read(RUN/'visual-decisions.json')
    for offer,review in decisions.items():
        folder=RUN/'offers'/offer;path=folder/'proposal.json'
        plan=read(path)
        if (folder/'final-audit.json').exists() and read(folder/'final-audit.json').get('rest_verified'):continue
        if review.get('block'):
            plan.update(visual_qa='FAIL',visual_review_note=review['block'])
            plan['failures'].append(review['block'])
            save(path,plan)
            save(folder/'final-audit.json',{'offer_id':offer,'product_id':plan['product_id'],'modified':False,'rest_verified':False,
                 'result':'WARNING_IMAGE_MISMATCH' if 'MISMATCH' in review['block'] else 'FAIL','reason':review['block'],'stopped_product_only':True,'reviewed_at':u.utcnow()})
            continue
        top=review['top'];detail=review['description'];variants=review.get('variation_extra',[])
        selected=set(top+detail+variants)
        records={r['index']:r for r in plan['records']}
        assert selected<=records.keys() and not (set(top)&set(detail))
        for index,r in records.items():
            if index in selected:
                assert r['final_decision']=='candidate'
                r.update(visual_qa='PASS',visual_review_sha256=sha(r['final_path']),product_visual_consistency='PASS',
                         visual_review_method='Agent inspected actual rendered image/contact sheet; product matches source evidence and title',reviewed_at=u.utcnow())
            if str(index) in review.get('reject',{}):
                r.update(visual_qa='FAIL',final_decision='reject',reason=review['reject'][str(index)])
        plan.update(top=top,description=detail,variation_extra=variants,visual_qa='PASS',visual_review_note=review['note'])
        if top and 'No clean square supplier-main candidate' in plan['failures']:plan['failures'].remove('No clean square supplier-main candidate')
        save(path,plan);contact_sheet(plan,folder)
        print('Actual visual review saved',offer,flush=True)

if __name__=='__main__':main()
