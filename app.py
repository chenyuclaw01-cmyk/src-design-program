#!/usr/bin/env python3
"""
SRC 鋼骨鋼筋混凝土結構設計程式 (Streamlit App)
依據：鋼骨鋼筋混凝土構造設計規範與解說 (Taiwan SRC Code)

部署方式：
1. git push 到 GitHub
2. 登入 streamlit.io → New App → 選擇 GitHub 倉庫
"""

import streamlit as st
import math
import sys
sys.path.insert(0, '.')

from src_design import (
    SRCColumn, SRCBeam, DEFAULT_MATERIAL, 
    STEEL_SECTIONS, MaterialProperties
)

# 頁面設定
st.set_page_config(
    page_title="SRC 梁柱設計程式",
    page_icon="📐",
    layout="wide"
)

st.title("📐 SRC 鋼骨鋼筋混凝土結構設計程式")
st.markdown("**依據：鋼骨鋼筋混凝土構造設計規範與解說**")

# 側邊欄 - 設計選項
st.sidebar.header("設計選項")
design_type = st.sidebar.radio("選擇設計類型", ["柱設計", "梁設計"])

if design_type == "柱設計":
    st.header(" SRC 柱設計")
    
    # 材料選擇
    st.subheader("材料性質")
    col1, col2, col3 = st.columns(3)
    with col1:
        fy_steel = st.number_input("鋼骨降伏應力 Fys (kgf/cm²)", value=2800, step=100)
    with col2:
        fy_rebar = st.number_input("鋼筋降伏應力 fy (kgf/cm²)", value=4200, step=100)
    with col3:
        fc = st.number_input("混凝土抗壓強度 f'c (kgf/cm²)", value=280, step=10)
    
    material = MaterialProperties.create(fy_steel=fy_steel, fy_rebar=fy_rebar, fc=fc)
    
    # 斷面選擇
    st.subheader("斷面尺寸")
    col1, col2 = st.columns(2)
    with col1:
        section_name = st.selectbox("鋼骨斷面", list(STEEL_SECTIONS.keys()))
    with col2:
        steel_info = STEEL_SECTIONS[section_name]
        st.write(f"斷面資訊: bf={steel_info['bf']}mm, d={steel_info['d']}mm, tw={steel_info['tw']}mm, tf={steel_info['tf']}mm")
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        width = st.number_input("混凝土寬度 b (cm)", value=50, step=5)
    with col2:
        depth = st.number_input("混凝土深度 h (cm)", value=50, step=5)
    with col3:
        cover = st.number_input("保護層 (cm)", value=4, step=1)
    with col4:
        As_rebar = st.number_input("鋼筋面積 As (cm²)", value=16.08, step=0.5)
    
    col1, col2 = st.columns(2)
    with col1:
        length = st.number_input("柱長度 L (cm)", value=300, step=50)
    with col2:
        K = st.number_input("有效長度因數 K", value=1.0, step=0.1)
    
    # 外力輸入
    st.subheader("外力作用")
    col1, col2 = st.columns(2)
    with col1:
        Pu = st.number_input("設計軸力 Pu (tf)", value=100.0, step=10.0)
    with col2:
        Mu = st.number_input("設計彎矩 Mu (tf-m)", value=20.0, step=5.0)
    
    Vu = st.number_input("設計剪力 Vu (tf)", value=30.0, step=5.0)
    
    # 設計計算
    if st.button("執行柱設計計算", type="primary"):
        col = SRCColumn(
            section_name=section_name,
            width=width,
            depth=depth,
            cover=cover,
            As_rebar=As_rebar,
            length=length,
            K=K,
            material=material
        )
        
        st.divider()
        
        # 軸力設計
        st.subheader("📊 軸力設計結果")
        axial_result = col.design_axial_strength(debug=True)
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("RC 軸力強度 Pn_rc", f"{axial_result['Pn_rc']:.1f} tf")
        with col2:
            st.metric("鋼骨軸力強度 Pn_s", f"{axial_result['Pn_s']:.1f} tf")
        with col3:
            st.metric("設計軸力強度 φPn", f"{axial_result['phi_Pn']:.1f} tf")
        
        # P-M 交互作用
        st.subheader("📊 P-M 交互作用檢核")
        pm_result = col.design_PM_interaction(Pu=Pu, Mu=Mu, debug=True)
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric("鋼骨檢核值", f"{pm_result['check_s']:.3f}", 
                     delta="✓ 安全" if pm_result['steel_safe'] else "✗ 不安全",
                     delta_color="normal" if pm_result['steel_safe'] else "inverse")
        with col2:
            st.metric("RC 檢核值", f"{pm_result['check_rc']:.3f}",
                     delta="✓ 安全" if pm_result['rc_safe'] else "✗ 不安全",
                     delta_color="normal" if pm_result['rc_safe'] else "inverse")
        
        st.metric("總檢核", "✓ 安全" if pm_result['is_safe'] else "✗ 不安全",
                 delta_color="normal" if pm_result['is_safe'] else "inverse")
        
        # 剪力設計
        st.divider()
        st.subheader("📊 剪力設計結果")
        shear_result = col.design_shear_strength(Vu=Vu, Pu=Pu, debug=True)
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric("鋼骨 φVns", f"{shear_result['phi_Vns']:.2f} tf")
            st.metric("鋼骨需要 Vu", f"{shear_result['Vu_s']:.2f} tf")
            st.metric("鋼骨檢核", "✓ 安全" if shear_result['steel_shear_safe'] else "✗ 不安全",
                     delta_color="normal" if shear_result['steel_shear_safe'] else "inverse")
        with col2:
            st.metric("RC φVc", f"{shear_result['phi_Vc']:.2f} tf")
            st.metric("RC 需要 Vu", f"{shear_result['Vu_rc']:.2f} tf")
            st.metric("RC 檢核", "✓ 安全" if shear_result['rc_shear_safe'] else "✗ 不安全",
                     delta_color="normal" if shear_result['rc_shear_safe'] else "inverse")
        
        st.metric("總剪力 φVn", f"{shear_result['phi_Vn_total']:.2f} tf",
                  delta="✓ 安全" if shear_result['is_safe'] else "✗ 不安全",
                  delta_color="normal" if shear_result['is_safe'] else "inverse")
        
        # 成果摘要
        st.divider()
        st.subheader("📋 剪力分析成果摘要")
        summary = col.shear_analysis_summary(Vu=Vu, Pu=Pu)
        st.code(summary, language=None)

