"""## Executive summary (read this first)
Give House truthful observed anchors, volatility ratios and baseline forecast summaries.
This corrects information plumbing; real House accuracy remains untested.
"""
import numpy as np
import pandas as pd
from qfbench2_track_forecasting.cli import _series,_monthly_series,_diff_without_gaps
from qfbench2_track_forecasting.targets import log_return_steps

def numerical_context(panels,assets,asof,target,monthly,steps,base,horizons):
    anchors={};stats={};details={};changes={}
    for ai,a in enumerate(assets):
        raw=_series(panels,a,asof).astype(float).sort_index()
        s=_monthly_series(raw) if monthly else raw
        if target=='log_return':ds=pd.Series(log_return_steps(s),index=s.index)
        elif monthly:ds=s.diff().where(np.r_[False,np.diff(s.index.asi8)==1])
        else:ds=_diff_without_gaps(s)
        ds=ds.dropna();recent=ds.iloc[-(12 if monthly else 252):]
        fullsd=float(ds.std(ddof=1));recent_sd=float(recent.std(ddof=1))
        anchors[a]=0. if target=='log_return' else float(raw.iloc[-1])
        longest=int(np.argmax(steps[ai]))
        stats[a]={'horizon_sd':float(base[:,longest,ai].std(ddof=1)),
                  'daily_sd_full':max(fullsd,1e-12),'daily_sd_recent':max(recent_sd,1e-12)}
        details[a]={'last_observation_date':str(raw.index[-1])[:10],'last_observed_value':float(raw.iloc[-1]),
                    'last_usable_change_label':str(ds.index[-1])[:10],
                    'recent_window_semantics':'last available usable changes; may be stale when the history has gaps',
                    'change_unit':'month' if monthly else 'business_day',
                    'recent_mean_change':float(recent.mean()),'full_mean_change':float(ds.mean()),
                    'baseline':{str(h):{'steps':int(steps[ai,hi]),'mean':float(base[:,hi,ai].mean()),
                        'q05':float(np.quantile(base[:,hi,ai],.05)),'q95':float(np.quantile(base[:,hi,ai],.95))}
                        for hi,h in enumerate(horizons)}}
        changes[a]=ds
    corr=pd.DataFrame(changes).corr().reindex(index=assets,columns=assets).fillna(0.)
    return anchors,stats,{'series':details,'change_correlation':corr.to_numpy(float).tolist(),
                        'correlation_asset_order':assets,
                        'anchor_semantics':'observed level; zero for cumulative future log returns'}
