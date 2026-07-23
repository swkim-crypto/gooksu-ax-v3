#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
물량+동력 A-Box를 repo 네임스페이스(samaneng.com/ax)로 빌드.
기존 merged_guksu.ttl의 asset/system URI에 정합되게 연결.
출력: data/abox_quantities.ttl (아이소+물량+라인+펌프동력 통합)
"""
import ezdxf, pandas as pd, json, re
from collections import defaultdict

UP='/mnt/user-data/uploads'
ONTO='http://samaneng.com/ax/onto#'
DATA='http://samaneng.com/ax/data/guksu/'

SYS={1:'SYS_PRETREAT',2:'SYS_BIO',3:'SYS_IPR',4:'SYS_UTILITY',5:'SYS_DEWATER',6:'SYS_DEODOR'}
SHEET_XLS={'2.1(침사지및유량조정조설비)':'SYS_PRETREAT','2.2(생물반응조설비)':'SYS_BIO',
           '2.3(총인처리설비)':'SYS_IPR','2.4(용수 공급설비)':'SYS_UTILITY',
           '2.5(슬러지탈수설비)':'SYS_DEWATER','2.6(탈취설비)':'SYS_DEODOR'}
FLUID={'TW':'처리수','SW':'하수','AA':'공기','ES':'농축슬러지','RS':'반송슬러지',
       'OG':'악취가스','MW':'용수','PL':'폴리머','DRN':'드레인'}

def esc(s): return str(s).replace('\\','\\\\').replace('"','\\"').replace('\n',' ').strip()

# ===== DXF 시트 추출 (처리장) =====
doc=ezdxf.readfile(f'{UP}/1_양평군_수량산출서_19_02_22_.dxf'); msp=doc.modelspace()
texts=[]
for e in msp:
    tp=e.dxftype()
    try:
        if tp=='TEXT': texts.append((e.dxf.text,e.dxf.insert.x,e.dxf.insert.y))
        elif tp=='MTEXT': texts.append((e.plain_text(),e.dxf.insert.x,e.dxf.insert.y))
    except: pass
for e in msp.query('INSERT'):
    for a in e.attribs:
        try: texts.append((a.dxf.text,a.dxf.insert.x,a.dxf.insert.y))
        except: pass
anchors={}
for tx,x,y in texts:
    s=str(tx).strip()
    if re.fullmatch(r'\d{3}',s): anchors[s]=(x,y)
x0=min(v[0] for v in anchors.values()); y0=min(v[1] for v in anchors.values())
cw,ch=295.0,210.0
ck=lambda x,y:(round((x-x0)/cw),round((y-y0)/ch))
cell2sheet={ck(*v):s for s,v in anchors.items()}
sheet_tags=defaultdict(set); sheet_lines=defaultdict(set); by_sheet=defaultdict(list)
for tx,x,y in texts:
    sh=cell2sheet.get(ck(x,y)); by_sheet[sh].append((str(tx),x,y))
    if not sh: continue
    for m in re.findall(r'\bM[-–]\d{3}(?:[-–]\d)?\b',str(tx)): sheet_tags[sh].add(m.replace('–','-'))
    for ln in re.findall(r'\b\d{2,3}A-[A-Z]{1,4}-[A-Z]{2,4}\b',str(tx)): sheet_lines[sh].add(ln)
def title(sh):
    ax_,ay_=anchors[sh]; c=[]
    for s,x,y in by_sheet[sh]:
        s=s.strip()
        if len(s)<4 or re.fullmatch(r'\d{3}',s) or '산출근거' in s: continue
        if re.search(r'[가-힣]',s) and (re.search(r'\d{2,3}A-[A-Z]+-[A-Z]+',s) or any(k in s for k in ('배관','펌프','설비','스크린'))):
            c.append((abs(x-ax_)+abs(y-ay_),s))
    c.sort(); return c[0][1] if c else ''
titles={sh:title(sh) for sh in cell2sheet.values()}
all_sheets=sorted(cell2sheet.values())
all_lines=sorted({ln for v in sheet_lines.values() for ln in v})

# ===== 엑셀 물량 =====
def parse_pipe(sname,sysid):
    df=pd.read_excel(f'{UP}/1_1_수량산출서-양평군_배관물량산출서__19_07_03_-복합탈취기.xls',sheet_name=sname,header=None)
    scol={}
    for c in range(4,df.shape[1]):
        v=df.iat[2,c]
        if pd.notna(v) and isinstance(v,(int,float)) and 100<=v<=999: scol[c]=int(v)
    hdr={str(df.iat[2,c]).replace(' ',''):c for c in range(df.shape[1]) if pd.notna(df.iat[2,c])}
    cN,cM,cT,cW=hdr.get('정미'),hdr.get('할증'),hdr.get('합계'),hdr.get('중량')
    recs=[]; cur=None
    for i in range(3,len(df)):
        item=df.iat[i,1]; spec=df.iat[i,2]; unit=df.iat[i,3]
        if pd.notna(item): cur=str(item).strip()
        if pd.isna(spec): continue
        ps={v:float(df.iat[i,c]) for c,v in scol.items() if pd.notna(df.iat[i,c]) and isinstance(df.iat[i,c],(int,float))}
        g=lambda c: float(df.iat[i,c]) if c and pd.notna(df.iat[i,c]) and isinstance(df.iat[i,c],(int,float)) else None
        rec={'sys':sysid,'item':cur,'spec':str(spec).strip(),'unit':str(unit).strip() if pd.notna(unit) else '',
             'net':g(cN),'margin':g(cM),'total':g(cT),'wt':g(cW),'sheets':ps}
        if ps or rec['total'] is not None: recs.append(rec)
    return recs
qty=[]
for sn,sid in SHEET_XLS.items(): qty+=parse_pipe(sn,sid)

# ===== 펌프 동력 =====
pumps=[]
for fn,site,sid,sname,xy in [
    ('2__동력설비_-_국수_중계펌프장.xls','국수','PS_GUKSU','국수 중계펌프장','235285.4 546072.8'),
    ('1__동력설비_-_도곡_중계펌프장.xls','도곡','PS_DOGOK','도곡 중계펌프장','233724.9 546202.7')]:
    df=pd.read_excel(f'{UP}/{fn}',sheet_name='1.1.1.2 동력설비 설치공사',header=None)
    mcc=None
    for i in range(len(df)):
        c1=str(df.iat[i,1]).strip() if pd.notna(df.iat[i,1]) else ''
        c2=str(df.iat[i,2]).strip() if pd.notna(df.iat[i,2]) else ''
        if re.fullmatch(r'MCC-[A-Z]',c1): mcc=c1
        if re.match(r'MP-\d{3}',c2):
            pumps.append({'site':site,'sid':sid,'sname':sname,'xy':xy,'mcc':mcc,'to':c2,
                          'cable':str(df.iat[i,3]).strip(),'sq':df.iat[i,4]})

# ===== TTL 출력 =====
PRE=f'''@prefix ax: <{ONTO}> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

'''
def sysU(s): return f'<{DATA}system/{s}>'
def assetU(base): return f'<{DATA}asset/{base.replace("-","_")}>'
def isoU(sh): return f'<{DATA}iso/ISO_{sh}>'
def lineU(ln): return f'<{DATA}line/{ln.replace("-","_")}>'
def qtyU(i,sys): return f'<{DATA}qty/QTY_{sys[4:]}_{i:03d}>'

O=[PRE]
# --- IsoSheet ---
for sh in all_sheets:
    sysid=SYS[int(sh[0])]
    O.append(f'{isoU(sh)} a ax:IsoSheet ;')
    O.append(f'    rdfs:label "아이소 {sh} {esc(titles.get(sh,""))}" ;')
    O.append(f'    ax:sheetNo "{sh}" ;')
    if titles.get(sh): O.append(f'    ax:sheetTitle "{esc(titles[sh])}" ;')
    O.append(f'    ax:partOf {sysU(sysid)} ;')
    for tg in sorted(sheet_tags.get(sh,[])):
        base=re.match(r'(M-\d{3})',tg).group(1)
        O.append(f'    ax:referencesAsset {assetU(base)} ;')
    for ln in sorted(sheet_lines.get(sh,[])):
        O.append(f'    ax:hasPipeLine {lineU(ln)} ;')
    O[-1]=O[-1][:-2]+' .'; O.append('')
# --- PipeLine ---
for ln in all_lines:
    m=re.match(r'(\d{2,3})A-([A-Z]+)-([A-Z]+)',ln)
    dia,fl,mat=m.group(1),m.group(2),m.group(3)
    O.append(f'{lineU(ln)} a ax:PipeLine ;')
    O.append(f'    rdfs:label "{ln}" ;')
    O.append(f'    ax:nominalDia "{dia}A" ; ax:fluidCode "{fl}" ;')
    if fl in FLUID: O.append(f'    ax:fluidName "{FLUID[fl]}" ;')
    O.append(f'    ax:material "{mat}" .'); O.append('')
# --- QuantityItem ---
for i,r in enumerate(qty):
    O.append(f'{qtyU(i,r["sys"])} a ax:QuantityItem ;')
    O.append(f'    rdfs:label "{esc(r["item"])} {esc(r["spec"])}" ;')
    O.append(f'    ax:itemName "{esc(r["item"])}" ; ax:spec "{esc(r["spec"])}" ;')
    if r['unit']: O.append(f'    ax:unit "{esc(r["unit"])}" ;')
    O.append(f'    ax:partOf {sysU(r["sys"])} ;')
    if r['net'] is not None: O.append(f'    ax:qtyNet "{r["net"]}"^^xsd:decimal ;')
    if r['margin'] is not None: O.append(f'    ax:qtyMargin "{r["margin"]}"^^xsd:decimal ;')
    if r['total'] is not None: O.append(f'    ax:qtyTotal "{r["total"]}"^^xsd:decimal ;')
    if r['wt'] is not None: O.append(f'    ax:weight "{r["wt"]}"^^xsd:decimal ;')
    for shno in sorted(r['sheets']):
        if str(shno) in all_sheets: O.append(f'    ax:derivedFrom {isoU(shno)} ;')
    O[-1]=O[-1][:-2]+' .'; O.append('')
# --- 펌프장 동력 ---
seen_mcc=set(); seen_pump=set(); seen_st=set()
for p in pumps:
    stU=f'<{DATA}pumpstation/{p["sid"]}>'
    if p['sid'] not in seen_st:
        O.append(f'{stU} a ax:PumpStation ;')
        O.append(f'    rdfs:label "{p["sname"]}" ; ax:localXY "{p["xy"]}" ; ax:coordSource "EPSG:5186" .')
        O.append(''); seen_st.add(p['sid'])
    mccU=f'<{DATA}mcc/{p["mcc"].replace("-","_")}_{p["sid"]}>'
    if mccU not in seen_mcc:
        O.append(f'{mccU} a ax:MCC ; rdfs:label "{p["mcc"]} ({p["sname"]})" ; ax:locatedIn {stU} .')
        O.append(''); seen_mcc.add(mccU)
    base=re.match(r'(MP-\d{3})',p['to']).group(1)
    puU=f'<{DATA}asset/{p["to"].replace("-","_")}>'
    if puU not in seen_pump:
        O.append(f'{puU} a ax:Asset ;')
        O.append(f'    rdfs:label "중계펌프 {p["to"]}" ; ax:hasTag "{p["to"]}" ; ax:baseTag "{base}" ;')
        O.append(f'    ax:locatedIn {stU} ; ax:poweredBy {mccU} .')
        O.append(''); seen_pump.add(puU)
    cU=f'<{DATA}cable/CBL_{p["sid"]}_{p["to"].replace("-","_")}>'
    O.append(f'{cU} a ax:PowerCable ;')
    O.append(f'    rdfs:label "{p["cable"]} → {p["to"]}" ; ax:cableSpec "{esc(p["cable"])}" ;')
    O.append(f'    ax:conductorSq "{p["sq"]}"^^xsd:decimal ; ax:cableFrom {mccU} ; ax:cableTo {puU} .')
    O.append('')

open('/home/claude/repo/data/abox_quantities.ttl','w').write('\n'.join(O))

from rdflib import Graph
g=Graph(); g.parse('/home/claude/repo/data/abox_quantities.ttl',format='turtle')
print(f"abox_quantities.ttl: {len(g)} 트리플 (파싱 OK)")
print(f"  IsoSheet {len(all_sheets)} / QuantityItem {len(qty)} / PipeLine {len(all_lines)} / 펌프 {len(seen_pump)}")
