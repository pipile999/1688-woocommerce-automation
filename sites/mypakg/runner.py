"""Fixed production entry; --dry-run alone checks isolation without any products."""
import argparse, json, sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
sys.path.insert(0,'D:/codex/tools/site-runner-libs')
from app.site_guard import preflight

def main():
    try:
        result=preflight()
        if sys.argv[1:]==['--dry-run']:
            print(json.dumps(result,ensure_ascii=False,indent=2)); return 0
        if len(sys.argv)==1:
            import tkinter as tk
            from tkinter.filedialog import askopenfilename
            root=tk.Tk(); root.withdraw()
            selected=askopenfilename(title=result['site']+' — select product input',filetypes=[('Product list','*.xlsx *.json')])
            root.destroy()
            if not selected:return 0
            sys.argv.append(selected)
        from app.auto_import_runner import main as run
        return run()
    except ValueError as exc:
        print(str(exc) if str(exc).startswith('HARD STOP:') else 'HARD STOP: INVALID_INPUT'); return 2
    except Exception:
        print('HARD STOP: RUNTIME_ERROR; no credential details logged'); return 2

if __name__=='__main__': raise SystemExit(main())
