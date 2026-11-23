"""TA full-period pipeline, preserving historical files and scientific defaults.

All outputs go to a new directory. Uses only the existing TA 45-degree LUT.
Clock policy 'audited' is a documented inference, not station log metadata.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import warnings
import platform

import numpy as np
import pandas as pd
import pvlib
import scipy
import xarray as xr

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from src.loader import load_gti_file
from src.clearsky import get_clear_sky_mask, count_clear_sky_minutes_around_max, estimate_omega_star
from src.estimator import AzimuthEstimator
from src.config import get_station_config

START, END = '2015-09-05', '2018-10-10'
LAT, LON = -31.74, -55.98
TILT = 45.0
TZ = 'America/Montevideo'
CONVENTION = 'SWC2021: north=0; east negative; west positive'
PARAMETERS = dict(start=START, end=END, window_minutes=120, clear_min_exclusive=110,
                  discard=True, max_discard_passes=3, eot_method='spencer',
                  lut_reference_year=2026, albedo=0.2, model='perez-driesse',
                  tilt=TILT,
                  tilt_basis='user-reported independent measured/modelled GTI '
                             'comparison: minimum nRMSD near 45 deg for both channels',
                  tie_break='last', transition_dates=['2016-09-27', '2017-05-12'])


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def period(date, clock_policy='audited'):
    date = pd.Timestamp(date).date().isoformat()
    if date < START or date > END:
        raise ValueError('outside_requested_period')
    if date in PARAMETERS['transition_dates']:
        raise ValueError('channel_transition' if date == '2016-09-27' else 'clock_transition')
    column = 'GTI30_AV (W/m2)' if date < '2016-09-27' else 'GTI45_AV (W/m2)'
    source_tz = 'Etc/GMT+3' if clock_policy == 'audited' and date > '2017-05-12' else 'UTC'
    return TILT, column, source_tz


def lookup_doy(date):
    """Match month/day, never raw leap-year DOY; Feb 29 explicitly interpolated."""
    date = pd.Timestamp(date)
    if date.month == 2 and date.day == 29:
        return (59, 60)
    return (pd.Timestamp(year=2026, month=date.month, day=date.day).dayofyear,)


def uniform_minutes(index):
    # pandas may store datetime indexes in microseconds or nanoseconds.
    return len(index) >= 2 and bool(((index[1:] - index[:-1]) == pd.Timedelta(minutes=1)).all())


def estimate_date(estimator, omega_star, date):
    days = lookup_doy(date)
    if len(days) == 1:
        return estimator.estimate(omega_star, days[0], tie_break='last'), 'month_day_2026'
    # Preserve all samples and both source curves; only this absent calendar day
    # gets a midpoint curve. Not used to alter March-December on leap years.
    values = estimator.ds.omega_star.sel(doy=list(days)).mean('doy').to_numpy()
    distances = np.abs(values - omega_star)
    idx = len(values) - 1 - np.argmin(distances[::-1])
    return float(estimator.ds.azimuth.values[idx]), 'feb29_midpoint_omega_curve'


def lut_day(tilt, doy, azimuths):
    """Synthetic control: same minute-grid geometry/model as historical TA LUT."""
    site = pvlib.location.Location(LAT, LON, tz=TZ)
    start = pd.Timestamp('2026-01-01', tz=TZ) + pd.Timedelta(days=int(doy)-1)
    times = pd.date_range(start, periods=1440, freq='min')
    sp = site.get_solarposition(times)
    cs = site.get_clearsky(times)
    zen = sp.zenith.to_numpy()[:, None]
    poa = pvlib.irradiance.get_total_irradiance(
        surface_tilt=tilt, surface_azimuth=(-azimuths[None, :]) % 360,
        solar_zenith=zen, solar_azimuth=sp.azimuth.to_numpy()[:, None],
        dni=cs.dni.to_numpy()[:, None], ghi=cs.ghi.to_numpy()[:, None],
        dhi=cs.dhi.to_numpy()[:, None],
        airmass=pvlib.atmosphere.get_relative_airmass(zen),
        albedo=0.2, dni_extra=pvlib.irradiance.get_extra_radiation(doy),
        model='perez-driesse')['poa_global']
    omega = np.asarray(pvlib.solarposition.hour_angle(times, LON, sp.equation_of_time))
    return omega[np.argmax(poa, axis=0)]


def build_lut30(out, lut45):
    azimuths = lut45.ds.azimuth.to_numpy()
    # Verify full angular curves, spanning all seasons, before building tilt 30.
    controls = []
    for day in [1, 59, 80, 127, 172, 266, 355]:
        generated = lut_day(45, day, azimuths)
        reference = lut45.ds.omega_star.sel(doy=day).to_numpy()
        error = float(np.max(np.abs(generated-reference)))
        controls.append(dict(doy=day,tilt=45,max_delta_omega_deg=error))
        np.testing.assert_allclose(generated, reference, rtol=0, atol=1e-10)
    pd.DataFrame(controls).to_csv(out/'synthetic_lut_equivalence.csv',index=False)
    values = []
    for doy in range(1,366):
        values.append(lut_day(30,doy,azimuths))
        if doy%50==0: print('LUT30 day',doy,flush=True)
    ds=xr.Dataset({'omega_star':(('azimuth','doy'),np.array(values).T)},
                  coords={'azimuth':azimuths,'doy':np.arange(1,366)})
    ds.attrs.update(station='TA',surface_tilt=30.,latitude=LAT,longitude=LON,
                    timezone=TZ,reference_year=2026,albedo=0.2,model='Perez-Driesse',
                    temporal_resolution_seconds=60,azimuth_step=0.1,
                    azimuth_convention=CONVENTION,maximum_method='1min argmax',
                    tie_break='last in ascending SWC2021 coordinates',
                    geometry_control_sha256=lut45.lookup_sha256)
    path=out/'lookup_TA_tilt30_swc2021.nc';ds.to_netcdf(path)
    return path


def provenance():
    sources=[*list((ROOT/'src').glob('*.py')),*list(Path(__file__).parent.glob('*.py')),
             ROOT/'main.py',ROOT/'analysis/generate_daily_screening_TA.py']
    return dict(commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
                branch=subprocess.check_output(['git','branch','--show-current'],cwd=ROOT,text=True).strip(),
                git_status=subprocess.check_output(['git','status','--short'],cwd=ROOT,text=True),
                command=[sys.executable,*sys.argv],python=platform.python_version(),
                versions={m.__name__:m.__version__ for m in [np,pd,pvlib,scipy,xr]},
                code_sha256={str(p.relative_to(ROOT)):sha(p) for p in sources},parameters=PARAMETERS)


def legacy_equivalence(estimator, out):
    old_path=ROOT/'outputs/TA/results/azimuth_results_20261103_204427_swc2021.csv'
    diag_path=ROOT/'outputs/TA/results/azimuth_diagnostics_20261103_204427.csv'
    old=pd.read_csv(old_path);diag=pd.read_csv(diag_path).set_index('date');rows=[]
    for r in old.itertuples():
        p=next((ROOT/'data/TA').rglob(diag.loc[r.date,'file']))
        f=load_gti_file(p,'TA');fit=estimate_omega_star(f,120,LON,True,3)
        gamma,_=estimate_date(estimator,fit['omega_star'],r.date)
        row=dict(date=r.date,delta_omega=fit['omega_star']-r.omega_star,
                 delta_gamma=gamma-r.azimuth,delta_discarded_pct=fit['discarded_pct']-r.discarded_pct)
        np.testing.assert_allclose(list(row.values())[1:],[0,0,0],atol=1e-10,rtol=0)
        assert fit['discard_passes']==r.discard_passes
        assert fit['discard_stop_reason']==r.discard_stop_reason
        rows.append(row)
    pd.DataFrame(rows).to_csv(out/'legacy_equivalence.csv',index=False)
    return {str(p.relative_to(ROOT)):sha(p) for p in [old_path,diag_path]}


def row_ledger(raw, df, source_tz, column, reason, fit=None, clear=None):
    times=pd.to_datetime(raw.Timestamp).dt.floor('min').dt.tz_localize(source_tz).dt.tz_convert(TZ)
    ledger=pd.DataFrame(dict(row_id=np.arange(len(raw)),csv_line=np.arange(len(raw))+2,
                            timestamp_raw=raw.Timestamp,timestamp=times.astype(str),
                            source_tz=source_tz,gti_column=column,
                            ghi_raw=raw['GHI1_AV (W/m2)'],gti_raw=raw[column],reason=reason))
    if clear is not None:
        mask=pd.Series(np.asarray(clear),index=df.index)
        ledger['clear_sky']=mask.reindex(pd.DatetimeIndex(times)).to_numpy()
    if fit is not None:
        tmax=df.gti.idxmax();window=(times>tmax-pd.Timedelta(minutes=60))&(times<=tmax+pd.Timedelta(minutes=60))
        ledger.loc[~window,'reason']='outside_fit_window'
        ledger.loc[window,'reason']='nonfinite_fit_input'
        ledger.loc[times.isin(fit['times']),'reason']='fit_kept'
        ledger.loc[times.isin(fit['times_discarded']),'reason']='fit_2sigma_discarded'
    return ledger


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--audit',type=Path,required=True,help='Completed audit_inputs.py output')
    ap.add_argument('--clock-policy',choices=['audited','utc'],default='audited')
    args=ap.parse_args();out=args.out.resolve();out.mkdir(parents=True,exist_ok=False)
    (out/'rows').mkdir()
    manifest=provenance();manifest['clock_policy']=args.clock_policy
    manifest['clock_evidence']='inferred from GHI solar timing; transition day excluded; no logbook confirmation'
    manifest['audit_manifest_sha256']=sha(args.audit/'manifest.json')
    manifest['audit_inventory_sha256']=sha(args.audit/'inventory.csv')
    manifest['audit_clock_hypotheses_sha256']=sha(args.audit/'clock_hypotheses.csv')
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2))
    (out/'working_tree.patch').write_text(subprocess.check_output(['git','diff'],cwd=ROOT,text=True))
    cfg=get_station_config('TA')
    est45=AzimuthEstimator(LAT,LON,TILT,ROOT/cfg['lookup_table'],station='TA',expected_sha256=cfg['lookup_sha256'])
    if est45.ds.attrs.get('azimuth_convention') != CONVENTION:raise ValueError('Wrong LUT sign convention')
    manifest['legacy_sources']=legacy_equivalence(est45,out)
    estimators={TILT:est45}
    manifest['luts']={str(k):dict(path=str(e.lookup_table),sha256=e.lookup_sha256,attrs=e.ds.attrs) for k,e in estimators.items()}
    inventory=pd.read_csv(args.audit/'inventory.csv',keep_default_na=False)
    audit_clock=pd.read_csv(args.audit/'clock_hypotheses.csv').set_index(['file','source_tz'])
    manifest['data_sha256']=dict(zip(inventory.file,inventory.sha256))
    screening=[];results=[];seen_dates=set()
    for i,entry in enumerate(inventory.itertuples()):
        p=ROOT/entry.file
        if sha(p)!=entry.sha256:raise RuntimeError(f'Input changed after audit: {p}')
        raw_date=pd.Timestamp(entry.raw_min).date().isoformat()
        r=dict(file=entry.file,source_sha256=entry.sha256,raw_date=raw_date,
               status='',candidate=False,clock_policy=args.clock_policy)
        try: tilt,column,source_tz=period(raw_date,args.clock_policy)
        except ValueError as e:
            r['status']=str(e);screening.append(r);continue
        seen_dates.add(raw_date)
        r.update(tilt=tilt,gti_column=column,source_tz=source_tz)
        raw=pd.read_csv(p)
        if column not in raw:
            r['status']='missing_expected_gti_channel';screening.append(r);continue
        df=load_gti_file(p,'TA',gti_col=column,source_tz=source_tz)
        fit=None;mask=None
        try:
            if df.index.has_duplicates:raise ValueError('duplicate_minutes')
            if not uniform_minutes(df.index):
                raise ValueError('nonuniform_minute_cadence')
            if not np.isfinite(df.gti.to_numpy()).any():raise ValueError('no_finite_gti')
            tmax=df.gti.idxmax();date=tmax.date().isoformat();r.update(date=date,gti_max_time=str(tmax))
            if not START<=date<=END:raise ValueError('maximum_outside_requested_period')
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter('always')
                mask,_=get_clear_sky_mask(df,LAT,LON,TZ)
            r['warnings']='; '.join(str(w.message) for w in caught)
            count=int(count_clear_sky_minutes_around_max(df.gti,mask,120))
            r.update(clear_minutes=count,candidate=count>110,passes_90pct=count>108)
            # Same data and source clock must yield the diagnostic screening count.
            reference=audit_clock.loc[(entry.file,source_tz),'clear_minutes']
            if count!=reference:raise RuntimeError(f'Audit screening mismatch for {entry.file}')
            r['clear_minutes_utc_control']=audit_clock.loc[(entry.file,'UTC'),'clear_minutes']
            r['status']='screening_rejected'
            if count>110:
                fit=estimate_omega_star(df,120,LON,True,3,latitude=LAT,eot_method='spencer')
                gamma,mapping=estimate_date(estimators[tilt],fit['omega_star'],date)
                r['status']='estimated'
                res=dict(station='TA',date=date,doy=tmax.dayofyear,tilt=tilt,
                         gti_column=column,
                         file=entry.file,source_sha256=entry.sha256,source_tz=source_tz,
                         clock_policy=args.clock_policy,gti_max_time=str(tmax),
                         azimuth=gamma,azimuth_convention=CONVENTION,lookup_mapping=mapping,
                         lookup_doy='|'.join(map(str,lookup_doy(date))),
                         lut_sha256=estimators[tilt].lookup_sha256,tie_break='last',
                         clear_minutes=count,eot_method='spencer')
                for key in ['omega_star','discarded_pct','n_window','n_nonfinite','n_discarded',
                            'discard_passes','discard_stop_reason','gti_star']:
                    res[key]=fit[key]
                res.update(zip(['coef_a','coef_b','coef_c'],fit['coef']))
                results.append(res)
        except ValueError as e:r['status']='rejected: '+str(e)
        r['row_ledger']='rows/'+p.stem+'.csv.gz'
        ledger=row_ledger(raw,df,source_tz,column,r['status'],fit,mask)
        ledger.to_csv(out/r['row_ledger'],index=False,compression='gzip')
        screening.append(r)
        if i%100==0:print('Measured input',i,raw_date,'estimates',len(results),flush=True)
    for date in pd.date_range(START,END).strftime('%Y-%m-%d'):
        if date not in seen_dates and date not in PARAMETERS['transition_dates']:
            screening.append(dict(raw_date=date,status='missing_input_date',candidate=False,clock_policy=args.clock_policy))
    screen=pd.DataFrame(screening);screen.to_csv(out/'screening.csv',index=False)
    if not results:
        raise RuntimeError('No valid estimates; inspect screening.csv. Run remains incomplete.')
    result=pd.DataFrame(results).sort_values(['date','file']);result.to_csv(out/'azimuth_results.csv',index=False)
    if result.date.duplicated().any():raise RuntimeError('Multiple estimates on one local day; review before aggregation')
    result['year']=result.date.str[:4]
    summaries=[]
    for keys in [['tilt'],['year','tilt'],['tilt','source_tz']]:
        for group,f in result.groupby(keys):
            summaries.append(dict(grouping='|'.join(keys),**dict(zip(keys,group if isinstance(group,tuple) else [group])),
                                  n=len(f),first=f.date.min(),last=f.date.max(),
                                  azimuth_mean=f.azimuth.mean(),azimuth_sd=f.azimuth.std(ddof=1),
                                  omega_mean=f.omega_star.mean(),azimuth_min=f.azimuth.min(),azimuth_max=f.azimuth.max()))
    pd.DataFrame(summaries).to_csv(out/'summary_by_period.csv',index=False)
    # Isolated diagnostic: preserve the previous channel-period populations.
    sensitivity=[]
    for (tilt,column),f in result.groupby(['tilt','gti_column']):
        keep=np.ones(len(f),dtype=bool);passes=np.zeros(len(f),dtype=int);iteration=0
        while keep.sum()>2:
            x=f.azimuth.to_numpy()[keep];mu=x.mean();sd=x.std(ddof=1)
            reject=keep & (np.abs(f.azimuth.to_numpy()-mu)>2*sd)
            if not reject.any():break
            iteration+=1;passes[reject]=iteration;keep[reject]=False
        for j,row in enumerate(f.itertuples()):
            sensitivity.append(dict(date=row.date,tilt=tilt,gti_column=column,azimuth=row.azimuth,
                                    retained=bool(keep[j]),rejection_iteration=int(passes[j])))
    pd.DataFrame(sensitivity).to_csv(out/'sensitivity_between_day_2sigma.csv',index=False)
    protected=json.loads((args.audit/'protected_sha256.json').read_text())
    changed=[p for p,h in protected.items() if not (ROOT/p).is_file() or sha(ROOT/p)!=h]
    manifest['protected_files_checked']=len(protected);manifest['protected_files_changed']=changed
    if changed:raise RuntimeError(f'Historical files changed: {changed}')
    manifest['complete']=True
    manifest['outputs_sha256']={str(p.relative_to(out)):sha(p) for p in out.rglob('*') if p.is_file() and p.name!='manifest.json'}
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2,default=lambda o:o.item() if isinstance(o,np.generic) else str(o)))
    print(pd.DataFrame(summaries).to_string(index=False));print('Results:',out,flush=True)

if __name__=='__main__':main()
