#!/usr/bin/env python3
"""
SRC 鋼骨鋼筋混凝土結構設計程式 (GUI版)
Steel Reinforced Concrete Design Program

設計依據：
- 鋼骨鋼筋混凝土構造設計規範與解說
- 建築物混凝土結構設計規範 (112年版)

⚠️ 重要提醒：本程式僅供設計初稿參考，實際設計應經專業結構技師確認。
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import math
from dataclasses import dataclass
from typing import Optional, Dict
import sys

# ============================================================================
# 材料性質與鋼骨資料庫 (與主程式共用)
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
# SRC 梁設計類別
# ============================================================================

class SRCBeamDesigner:
    """SRC 梁設計 (強度疊加法)"""
    
    def __init__(self, material: MaterialProperties = DEFAULT_MATERIAL):
        self.mat = material
        
    def calculate(self, section_name: str, width: float, height: float, 
                  cover: float, As_rebar: float) -> Dict:
        steel = STEEL_SECTIONS[section_name]
        
        # 鋼骨部分
        Z_s = steel['Zx']
        Mns = Z_s * self.mat.fy_steel / 1e6  # tf-m
        phi_Mns = 0.9 * Mns
        
        # RC 部分
        d_rc = height * 10 - cover * 10
        a = As_rebar * self.mat.fy_rebar / (0.85 * self.mat.fc * width * 10)
        Mnrc = As_rebar * self.mat.fy_rebar * (d_rc - a*10/2) / 1e6
        phi_Mnrc = 0.9 * Mnrc
        
        # 總計
        phi_Mn_total = phi_Mns + phi_Mnrc
        
        return {
            'Mns': Mns,
            'phi_Mns': phi_Mns,
            'Mnrc': Mnrc,
            'phi_Mnrc': phi_Mnrc,
            'phi_Mn_total': phi_Mn_total,
            'd_rc': d_rc / 10,
            'rho': As_rebar / (width * d_rc/10)
        }


# ============================================================================
# SRC 柱設計類別
# ============================================================================

class SRCColumnDesigner:
    """SRC 柱設計 (相對剛度法)"""
    
    def __init__(self, material: MaterialProperties = DEFAULT_MATERIAL):
        self.mat = material
        
    def calculate_axial(self, section_name: str, width: float, depth: float,
                        cover: float, As_rebar: float) -> Dict:
        steel = STEEL_SECTIONS[section_name]
        
        # 計算混凝土淨面積
        bf = steel['bf']
        d = steel['d']
        tf = steel['tf']
        tw = steel['tw']
        
        Ac_inner = (bf - 2*tw) * (d - 2*tf) / 100  # cm²
        Ac_total = width * depth - steel['A'] - Ac_inner
        
        # RC 部分軸力
        Pn_rc = (0.85 * self.mat.fc * Ac_total + 
                  self.mat.fy_rebar * As_rebar) / 1000  # tf
        
        # 鋼骨部分軸力
        Pn_s = self.mat.fy_steel * steel['A'] / 1000  # tf
        
        # 總軸力
        Pn_total = Pn_rc + Pn_s
        phi_Pn = 0.75 * Pn_rc + 0.9 * Pn_s
        
        return {
            'Ac': Ac_total,
            'Pn_rc': Pn_rc,
            'Pn_s': Pn_s,
            'Pn_total': Pn_total,
            'phi_Pn': phi_Pn
        }
    
    def calculate_PM(self, section_name: str, width: float, depth: float,
                      cover: float, As_rebar: float, Pu: float, Mu: float) -> Dict:
        steel = STEEL_SECTIONS[section_name]
        
        # 計算剛度比
        EsIs = self.mat.Es * steel['Ix']
        I_rc = width * (depth*10)**3 / 12 / 1e4
        EcIc = self.mat.Ec * I_rc
        
        ratio_s = EsIs / (EsIs + EcIc)
        ratio_rc = EcIc / (EsIs + EcIc)
        
        # 分配軸力與彎矩
        Pus = ratio_s * Pu
        Purc = ratio_rc * Pu
        Mus = ratio_s * Mu
        Murc = ratio_rc * Mu
        
        # 鋼骨檢核
        Pns = self.mat.fy_steel * steel['A'] / 1000  # tf
        Mns = self.mat.fy_steel * steel['Zx'] / 1e6  # tf-m
        
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
            'ratio_s': ratio_s,
            'ratio_rc': ratio_rc,
            'Pus': Pus, 'Purc': Purc,
            'Mus': Mus, 'Murc': Murc,
            'check_s': check_s,
            'steel_safe': steel_safe,
            'check_rc': check_rc,
            'rc_safe': rc_safe,
            'is_safe': steel_safe and rc_safe
        }


# ============================================================================
# GUI 應用程式
# ============================================================================

class SRCDesignApp:
    def __init__(self, root):
        self.root = root
        self.root.title("SRC 鋼骨鋼筋混凝土結構設計程式")
        self.root.geometry("700x750")
        
        # 設計工具
        self.beam_designer = SRCBeamDesigner(DEFAULT_MATERIAL)
        self.column_designer = SRCColumnDesigner(DEFAULT_MATERIAL)
        
        self.setup_ui()
        
    def setup_ui(self):
        # 建立標籤頁
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill='both', expand=True, padx=10, pady=10)
        
        # 梁設計頁面
        self.beam_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.beam_frame, text="SRC 梁設計")
        self.setup_beam_ui()
        
        # 柱設計頁面
        self.column_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.column_frame, text="SRC 柱設計")
        self.setup_column_ui()
        
        # 說明頁面
        self.info_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.info_frame, text="設計說明")
        self.setup_info_ui()
        
    def setup_beam_ui(self):
        # 標題
        ttk.Label(self.beam_frame, text="SRC 梁設計 (強度疊加法)", 
                  font=('Arial', 14, 'bold')).pack(pady=10)
        
        # 輸入框架
        input_frame = ttk.LabelFrame(self.beam_frame, text="設計條件", padding=10)
        input_frame.pack(fill='x', padx=10, pady=5)
        
        # 鋼骨斷面
        ttk.Label(input_frame, text="鋼骨斷面:").grid(row=0, column=0, sticky='w', pady=5)
        self.beam_steel = ttk.Combobox(input_frame, width=20, 
                                         values=list(STEEL_SECTIONS.keys()))
        self.beam_steel.current(2)  # H400x200x8x13
        self.beam_steel.grid(row=0, column=1, padx=5, pady=5)
        
        # 混凝土寬度
        ttk.Label(input_frame, text="混凝土寬度 (cm):").grid(row=1, column=0, sticky='w', pady=5)
        self.beam_width = ttk.Entry(input_frame, width=22)
        self.beam_width.insert(0, "40")
        self.beam_width.grid(row=1, column=1, padx=5, pady=5)
        
        # 混凝土高度
        ttk.Label(input_frame, text="混凝土高度 (cm):").grid(row=2, column=0, sticky='w', pady=5)
        self.beam_height = ttk.Entry(input_frame, width=22)
        self.beam_height.insert(0, "80")
        self.beam_height.grid(row=2, column=1, padx=5, pady=5)
        
        # 保護層
        ttk.Label(input_frame, text="保護層厚度 (cm):").grid(row=3, column=0, sticky='w', pady=5)
        self.beam_cover = ttk.Entry(input_frame, width=22)
        self.beam_cover.insert(0, "5")
        self.beam_cover.grid(row=3, column=1, padx=5, pady=5)
        
        # 鋼筋
        ttk.Label(input_frame, text="鋼筋 (數量-規格):").grid(row=4, column=0, sticky='w', pady=5)
        rebar_frame = ttk.Frame(input_frame)
        rebar_frame.grid(row=4, column=1, padx=5, pady=5, sticky='w')
        
        self.beam_rebar_num = ttk.Spinbox(rebar_frame, from_=2, to=20, width=5)
        self.beam_rebar_num.set(4)
        self.beam_rebar_num.pack(side='left')
        
        ttk.Label(rebar_frame, text="-").pack(side='left')
        
        self.beam_rebar_size = ttk.Combobox(rebar_frame, width=8, values=list(REBAR_SIZES.keys()))
        self.beam_rebar_size.current(2)  # D16
        self.beam_rebar_size.pack(side='left')
        
        # 設計彎矩輸入
        ttk.Label(input_frame, text="設計彎矩 (tf-m):").grid(row=5, column=0, sticky='w', pady=5)
        self.beam_Mu = ttk.Entry(input_frame, width=22)
        self.beam_Mu.insert(0, "15")
        self.beam_Mu.grid(row=5, column=1, padx=5, pady=5)
        
        # 設計剪力輸入
        ttk.Label(input_frame, text="設計剪力 (tf):").grid(row=6, column=0, sticky='w', pady=5)
        self.beam_Vu = ttk.Entry(input_frame, width=22)
        self.beam_Vu.insert(0, "15")
        self.beam_Vu.grid(row=6, column=1, padx=5, pady=5)
        
        # 計算按鈕
        ttk.Button(input_frame, text="計算設計", command=self.calculate_beam).grid(
            row=7, column=0, columnspan=2, pady=15)
        
        # 結果顯示
        result_frame = ttk.LabelFrame(self.beam_frame, text="計算結果", padding=10)
        result_frame.pack(fill='both', expand=True, padx=10, pady=5)
        
        self.beam_result = scrolledtext.ScrolledText(result_frame, height=12, font=('Consolas', 10))
        self.beam_result.pack(fill='both', expand=True)
        
    def setup_column_ui(self):
        # 標題
        ttk.Label(self.column_frame, text="SRC 柱設計 (相對剛度法)", 
                  font=('Arial', 14, 'bold')).pack(pady=10)
        
        # 輸入框架
        input_frame = ttk.LabelFrame(self.column_frame, text="設計條件", padding=10)
        input_frame.pack(fill='x', padx=10, pady=5)
        
        # 鋼骨斷面
        ttk.Label(input_frame, text="鋼骨斷面:").grid(row=0, column=0, sticky='w', pady=5)
        self.col_steel = ttk.Combobox(input_frame, width=20, 
                                       values=list(STEEL_SECTIONS.keys()))
        self.col_steel.current(8)  # BOX300x300x10x10
        self.col_steel.grid(row=0, column=1, padx=5, pady=5)
        
        # 混凝土寬度
        ttk.Label(input_frame, text="混凝土寬度 (cm):").grid(row=1, column=0, sticky='w', pady=5)
        self.col_width = ttk.Entry(input_frame, width=22)
        self.col_width.insert(0, "50")
        self.col_width.grid(row=1, column=1, padx=5, pady=5)
        
        # 混凝土深度
        ttk.Label(input_frame, text="混凝土深度 (cm):").grid(row=2, column=0, sticky='w', pady=5)
        self.col_depth = ttk.Entry(input_frame, width=22)
        self.col_depth.insert(0, "50")
        self.col_depth.grid(row=2, column=1, padx=5, pady=5)
        
        # 保護層
        ttk.Label(input_frame, text="保護層厚度 (cm):").grid(row=3, column=0, sticky='w', pady=5)
        self.col_cover = ttk.Entry(input_frame, width=22)
        self.col_cover.insert(0, "4")
        self.col_cover.grid(row=3, column=1, padx=5, pady=5)
        
        # 鋼筋
        ttk.Label(input_frame, text="鋼筋 (數量-規格):").grid(row=4, column=0, sticky='w', pady=5)
        rebar_frame = ttk.Frame(input_frame)
        rebar_frame.grid(row=4, column=1, padx=5, pady=5, sticky='w')
        
        self.col_rebar_num = ttk.Spinbox(rebar_frame, from_=4, to=20, width=5)
        self.col_rebar_num.set(8)
        self.col_rebar_num.pack(side='left')
        
        ttk.Label(rebar_frame, text="-").pack(side='left')
        
        self.col_rebar_size = ttk.Combobox(rebar_frame, width=8, values=list(REBAR_SIZES.keys()))
        self.col_rebar_size.current(2)  # D16
        self.col_rebar_size.pack(side='left')
        
        # 設計軸力
        ttk.Label(input_frame, text="設計軸力 (tf):").grid(row=5, column=0, sticky='w', pady=5)
        self.col_Pu = ttk.Entry(input_frame, width=22)
        self.col_Pu.insert(0, "100")
        self.col_Pu.grid(row=5, column=1, padx=5, pady=5)
        
        # 設計彎矩
        ttk.Label(input_frame, text="設計彎矩 (tf-m):").grid(row=6, column=0, sticky='w', pady=5)
        self.col_Mu = ttk.Entry(input_frame, width=22)
        self.col_Mu.insert(0, "20")
        self.col_Mu.grid(row=6, column=1, padx=5, pady=5)
        
        # 按鈕
        btn_frame = ttk.Frame(input_frame)
        btn_frame.grid(row=7, column=0, columnspan=2, pady=15)
        
        ttk.Button(btn_frame, text="計算軸力強度", command=self.calculate_col_axial).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="計算P-M檢核", command=self.calculate_col_pm).pack(side='left', padx=5)
        
        # 結果顯示
        result_frame = ttk.LabelFrame(self.column_frame, text="計算結果", padding=10)
        result_frame.pack(fill='both', expand=True, padx=10, pady=5)
        
        self.col_result = scrolledtext.ScrolledText(result_frame, height=12, font=('Consolas', 10))
        self.col_result.pack(fill='both', expand=True)
        
    def setup_info_ui(self):
        info_text = """
