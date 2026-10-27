"""Fair monthly rolling-origin backtest on matched genuine purchase-order actuals."""
import numpy as np
import pandas as pd
from statsmodels.tsa.holtwinters import ExponentialSmoothing
from insights import transactions

END = pd.Period('2026-09',freq='M')

def backtest():
    df=transactions(True)
    periods=pd.period_range(end=END,periods=36,freq='M').astype(str).tolist()
    sums=df.groupby(['country','product','period'])['qty'].sum()
    errors={'6-month moving average':[],'Holt-Winters':[]}
    rows=[]
    # Three held-out monthly origins, all models evaluated on identical genuine PO actuals.
    for cc in ['SG','MY','ID','TH','VN']:
        for product in 'ABC':
            series=np.asarray([float(sums.get((cc,product,p),0)) for p in periods])
            for end_idx in (32,33,34):
                train=series[:end_idx+1]; actual=float(series[end_idx+1])
                baseline=float(np.mean(train[-6:]))
                try:
                    hw=ExponentialSmoothing(train,trend='add',seasonal='add',seasonal_periods=12,
                                            initialization_method='estimated').fit(optimized=True)
                    predicted=max(0.,float(hw.forecast(1)[0]))
                except (ValueError,ZeroDivisionError,RuntimeError,OverflowError):
                    predicted=baseline
                for model,forecast in [('6-month moving average',baseline),('Holt-Winters',predicted)]:
                    errors[model].append((abs(actual-forecast),actual))
                    rows.append({'country':cc,'product':product,'test_month':periods[end_idx+1],
                                 'model':model,'actual':actual,'forecast':round(forecast,2)})
    summary=[]
    for name,pairs in errors.items():
        denom=sum(actual for err,actual in pairs)
        summary.append({'model':name,'WAPE %':round(100*sum(err for err,actual in pairs)/denom,2) if denom else np.nan,
                        'held_out_points':len(pairs)})
    return pd.DataFrame(summary),pd.DataFrame(rows)


def forward_plan(country, product, horizon=6, method='6-month moving average'):
    """Future monthly demand plan for one market and product.

    All quantities come from synthetic confirmed POs. The moving-average model
    produces a constant level over the horizon; Holt-Winters extrapolates
    trend/seasonality where feasible. Planning bands are sensitivity scenarios,
    NOT calibrated confidence intervals.
    """
    if country not in ('SG', 'MY', 'ID', 'TH', 'VN'):
        raise ValueError('Choose one supported market')
    if product not in ('A', 'B', 'C'):
        raise ValueError('Choose one supported product')
    if horizon not in (6, 12):
        raise ValueError('Only six- or twelve-month plans are supported')
    if method not in ('6-month moving average', 'Holt-Winters'):
        raise ValueError('Unknown forecast model')
    series_data=transactions(True)
    months=pd.period_range(end=END,periods=36,freq='M')
    subset=series_data[(series_data.country==country)&(series_data['product']==product)]
    totals=subset.groupby('period')['qty'].sum()
    series=np.asarray([float(totals.get(str(p),0)) for p in months], dtype=float)
    baseline=float(np.mean(series[-6:]))
    if method=='Holt-Winters':
        try:
            fit=ExponentialSmoothing(
                series,trend='add',seasonal='add',seasonal_periods=12,
                initialization_method='estimated'
            ).fit(optimized=True)
            future=np.maximum(0.,np.asarray(fit.forecast(horizon),dtype=float))
            if not np.isfinite(future).all():
                raise ValueError('Unstable Holt-Winters output')
        except (ValueError,ZeroDivisionError,RuntimeError,OverflowError):
            future=np.repeat(baseline,horizon)
    else:
        future=np.repeat(baseline,horizon)

    # Variation of the most recent 12 months provides an editable planning
    # sensitivity; it is NOT a probability bound or model validation result.
    swing=min(.4,max(.1,float(np.std(series[-12:])/(np.mean(series[-12:])+1e-9))))
    forecast_months=pd.period_range(start=END+1,periods=horizon,freq='M')
    return pd.DataFrame({
        'Month':forecast_months.astype(str),
        'Market':country,'Product':product,
        'Forecast units':np.round(future).astype(int),
        'Low planning scenario':np.maximum(0,np.round(future*(1-swing))).astype(int),
        'High planning scenario':np.round(future*(1+swing)).astype(int),
    })
