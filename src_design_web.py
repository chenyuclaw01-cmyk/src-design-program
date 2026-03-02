#!/usr/bin/env python3
"""
SRC 鋼骨鋼筋混凝土結構設計程式 (Web UI)
使用 Streamlit 執行

執行方式：
  pip install streamlit
  streamlit run src_design_web.py

設計依據：
- 鋼骨鋼筋混凝土構造設計規範與解說
- 建築物混凝土結構設計規範 (112年版)

⚠️ 重要提醒：本程式僅供設計初稿參考，實際設計應經專業結構技師確認。
"""

import streamlit as st
import math
from dataclasses import dataclass
from typing import Dict

# ============================================================================
# 材料性質與鋼骨資料庫
# ============================================================================

@dataclass
class MaterialProperties:
    fy_steel: float
    fy_rebar: float
    fc: float
    Es: float
    Ec: float
    
    @classmethod
    def create(cls, fy_steel=2800, fy_rebar=4200, fc=280):
        Es = 2.04e6
        Ec = 4700 * math.sqrt(fc) * 10
        return cls(fy_steel=fy_steel, fy_rebar=fy_rebar, fc=fc, Es=Es, Ec=Ec)


DEFAULT_MATERIAL = MaterialProperties.create()

STEEL_SECTIONS = {
    'H300x150x6.5x9': {'bf': 150, 'tw': 6.5, 'tf': 9, 'd': 300, 'Ix': 3770, 'Zx': 251, 'A': 46.78},
    'H350x175x7x11': {'bf': 175, 'tw': 7, 'tf': 11, 'd': 350, 'Ix': 7890, 'Zx': 450, 'A': 62.91},
    'H400x200x8x13': {'bf': 200, 'tw': 8, 'tf': 13, 'd': 400, 'Ix': 13400, 'Zx': 670, 'A': 84.12},
    'H450x200x9x14': {'bf': 200, 'tw': 9, 'tf': 14, 'd': 450, 'Ix': 18700, 'Zx': 831, 'A': 96.76},
    'H500x200x10x16': {'bf': 200, 'tw': 10, 'tf': 16, 'd': 500, 'Ix': 25500, 'Zx': 1120, 'A': 114.2},
    'H600x200x11x17': {'bf': 200, 'tw': 11, 'tf': 17, 'd': 600, 'Ix': 36200, 'Zx': 1490, 'A': 134.4},
    'BOX200x200x9x9': {'bf': 200, 'tw': 9, 'tf': 9, 'd': 200, 'Ix': 2620, 'Zx': 290, 'A': 57.36},
    'BOX250x250x9x9': {'bf': 250, 'tw': 9, 'tf': 9, 'd': 250, 'Ix': 5200, 'Zx': 576, 'A': 71.36},
    'BOX300x300x10x10': {'bf': 300, 'tw': 10, 'tf': 10, 'd': 300, 'Ix': 8950, 'Zx': 1080, 'A': 95.36},
    'BOX350x350x12x12': {'bf': 350, 'tw': 12, 'tf': 12, 'd': 350, 'Ix': 14300, 'Zx': 1588, 'A': 129.36},
    'BOX400x400x14x14': {'bf': 400, 'tw': 14, 'tf': 14, 'd': 400, 'Ix': 21400, 'Zx': 2370, 'A': 169.36},
    'BOX500x500x16x16': {'bf': 500, 'tw': 16, 'tf': 16, 'd': 500, 'Ix': 43800, 'Zx': 4850, 'A': 249.0},
}

REBAR_SIZES = {
    'D10': 0.71, 'D13': 1.27, 'D16': 2.01, 'D19': 2.87, 
    'D22': 3.87, 'D25': 5.07, 'D29': 6.51, 'D32': 8.04
}


# ============================================================================
# 設計類別
# ============================================================================

class SRCBeamDesigner:
    """SRC 梁設計 (強度疊加法)"""
    
    def __init__(self, material=DEFAULT_MATERIAL):
        self.mat = material
        
    def calculate(self, section_name, width, height, cover, As_rebar):
        steel = STEEL_SECTIONS[section_name]
        
        # 鋼骨部分
        Z_s = steel['Zx']
        Mns = Z_s * self.mat.fy_steel / 1e6
        phi_Mns = 0.9 * Mns
        
        # RC 部分
        d_rc = height * 10 - cover * 10
        a = As_rebar * self.mat.fy_rebar / (0.85 * self.mat.fc * width * 10)
        Mnrc = As_rebar * self.mat.fy_rebar * (d_rc - a*10/2) / 1e6
        phi_Mnrc = 0.9 * Mnrc
        
        phi_Mn_total = phi_Mns + phi_Mnrc
        
        return {
            'Mns': Mns, 'phi_Mns': phi_Mns,
            'Mnrc': Mnrc, 'phi_Mnrc': phi_Mnrc,
            'phi_Mn_total': phi_Mn_total,
            'd_rc': d_rc / 10,
            'rho': As_rebar / (width * d_rc/10)
        }