╔══════════════════════════════════════════════════════════════════╗
║                    SRC 結構設計程式說明                            ║
╠══════════════════════════════════════════════════════════════════╣
║ 設計依據：                                                          ║
║   • 鋼骨鋼筋混凝土構造設計規範與解說                               ║
║   • 建築物混凝土結構設計規範 (112年版)                            ║
║   • 鋼結構極限設計法規範及解說                                     ║
╠══════════════════════════════════════════════════════════════════╣
║ 設計方法：                                                          ║
║                                                                  ║
║ 【梁】強度疊加法                                                   ║
║   φbMn = φbsMns + φbrcMnrc                                      ║
║                                                                  ║
║   • Mns = Z × Fys (鋼骨塑性彎矩)                                 ║
║   • Mnrc = As × fy × (d - a/2) (RC彎矩)                         ║
║   • φbs = 0.9, φbrc = 0.9                                       ║
║                                                                  ║
║ 【柱】相對剛度法                                                   ║
║   1. 依剛度比例分配 Pu 與 Mu                                      ║
║   2. 分別檢核鋼骨與 RC 部分                                        ║
║   3. 使用 P-M 互制公式                                            ║
║                                                                  ║
╠══════════════════════════════════════════════════════════════════╣
║ 預設材料：                                                          ║
║   • 鋼骨：SN280 (Fys = 2800 kgf/cm²)                             ║
║   • 鋼筋：SD420 (Fy = 4200 kgf/cm²)                              ║
║   • 混凝土：f'c = 280 kgf/cm²                                    ║
╠══════════════════════════════════════════════════════════════════╣
║ ⚠️  重要提醒：                                                     ║
║   本程式僅供設計初稿參考，實際設計應經                             ║
║   專業結構技師確認並符合最新法規規定。                             ║
╚══════════════════════════════════════════════════════════════════╝
"""
        info_widget = scrolledtext.ScrolledText(self.info_frame, font=('Consolas', 11))
        info_widget.pack(fill='both', expand=True, padx=10, pady=10)
        info_widget.insert('1.0', info_text)
        info_widget.config(state='disabled')
        
    def calculate_beam(self):
        try:
            # 取得輸入值
            section = self.beam_steel.get()
            b = float(self.beam_width.get())
            h = float(self.beam_height.get())
            cover = float(self.beam_cover.get())
            num = int(self.beam_rebar_num.get())
            size = self.beam_rebar_size.get()
            As = num * REBAR_SIZES[size]
            Mu = float(self.beam_Mu.get())
            Vu = float(self.beam_Vu.get())
            
            # 計算
            result = self.beam_designer.calculate(section, b, h, cover, As)
            
            # 顯示結果
            output = f"""
{'='*50}
SRC 梁設計結果 - 強度疊加法
{'='*50}

