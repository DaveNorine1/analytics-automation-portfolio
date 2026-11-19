from openpyxl import Workbook
from openpyxl.styles import Font,PatternFill,Alignment,Border,Side
from openpyxl.chart import BarChart,Reference
from openpyxl.formatting.rule import ColorScaleRule,CellIsRule
from openpyxl.comments import Comment
wb=Workbook()
F='Arial'; NAVY='1F2A44'
h1=Font(name=F,size=16,bold=True,color=NAVY); h2=Font(name=F,size=12,bold=True,color=NAVY)
lab=Font(name=F,size=10,color='333333'); inp=Font(name=F,size=10,color='0000FF',bold=True); fx=Font(name=F,size=10,color='000000')
lnk=Font(name=F,size=10,color='008000'); note=Font(name=F,size=9,italic=True,color='666666'); hdr=Font(name=F,size=10,bold=True,color='FFFFFF')
YEL=PatternFill('solid',fgColor='FFFF00'); HF=PatternFill('solid',fgColor=NAVY); OUT=PatternFill('solid',fgColor='E8F0FB')
thin=Side(style='thin',color='D0D0D0'); box=Border(left=thin,right=thin,top=thin,bottom=thin)
USD='$#,##0;($#,##0);-'; USD2='$#,##0.00;($#,##0.00);-'; NUM='#,##0;(#,##0);-'; PCT='0.0%;(0.0%);-'; X='0.00"x"'

ws=wb.active; ws.title='Inputs'
ws['A1']='Marketing ROI Scenario Planner'; ws['A1'].font=h1
ws['A2']='Change the yellow cells. Everything else recalculates.'; ws['A2'].font=note
rows=[('Annual marketing budget',1500000,USD,'Total paid media + program spend for the year.'),
      ('Revenue per new customer',4000,USD,'Average first-year revenue from one converted customer.'),
      ('Lead-to-customer conversion rate',0.05,PCT,'Share of leads that become paying customers.'),
      ('Current cost per lead (CPL)',90,USD2,'Blended CPL today, from the ad platforms or CRM.')]
ws['A4']='Inputs'; ws['A4'].font=h2
for i,(l,v,f,c) in enumerate(rows,start=5):
    ws[f'A{i}']=l; ws[f'A{i}'].font=lab
    cell=ws[f'B{i}']; cell.value=v; cell.font=inp; cell.fill=YEL; cell.number_format=f; cell.border=box
    ws[f'C{i}']=c; ws[f'C{i}'].font=note
ws['A10']='Current plan (at today\'s CPL)'; ws['A10'].font=h2
out=[('Projected leads','=IFERROR(ROUNDDOWN(B5/B8,0),0)',NUM),
     ('Projected customers','=ROUNDDOWN(B11*B7,0)',NUM),
     ('Projected revenue','=B12*B6',USD),
     ('Projected ROI (revenue / spend)','=IFERROR(B13/B5,0)',X),
     ('Cost per customer','=IFERROR(B5/B12,0)',USD)]
for i,(l,f_,nf) in enumerate(out,start=11):
    ws[f'A{i}']=l; ws[f'A{i}'].font=lab; c=ws[f'B{i}']; c.value=f_; c.font=fx; c.number_format=nf; c.fill=OUT; c.border=box
ws['A17']='How to read this'; ws['A17'].font=h2
for i,t in enumerate(['ROI here is gross revenue divided by marketing spend (e.g. 3.00x = $3 of revenue per $1 spent).',
 'Customers and leads round up, because you cannot close part of a customer. The same two-step rounding is used on every tab.',
 'Blue text = input you can change. Black = formula. Green = pulled from another tab.',
 'Example values are illustrative, not from a real company.'],start=18):
    ws[f'A{i}']=t; ws[f'A{i}'].font=note
ws.column_dimensions['A'].width=36; ws.column_dimensions['B'].width=16; ws.column_dimensions['C'].width=62

s=wb.create_sheet('Scenarios')
s['A1']='What it takes to hit each ROI target'; s['A1'].font=h1
s['A2']='Edit the blue ROI targets in column A. Inputs come from the Inputs tab.'; s['A2'].font=note
heads=['ROI target','Revenue needed','Customers needed','Leads needed','Max CPL to hit target','Current CPL','CPL gap (max - current)','Max cost per customer','Status']
for j,hd in enumerate(heads,start=1):
    c=s.cell(4,j,hd); c.font=hdr; c.fill=HF; c.alignment=Alignment(wrap_text=True,horizontal='center',vertical='center'); c.border=box
