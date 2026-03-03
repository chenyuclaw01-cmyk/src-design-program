#!/usr/bin/env python3
"""
SRC 鋼骨鋼筋混凝土結構設計程式 (Web UI 增強版)
Steel Reinforced Concrete Design Program - Enhanced Web UI

功能：
- 完整計算報告輸出
- P-M 曲線圖
- 斷面配筋圖生成
- 自訂鋼骨強度

⚠️ 重要提醒：本程式僅供設計初稿參考，實際設計應經專業結構技師確認。
"""

import streamlit as st
import math
from dataclasses import dataclass
import matplotlib.pyplot as plt
import matplotlib
import numpy as np

# 支援中文
matplotlib.rcParams['font.sans-serif'] = ['Arial Unicode MS', 'DejaVu Sans']
matplotlib.rcParams['axes.unicode_minus'] = False

@dataclass
class Material:
    fy_steel: float
    fy_rebar: float
    fc: float
    Es: float
    Ec: float
    
    @classmethod
    def create(cls, fy_steel=2800, fy_rebar=4200, fc=280):
        return cls(
            fy_steel=fy_steel, fy_rebar=fy_rebar, fc=fc,
            Es=2.04e6, Ec=4700 * math.sqrt(fc) * 10
        )

@dataclass
class SteelSection:
    name: str; section_type: str; bf: float; tf: float
    tw: float; d: float; Ix: float; Zx: float; A: float

STEEL_DB = {
    'H300x150x6.5x9': SteelSection('H300x150x6.5x9','H',150,9,6.5,300,3770,251,46.78),
    'H350x175x7x11': SteelSection('H350x175x7x11','H',175,11,7,350,7890,450,62.91),
    'H400x200x8x13': SteelSection('H400x200x8x13','H',200,13,8,400,13400,670,84.12),
    'H450x200x9x14': SteelSection('H450x200x9x14','H',200,14,9,450,18700,831,96.76),
    'H500x200x10x16': SteelSection('H500x200x10x16','H',200,16,10,500,25500,1120,114.2),
    'H600x200x11x17': SteelSection('H600x200x11x17','H',200,17,11,600,36200,1490,134.4),
    'BOX200x200x9x9': SteelSection('BOX200x200x9x9','BOX',200,9,9,200,2620,290,57.36),
    'BOX250x250x9x9': SteelSection('BOX250x250x9x9','BOX',250,9,9,250,5200,576,71.36),
    'BOX300x300x10x10': SteelSection('BOX300x300x10x10','BOX',300,10,10,300,8950,1080,95.36),
    'BOX350x350x12x12': SteelSection('BOX350x350x12x12','BOX',350,12,12,350,14300,1588,129.36),
    'BOX400x400x14x14': SteelSection('BOX400x400x14x14','BOX',400,14,14,400,21400,2370,169.36),
    'BOX500x500x16x16': SteelSection('BOX500x500x16x16','BOX',500,16,16,500,43800,4850,249.0),
}

REBAR_DB = {'D10':0.71,'D13':1.27,'D16':2.01,'D19':2.87,'D22':3.87,'D25':5.07,'D29':6.51,'D32':8.04}

class SRCBeamDesigner:
    def __init__(self, mat): self.mat = mat
    def calculate(self, steel, b, h, cover, As):
        d_rc = h*10 - cover*10
        Mns = steel.Zx * self.mat.fy_steel / 1e6
        a = As * self.mat.fy_rebar / (0.85 * self.mat.fc * b)
        Mnrc = As * self.mat.fy_rebar * (d_rc - a*10/2) / 1e6
        return {'phi_Mn':0.9*(Mns+Mnrc), 'Mns':Mns,'Mnrc':Mnrc,'rho':As/(b*d_rc/10),'a':a,'d_rc':d_rc/10}