【設計條件】
  鋼骨斷面：{section}
  混凝土：{b} × {h} cm，保護層 {cover} cm
  鋼筋：{num}-{size}，As = {As:.2f} cm²
  材料：fys=2800, fy=4200, fc=280

【彎矩強度計算】
  鋼骨部分 Mns = {result['Mns']:.2f} tf-m
  設計強度 φMns = {result['phi_Mns']:.2f} tf-m

  RC部分 Mnrc = {result['Mnrc']:.2f} tf-m  
  設計強度 φMnrc = {result['phi_Mnrc']:.2f} tf-m

  ────────────────
  總設計彎矩 φMn = {result['phi_Mn_total']:.2f} tf-m
  需要彎矩 Mu = {Mu:.1f} tf-m
  ────────────────

【檢核結果】
  彎矩：{'✓ 安全' if result['phi_Mn_total'] >= Mu else '✗ 不安全'}
  
  (剪力檢核需依實際配置進行)
"""
            self.beam_result.delete('1.0', 'end')
            self.beam_result.insert('1.0', output)
            
        except Exception as e:
            messagebox.showerror("錯誤", f"計算發生錯誤：{str(e)}")
            
    def calculate_col_axial(self):
        try:
            section = self.col_steel.get()
            b = float(self.col_width.get())
            h = float(self.col_depth.get())
            cover = float(self.col_cover.get())
            num = int(self.col_rebar_num.get())
            size = self.col_rebar_size.get()
            As = num * REBAR_SIZES[size]
            
            result = self.column_designer.calculate_axial(section, b, h, cover, As)
            
            output = f"""
{'='*50}
SRC 柱軸力強度計算結果
{'='*50}