class SRCColumnDesigner:
    """SRC 柱設計 (相對剛度法)"""
    
    def __init__(self, material=DEFAULT_MATERIAL):
        self.mat = material
        
    def calculate_axial(self, section_name, width, depth, cover, As_rebar):
        steel = STEEL_SECTIONS[section_name]
        
        bf = steel['bf']
        d = steel['d']
        tf = steel['tf']
        tw = steel['tw']
        
        Ac_inner = (bf - 2*tw) * (d - 2*tf) / 100
        Ac_total = width * depth - steel['A'] - Ac_inner
        
        Pn_rc = (0.85 * self.mat.fc * Ac_total + self.mat.fy_rebar * As_rebar) / 1000
        Pn_s = self.mat.fy_steel * steel['A'] / 1000
        Pn_total = Pn_rc + Pn_s
        phi_Pn = 0.75 * Pn_rc + 0.9 * Pn_s
        
        return {'Ac': Ac_total, 'Pn_rc': Pn_rc, 'Pn_s': Pn_s, 
                'Pn_total': Pn_total, 'phi_Pn': phi_Pn}
    
    def calculate_PM(self, section_name, width, depth, cover, As_rebar, Pu, Mu):
        steel = STEEL_SECTIONS[section_name]
        
        EsIs = self.mat.Es * steel['Ix']
        I_rc = width * (depth*10)**3 / 12 / 1e4
        EcIc = self.mat.Ec * I_rc
        
        ratio_s = EsIs / (EsIs + EcIc)
        ratio_rc = EcIc / (EsIs + EcIc)
        
        Pus = ratio_s * Pu
        Purc = ratio_rc * Pu
        Mus = ratio_s * Mu
        Murc = ratio_rc * Mu
        
        # 鋼骨檢核
        Pns = self.mat.fy_steel * steel['A'] / 1000
        Mns = self.mat.fy_steel * steel['Zx'] / 1e6
        
        if Pus > 0:
            ratio = Pus / (0.9 * Pns)
            if ratio >= 0.2:
                check_s = ratio + Mus / (0.9 * Mns)
            else:
                check_s = Pus / (1.8 * Pns) + Mus / (0.9 * Mns)
        else:
            check_s = Mus / (0.9 * Mns)
        
        steel_safe = check_s <= 1.0
        
        # RC 檢核
        d = depth * 10 - cover * 10
        a = As_rebar * self.mat.fy_rebar / (0.85 * self.mat.fc * width * 10)
        
        Ac_inner = (steel['bf'] - 2*steel['tw']) * (steel['d'] - 2*steel['tf']) / 100
        Ac = width * depth - steel['A'] - Ac_inner
        
        Pn_rc = (0.85 * self.mat.fc * Ac + self.mat.fy_rebar * As_rebar) / 1000
        Mn_rc = As_rebar * self.mat.fy_rebar * (d - a*10/2) / 1e6
        
        if Purc > 0:
            ratio = Purc / (0.65 * Pn_rc)
            if ratio >= 0.1:
                check_rc = ratio + Murc / (0.9 * Mn_rc)
            else:
                check_rc = Purc / (1.3 * Pn_rc) + Murc / (0.9 * Mn_rc)
        else:
            check_rc = Murc / (0.9 * Mn_rc)
        
        rc_safe = check_rc <= 1.0
        
        return {
            'ratio_s': ratio_s, 'ratio_rc': ratio_rc,
            'Pus': Pus, 'Purc': Purc, 'Mus': Mus, 'Murc': Murc,
            'check_s': check_s, 'steel_safe': steel_safe,
            'check_rc': check_rc, 'rc_safe': rc_safe,
            'is_safe': steel_safe and rc_safe
        }


# ============================================================================
# Streamlit Web UI
# ============================================================================