class SRCColumnDesigner:
    def __init__(self, mat): self.mat = mat
    def calc_axial(self, steel, b, h, cover, As):
        bf,d,tf,tw = steel.bf, steel.d, steel.tf, steel.tw
        Ac_inner = (bf-2*tw)*(d-2*tf)/100
        Ac = b*h - steel.A - Ac_inner
        Pn_rc = (0.85*self.mat.fc*Ac + self.mat.fy_rebar*As)/1000
        Pn_s = self.mat.fy_steel * steel.A / 1000
        return {'phi_Pn':0.75*Pn_rc+0.9*Pn_s, 'Ac':Ac, 'Pn_rc':Pn_rc, 'Pn_s':Pn_s}
    
    def calc_PM(self, steel, b, h, cover, As, Pu, Mu):
        mat = self.mat
        EsIs = mat.Es * steel.Ix
        I_rc = b*(h*10)**3/12/1e4
        EcIc = mat.Ec * I_rc
        rs, rr = EsIs/(EsIs+EcIc), EcIc/(EsIs+EcIc)
        Pus, Purc = rs*Pu, rr*Pu
        Mus, Murc = rs*Mu, rr*Mu
        Pns = mat.fy_steel*steel.A/1000
        Mns = mat.fy_steel*steel.Zx/1e6
        if Pus>0:
            r = Pus/(0.9*Pns)
            chk_s = r+Mus/(0.9*Mns) if r>=0.2 else Pus/(1.8*Pns)+Mus/(0.9*Mns)
        else: chk_s = Mus/(0.9*Mns)
        d_rc = h*10 - cover*10
        bf,d,tf,tw = steel.bf, steel.d, steel.tf, steel.tw
        Ac = b*h-steel.A-(bf-2*tw)*(d-2*tf)/100
        a = As*mat.fy_rebar/(0.85*mat.fc*b*10)
        Pn_rc = (0.85*mat.fc*Ac+mat.fy_rebar*As)/1000
        Mn_rc = As*mat.fy_rebar*(d_rc-a*10/2)/1e6
        if Purc>0:
            r = Purc/(0.65*Pn_rc)
            chk_r = r+Murc/(0.9*Mn_rc) if r>=0.1 else Purc/(1.3*Pn_rc)+Murc/(0.9*Mn_rc)
        else: chk_r = Murc/(0.9*Mn_rc)
        return {'ratio_s':rs,'ratio_rc':rr,'Pus':Pus,'Purc':Purc,'Mus':Mus,'Murc':Murc,
                'check_s':chk_s,'check_r':chk_r,'is_safe':chk_s<=1 and chk_r<=1,
                'Pns':Pns,'Mns':Mns,'Pn_rc':Pn_rc,'Mn_rc':Mn_rc,'Ac':Ac}
    
    def gen_pm_curve(self, steel, b, h, cover, As, pts=50):
        mat = self.mat
        bf,d,tf,tw = steel.bf, steel.d, steel.tf, steel.tw
        Ac = b*h-steel.A-(bf-2*tw)*(d-2*tf)/100
        d_rc = h*10 - cover*10
        Pmax_t = -(mat.fy_rebar*As + mat.fy_steel*steel.A)/1000
        Pmax_c = (0.85*mat.fc*Ac + mat.fy_rebar*As + mat.fy_steel*steel.A)/1000
        pts_list = [(Pmax_t,0)]
        for i in range(pts+1):
            r = i/pts
            P = Pmax_t*(1-r)
            M = (As*mat.fy_rebar*(d_rc/10-0.5) + mat.fy_steel*steel.Zx/1e4*0.8) * r if r>0.1 else 0
            pts_list.append((P,M))
        pts_list.append((Pmax_c,0))
        return pts_list

# ==================== Streamlit UI ====================

st.set_page_config(page_title="SRC梁柱設計", page_icon="🏗️", layout="wide")
st.title("🏗️ SRC 鋼骨鋼筋混凝土結構設計程式")
st.markdown("### 完整計算報告 + P-M曲線 + 配筋圖")