【設計條件】
  鋼骨斷面：{section}
  混凝土：{b} × {h} cm，保護層 {cover} cm
  鋼筋：{num}-{size}，As = {As:.2f} cm²
  材料：fys=2800, fy=4200, fc=280

【斷面面積】
  混凝土淨面積：{result['Ac']:.1f} cm²

【軸力強度】
  RC部分 Pn = {result['Pn_rc']:.1f} tf
  鋼骨部分 Pns = {result['Pn_s']:.1f} tf
  ────────────────
  總強度 Pn = {result['Pn_total']:.1f} tf
  設計強度 φPn = {result['phi_Pn']:.1f} tf
  ────────────────
"""
            self.col_result.delete('1.0', 'end')
            self.col_result.insert('1.0', output)
            
        except Exception as e:
            messagebox.showerror("錯誤", f"計算發生錯誤：{str(e)}")
            
    def calculate_col_pm(self):
        try:
            section = self.col_steel.get()
            b = float(self.col_width.get())
            h = float(self.col_depth.get())
            cover = float(self.col_cover.get())
            num = int(self.col_rebar_num.get())
            size = self.col_rebar_size.get()
            As = num * REBAR_SIZES[size]
            Pu = float(self.col_Pu.get())
            Mu = float(self.col_Mu.get())
            
            result = self.column_designer.calculate_PM(section, b, h, cover, As, Pu, Mu)
            
            output = f"""
{'='*50}
SRC 柱 P-M 檢核結果
{'='*50}