elif design_type == "梁設計":
    st.header(" SRC 梁設計")
    
    # 材料選擇
    st.subheader("材料性質")
    col1, col2, col3 = st.columns(3)
    with col1:
        fy_steel = st.number_input("鋼骨降伏應力 Fys (kgf/cm²)", value=2800, step=100, key="beam_fy_steel")
    with col2:
        fy_rebar = st.number_input("鋼筋降伏應力 fy (kgf/cm²)", value=4200, step=100, key="beam_fy_rebar")
    with col3:
        fc = st.number_input("混凝土抗壓強度 f'c (kgf/cm²)", value=280, step=10, key="beam_fc")
    
    material = MaterialProperties.create(fy_steel=fy_steel, fy_rebar=fy_rebar, fc=fc)
    
    # 斷面選擇
    st.subheader("斷面尺寸")
    col1, col2 = st.columns(2)
    with col1:
        section_name = st.selectbox("鋼骨斷面", list(STEEL_SECTIONS.keys()), key="beam_section")
    with col2:
        steel_info = STEEL_SECTIONS[section_name]
        st.write(f"斷面資訊: bf={steel_info['bf']}mm, d={steel_info['d']}mm")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        width = st.number_input("混凝土寬度 b (cm)", value=40, step=5, key="beam_width")
    with col2:
        height = st.number_input("混凝土高度 h (cm)", value=80, step=5, key="beam_height")
    with col3:
        cover = st.number_input("保護層 (cm)", value=5, step=1, key="beam_cover")
    
    As_rebar = st.number_input("鋼筋面積 As (cm²)", value=8.04, step=0.5, key="beam_As")
    
    # 外力輸入
    st.subheader("外力作用")
    col1, col2 = st.columns(2)
    with col1:
        Mu = st.number_input("設計彎矩 Mu (tf-m)", value=15.0, step=5.0, key="beam_Mu")
    with col2:
        Vu = st.number_input("設計剪力 Vu (tf)", value=15.0, step=5.0, key="beam_Vu")
    
    # 設計計算
    if st.button("執行梁設計計算", type="primary", key="beam_calc"):
        beam = SRCBeam(
            section_name=section_name,
            width=width,
            height=height,
            cover=cover,
            As_rebar=As_rebar,
            material=material
        )
        
        st.divider()
        
        # 彎矩設計
        st.subheader("📊 彎矩設計結果")
        Mn_result = beam.design_moment_strength(debug=True)
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("鋼骨 φMns", f"{Mn_result['phi_Mns']:.2f} tf-m")
        with col2:
            st.metric("RC φMnrc", f"{Mn_result['phi_Mnrc']:.2f} tf-m")
        with col3:
            st.metric("總設計彎矩 φMn", f"{Mn_result['phi_Mn_total']:.2f} tf-m")
        
        # 剪力設計
        st.divider()
        st.subheader("📊 剪力設計結果")
        shear_result = beam.design_shear_strength(Vu=Vu, debug=True)
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric("鋼骨 φVns", f"{shear_result['phi_Vns']:.2f} tf")
            st.metric("鋼骨檢核", "✓ 安全" if shear_result['steel_shear_safe'] else "✗ 不安全",
                     delta_color="normal" if shear_result['steel_shear_safe'] else "inverse")
        with col2:
            st.metric("RC φVc", f"{shear_result['phi_Vc']:.2f} tf")
            st.metric("RC 檢核", "✓ 安全" if shear_result['rc_shear_safe'] else "✗ 不安全",
                     delta_color="normal" if shear_result['rc_shear_safe'] else "inverse")
        
        st.metric("總剪力 φVn", f"{shear_result['phi_Vn_total']:.2f} tf",
                  delta="✓ 安全" if shear_result['is_safe'] else "✗ 不安全",
                  delta_color="normal" if shear_result['is_safe'] else "inverse")

# 頁腳
st.divider()
st.markdown("""
---
📌 **參考規範**：
- 鋼骨鋼筋混凝土構造設計規範與解說 (內政部)
- 建築物混凝土結構設計規範
- 鋼結構極限設計法規範及解說

⚠️ **注意**：本程式僅供設計初稿參考，實際設計應經專業結構技師確認。
""")
