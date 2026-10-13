"""## Executive summary (read this first)
Test information cutoffs, asset-specific routing and shared joint path behavior.
"""
import numpy as np
import pandas as pd
from vnext.specialists import prepare,paths,forecast,MONTHLY,DAILY

def fixture(monthly=False):
    dates=pd.date_range('2000-01-01',periods=180,freq='MS') if monthly else pd.bdate_range('2000-01-03',periods=1500)
    rng=np.random.default_rng(7);z=rng.normal(size=len(dates))
    assets=['CPI_ALL','NFP'] if monthly else ['EUR','JPY']
    levels=np.cumsum(np.stack([.2+z*.03,3+z*.4],axis=1),axis=0)+[100,200]
    frame=pd.DataFrame({'date':np.repeat(dates,2),'asset':np.tile(assets,len(dates)),
                        'value':levels.reshape(-1),'panel_id':'test'})
    return {'test':frame},assets,str(dates[-1].date())

def test_future_input_invariance():
    panels,assets,asof=fixture();steps=np.tile([5,21,63],(2,1))
    result,_=forecast(panels,assets,steps,asof,'level',512,42)
    future=panels['test'].iloc[-2:].copy();future['date']=pd.Timestamp(asof)+pd.Timedelta(days=100)
    future['value']=1e8
    contaminated={'test':pd.concat([panels['test'],future])}
    other,_=forecast(contaminated,assets,steps,asof,'level',512,42)
    assert np.array_equal(result,other)

def test_shared_innovations_and_nested_horizons():
    panels,assets,asof=fixture();s=prepare(panels,assets,asof,'level')
    sample=paths(s,np.tile([5,21,63],(2,1)),2048,42,['baseline'])['baseline']
    assert np.corrcoef(sample[:,2,:].T)[0,1]>.95
    assert np.corrcoef(sample[:,0,0],sample[:,2,0])[0,1]>.15

def test_all_candidates_monthly_finite_and_positive_prices():
    panels,assets,asof=fixture(True);s=prepare(panels,assets,asof,'level',True)
    result=paths(s,np.array([[9,1,3],[10,2,4]]),512,42,MONTHLY)
    assert all(v.shape==(512,3,2) and np.isfinite(v).all() for v in result.values())
    assert all((result[k][:,:,0]>0).all() for k in ['log_trend12','log_trend36'])
    a,meta=forecast(panels,assets,np.tile([1,3,9],(2,1)),asof,'level',512,42,True)
    assert meta['selection']['folds']>=4
    assert meta['selection']['asset_models']['CPI_ALL']!='baseline'

def test_daily_factor_modes_and_short_history_fallback():
    panels,assets,asof=fixture();d=panels['test'].copy()
    d['value']=np.random.default_rng(1).normal(0,.005,len(d));panels={'test':d}
    s=prepare(panels,assets,asof,'log_return')
    result=paths(s,np.tile([5,21,63],(2,1)),256,9,DAILY)
    assert all(np.isfinite(v).all() for v in result.values())
    cutoff=str(pd.Timestamp(d['date'].unique()[500]).date())
    a,meta=forecast(panels,assets,np.tile([5,21,63],(2,1)),cutoff,'log_return',256,9)
    assert meta['engine']=='asset_specialists_v11_fallback'

def test_inflation_drift_uncertainty_and_nonprice_fallback():
    from vnext.inflation import forecast as price_forecast,candidates
    from v11_new.production_cli import _daily_e2_draws
    panels,assets,asof=fixture(True);s=prepare(panels,assets,asof,'level',True)
    grid=candidates(s,np.tile([1,3,9],(2,1)),1024,7)
    assert np.isfinite(grid['trend12:u1.5']).all()
    dates=panels['test']['date'].unique();cutoff=str(pd.Timestamp(dates[150]).date())
    a,_=price_forecast(panels,assets,np.tile([1,3,9],(2,1)),cutoff,'level',512,7,True)
    clipped={'test':panels['test'][panels['test']['date']<=cutoff]}
    b,_=price_forecast(clipped,assets,np.tile([1,3,9],(2,1)),cutoff,'level',512,7,True)
    assert np.array_equal(a,b)

    from qfbench2_track_forecasting.cli import _draw
    reference,_=_draw(panels,assets,[1,3,9],cutoff,512,7,panel_steps=np.tile([1,3,9],(2,1)))
    assert np.allclose(a[:,:,1],reference[:,1,:],rtol=1e-12,atol=1e-12)
    panels,assets,asof=fixture(False)
    a,_=price_forecast(panels,assets,np.tile([5,21,63],(2,1)),asof,'level',512,7)
    b,*_=_daily_e2_draws(panels,assets,[5,21,63],asof,'level',512,7)
    assert np.array_equal(a,b)

def test_crossasset_predictors_keep_shared_shocks():
    from vnext.crossasset import candidate,KINDS
    panels,assets,asof=fixture(False);s=prepare(panels,assets,asof,'level')
    for kind in KINDS:
        sample=candidate(s,np.tile([5,21,63],(2,1)),1024,7,kind)
        assert np.isfinite(sample).all()
        assert np.corrcoef(sample[:,2,:].T)[0,1]>.8
