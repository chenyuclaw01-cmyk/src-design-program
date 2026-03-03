#!/usr/bin/env python3
"""
SRC 鋼骨鋼筋混凝土結構設計程式
依據：鋼骨鋼筋混凝土構造設計規範與解說 (Taiwan SRC Code)
"""
import streamlit as st
import math
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import Rectangle, Circle, FancyArrowPatch
import numpy as np
from dataclasses import dataclass
import io
import datetime

matplotlib.rcParams['font.sans-serif'] = ['Arial Unicode MS', 'PingFang TC', 'Microsoft JhengHei', 'DejaVu Sans']
matplotlib.rcParams['axes.unicode_minus'] = False
import matplotlib
matplotlib.rcParams['font.sans-serif'] = ['Arial Unicode MS', 'PingFang TC', 'DejaVu Sans']

# ============================================================
# 材料資料類別
# ============================================================
@dataclass
class Material:
    fy_steel: float   # 鋼骨降伏強度 kgf/cm²
    fy_rebar: float   # 鋼筋降伏強度 kgf/cm²
    fc: float         # 混凝土抗壓強度 kgf/cm²
    Es: float = 2040000.0   # 鋼材彈性模數 kgf/cm²
    Ec: float = 0.0         # 混凝土彈性模數 kgf/cm²
    
    def __post_init__(self):
        self.Ec = 4700 * math.sqrt(self.fc * 0.0981) / 0.0981  # kgf/cm²
        # Ec = 4700√fc'(MPa) → 換算 kgf/cm²
        # fc(kgf/cm²) → MPa: *0.0981; √MPa → /√0.0981 back
        self.Ec = round(15000 * math.sqrt(self.fc), 0)  # 台灣規範近似值

# ============================================================
# 鋼骨斷面資料庫
# ============================================================
@dataclass
class SteelSection:
    name: str
    section_type: str  # 'H' or 'BOX'
    bf: float   # 翼板寬度 mm
    tf: float   # 翼板厚度 mm
    tw: float   # 腹板厚度 mm
    d: float    # 斷面深度 mm
    Ix: float   # 慣性矩 cm⁴
    Zx: float   # 塑性斷面模數 cm³
    A: float    # 斷面積 cm²

STEEL_DB = {
    'H300x150x6.5x9':  SteelSection('H300x150x6.5x9', 'H', 150, 9,   6.5, 300, 3770,  251,  46.78),
    'H350x175x7x11':   SteelSection('H350x175x7x11',  'H', 175, 11,  7,   350, 7890,  450,  62.91),
    'H400x200x8x13':   SteelSection('H400x200x8x13',  'H', 200, 13,  8,   400, 13400, 670,  84.12),
    'H450x200x9x14':   SteelSection('H450x200x9x14',  'H', 200, 14,  9,   450, 18700, 831,  96.76),
    'H500x200x10x16':  SteelSection('H500x200x10x16', 'H', 200, 16,  10,  500, 25500, 1120, 114.2),
    'H600x200x11x17':  SteelSection('H600x200x11x17', 'H', 200, 17,  11,  600, 36200, 1490, 134.4),
    'BOX200x200x9x9':  SteelSection('BOX200x200x9x9', 'BOX', 200, 9,  9,  200, 2620,  290,  57.36),
    'BOX250x250x9x9':  SteelSection('BOX250x250x9x9', 'BOX', 250, 9,  9,  250, 5200,  576,  71.36),
    'BOX300x300x10x10':SteelSection('BOX300x300x10x10','BOX',300, 10, 10, 300, 8950,  1080, 95.36),
    'BOX350x350x12x12':SteelSection('BOX350x350x12x12','BOX',350, 12, 12, 350, 14300, 1588, 129.36),
    'BOX400x400x14x14':SteelSection('BOX400x400x14x14','BOX',400, 14, 14, 400, 21400, 2370, 169.36),
    'BOX500x500x16x16':SteelSection('BOX500x500x16x16','BOX',500, 16, 16, 500, 43800, 4850, 249.0),
}

REBAR_DB = {
    'D10': 0.71, 'D13': 1.27, 'D16': 2.01, 'D19': 2.87,
    'D22': 3.87, 'D25': 5.07, 'D29': 6.51, 'D32': 8.04
}

_CUSTOM_LABEL = "✏️ 自訂斷面"

