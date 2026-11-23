"""Read-only TA inventory and clock hypothesis audit. Outputs require a new directory."""
from pathlib import Path
import sys, json, hashlib, subprocess, warnings, argparse
import numpy as np
import pandas as pd
import pvlib
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from src.clearsky import get_clear_sky_mask, count_clear_sky_minutes_around_max


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--out',type=Path,required=True); args=ap.parse_args()
    args.out.mkdir(parents=True,exist_ok=False)
    rows=[]; clocks=[]
    for i,p in enumerate(sorted((ROOT/'data/TA').rglob('*.csv'))):
        d=pd.read_csv(p); raw=pd.to_datetime(d.Timestamp,errors='coerce'); t=raw.dt.floor('min')
        cols=[c for c in d if c.startswith('GTI') and '_AV' in c]
        row=dict(file=str(p.relative_to(ROOT)),sha256=sha(p),rows=len(d),raw_min=str(raw.min()),raw_max=str(raw.max()),tz_codes='|'.join(map(str,d.TZ.unique())),gti_columns='|'.join(cols),invalid_time=int(t.isna().sum()),duplicate_minutes=int(t.duplicated().sum()),unsorted=not t.is_monotonic_increasing)
        rows.append(row)
        if not cols or t.min()<pd.Timestamp('2015-09-04') or t.max()>pd.Timestamp('2018-10-12'):continue
        df=pd.DataFrame({'ghi':pd.to_numeric(d['GHI1_AV (W/m2)'],errors='coerce'),'gti':pd.to_numeric(d[cols[0]],errors='coerce')})
        for source_tz in ['UTC','Etc/GMT+3']:
            f=df.copy();f.index=pd.DatetimeIndex(t).tz_localize(source_tz).tz_convert('America/Montevideo');f=f.sort_index()
            r=dict(file=row['file'],source_tz=source_tz,raw_date=str(t.min().date()))
            try:
                with warnings.catch_warnings(record=True) as w:
                    warnings.simplefilter('always');m,c=get_clear_sky_mask(f,-31.74,-55.98,'America/Montevideo')
                day=c>50; x=c[day].to_numpy();y=f.ghi[day].to_numpy();ok=np.isfinite(x)&np.isfinite(y)
                r.update(clear_minutes=int(count_clear_sky_minutes_around_max(f.gti,m,120)),clear_total=int(m.sum()),ghi_correlation=float(np.corrcoef(x[ok],y[ok])[0,1]),gti_max_time=str(f.gti.idxmax()),warnings='; '.join(str(a.message) for a in w))
            except Exception as e:r['error']=str(e)
            clocks.append(r)
        if i%100==0:print(i,p.name,flush=True)
    pd.DataFrame(rows).to_csv(args.out/'inventory.csv',index=False)
    pd.DataFrame(clocks).to_csv(args.out/'clock_hypotheses.csv',index=False)
    protected={str(p.relative_to(ROOT)):sha(p) for directory in ['outputs/TA','lookup','MANUSCRIPT','FIG','FIG '] for p in (ROOT/directory).rglob('*') if p.is_file()}
    (args.out/'protected_sha256.json').write_text(json.dumps(protected,indent=2))
    (args.out/'manifest.json').write_text(json.dumps(dict(commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),status=subprocess.check_output(['git','status','--short'],cwd=ROOT,text=True),command=sys.argv,versions={m.__name__:m.__version__ for m in [pd,np,pvlib]},code={str(p.relative_to(ROOT)):sha(p) for p in [Path(__file__),*list((ROOT/'src').glob('*.py'))]},source_documents={str(p.relative_to(ROOT)):sha(p) for p in (ROOT/'docs').glob('*.pdf')}),indent=2))
    print('Completed',len(rows),len(clocks),flush=True)
if __name__=='__main__':main()