# 側邊欄
st.sidebar.header("📋 設計參數")
st.sidebar.subheader("材料選擇")
fy_steel = st.sidebar.number_input("鋼骨 Fys", value=2800, min_value=2100, max_value=4500)
fy_rebar = st.sidebar.number_input("鋼筋 Fy", value=4200, min_value=2800, max_value=5600)
fc = st.sidebar.selectbox("混凝土 fc'", [210,280,350,420], index=1)
mat = Material.create(fy_steel, fy_rebar, fc)

st.sidebar.markdown("---")
st.sidebar.markdown("### 📐 鋼筋面積")
for n,a in REBAR_DB.items(): st.sidebar.markdown(f"- {n}: {a} cm²")

# 分頁
tab1,tab2,tab3,tab4 = st.tabs(["📐 梁設計","🏛️ 柱設計","📈 P-M曲線","📊 配筋圖"])

# ===== 梁 =====
with tab1:
    st.header("SRC 梁設計 (強度疊加法)")
    c1,c2 = st.columns([1,2])
    with c1:
        sec = st.selectbox("鋼骨", list(STEEL_DB.keys()))
        b,h,cover = st.number_input("b (cm)",40), st.number_input("h (cm)",80), st.number_input("cover",5)
        n_r, s_r = st.columns(2)
        with n_r: num = st.number_input("筋數",4,min_value=2)
        with s_r: size = st.selectbox("規格", list(REBAR_DB.keys()))
        As = num*REBAR_DB[size]
        st.info(f"As = {As:.2f} cm²")
        Mu = st.number_input("Mu (tf-m)",15.0)
    with c2:
        if st.button("計算梁",type="primary"):
            stl = STEEL_DB[sec]
            res = SRCBeamDesigner(mat).calculate(stl,b,h,cover,As)
            st.subheader("📄 計算報告")
            st.markdown(f"""
## 一、設計條件
| 材料 | 數值 |
|------|------|
| 鋼骨 Fys | {fy_steel} kgf/cm² |
| 鋼筋 Fy | {fy_rebar} kgf/cm² |
| 混凝土 fc' | {fc} kgf/cm² |

## 二、彎矩強度計算
**規範來源**：鋼骨鋼筋混凝土構造設計規範與解說 5.4.1

### 鋼骨部分
- Mns = Z × Fys = {stl.Zx} × {fy_steel} = **{res['Mns']:.2f} tf-m**
- φMns = 0.9 × {res['Mns']:.2f} = **{0.9*res['Mns']:.2f} tf-m**

### RC部分
- a = As·fy/(0.85·fc'·b) = {As}×{fy_rebar}/(0.85×{fc}×{b}) = **{res['a']:.2f} cm**
- Mnrc = As·fy·(d-a/2) = **{res['Mnrc']:.2f} tf-m**
- φMnrc = **{0.9*res['Mnrc']:.2f} tf-m**

### 疊加
- **φbMn = {res['phi_Mn']:.2f} tf-m**

## 三、檢核
| 項目 | 需要 | 強度 | 結果 |
|------|------|------|------|
| 彎矩 | {Mu:.2f} | {res['phi_Mn']:.2f} | {'✓' if res['phi_Mn']>=Mu else '✗'} |
| 鋼筋比 | ρ={res['rho']:.4f} | ρmin={1.4/fy_rebar:.4f} | {'✓' if res['rho']>=1.4/fy_rebar else '✗'} |
""")