def steel_section_selector(key: str, filter_type: str = 'all',
                           default_name: str | None = None) -> SteelSection:
    """
    顯示鋼骨斷面選擇器（含自訂斷面）。
    filter_type: 'H' | 'BOX' | 'all'
    傳回所選 / 自訂的 SteelSection 物件。
    """
    if filter_type == 'H':
        db_keys = [k for k in STEEL_DB if k.startswith('H')]
    elif filter_type == 'BOX':
        db_keys = [k for k in STEEL_DB if k.startswith('BOX')]
    else:
        db_keys = list(STEEL_DB.keys())

    options = db_keys + [_CUSTOM_LABEL]

    # 預設索引
    if default_name and default_name in db_keys:
        def_idx = db_keys.index(default_name)
    else:
        def_idx = 0

    chosen = st.selectbox("鋼骨斷面", options, index=def_idx, key=f"{key}_sec")

    if chosen != _CUSTOM_LABEL:
        return STEEL_DB[chosen]

    # ── 自訂斷面輸入 ────────────────────────────────────────────
    st.markdown("##### ✏️ 自訂斷面參數")
    cust_type = st.radio("斷面類型", ['H型鋼', 'BOX型鋼'],
                         horizontal=True, key=f"{key}_type")
    sec_type = 'H' if cust_type == 'H型鋼' else 'BOX'

    ca, cb = st.columns(2)
    with ca:
        c_d  = st.number_input("断面深度 d (mm)",  min_value=100, max_value=2000,
                               value=400, step=10, key=f"{key}_d")
        c_bf = st.number_input("翼板寬度 bf (mm)", min_value=50,  max_value=1000,
                               value=200, step=5,  key=f"{key}_bf")
        c_tf = st.number_input("翼板厚度 tf (mm)", min_value=4,   max_value=100,
                               value=13,  step=1,  key=f"{key}_tf")
        c_tw = st.number_input("腹板厚度 tw (mm)", min_value=3,   max_value=80,
                               value=8,   step=1,  key=f"{key}_tw")
    with cb:
        # 自動估算預設值（供使用者參考後修改）
        d_cm  = c_d  / 10.0
        bf_cm = c_bf / 10.0
        tf_cm = c_tf / 10.0
        tw_cm = c_tw / 10.0
        if sec_type == 'H':
            _A_est  = round(2*bf_cm*tf_cm + (d_cm - 2*tf_cm)*tw_cm, 2)
            _Ix_est = round(bf_cm*d_cm**3/12 - (bf_cm-tw_cm)*(d_cm-2*tf_cm)**3/12, 1)
            _Zx_est = round(_Ix_est / (d_cm/2), 1)
        else:
            _A_est  = round(bf_cm*d_cm - (bf_cm-2*tw_cm)*(d_cm-2*tf_cm), 2)
            _Ix_est = round((bf_cm*d_cm**3 - (bf_cm-2*tw_cm)*(d_cm-2*tf_cm)**3)/12, 1)
            _Zx_est = round(_Ix_est / (d_cm/2), 1)

        c_A  = st.number_input("斷面積 A (cm²)",    min_value=1.0,  max_value=5000.0,
                               value=float(_A_est),  step=0.1, format="%.2f", key=f"{key}_A")
        c_Ix = st.number_input("慣性矩 Ix (cm⁴)",   min_value=1.0,  max_value=9999999.0,
                               value=float(_Ix_est), step=1.0, format="%.1f", key=f"{key}_Ix")
        c_Zx = st.number_input("塑性模數 Zx (cm³)", min_value=1.0,  max_value=999999.0,
                               value=float(_Zx_est), step=1.0, format="%.1f", key=f"{key}_Zx")

    cust_name = f"自訂-{sec_type}{c_d}x{c_bf}x{c_tw}x{c_tf}"
    st.caption(f"斷面名稱：{cust_name} | A={c_A:.2f} cm² | Ix={c_Ix:.1f} cm⁴ | Zx={c_Zx:.1f} cm³")
    return SteelSection(name=cust_name, section_type=sec_type,
                        bf=float(c_bf), tf=float(c_tf), tw=float(c_tw), d=float(c_d),
                        Ix=float(c_Ix), Zx=float(c_Zx), A=float(c_A))

# ============================================================
# SRC 梁設計 (規範第5章)
# ============================================================
def calc_beam(mat: Material, steel: SteelSection, b, h, cover, As_top, As_bot, Mu):
    """
    規範 5.4 強度疊加法
    φMn = φ(Mns + Mnrc)
    """
    lines = []
    lines.append("=" * 60)
    lines.append("SRC 梁設計計算書")
    lines.append("依據：鋼骨鋼筋混凝土構造設計規範與解說 第5章")
    lines.append("=" * 60)

    lines.append("\n【一、設計條件】")
    lines.append(f"  鋼骨斷面    : {steel.name}")
    lines.append(f"  梁寬  b     : {b} cm")
    lines.append(f"  梁深  h     : {h} cm")
    lines.append(f"  保護層 dc   : {cover} cm")
    lines.append(f"  上部鋼筋 As_top : {As_top:.2f} cm²")
    lines.append(f"  下部鋼筋 As_bot : {As_bot:.2f} cm²")
    lines.append(f"  設計彎矩 Mu : {Mu:.2f} tf-m")
    lines.append(f"\n  材料強度：")
    lines.append(f"  鋼骨 Fys = {mat.fy_steel:.0f} kgf/cm²")
    lines.append(f"  鋼筋 Fy  = {mat.fy_rebar:.0f} kgf/cm²")
    lines.append(f"  混凝土 fc' = {mat.fc:.0f} kgf/cm²")

    lines.append("\n【二、鋼骨彎矩強度 Mns】(規範 5.4.1)")
    lines.append("  公式：Mns = Zs × Fys")
    lines.append(f"  Zs   = {steel.Zx:.1f} cm³   (由型鋼表查得)")
    lines.append(f"  Fys  = {mat.fy_steel:.0f} kgf/cm²")
    Mns = steel.Zx * mat.fy_steel / 1e6
    lines.append(f"  Mns  = {steel.Zx:.1f} × {mat.fy_steel:.0f} / 10⁶")
    lines.append(f"       = {Mns:.3f} tf-m")
    phi_Mns = 0.9 * Mns
    lines.append(f"  φMns = 0.9 × {Mns:.3f} = {phi_Mns:.3f} tf-m")

    lines.append("\n【三、RC部分彎矩強度 Mnrc】(規範 5.4.2)")
    lines.append("  採用受拉鋼筋 (下部鋼筋) 計算正彎矩強度")
    As = As_bot
    d_rc = h - cover  # cm，有效深度
    lines.append(f"  有效深度 d = h - dc = {h} - {cover} = {d_rc:.1f} cm")
    lines.append(f"  As (下筋)  = {As:.2f} cm²")
    lines.append("  公式：a = As × Fy / (0.85 × fc' × b)")
    a = As * mat.fy_rebar / (0.85 * mat.fc * b)
    lines.append(f"  a = {As:.2f} × {mat.fy_rebar:.0f} / (0.85 × {mat.fc:.0f} × {b})")
    lines.append(f"    = {a:.3f} cm")
    lines.append("  公式：Mnrc = As × Fy × (d - a/2)")
    Mnrc = As * mat.fy_rebar * (d_rc - a / 2) / 1e6
    lines.append(f"  Mnrc = {As:.2f} × {mat.fy_rebar:.0f} × ({d_rc:.1f} - {a:.3f}/2) / 10⁶")
    lines.append(f"       = {Mnrc:.3f} tf-m")
    phi_Mnrc = 0.9 * Mnrc
    lines.append(f"  φMnrc = 0.9 × {Mnrc:.3f} = {phi_Mnrc:.3f} tf-m")

    lines.append("\n【四、疊加彎矩強度】(規範 5.4)")
    lines.append("  公式：φMn = φ(Mns + Mnrc) = φMns + φMnrc")
    phi_Mn = phi_Mns + phi_Mnrc
    lines.append(f"  φMn = {phi_Mns:.3f} + {phi_Mnrc:.3f}")
    lines.append(f"      = {phi_Mn:.3f} tf-m")

    lines.append("\n【五、最小鋼筋比檢核】(規範 5.3)")
    rho = As / (b * d_rc)
    rho_min = max(1.4 / mat.fy_rebar, 0.8 * math.sqrt(mat.fc) / mat.fy_rebar)
    lines.append(f"  ρ = As/(b×d) = {As:.2f}/({b}×{d_rc:.1f}) = {rho:.5f}")
    lines.append(f"  ρmin = max(1.4/Fy, 0.8√fc'/Fy)")
    lines.append(f"       = max({1.4/mat.fy_rebar:.5f}, {0.8*math.sqrt(mat.fc)/mat.fy_rebar:.5f})")
    lines.append(f"       = {rho_min:.5f}")
    ok_rho = "✓ OK" if rho >= rho_min else "✗ NG"
    lines.append(f"  ρ = {rho:.5f} {'≥' if rho>=rho_min else '<'} ρmin = {rho_min:.5f}  → {ok_rho}")

    lines.append("\n【六、強度檢核】")
    ok_mu = "✓ OK" if phi_Mn >= Mu else "✗ NG"
    lines.append(f"  φMn = {phi_Mn:.3f} tf-m {'≥' if phi_Mn>=Mu else '<'} Mu = {Mu:.3f} tf-m  → {ok_mu}")

    lines.append("\n" + "=" * 60)
    lines.append(f"  結論：{'設計安全 ✓' if phi_Mn>=Mu and rho>=rho_min else '設計不足 ✗，請加大斷面或配筋'}")
    lines.append("=" * 60)

    result = {
        'Mns': Mns, 'Mnrc': Mnrc, 'phi_Mn': phi_Mn,
        'a': a, 'd_rc': d_rc, 'rho': rho, 'rho_min': rho_min,
        'ok': phi_Mn >= Mu and rho >= rho_min
    }
    return '\n'.join(lines), result


