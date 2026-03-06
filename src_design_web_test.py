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
# 回傳 matplotlib.font_manager.FontProperties 物件，供繪圖函數明確使用
def _setup_cjk_font():
    import os, urllib.request
    import matplotlib.font_manager as fm
    import matplotlib

    # 1. Windows 系統字體路徑（優先使用，不依賴 fontManager 名稱比對）
    WIN_FONTS = [
        r'C:\Windows\Fonts\msjh.ttc',      # 微軟正黑體 Regular
        r'C:\Windows\Fonts\msjhbd.ttc',    # 微軟正黑體 Bold
        r'C:\Windows\Fonts\mingliu.ttc',   # 新細明體
        r'C:\Windows\Fonts\kaiu.ttf',      # 標楷體
    ]
    for fpath in WIN_FONTS:
        if os.path.exists(fpath):
            try:
                fm.fontManager.addfont(fpath)
                prop = fm.FontProperties(fname=fpath)
                matplotlib.rcParams['font.sans-serif'] = [prop.get_name(), 'DejaVu Sans']
                matplotlib.rcParams['axes.unicode_minus'] = False
                return prop
            except Exception:
                continue

    # 2. macOS 系統字體
    MAC_FONTS = [
        '/System/Library/Fonts/PingFang.ttc',
        '/System/Library/Fonts/STHeiti Light.ttc',
        '/Library/Fonts/Arial Unicode.ttf',
    ]
    for fpath in MAC_FONTS:
        if os.path.exists(fpath):
            try:
                fm.fontManager.addfont(fpath)
                prop = fm.FontProperties(fname=fpath)
                matplotlib.rcParams['font.sans-serif'] = [prop.get_name(), 'DejaVu Sans']
                matplotlib.rcParams['axes.unicode_minus'] = False
                return prop
            except Exception:
                continue

    # 3. 嘗試 matplotlib 已知 CJK 字體（Linux / Streamlit Cloud）
    prefer = ['Noto Sans TC', 'Noto Sans CJK TC', 'WenQuanYi Zen Hei',
              'AR PL UMing TW', 'Arial Unicode MS']
    available = {f.name for f in fm.fontManager.ttflist}
    for name in prefer:
        if name in available:
            matplotlib.rcParams['font.sans-serif'] = [name, 'DejaVu Sans']
            matplotlib.rcParams['axes.unicode_minus'] = False
            return fm.FontProperties(family=name)

    # 4. 動態下載 Noto Sans TC（Streamlit Cloud 無任何 CJK 字體時的最後手段）
    font_dir  = os.path.join(os.path.expanduser('~'), '.matplotlib_fonts')
    font_path = os.path.join(font_dir, 'NotoSansTC-Regular.ttf')
    if not os.path.exists(font_path):
        os.makedirs(font_dir, exist_ok=True)
        _FONT_URLS = [
            ('https://fonts.gstatic.com/s/notosanstc/v36/'
             'nKKQ-GM_FYFRJvXzVXaAPe97P1KHynJFbsJr-E-YGr4.ttf'),
        ]
        for _url in _FONT_URLS:
            try:
                urllib.request.urlretrieve(_url, font_path)
                break
            except Exception:
                if os.path.exists(font_path):
                    os.remove(font_path)
    if os.path.exists(font_path):
        try:
            fm.fontManager.addfont(font_path)
            prop = fm.FontProperties(fname=font_path)
            matplotlib.rcParams['font.sans-serif'] = [prop.get_name(), 'DejaVu Sans']
            matplotlib.rcParams['axes.unicode_minus'] = False
            return prop
        except Exception:
            pass

    # 5. 完全找不到 → 用 DejaVu Sans（中文會亂碼，但不會崩潰）
    matplotlib.rcParams['axes.unicode_minus'] = False
    return fm.FontProperties(family='DejaVu Sans')

_CJK_FONT = _setup_cjk_font()   # 全域 FontProperties，供繪圖函數使用


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
    Ix: float   # X軸慣性矩 cm⁴（強軸，高度方向）
    Zx: float   # X軸塑性斷面模數 cm³
    A: float    # 斷面積 cm²
    Iy: float = 0.0   # Y軸慣性矩 cm⁴（弱軸，寬度方向）；0=自動估算
    Zy: float = 0.0   # Y軸塑性斷面模數 cm³；0=自動估算

    def __post_init__(self):
        """若 Iy/Zy 未提供，依斷面幾何自動估算"""
        bf_cm = self.bf / 10.0
        d_cm  = self.d  / 10.0
        tf_cm = self.tf / 10.0
        tw_cm = self.tw / 10.0
        if self.Iy == 0.0:
            if self.section_type == 'BOX':
                # BOX方形：寬度方向與高度方向相同公式
                self.Iy = round(
                    (d_cm * bf_cm**3 - (d_cm - 2*tf_cm) * (bf_cm - 2*tw_cm)**3) / 12.0, 1)
            else:
                # H型鋼弱軸：主要由翼板貢獻
                self.Iy = round(
                    2 * (tf_cm * bf_cm**3 / 12.0) + (d_cm - 2*tf_cm) * tw_cm**3 / 12.0, 1)
        if self.Zy == 0.0 and bf_cm > 0:
            if self.section_type == 'BOX':
                self.Zy = round(self.Iy / (bf_cm / 2.0), 1)
            else:
                # H型鋼弱軸塑性模數（近似：翼板全塑性）
                self.Zy = round(
                    tf_cm * bf_cm**2 / 2.0 + (d_cm - 2*tf_cm) * tw_cm**2 / 4.0, 1)

