"""## Executive summary (read this first)
Test cutoff invariance, gaps, path dependence, monthly drift and text evidence controls.
These tests target failure modes, not private outcomes or authored-unit accuracy.
"""
import json
import pathlib
import tempfile
import numpy as np
import pandas as pd
import pytest
from vnext.numeric import prepare,forecast,candidate
from vnext.cli import corpus,guard_scenarios,transform
from vnext.transfer import adjust
from v11_new.production_cli import _daily_e2_draws


def panel(dates,values,assets):
    return {'p':pd.DataFrame({'date':np.repeat(dates,len(assets)),
                            'asset':np.tile(assets,len(dates)),'value':np.asarray(values).reshape(-1)})}


def daily():
    dates=pd.bdate_range('2010-01-01',periods=1000)
    rng=np.random.default_rng(4)
    z=rng.normal(0,.01,(len(dates),2));z[:,1]=.8*z[:,0]+.2*z[:,1]
    vals=2+np.cumsum(z,axis=0)
    return dates,vals,panel(dates,vals,['UST_2Y','UST_10Y'])


def test_future_panel_rows_cannot_change_forecast():
    dates,values,p=daily();asof=str(dates[799].date())
    clipped=panel(dates[:800],values[:800],['UST_2Y','UST_10Y'])
    a,ma=forecast(p,['UST_2Y','UST_10Y'],np.array([[5,21],[5,21]]),asof,'level',400,7)
    b,mb=forecast(clipped,['UST_2Y','UST_10Y'],np.array([[5,21],[5,21]]),asof,'level',400,7)
    assert np.array_equal(a,b)
    assert ma==mb


def test_gap_regression_demonstrates_v11_failure():
    dates,values,p=daily()
    old=panel(dates[:800],values[:800,:1],['UST_2Y'])
    late=panel(pd.DatetimeIndex(['2020-01-01']),[[20.]],['UST_2Y'])
    combined={'p':pd.concat([old['p'],late['p']],ignore_index=True)}
    h=prepare(combined,['UST_2Y'],'2020-01-01','level')
    assert h.gap_count==1
    assert h.anchor[0]==20
    assert np.abs(h.steps.to_numpy()).max()<.1
    new,_=forecast(combined,['UST_2Y'],np.array([[21]]),'2020-01-01','level',1000,42,mode='v11_safe')
    old_sample,*_=_daily_e2_draws(combined,['UST_2Y'],[21],'2020-01-01','level',1000,42)
    assert old_sample.std()>new.std()*10


def test_monthly_trend_is_present_instead_of_driftless_walk():
    dates=pd.date_range('2000-01-01',periods=240,freq='MS')
    rng=np.random.default_rng(6)
    values=(100+np.cumsum(.35+rng.normal(0,.03,len(dates))))[:,None]
    p=panel(dates,values,['CPI_ALL'])
    sample,meta=forecast(p,['CPI_ALL'],np.array([[2,9]]),str(dates[-1].date()),'level',1500,3,monthly=True)
    assert sample[:,1,0].mean()-values[-1,0]>2.0
    assert meta['selection']['folds']>0


def test_common_paths_have_nested_horizons():
    dates,values,p=daily()
    h=prepare(p,['UST_2Y','UST_10Y'],str(dates[-1].date()),'level')
    samples=candidate(h,np.array([[5,21],[5,21]]),3000,5,'fhs60')
    x=samples-h.anchor
    assert np.corrcoef(x[:,0,0],x[:,1,0])[0,1]>.25
    assert np.corrcoef(x[:,1,0],x[:,1,1])[0,1]>.8


def test_corpus_rejects_future_dates_and_escape_paths(tmp_path):
    (tmp_path/'now.txt').write_text('valid policy evidence')
    (tmp_path/'later.txt').write_text('future evidence')
    docs=[{'doc_id':'now','timestamp':'2024-01-01','file':'now.txt'},
          {'doc_id':'later','timestamp':'2025-01-01','file':'later.txt'},
          {'doc_id':'escape','timestamp':'2024-01-01','file':'../outside.txt'},
          {'doc_id':'bad','timestamp':'bad-date','file':'now.txt'}]
    (tmp_path/'corpus_index.json').write_text(json.dumps({'documents':docs}))
    kept,meta=corpus(tmp_path,'2024-06-01')
    assert [d['doc_id'] for d in kept]==['now']
    assert meta['excluded']==3


def test_uncited_text_cannot_move_forecast():
    parsed={'state':{'confidence':1},'scenarios':[{'prob':1,'name':'invented',
                'assets':{'EUR':{'shift_sd':2,'vol_scale':2,'because':'invented-id'}}}]}
    scenarios,state,invalid=guard_scenarios(parsed,['EUR'],[{'doc_id':'actual'}],'T2-F2')
    assert scenarios[0]['assets']['EUR']['shift_sd']==0
    assert scenarios[0]['assets']['EUR']['vol_scale']==1
    assert invalid==1


def test_monthly_shift_uses_steps_and_unsorted_horizons():
    rng=np.random.default_rng(7);base=rng.normal(size=(2000,2,1))
    scenarios=[{'name':'s','prob':1,'assets':{'CPI_ALL':{'shift_sd':1.,'vol_scale':1.}}}]
    changed,_=transform(base,['CPI_ALL'],np.array([[9,2]]),scenarios,42)
    delta=(changed-base).mean(axis=0).ravel()
    assert delta[1]/delta[0]==pytest.approx(2/9)


def test_numeric_forecast_is_repeatable():
    dates,values,p=daily();asof=str(dates[-1].date());steps=np.array([[5,21],[5,21]])
    first,_=forecast(p,['UST_2Y','UST_10Y'],steps,asof,'level',400,23)
    second,_=forecast(p,['UST_2Y','UST_10Y'],steps,asof,'level',400,23)
    assert np.array_equal(first,second)


def test_stale_fx_proxy_is_cutoff_local():
    dates=pd.bdate_range('2010-01-01',periods=1200)
    rng=np.random.default_rng(88)
    returns=rng.normal(0,.006,(len(dates),3))
    values=np.exp(np.cumsum(returns,axis=0))
    p=panel(dates,values,['AUD','EUR','CAD'])
    dense=p['p']
    sparse=dense[(dense['asset']!='AUD')|(dense['date']<=dates[399])|(dense['date']==dates[-1])]
    p={'p':sparse};asof=str(dates[-1].date());steps=np.array([[21]])
    base,_=forecast(p,['AUD'],steps,asof,'level',500,42)
    adjusted,meta=adjust(p,['AUD'],steps,asof,base,42)
    assert meta['applied']
    assert meta['fit_last_date']<asof
    assert np.isfinite(adjusted).all()
    later=panel(pd.bdate_range(dates[-1]+pd.Timedelta(days=3),periods=20),np.full((20,3),999.),['AUD','EUR','CAD'])
    augmented={'p':pd.concat([sparse,later['p']],ignore_index=True)}
    again,meta2=adjust(augmented,['AUD'],steps,asof,base,42)
    assert np.array_equal(adjusted,again)
    assert meta==meta2
