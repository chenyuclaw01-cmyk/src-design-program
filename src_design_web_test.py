#!/usr/bin/env python3
"""
SRC 鋼骨鋼筋混凝土結構設計程式
依據：鋼骨鋼筋混凝土構造設計規範與解說 (Taiwan SRC Code)
"""
import streamlit as st
import math
import matplotlib
matplotlib.use('Agg')   # 非互動式後端，適用於 Streamlit / 無 GUI 環境
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import Rectangle, Circle, FancyArrowPatch
import matplotlib.font_manager as fm
import numpy as np
from dataclasses import dataclass
import io
import datetime
import os
import urllib.request

# ── 跨平台中文字體設定 ─────────────────────────────────────────────
# 優先使用系統已有的CJK字體，否則自動下載 Noto Sans TC（靜態版本）
def _setup_cjk_font():
    # 1. 嘗試系統/已安裝字體（Windows / macOS）
    prefer = ['Microsoft JhengHei', 'PingFang TC', 'Noto Sans TC',
              'Noto Sans CJK TC', 'Arial Unicode MS', 'WenQuanYi Zen Hei']
    available = {f.name for f in fm.fontManager.ttflist}
    for name in prefer:
        if name in available:
            matplotlib.rcParams['font.sans-serif'] = [name, 'DejaVu Sans']
            matplotlib.rcParams['axes.unicode_minus'] = False
            return

    # 2. 在 Streamlit Cloud (Linux) 找不到上述字體 → 動態下載 Noto Sans TC
    #    使用固定版本 TTF（無可變字體，URL 不含特殊字元，下載更穩定）
    font_dir  = os.path.join(os.path.expanduser('~'), '.matplotlib_fonts')
    font_path = os.path.join(font_dir, 'NotoSansTC-Regular.ttf')
    if not os.path.exists(font_path):
        os.makedirs(font_dir, exist_ok=True)
        # 主要來源：Google Fonts CDN 靜態連結（固定版本 v36，最穩定）
        _FONT_URLS = [
            ('https://fonts.gstatic.com/s/notosanstc/v36/'
             'nKKQ-GM_FYFRJvXzVXaAPe97P1KHynJFbsJr-E-YGr4.ttf'),
            # 備援：GitHub Noto 字體 Releases 直連（固定 tag，無方括號）
            ('https://github.com/notofonts/noto-cjk/releases/download/'
             'Sans2.004R/NotoSansCJK-Regular.ttc'),
        ]
        for _url in _FONT_URLS:
            try:
                urllib.request.urlretrieve(_url, font_path)
                break   # 下載成功即跳出
            except Exception:
                if os.path.exists(font_path):
                    os.remove(font_path)  # 清除可能損壞的檔案
    if os.path.exists(font_path):
        # 刷新 matplotlib 字體快取，確保新下載的字體被識別
        try:
            fm.fontManager.addfont(font_path)
            # 取得實際字體名稱以正確設定 rcParams
            prop = fm.FontProperties(fname=font_path)
            font_name = prop.get_name()
            matplotlib.rcParams['font.sans-serif'] = [font_name, 'DejaVu Sans']
        except Exception:
            # 萬一無法識別字體名稱，直接以路徑指定
            matplotlib.rcParams['font.sans-serif'] = ['DejaVu Sans']
    matplotlib.rcParams['axes.unicode_minus'] = False

_setup_cjk_font()

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
        # 常重混凝土彈性模數：Ec = 15,000√f'c (kgf/cm²)，依台灣SRC設計規範
        self.Ec = round(15000 * math.sqrt(self.fc), 0)

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

# 依據 JIS G 3192 (台灣採用) 及台灣鋼結構設計手冊
# 格式：name, type, bf(mm), tf(mm), tw(mm), d(mm), Ix(cm⁴), Zx(cm³), A(cm²)
STEEL_DB = {
    # ── HN 中翼型（梁常用）────────────────────────────────────
    'HN300×150×6.5×9':  SteelSection('HN300×150×6.5×9',  'H', 150,  9,  6.5, 300,  7210,  509,  46.78),
    'HN350×175×7×11':   SteelSection('HN350×175×7×11',   'H', 175, 11,  7.0, 350, 13600,  819,  62.91),
    'HN400×200×8×13':   SteelSection('HN400×200×8×13',   'H', 200, 13,  8.0, 400, 23700, 1250,  84.12),
    'HN450×200×9×14':   SteelSection('HN450×200×9×14',   'H', 200, 14,  9.0, 450, 33500, 1570,  96.76),
    'HN500×200×10×16':  SteelSection('HN500×200×10×16',  'H', 200, 16, 10.0, 500, 47800, 2020, 114.2 ),
    'HN600×200×11×17':  SteelSection('HN600×200×11×17',  'H', 200, 17, 11.0, 600, 92800, 3270, 134.4 ),
    # ── HW 寬翼型（梁柱皆可）──────────────────────────────────
    'HW200×200×8×12':   SteelSection('HW200×200×8×12',   'H', 200, 12,  8.0, 200,  4730,  523,  63.53),
    'HW250×250×9×14':   SteelSection('HW250×250×9×14',   'H', 250, 14,  9.0, 250, 10800,  960,  91.43),
    'HW300×300×10×15':  SteelSection('HW300×300×10×15',  'H', 300, 15, 10.0, 300, 20500, 1500, 119.8 ),
    'HW350×350×12×19':  SteelSection('HW350×350×12×19',  'H', 350, 19, 12.0, 350, 40300, 2520, 173.9 ),
    'HW400×400×13×21':  SteelSection('HW400×400×13×21',  'H', 400, 21, 13.0, 400, 66600, 3650, 218.7 ),
    # ── BOX 箱型鋼（柱常用）───────────────────────────────────
    'BOX200×200×9':     SteelSection('BOX200×200×9',   'BOX', 200,  9,  9, 200,  4190,  493,  68.76),
    'BOX250×250×9':     SteelSection('BOX250×250×9',   'BOX', 250,  9,  9, 250,  8410,  789,  86.76),
    'BOX300×300×9':     SteelSection('BOX300×300×9',   'BOX', 300,  9,  9, 300, 14780, 1142, 104.76),
    'BOX350×350×12':    SteelSection('BOX350×350×12',  'BOX', 350, 12, 12, 350, 30930, 2057, 162.24),
    'BOX400×400×16':    SteelSection('BOX400×400×16',  'BOX', 400, 16, 16, 400, 60500, 3533, 245.76),
    'BOX500×500×19':    SteelSection('BOX500×500×19',  'BOX', 500, 19, 19, 500,141200, 6607, 365.56),
}

REBAR_DB = {
    'D10': 0.71, 'D13': 1.27, 'D16': 2.01, 'D19': 2.87,
    'D22': 3.87, 'D25': 5.07, 'D29': 6.51, 'D32': 8.04
}

