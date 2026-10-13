"""## Executive summary (read this first)
Run every public practice unit through VNext and the official admissibility gates.
No realized values or organizer scales are loaded. A pass is structural only.
"""
import argparse
import contextlib
import io
import json
import os
import pathlib
import time
import tomllib
import traceback

import pandas as pd
from qfbench2_track_forecasting.scoring import GATES,hydrate_ctx
from vnext.cli import main,corpus


def run_gates(unit,out):
    ctx={'unit_dir':unit,'output_dir':out,'realized':None}
    hydrate_ctx(ctx)
    results={}
    for name,gate in GATES:
        result=gate(ctx);results[name]=result.passed
        if not result.passed:break
    return results


def main_validator():
    ap=argparse.ArgumentParser()
    ap.add_argument('--units',default='/repo/V11/units')
    ap.add_argument('--out',default='/lab/results/gates01')
    ap.add_argument('--draws',type=int,default=2000)
    ap.add_argument('--mode',default='price')
    args=ap.parse_args()
    out=pathlib.Path(args.out);out.mkdir(parents=True,exist_ok=False)
    rows=[];start=time.monotonic();family_examples={}
    for key in ('MODEL_ENDPOINT','MODEL_NAME','V11_MOCK_HOUSE_JSON','V8_MOCK_HOUSE_JSON'):
        os.environ.pop(key,None)
    for unit in sorted(pathlib.Path(args.units).iterdir()):
        if not (unit/'forecast_spec.json').is_file():continue
        card=tomllib.loads((unit/'card.toml').read_text());family=card['metadata']['category']
        asof=str(card['provenance']['data_cutoff']);dest=out/'outputs'/unit.name
        command=['--panels',str(unit/'panels'),'--text',str(unit/'text'),'--asof',asof,
                 '--card',str(unit/'card.toml'),'--out',str(dest/'forecast.parquet'),
                 '--n-draws',str(args.draws),'--mode',args.mode,'--text-policy','off']
        error='';gates={};t=time.monotonic()
        try:
            with contextlib.redirect_stdout(io.StringIO()):main(command)
            gates=run_gates(unit,dest)
            meta=json.loads((dest/'forecast_meta.json').read_text())
            ok=len(gates)==4 and all(gates.values())
            if ok and family not in family_examples:family_examples[family]=(unit,command)
        except Exception as exc:
            ok=False;error=f'{type(exc).__name__}: {exc}'
        rows.append({'unit':unit.name,'family':family,'ok':ok,'seconds':time.monotonic()-t,
                     'error':error,**gates})
        pd.DataFrame(rows).to_csv(out/'gates.csv',index=False)
        print(f'{len(rows):3d} {unit.name:42s} {"PASS" if ok else "FAIL"} {error}',flush=True)
    mocks=[]
    for family,(unit,cmd) in family_examples.items():
        card=tomllib.loads((unit/'card.toml').read_text());asof=str(card['provenance']['data_cutoff'])
        docs,_=corpus(unit/'text',asof)
        if not docs:raise AssertionError('mock example has no documents')
        assets=card['targets']['asset_ids']
        mock={'state':{'label':'transition','confidence':.8},'scenarios':[{'name':'mock','prob':1.,
              'assets':{a:{'shift_sd':.3,'vol_scale':1.15,'because':docs[0]['doc_id']} for a in assets}}]}
        os.environ['V11_MOCK_HOUSE_JSON']=json.dumps(mock)
        dest=out/'mock_outputs'/family
        mockcmd=cmd.copy()
        mockcmd[mockcmd.index('--out')+1]=str(dest/'forecast.parquet')
        mockcmd[mockcmd.index('--text-policy')+1]='guarded'
        with contextlib.redirect_stdout(io.StringIO()):main(mockcmd)
        gates=run_gates(unit,dest)
        m=json.loads((dest/'forecast_meta.json').read_text())
        before=pd.read_parquet(out/'outputs'/unit.name/'forecast.parquet')['value']
        after=pd.read_parquet(dest/'forecast.parquet')['value']
        changed=not before.equals(after)
        mocks.append({'family':family,'ok':all(gates.values()) and m['reasoning_applied'] and changed})
        os.environ.pop('V11_MOCK_HOUSE_JSON',None)
    result={'units':len(rows),'passed':sum(r['ok'] for r in rows),'mocks':mocks,
            'draws':args.draws,'seconds':time.monotonic()-start,'scored':False,
            'meaning':'official admissibility gates only; mock text is not a real House test'}
    (out/'summary.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(result,indent=2),flush=True)
    return 0 if all(r['ok'] for r in rows) and all(r['ok'] for r in mocks) else 1

if __name__=='__main__':raise SystemExit(main_validator())