s.row_dimensions[4].height=32
for k,t in enumerate([2,3,5,7],start=5):
    r=str(k)
    vals=[t,f'=A{r}*Inputs!$B$5',f'=IFERROR(ROUNDUP(B{r}/Inputs!$B$6,0),0)',f'=IFERROR(ROUNDUP(C{r}/Inputs!$B$7,0),0)',
          f'=IFERROR(Inputs!$B$5/D{r},0)','=Inputs!$B$8',f'=E{r}-F{r}',f'=IFERROR(Inputs!$B$5/C{r},0)',f'=IF(E{r}>=F{r},"On track","CPL too high")']
    fm=[X,USD,NUM,NUM,USD2,USD2,USD2+';',USD,'@']
    for j,(v,nf) in enumerate(zip(vals,fm),start=1):
        c=s.cell(k,j,v); c.number_format=nf if j!=7 else '$#,##0.00;($#,##0.00);-'; c.border=box
        c.font=inp if j==1 else (lnk if j==6 else fx)
s.conditional_formatting.add('I5:I8',CellIsRule(operator='equal',formula=['"On track"'],fill=PatternFill('solid',fgColor='D9F2E3')))
s.conditional_formatting.add('I5:I8',CellIsRule(operator='equal',formula=['"CPL too high"'],fill=PatternFill('solid',fgColor='FBE1E1')))
s['A10']='Reading the gap: a negative CPL gap means leads have to get cheaper (or convert better) to reach that target.'; s['A10'].font=note
for col,w in zip('ABCDEFGHI',[11,16,13,13,14,12,16,15,14]): s.column_dimensions[col].width=w
ch=BarChart(); ch.type='col'; ch.title='Max CPL by ROI target vs. current CPL'; ch.y_axis.title='Cost per lead ($)'; ch.x_axis.title='ROI target'
data=Reference(s,min_col=5,max_col=6,min_row=4,max_row=8); cats=Reference(s,min_col=1,min_row=5,max_row=8)
ch.add_data(data,titles_from_data=True); ch.set_categories(cats)
ch.roundedCorners=False; ch.legend.overlay=False; ch.title.overlay=False; ch.x_axis.title.overlay=False; ch.y_axis.title.overlay=False
ch.x_axis.delete=False; ch.y_axis.delete=False; ch.y_axis.numFmt='$#,##0'; ch.height=8; ch.width=18
ch.series[0].graphicalProperties.solidFill='2A78D6'; ch.series[1].graphicalProperties.solidFill='B9B8B2'
s.add_chart(ch,'A12')

z=wb.create_sheet('Sensitivity')
z['A1']='Sensitivity: leads needed and max CPL'; z['A1'].font=h1
z['A2']='Rows = lead-to-customer conversion rate, columns = ROI target. Edit any blue header.'; z['A2'].font=note
targets=[2,3,4,5,6,7]; rates=[0.02,0.03,0.04,0.05,0.06,0.07,0.08,0.10]
def grid(top,title,formula,nf):
    z.cell(top,1,title).font=h2
    c=z.cell(top+1,1,'Conv. rate \\ ROI'); c.font=hdr; c.fill=HF; c.border=box
    for j,t in enumerate(targets,start=2):
        c=z.cell(top+1,j,t); c.font=Font(name=F,size=10,bold=True,color='0000FF'); c.number_format=X; c.border=box; c.fill=PatternFill('solid',fgColor='EEF2F8')
    for i,rt in enumerate(rates,start=top+2):
        c=z.cell(i,1,rt); c.font=Font(name=F,size=10,bold=True,color='0000FF'); c.number_format=PCT; c.border=box; c.fill=PatternFill('solid',fgColor='EEF2F8')
        for j in range(2,2+len(targets)):
            col=z.cell(top+1,j).column_letter
            c=z.cell(i,j,formula(f'{col}${top+1}',f'$A{i}')); c.number_format=nf; c.font=fx; c.border=box
    rng=f'B{top+2}:{z.cell(top+1+len(rates),1+len(targets)).coordinate}'
    return rng
r1=grid(4,'Leads needed',lambda t,r:f'=IFERROR(ROUNDUP(ROUNDUP({t}*Inputs!$B$5/Inputs!$B$6,0)/{r},0),0)',NUM)
z.conditional_formatting.add(r1,ColorScaleRule(start_type='min',start_color='F7FBFF',end_type='max',end_color='2A78D6'))
r2=grid(16,'Max CPL to hit the target',lambda t,r:f'=IFERROR(Inputs!$B$5/ROUNDUP(ROUNDUP({t}*Inputs!$B$5/Inputs!$B$6,0)/{r},0),0)',USD2)
z.conditional_formatting.add(r2,CellIsRule(operator='greaterThanOrEqual',formula=['Inputs!$B$8'],fill=PatternFill('solid',fgColor='D9F2E3')))
z.conditional_formatting.add(r2,CellIsRule(operator='lessThan',formula=['Inputs!$B$8'],fill=PatternFill('solid',fgColor='FBE1E1')))
z['A28']='Green = achievable at today\'s CPL (Inputs!B8). Red = needs cheaper leads or better conversion.'; z['A28'].font=note
z.column_dimensions['A'].width=18
for col in 'BCDEFG': z.column_dimensions[col].width=13
for w in wb.worksheets: w.sheet_view.showGridLines=False
wb.save('ROI_Scenario_Planner.xlsx')