# CNS 560 鋼筋強度等級（W = 可熔接性，fy 單位：kgf/cm²）
REBAR_GRADE = {
    'SD280W / SD280  (2800 kgf/cm²)': 2800,
    'SD420W / SD420  (4200 kgf/cm²)': 4200,
    'SD490W / SD490  (4900 kgf/cm²)': 4900,
    'SD550W / SD550  (5500 kgf/cm²)': 5500,
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
# 鋼骨斷面寬厚比檢核
# ============================================================
def check_width_thickness(mat: Material, steel: SteelSection) -> tuple:
    """
    寬厚比檢核 (依台灣SRC設計規範 / AISC LRFD 緊密斷面限值)
    H型鋼：翼板 λf = bf/(2tf)，腹板 λw = (d-2tf)/tw
    BOX型鋼：板件 λ = (b-2t)/t
    """
    lines = []
    lines.append("=" * 60)
    lines.append("鋼骨斷面寬厚比檢核")
    lines.append("依據：SRC設計規範第3章 / AISC LRFD 緊密斷面限值")
    lines.append("=" * 60)

    E  = mat.Es
    Fy = mat.fy_steel
    r  = math.sqrt(E / Fy)   # √(Es/Fys)

    bf_cm = steel.bf / 10
    d_cm  = steel.d  / 10
    tf_cm = steel.tf / 10
    tw_cm = steel.tw / 10

    lines.append(f"  鋼骨斷面  : {steel.name}  ({steel.section_type}型)")
    lines.append(f"  Es = {E:.0f} kgf/cm²，Fys = {Fy:.0f} kgf/cm²")
    lines.append(f"  √(Es/Fys) = {r:.3f}")

    is_ok = True

    if steel.section_type == 'H':
        # ── 翼板寬厚比 ────────────────────────────────────────
        lam_f   = bf_cm / (2 * tf_cm)
        lam_pf  = 0.38 * r    # 緊密斷面上限
        lam_rf  = 1.00 * r    # 非緊密斷面上限
        if lam_f <= lam_pf:
            tag_f = "✓ 緊密斷面"
        elif lam_f <= lam_rf:
            tag_f = "△ 非緊密斷面"
            is_ok = False
        else:
            tag_f = "✗ 細長斷面"
            is_ok = False

        lines.append("\n【翼板寬厚比 λf = bf/(2tf)】")
        lines.append(f"  bf = {bf_cm:.1f} cm，tf = {tf_cm:.1f} cm")
        lines.append(f"  λf  = {bf_cm:.1f} / (2×{tf_cm:.1f}) = {lam_f:.2f}")
        lines.append(f"  λpf = 0.38×√(Es/Fys) = 0.38×{r:.3f} = {lam_pf:.2f}  ← 緊密斷面限值")
        lines.append(f"  λrf = 1.00×√(Es/Fys) = 1.00×{r:.3f} = {lam_rf:.2f}  ← 非緊密斷面限值")
        lines.append(f"  λf = {lam_f:.2f}  → {tag_f}")

        # ── 腹板寬厚比 ────────────────────────────────────────
        lam_w   = (d_cm - 2 * tf_cm) / tw_cm
        lam_pw  = 3.76 * r   # 梁（純彎）緊密斷面上限
        lam_rw  = 5.70 * r   # 非緊密斷面上限
        if lam_w <= lam_pw:
            tag_w = "✓ 緊密斷面"
        elif lam_w <= lam_rw:
            tag_w = "△ 非緊密斷面"
            is_ok = False
        else:
            tag_w = "✗ 細長斷面"
            is_ok = False

        lines.append("\n【腹板寬厚比 λw = (d-2tf)/tw】")
        lines.append(f"  d = {d_cm:.1f} cm，tf = {tf_cm:.1f} cm，tw = {tw_cm:.1f} cm")
        lines.append(f"  λw  = ({d_cm:.1f}-2×{tf_cm:.1f}) / {tw_cm:.1f} = {lam_w:.2f}")
        lines.append(f"  λpw = 3.76×√(Es/Fys) = 3.76×{r:.3f} = {lam_pw:.2f}  ← 梁緊密斷面限值")
        lines.append(f"  λrw = 5.70×√(Es/Fys) = 5.70×{r:.3f} = {lam_rw:.2f}  ← 非緊密斷面限值")
        lines.append(f"  λw = {lam_w:.2f}  → {tag_w}")

    else:  # BOX
        # ── 箱型斷面：寬側板件（b方向）────────────────────────
        lam_b   = (bf_cm - 2 * tw_cm) / tw_cm
        lam_pb  = 1.12 * r   # 緊密斷面上限
        lam_rb  = 1.40 * r   # 非緊密斷面上限
        if lam_b <= lam_pb:
            tag_b = "✓ 緊密斷面"
        elif lam_b <= lam_rb:
            tag_b = "△ 非緊密斷面"
            is_ok = False
        else:
            tag_b = "✗ 細長斷面"
            is_ok = False

        lines.append("\n【箱形斷面板件寬厚比 (b-2t)/t】")
        lines.append(f"  bf = {bf_cm:.1f} cm，tw = {tw_cm:.1f} cm")
        lines.append(f"  λb  = ({bf_cm:.1f}-2×{tw_cm:.1f}) / {tw_cm:.1f} = {lam_b:.2f}")
        lines.append(f"  λpb = 1.12×√(Es/Fys) = 1.12×{r:.3f} = {lam_pb:.2f}  ← 緊密斷面限值")
        lines.append(f"  λrb = 1.40×√(Es/Fys) = 1.40×{r:.3f} = {lam_rb:.2f}  ← 非緊密斷面限值")
        lines.append(f"  λb = {lam_b:.2f}  → {tag_b}")

        # ── 箱型斷面：深側板件（d方向）────────────────────────
        lam_d   = (d_cm - 2 * tf_cm) / tf_cm
        if lam_d <= lam_pb:
            tag_d = "✓ 緊密斷面"
        elif lam_d <= lam_rb:
            tag_d = "△ 非緊密斷面"
            is_ok = False
        else:
            tag_d = "✗ 細長斷面"
            is_ok = False

        lines.append("\n【箱形斷面板件深厚比 (d-2t)/t】")
        lines.append(f"  d = {d_cm:.1f} cm，tf = {tf_cm:.1f} cm")
        lines.append(f"  λd  = ({d_cm:.1f}-2×{tf_cm:.1f}) / {tf_cm:.1f} = {lam_d:.2f}")
        lines.append(f"  λpb = {lam_pb:.2f}，λrb = {lam_rb:.2f}")
        lines.append(f"  λd = {lam_d:.2f}  → {tag_d}")

    lines.append("\n" + "=" * 60)
    lines.append(f"  寬厚比判定：{'緊密斷面 ✓  可充分發展塑性彎矩' if is_ok else '非緊密或細長斷面 ✗  強度需折減，請改用較厚板件'}")
    lines.append("=" * 60)
    return '\n'.join(lines), is_ok


# ============================================================
# SRC 梁設計 (規範第5章)
# ============================================================
def calc_beam(mat: Material, steel: SteelSection, b, h, cover, As_top, As_bot, Mu,
              Vu: float = 0.0, Av_s: float = 0.0, s_s: float = 15.0):
    """
    規範 5.4 強度疊加法 / φMn = φ(Mns + Mnrc)
    """
    # 進行計算
    Mns = steel.Zx * mat.fy_steel / 1e5
    phi_Mns = 0.9 * Mns
    
    d_rc = h - cover
    As = As_bot
    a = As * mat.fy_rebar / (0.85 * mat.fc * b)
    Mnrc = As * mat.fy_rebar * (d_rc - a / 2) / 1e5
    phi_Mnrc = 0.9 * Mnrc
    phi_Mn = phi_Mns + phi_Mnrc
    
    rho = As / (b * d_rc)
    rho_min = max(14.0 / mat.fy_rebar, 0.8 * math.sqrt(mat.fc) / mat.fy_rebar)
    
    # 剪力計算
    s_d_cm = steel.d / 10
    s_tw_cm = steel.tw / 10
    s_tf_cm = steel.tf / 10
    Aw = s_tw_cm * (s_d_cm - 2 * s_tf_cm)
    Vns = 0.6 * mat.fy_steel * Aw / 1000
    phi_Vns = 0.9 * Vns
    Vc = 0.53 * math.sqrt(mat.fc) * b * d_rc / 1000
    phi_Vc = 0.75 * Vc
    Vs = (Av_s * mat.fy_rebar * d_rc / s_s / 1000) if (Av_s > 0 and s_s > 0) else 0.0
    phi_Vs = 0.75 * Vs
    phi_Vn = phi_Vns + phi_Vc + phi_Vs
    
    # 寬厚比
    wt_report, wt_ok = check_width_thickness(mat, steel)
    
    # 判定
    ok_mu = phi_Mn >= Mu
    ok_rho = rho >= rho_min
    ok_vu = (Vu <= 0 or Vu <= phi_Vn)
    is_safe = ok_mu and ok_rho and ok_vu and wt_ok
    
    # 組裝報告
    lines = []
    lines.append("=" * 60)
    lines.append("SRC 梁設計分析報告 (分析結果摘要)")
    lines.append("=" * 60)
    lines.append(f"  ● 彎矩強度：Mu={Mu:.2f} / φMn={phi_Mn:.2f} (tf-m) -> D/C={Mu/phi_Mn if phi_Mn>0 else 0:.3f} {'✓' if ok_mu else '✗'}")
    if Vu > 0:
        lines.append(f"  ● 剪力強度：Vu={Vu:.2f} / φVn={phi_Vn:.2f} (tf)   -> D/C={Vu/phi_Vn if phi_Vn>0 else 0:.3f} {'✓' if ok_vu else '✗'}")
    lines.append(f"  ● 最小鋼筋：ρ={rho:.5f} / ρmin={rho_min:.5f}      -> {'✓' if ok_rho else '✗'}")
    lines.append(f"  ● 鋼骨寬厚比：{ '✓ 合格' if wt_ok else '✗ 不合格' }")
    lines.append(f"\n  結論：{'設計安全 ✓' if is_safe else '設計不足 ✗，請檢視詳細計算'}")
    lines.append("=" * 60)
    
    lines.append("\n【詳細計算過程】")
    lines.append(f"\n1. 設計條件")
    lines.append(f"   鋼骨: {steel.name}, b/h: {b}/{h} cm, dc: {cover} cm")
    lines.append(f"   Mu: {Mu:.2f} tf-m, Vu: {Vu:.2f} tf")
    lines.append(f"   Fys: {mat.fy_steel:.0f}, Fy: {mat.fy_rebar:.0f}, fc': {mat.fc:.0f} (kgf/cm²)")
    
    lines.append(f"\n2. 彎矩強度 (疊加法)")
    lines.append(f"   φMns = 0.9 × (Zs×Fys) = 0.9 × ({steel.Zx:.1f}×{mat.fy_steel:.0f}/10⁵) = {phi_Mns:.3f} tf-m")
    lines.append(f"   a = As×Fy/(0.85×fc'×b) = {As:.2f}×{mat.fy_rebar:.0f}/(0.85×{mat.fc:.0f}×{b}) = {a:.3f} cm")
    lines.append(f"   φMnrc = 0.9 × As×Fy×(d-a/2) = 0.9×{Mnrc:.3f} = {phi_Mnrc:.3f} tf-m")
    lines.append(f"   φMn = {phi_Mns:.3f} + {phi_Mnrc:.3f} = {phi_Mn:.3f} tf-m")
    
    lines.append(f"\n3. 剪力強度 (疊加法)")
    lines.append(f"   φVns = 0.9 × (0.6×Fys×Aw) = 0.9 × (0.6×{mat.fy_steel:.0f}×{Aw:.2f}/1000) = {phi_Vns:.3f} tf")
    lines.append(f"   φVc = 0.75 × (0.53√fc'×b×d/1000) = {phi_Vc:.3f} tf")
    lines.append(f"   φVs = 0.75 × (Av×Fyr×d/s/1000) = {phi_Vs:.3f} tf")
    lines.append(f"   φVn = {phi_Vn:.3f} tf")
    
    lines.append("\n4. 鋼骨寬厚比檢核")
    lines.append(wt_report)

    result = {
        'Mns': Mns, 'Mnrc': Mnrc, 'phi_Mn': phi_Mn,
        'phi_Vn': phi_Vn, 'ok': is_safe, 'wt_ok': wt_ok
    }
    return '\n'.join(lines), result


# ============================================================
# SRC 柱設計 (規範第6、7章)
# ============================================================
def calc_column(mat: Material, steel: SteelSection, b, h, cover, As, Pu, Mu,
                Vu: float = 0.0, Av_s: float = 0.0, s_s: float = 15.0):
    """
    規範 6.4 軸力強度 + 7.3 P-M交互作用 + 7.4 剪力強度疊加
    採用相對剛度分配法
    """
    lines = []
    lines.append("=" * 60)
    lines.append("SRC 柱設計計算書")
    lines.append("依據：鋼骨鋼筋混凝土構造設計規範與解說 第6、7章")
    lines.append("=" * 60)

    # ── 斷面幾何（前置計算） ────────────────────────────────
    bf_cm   = steel.bf / 10
    d_cm    = steel.d  / 10
    tf_cm   = steel.tf / 10
    tw_cm   = steel.tw / 10
    A_gross = b * h
    A_steel = steel.A
    Ac      = A_gross - A_steel
    d_rc    = h - cover

    lines.append("\n【一、設計條件】")
    lines.append(f"  鋼骨斷面    : {steel.name}  ({steel.section_type}型)")
    lines.append(f"  柱寬  b     : {b} cm")
    lines.append(f"  柱深  h     : {h} cm")
    lines.append(f"  保護層 dc   : {cover} cm")
    lines.append(f"  有效深度 d  : h − dc = {h} − {cover} = {d_rc:.1f} cm")
    lines.append(f"  Ag（全斷面）= {b}×{h} = {A_gross:.2f} cm²")
    lines.append(f"  As_stl      = {A_steel:.2f} cm²  (鋼骨斷面積)")
    lines.append(f"  Ac          = Ag − As_stl = {A_gross:.2f} − {A_steel:.2f} = {Ac:.2f} cm²")
    lines.append(f"  縱向鋼筋 As : {As:.2f} cm²")
    lines.append(f"  設計軸力 Pu : {Pu:.2f} tf")
    lines.append(f"  設計彎矩 Mu : {Mu:.2f} tf-m")
    if Vu > 0:
        lines.append(f"  設計剪力 Vu : {Vu:.2f} tf")
    if Av_s > 0:
        lines.append(f"  箍筋 Av/s   : {Av_s:.2f} cm² / {s_s:.1f} cm")
    lines.append(f"\n  材料強度：")
    lines.append(f"  Fys（鋼骨）= {mat.fy_steel:.0f} kgf/cm²")
    lines.append(f"  Fyr（鋼筋）= {mat.fy_rebar:.0f} kgf/cm²")
    lines.append(f"  fc'（混凝土）= {mat.fc:.0f} kgf/cm²")
    lines.append(f"  Es = {mat.Es:.0f} kgf/cm²")
    lines.append(f"  Ec = 15000√fc' = 15000×√{mat.fc:.0f} = {mat.Ec:.0f} kgf/cm²")

    # ── 軸力強度（前置計算）────────────────────────────────
    Pn_rc  = (0.85 * mat.fc * Ac + mat.fy_rebar * As) / 1000
    Pn_s   = mat.fy_steel * A_steel / 1000
    phi_Pn = 0.75 * Pn_rc + 0.9 * Pn_s

    # ── 相對剛度（前置計算） ────────────────────────────────
    Is   = steel.Ix
    Ic   = b * (h ** 3) / 12
    EsIs = mat.Es * Is
    EcIc = mat.Ec * Ic
    rs   = EsIs / (EsIs + EcIc)
    rrc  = 1 - rs
    Pu_s  = rs  * Pu;  Pu_rc = rrc * Pu
    Mu_s  = rs  * Mu;  Mu_rc = rrc * Mu

    # ══════════════════════════════════════════════════════
    # 二、鋼骨彎矩強度 Mns
    # ══════════════════════════════════════════════════════
    Pns     = mat.fy_steel * A_steel / 1000
    Mns     = mat.fy_steel * steel.Zx / 1e5
    phi_Mns = 0.9 * Mns

    lines.append("\n【二、鋼骨彎矩強度 Mns】(規範 7.3.1 / AISC LRFD)")
    lines.append(f"  Mns = Fys × Zs / 10⁵ = {mat.fy_steel:.0f} × {steel.Zx:.1f} / 10⁵ = {Mns:.3f} tf-m")
    lines.append(f"  φMns = 0.9 × {Mns:.3f} = {phi_Mns:.3f} tf-m")
    lines.append(f"\n  ─ 相對剛度分配（規範 7.3）─")
    lines.append(f"  Is = {Is:.1f} cm⁴，Ic = b×h³/12 = {Ic:.1f} cm⁴")
    lines.append(f"  r_s  = {EsIs:.3e}/({EsIs:.3e}+{EcIc:.3e}) = {rs:.4f}")
    lines.append(f"  r_rc = 1 − r_s = {rrc:.4f}")
    lines.append(f"  Mu_s = {rs:.4f}×{Mu:.2f} = {Mu_s:.3f} tf-m")
    lines.append(f"  φPns = 0.9×Fys×As_stl = 0.9×{mat.fy_steel:.0f}×{A_steel:.2f}/1000 = {0.9*Pns:.2f} tf")
    ratio_pu_pns = Pu_s / (0.9 * Pns) if Pns > 0 else 0
    if ratio_pu_pns >= 0.2:
        chk_s = Pu_s / (0.9 * Pns) + Mu_s / (0.9 * Mns)
        lines.append(f"  P-M交互作用（Pu_s/φPns={ratio_pu_pns:.3f} ≥ 0.2）：")
        lines.append(f"  Pu_s/(φPns)+Mu_s/(φMns) = {Pu_s:.2f}/{0.9*Pns:.2f}+{Mu_s:.2f}/{phi_Mns:.3f} = {chk_s:.3f}")
    else:
        chk_s = Pu_s / (1.8 * Pns) + Mu_s / (0.9 * Mns)
        lines.append(f"  P-M交互作用（Pu_s/φPns={ratio_pu_pns:.3f} < 0.2）：")
        lines.append(f"  Pu_s/(1.8Pns)+Mu_s/(φMns) = {Pu_s:.2f}/{1.8*Pns:.2f}+{Mu_s:.2f}/{phi_Mns:.3f} = {chk_s:.3f}")
    ok_s = "✓ OK" if chk_s <= 1.0 else "✗ NG"
    lines.append(f"  鋼骨P-M比值 = {chk_s:.3f} → {ok_s}")

    # ══════════════════════════════════════════════════════
    # 三、RC部分彎矩強度 Mnrc
    # ══════════════════════════════════════════════════════
    a2     = As * mat.fy_rebar / (0.85 * mat.fc * b)
    Mn_rc  = As * mat.fy_rebar * (d_rc - a2 / 2) / 1e5
    phi_Mn_rc = 0.9 * Mn_rc

    lines.append("\n【三、RC部分彎矩強度 Mnrc】(規範 7.3.2 / ACI 318)")
    lines.append(f"  d = h − dc = {h} − {cover} = {d_rc:.1f} cm")
    lines.append(f"  a = As·Fyr/(0.85·fc'·b) = {As:.2f}×{mat.fy_rebar:.0f}/(0.85×{mat.fc:.0f}×{b}) = {a2:.3f} cm")
    lines.append(f"  Mnrc = As·Fyr·(d−a/2)/10⁵ = {As:.2f}×{mat.fy_rebar:.0f}×({d_rc:.1f}−{a2:.3f}/2)/10⁵ = {Mn_rc:.3f} tf-m")
    lines.append(f"  φMnrc = 0.9×{Mn_rc:.3f} = {phi_Mn_rc:.3f} tf-m")
    lines.append(f"\n  ─ RC部分P-M交互作用 ─")
    lines.append(f"  φPn_rc = 0.65×Pn_rc = 0.65×{Pn_rc:.2f} = {0.65*Pn_rc:.2f} tf")
    ratio_pu_pnrc = Pu_rc / (0.65 * Pn_rc) if Pn_rc > 0 else 0
    if ratio_pu_pnrc >= 0.1:
        chk_r = Pu_rc / (0.65 * Pn_rc) + Mu_rc / (0.9 * Mn_rc)
        lines.append(f"  P-M交互作用（Pu_rc/φPn_rc={ratio_pu_pnrc:.3f} ≥ 0.1）：")
        lines.append(f"  Pu_rc/(φPn_rc)+Mu_rc/(φMnrc) = {Pu_rc:.2f}/{0.65*Pn_rc:.2f}+{Mu_rc:.2f}/{phi_Mn_rc:.3f} = {chk_r:.3f}")
    else:
        chk_r = Pu_rc / (1.3 * Pn_rc) + Mu_rc / (0.9 * Mn_rc)
        lines.append(f"  P-M交互作用（Pu_rc/φPn_rc={ratio_pu_pnrc:.3f} < 0.1）：")
        lines.append(f"  Pu_rc/(1.3Pn_rc)+Mu_rc/(φMnrc) = {Pu_rc:.2f}/{1.3*Pn_rc:.2f}+{Mu_rc:.2f}/{phi_Mn_rc:.3f} = {chk_r:.3f}")
    ok_r = "✓ OK" if chk_r <= 1.0 else "✗ NG"
    lines.append(f"  RC部分P-M比值 = {chk_r:.3f} → {ok_r}")

    # ══════════════════════════════════════════════════════
    # 四、疊加彎矩強度
    # ══════════════════════════════════════════════════════
    phi_Mn_total = phi_Mns + phi_Mn_rc
    dc_M  = Mu / phi_Mn_total if phi_Mn_total > 0 else 0
    ok_mu = phi_Mn_total >= Mu
    tag_mu = "✓ OK" if ok_mu else "✗ NG"

    lines.append("\n【四、疊加彎矩強度】(規範 7.3 強度疊加法)")
    lines.append(f"  φMn = φMns + φMnrc")
    lines.append(f"      = {phi_Mns:.3f} + {phi_Mn_rc:.3f}")
    lines.append(f"      = {phi_Mn_total:.3f} tf-m")
    lines.append(f"  設計需求：Mu = {Mu:.2f} tf-m")
    lines.append(f"  D/C = Mu / φMn = {Mu:.2f} / {phi_Mn_total:.3f} = {dc_M:.3f} → {tag_mu}")

    # ══════════════════════════════════════════════════════
    # 五、最小鋼筋比檢核
    # ══════════════════════════════════════════════════════
    rho     = As / (b * d_rc)
    rho_min = max(14.0 / mat.fy_rebar, 0.8 * math.sqrt(mat.fc) / mat.fy_rebar)
    rho_max = 0.08
    ok_rho     = rho >= rho_min
    ok_rho_max = rho <= rho_max
    tag_rho    = "✓ OK" if ok_rho else "✗ NG"

    lines.append("\n【五、最小鋼筋比檢核】(規範 6.2 / ACI 318 §10.6)")
    lines.append(f"  ρ = As/(b×d)  = {As:.2f}/({b}×{d_rc:.1f}) = {rho:.5f}")
    lines.append(f"  ρmin = max(14/Fyr, 0.8√fc'/Fyr)")
    lines.append(f"       = max({14/mat.fy_rebar:.5f}, {0.8*math.sqrt(mat.fc)/mat.fy_rebar:.5f})")
    lines.append(f"       = {rho_min:.5f}")
    lines.append(f"  ρmax = 0.080（SRC柱縱筋比上限）")
    lines.append(f"  ρ = {rho:.5f} {'≥' if ok_rho else '<'} ρmin = {rho_min:.5f} → {tag_rho}")
    lines.append(f"  ρ = {rho:.5f} {'≤' if ok_rho_max else '>'} ρmax = {rho_max:.3f} → {'✓ OK' if ok_rho_max else '✗ NG（超過上限）'}")

    # ══════════════════════════════════════════════════════
    # 六、彎矩強度檢核
    # ══════════════════════════════════════════════════════
    ok_pu  = Pu <= phi_Pn
    dc_P   = Pu / phi_Pn if phi_Pn > 0 else 0
    tag_pu = "✓ OK" if ok_pu else "✗ NG"

    lines.append("\n【六、彎矩強度檢核】")
    lines.append(f"  軸力強度：φPn = 0.75×Pn_rc + 0.9×Pn_s")
    lines.append(f"    Pn_rc = (0.85×{mat.fc:.0f}×{Ac:.1f}+{mat.fy_rebar:.0f}×{As:.2f})/1000 = {Pn_rc:.2f} tf")
    lines.append(f"    Pn_s  = {mat.fy_steel:.0f}×{A_steel:.2f}/1000 = {Pn_s:.2f} tf")
    lines.append(f"    φPn = 0.75×{Pn_rc:.2f}+0.9×{Pn_s:.2f} = {phi_Pn:.2f} tf")
    lines.append(f"    Pu = {Pu:.2f} tf {'≤' if ok_pu else '>'} φPn = {phi_Pn:.2f} tf，D/C = {dc_P:.3f} → {tag_pu}")
    lines.append(f"  鋼骨P-M（AISC 7.3.1）= {chk_s:.3f} → {ok_s}")
    lines.append(f"  RC部分P-M（ACI 7.3.2）= {chk_r:.3f} → {ok_r}")
    lines.append(f"  疊加彎矩：φMn = {phi_Mn_total:.3f} tf-m，Mu = {Mu:.2f} tf-m，D/C = {dc_M:.3f} → {tag_mu}")

    # ══════════════════════════════════════════════════════
    # 七、剪力強度檢核（彎矩分配法，規範 7.4）
    # ══════════════════════════════════════════════════════
    lines.append("\n【七、剪力強度檢核】(規範 7.4 彎矩分配法)")
    lines.append("  方法：依彎矩分配比將 Vu 分給鋼骨（Vu_s）與RC（Vu_rc），分別檢核")

    # ── (1) 鋼骨腹板剪力強度 φVns ─────────────────────────
    s_d_cm  = steel.d  / 10
    s_tw_cm = steel.tw / 10
    s_tf_cm = steel.tf / 10
    if steel.section_type == 'BOX':
        Aw_col = 2 * s_tw_cm * (s_d_cm - 2 * s_tf_cm)
    else:
        Aw_col = s_tw_cm * (s_d_cm - 2 * s_tf_cm)
    Vns_col     = 0.6 * mat.fy_steel * Aw_col / 1000
    phi_Vns_col = 0.9 * Vns_col

    # ── (2) RC 剪力強度 φVnrc = φVc + φVs ──────────────────
    Vc_col      = 0.53 * math.sqrt(mat.fc) * b * d_rc / 1000
    phi_Vc_col  = 0.75 * Vc_col
    Vs_col      = (Av_s * mat.fy_rebar * d_rc / s_s / 1000) if (Av_s > 0 and s_s > 0) else 0.0
    phi_Vs_col  = 0.75 * Vs_col
    phi_Vnrc_col = phi_Vc_col + phi_Vs_col   # RC 剪力強度合計

    # ── (3) 總剪力強度 φVn = φVns + φVnrc ─────────────────
    phi_Vn_col = phi_Vns_col + phi_Vnrc_col

    # ── (4) 彎矩分配比 ────────────────────────────────────
    Mn_total = Mns + Mn_rc   # 名目彎矩（未乘 φ）合計（tf-m）
    r_vns  = Mns  / Mn_total if Mn_total > 0 else 0.5
    r_vnrc = Mn_rc / Mn_total if Mn_total > 0 else 0.5

    lines.append(f"\n  ─ 彎矩比例計算 ─")
    lines.append(f"  Mns  = {Mns:.3f} tf-m（鋼骨名目彎矩）")
    lines.append(f"  Mnrc = {Mn_rc:.3f} tf-m（RC名目彎矩）")
    lines.append(f"  Mn   = Mns + Mnrc = {Mns:.3f} + {Mn_rc:.3f} = {Mn_total:.3f} tf-m")
    lines.append(f"  r_s  = Mns/Mn  = {Mns:.3f}/{Mn_total:.3f} = {r_vns:.4f}")
    lines.append(f"  r_rc = Mnrc/Mn = {Mn_rc:.3f}/{Mn_total:.3f} = {r_vnrc:.4f}")

    # ── (5) 計算書：鋼骨腹板剪力強度 ─────────────────────
    lines.append(f"\n  ─ 鋼骨腹板剪力強度 φVns ─")
    if steel.section_type == 'BOX':
        lines.append(f"  BOX型鋼：Aw = 2×tw×(d-2tf) = 2×{s_tw_cm:.1f}×({s_d_cm:.1f}-2×{s_tf_cm:.2f}) = {Aw_col:.2f} cm²")
    else:
        lines.append(f"  H型鋼：Aw = tw×(d-2tf) = {s_tw_cm:.1f}×({s_d_cm:.1f}-2×{s_tf_cm:.2f}) = {Aw_col:.2f} cm²")
    lines.append(f"  Vns = 0.6×Fys×Aw = 0.6×{mat.fy_steel:.0f}×{Aw_col:.2f}/1000 = {Vns_col:.3f} tf")
    lines.append(f"  φVns = 0.9×{Vns_col:.3f} = {phi_Vns_col:.3f} tf")

    # ── (6) 計算書：RC 剪力強度 ────────────────────────────
    lines.append(f"\n  ─ RC 剪力強度 φVnrc = φVc + φVs ─")
    lines.append(f"  Vc = 0.53×√fc'×b×d/1000 = 0.53×√{mat.fc:.0f}×{b}×{d_rc:.1f}/1000 = {Vc_col:.3f} tf")
    lines.append(f"  φVc = 0.75×{Vc_col:.3f} = {phi_Vc_col:.3f} tf")
    if Av_s > 0:
        lines.append(f"  Vs = Av×Fyr×d/(s×1000) = {Av_s:.2f}×{mat.fy_rebar:.0f}×{d_rc:.1f}/({s_s:.1f}×1000) = {Vs_col:.3f} tf")
        lines.append(f"  φVs = 0.75×{Vs_col:.3f} = {phi_Vs_col:.3f} tf")
    else:
        lines.append("  φVs = 0.000 tf（未輸入箍筋）")
    lines.append(f"  φVnrc = φVc + φVs = {phi_Vc_col:.3f} + {phi_Vs_col:.3f} = {phi_Vnrc_col:.3f} tf")

    # ── (7) 彎矩分配法檢核 ────────────────────────────────
    lines.append(f"\n  ─ 彎矩分配法分別檢核 ─")
    ok_vu = True
    ok_vu_s   = True
    ok_vu_rc  = True
    dc_vu     = 0.0
    dc_vu_s   = 0.0
    dc_vu_rc  = 0.0
    if Vu > 0:
        Vu_s  = r_vns  * Vu   # 鋼骨分配剪力
        Vu_rc = r_vnrc * Vu   # RC 分配剪力
        lines.append(f"  Vu_s  = r_s × Vu  = {r_vns:.4f} × {Vu:.2f} = {Vu_s:.3f} tf（鋼骨分配剪力）")
        lines.append(f"  Vu_rc = r_rc × Vu = {r_vnrc:.4f} × {Vu:.2f} = {Vu_rc:.3f} tf（RC 分配剪力）")
        # 鋼骨檢核
        dc_vu_s  = Vu_s  / phi_Vns_col  if phi_Vns_col  > 0 else 999
        ok_vu_s  = dc_vu_s  <= 1.0
        tag_s_v  = '✓ OK' if ok_vu_s  else '✗ NG'
        lines.append(f"  ① 鋼骨：Vu_s={Vu_s:.3f} tf {'≤' if ok_vu_s else '>'} φVns={phi_Vns_col:.3f} tf，D/C={dc_vu_s:.3f} → {tag_s_v}")
        # RC 檢核
        dc_vu_rc = Vu_rc / phi_Vnrc_col if phi_Vnrc_col > 0 else 999
        ok_vu_rc = dc_vu_rc <= 1.0
        tag_rc_v = '✓ OK' if ok_vu_rc else '✗ NG'
        lines.append(f"  ② RC ：Vu_rc={Vu_rc:.3f} tf {'≤' if ok_vu_rc else '>'} φVnrc={phi_Vnrc_col:.3f} tf，D/C={dc_vu_rc:.3f} → {tag_rc_v}")
        # 總剪力
        dc_vu  = Vu / phi_Vn_col if phi_Vn_col > 0 else 999
        ok_vu  = ok_vu_s and ok_vu_rc and (dc_vu <= 1.0)
        tag_vu = '✓ OK' if ok_vu else '✗ NG'
        lines.append(f"  ③ 總計：φVn = φVns + φVnrc = {phi_Vns_col:.3f} + {phi_Vnrc_col:.3f} = {phi_Vn_col:.3f} tf")
        lines.append(f"     Vu = {Vu:.2f} tf {'≤' if ok_vu else '>'} φVn = {phi_Vn_col:.3f} tf，D/C = {dc_vu:.3f} → {tag_vu}")
    else:
        lines.append(f"  φVns  = {phi_Vns_col:.3f} tf（鋼骨腹板）")
        lines.append(f"  φVnrc = {phi_Vnrc_col:.3f} tf（RC = φVc + φVs）")
        lines.append(f"  φVn   = {phi_Vn_col:.3f} tf（未輸入 Vu，無法 D/C 檢核）")

    # ══════════════════════════════════════════════════════
    # 八、結論
    # ══════════════════════════════════════════════════════
    is_safe = (chk_s <= 1.0 and chk_r <= 1.0 and ok_pu
               and ok_mu and ok_rho and ok_rho_max and ok_vu)

    lines.append("\n【八、結論】")
    lines.append("=" * 60)
    lines.append("  各項檢核彙整：")
    lines.append(f"  ① 軸力強度  ：Pu={Pu:.2f} tf，φPn={phi_Pn:.2f} tf，D/C={dc_P:.3f} → {tag_pu}")
    lines.append(f"  ② 鋼骨P-M  ：{chk_s:.3f} → {ok_s}")
    lines.append(f"  ③ RC P-M   ：{chk_r:.3f} → {ok_r}")
    lines.append(f"  ④ 疊加彎矩 ：Mu={Mu:.2f} tf-m，φMn={phi_Mn_total:.3f} tf-m，D/C={dc_M:.3f} → {tag_mu}")
    lines.append(f"  ⑤ 最小鋼筋比：ρ={rho:.5f}，ρmin={rho_min:.5f} → {tag_rho}")
    if Vu > 0:
        lines.append(f"  ⑥ 剪力強度 ：Vu={Vu:.2f} tf，φVn={phi_Vn_col:.3f} tf，D/C={dc_vu:.3f} → {'✓ OK' if ok_vu else '✗ NG'}")
        lines.append(f"      鋼骨：Vu_s={r_vns*Vu:.3f} tf，φVns={phi_Vns_col:.3f} tf，D/C={dc_vu_s:.3f} → {'✓' if ok_vu_s else '✗'}")
        lines.append(f"      RC ：Vu_rc={r_vnrc*Vu:.3f} tf，φVnrc={phi_Vnrc_col:.3f} tf，D/C={dc_vu_rc:.3f} → {'✓' if ok_vu_rc else '✗'}")
    else:
        lines.append(f"  ⑥ 剪力強度 ：φVn={phi_Vn_col:.3f} tf（未輸入 Vu，無法D/C檢核）")
    lines.append("-" * 60)
    lines.append(f"  ★ {'設計安全 ✓  所有檢核均通過' if is_safe else '設計不足 ✗  請檢視不通過項目並加大斷面或配筋'}")
    lines.append("=" * 60)

    wt_report, wt_ok = check_width_thickness(mat, steel)
    lines.append("")
    lines.append(wt_report)

    result = {
        'phi_Pn': phi_Pn,  'Pn_rc': Pn_rc,  'Pn_s': Pn_s,
        'Ac': Ac,           'rs': rs,          'rrc': rrc,
        'Pu_s': Pu_s,       'Pu_rc': Pu_rc,    'Mu_s': Mu_s,  'Mu_rc': Mu_rc,
        'Pns': Pns,         'Mns': Mns,        'Mn_rc': Mn_rc,
        'phi_Mns': phi_Mns, 'phi_Mn_rc': phi_Mn_rc, 'phi_Mn': phi_Mn_total,
        'chk_s': chk_s,     'chk_r': chk_r,    'is_safe': is_safe,
        'd_rc': d_rc,        'a': a2,           'Ic': Ic,       'Is': Is,
        'wt_ok': wt_ok,      'rho': rho,        'rho_min': rho_min,
        'ok_rho': ok_rho,    'dc_P': dc_P,      'ok_pu': ok_pu,
        'dc_M': dc_M,        'ok_mu': ok_mu,
        'phi_Vn': phi_Vn_col,  'phi_Vnrc': phi_Vnrc_col, 'phi_Vns': phi_Vns_col,
        'Vu': Vu,              'dc_vu': dc_vu,   'ok_vu': ok_vu,
        'dc_vu_s': dc_vu_s,    'ok_vu_s': ok_vu_s,
        'dc_vu_rc': dc_vu_rc,  'ok_vu_rc': ok_vu_rc
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
            M = (0.5 * As * mat.fy_rebar * (d_rc - cover) / 1e5
                 + 0.5 * mat.fy_steel * steel.Zx / 1e5) * math.sin(r * math.pi)
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
    ax.text(0, -h/2 - 4, f'b = {b} cm', ha='center', va='top', fontsize=11)
    ax.annotate('', xy=(b/2 + 3, h/2), xytext=(b/2 + 3, -h/2),
                arrowprops=dict(arrowstyle='<->', color='black'))
    ax.text(b/2 + 4.5, 0, f'h = {h} cm', ha='left', va='center', fontsize=11, rotation=90)

    ax.set_title(f'圖C5.2.1 包覆型SRC梁斷面配筋示意\n'
                 f'b×h={b}×{h}cm  鋼骨:{steel.name}\n'
                 f'上筋:{top_rebars}-{top_size}  下筋:{bot_rebars}-{bot_size}',
                 fontsize=12, fontweight='bold')

    # 圖例
    legend_elements = [
        mpatches.Patch(fc='#D0D0D0', ec='black', label='混凝土'),
        mpatches.Patch(fc='#404040', ec='black', label='型鋼'),
        mpatches.Patch(fc='#CC0000', ec='black', label=f'上筋 {top_rebars}-{top_size}'),
        mpatches.Patch(fc='#0044CC', ec='black', label=f'下筋 {bot_rebars}-{bot_size}'),
    ]
    ax.legend(handles=legend_elements, loc='upper left', fontsize=9,
               bbox_to_anchor=(1.02, 1), borderaxespad=0, framealpha=0.8)


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
    ax.text(0, -h/2 - 4, f'b = {b} cm', ha='center', va='top', fontsize=11)
    ax.annotate('', xy=(b/2 + 3, h/2), xytext=(b/2 + 3, -h/2),
                arrowprops=dict(arrowstyle='<->', color='black'))
    ax.text(b/2 + 4.5, 0, f'h = {h} cm', ha='left', va='center', fontsize=11, rotation=90)

    ax.set_title(f'圖C6.2.1 包覆型SRC柱斷面配筋示意\n'
                 f'b×h={b}×{h}cm  鋼骨:{steel.name}\n'
                 f'縱筋:{num_bars}-{bar_size}',
                 fontsize=12, fontweight='bold')

    legend_elements = [
        mpatches.Patch(fc='#D0D0D0', ec='black', label='混凝土'),
        mpatches.Patch(fc='#404040', ec='black', label='型鋼'),
        mpatches.Patch(fc='#CC0000', ec='black', label=f'縱筋 {num_bars}-{bar_size}'),
    ]
    ax.legend(handles=legend_elements, loc='upper left', fontsize=9,
               bbox_to_anchor=(1.02, 1), borderaxespad=0, framealpha=0.8)


# ============================================================
# 輔助函式：分析成果摘要卡片 & HTML 計算書生成
# ============================================================
import html as _html

def _dc_color(ratio: float) -> str:
    if ratio <= 0.8:  return '#27ae60'   # 綠
    if ratio <= 1.0:  return '#e67e22'   # 橘
    return '#e74c3c'                      # 紅

def _card(label: str, main: str, sub: str, color: str) -> str:
    return (f'<div style="background:#f8f9fa;border-left:6px solid {color};'
            f'border-radius:8px;padding:16px 20px;margin:6px 0">'
            f'<div style="font-size:14px;color:#555;margin-bottom:4px;font-weight:600">{label}</div>'
            f'<div style="font-size:22px;font-weight:bold;color:{color};margin:4px 0">{main}</div>'
            f'<div style="font-size:13px;color:#444;margin-top:5px">{sub}</div></div>')

def show_beam_summary(res: dict, Mu: float, Vu: float):
    """顯示梁設計分析成果摘要"""
    ok      = res['ok']
    phi_Mn  = res['phi_Mn']
    phi_Vn  = res['phi_Vn']
    dc_M    = Mu / phi_Mn if phi_Mn > 0 else 0

    if ok:
        st.success('✅ **設計安全 — 所有檢核均通過**')
    else:
        st.error('❌ **設計不足 — 請下載計算書檢視詳細內容**')

    cols = st.columns(3)
    with cols[0]:
        c = _dc_color(dc_M)
        tag = '✓ OK' if dc_M <= 1.0 else '✗ NG'
        st.markdown(_card('彎矩強度 φMn',
                          f'{phi_Mn:.2f} tf-m',
                          f'Mu = {Mu:.2f} tf-m　D/C = {dc_M:.3f}　{tag}', c),
                    unsafe_allow_html=True)
    with cols[1]:
        if Vu > 0:
            dc_V = Vu / phi_Vn if phi_Vn > 0 else 0
            cv  = _dc_color(dc_V)
            tag_v = '✓ OK' if dc_V <= 1.0 else '✗ NG'
            st.markdown(_card('剪力強度 φVn',
                              f'{phi_Vn:.2f} tf',
                              f'Vu = {Vu:.2f} tf　D/C = {dc_V:.3f}　{tag_v}', cv),
                        unsafe_allow_html=True)
        else:
            st.markdown(_card('剪力強度', '—', '未輸入 Vu', '#bbb'),
                        unsafe_allow_html=True)
    with cols[2]:
        wc   = '#27ae60' if res['wt_ok'] else '#e74c3c'
        wtxt = '✓ 緊密斷面' if res['wt_ok'] else '✗ 非緊密/細長'
        st.markdown(_card('鋼骨寬厚比', wtxt, '依SRC規範第3章', wc),
                    unsafe_allow_html=True)

def show_column_summary(res: dict, Pu: float, Mu: float):
    """顯示柱設計分析成果摘要"""
    ok        = res['is_safe']
    phi_Pn    = res['phi_Pn']
    chk_s     = res['chk_s']
    chk_r     = res['chk_r']
    phi_Mn    = res.get('phi_Mn', 0.0)
    phi_Vn    = res.get('phi_Vn', 0.0)
    phi_Vns   = res.get('phi_Vns', 0.0)
    phi_Vnrc  = res.get('phi_Vnrc', 0.0)
    Vu        = res.get('Vu', 0.0)
    dc_vu     = res.get('dc_vu', 0.0)
    ok_vu     = res.get('ok_vu', True)
    dc_vu_s   = res.get('dc_vu_s', 0.0)
    ok_vu_s   = res.get('ok_vu_s', True)
    dc_vu_rc  = res.get('dc_vu_rc', 0.0)
    ok_vu_rc  = res.get('ok_vu_rc', True)
    dc_M      = res.get('dc_M', Mu / phi_Mn if phi_Mn > 0 else 0)
    ok_mu     = res.get('ok_mu', phi_Mn >= Mu)
    dc_P      = Pu / phi_Pn if phi_Pn > 0 else 0

    if ok:
        st.success('✅ **設計安全 — 所有檢核均通過**')
    else:
        st.error('❌ **設計不足 — 請下載計算書檢視詳細內容**')

    # ── 第一列：軸力 / 鋼骨P-M / RC P-M / 疊加彎矩 ───────────
    cols1 = st.columns(4)
    with cols1[0]:
        c = _dc_color(dc_P)
        tag = '✓ OK' if dc_P <= 1.0 else '✗ NG'
        st.markdown(_card('軸力強度 φPn',
                          f'{phi_Pn:.2f} tf',
                          f'Pu = {Pu:.2f} tf　D/C = {dc_P:.3f}　{tag}', c),
                    unsafe_allow_html=True)
    with cols1[1]:
        cs = _dc_color(chk_s)
        tag_s = '✓ OK' if chk_s <= 1.0 else '✗ NG'
        st.markdown(_card('鋼骨 P-M（AISC）',
                          f'{chk_s:.3f}　{tag_s}',
                          '規範 7.3.1', cs),
                    unsafe_allow_html=True)
    with cols1[2]:
        cr = _dc_color(chk_r)
        tag_r = '✓ OK' if chk_r <= 1.0 else '✗ NG'
        st.markdown(_card('RC P-M（ACI）',
                          f'{chk_r:.3f}　{tag_r}',
                          '規範 7.3.2', cr),
                    unsafe_allow_html=True)
    with cols1[3]:
        cm = _dc_color(dc_M)
        tag_m = '✓ OK' if ok_mu else '✗ NG'
        st.markdown(_card('疊加彎矩 φMn',
                          f'{phi_Mn:.2f} tf-m',
                          f'Mu = {Mu:.2f} tf-m　D/C = {dc_M:.3f}　{tag_m}', cm),
                    unsafe_allow_html=True)

    # ── 第二列：剪力強度 / 鋼骨寬厚比 ────────────────────────
    cols2 = st.columns(2)
    with cols2[0]:
        if Vu > 0:
            cv      = _dc_color(dc_vu)
            tag_v   = '✓ OK' if ok_vu   else '✗ NG'
            tag_vs  = '✓' if ok_vu_s  else '✗'
            tag_vrc = '✓' if ok_vu_rc else '✗'
            sub_txt = (f'Vu={Vu:.2f} tf，φVn={phi_Vn:.2f} tf，D/C={dc_vu:.3f} {tag_v}　'
                       f'鋼骨 D/C={dc_vu_s:.3f} {tag_vs}，RC D/C={dc_vu_rc:.3f} {tag_vrc}')
            st.markdown(_card('剪力強度 φVn',
                              f'{phi_Vn:.2f} tf',
                              sub_txt, cv),
                        unsafe_allow_html=True)
        else:
            st.markdown(_card('剪力強度 φVn',
                              f'{phi_Vn:.2f} tf',
                              f'φVns={phi_Vns:.2f} tf（鋼骨），φVnrc={phi_Vnrc:.2f} tf（RC），未輸入 Vu', '#17a589'),
                        unsafe_allow_html=True)
    with cols2[1]:
        wc   = '#27ae60' if res['wt_ok'] else '#e74c3c'
        wtxt = '✓ 緊密斷面' if res['wt_ok'] else '✗ 非緊密/細長'
        st.markdown(_card('鋼骨寬厚比', wtxt, '依SRC規範第3章', wc),
                    unsafe_allow_html=True)

def report_to_html(title: str, report: str) -> str:
    """將純文字計算書轉換為格式化 HTML 網頁版計算書"""
    lines = report.split('\n')
    html_lines = []
    for line in lines:
        esc = _html.escape(line)
        if set(esc.strip()) <= {'=', '-', ' '} and len(esc.strip()) > 4:
            html_lines.append(f'<div class="sep">{esc}</div>')
        elif esc.strip().startswith(('【', '●')):
            html_lines.append(f'<div class="sec">{esc}</div>')
        elif '✓' in esc:
            html_lines.append(f'<div class="ok">{esc}</div>')
        elif '✗' in esc:
            html_lines.append(f'<div class="ng">{esc}</div>')
        elif esc.strip() == '':
            html_lines.append('<div class="bl"> </div>')
        else:
            html_lines.append(f'<div class="ln">{esc}</div>')
    body = '\n'.join(html_lines)
    today = datetime.date.today().strftime('%Y-%m-%d')
    esc_title = _html.escape(title)
    return f"""<!DOCTYPE html>
<html lang="zh-TW"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>{esc_title}</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:'Microsoft JhengHei','PingFang TC','Noto Sans TC',sans-serif;
      background:#eef1f7;padding:30px;color:#222}}
.page{{max-width:900px;margin:0 auto;background:#fff;border-radius:12px;
       box-shadow:0 4px 24px rgba(0,0,0,.12);padding:44px 52px}}
.hdr{{border-bottom:3px solid #1a3c6d;padding-bottom:16px;margin-bottom:24px}}
.hdr h1{{color:#1a3c6d;font-size:22px}}
.hdr p{{color:#666;font-size:12px;margin-top:6px}}
.report{{font-family:'Courier New',Courier,monospace;font-size:12.5px;line-height:1.7}}
.sep{{color:#1a3c6d;font-weight:bold;border-top:1px solid #d0dae8;
      margin:10px 0 4px;padding-top:4px}}
.sec{{color:#2c3e50;font-weight:bold;margin:8px 0 2px}}
.ok{{color:#1e8449}}
.ng{{color:#c0392b;font-weight:bold}}
.ln{{color:#333}}
.bl{{height:6px}}
.ftr{{text-align:center;font-size:11px;color:#aaa;
      margin-top:30px;border-top:1px solid #eee;padding-top:14px}}
</style></head>
<body><div class="page">
  <div class="hdr">
    <h1>🏗️ {esc_title}</h1>
    <p>宏利工程顧問有限公司 ｜ 生成日期：{today}<br>
    依據：鋼骨鋼筋混凝土構造設計規範與解說（Taiwan SRC Code）</p>
  </div>
  <div class="report">
{body}
  </div>
  <div class="ftr">⚠️ 本程式僅供設計初稿參考，實際設計應經專業結構技師審查簽證。</div>
</div></body></html>"""

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
              padding: 8px 12px; font-family: monospace; font-size: 9px;
              white-space: pre-wrap; line-height: 1.4; }
</style>
""", unsafe_allow_html=True)

st.title("🏗️ SRC 鋼骨鋼筋混凝土結構設計程式_測試版")
st.markdown("**宏利工程顧問有限公司**")
st.markdown(f"**依據：鋼骨鋼筋混凝土構造設計規範與解說（Taiwan SRC Code）** ｜ 日期：{datetime.date.today().strftime('%Y-%m-%d')}")
st.markdown("---")

# 側邊欄：材料選擇
with st.sidebar:
    st.header("📋 材料設計參數")
    _fys_opts = ['SN400 (2400 kgf/cm²)', 'SN490 (3300 kgf/cm²)', '自訂']
    _fys_sel = st.selectbox("鋼骨降伏強度 Fys", _fys_opts, index=0)
    if _fys_sel == _fys_opts[0]:
        fy_steel = 2400
    elif _fys_sel == _fys_opts[1]:
        fy_steel = 3300
    else:
        fy_steel = st.number_input("自訂 Fys (kgf/cm²)", value=2400, min_value=2100, max_value=4500, step=100)
    _rg_keys = list(REBAR_GRADE.keys())
    _rg_sel  = st.selectbox(
        "鋼筋強度等級 (CNS 560)", _rg_keys, index=1,
        help="SD280W≡SD280: fy=2800  SD420W≡SD420: fy=4200\n"
             "SD490W≡SD490: fy=4900  SD550W≡SD550: fy=5500  (kgf/cm²)")
    fy_rebar = REBAR_GRADE[_rg_sel]
    fc = st.selectbox("混凝土 fc' (kgf/cm²)", [210, 280, 350, 420], index=1)
    mat = Material(fy_steel=fy_steel, fy_rebar=fy_rebar, fc=fc)
    st.info(f"Ec = 15,000×√{fc} = {mat.Ec:.0f} kgf/cm²")
    st.markdown("---")
    st.markdown("**鋼筋斷面積表**")
    for n, a in REBAR_DB.items():
        st.markdown(f"- {n}: {a} cm²")

# 主分頁
tab_beam, tab_col, tab_pm = st.tabs([
    "📐 SRC梁設計", "🏛️ SRC柱設計", "📈 P-M曲線"
])

# ===== 梁設計 =====
with tab_beam:
    st.header("SRC 梁設計計算書")
    st.caption("規範：5.4 強度疊加法／5.5 剪力強度疊加法")
    c1, c2 = st.columns([1, 1])
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
        Vu_b = st.number_input("設計剪力 Vu (tf)", value=0.0, min_value=0.0, key='Vu_b')
        st.markdown("**箍筋**")
        c7, c8, c9 = st.columns(3)
        with c7: stir_legs = st.number_input("支數", min_value=2, value=2, step=1, key='stleg')
        with c8: stir_sz   = st.selectbox("規格", list(REBAR_DB.keys()), index=0, key='stsz')
        with c9: stir_s    = st.number_input("間距 s(cm)", min_value=5, value=15, key='stsp')
        Av_b = float(stir_legs) * REBAR_DB[stir_sz]
        st.caption(f"Av = {Av_b:.2f} cm²")
    with c2:
        st.markdown("**斷面配筋示意圖（圖C5.2.1）**")
        _fig, _ax = plt.subplots(figsize=(3, 3.5))
        draw_beam_section(_fig, _ax, b_stl, bw, bh, bc, int(top_n), int(bot_n), top_s, bot_s)
        plt.tight_layout(pad=0.2)
        st.pyplot(_fig)
        plt.close(_fig)
    st.divider()
    if st.button("🔢 計算梁設計", type="primary", key='btn_beam'):
        report, res = calc_beam(mat, b_stl, bw, bh, bc, As_top, As_bot, Mu_b,
                                Vu=Vu_b, Av_s=Av_b, s_s=float(stir_s))
        st.markdown("#### 📊 分析成果摘要")
        show_beam_summary(res, Mu_b, Vu_b)
        st.markdown("---")
        st.markdown("#### 📥 下載計算書")
        _dc1, _dc2 = st.columns(2)
        with _dc1:
            st.download_button("📄 純文字版 (.txt)", data=report,
                               file_name="SRC梁計算書.txt", mime="text/plain",
                               key='dl_beam_txt', use_container_width=True)
        with _dc2:
            _html_rpt = report_to_html("SRC梁設計計算書", report)
            st.download_button("🌐 網頁版 (.html)", data=_html_rpt,
                               file_name="SRC梁計算書.html", mime="text/html",
                               key='dl_beam_html', use_container_width=True)

# ===== 柱設計 =====
with tab_col:
    st.header("SRC 柱設計計算書")
    st.caption("規範：6.4 軸力強度 / 7.3 P-M交互作用（相對剛度分配法）")
    c1, c2 = st.columns([1, 1])
    with c1:
        c_stl = steel_section_selector('col', filter_type='all',
                                       default_name='BOX300×300×9')
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
        Vu_c = st.number_input("設計剪力 Vu (tf)", value=0.0, min_value=0.0, key='Vu_c')
        st.markdown("**柱剪力筋（箍筋）**")
        cstir_c, cstir_sp = st.columns(2)
        with cstir_c:
            c_stir_legs = st.number_input("箍筋支數", min_value=2, value=2, step=1, key='c_stleg')
            c_stir_sz   = st.selectbox("箍筋規格", list(REBAR_DB.keys()), index=0, key='c_stsz')
        with cstir_sp:
            c_stir_s    = st.number_input("箍筋間距 s(cm)", min_value=5, value=15, key='c_stsp')
        Av_c = float(c_stir_legs) * REBAR_DB[c_stir_sz]
        st.caption(f"Av = {Av_c:.2f} cm²（{c_stir_legs}支 {c_stir_sz}）")
    with c2:
        st.markdown("**斷面配筋示意圖（圖C6.2.1）**")
        _fig2, _ax2 = plt.subplots(figsize=(3, 3))
        draw_column_section(_fig2, _ax2, c_stl, cw, ch, cc, int(c_num), c_siz)
        plt.tight_layout(pad=0.2)
        st.pyplot(_fig2)
        plt.close(_fig2)
    st.divider()
    if st.button("🔢 計算柱設計", type="primary", key='btn_col'):
        report, res = calc_column(mat, c_stl, cw, ch, cc, As_col, Pu_c, Mu_c,
                                  Vu=Vu_c, Av_s=Av_c, s_s=float(c_stir_s))
        st.markdown("#### 📊 分析成果摘要")
        show_column_summary(res, Pu_c, Mu_c)
        st.markdown("---")
        st.markdown("#### 📥 下載計算書")
        _dc1, _dc2 = st.columns(2)
        with _dc1:
            st.download_button("📄 純文字版 (.txt)", data=report,
                               file_name="SRC柱計算書.txt", mime="text/plain",
                               key='dl_col_txt', use_container_width=True)
        with _dc2:
            _html_rpt = report_to_html("SRC柱設計計算書", report)
            st.download_button("🌐 網頁版 (.html)", data=_html_rpt,
                               file_name="SRC柱計算書.html", mime="text/html",
                               key='dl_col_html', use_container_width=True)

# ===== P-M 曲線 =====
with tab_pm:
    st.header("📈 SRC 柱 P-M 互制曲線")
    c1, c2 = st.columns([1, 2])
    with c1:
        pm_stl = steel_section_selector('pm', filter_type='all',
                                        default_name='BOX300×300×9')
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

st.markdown("---")
st.warning("⚠️ 本程式依據『內政部頒布 — 鋼骨鋼筋混凝土構造設計規範與解說（110年3月24日修正）』計算，僅供設計初稿參考，實際設計應經專業結構技師審查簽證。")
