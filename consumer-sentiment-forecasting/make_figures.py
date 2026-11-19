import pandas as pd,numpy as np,matplotlib.pyplot as plt
INK,INK2,GRID,SURF='#0b0b0b','#52514e','#e4e3df','#fcfcfb'; BLUE,ORANGE,AQUA='#2a78d6','#eb6834','#1baf7a'; GREY='#b9b8b2'
plt.rcParams.update({'figure.facecolor':SURF,'axes.facecolor':SURF,'axes.edgecolor':GRID,'axes.labelcolor':INK2,'xtick.color':INK2,'ytick.color':INK2,
'axes.spines.top':False,'axes.spines.right':False,'axes.grid':True,'grid.color':GRID,'axes.axisbelow':True,'font.size':12,'axes.titlesize':16,
'axes.titleweight':'bold','axes.titlecolor':INK,'axes.titlelocation':'left','savefig.dpi':200})
def save(f,n): f.savefig(f'figures/{n}.png',bbox_inches='tight',facecolor=SURF)
g=pd.read_csv('results/granger_causality_results.csv').sort_values('min_p_value',ascending=False)
#CC4WSA is FRED's continued jobless claims (4-week avg); the original run labeled it consumer credit
g.loc[g.indicator=='CC4WSA','description']='Continued Jobless Claims'
f,ax=plt.subplots(figsize=(8,6)); y=np.arange(len(g))
ax.barh(y,-np.log10(g.min_p_value),height=0.55,color=[BLUE if s else GREY for s in g.significant_5pct])
ax.axvline(-np.log10(0.05),color=INK2,lw=1.4,ls='--'); ax.text(-np.log10(0.05)+0.05,-0.75,'p = 0.05',color=INK2,fontsize=11)
for yi,(p,l) in zip(y,zip(g.min_p_value,g.best_lag)): ax.text(-np.log10(p)+0.06,yi,f'p = {p:.4f} (lag {l} mo)',va='center',color=INK,fontsize=11)
ax.set_yticks(y,g.description); ax.grid(axis='y',visible=False); ax.set_xlabel('Strength of evidence, -log10(p)')
ax.set_xlim(0,4.6); ax.set_title('Sentiment helps predict jobless claims and\nhousing starts, not spending',pad=14); save(f,'01_granger_causality')
a=pd.read_csv('results/leakage_audit_results.csv')
lab={'Naive (last month)':'Naive: same as last month','Ridge (clean features)':'Ridge, leak-free','RandomForest (clean features)':'Random forest, leak-free',
'Ridge (leaky features)':'Ridge, original (leaky)','RandomForest (leaky features)':'Random forest, original (leaky)'}
a=a.set_index('Model').loc[['Ridge (leaky features)','RandomForest (leaky features)','Naive (last month)','RandomForest (clean features)','Ridge (clean features)']]
f,ax=plt.subplots(figsize=(8,6)); y=np.arange(len(a))[::-1]
cols=[ORANGE,ORANGE,INK2,BLUE,BLUE]
ax.barh(y,a.MAE,height=0.55,color=cols)
for yi,v in zip(y,a.MAE): ax.text(v+0.05,yi,f'{v:.2f}',va='center',color=INK,fontsize=12)
ax.set_yticks(y,[lab[i] for i in a.index]); ax.grid(axis='y',visible=False); ax.set_xlabel('Mean absolute error, index points (lower is better)')
ax.set_xlim(0,a.MAE.max()*1.2); ax.set_title('Once the leak is removed, nothing beats\n"same as last month"',pad=14); save(f,'02_leakage_audit_mae')
p=pd.read_csv('results/audit_predictions.csv',index_col=0,parse_dates=True).loc['2019-01-01':]
f,ax=plt.subplots(figsize=(8,6))
ax.plot(p.index,p.actual,color=INK,lw=2.2,label='Actual')
ax.plot(p.index,p.ridge_leaky,color=ORANGE,lw=2,label='Original model (leaky)')
ax.plot(p.index,p.ridge_clean,color=BLUE,lw=2,label='Leak-free model')
ax.set_ylabel('Michigan Consumer Sentiment Index'); ax.legend(frameon=False,loc='upper right')
ax.set_title('A leaky model looks almost perfect,\nbecause it already knows the answer',pad=14); save(f,'03_actual_vs_predicted')