【設計條件】
  鋼骨斷面：{section}
  混凝土：{b} × {h} cm
  鋼筋：{num}-{size}，As = {As:.2f} cm²
  設計軸力 Pu = {Pu} tf
  設計彎矩 Mu = {Mu} tf-m

【剛度分配】
  鋼骨分配比例：{result['ratio_s']:.1%}
  RC分配比例：{result['ratio_rc']:.1%}

【力分配】
  鋼骨部分：Pus = {result['Pus']:.1f} tf, Mus = {result['Mus']:.1f} tf-m
  RC部分：Purc = {result['Purc']:.1f} tf, Murc = {result['Murc']:.1f} tf-m

【檢核結果】
  鋼骨檢核值：{result['check_s']:.3f} → {'✓ 安全' if result['steel_safe'] else '✗ 不安全'}
  RC檢核值：{result['check_rc']:.3f} → {'✓ 安全' if result['rc_safe'] else '✗ 不安全'}
  
  ──────────────────
  結論：{'✓ 設計安全' if result['is_safe'] else '✗ 設計不安全'}
  ──────────────────
"""
            self.col_result.delete('1.0', 'end')
            self.col_result.insert('1.0', output)
            
        except Exception as e:
            messagebox.showerror("錯誤", f"計算發生錯誤：{str(e)}")


# ============================================================================
# 主程式
# ============================================================================

if __name__ == "__main__":
    root = tk.Tk()
    app = SRCDesignApp(root)
    
    # 設定樣式
    style = ttk.Style()
    style.theme_use('clam')
    
    root.mainloop()