st.set_page_config(page_title="SRC結構設計程式", page_icon="🏗️", layout="wide")

st.title("🏗️ SRC 鋼骨鋼筋混凝土結構設計程式")
st.markdown("### 設計依據：鋼骨鋼筋混凝土構造設計規範與解說")

# 側邊欄 - 材料選擇
st.sidebar.header("📋 設計參數")

st.sidebar.subheader("材料選擇")
material = MaterialProperties.create(
    fy_steel=st.sidebar.selectbox("鋼骨降伏應力", [2800, 3500], format_func=lambda x: f"{x} kgf/cm²"),
    fy_rebar=st.sidebar.selectbox("鋼筋降伏應力", [2800, 4200], format_func=lambda x: f"{x} kgf/cm²"),
    fc=st.sidebar.selectbox("混凝土抗壓強度", [210, 280, 350, 420], format_func=lambda x: f"{x} kgf/cm²")
)

beam_designer = SRCBeamDesigner(material)
column_designer = SRCColumnDesigner(material)

# 分頁
tab1, tab2, tab3 = st.tabs(["📐 SRC 梁設計", "🏛️ SRC 柱設計", "ℹ️ 設計說明"])

# ===== 梁設計 =====
with tab1:
    st.header("SRC 梁設計 (強度疊加法)")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("輸入參數")
        section = st.selectbox("鋼骨斷面", list(STEEL_SECTIONS.keys()), key='beam_steel')
        b = st.number_input("混凝土寬度 (cm)", value=40, key='beam_b')
        h = st.number_input("混凝土高度 (cm)", value=80, key='beam_h')
        cover = st.number_input("保護層厚度 (cm)", value=5, key='beam_cover')
        
        col_r1, col_r2 = st.columns(2)
        with col_r1:
            rebar_num = st.number_input("鋼筋數量", value=4, min_value=2, key='beam_num')
        with col_r2:
            rebar_size = st.selectbox("鋼筋規格", list(REBAR_SIZES.keys()), key='beam_size')
        
        As = rebar_num * REBAR_SIZES[rebar_size]
        st.info(f"鋼筋面積 As = {As:.2f} cm²")
        
        Mu = st.number_input("設計彎矩 Mu (tf-m)", value=15.0, key='beam_Mu')
        
    with col2:
        if st.button("計算梁設計", type='primary'):
            try:
                result = beam_designer.calculate(section, b, h, cover, As)
                
                st.subheader("計算結果")
                
                # 顯示結果
                st.markdown("### 彎矩強度")
                col_a, col_b = st.columns(2)
                with col_a:
                    st.metric("鋼骨 Mns", f"{result['Mns']:.2f} tf-m")
                    st.metric("RC Mnrc", f"{result['Mnrc']:.2f} tf-m")
                with col_b:
                    st.metric("φMns", f"{result['phi_Mns']:.2f} tf-m", delta=f"{result['phi_Mns']-result['Mns']:.2f}")
                    st.metric("φMnrc", f"{result['phi_Mnrc']:.2f} tf-m", delta=f"{result['phi_Mnrc']-result['Mnrc']:.2f}")
                
                st.divider()
                st.metric("總設計彎矩 φMn", f"{result['phi_Mn_total']:.2f} tf-m")
                
                if result['phi_Mn_total'] >= Mu:
                    st.success(f"✓ 彎矩檢核通過 (需要 {Mu:.1f} tf-m)")
                else:
                    st.error(f"✗ 彎矩不足 (差 {Mu-result['phi_Mn_total']:.2f} tf-m)")
                    
            except Exception as e:
                st.error(f"計算錯誤：{str(e)}")