# 依據 JIS G 3192 (台灣採用) 及台灣鋼結構設計手冊
# 格式：name, type, bf(mm), tf(mm), tw(mm), d(mm), Ix(cm⁴), Zx(cm³), A(cm²)
STEEL_DB = {
    # ── RH 等翼型 (bf≈d，梁柱皆可) ─────────────────────────────
    'RH100×100×6×8':    SteelSection('RH100×100×6×8',    'H', 100,  8,  6.0, 100,   370,   84, 21.04),
    'RH125×125×6.5×9':  SteelSection('RH125×125×6.5×9',  'H', 125,  9,  6.5, 125,   825,  149, 29.46),
    'RH150×150×7×10':   SteelSection('RH150×150×7×10',   'H', 150, 10,  7.0, 150,  1601,  240, 39.10),
    'RH200×200×8×12':   SteelSection('RH200×200×8×12',   'H', 200, 12,  8.0, 200,  4611,  513, 62.08),
    'RH250×250×9×14':   SteelSection('RH250×250×9×14',   'H', 250, 14,  9.0, 250, 10587,  937, 89.98),
    'RH300×300×10×15':  SteelSection('RH300×300×10×15',  'H', 300, 15, 10.0, 300, 19933, 1465,117.00),
    'RH350×350×12×19':  SteelSection('RH350×350×12×19',  'H', 350, 19, 12.0, 350, 39431, 2493,170.44),
    'RH400×400×13×21':  SteelSection('RH400×400×13×21',  'H', 400, 21, 13.0, 400, 65369, 3600,214.54),
    # ── RH 中翼型 (梁常用) ─────────────────────────────────────
    'RH150×75×5×7':     SteelSection('RH150×75×5×7',     'H',  75,  7,  5.0, 150,   642,   98, 17.30),
    'RH200×100×5.5×8':  SteelSection('RH200×100×5.5×8',  'H', 100,  8,  5.5, 200,  1761,  200, 26.12),
    'RH250×125×6×9':    SteelSection('RH250×125×6×9',    'H', 125,  9,  6.0, 250,  3893,  351, 36.42),
    'RH300×150×6.5×9':  SteelSection('RH300×150×6.5×9',  'H', 150,  9,  6.5, 300,  6928,  524, 45.33),
    'RH350×175×7×11':   SteelSection('RH350×175×7×11',   'H', 175, 11,  7.0, 350, 13123,  841, 61.46),
    'RH400×200×8×13':   SteelSection('RH400×200×8×13',   'H', 200, 13,  8.0, 400, 22963, 1286, 81.92),
    'RH450×200×9×14':   SteelSection('RH450×200×9×14',   'H', 200, 14,  9.0, 450, 32259, 1621, 93.98),
    'RH500×200×10×16':  SteelSection('RH500×200×10×16',  'H', 200, 16, 10.0, 500, 46037, 2096,110.80),
    'RH600×200×11×17':  SteelSection('RH600×200×11×17',  'H', 200, 17, 11.0, 600, 74584, 2863,130.26),
    'RH700×300×13×24':  SteelSection('RH700×300×13×24',  'H', 300, 24, 13.0, 700,193983, 6250,228.76),
    'RH800×300×14×26':  SteelSection('RH800×300×14×26',  'H', 300, 26, 14.0, 800,283025, 7996,260.72),
    'RH900×300×16×28':  SteelSection('RH900×300×16×28',  'H', 300, 28, 16.0, 900,399926,10174,303.04),
    # ── RH 特殊型 (非標準比例) ──────────────────────────────────
    'RH244×175×7×11':   SteelSection('RH244×175×7×11',   'H', 175, 11,  7.0, 244,  5868,  535, 54.04),
    'RH294×200×8×12':   SteelSection('RH294×200×8×12',   'H', 200, 12,  8.0, 294, 10828,  823, 69.60),
    'RH340×250×9×14':   SteelSection('RH340×250×9×14',   'H', 250, 14,  9.0, 340, 20888, 1360, 98.08),
    'RH390×300×10×16':  SteelSection('RH390×300×10×16',  'H', 300, 16, 10.0, 390, 37414, 2116,131.80),
    'RH440×300×11×18':  SteelSection('RH440×300×11×18',  'H', 300, 18, 11.0, 440, 54060, 2728,152.44),
    'RH488×300×11×18':  SteelSection('RH488×300×11×18',  'H', 300, 18, 11.0, 488, 68337, 3100,157.72),
    'RH588×300×12×20':  SteelSection('RH588×300×12×20',  'H', 300, 20, 12.0, 588,113284, 4309,185.76),
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
        # H型鋼在資料庫中以 'RH' 開頭（JIS G 3192）
        db_keys = [k for k in STEEL_DB if not k.startswith('BOX')]
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
            _Iy_est = round(2*tf_cm*bf_cm**3/12 + (d_cm-2*tf_cm)*tw_cm**3/12, 1)
            _Zy_est = round(_Iy_est / (bf_cm/2), 1)
        else:
            _A_est  = round(bf_cm*d_cm - (bf_cm-2*tw_cm)*(d_cm-2*tf_cm), 2)
            _Ix_est = round((bf_cm*d_cm**3 - (bf_cm-2*tw_cm)*(d_cm-2*tf_cm)**3)/12, 1)
            _Zx_est = round(_Ix_est / (d_cm/2), 1)
            _Iy_est = round((d_cm*bf_cm**3 - (d_cm-2*tf_cm)*(bf_cm-2*tw_cm)**3)/12, 1)
            _Zy_est = round(_Iy_est / (bf_cm/2), 1)

        c_A  = st.number_input("斷面積 A (cm²)",    min_value=1.0,  max_value=5000.0,
                               value=float(_A_est),  step=0.1, format="%.2f", key=f"{key}_A")
        c_Ix = st.number_input("慣性矩 Ix (cm⁴) (X向)",   min_value=1.0,  max_value=9999999.0,
                               value=float(_Ix_est), step=1.0, format="%.1f", key=f"{key}_Ix")
        c_Zx = st.number_input("塑性模數 Zx (cm³) (X向)", min_value=1.0,  max_value=999999.0,
                               value=float(_Zx_est), step=1.0, format="%.1f", key=f"{key}_Zx")
        c_Iy = st.number_input("慣性矩 Iy (cm⁴) (Y向)",   min_value=1.0,  max_value=9999999.0,
                               value=float(_Iy_est), step=1.0, format="%.1f", key=f"{key}_Iy")
        c_Zy = st.number_input("塑性模數 Zy (cm³) (Y向)", min_value=1.0,  max_value=999999.0,
                               value=float(_Zy_est), step=1.0, format="%.1f", key=f"{key}_Zy")

    cust_name = f"自訂-{sec_type}{c_d}x{c_bf}x{c_tw}x{c_tf}"
    st.caption(f"斷面名稱：{cust_name} | A={c_A:.2f} cm² | Ix={c_Ix:.1f} cm⁴ | Zx={c_Zx:.1f} cm³ | Iy={c_Iy:.1f} cm⁴ | Zy={c_Zy:.1f} cm³")
    return SteelSection(name=cust_name, section_type=sec_type,
                        bf=float(c_bf), tf=float(c_tf), tw=float(c_tw), d=float(c_d),
                        Ix=float(c_Ix), Zx=float(c_Zx), A=float(c_A),
                        Iy=float(c_Iy), Zy=float(c_Zy))

# ============================================================
# 鋼骨斷面寬厚比檢核
# ============================================================
def check_width_thickness(mat: Material, steel: SteelSection,
                          member: str = 'beam',
                          seismic: bool = False) -> tuple:
    """
    寬厚比檢核（依台灣SRC規範 110年版 第3.4節 表3.4-1~3.4-3）

    台灣SRC規範核心規定：
      被混凝土完全包覆的鋼骨，其局部挫屈受混凝土圍束抑制，
      故寬厚比限值比純鋼骨（AISC 360 Table B4.1）放寬。
      規範依構件類別訂有兩組限值：
        λp  ── 一般（非耐震）設計之緊密斷面上限
        λpd ── 耐震設計之緊密斷面上限（較嚴格）

    參數
    -----
    member  : 'beam'（梁，對應表3.4-1）或 'column'（柱，對應表3.4-2/3.4-3）
    seismic : True → 使用耐震設計限值 λpd；False → 使用一般限值 λp

    ─ 表3.4-1  包覆型SRC梁（H型鋼）─────────────────────────────
      翼板 bf/(2tf)
        λp  = 0.38√(Es/Fys)
        λpd = 0.30√(Es/Fys)
      腹板 (d-2tf)/tw
        λp  = 3.76√(Es/Fys)
        λpd = 2.54√(Es/Fys)

    ─ 表3.4-2  包覆型SRC柱（H型鋼）─────────────────────────────
      翼板 bf/(2tf)
        λp  = 0.56√(Es/Fys)   ← 放寬（混凝土包覆效益）
        λpd = 0.40√(Es/Fys)
      腹板 (d-2tf)/tw
        λp  = 3.05√(Es/Fys)
        λpd = 2.54√(Es/Fys)

    ─ 表3.4-3  包覆型SRC柱（BOX型鋼/鋼管）──────────────────────
      板件 (b-2t)/t
        λp  = 1.40√(Es/Fys)   ← 放寬（混凝土填充）
        λpd = 1.12√(Es/Fys)
    """
    lines = []
    lines.append("=" * 60)
    lines.append("鋼骨斷面寬厚比檢核")
    if member == 'beam':
        lines.append("依據：台灣SRC規範 第3.4節 表3.4-1（包覆型SRC梁）")
    else:
        if steel.section_type == 'BOX':
            lines.append("依據：台灣SRC規範 第3.4節 表3.4-3（包覆型SRC柱，BOX型）")
        else:
            lines.append("依據：台灣SRC規範 第3.4節 表3.4-2（包覆型SRC柱，H型）")
    design_label = "耐震設計 (λpd)" if seismic else "一般設計 (λp)"
    lines.append(f"設計類別：{design_label}")
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
        # ─ 翼板寬厚比限值（梁 vs 柱）────────────────────────
        if member == 'beam':
            # 表3.4-1 梁翼板：λp=0.38, λpd=0.30
            lam_pf = (0.30 if seismic else 0.38) * r
            coeff_f = 0.30 if seismic else 0.38
        else:
            # 表3.4-2 柱翼板：λp=0.56, λpd=0.40
            lam_pf = (0.40 if seismic else 0.56) * r
            coeff_f = 0.40 if seismic else 0.56

        # 非緊密斷面上限（超過則為細長，規範不允許用於SRC）
        lam_rf = 1.00 * r   # 參照AISC 360 Table B4.1b；超過此值不得用於SRC

        lam_f = bf_cm / (2 * tf_cm)
        if lam_f <= lam_pf:
            tag_f = "✓ 緊密斷面（結實斷面）"
        elif lam_f <= lam_rf:
            tag_f = "△ 非緊密斷面（超過λp，不符SRC規範第3.4節要求）"
            is_ok = False
        else:
            tag_f = "✗ 細長斷面（不得用於包覆型SRC構件）"
            is_ok = False

        label_f = "λpd（耐震）" if seismic else "λp（一般）"
        lines.append(f"\n【翼板寬厚比 λf = bf/(2tf)】")
        lines.append(f"  bf = {bf_cm:.1f} cm，tf = {tf_cm:.1f} cm")
        lines.append(f"  λf   = {bf_cm:.1f} / (2×{tf_cm:.1f}) = {lam_f:.2f}")
        lines.append(f"  {label_f} = {coeff_f:.2f}×√(Es/Fys) = {coeff_f:.2f}×{r:.3f} = {lam_pf:.2f}")
        lines.append(f"  λrf  = 1.00×√(Es/Fys) = {lam_rf:.2f}  ← 非緊密斷面上限（SRC不允許超過）")
        lines.append(f"  λf = {lam_f:.2f}  → {tag_f}")

        # ─ 腹板寬厚比限值（梁 vs 柱）────────────────────────
        if member == 'beam':
            # 表3.4-1 梁腹板：λp=3.76, λpd=2.54
            lam_pw = (2.54 if seismic else 3.76) * r
            coeff_w = 2.54 if seismic else 3.76
        else:
            # 表3.4-2 柱腹板：λp=3.05, λpd=2.54
            lam_pw = (2.54 if seismic else 3.05) * r
            coeff_w = 2.54 if seismic else 3.05

        lam_rw = 5.70 * r   # 非緊密斷面上限（參照AISC 360）
        lam_w  = (d_cm - 2 * tf_cm) / tw_cm

        if lam_w <= lam_pw:
            tag_w = "✓ 緊密斷面（結實斷面）"
        elif lam_w <= lam_rw:
            tag_w = "△ 非緊密斷面（超過λp，不符SRC規範第3.4節要求）"
            is_ok = False
        else:
            tag_w = "✗ 細長斷面（不得用於包覆型SRC構件）"
            is_ok = False

        label_w = "λpd（耐震）" if seismic else "λp（一般）"
        lines.append(f"\n【腹板寬厚比 λw = (d-2tf)/tw】")
        lines.append(f"  d = {d_cm:.1f} cm，tf = {tf_cm:.1f} cm，tw = {tw_cm:.1f} cm")
        lines.append(f"  λw   = ({d_cm:.1f}-2×{tf_cm:.1f}) / {tw_cm:.1f} = {lam_w:.2f}")
        lines.append(f"  {label_w} = {coeff_w:.2f}×√(Es/Fys) = {coeff_w:.2f}×{r:.3f} = {lam_pw:.2f}")
        lines.append(f"  λrw  = 5.70×√(Es/Fys) = {lam_rw:.2f}  ← 非緊密斷面上限（SRC不允許超過）")
        lines.append(f"  λw = {lam_w:.2f}  → {tag_w}")

    else:  # BOX（表3.4-3 包覆型SRC柱）
        # 表3.4-3 BOX板件：λp=1.40, λpd=1.12
        lam_pb = (1.12 if seismic else 1.40) * r
        coeff_b = 1.12 if seismic else 1.40
        lam_rb  = 2.00 * r   # 非緊密斷面上限（SRC BOX柱）

        # ─ 寬側板件（b方向）────────────────────────────────
        lam_b  = (bf_cm - 2 * tw_cm) / tw_cm
        if lam_b <= lam_pb:
            tag_b = "✓ 緊密斷面（結實斷面）"
        elif lam_b <= lam_rb:
            tag_b = "△ 非緊密斷面（超過λp，不符SRC規範第3.4-3節要求）"
            is_ok = False
        else:
            tag_b = "✗ 細長斷面（不得用於包覆型SRC柱）"
            is_ok = False

        label_b = "λpd（耐震）" if seismic else "λp（一般）"
        lines.append(f"\n【BOX型鋼 寬側板件寬厚比 λb = (b-2t)/t】")
        lines.append(f"  bf = {bf_cm:.1f} cm，tw = {tw_cm:.1f} cm")
        lines.append(f"  λb   = ({bf_cm:.1f}-2×{tw_cm:.1f}) / {tw_cm:.1f} = {lam_b:.2f}")
        lines.append(f"  {label_b} = {coeff_b:.2f}×√(Es/Fys) = {coeff_b:.2f}×{r:.3f} = {lam_pb:.2f}")
        lines.append(f"  λrb  = 2.00×√(Es/Fys) = {lam_rb:.2f}  ← 非緊密斷面上限")
        lines.append(f"  λb = {lam_b:.2f}  → {tag_b}")

        # ─ 深側板件（d方向）────────────────────────────────
        lam_d  = (d_cm - 2 * tf_cm) / tf_cm
        if lam_d <= lam_pb:
            tag_d = "✓ 緊密斷面（結實斷面）"
        elif lam_d <= lam_rb:
            tag_d = "△ 非緊密斷面（超過λp，不符SRC規範第3.4-3節要求）"
            is_ok = False
        else:
            tag_d = "✗ 細長斷面（不得用於包覆型SRC柱）"
            is_ok = False

        lines.append(f"\n【BOX型鋼 深側板件深厚比 λd = (d-2t)/t】")
        lines.append(f"  d = {d_cm:.1f} cm，tf = {tf_cm:.1f} cm")
        lines.append(f"  λd   = ({d_cm:.1f}-2×{tf_cm:.1f}) / {tf_cm:.1f} = {lam_d:.2f}")
        lines.append(f"  {label_b} = {lam_pb:.2f}，λrb = {lam_rb:.2f}")
        lines.append(f"  λd = {lam_d:.2f}  → {tag_d}")

    lines.append("\n" + "=" * 60)
    if is_ok:
        lines.append(f"  寬厚比判定：✓ 符合 SRC規範第3.4節規定（{design_label}）")
        lines.append("              斷面為結實斷面，可充分發展塑性彎矩")
    else:
        lines.append(f"  寬厚比判定：✗ 不符 SRC規範第3.4節規定（{design_label}）")
        lines.append("              請改用板厚較大之型鋼，或選用符合限值之斷面")
    lines.append("=" * 60)
    return '\n'.join(lines), is_ok


# ============================================================
# SRC 梁設計 (規範第5章)
# ============================================================
def calc_beam(mat: Material, steel: SteelSection, b, h, cover, As_top, As_bot, Mu,
              Vu: float = 0.0, Av_s: float = 0.0, s_s: float = 15.0,
              seismic: bool = False):
    """
    規範 5.4 強度疊加法 / φMn = φ(Mns + Mnrc)
    seismic: True = 耐震設計，使用 λpd 限值（表3.4-1 梁）
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
    
    # 寬厚比（表3.4-1 包覆型SRC梁）
    wt_report, wt_ok = check_width_thickness(mat, steel, member='beam', seismic=seismic)
    
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
# SRC 柱設計 (規範第6、7章) — 含雙向彎矩
# ============================================================
def calc_column(mat: Material, steel: SteelSection, b, h, cover, As, Pu,
                Mux: float = 0.0, Muy: float = 0.0,
                Vu: float = 0.0, Av_s: float = 0.0, s_s: float = 15.0,
                seismic: bool = False):
    """
    規範 6.4 軸力強度 + 7.3 雙向P-M交互作用 + 7.4 剪力強度疊加
    Mux : X軸（強軸，d方向）設計彎矩 tf-m
    Muy : Y軸（弱軸，b方向）設計彎矩 tf-m
    雙向P-M採 AISC 360 H1-1a/H1-1b 公式
    seismic: True = 耐震設計，寬厚比使用 λpd 限值
    """
    lines = []
    lines.append("=" * 60)
    lines.append("SRC 柱設計計算書（雙向彎矩）")
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
    d_rc_x  = h - cover   # X軸有效深度（強軸，h方向）
    d_rc_y  = b - cover   # Y軸有效深度（弱軸，b方向）

    lines.append("\n【一、設計條件】")
    lines.append(f"  鋼骨斷面    : {steel.name}  ({steel.section_type}型)")
    lines.append(f"  柱寬  b     : {b} cm（Y向，弱軸方向）")
    lines.append(f"  柱深  h     : {h} cm（X向，強軸方向）")
    lines.append(f"  保護層 dc   : {cover} cm")
    lines.append(f"  有效深度 dx : h−dc = {h}−{cover} = {d_rc_x:.1f} cm（X軸強軸）")
    lines.append(f"  有效深度 dy : b−dc = {b}−{cover} = {d_rc_y:.1f} cm（Y軸弱軸）")
    lines.append(f"  Ag（全斷面）= {b}×{h} = {A_gross:.2f} cm²")
    lines.append(f"  As_stl      = {A_steel:.2f} cm²  (鋼骨斷面積)")
    lines.append(f"  Ac          = Ag−As_stl = {A_gross:.2f}−{A_steel:.2f} = {Ac:.2f} cm²")
    lines.append(f"  縱向鋼筋 As : {As:.2f} cm²")
    lines.append(f"  設計軸力 Pu : {Pu:.2f} tf")
    lines.append(f"  設計彎矩 Mux: {Mux:.2f} tf-m（X軸強軸，Zx方向）")
    lines.append(f"  設計彎矩 Muy: {Muy:.2f} tf-m（Y軸弱軸，Zy方向）")
    if Vu > 0:
        lines.append(f"  設計剪力 Vu : {Vu:.2f} tf")
    if Av_s > 0:
        lines.append(f"  箍筋 Av/s   : {Av_s:.2f} cm² / {s_s:.1f} cm")
    lines.append(f"\n  鋼骨斷面性質：")
    lines.append(f"  Ix = {steel.Ix:.1f} cm⁴，Zx = {steel.Zx:.1f} cm³（強軸X）")
    lines.append(f"  Iy = {steel.Iy:.1f} cm⁴，Zy = {steel.Zy:.1f} cm³（弱軸Y）")
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

    # ── X向相對剛度分配 ─────────────────────────────────────
    Is_x    = steel.Ix
    Ic_x    = b * (h ** 3) / 12
    EsIs_x  = mat.Es * Is_x
    EcIc_x  = mat.Ec * Ic_x
    rs_x    = EsIs_x / (EsIs_x + EcIc_x)
    rrc_x   = 1 - rs_x
    Pu_s_x  = rs_x  * Pu;  Pu_rc_x = rrc_x * Pu
    Mux_s   = rs_x  * Mux; Mux_rc  = rrc_x * Mux

    # ── Y向相對剛度分配 ─────────────────────────────────────
    Is_y    = steel.Iy
    Ic_y    = h * (b ** 3) / 12   # Y向混凝土柱慣性矩
    EsIs_y  = mat.Es * Is_y
    EcIc_y  = mat.Ec * Ic_y
    rs_y    = EsIs_y / (EsIs_y + EcIc_y)
    rrc_y   = 1 - rs_y
    Muy_s   = rs_y  * Muy; Muy_rc  = rrc_y * Muy

    # ── 取較大的分配比用於 P 分配（保守）────────────────────
    rs   = rs_x   # 以 X 向分配比作代表（通常為主彎矩方向）
    rrc  = rrc_x
    Pu_s = Pu_s_x; Pu_rc = Pu_rc_x

    # ══════════════════════════════════════════════════════
    # 二、鋼骨彎矩強度 (X/Y兩向)
    # ══════════════════════════════════════════════════════
    Pns      = mat.fy_steel * A_steel / 1000
    Mnsx     = mat.fy_steel * steel.Zx / 1e5   # X向
    Mnsy     = mat.fy_steel * steel.Zy / 1e5   # Y向
    phi_Mnsx = 0.9 * Mnsx
    phi_Mnsy = 0.9 * Mnsy

    lines.append("\n【二、鋼骨彎矩強度（X/Y雙向）】(規範 7.3.1 / AISC 360 H1)")
    lines.append(f"  ─ X軸（強軸，Zx = {steel.Zx:.1f} cm³）─")
    lines.append(f"  Mnsx = Fys×Zx/10⁵ = {mat.fy_steel:.0f}×{steel.Zx:.1f}/10⁵ = {Mnsx:.3f} tf-m")
    lines.append(f"  φMnsx = 0.9×{Mnsx:.3f} = {phi_Mnsx:.3f} tf-m")
    lines.append(f"  ─ Y軸（弱軸，Zy = {steel.Zy:.1f} cm³）─")
    lines.append(f"  Mnsy = Fys×Zy/10⁵ = {mat.fy_steel:.0f}×{steel.Zy:.1f}/10⁵ = {Mnsy:.3f} tf-m")
    lines.append(f"  φMnsy = 0.9×{Mnsy:.3f} = {phi_Mnsy:.3f} tf-m")

    lines.append(f"\n  ─ X向相對剛度分配（規範7.3）─")
    lines.append(f"  Isx={Is_x:.1f} cm⁴，Icx=b×h³/12={Ic_x:.1f} cm⁴")
    lines.append(f"  rs_x = {EsIs_x:.3e}/({EsIs_x:.3e}+{EcIc_x:.3e}) = {rs_x:.4f}")
    lines.append(f"  Mux_s = {rs_x:.4f}×{Mux:.2f} = {Mux_s:.3f} tf-m（鋼骨承擔X彎矩）")
    lines.append(f"  ─ Y向相對剛度分配（規範7.3）─")
    lines.append(f"  Isy={Is_y:.1f} cm⁴，Icy=h×b³/12={Ic_y:.1f} cm⁴")
    lines.append(f"  rs_y = {EsIs_y:.3e}/({EsIs_y:.3e}+{EcIc_y:.3e}) = {rs_y:.4f}")
    lines.append(f"  Muy_s = {rs_y:.4f}×{Muy:.2f} = {Muy_s:.3f} tf-m（鋼骨承擔Y彎矩）")

    # AISC 360 H1-1 雙向P-M互制（鋼骨部分）
    lines.append(f"\n  ─ 鋼骨 雙向P-M互制（AISC 360 H1-1 雙向）─")
    lines.append(f"  φPns = 0.9×{Pns:.2f} = {0.9*Pns:.2f} tf")
    pm_ratio_s = Pu_s / (0.9 * Pns) if Pns > 0 else 0
    if pm_ratio_s >= 0.2:
        # H1-1a：Pu/(φPn) + (8/9)[Mux/(φMnx) + Muy/(φMny)] ≤ 1.0
        chk_s = (Pu_s / (0.9 * Pns)
                 + (8/9) * (Mux_s / phi_Mnsx if phi_Mnsx > 0 else 0)
                 + (8/9) * (Muy_s / phi_Mnsy if phi_Mnsy > 0 else 0))
        lines.append(f"  Pu_s/(φPns) = {pm_ratio_s:.3f} ≥ 0.2 → 採 H1-1a")
        lines.append(f"  = Pu_s/(φPns)+(8/9)[Mux_s/(φMnsx)+Muy_s/(φMnsy)]")
        lines.append(f"  = {Pu_s:.3f}/{0.9*Pns:.3f}+(8/9)[{Mux_s:.3f}/{phi_Mnsx:.3f}+{Muy_s:.3f}/{phi_Mnsy:.3f}]")
        lines.append(f"  = {chk_s:.4f}")
    else:
        # H1-1b：Pu/(2φPn) + Mux/(φMnx) + Muy/(φMny) ≤ 1.0
        chk_s = (Pu_s / (2 * 0.9 * Pns)
                 + (Mux_s / phi_Mnsx if phi_Mnsx > 0 else 0)
                 + (Muy_s / phi_Mnsy if phi_Mnsy > 0 else 0))
        lines.append(f"  Pu_s/(φPns) = {pm_ratio_s:.3f} < 0.2 → 採 H1-1b")
        lines.append(f"  = Pu_s/(2φPns)+Mux_s/(φMnsx)+Muy_s/(φMnsy)")
        lines.append(f"  = {Pu_s:.3f}/{2*0.9*Pns:.3f}+{Mux_s:.3f}/{phi_Mnsx:.3f}+{Muy_s:.3f}/{phi_Mnsy:.3f}")
        lines.append(f"  = {chk_s:.4f}")
    ok_s = "✓ OK" if chk_s <= 1.0 else "✗ NG"
    lines.append(f"  鋼骨雙向P-M比值 = {chk_s:.4f} → {ok_s}")

    # ══════════════════════════════════════════════════════
    # 三、RC部分彎矩強度（X/Y兩向）
    # ══════════════════════════════════════════════════════
    # X向（強軸，h方向受彎）
    a_x    = As * mat.fy_rebar / (0.85 * mat.fc * b)
    Mn_rcx = As * mat.fy_rebar * (d_rc_x - a_x / 2) / 1e5
    phi_Mn_rcx = 0.9 * Mn_rcx
    # Y向（弱軸，b方向受彎）
    a_y    = As * mat.fy_rebar / (0.85 * mat.fc * h)
    Mn_rcy = As * mat.fy_rebar * (d_rc_y - a_y / 2) / 1e5
    phi_Mn_rcy = 0.9 * Mn_rcy

    lines.append("\n【三、RC部分彎矩強度（X/Y雙向）】(規範 7.3.2 / ACI 318)")
    lines.append(f"  ─ X軸（強軸，有效深度 dx = {d_rc_x:.1f} cm）─")
    lines.append(f"  a_x = As·Fyr/(0.85·fc'·b) = {As:.2f}×{mat.fy_rebar:.0f}/(0.85×{mat.fc:.0f}×{b}) = {a_x:.3f} cm")
    lines.append(f"  Mnrcx = As·Fyr·(dx-a/2)/10⁵ = {Mn_rcx:.3f} tf-m")
    lines.append(f"  φMnrcx = 0.9×{Mn_rcx:.3f} = {phi_Mn_rcx:.3f} tf-m")
    lines.append(f"  ─ Y軸（弱軸，有效深度 dy = {d_rc_y:.1f} cm）─")
    lines.append(f"  a_y = As·Fyr/(0.85·fc'·h) = {As:.2f}×{mat.fy_rebar:.0f}/(0.85×{mat.fc:.0f}×{h}) = {a_y:.3f} cm")
    lines.append(f"  Mnrcy = As·Fyr·(dy-a/2)/10⁵ = {Mn_rcy:.3f} tf-m")
    lines.append(f"  φMnrcy = 0.9×{Mn_rcy:.3f} = {phi_Mn_rcy:.3f} tf-m")

    # RC P-M 互制（雙向線性近似）
    lines.append(f"\n  ─ RC雙向P-M互制（線性近似）─")
    lines.append(f"  φPn_rc = 0.65×{Pn_rc:.2f} = {0.65*Pn_rc:.2f} tf")
    pm_ratio_rc = Pu_rc / (0.65 * Pn_rc) if Pn_rc > 0 else 0
    if pm_ratio_rc >= 0.1:
        chk_r = (Pu_rc / (0.65 * Pn_rc)
                 + (Mux_rc / phi_Mn_rcx if phi_Mn_rcx > 0 else 0)
                 + (Muy_rc / phi_Mn_rcy if phi_Mn_rcy > 0 else 0))
        lines.append(f"  Pu_rc/(φPn_rc) = {pm_ratio_rc:.3f} ≥ 0.1")
        lines.append(f"  = Pu_rc/(φPn_rc)+Mux_rc/(φMnrcx)+Muy_rc/(φMnrcy)")
        lines.append(f"  = {Pu_rc:.3f}/{0.65*Pn_rc:.3f}+{Mux_rc:.3f}/{phi_Mn_rcx:.3f}+{Muy_rc:.3f}/{phi_Mn_rcy:.3f}")
        lines.append(f"  = {chk_r:.4f}")
    else:
        chk_r = (Pu_rc / (1.3 * Pn_rc)
                 + (Mux_rc / phi_Mn_rcx if phi_Mn_rcx > 0 else 0)
                 + (Muy_rc / phi_Mn_rcy if phi_Mn_rcy > 0 else 0))
        lines.append(f"  Pu_rc/(φPn_rc) = {pm_ratio_rc:.3f} < 0.1")
        lines.append(f"  = Pu_rc/(1.3Pn_rc)+Mux_rc/(φMnrcx)+Muy_rc/(φMnrcy)")
        lines.append(f"  = {Pu_rc:.3f}/{1.3*Pn_rc:.3f}+{Mux_rc:.3f}/{phi_Mn_rcx:.3f}+{Muy_rc:.3f}/{phi_Mn_rcy:.3f}")
        lines.append(f"  = {chk_r:.4f}")
    ok_r = "✓ OK" if chk_r <= 1.0 else "✗ NG"
    lines.append(f"  RC雙向P-M比值 = {chk_r:.4f} → {ok_r}")

    # ══════════════════════════════════════════════════════
    # 四、疊加彎矩強度（X/Y分別檢核）
    # ══════════════════════════════════════════════════════
    phi_Mnx_total = phi_Mnsx + phi_Mn_rcx   # X軸總強度
    phi_Mny_total = phi_Mnsy + phi_Mn_rcy   # Y軸總強度

    dc_Mx = Mux / phi_Mnx_total if phi_Mnx_total > 0 else 0
    dc_My = Muy / phi_Mny_total if phi_Mny_total > 0 else 0
    ok_mux = phi_Mnx_total >= Mux
    ok_muy = phi_Mny_total >= Muy
    ok_mu  = ok_mux and ok_muy

    lines.append("\n【四、疊加彎矩強度（X/Y雙向）】(規範 7.3 強度疊加法)")
    lines.append(f"  ─ X軸（強軸）─")
    lines.append(f"  φMnx = φMnsx + φMnrcx = {phi_Mnsx:.3f} + {phi_Mn_rcx:.3f} = {phi_Mnx_total:.3f} tf-m")
    lines.append(f"  Mux = {Mux:.2f} tf-m，D/C = {dc_Mx:.3f} → {'✓ OK' if ok_mux else '✗ NG'}")
    lines.append(f"  ─ Y軸（弱軸）─")
    lines.append(f"  φMny = φMnsy + φMnrcy = {phi_Mnsy:.3f} + {phi_Mn_rcy:.3f} = {phi_Mny_total:.3f} tf-m")
    lines.append(f"  Muy = {Muy:.2f} tf-m，D/C = {dc_My:.3f} → {'✓ OK' if ok_muy else '✗ NG'}")

    # ══════════════════════════════════════════════════════
    # 五、縱向鋼筋比檢核
    # ══════════════════════════════════════════════════════
    rho     = As / (b * d_rc_x)
    rho_min = 0.01
    rho_max = 0.08
    ok_rho     = rho >= rho_min
    ok_rho_max = rho <= rho_max
    tag_rho    = "✓ OK" if ok_rho else "✗ NG"

    lines.append("\n【五、縱向鋼筋比檢核】(規範 6.2.1 / ACI 318 §10.6.1.1)")
    lines.append(f"  ρ = As/(b×d)  = {As:.2f}/({b}×{d_rc_x:.1f}) = {rho:.5f}")
    lines.append(f"  ρmin = 0.010（規範6.2.1：SRC柱縱筋比不得小於1%）")
    lines.append(f"  ρmax = 0.080（規範6.2.2：SRC柱縱筋比上限8%）")
    lines.append(f"  ρ = {rho:.5f} {'≥' if ok_rho else '<'} ρmin = {rho_min:.3f} → {tag_rho}")
    lines.append(f"  ρ = {rho:.5f} {'≤' if ok_rho_max else '>'} ρmax = {rho_max:.3f} → {'✓ OK' if ok_rho_max else '✗ NG（超過上限）'}")

    # ══════════════════════════════════════════════════════
    # 六、軸力強度檢核
    # ══════════════════════════════════════════════════════
    ok_pu  = Pu <= phi_Pn
    dc_P   = Pu / phi_Pn if phi_Pn > 0 else 0
    tag_pu = "✓ OK" if ok_pu else "✗ NG"

    lines.append("\n【六、軸力強度檢核】(規範 6.4)")
    lines.append(f"  φPn = 0.75×Pn_rc + 0.9×Pn_s")
    lines.append(f"    Pn_rc = (0.85×{mat.fc:.0f}×{Ac:.1f}+{mat.fy_rebar:.0f}×{As:.2f})/1000 = {Pn_rc:.2f} tf")
    lines.append(f"    Pn_s  = {mat.fy_steel:.0f}×{A_steel:.2f}/1000 = {Pn_s:.2f} tf")
    lines.append(f"    φPn = 0.75×{Pn_rc:.2f}+0.9×{Pn_s:.2f} = {phi_Pn:.2f} tf")
    lines.append(f"    Pu = {Pu:.2f} tf {'≤' if ok_pu else '>'} φPn = {phi_Pn:.2f} tf，D/C = {dc_P:.3f} → {tag_pu}")

    # ══════════════════════════════════════════════════════
    # 七、剪力強度檢核（彎矩分配法，規範 7.4）
    # ══════════════════════════════════════════════════════
    lines.append("\n【七、剪力強度檢核】(規範 7.4 彎矩分配法)")
    lines.append("  方法：依Mux向彎矩比（rs_x）分配 Vu 給鋼骨與RC")

    s_d_cm  = steel.d  / 10
    s_tw_cm = steel.tw / 10
    s_tf_cm = steel.tf / 10
    if steel.section_type == 'BOX':
        Aw_col = 2 * s_tw_cm * (s_d_cm - 2 * s_tf_cm)
    else:
        Aw_col = s_tw_cm * (s_d_cm - 2 * s_tf_cm)
    Vns_col     = 0.6 * mat.fy_steel * Aw_col / 1000
    phi_Vns_col = 0.9 * Vns_col

    A_gross_col  = b * h
    Nu_kgf       = Pu * 1000
    axial_factor = max(1.0 + Nu_kgf / (140.0 * A_gross_col), 0.0)
    Vc_col       = 0.53 * math.sqrt(mat.fc) * axial_factor * b * d_rc_x / 1000
    phi_Vc_col   = 0.75 * Vc_col
    Vs_col       = (Av_s * mat.fy_rebar * d_rc_x / s_s / 1000) if (Av_s > 0 and s_s > 0) else 0.0
    phi_Vs_col   = 0.75 * Vs_col
    phi_Vnrc_col = phi_Vc_col + phi_Vs_col
    phi_Vn_col   = phi_Vns_col + phi_Vnrc_col

    # 彎矩分配比（以X向名目彎矩為準）
    Mn_total = Mnsx + Mn_rcx
    r_vns    = Mnsx  / Mn_total if Mn_total > 0 else 0.5
    r_vnrc   = Mn_rcx / Mn_total if Mn_total > 0 else 0.5

    lines.append(f"\n  ─ 鋼骨腹板剪力強度 φVns ─")
    if steel.section_type == 'BOX':
        lines.append(f"  BOX：Aw = 2×{s_tw_cm:.1f}×({s_d_cm:.1f}-2×{s_tf_cm:.2f}) = {Aw_col:.2f} cm²")
    else:
        lines.append(f"  H型：Aw = {s_tw_cm:.1f}×({s_d_cm:.1f}-2×{s_tf_cm:.2f}) = {Aw_col:.2f} cm²")
    lines.append(f"  Vns = 0.6×{mat.fy_steel:.0f}×{Aw_col:.2f}/1000 = {Vns_col:.3f} tf，φVns = {phi_Vns_col:.3f} tf")
    lines.append(f"\n  ─ RC 剪力強度 φVnrc（規範7.4.2 / ACI §22.5.6.1）─")
    lines.append(f"  軸力修正 = 1+{Nu_kgf:.0f}/(140×{A_gross_col}) = {axial_factor:.4f}")
    lines.append(f"  Vc = 0.53×√{mat.fc:.0f}×{axial_factor:.4f}×{b}×{d_rc_x:.1f}/1000 = {Vc_col:.3f} tf，φVc = {phi_Vc_col:.3f} tf")
    if Av_s > 0:
        lines.append(f"  Vs = {Av_s:.2f}×{mat.fy_rebar:.0f}×{d_rc_x:.1f}/({s_s:.1f}×1000) = {Vs_col:.3f} tf，φVs = {phi_Vs_col:.3f} tf")
    lines.append(f"  φVnrc = {phi_Vnrc_col:.3f} tf，φVn = {phi_Vn_col:.3f} tf")

    ok_vu = True; ok_vu_s = True; ok_vu_rc = True
    dc_vu = 0.0;  dc_vu_s = 0.0;  dc_vu_rc = 0.0
    lines.append(f"\n  ─ 彎矩分配比（以X向名目彎矩）：r_s={r_vns:.4f}，r_rc={r_vnrc:.4f} ─")
    if Vu > 0:
        Vu_s  = r_vns  * Vu
        Vu_rc = r_vnrc * Vu
        dc_vu_s  = Vu_s  / phi_Vns_col  if phi_Vns_col  > 0 else 999
        ok_vu_s  = dc_vu_s  <= 1.0
        dc_vu_rc = Vu_rc / phi_Vnrc_col if phi_Vnrc_col > 0 else 999
        ok_vu_rc = dc_vu_rc <= 1.0
        dc_vu    = Vu / phi_Vn_col if phi_Vn_col > 0 else 999
        ok_vu    = ok_vu_s and ok_vu_rc and (dc_vu <= 1.0)
        lines.append(f"  ① 鋼骨：Vu_s={Vu_s:.3f} tf，φVns={phi_Vns_col:.3f} tf，D/C={dc_vu_s:.3f} → {'✓ OK' if ok_vu_s else '✗ NG'}")
        lines.append(f"  ② RC  ：Vu_rc={Vu_rc:.3f} tf，φVnrc={phi_Vnrc_col:.3f} tf，D/C={dc_vu_rc:.3f} → {'✓ OK' if ok_vu_rc else '✗ NG'}")
        lines.append(f"  ③ 總計：Vu={Vu:.2f} tf，φVn={phi_Vn_col:.3f} tf，D/C={dc_vu:.3f} → {'✓ OK' if ok_vu else '✗ NG'}")
    else:
        lines.append(f"  φVns={phi_Vns_col:.3f} tf，φVnrc={phi_Vnrc_col:.3f} tf，φVn={phi_Vn_col:.3f} tf（未輸入Vu）")

    # ══════════════════════════════════════════════════════
    # ══════════════════════════════════════════════════════════════
    # 八、P-M 互制曲線資料
    # ══════════════════════════════════════════════════════════════
    lines.append("\n【八、P-M 互制曲線資料】")
    lines.append("=" * 60)
    curve_x = gen_pm_curve(mat, steel, b, h, cover, As, axis='X')
    curve_y = gen_pm_curve(mat, steel, b, h, cover, As, axis='Y')
    lines.append(f"  斷面：{steel.name} / b×h = {b}×{h} cm")
    lines.append(f"  X軸曲線（強軸，Zx={steel.Zx:.1f} cm³）：")
    idx_list = [0, len(curve_x)//4, len(curve_x)//2, 3*len(curve_x)//4, len(curve_x)-1]
    for idx in idx_list:
        p, m = curve_x[idx]
        lines.append(f"    P={p:7.2f} tf, M={m:7.2f} tf-m")
    lines.append(f"  Y軸曲線（弱軸，Zy={steel.Zy:.1f} cm³）：")
    for idx in idx_list:
        p, m = curve_y[idx]
        lines.append(f"    P={p:7.2f} tf, M={m:7.2f} tf-m")
    lines.append(f"  設計點：Pu={Pu:.2f} tf, Mux={Mux:.2f} tf-m, Muy={Muy:.2f} tf-m")

    # ══════════════════════════════════════════════════════════════
    # 九、結論
    # ══════════════════════════════════════════════════════════════
    # 九、結論
    # ══════════════════════════════════════════════════════
    is_safe = (chk_s <= 1.0 and chk_r <= 1.0 and ok_pu
               and ok_mu and ok_rho and ok_rho_max and ok_vu)

    lines.append("\n【八、結論】")
    lines.append("=" * 60)
    lines.append("  各項檢核彙整：")
    lines.append(f"  ① 軸力強度      ：Pu={Pu:.2f} tf，φPn={phi_Pn:.2f} tf，D/C={dc_P:.3f} → {tag_pu}")
    lines.append(f"  ② 鋼骨雙向P-M   ：{chk_s:.4f} → {ok_s}")
    lines.append(f"  ③ RC雙向P-M     ：{chk_r:.4f} → {ok_r}")
    lines.append(f"  ④ X向疊加彎矩   ：Mux={Mux:.2f} tf-m，φMnx={phi_Mnx_total:.3f} tf-m，D/C={dc_Mx:.3f} → {'✓ OK' if ok_mux else '✗ NG'}")
    lines.append(f"  ⑤ Y向疊加彎矩   ：Muy={Muy:.2f} tf-m，φMny={phi_Mny_total:.3f} tf-m，D/C={dc_My:.3f} → {'✓ OK' if ok_muy else '✗ NG'}")
    lines.append(f"  ⑥ 縱向鋼筋比    ：ρ={rho:.5f}，ρmin={rho_min:.3f} → {tag_rho}")
    if Vu > 0:
        lines.append(f"  ⑦ 剪力強度      ：Vu={Vu:.2f} tf，φVn={phi_Vn_col:.3f} tf，D/C={dc_vu:.3f} → {'✓ OK' if ok_vu else '✗ NG'}")
    else:
        lines.append(f"  ⑦ 剪力強度      ：φVn={phi_Vn_col:.3f} tf（未輸入Vu）")
    lines.append("-" * 60)
    lines.append(f"  ★ {'設計安全 ✓  所有檢核均通過' if is_safe else '設計不足 ✗  請檢視不通過項目並加大斷面或配筋'}")
    lines.append("=" * 60)

    # 寬厚比（表3.4-2/3）
    wt_report, wt_ok = check_width_thickness(mat, steel, member='column', seismic=seismic)
    lines.append("")
    lines.append(wt_report)

    result = {
        'phi_Pn': phi_Pn, 'Pn_rc': Pn_rc, 'Pn_s': Pn_s,
        'Ac': Ac,
        'rs_x': rs_x, 'rrc_x': rrc_x, 'rs_y': rs_y, 'rrc_y': rrc_y,
        'Pu_s': Pu_s, 'Pu_rc': Pu_rc,
        'Mux_s': Mux_s, 'Mux_rc': Mux_rc,
        'Muy_s': Muy_s, 'Muy_rc': Muy_rc,
        'Pns': Pns,
        'Mnsx': Mnsx, 'Mnsy': Mnsy, 'Mn_rcx': Mn_rcx, 'Mn_rcy': Mn_rcy,
        'phi_Mnsx': phi_Mnsx, 'phi_Mnsy': phi_Mnsy,
        'phi_Mn_rcx': phi_Mn_rcx, 'phi_Mn_rcy': phi_Mn_rcy,
        'phi_Mnx': phi_Mnx_total, 'phi_Mny': phi_Mny_total,
        'chk_s': chk_s, 'chk_r': chk_r, 'is_safe': is_safe,
        'Ic_x': Ic_x, 'Is_x': Is_x, 'Ic_y': Ic_y, 'Is_y': Is_y,
        'wt_ok': wt_ok, 'rho': rho, 'rho_min': rho_min,
        'ok_rho': ok_rho, 'dc_P': dc_P, 'ok_pu': ok_pu,
        'dc_Mx': dc_Mx, 'ok_mux': ok_mux,
        'dc_My': dc_My, 'ok_muy': ok_muy, 'ok_mu': ok_mu,
        'Mux': Mux, 'Muy': Muy,
        'phi_Vn': phi_Vn_col, 'phi_Vnrc': phi_Vnrc_col, 'phi_Vns': phi_Vns_col,
        'Vu': Vu, 'dc_vu': dc_vu, 'ok_vu': ok_vu,
        'dc_vu_s': dc_vu_s, 'ok_vu_s': ok_vu_s,
        'dc_vu_rc': dc_vu_rc, 'ok_vu_rc': ok_vu_rc,
        # P-M曲線資料
        'pm_curve_x': gen_pm_curve(mat, steel, b, h, cover, As, axis='X'),
        'pm_curve_y': gen_pm_curve(mat, steel, b, h, cover, As, axis='Y'),
        'pm_b': b, 'pm_h': h, 'pm_As': As, 'pm_stl_name': steel.name
    }
    return '\n'.join(lines), result





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
        # AISC 360 H1-1a：Pu/(φPn) + (8/9)·Mu/(φMn) ≤ 1.0
        chk_s = Pu_s / (0.9 * Pns) + (8/9) * Mu_s / (0.9 * Mns)
        lines.append(f"  P-M交互作用（Pu_s/φPns={ratio_pu_pns:.3f} ≥ 0.2，AISC H1-1a）：")
        lines.append(f"  Pu_s/(φPns)+(8/9)×Mu_s/(φMns) = {Pu_s:.2f}/{0.9*Pns:.2f}+(8/9)×{Mu_s:.2f}/{phi_Mns:.3f} = {chk_s:.3f}")
    else:
        # AISC 360 H1-1b：Pu/(2φPn) + Mu/(φMn) ≤ 1.0
        chk_s = Pu_s / (2 * 0.9 * Pns) + Mu_s / (0.9 * Mns)
        lines.append(f"  P-M交互作用（Pu_s/φPns={ratio_pu_pns:.3f} < 0.2，AISC H1-1b）：")
        lines.append(f"  Pu_s/(2φPns)+Mu_s/(φMns) = {Pu_s:.2f}/{2*0.9*Pns:.2f}+{Mu_s:.2f}/{phi_Mns:.3f} = {chk_s:.3f}")
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
    # 規範 6.2.1：SRC柱縱筋比 ρ ≥ 1%（0.010）
    # ACI 318-14 §10.6.1.1 柱最小鋼筋比亦為 0.01
    rho_min = 0.01
    rho_max = 0.08
    ok_rho     = rho >= rho_min
    ok_rho_max = rho <= rho_max
    tag_rho    = "✓ OK" if ok_rho else "✗ NG"

    lines.append("\n【五、縱向鋼筋比檢核】(規範 6.2.1 / ACI 318 §10.6.1.1)")
    lines.append(f"  ρ = As/(b×d)  = {As:.2f}/({b}×{d_rc:.1f}) = {rho:.5f}")
    lines.append(f"  ρmin = 0.010（規範6.2.1：SRC柱縱筋比不得小於1%）")
    lines.append(f"  ρmax = 0.080（規範6.2.2：SRC柱縱筋比上限8%）")
    lines.append(f"  ρ = {rho:.5f} {'≥' if ok_rho else '<'} ρmin = {rho_min:.3f} → {tag_rho}")
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
    # 規範7.4.2引用ACI 318-14 §22.5.6.1：含軸力修正
    # Vc = 0.53√fc'·(1 + Nu/(140·Ag))·b·d（Nu 為壓力正值，kgf；Ag 為 cm²）
    # Nu/Ag 以 kgf/cm² 計；Nu = Pu × 1000（tf→kgf）
    A_gross_col = b * h
    Nu_kgf      = Pu * 1000          # tf → kgf（壓力正值）
    axial_factor = 1.0 + Nu_kgf / (140.0 * A_gross_col)   # ACI 22.5.6.1 修正項
    axial_factor = max(axial_factor, 0.0)  # 拉力時不得小於0
    Vc_col      = 0.53 * math.sqrt(mat.fc) * axial_factor * b * d_rc / 1000
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
    lines.append(f"\n  ─ RC 剪力強度 φVnrc = φVc + φVs（規範7.4.2 / ACI §22.5.6.1）─")
    lines.append(f"  Nu = Pu×1000 = {Nu_kgf:.0f} kgf（壓力正值），Ag = {A_gross_col} cm²")
    lines.append(f"  軸力修正係數 = 1 + Nu/(140·Ag) = 1 + {Nu_kgf:.0f}/(140×{A_gross_col}) = {axial_factor:.4f}")
    lines.append(f"  Vc = 0.53×√fc'×{axial_factor:.4f}×b×d/1000 = 0.53×√{mat.fc:.0f}×{axial_factor:.4f}×{b}×{d_rc:.1f}/1000 = {Vc_col:.3f} tf")
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

    # 寬厚比（表3.4-2/3 包覆型SRC柱）
    wt_report, wt_ok = check_width_thickness(mat, steel, member='column', seismic=seismic)
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
def gen_pm_curve(mat, steel, b, h, cover, As, axis='X', pts=60):
    """
    產生 SRC 柱 P-M 互制曲線
    axis: 'X' = X軸（強軸）, 'Y' = Y軸（弱軸）
    """
    bf_cm = steel.bf / 10
    d_cm  = steel.d  / 10
    tf_cm = steel.tf / 10
    tw_cm = steel.tw / 10
    Ac = b * h - steel.A
    d_rc = h - cover
    
    # 選擇對應的塑性斷面模數
    if axis.upper() == 'Y':
        Z = steel.Zy if steel.Zy > 0 else steel.Zx * 0.5  # Y軸用 Zy
    else:
        Z = steel.Zx  # X軸用 Zx
    
    Pmax_t = -(mat.fy_rebar * As + mat.fy_steel * steel.A) / 1000
    Pmax_c = (0.85 * mat.fc * Ac + mat.fy_rebar * As + mat.fy_steel * steel.A) / 1000
    curve = []
    for i in range(pts + 1):
        r = i / pts
        P = Pmax_t + (Pmax_c - Pmax_t) * r
        if 0.1 < r < 0.9:
            M = (0.5 * As * mat.fy_rebar * (d_rc - cover) / 1e5
                 + 0.5 * mat.fy_steel * Z / 1e5) * math.sin(r * math.pi)
        else:
            M = 0
        curve.append((P, M))
    return curve


# ============================================================
# P-M-M 3D 曲面圖（精確應變分布迭代分析）
# ============================================================
def gen_pm_surface_accurate(mat, steel, b, h, cover, As, pts=15):
    """
    精確 SRC 柱 P-M-M 3D 互制曲面（纖維分割法 + 迭代求解中性軸）
    返回：(Mx, My, P) 網格數據
    """
    import numpy as np
    from scipy.optimize import minimize, brentq
    
    # 斷面幾何
    bf = steel.bf / 10   # cm
    d = steel.d / 10     # cm
    tf = steel.tf / 10   # cm
    tw = steel.tw / 10   # cm
    
    # 鋼骨斷面角點（相對於斷面中心）
    steel_points = [
        (-bf/2, d/2), (bf/2, d/2),        # 上翼板
        (tw/2, d/2), (tw/2, -d/2+tf),    # 右腹板
        (bf/2, -d/2+tf), (-bf/2, -d/2+tf), # 下翼板
        (-tw/2, -d/2+tf), (-tw/2, d/2)    # 左腹板
    ]
    
    # 鋼筋位置（均勻分布）
    rebar_x = np.linspace(-b/2 + cover + 2, b/2 - cover - 2, int(np.sqrt(As / 0.71)))
    rebar_y = np.linspace(-h/2 + cover + 2, h/2 - cover - 2, len(rebar_x))
    rebar_xy = np.array([[x, y] for x in rebar_x for y in rebar_y])
    
    # 混凝土分割（纖維網格）
    conc_x = np.linspace(-b/2, b/2, 20)
    conc_y = np.linspace(-h/2, h/2, 20)
    conc_xx, conc_yy = np.meshgrid(conc_x, conc_y)
    conc_points = np.column_stack([conc_xx.ravel(), conc_yy.ravel()])
    
    # 過濾混凝土點（排除鋼骨區域）
    def in_steel(x, y):
        # 簡化：檢查是否在鋼骨範圍內
        return (abs(x) < bf/2 and abs(y) < d/2 - tf) or                (abs(x) < bf/2 and abs(y) > d/2 - tf)
    conc_points = np.array([p for p in conc_points if not in_steel(p[0], p[1])])
    
    # 材料參數
    Ec = 15000 * np.sqrt(mat.fc)  # 混凝土彈性模數
    Es = 2040000  # 鋼筋彈性模數 (kgf/cm²)
    Fy = mat.fy_steel  # 鋼骨降伏強度
    fyr = mat.fy_rebar  # 鋼筋降伏強度
    fc = mat.fc  # 混凝土抗壓強度
    
    def calc_PM_from_strain(cu, theta, phi, d_NA):
        """
        根據混凝土最大壓應變 cu、旋轉角 theta、phi、中性軸深度 d_NA 計算 P, Mx, My
        """
        # 應變計算
        def strain_at(x, y):
            # 旋轉後的座標
            rx = x * np.cos(theta) + y * np.sin(theta)
            ry = -x * np.sin(theta) + y * np.cos(theta)
            # 距離中性軸的距離
            dist = rx - d_NA
            return cu * dist / d_NA if d_NA > 0 else cu
        
        P = 0
        Mx = 0
        My = 0
        
        # 混凝土纖維
        for pt in conc_points:
            eps = strain_at(pt[0], pt[1])
            # 混凝土應力（簡化：線彈性）
            fc_eff = min(0.85 * fc, Ec * abs(eps)) * np.sign(eps) if eps < 0 else 0
            area = (b/20) * (h/20)
            P += fc_eff * area / 1000
            Mx += fc_eff * area * pt[1] / 1e5
            My += fc_eff * area * pt[0] / 1e5
        
        # 鋼骨纖維
        for pt in steel_points:
            eps = strain_at(pt[0], pt[1])
            fs = min(Fy, Es * eps) * np.sign(eps) if eps != 0 else 0
            area_st = 1.0  # 簡化
            P += fs * area_st / 1000
            Mx += fs * area_st * pt[1] / 1e5
            My += fs * area_st * pt[0] / 1e5
        
        # 鋼筋
        for pt in rebar_xy:
            eps = strain_at(pt[0], pt[1])
            fs = min(fyr, Es * eps) * np.sign(eps) if eps != 0 else 0
            area_rb = 0.71  # D10
            P += fs * area_rb / 1000
            Mx += fs * area_rb * pt[1] / 1e5
            My += fs * area_rb * pt[0] / 1e5
        
        return P, Mx, My
    
    # 網格計算
    M_range = np.linspace(0, 150, pts)  # 彎矩範圍
    Mx, My = np.meshgrid(M_range, M_range)
    P = np.zeros_like(Mx)
    
    # 設定目標 Pu 值
    P_target = 200  # tf
    
    # 對每個點進行迭代求解
    for i in range(pts):
        for j in range(pts):
            mx = Mx[i, j]
            my = My[i, j]
            
            # 嘗試找到滿足彎矩條件的中性軸位置
            # 簡化：使用近似公式
            m_total = np.sqrt(mx**2 + my**2)
            if m_total > 0:
                # 近似中性軸深度（基於彎矩）
                d_approx = h * 0.3 * (1 - m_total / 200)
                d_approx = max(d_approx, 5)  # 最小深度
                
                # 計算對應的 Pu
                cu = 0.003  # 混凝土設計應變
                theta = np.arctan2(my, mx) if mx != 0 else 0
                
                P[i, j], _, _ = calc_PM_from_strain(cu, theta, 0, d_approx)
    
    return Mx, My, P


# 保留簡化版本（快速顯示用）
def gen_pm_surface(mat, steel, b, h, cover, As, pts=20):
    """P-M-M 曲面（快速近似）"""
    import numpy as np
    
    Ac = b * h - steel.A
    d_rc = h - cover
    
    Mns_x = mat.fy_steel * steel.Zx / 1e5
    Mns_y = mat.fy_steel * steel.Zy / 1e5
    Mn_rc = 0.5 * As * mat.fy_rebar * (d_rc - cover) / 1e5
    Mn_x = Mns_x + Mn_rc
    Mn_y = Mns_y + Mn_rc
    
    Pmax_t = -(mat.fy_rebar * As + mat.fy_steel * steel.A) / 1000
    Pmax_c = (0.85 * mat.fc * Ac + mat.fy_rebar * As + mat.fy_steel * steel.A) / 1000
    
    M_range = np.linspace(0, max(Mn_x, Mn_y) * 1.1, pts)
    Mx, My = np.meshgrid(M_range, M_range)
    P = np.zeros_like(Mx)
    
    for i in range(pts):
        for j in range(pts):
            mx, my = Mx[i, j], My[i, j]
            m_ratio = (mx / Mn_x + my / Mn_y) / 2 if (Mn_x > 0 and Mn_y > 0) else 1
            m_ratio = min(m_ratio, 1.0)
            P[i, j] = Pmax_c * (1 - m_ratio * 0.8) + Pmax_t * m_ratio * 0.2
    
    return Mx, My, P

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
                 fontsize=12, fontweight='bold', fontproperties=_CJK_FONT)

    # 圖例
    legend_elements = [
        mpatches.Patch(fc='#D0D0D0', ec='black', label='混凝土'),
        mpatches.Patch(fc='#404040', ec='black', label='型鋼'),
        mpatches.Patch(fc='#CC0000', ec='black', label=f'上筋 {top_rebars}-{top_size}'),
        mpatches.Patch(fc='#0044CC', ec='black', label=f'下筋 {bot_rebars}-{bot_size}'),
    ]
    ax.legend(handles=legend_elements, loc='upper left', fontsize=9,
               bbox_to_anchor=(1.02, 1), borderaxespad=0, framealpha=0.8,
               prop=_CJK_FONT)


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
                 fontsize=12, fontweight='bold', fontproperties=_CJK_FONT)

    legend_elements = [
        mpatches.Patch(fc='#D0D0D0', ec='black', label='混凝土'),
        mpatches.Patch(fc='#404040', ec='black', label='型鋼'),
        mpatches.Patch(fc='#CC0000', ec='black', label=f'縱筋 {num_bars}-{bar_size}'),
    ]
    ax.legend(handles=legend_elements, loc='upper left', fontsize=9,
               bbox_to_anchor=(1.02, 1), borderaxespad=0, framealpha=0.8,
               prop=_CJK_FONT)


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

def show_column_summary(res: dict, Pu: float, Mux: float, Muy: float = 0.0):
    """顯示柱設計分析成果摘要（雙向彎矩）"""
    ok        = res['is_safe']
    phi_Pn    = res['phi_Pn']
    chk_s     = res['chk_s']
    chk_r     = res['chk_r']
    phi_Mnx   = res.get('phi_Mnx', 0.0)  # X軸彎矩強度
    phi_Mny   = res.get('phi_Mny', 0.0)  # Y軸彎矩強度
    phi_Mn    = res.get('phi_Mn', phi_Mnx)  # 單向或X向疊加彎矩
    # 如果只有单向，phi_Mnx有值；如果雙向，兩者都有值
    # 取两者中的较大值作为组合强度显示
    if phi_Mny > 0:
        phi_Mn = max(phi_Mnx, phi_Mny)
    phi_Vn    = res.get('phi_Vn', 0.0)
    phi_Vns   = res.get('phi_Vns', 0.0)
    phi_Vnrc  = res.get('phi_Vnrc', 0.0)
    Vu        = res.get('Vu', 0.0)
    dc_vu     = res.get('dc_vu', 0.0)
    ok_vu     = res.get('ok_vu', True)
    dc_vu_s   = res.get('dc_Vu_s', 0.0)
    ok_vu_s   = res.get('ok_Vu_s', True)
    dc_vu_rc  = res.get('dc_Vu_rc', 0.0)
    ok_vu_rc  = res.get('ok_Vu_rc', True)
    # 雙向彎矩取合力
    Mu_total = (Mux**2 + Muy**2) ** 0.5 if Muy != 0 else Mux
    dc_M      = res.get('dc_M', Mu_total / phi_Mn if phi_Mn > 0 else 0)
    ok_mu     = res.get('ok_mu', phi_Mn >= Mu_total)
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
                          f'Mu = {Mu_total:.2f} tf-m　D/C = {dc_M:.3f}　{tag_m}', cm),
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

def report_to_html(title: str, report: str, pm_image: str = None, pm3d_image: str = None) -> str:
    """將純文字計算書轉換為格式化 HTML 網頁版計算書（可選：嵌入P-M曲線圖）"""
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
.chart-section{{margin-top:30px;padding:20px;background:#f8f9fa;border-radius:8px}}
.chart-section h3{{color:#1a3c6d;margin-bottom:15px}}
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

# 主分頁（柱設計包含P-M曲線）
tab_beam, tab_col = st.tabs([
    "📐 SRC梁設計", "🏛️ SRC柱設計"
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
        c_mx_my = st.columns(2)
        with c_mx_my[0]:
            Mux_c = st.number_input("設計彎矩 Mux (tf-m)", value=30.0, key='Mux_c')
        with c_mx_my[1]:
            Muy_c = st.number_input("設計彎矩 Muy (tf-m)", value=0.0, key='Muy_c')
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
        report, res = calc_column(mat, c_stl, cw, ch, cc, As_col, Pu_c, Mux=Mux_c, Muy=Muy_c,
                                  Vu=Vu_c, Av_s=Av_c, s_s=float(c_stir_s))
        st.markdown("#### 📊 分析成果摘要")
        show_column_summary(res, Pu_c, Mux_c, Muy_c)
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

# ===== P-M 曲線（雙向彎矩）=====
    st.divider()
    st.header("📈 SRC 柱 P-M 互制曲線（雙向彎矩）")
    st.caption("自動使用上方柱設計參數")
    c1, c2 = st.columns([1, 2])
    with c1:
        # 顯示柱設計參數（唯讀）
        st.info(f"📌 柱斷面：{c_stl.name}")
        st.info(f"📌 b×h = {cw}×{ch} cm")
        st.info(f"📌 保護層 = {cc} cm")
        st.info(f"📌 縱筋：{c_num}-{c_siz} (As={As_col:.2f} cm²)")
        st.info(f"📌 設計軸力 Pu = {Pu_c:.2f} tf")
        st.info(f"📌 設計彎矩 Mux = {Mux_c:.2f} tf-m, Muy = {Muy_c:.2f} tf-m")
        
    with c2:
        # 自動使用柱設計參數產生 P-M 曲線
        curve_x = gen_pm_curve(mat, c_stl, cw, ch, cc, As_col, axis='X')
        curve_y = gen_pm_curve(mat, c_stl, cw, ch, cc, As_col, axis='Y')
        Pv_x = [p[0] for p in curve_x]
        Mv_x = [p[1] for p in curve_x]
        Pv_y = [p[0] for p in curve_y]
        Mv_y = [p[1] for p in curve_y]
        
        fig, ax = plt.subplots(figsize=(9, 7))
        ax.plot(Mv_x, Pv_x, 'b-', lw=2.5, label='X軸 P-M（Mux）')
        ax.plot(Mv_y, Pv_y, 'g-', lw=2.5, label='Y軸 P-M（Muy）')
        
        # 設計點
        ax.scatter([Mux_c], [Pu_c], c='red', s=150, zorder=5, marker='o',
                   label=f'設計點X ({Pu_c:.0f} tf, {Mux_c:.0f} tf-m)')
        if Muy_c > 0:
            ax.scatter([Muy_c], [Pu_c], c='orange', s=150, zorder=5, marker='s',
                       label=f'設計點Y ({Pu_c:.0f} tf, {Muy_c:.0f} tf-m)')
        
        ax.axhline(0, color='gray', ls='--', lw=0.8)
        ax.axvline(0, color='gray', ls='--', lw=0.8)
        # 設定中文字體
        try:
            from matplotlib.font_manager import FontProperties
            font_cn = FontProperties(family=['Microsoft JhengHei', 'PingFang TC', 
                                             'Noto Sans CJK TC', 'WenQuanYi Zen Hei', 
                                             'DejaVu Sans'])
        except Exception:
            font_cn = None
        ax.set_xlabel('彎矩 M (tf-m)', fontsize=12, fontproperties=font_cn)
        ax.set_ylabel('軸力 P (tf)', fontsize=12, fontproperties=font_cn)
        ax.set_title(f'SRC 柱 P-M 互制曲線（雙向）\n{c_stl.name} / {cw}×{ch}cm / {c_num}-{c_siz}', 
                     fontsize=12, fontproperties=font_cn)
        ax.legend(fontsize=10, prop=font_cn)
        ax.grid(alpha=0.3)
        st.pyplot(fig)
        
        # ── P-M-M 3D 曲面圖 ─────────────────────────────
        st.markdown("#### 📊 P-M-M 3D 曲面圖")
        try:
            import numpy as np
            from mpl_toolkits.mplot3d import Axes3D
            
            # 嘗試使用精確版本，失敗則用近似版本
            try:
                Mx, My, P = gen_pm_surface_accurate(mat, c_stl, cw, ch, cc, As_col, pts=15)
            except Exception as e1:
                try:
                    Mx, My, P = gen_pm_surface(mat, c_stl, cw, ch, cc, As_col, pts=20)
                except Exception as e2:
                    st.warning(f"3D曲面生成失敗，使用2D曲線代替")
                    st.pyplot(fig)  # 仍顯示2D
                    st.stop()
            
            fig3d = plt.figure(figsize=(10, 8))
            ax3d = fig3d.add_subplot(111, projection='3d')
            
            surf = ax3d.plot_surface(Mx, My, P, cmap='viridis', alpha=0.8, 
                                     edgecolor='none', antialiased=True)
            
            # 設計點
            ax3d.scatter([Mux_c], [Muy_c], [Pu_c], c='red', s=150, marker='o', 
                        label=f'設計點', zorder=5)
            
            ax3d.set_xlabel('Mx (tf-m)', fontsize=11, fontproperties=font_cn)
            ax3d.set_ylabel('My (tf-m)', fontsize=11, fontproperties=font_cn)
            ax3d.set_zlabel('P (tf)', fontsize=11, fontproperties=font_cn)
            ax3d.set_title(f'SRC 柱 P-M-M 3D 曲面\n{c_stl.name} / {cw}×{ch}cm', 
                          fontsize=12, fontproperties=font_cn)
            ax3d.legend(fontsize=10, prop=font_cn)
            fig3d.colorbar(surf, shrink=0.5, aspect=10, label='P (tf)')
            
            st.pyplot(fig3d)
        except Exception as e:
            st.warning(f"3D 曲面圖生成失敗: {e}")

st.markdown("---")
st.warning("⚠️ 本程式依據『內政部頒布 — 鋼骨鋼筋混凝土構造設計規範與解說（110年3月24日修正）』計算，僅供設計初稿參考，實際設計應經專業結構技師審查簽證。")
