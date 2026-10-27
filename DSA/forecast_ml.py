"""Pooled boosted-demand forecasting across all five markets and three products.

Training is strictly chronological. Genuine purchase orders define the target.
The optional ablation deliberately lets non-orders contaminate the *training*
series; evaluation always uses confirmed PO actuals to quantify the consequence.
"""
from functools import lru_cache
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from insights import transactions

COUNTRIES=("SG","MY","ID","TH","VN")
PRODUCTS=("A","B","C")
MONTHS=pd.period_range(end="2026-09",periods=36,freq="M")
PERIODS=MONTHS.astype(str).tolist()
KEYS=[(country,product) for country in COUNTRIES for product in PRODUCTS]
ORIGINS=(32,33,34)


def series_data(including_nonorders=False):
    # An MDM setup is not a transaction and has no order quantity; it must never
    # become a fictitious PO in the contamination experiment.
    raw=transactions(False)
    if not including_nonorders:
        raw=raw[raw.record_type=="PO"]
    grouped=raw.groupby(["country","product","period"]).qty.sum()
    return {
        key:np.array([float(grouped.get((*key,p),0)) for p in PERIODS],dtype=float)
        for key in KEYS
    }


def features(history,period_index,key):
    """All features are available before the target month."""
    if len(history)<12:
        raise ValueError("Need twelve months of lag history")
    latest=history[-1]
    month=((MONTHS[0].month-1+period_index)%12)+1
    return [
        float(latest),float(np.mean(history[-3:])),
        float(np.mean(history[-6:])),float(history[-12]),
        float(np.mean(history[-12:])),float(np.std(history[-6:])),
        float(np.sin(month*2*np.pi/12)),float(np.cos(month*2*np.pi/12)),
        float(COUNTRIES.index(key[0])),float(PRODUCTS.index(key[1])),
    ]


def fit_pooled(data,end_index):
    X=[];y=[]
    for key in KEYS:
        series=data[key]
        for i in range(12,end_index+1):
            X.append(features(series[:i],i,key))
            y.append(float(series[i]))
    model=HistGradientBoostingRegressor(
        max_iter=85,learning_rate=.065,max_leaf_nodes=10,
        min_samples_leaf=8,l2_regularization=4.0,
        early_stopping=False,random_state=2026,
    )
    model.fit(X,y)
    return model


def model_forecast(model,history,period_index,key):
    value=float(model.predict([features(history,period_index,key)])[0])
    return max(0.0,value) if np.isfinite(value) else max(0.0,float(np.mean(history[-6:])))


@lru_cache(maxsize=1)
def _backtest_cached():
    po=series_data(False)
    contaminated=series_data(True)
    details=[]
    for origin in ORIGINS:
        # One pooled model per origin, fitted on earlier observations only.
        clean_model=fit_pooled(po,origin)
        dirty_model=fit_pooled(contaminated,origin)
        for key in KEYS:
            actual=float(po[key][origin+1])
            for label, model, history in (
                ("Pooled gradient boosting",clean_model,po[key][:origin+1]),
                ("Unfiltered training (ablation)",dirty_model,contaminated[key][:origin+1]),
            ):
                pred=model_forecast(model,history,origin+1,key)
                details.append({
                    "country":key[0],"product":key[1],
                    "test_month":PERIODS[origin+1],
                    "model":label,"actual":actual,"forecast":round(pred,2),
                })
    frame=pd.DataFrame(details)
    summary=frame.assign(error=(frame.actual-frame.forecast).abs()).groupby("model",sort=False).agg(
        absolute_error=("error","sum"),actual=("actual","sum"),
        held_out_points=("error","size"),
    ).reset_index()
    summary["WAPE %"]=(100*summary.absolute_error/summary.actual).round(2)
    summary=summary[["model","WAPE %","held_out_points"]]
    return summary,frame


def pooled_backtest():
    return _backtest_cached()


@lru_cache(maxsize=1)
def _full_model():
    return fit_pooled(series_data(False),35)


def pooled_future(country,product,horizon):
    if (country,product) not in KEYS:
        raise ValueError("Unsupported market/product")
    model=_full_model()
    series=series_data(False)[(country,product)].tolist()
    predictions=[]
    for i in range(horizon):
        value=model_forecast(model,series,36+i,(country,product))
        predictions.append(value)
        series.append(value)
    return np.array(predictions,dtype=float)