# ============================================================
# SRC 柱設計 (規範第6、7章)
# ============================================================
def calc_column(mat: Material, steel: SteelSection, b, h, cover, As, Pu, Mu):
    """
    規範 6.4 軸力強度 + 7.3 P-M交互作用
    採用相對剛度分配法
    """
    lines = []
    lines.append("=" * 60)
    lines.append("SRC 柱設計計算書")
    lines.append("依據：鋼骨鋼筋混凝土構造設計規範與解說 第6、7章")
    lines.append("=" * 60)

    lines.append("\n【一、設計條件】")
    lines.append(f"  鋼骨斷面    : {steel.name}")
    lines.append(f"  柱寬  b     : {b} cm")
    lines.append(f"  柱深  h     : {h} cm")
    lines.append(f"  保護層 dc   : {cover} cm")
    lines.append(f"  縱向鋼筋 As : {As:.2f} cm²")
    lines.append(f"  設計軸力 Pu : {Pu:.2f} tf")
    lines.append(f"  設計彎矩 Mu : {Mu:.2f} tf-m")
    lines.append(f"\n  材料強度：")
    lines.append(f"  鋼骨 Fys = {mat.fy_steel:.0f} kgf/cm²")
    lines.append(f"  鋼筋 Fy  = {mat.fy_rebar:.0f} kgf/cm²")
    lines.append(f"  混凝土 fc' = {mat.fc:.0f} kgf/cm²")
    lines.append(f"  Es = {mat.Es:.0f} kgf/cm²")
    lines.append(f"  Ec = 15000√fc' = 15000×√{mat.fc:.0f} = {mat.Ec:.0f} kgf/cm²")

    lines.append("\n【二、斷面積計算】")
    bf_cm = steel.bf / 10
    d_cm = steel.d / 10
    tf_cm = steel.tf / 10
    tw_cm = steel.tw / 10
    A_gross = b * h
    A_steel = steel.A
    Ac_inner = (bf_cm - 2*tw_cm) * (d_cm - 2*tf_cm)
    Ac = A_gross - A_steel - Ac_inner + Ac_inner  # 全斷面混凝土(含內孔)
    # 正確算法: 混凝土淨面積 = 總面積 - 鋼骨面積
    Ac = A_gross - A_steel
    lines.append(f"  Ag (全斷面)  = b × h = {b} × {h} = {A_gross:.2f} cm²")
    lines.append(f"  As_steel     = {A_steel:.2f} cm²  (鋼骨斷面積)")
    lines.append(f"  Ac           = Ag - As_steel = {A_gross:.2f} - {A_steel:.2f} = {Ac:.2f} cm²")

    lines.append("\n【三、軸力強度 φPn】(規範 6.4)")
    lines.append("  公式：Pn = Pn_rc + Pn_s")
    lines.append("  Pn_rc = 0.85 fc' Ac + Fy As")
    lines.append("  Pn_s  = Fys As_steel")
    Pn_rc = (0.85 * mat.fc * Ac + mat.fy_rebar * As) / 1000
    Pn_s  = mat.fy_steel * A_steel / 1000
    lines.append(f"  Pn_rc = (0.85×{mat.fc:.0f}×{Ac:.1f} + {mat.fy_rebar:.0f}×{As:.2f}) / 1000")
    lines.append(f"        = {Pn_rc:.2f} tf")
    lines.append(f"  Pn_s  = {mat.fy_steel:.0f}×{A_steel:.2f}/1000 = {Pn_s:.2f} tf")
    phi_Pn = 0.75 * Pn_rc + 0.9 * Pn_s
    lines.append(f"  φPn = φrc×Pn_rc + φs×Pn_s")
    lines.append(f"      = 0.75×{Pn_rc:.2f} + 0.9×{Pn_s:.2f}")
    lines.append(f"      = {phi_Pn:.2f} tf")

    lines.append("\n【四、相對剛度分配】(規範 7.3)")
    lines.append("  公式：r_s = Es·Is / (Es·Is + Ec·Ic)")
    Is = steel.Ix  # cm⁴
    Ic = b * (h ** 3) / 12  # cm⁴
    EsIs = mat.Es * Is
    EcIc = mat.Ec * Ic
    rs = EsIs / (EsIs + EcIc)
    rrc = 1 - rs
    lines.append(f"  Is (鋼骨慣性矩)= {Is:.1f} cm⁴")
    lines.append(f"  Ic (全斷面慣性矩) = b×h³/12 = {b}×{h}³/12 = {Ic:.1f} cm⁴")
    lines.append(f"  Es·Is = {mat.Es:.0f}×{Is:.1f} = {EsIs:.3e}")
    lines.append(f"  Ec·Ic = {mat.Ec:.0f}×{Ic:.1f} = {EcIc:.3e}")
    lines.append(f"  r_s  = {EsIs:.3e}/({EsIs:.3e}+{EcIc:.3e}) = {rs:.4f}")
    lines.append(f"  r_rc = 1 - r_s = {rrc:.4f}")

    Pu_s  = rs  * Pu
    Pu_rc = rrc * Pu
    Mu_s  = rs  * Mu
    Mu_rc = rrc * Mu
    lines.append(f"\n  Pu_s  = r_s × Pu  = {rs:.4f}×{Pu:.2f} = {Pu_s:.2f} tf")
    lines.append(f"  Pu_rc = r_rc× Pu  = {rrc:.4f}×{Pu:.2f} = {Pu_rc:.2f} tf")
    lines.append(f"  Mu_s  = r_s × Mu  = {rs:.4f}×{Mu:.2f} = {Mu_s:.2f} tf-m")
    lines.append(f"  Mu_rc = r_rc× Mu  = {rrc:.4f}×{Mu:.2f} = {Mu_rc:.2f} tf-m")

    lines.append("\n【五、鋼骨P-M交互作用】(規範 7.3.1 AISC LRFD)")
    Pns = mat.fy_steel * A_steel / 1000
    Mns = mat.fy_steel * steel.Zx / 1e6
    lines.append(f"  φPns = 0.9×Fys×As = 0.9×{mat.fy_steel:.0f}×{A_steel:.2f}/1000 = {0.9*Pns:.2f} tf")
    lines.append(f"  φMns = 0.9×Fys×Zs = 0.9×{mat.fy_steel:.0f}×{steel.Zx:.1f}/10⁶ = {0.9*Mns:.3f} tf-m")
    ratio_pu_pns = Pu_s / (0.9 * Pns) if Pns > 0 else 0
    if ratio_pu_pns >= 0.2:
        chk_s = Pu_s / (0.9 * Pns) + Mu_s / (0.9 * Mns)
        lines.append(f"  Pu_s/(φPns) = {ratio_pu_pns:.3f} ≥ 0.2，採用:")
        lines.append(f"  Pu_s/(φPns) + Mu_s/(φMns) ≤ 1.0")
        lines.append(f"  {Pu_s:.2f}/{0.9*Pns:.2f} + {Mu_s:.2f}/{0.9*Mns:.3f} = {chk_s:.3f}")
    else:
        chk_s = Pu_s / (1.8 * Pns) + Mu_s / (0.9 * Mns)
        lines.append(f"  Pu_s/(φPns) = {ratio_pu_pns:.3f} < 0.2，採用:")
        lines.append(f"  Pu_s/(1.8Pns) + Mu_s/(φMns) ≤ 1.0")
        lines.append(f"  {Pu_s:.2f}/{1.8*Pns:.2f} + {Mu_s:.2f}/{0.9*Mns:.3f} = {chk_s:.3f}")
    ok_s = "✓ OK" if chk_s <= 1.0 else "✗ NG"
    lines.append(f"  鋼骨P-M比值 = {chk_s:.3f} → {ok_s}")

    lines.append("\n【六、RC部分P-M交互作用】(規範 7.3.2 ACI 318)")
    d_rc = h - cover
    a2 = As * mat.fy_rebar / (0.85 * mat.fc * b)
    Mn_rc = As * mat.fy_rebar * (d_rc - a2/2) / 1e6
    lines.append(f"  d = h - cover = {h} - {cover} = {d_rc:.1f} cm")
    lines.append(f"  a = As·Fy/(0.85·fc'·b) = {As:.2f}×{mat.fy_rebar:.0f}/(0.85×{mat.fc:.0f}×{b})")
    lines.append(f"    = {a2:.3f} cm")
    lines.append(f"  Mn_rc = As·Fy·(d-a/2) = {As:.2f}×{mat.fy_rebar:.0f}×({d_rc:.1f}-{a2:.3f}/2)/10⁶")
    lines.append(f"        = {Mn_rc:.3f} tf-m")
    lines.append(f"  φPn_rc = 0.65×{Pn_rc:.2f} = {0.65*Pn_rc:.2f} tf")
    ratio_pu_pnrc = Pu_rc / (0.65 * Pn_rc) if Pn_rc > 0 else 0
    if ratio_pu_pnrc >= 0.1:
        chk_r = Pu_rc / (0.65 * Pn_rc) + Mu_rc / (0.9 * Mn_rc)
        lines.append(f"  Pu_rc/(φPn_rc) = {ratio_pu_pnrc:.3f} ≥ 0.1，採用:")
        lines.append(f"  Pu_rc/(φPn_rc) + Mu_rc/(φMn_rc) ≤ 1.0")
        lines.append(f"  {Pu_rc:.2f}/{0.65*Pn_rc:.2f} + {Mu_rc:.2f}/{0.9*Mn_rc:.3f} = {chk_r:.3f}")
    else:
        chk_r = Pu_rc / (1.3 * Pn_rc) + Mu_rc / (0.9 * Mn_rc)
        lines.append(f"  Pu_rc/(φPn_rc) = {ratio_pu_pnrc:.3f} < 0.1，採用:")
        lines.append(f"  Pu_rc/(1.3Pn_rc) + Mu_rc/(φMn_rc) ≤ 1.0")
        lines.append(f"  {Pu_rc:.2f}/{1.3*Pn_rc:.2f} + {Mu_rc:.2f}/{0.9*Mn_rc:.3f} = {chk_r:.3f}")
    ok_r = "✓ OK" if chk_r <= 1.0 else "✗ NG"
    lines.append(f"  RC部分P-M比值 = {chk_r:.3f} → {ok_r}")

    is_safe = chk_s <= 1.0 and chk_r <= 1.0 and Pu <= phi_Pn
    lines.append("\n【七、軸力檢核】")
    ok_pu = "✓ OK" if Pu <= phi_Pn else "✗ NG"
    lines.append(f"  Pu = {Pu:.2f} tf {'≤' if Pu<=phi_Pn else '>'} φPn = {phi_Pn:.2f} tf → {ok_pu}")

    lines.append("\n" + "=" * 60)
    lines.append(f"  結論：{'設計安全 ✓' if is_safe else '設計不足 ✗，請加大斷面或配筋'}")
    lines.append("=" * 60)

    result = {
        'phi_Pn': phi_Pn, 'Pn_rc': Pn_rc, 'Pn_s': Pn_s,
        'Ac': Ac, 'rs': rs, 'rrc': rrc,
        'Pu_s': Pu_s, 'Pu_rc': Pu_rc, 'Mu_s': Mu_s, 'Mu_rc': Mu_rc,
        'Pns': Pns, 'Mns': Mns, 'Mn_rc': Mn_rc,
        'chk_s': chk_s, 'chk_r': chk_r, 'is_safe': is_safe,
        'd_rc': d_rc, 'a': a2, 'Ic': Ic, 'Is': Is
    }
    return '\n'.join(lines), result


