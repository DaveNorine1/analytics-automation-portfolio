import pandas as pd, numpy as np
from sklearn.linear_model import Ridge
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline
d=pd.read_csv('data/core_monthly.csv',index_col=0,parse_dates=True)
y=d['UMCSENT']
X=pd.DataFrame(index=d.index)
#every feature uses information available before month t
for c in d.columns:
    s=d[c] if c!='CPIAUCSL' else d[c].pct_change(12)*100
    for L in [1,2,3,6,12]: X[f'{c}_lag{L}']=s.shift(L)
X['UMCSENT_ma3_lag1']=y.shift(1).rolling(3).mean()
X['UMCSENT_chg_lag1']=y.shift(1)-y.shift(2)
#leaky version reproducing the original setup
Xleak=X.copy(); Xleak['UMCSENT_ma3_leaky']=y.rolling(3,min_periods=1).mean()
df=pd.concat([y.rename('y'),X,Xleak[['UMCSENT_ma3_leaky']]],axis=1).dropna()
start=int(len(df)*0.6)
models={'Ridge':lambda:make_pipeline(StandardScaler(),Ridge(1.0)),
        'RandomForest':lambda:RandomForestRegressor(300,min_samples_leaf=3,random_state=0,n_jobs=-1)}
feat=[c for c in X.columns]; leak=feat+['UMCSENT_ma3_leaky']
rows=[];preds={}
for name,mk in models.items():
    for tag,cols in [('clean',feat),('leaky',leak)]:
        yh=[]
        for t in range(start,len(df)):
            m=mk().fit(df[cols].iloc[:t],df['y'].iloc[:t]); yh.append(m.predict(df[cols].iloc[[t]])[0])
        preds[(name,tag)]=np.array(yh)
yt=df['y'].iloc[start:].values; naive=df['UMCSENT_lag1'].iloc[start:].values
def met(p):
    e=yt-p; mae=np.abs(e).mean(); rmse=np.sqrt((e**2).mean())
    r2=1-(e**2).sum()/((yt-yt.mean())**2).sum()
    diracc=np.mean(np.sign(p-naive)==np.sign(yt-naive))
    return mae,rmse,r2,diracc
rows.append(('Naive (last month)',)+met(naive))
for k,p in preds.items(): rows.append((f'{k[0]} ({k[1]} features)',)+met(p))
res=pd.DataFrame(rows,columns=['Model','MAE','RMSE','R2','Directional accuracy']).round(3)
res['MAE vs naive']=(res['MAE']/res.loc[0,'MAE']).round(3)
print(df.index[start],'to',df.index[-1],len(yt),'months')
print(res.to_string(index=False)); res.to_csv('results/leakage_audit_results.csv',index=False)
out=pd.DataFrame({'actual':yt,'naive':naive,'ridge_clean':preds[('Ridge','clean')],'ridge_leaky':preds[('Ridge','leaky')]},index=df.index[start:])
out.to_csv('results/audit_predictions.csv')
