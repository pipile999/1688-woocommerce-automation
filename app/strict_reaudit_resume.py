"""Apply existing decisions only. No model imports/inference, no image regeneration."""
import contextlib
from .strict_reaudit import RUN,ROOT,read,save
from .strict_reaudit_apply import apply_one,checkpoint,CHECKPOINT
from .strict_reaudit_sync import sync_one
from . import batch50_upload_publish as u

def main():
    decisions=read(RUN/'visual-decisions.json')
    # Recover durable successful writes before any network activity.
    for path in (RUN/'offers').glob('*/final-audit.json'):
        result=read(path)
        if result.get('rest_verified'):checkpoint(result)
    u.load_dotenv(ROOT/'.env');client=u.WooCommerceClient()
    done=0
    with (RUN/'resume-execution.log').open('a',encoding='utf-8') as log:
        for offer,decision in sorted(decisions.items()):
            folder=RUN/'offers'/offer
            if read(CHECKPOINT).get(offer,{}).get('status') in ('UPDATED','SKIPPED'):continue
            if decision.get('block'):continue
            plan=read(folder/'proposal.json')
            if plan.get('visual_qa')!='PASS' or plan.get('failures'):continue
            with contextlib.redirect_stdout(log):apply_one(client,folder/'proposal.json')
            log.flush()
            try:sync_one(folder)
            except Exception as exc:print('Local artifact sync warning',offer,type(exc).__name__,flush=True)
            done+=1
            if done%20==0:print('Checkpoint progress:',done,'remaining products attempted;',len(read(CHECKPOINT)),'verified total',flush=True)
    print('Existing decisions applied; verified checkpoint records:',len(read(CHECKPOINT)),flush=True)

if __name__=='__main__':main()