# ============================================================
# P-M 曲線生成
# ============================================================
def gen_pm_curve(mat, steel, b, h, cover, As, pts=60):
    bf_cm = steel.bf / 10
    d_cm  = steel.d  / 10
    tf_cm = steel.tf / 10
    tw_cm = steel.tw / 10
    Ac = b * h - steel.A
    d_rc = h - cover
    Pmax_t = -(mat.fy_rebar * As + mat.fy_steel * steel.A) / 1000
    Pmax_c = (0.85 * mat.fc * Ac + mat.fy_rebar * As + mat.fy_steel * steel.A) / 1000
    curve = []
    for i in range(pts + 1):
        r = i / pts
        P = Pmax_t + (Pmax_c - Pmax_t) * r
        if 0.1 < r < 0.9:
            M = (0.5 * As * mat.fy_rebar * (d_rc - cover) / 1e6
                 + 0.5 * mat.fy_steel * steel.Zx / 1e6) * math.sin(r * math.pi)
        else:
            M = 0
        curve.append((P, M))
    return curve


# ============================================================
# 配筋圖 - SRC 梁 (依圖C5.2.1)
# ============================================================
def draw_beam_section(fig, ax, steel: SteelSection, b, h, cover,
                      top_rebars, bot_rebars, top_size, bot_size):
    """
    依規範圖C5.2.1 包覆型SRC梁斷面配筋示意
    """
    ax.set_aspect('equal')
    ax.set_xlim(-b/2 - 5, b/2 + 5)
    ax.set_ylim(-h/2 - 5, h/2 + 5)
    ax.axis('off')

    # 混凝土斷面 (灰色)
    conc = Rectangle((-b/2, -h/2), b, h, fc='#D0D0D0', ec='black', lw=2, zorder=1)
    ax.add_patch(conc)

    # 箍筋 (虛線框)
    stir_off = cover - 0.5
    stir = Rectangle((-b/2 + stir_off, -h/2 + stir_off),
                     b - 2*stir_off, h - 2*stir_off,
                     fc='none', ec='black', lw=1.2, ls='--', zorder=2)
    ax.add_patch(stir)

    # 鋼骨 (深灰)
    s_d = steel.d / 10   # mm→cm
    s_bf= steel.bf/ 10
    s_tf= steel.tf/ 10
    s_tw= steel.tw/ 10

    if steel.section_type == 'H':
        # 上翼板
        ax.add_patch(Rectangle((-s_bf/2, s_d/2 - s_tf), s_bf, s_tf,
                               fc='#404040', ec='black', lw=1, zorder=3))
        # 下翼板
        ax.add_patch(Rectangle((-s_bf/2, -s_d/2), s_bf, s_tf,
                               fc='#404040', ec='black', lw=1, zorder=3))
        # 腹板
        ax.add_patch(Rectangle((-s_tw/2, -s_d/2 + s_tf), s_tw, s_d - 2*s_tf,
                               fc='#404040', ec='black', lw=1, zorder=3))

    # 鋼筋 (紅色=上筋，藍色=下筋)
    rr = REBAR_DB.get(top_size, 1.27) ** 0.5 * 0.56  # 近似半徑cm
    rb = REBAR_DB.get(bot_size, 1.27) ** 0.5 * 0.56

    # 上部鋼筋
    top_y = h/2 - cover
    spacing = (b - 2*cover) / max(top_rebars - 1, 1)
    for i in range(top_rebars):
        xp = -b/2 + cover + i * spacing if top_rebars > 1 else 0
        ax.add_patch(Circle((xp, top_y), rr, fc='#CC0000', ec='black', lw=0.8, zorder=4))

    # 下部鋼筋
    bot_y = -h/2 + cover
    spacing = (b - 2*cover) / max(bot_rebars - 1, 1)
    for i in range(bot_rebars):
        xp = -b/2 + cover + i * spacing if bot_rebars > 1 else 0
        ax.add_patch(Circle((xp, bot_y), rb, fc='#0044CC', ec='black', lw=0.8, zorder=4))

    # 標注尺寸
    ax.annotate('', xy=(b/2, -h/2 - 3), xytext=(-b/2, -h/2 - 3),
                arrowprops=dict(arrowstyle='<->', color='black'))
    ax.text(0, -h/2 - 4, f'b = {b} cm', ha='center', va='top', fontsize=9)
    ax.annotate('', xy=(b/2 + 3, h/2), xytext=(b/2 + 3, -h/2),
                arrowprops=dict(arrowstyle='<->', color='black'))
    ax.text(b/2 + 4.5, 0, f'h = {h} cm', ha='left', va='center', fontsize=9, rotation=90)

    ax.set_title(f'圖C5.2.1 包覆型SRC梁斷面配筋示意\n'
                 f'b×h={b}×{h}cm  鋼骨:{steel.name}\n'
                 f'上筋:{top_rebars}-{top_size}  下筋:{bot_rebars}-{bot_size}',
                 fontsize=10, fontweight='bold')

    # 圖例
    legend_elements = [
        mpatches.Patch(fc='#D0D0D0', ec='black', label='混凝土'),
        mpatches.Patch(fc='#404040', ec='black', label='型鋼'),
        mpatches.Patch(fc='#CC0000', ec='black', label=f'上筋 {top_rebars}-{top_size}'),
        mpatches.Patch(fc='#0044CC', ec='black', label=f'下筋 {bot_rebars}-{bot_size}'),
    ]
    ax.legend(handles=legend_elements, loc='lower right', fontsize=8)


