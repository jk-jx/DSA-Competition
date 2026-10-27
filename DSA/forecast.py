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