# ===== 柱 =====
with tab2:
    st.header("SRC 柱設計 (相對剛度法)")
    c1,c2 = st.columns([1,2])
    with c1:
        sec = st.selectbox("鋼骨", list(STEEL_DB.keys()),key='c')
        b,h,cover = st.number_input("b",50,key='cb'), st.number_input("h",50,key='ch'), st.number_input("cover",4,key='cc')
        n_r,s_r = st.columns(2)
        with n_r: num = st.number_input("筋數",8,min_value=4,key='cn')
        with s_r: size = st.selectbox("規格", list(REBAR_DB.keys()),key='cs')
        As = num*REBAR_DB[size]
        st.info(f"As = {As:.2f} cm²")
        Pu = st.number_input("Pu (tf)",80.0)
        Mu = st.number_input("Mu (tf-m)",20.0)
    with c2:
        if st.button("計算柱",type="primary",key='bc'):
            stl = STEEL_DB[sec]
            col = SRCColumnDesigner(mat)
            ax = col.calc_axial(stl,b,h,cover,As)
            pm = col.calc_PM(stl,b,h,cover,As,Pu,Mu)
            st.subheader("📄 計算報告")
            st.markdown(f"""
## 一、設計條件
- 鋼骨: {sec}
- 混凝土: {b}×{h} cm
- 鋼筋: {num}-{size}, As={As} cm²

## 二、軸力強度 (規範 6.4)
- Ac = {pm['Ac']:.1f} cm²
- Pn_rc = {pm['Pn_rc']:.1f} tf
- Pns = {pm['Pns']:.1f} tf
- **φPn = {ax['phi_Pn']:.1f} tf**

## 三、P-M檢核 (規範 7.3)
| 分配 | 鋼骨 | RC |
|------|------|-----|
| 比例 | {pm['ratio_s']:.1%} | {pm['ratio_rc']:.1%} |
| Pu | {pm['Pus']:.1f} | {pm['Purc']:.1f} tf |
| Mu | {pm['Mus']:.1f} | {pm['Murc']:.1f} tf-m |

| 檢核 | 鋼骨 | RC |
|------|------|-----|
| 值 | {pm['check_s']:.3f} | {pm['check_r']:.3f} |
| 結果 | {'✓' if pm['check_s']<=1 else '✗'} | {'✓' if pm['check_r']<=1 else '✗'} |

**結論**: {'✓ 設計安全' if pm['is_safe'] else '✗ 設計不安全'}
""")

# ===== P-M曲線 =====
with tab3:
    st.header("📈 P-M 曲線")
    c1,c2 = st.columns([1,2])
    with c1:
        sec = st.selectbox("鋼骨", list(STEEL_DB.keys()),key='pm')
        b,h,cover = st.number_input("b",50,key='pmb'), st.number_input("h",50,key='pmh'), st.number_input("cover",4,key='pmc')
        n_r,s_r = st.columns(2)
        with n_r: num = st.number_input("筋數",8,key='pmn')
        with s_r: size = st.selectbox("規格", list(REBAR_DB.keys()),key='pms')
        As = num*REBAR_DB[size]
        Pu_d = st.number_input("設計Pu",80.0,key='pmPu')
        Mu_d = st.number_input("設計Mu",20.0,key='pmMu')
    with c2:
        stl = STEEL_DB[sec]
        curve = SRCColumnDesigner(mat).gen_pm_curve(stl,b,h,cover,As)
        Pv = [p[0] for p in curve]
        Mv = [p[1] for p in curve]
        fig,ax = plt.subplots(figsize=(10,8))
        ax.plot(Mv,Pv,'b-',lw=2,label='P-M Curve')
        ax.plot(Mu_d,Pu_d,'ro',ms=12,label=f'Design ({Pu_d},{Mu_d})')
        ax.axhline(0,color='gray',ls='--',lw=0.5)
        ax.axvline(0,color='gray',ls='--',lw=0.5)
        ax.set_xlabel('Moment M (tf-m)',fontsize=12)
        ax.set_ylabel('Axial Force P (tf)',fontsize=12)
        ax.set_title(f'SRC Column P-M Diagram\n{sec} / {b}×{h}cm / {num}-{size}')
        ax.legend()
        ax.grid(alpha=0.3)
        st.pyplot(fig)