# ============================================================
# 配筋圖 - SRC 柱 (依圖C6.2.1)
# ============================================================
def draw_column_section(fig, ax, steel: SteelSection, b, h, cover,
                        num_bars, bar_size):
    """
    依規範圖C6.2.1 包覆型SRC柱斷面配筋示意
    """
    ax.set_aspect('equal')
    ax.set_xlim(-b/2 - 5, b/2 + 5)
    ax.set_ylim(-h/2 - 5, h/2 + 5)
    ax.axis('off')

    # 混凝土斷面
    conc = Rectangle((-b/2, -h/2), b, h, fc='#D0D0D0', ec='black', lw=2, zorder=1)
    ax.add_patch(conc)

    # 箍筋
    stir_off = cover - 0.5
    stir = Rectangle((-b/2 + stir_off, -h/2 + stir_off),
                     b - 2*stir_off, h - 2*stir_off,
                     fc='none', ec='black', lw=1.2, ls='--', zorder=2)
    ax.add_patch(stir)

    # 鋼骨
    s_d = steel.d / 10
    s_bf= steel.bf / 10
    s_tf= steel.tf / 10
    s_tw= steel.tw / 10

    if steel.section_type == 'BOX':
        # 外框
        ax.add_patch(Rectangle((-s_bf/2, -s_d/2), s_bf, s_d,
                               fc='#404040', ec='black', lw=1, zorder=3))
        # 中空內部
        ax.add_patch(Rectangle((-s_bf/2 + s_tw, -s_d/2 + s_tf),
                               s_bf - 2*s_tw, s_d - 2*s_tf,
                               fc='#D0D0D0', ec='none', zorder=4))
    else:
        ax.add_patch(Rectangle((-s_bf/2, s_d/2 - s_tf), s_bf, s_tf,
                               fc='#404040', ec='black', lw=1, zorder=3))
        ax.add_patch(Rectangle((-s_bf/2, -s_d/2), s_bf, s_tf,
                               fc='#404040', ec='black', lw=1, zorder=3))
        ax.add_patch(Rectangle((-s_tw/2, -s_d/2 + s_tf), s_tw, s_d - 2*s_tf,
                               fc='#404040', ec='black', lw=1, zorder=3))

    # 縱向鋼筋 (周圍均勻分布)
    rr = REBAR_DB.get(bar_size, 2.87) ** 0.5 * 0.56
    margin = cover
    n_side = num_bars // 4  # 每側
    bar_positions = []
    # 四邊均勻分布
    corners = [
        (-b/2 + margin, -h/2 + margin),
        ( b/2 - margin, -h/2 + margin),
        ( b/2 - margin,  h/2 - margin),
        (-b/2 + margin,  h/2 - margin),
    ]
    # 簡單均勻分布
    total = num_bars
    pts_per_side = total // 4
    rem = total % 4

    sides = []
    for s in range(4):
        n = pts_per_side + (1 if s < rem else 0)
        x0, y0 = corners[s]
        x1, y1 = corners[(s+1) % 4]
        for j in range(n):
            t = j / (n) if n > 1 else 0.5
            sides.append((x0 + t*(x1-x0), y0 + t*(y1-y0)))

    for (xp, yp) in sides:
        ax.add_patch(Circle((xp, yp), rr, fc='#CC0000', ec='black', lw=0.8, zorder=5))

    # 尺寸標注
    ax.annotate('', xy=(b/2, -h/2 - 3), xytext=(-b/2, -h/2 - 3),
                arrowprops=dict(arrowstyle='<->', color='black'))
    ax.text(0, -h/2 - 4, f'b = {b} cm', ha='center', va='top', fontsize=9)
    ax.annotate('', xy=(b/2 + 3, h/2), xytext=(b/2 + 3, -h/2),
                arrowprops=dict(arrowstyle='<->', color='black'))
    ax.text(b/2 + 4.5, 0, f'h = {h} cm', ha='left', va='center', fontsize=9, rotation=90)

    ax.set_title(f'圖C6.2.1 包覆型SRC柱斷面配筋示意\n'
                 f'b×h={b}×{h}cm  鋼骨:{steel.name}\n'
                 f'縱筋:{num_bars}-{bar_size}',
                 fontsize=10, fontweight='bold')

    legend_elements = [
        mpatches.Patch(fc='#D0D0D0', ec='black', label='混凝土'),
        mpatches.Patch(fc='#404040', ec='black', label='型鋼'),
        mpatches.Patch(fc='#CC0000', ec='black', label=f'縱筋 {num_bars}-{bar_size}'),
    ]
    ax.legend(handles=legend_elements, loc='lower right', fontsize=8)