# ===== 柱設計 =====
with tab2:
    st.header("SRC 柱設計 (相對剛度法)")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("輸入參數")
        section = st.selectbox("鋼骨斷面", list(STEEL_SECTIONS.keys()), key='col_steel')
        b = st.number_input("混凝土寬度 (cm)", value=50, key='col_b')
        h = st.number_input("混凝土深度 (cm)", value=50, key='col_h')
        cover = st.number_input("保護層厚度 (cm)", value=4, key='col_cover')
        
        col_r1, col_r2 = st.columns(2)
        with col_r1:
            rebar_num = st.number_input("鋼筋數量", value=8, min_value=4, key='col_num')
        with col_r2:
            rebar_size = st.selectbox("鋼筋規格", list(REBAR_SIZES.keys()), key='col_size')
        
        As = rebar_num * REBAR_SIZES[rebar_size]
        st.info(f"鋼筋面積 As = {As:.2f} cm²")
        
    with col2:
        st.subheader("設計載重")
        Pu = st.number_input("設計軸力 Pu (tf)", value=100.0, key='col_Pu')
        Mu = st.number_input("設計彎矩 Mu (tf-m)", value=20.0, key='col_Mu')
        
    st.divider()
    
    col_btn1, col_btn2 = st.columns(2)
    
    with col_btn1:
        if st.button("計算軸力強度", type='secondary'):
            try:
                result = column_designer.calculate_axial(section, b, h, cover, As)
                
                st.subheader("軸力強度結果")
                col_a, col_b = st.columns(2)
                with col_a:
                    st.metric("RC部分 Pn", f"{result['Pn_rc']:.1f} tf")
                    st.metric("鋼骨部分 Pns", f"{result['Pn_s']:.1f} tf")
                with col_b:
                    st.metric("總強度 Pn", f"{result['Pn_total']:.1f} tf")
                    st.metric("設計強度 φPn", f"{result['phi_Pn']:.1f} tf")
                
                if result['phi_Pn'] >= Pu:
                    st.success(f"✓ 軸力檢核通過 (需要 {Pu:.1f} tf)")
                else:
                    st.error(f"✗ 軸力不足")
                    
            except Exception as e:
                st.error(f"計算錯誤：{str(e)}")
                
    with col_btn2:
        if st.button("計算P-M檢核", type='primary'):
            try:
                result = column_designer.calculate_PM(section, b, h, cover, As, Pu, Mu)
                
                st.subheader("P-M 檢核結果")
                
                col_a, col_b = st.columns(2)
                with col_a:
                    st.metric("鋼骨分配比例", f"{result['ratio_s']:.1%}")
                    st.metric("鋼骨 Pus", f"{result['Pus']:.1f} tf")
                    st.metric("鋼骨 Mus", f"{result['Mus']:.1f} tf-m")
                with col_b:
                    st.metric("RC分配比例", f"{result['ratio_rc']:.1%}")
                    st.metric("RC Purc", f"{result['Purc']:.1f} tf")
                    st.metric("RC Murc", f"{result['Murc']:.1f} tf-m")
                
                st.divider()
                
                col_c, col_d = st.columns(2)
                with col_c:
                    st.metric("鋼骨檢核值", f"{result['check_s']:.3f}", 
                             delta="安全" if result['steel_safe'] else "不安全",
                             delta_color="normal" if result['steel_safe'] else "inverse")
                with col_d:
                    st.metric("RC檢核值", f"{result['check_rc']:.3f}",
                             delta="安全" if result['rc_safe'] else "不安全",
                             delta_color="normal" if result['rc_safe'] else "inverse")
                
                if result['is_safe']:
                    st.success("✓ 設計安全")
                else:
                    st.error("✗ 設計不安全")
                    
            except Exception as e:
                st.error(f"計算錯誤：{str(e)}")

# ===== 說明 =====
with tab3:
    st.header("設計說明")
    
    st.markdown("""
    ## 設計依據
    - 鋼骨鋼筋混凝土構造設計規範與解說
    - 建築物混凝土結構設計規範 (112年版)
    - 鋼結構極限設計法規範及解說
    
    ## 設計方法
    
    ### 梁 - 強度疊加法
    $$\\phi_b M_n = \\phi_{bs} M_{ns} + \\phi_{brc} M_{nrc}$$
    
    - $M_{ns} = Z \\times F_{ys}$ (鋼骨塑性彎矩)
    - $M_{nrc} = A_s \\times f_y \\times (d - a/2)$ (RC彎矩)
    - $\\phi_{bs} = 0.9$, $\\phi_{brc} = 0.9$
    
    ### 柱 - 相對剛度法
    1. 依相對剛度分配軸力與彎矩
    2. 分別檢核鋼骨與RC部分
    3. 使用P-M互制公式
    
    ## 預設材料
    | 材料 | 規格 |
    |------|------|
    | 鋼骨 | SN280 (Fys = 2800 kgf/cm²) |
    | 鋼筋 | SD420 (Fy = 4200 kgf/cm²) |
    | 混凝土 | f'c = 280 kgf/cm² |
    """)
    
    st.warning("⚠️ 重要提醒：本程式僅供設計初稿參考，實際設計應經專業結構技師確認並符合最新法規規定。")