# ===== 配筋圖 =====
with tab4:
    st.header("📊 斷面配筋圖")
    c1,c2 = st.columns([1,2])
    with c1:
        typ = st.radio("類型",["梁","柱"])
        if typ=="梁":
            b,h,cover = st.number_input("b",40,key='db'), st.number_input("h",80,key='dh'), st.number_input("cover",5,key='dc')
            top_n = st.number_input("上筋數",2,min_value=2)
            top_s = st.selectbox("上筋規格", list(REBAR_DB.keys()),key='dts')
            bot_n = st.number_input("下筋數",2,min_value=2)
            bot_s = st.selectbox("下筋規格", list(REBAR_DB.keys()),key='dbs')
            stl = st.selectbox("鋼骨", [s for s in STEEL_DB if s.startswith('H')],key='ds')
        else:
            b,h,cover = st.number_input("b",50,key='dcb'), st.number_input("h",50,key='dch'), st.number_input("cover",4,key='dcc')
            num = st.number_input("筋數",8,min_value=4,key='dcn')
            size = st.selectbox("規格", list(REBAR_DB.keys()),key='dcs')
            stl = st.selectbox("鋼骨", [s for s in STEEL_DB if s.startswith('BOX')],key='dsc')
    with c2:
        fig,ax = plt.subplots(figsize=(10,8))
        sc = 8
        cx,cy = 250,250
        
        # 混凝土
        rect = plt.Rectangle((cx-b*sc/2,cy-h*sc/2),b*sc,h*sc,fc='#E8E8E8',ec='k',lw=2)
        ax.add_patch(rect)
        
        stl_dt = STEEL_DB[stl]
        sw,sh = stl_dt.d*sc/10, stl_dt.bf*sc/10
        
        if typ=="梁":
            stl_r = plt.Rectangle((cx-sw/2,cy-sh/2),sw,sh,fc='#606060',ec='k',lw=2)
            ax.add_patch(stl_r)
            rr = 0.8*sc
            for i in range(top_n):
                x = cx-(top_n-1)*sc + i*2*sc
                y = cy + h*sc/2 - cover*sc - rr
                ax.add_patch(plt.Circle((x,y),rr,fc='r'))
            for i in range(bot_n):
                x = cx-(bot_n-1)*sc + i*2*sc
                y = cy - h*sc/2 + cover*sc + rr
                ax.add_patch(plt.Circle((x,y),rr,fc='b'))
            ax.set_title(f"SRC Beam\n{b}×{h}cm, {stl}\nTop:{top_n}-{top_s}, Bottom:{bot_n}-{bot_s}")
        else:
            stl_r = plt.Rectangle((cx-sw/2,cy-sh/2),sw,sh,fc='#606060',ec='k',lw=2)
            ax.add_patch(stl_r)
            tw = stl_dt.tw*sc/10
            inner = plt.Rectangle((cx-(sw-2*tw)/2,cy-(sh-2*tw)/2),sw-2*tw,sh-2*tw,fc='#E8E8E8',ec='k',lw=1)
            ax.add_patch(inner)
            rr = 0.8*sc
            for i in range(num):
                ang = 2*3.14159*i/num
                rx = cx + (b*sc/2-cover*sc-rr)*math.cos(ang)
                ry = cy + (h*sc/2-cover*sc-rr)*math.sin(ang)
                ax.add_patch(plt.Circle((rx,ry),rr,fc='r'))
            ax.set_title(f"SRC Column\n{b}×{h}cm, {stl}\n{num}-{size}")
        
        ax.set_xlim(0,500); ax.set_ylim(0,500)
        ax.set_aspect('equal'); ax.axis('off')
        st.pyplot(fig)
        
        # 材料表
        st.subheader("材料表")
        st.markdown(f"""
| 項目 | 數值 |
|------|------|
| 混凝土 | {b}×{h} cm, fc'={fc} |
| 鋼骨 | {stl}, Fys={fy_steel} |
| 鋼筋 | {num if typ=='柱' else top_n+bot_n}-{size}, As={As if typ=='柱' else (top_n+bot_n)*REBAR_DB[size]} cm² |
""")

st.warning("⚠️ 本程式僅供設計初稿參考，實際設計應經專業結構技師確認。")