# ============================================================
# Streamlit UI
# ============================================================
st.set_page_config(
    page_title="SRC梁柱設計 - 台灣規範",
    page_icon="🏗️",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
body { font-family: 'Microsoft JhengHei', sans-serif; }
.stButton > button { background-color: #1a3c6d; color: white; border-radius: 6px; }
.report-box { background: #f8f9fa; border: 1px solid #dee2e6; border-radius: 8px;
              padding: 16px; font-family: monospace; font-size: 13px; white-space: pre-wrap; }
</style>
""", unsafe_allow_html=True)

st.title("🏗️ SRC 鋼骨鋼筋混凝土結構設計程式")
st.markdown("**宏利工程顧問有限公司**")
st.markdown(f"**依據：鋼骨鋼筋混凝土構造設計規範與解說（Taiwan SRC Code）** ｜ 日期：{datetime.date.today().strftime('%Y-%m-%d')}")
st.markdown("---")

# 側邊欄：材料選擇
with st.sidebar:
    st.header("📋 材料設計參數")
    fy_steel = st.number_input("鋼骨 Fys (kgf/cm²)", value=2800, min_value=2100, max_value=4500, step=100)
    fy_rebar = st.selectbox("鋼筋降伏強度 Fy", [2800, 4200, 5600],
                            format_func=lambda x: f"SD{int(x/28.6):.0f} ({x} kgf/cm²)", index=1)
    fc = st.selectbox("混凝土 fc' (kgf/cm²)", [210, 280, 350, 420], index=1)
    mat = Material(fy_steel=fy_steel, fy_rebar=fy_rebar, fc=fc)
    st.info(f"Ec = {mat.Ec:.0f} kgf/cm²")
    st.markdown("---")
    st.markdown("**鋼筋斷面積表**")
    for n, a in REBAR_DB.items():
        st.markdown(f"- {n}: {a} cm²")

# 主分頁
tab_beam, tab_col, tab_pm, tab_rebar = st.tabs([
    "📐 SRC梁設計", "🏛️ SRC柱設計", "📈 P-M曲線", "🖼️ 配筋圖"
])

# ===== 梁設計 =====
with tab_beam:
    st.header("SRC 梁設計計算書")
    st.caption("規範：5.4 強度疊加法（Superposition Method）")
    c1, c2 = st.columns([1, 2])
    with c1:
        b_stl = steel_section_selector('beam', filter_type='H')
        bw = st.number_input("梁寬 b (cm)", value=40, min_value=20, max_value=150, key='bw')
        bh = st.number_input("梁深 h (cm)", value=80, min_value=30, max_value=300, key='bh')
        bc = st.number_input("保護層 (cm)", value=5, min_value=3, max_value=10, key='bc')
        st.markdown("**上部鋼筋**")
        c3, c4 = st.columns(2)
        with c3: top_n = st.number_input("根數", min_value=2, value=2, key='btn')
        with c4: top_s = st.selectbox("規格", list(REBAR_DB.keys()), index=3, key='bts')
        st.markdown("**下部鋼筋**")
        c5, c6 = st.columns(2)
        with c5: bot_n = st.number_input("根數", min_value=2, value=3, key='bbn')
        with c6: bot_s = st.selectbox("規格", list(REBAR_DB.keys()), index=3, key='bbs')
        As_top = top_n * REBAR_DB[top_s]
        As_bot = bot_n * REBAR_DB[bot_s]
        st.info(f"上筋 As = {As_top:.2f} cm²\n下筋 As = {As_bot:.2f} cm²")
        Mu_b = st.number_input("設計彎矩 Mu (tf-m)", value=20.0, key='Mu_b')
    with c2:
        if st.button("🔢 計算梁設計", type="primary", key='btn_beam'):
            report, res = calc_beam(mat, b_stl, bw, bh, bc, As_top, As_bot, Mu_b)
            st.markdown(f'<div class="report-box">{report}</div>', unsafe_allow_html=True)
            st.download_button("📥 下載計算書", data=report,
                               file_name="SRC梁計算書.txt", mime="text/plain")

# ===== 柱設計 =====
with tab_col:
    st.header("SRC 柱設計計算書")
    st.caption("規範：6.4 軸力強度 / 7.3 P-M交互作用（相對剛度分配法）")
    c1, c2 = st.columns([1, 2])
    with c1:
        c_stl = steel_section_selector('col', filter_type='all',
                                       default_name='BOX300x300x10x10')
        cw = st.number_input("柱寬 b (cm)", value=60, min_value=30, max_value=200, key='cw')
        ch = st.number_input("柱深 h (cm)", value=60, min_value=30, max_value=200, key='ch')
        cc = st.number_input("保護層 (cm)", value=5, min_value=3, max_value=10, key='cc')
        c3, c4 = st.columns(2)
        with c3: c_num = st.number_input("縱筋根數", min_value=4, value=8, key='c_num')
        with c4: c_siz = st.selectbox("縱筋規格", list(REBAR_DB.keys()), index=3, key='c_siz')
        As_col = c_num * REBAR_DB[c_siz]
        st.info(f"As = {As_col:.2f} cm²")
        Pu_c = st.number_input("設計軸力 Pu (tf)", value=200.0, key='Pu_c')
        Mu_c = st.number_input("設計彎矩 Mu (tf-m)", value=30.0, key='Mu_c')
    with c2:
        if st.button("🔢 計算柱設計", type="primary", key='btn_col'):
            report, res = calc_column(mat, c_stl, cw, ch, cc, As_col, Pu_c, Mu_c)
            st.markdown(f'<div class="report-box">{report}</div>', unsafe_allow_html=True)
            st.download_button("📥 下載計算書", data=report,
                               file_name="SRC柱計算書.txt", mime="text/plain")

# ===== P-M 曲線 =====
with tab_pm:
    st.header("📈 SRC 柱 P-M 互制曲線")
    c1, c2 = st.columns([1, 2])
    with c1:
        pm_stl = steel_section_selector('pm', filter_type='all',
                                        default_name='BOX300x300x10x10')
        pm_b = st.number_input("b (cm)", value=60, key='pm_b')
        pm_h = st.number_input("h (cm)", value=60, key='pm_h')
        pm_c = st.number_input("cover (cm)", value=5, key='pm_c')
        c3, c4 = st.columns(2)
        with c3: pm_n = st.number_input("筋數", min_value=4, value=8, key='pm_n')
        with c4: pm_s = st.selectbox("規格", list(REBAR_DB.keys()), index=3, key='pm_s')
        pm_As = pm_n * REBAR_DB[pm_s]
        pm_Pu = st.number_input("設計 Pu (tf)", value=200.0, key='pm_Pu')
        pm_Mu = st.number_input("設計 Mu (tf-m)", value=30.0, key='pm_Mu')
    with c2:
        curve = gen_pm_curve(mat, pm_stl, pm_b, pm_h, pm_c, pm_As)
        Pv = [p[0] for p in curve]
        Mv = [p[1] for p in curve]
        fig, ax = plt.subplots(figsize=(9, 7))
        ax.plot(Mv, Pv, 'b-', lw=2.5, label='P-M 互制曲線')
        ax.scatter([pm_Mu], [pm_Pu], c='red', s=120, zorder=5,
                   label=f'設計點 ({pm_Pu:.0f} tf, {pm_Mu:.0f} tf-m)')
        ax.axhline(0, color='gray', ls='--', lw=0.8)
        ax.axvline(0, color='gray', ls='--', lw=0.8)
        ax.set_xlabel('彎矩 M (tf-m)', fontsize=12)
        ax.set_ylabel('軸力 P (tf)', fontsize=12)
        ax.set_title(f'SRC 柱 P-M 互制曲線\n{pm_stl.name} / {pm_b}×{pm_h}cm / {pm_n}-{pm_s}', fontsize=12)
        ax.legend(fontsize=10)
        ax.grid(alpha=0.3)
        st.pyplot(fig)

# ===== 配筋圖 =====
with tab_rebar:
    st.header("🖼️ 斷面配筋圖")
    st.info("依規範圖C5.2.1（SRC梁）及圖C6.2.1（SRC柱）繪製")
    r_type = st.radio("構件類型", ["SRC 梁", "SRC 柱"], horizontal=True)

    if r_type == "SRC 梁":
        c1, c2 = st.columns([1, 2])
        with c1:
            rb_stl = steel_section_selector('rb', filter_type='H')
            rb_b = st.number_input("梁寬 b (cm)", value=40, key='rb_b')
            rb_h = st.number_input("梁深 h (cm)", value=80, key='rb_h')
            rb_c = st.number_input("保護層 (cm)", value=5, key='rb_c')
            c3, c4 = st.columns(2)
            with c3: rb_tn = st.number_input("上筋數", min_value=2, value=2, key='rb_tn')
            with c4: rb_ts = st.selectbox("上筋規格", list(REBAR_DB.keys()), index=3, key='rb_ts')
            c5, c6 = st.columns(2)
            with c5: rb_bn = st.number_input("下筋數", min_value=2, value=3, key='rb_bn')
            with c6: rb_bs = st.selectbox("下筋規格", list(REBAR_DB.keys()), index=3, key='rb_bs')
        with c2:
            fig, ax = plt.subplots(figsize=(8, 7))
            draw_beam_section(fig, ax, rb_stl, rb_b, rb_h, rb_c,
                              rb_tn, rb_bn, rb_ts, rb_bs)
            plt.tight_layout()
            st.pyplot(fig)
    else:
        c1, c2 = st.columns([1, 2])
        with c1:
            rc_stl = steel_section_selector('rc', filter_type='BOX')
            rc_b = st.number_input("柱寬 b (cm)", value=60, key='rc_b')
            rc_h = st.number_input("柱深 h (cm)", value=60, key='rc_h')
            rc_c = st.number_input("保護層 (cm)", value=5, key='rc_c')
            c3, c4 = st.columns(2)
            with c3: rc_n = st.number_input("縱筋數", min_value=4, value=8, key='rc_n')
            with c4: rc_s = st.selectbox("縱筋規格", list(REBAR_DB.keys()), index=3, key='rc_s')
        with c2:
            fig, ax = plt.subplots(figsize=(8, 7))
            draw_column_section(fig, ax, rc_stl, rc_b, rc_h, rc_c, rc_n, rc_s)
            plt.tight_layout()
            st.pyplot(fig)

st.markdown("---")
st.warning("⚠️ 本程式依據台灣『鋼骨鋼筋混凝土構造設計規範與解說』計算，僅供設計初稿參考，實際設計應經專業結構技師審查確認。")
