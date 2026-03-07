#!/usr/bin/env python3
"""
SRC 鋼骨鋼筋混凝土結構設計程式
Steel Reinforced Concrete Design Program

設計依據：
- 鋼骨鋼筋混凝土構造設計規範與解說
- 建築物混凝土結構設計規範 (112年版)
- 鋼結構極限設計法規範及解說

⚠️ 重要提醒：
本程式僅供設計初稿參考，實際設計應經專業結構技師確認符合最新法規規定。
"""

import math
from dataclasses import dataclass
from typing import Optional, Tuple

# ============================================================================
# 材料性質
# ============================================================================

@dataclass
class MaterialProperties:
    """材料性質"""
    fy_steel: float  # 鋼骨降伏應力 (kgf/cm²)
    fy_rebar: float  # 鋼筋降伏應力 (kgf/cm²)
    fc: float       # 混凝土設計抗壓強度 (kgf/cm²)
    Es: float       # 鋼材彈性模數 (kgf/cm²)
    Ec: float       # 混凝土彈性模數 (kgf/cm²)
    
    @classmethod
    def create(cls, fy_steel=2800, fy_rebar=4200, fc=280):
        """建立材料性質"""
        # 鋼材彈性模數
        Es = 2.04e6  # kgf/cm²
        
        # 混凝土彈性模數 (ACI 318)
        Ec = 4700 * math.sqrt(fc) * 10  # kgf/cm² (f'c in kgf/cm²)
        
        return cls(
            fy_steel=fy_steel,
            fy_rebar=fy_rebar,
            fc=fc,
            Es=Es,
            Ec=Ec
        )

# 預設材料 (SD280 鋼骨 + SD420 鋼筋 + f'c=280 kgf/cm²)
DEFAULT_MATERIAL = MaterialProperties.create(fy_steel=2800, fy_rebar=4200, fc=280)


# ============================================================================
# 鋼骨斷面資料庫
# ============================================================================

STEEL_SECTIONS = {
    # H型鋼 (mm) - 資料來源: CNS 標準
    'H300x150x6.5x9': {'bf': 150, 'tw': 6.5, 'tf': 9, 'd': 300, 'Ix': 3770, 'Zx': 251, 'Sx': 171, 'A': 46.78},
    'H350x175x7x11': {'bf': 175, 'tw': 7, 'tf': 11, 'd': 350, 'Ix': 7890, 'Zx': 450, 'Sx': 395, 'A': 62.91},
    'H400x200x8x13': {'bf': 200, 'tw': 8, 'tf': 13, 'd': 400, 'Ix': 13400, 'Zx': 670, 'Sx': 557, 'A': 84.12},
    'H450x200x9x14': {'bf': 200, 'tw': 9, 'tf': 14, 'd': 450, 'Ix': 18700, 'Zx': 831, 'Sx': 753, 'A': 96.76},
    'H500x200x10x16': {'bf': 200, 'tw': 10, 'tf': 16, 'd': 500, 'Ix': 25500, 'Zx': 1120, 'Sx': 962, 'A': 114.2},
    'H600x200x11x17': {'bf': 200, 'tw': 11, 'tf': 17, 'd': 600, 'Ix': 36200, 'Zx': 1490, 'Sx': 1290, 'A': 134.4},
    
    # 箱型鋼 (mm) - 計算值
    # 計算公式說明：
    # Zx (塑性斷面模數) = B×tf×(H-tf) + (H-2×tf)×tw×(H/2)  (mm³)
    # 參考：鋼骨鋼筋混凝土構造設計規範與解說
    'BOX200x200x9x9': {
        'bf': 200, 'tw': 9, 'tf': 9, 'd': 200, 
        'Ix': 2620, 'Zx': 508, 'Sx': 183, 'A': 57.36
    },
    'BOX250x250x9x9': {
        'bf': 250, 'tw': 9, 'tf': 9, 'd': 250, 
        'Ix': 5200, 'Zx': 803, 'Sx': 312, 'A': 71.36
    },
    'BOX300x300x10x10': {
        'bf': 300, 'tw': 10, 'tf': 10, 'd': 300, 
        'Ix': 8950, 'Zx': 1290, 'Sx': 597, 'A': 95.36
    },
    'BOX350x350x12x12': {
        'bf': 350, 'tw': 12, 'tf': 12, 'd': 350, 
        'Ix': 14300, 'Zx': 2104, 'Sx': 817, 'A': 129.36
    },
    'BOX400x400x14x14': {
        'bf': 400, 'tw': 14, 'tf': 14, 'd': 400, 
        'Ix': 21400, 'Zx': 3203, 'Sx': 802, 'A': 169.36
    },
    # 大型箱型柱
    'BOX500x500x16x16': {
        'bf': 500, 'tw': 16, 'tf': 16, 'd': 500, 
        'Ix': 43800, 'Zx': 5744, 'Sx': 1752, 'A': 249.0
    },
}


def get_steel_section(section_name: str) -> dict:
    """取得鋼骨斷面資料"""
    if section_name not in STEEL_SECTIONS:
        raise ValueError(f"找不到鋼骨斷面: {section_name}")
    return STEEL_SECTIONS[section_name]


# ============================================================================
# SRC 梁設計 (強度疊加法)
# ============================================================================

class SRCSection:
    """SRC 構材基礎類別"""
    
    def __init__(self, material: MaterialProperties = DEFAULT_MATERIAL):
        self.mat = material
        
    def calculate_modular_ratio(self) -> float:
        """計算彈性模數比 n = Es/Ec"""
        return self.mat.Es / self.mat.Ec


class SRCBeam(SRCSection):
    """
    SRC 梁設計 (強度疊加法)
    
    設計彎矩強度：φbMn = φbsMns + φbrcMnrc
    
    參考：
    - 鋼骨鋼筋混凝土構造設計規範與解說 第五章
    """
    
    def __init__(
        self,
        section_name: str,
        width: float,      # 混凝土寬度 (cm)
        height: float,     # 混凝土高度 (cm)
        cover: float,      # 混凝土保護層厚度 (cm)
        As_rebar: float,  # 鋼筋面積 (cm²)
        material: MaterialProperties = DEFAULT_MATERIAL
    ):
        super().__init__(material)
        
        # 鋼骨資料
        self.steel = get_steel_section(section_name)
        
        # 斷面幾何
        self.b = width          # 混凝土寬度 (cm)
        self.h = height         # 混凝土高度 (cm)
        self.cover = cover       # 保護層 (cm)
        
        # 鋼筋
        self.As = As_rebar       # 鋼筋面積 (cm²)
        
        # 計算鋼骨有效深度
        self.d_s = height * 10 - cover * 10 - self.steel['tf']  # mm
        self.d_s_cm = self.d_s / 10  # cm
        
        # 計算 RC 有效深度
        self.d_rc = height * 10 - cover * 10  # mm
        self.d_rc_cm = self.d_rc / 10  # cm
        
    def design_moment_strength(self, debug: bool = False) -> dict:
        """
        計算設計彎矩強度
        強度疊加法：Mn = Mns + Mnrc
        """
        mat = self.mat
        
        # ===== 鋼骨部分 =====
        # 塑性彎矩強度 Mns = Z × Fys
        Z_s = self.steel['Zx']  # cm³ (塑性斷面模數)
        Mns = Z_s * mat.fy_steel  # kgf-cm
        
        # 設計彎矩強度
        phi_bs = 0.9
        phi_Mns = phi_bs * Mns
        
        if debug:
            print(f"=== 鋼骨部分 ===")
            print(f"  鋼骨斷面: {list(STEEL_SECTIONS.keys())[list(STEEL_SECTIONS.values()).index(self.steel)]}")
            print(f"  塑性斷面模數 Zx = {Z_s} cm³")
            print(f"  鋼骨降伏應力 fys = {mat.fy_steel} kgf/cm²")
            print(f"  標稱彎矩強度 Mns = {Z_s} × {mat.fy_steel} = {Mns:.0f} kgf-cm = {Mns/1e6:.2f} tf-m")
            print(f"  設計彎矩強度 φMns = 0.9 × {Mns/1e6:.2f} = {phi_Mns/1e6:.2f} tf-m")
        
        # ===== RC 部分 =====
        # 簡化計算：假設單筋矩形梁
        b = self.b  # cm
        d = self.d_rc_cm  # cm
        As = self.As  # cm²
        fc = mat.fc  # kgf/cm²
        fy = mat.fy_rebar  # kgf/cm²
        
        # 計算 a 值
        As_fy = As * fy
        a = As_fy / (0.85 * fc * b)
        
        # 檢核鋼筋比
        rho = As / (b * d)
        rho_max = 0.85 * fc / fy * 0.003  # 簡化
        rho_min = 1.4 / fy
        
        if rho < rho_min:
            print(f"  ⚠️ 鋼筋比 ρ = {rho:.4f} < ρmin = {rho_min:.4f} (不足)")
        
        # RC 標稱彎矩強度
        # Mnrc = As × fy × (d - a/2)
        Mnrc = As * fy * (d - a/2)  # kgf-cm
        
        # 設計彎矩強度
        phi_rc = 0.9
        phi_Mnrc = phi_rc * Mnrc
        
        if debug:
            print(f"\n=== RC 部分 ===")
            print(f"  混凝土寬度 b = {b} cm")
            print(f"  有效深度 d = {d:.1f} cm")
            print(f"  鋼筋面積 As = {As} cm²")
            print(f"  鋼筋比 ρ = {As/(b*d):.4f}")
            print(f"  a = {As*fy/(0.85*fc*b):.2f} cm")
            print(f"  標稱彎矩 Mnrc = {Mnrc/1e6:.2f} tf-m")
            print(f"  設計彎矩 φMnrc = {phi_Mnrc/1e6:.2f} tf-m")
        
        # ===== 疊加總和 =====
        phi_Mn_total = phi_Mns + phi_Mnrc
        
        if debug:
            print(f"\n=== 疊加結果 ===")
            print(f"  SRC 梁設計彎矩強度 = {phi_Mn_total/1e6:.2f} tf-m")
        
        return {
            'Mns': Mns / 1e6,           # tf-m
            'phi_Mns': phi_Mns / 1e6,   # tf-m
            'Mnrc': Mnrc / 1e6,         # tf-m
            'phi_Mnrc': phi_Mnrc / 1e6, # tf-m
            'phi_Mn_total': phi_Mn_total / 1e6,  # tf-m
            'rho': rho,
            'rho_min': rho_min,
            'a': a,
            'd_rc': d,
            'd_s': self.d_s_cm
        }
    
    def design_shear_strength(self, Vu: float, debug: bool = False) -> dict:
        """
        設計剪力強度
        
        參考：鋼骨鋼筋混凝土構造設計規範與解說 5.5節
        
        φvsVns ≥ (Mns/Mn) × Vu
        φvrcVnrc ≥ (Mnrc/Mn) × Vu
        """
        mat = self.mat
        
        # 先計算彎矩強度
        Mn_dict = self.design_moment_strength()
        Mns = Mn_dict['Mns'] * 1e6  # kgf-cm
        Mnrc = Mn_dict['Mnrc'] * 1e6  # kgf-cm
        Mn_total = Mn_dict['phi_Mn_total'] * 1e6  # kgf-cm
        
        # ===== 鋼骨部分剪力強度 =====
        # Vns = 0.6 × Fys × Aw
        tw = self.steel['tw'] / 10  # cm
        d = self.steel['d'] / 10    # cm
        Aw = tw * d  # 腹板面積 cm²
        
        Vns = 0.6 * mat.fy_steel * Aw  # kgf
        
        # 分配剪力
        Vns_ratio = Mns / (Mns + Mnrc)
        Vns_design = Vns_ratio * Vu * 1000  # kgf (Vu in tf)
        
        phi_vs = 0.9
        phi_Vns = phi_vs * Vns / 1000  # tf
        
        if debug:
            print(f"=== 鋼骨部分剪力 ===")
            print(f"  腹板厚度 tw = {tw:.1f} cm")
            print(f"  腹板高度 d = {d:.1f} cm")
            print(f"  腹板面積 Aw = {Aw:.1f} cm²")
            print(f"  名義剪力強度 Vns = {Vns/1000:.1f} tf")
            print(f"  剪力分配比例 = {Vns_ratio:.2%}")
            print(f"  需要剪力 Vu = {Vu} tf")
            print(f"  設計剪力 = {Vns_design/1000:.2f} tf")
        
        # ===== RC 部分剪力強度 =====
        # Vc = 0.17 × √f'c × b × d (ACI 318 簡化)
        b = self.b  # cm
        d = self.d_rc_cm  # cm
        
        Vc = 0.17 * math.sqrt(mat.fc) * b * d  # kgf
        
        # 分配剪力
        Vrc_ratio = Mnrc / (Mns + Mnrc)
        Vrc_design = Vrc_ratio * Vu * 1000  # kgf
        
        phi_vrc = 0.75
        phi_Vc = phi_vrc * Vc / 1000  # tf
        
        if debug:
            print(f"\n=== RC 部分剪力 ===")
            print(f"  Vc = 0.17√{mat.fc} × {b} × {d:.1f} = {Vc/1000:.1f} tf")
            print(f"  設計剪力強度 φVc = {phi_Vc:.2f} tf")
            print(f"  需要設計剪力 = {Vrc_design/1000:.2f} tf")
        
        # RC 部分檢核：Vu 與 φVn 比較
        # 總剪力強度
        phi_Vn_total = phi_Vns + phi_Vc
        Vu_total = Vu
        
        # 檢核
        is_safe = phi_Vn_total >= Vu_total
        
        return {
            'phi_Vns': phi_Vns,      # tf
            'Vns_design': Vns_design/1000,  # tf
            'phi_Vc': phi_Vc,        # tf
            'Vrc_design': Vrc_design/1000, # tf
            'phi_Vn_total': phi_Vn_total,  # tf
            'Vu': Vu,
            'is_safe': is_safe
        }


# ============================================================================
# SRC 柱設計 (相對剛度法)
# ============================================================================

class SRCColumn(SRCSection):
    """
    SRC 柱設計 (相對剛度法)
    
    設計步驟：
    1. 依相對剛度分配軸力與彎矩
    2. 分別檢核鋼骨與 RC 部分強度
    
    參考：
    - 鋼骨鋼筋混凝土構造設計規範與解說 第七章
    """
    
    def __init__(
        self,
        section_name: str,
        width: float,       # 混凝土寬度 (cm)
        depth: float,       # 混凝土深度 (cm)
        cover: float,       # 保護層厚度 (cm)
        As_rebar: float,    # 鋼筋面積 (cm²)
        length: float,      # 柱長度 (cm)
        K: float = 1.0,     # 有效長度因數
        material: MaterialProperties = DEFAULT_MATERIAL
    ):
        super().__init__(material)
        
        # 鋼骨資料
        self.steel = get_steel_section(section_name)
        
        # 斷面幾何
        self.b = width      # cm
        self.h = depth      # cm
        self.cover = cover # cm
        
        # 鋼筋
        self.As = As_rebar  # cm²
        
        # 柱幾何
        self.L = length     # cm
        self.K = K          # 有效長度因數
        
        # 計算斷面積
        # 混凝土斷面積 (RC 部分)
        # Ac = 總面積 - 鋼骨投影面積
        # 鋼骨投影面積 = bf × d (mm → cm²)
        bf = self.steel['bf'] / 10  # cm
        d = self.steel['d'] / 10   # cm
        steel_projected_area = bf * d  # cm²
        self.Ac = width * depth - steel_projected_area  # cm²
        
        # 鋼骨斷面積
        self.As_steel = self.steel['A']  # cm²
        
        # 總斷面積
        self.Ag = width * depth  # cm²
        
    def calculate_stiffness(self) -> dict:
        """計算鋼骨與 RC 之相對剛度"""
        mat = self.mat
        Es = mat.Es
        Ec = mat.Ec
        
        # 鋼骨剛度
        Is = self.steel['Ix']  # cm⁴
        EsIs = Es * Is
        
        # RC 慣性矩 (簡化：忽略鋼筋)
        # b × h³ / 12
        I_rc = self.b * (self.h * 10)**3 / 12 / 1e4  # cm⁴
        EcIc = Ec * I_rc
        
        # 總剛度
        EItotal = EsIs + EcIc
        
        # 分配比例
        ratio_s = EsIs / EItotal
        ratio_rc = EcIc / EItotal
        
        return {
            'EsIs': EsIs,
            'EcIc': EcIc,
            'EItotal': EItotal,
            'ratio_s': ratio_s,
            'ratio_rc': ratio_rc
        }
    
    def design_axial_strength(self, debug: bool = False) -> dict:
        """
        計算軸力強度
        
        參考：鋼骨鋼筋混凝土構造設計規範與解說 6.4節
        """
        mat = self.mat
        fc = mat.fc
        fys = mat.fy_steel
        fyr = mat.fy_rebar
        
        # ===== RC 部分軸力強度 =====
        # Pn = 0.85 × f'c × Ac + fy × As
        Pn_rc = 0.85 * fc * self.Ac + fyr * self.As  # kgf
        
        # ===== 鋼骨部分軸力強度 =====
        # Pn = fys × As
        Pn_s = fys * self.As_steel  # kgf
        
        # ===== 總軸力強度 =====
        Pn_total = Pn_rc + Pn_s
        
        # 設計軸力強度
        # RC 部分折減
        if Pn_rc > 0:
            phi_rc = 0.75  # 螺旋箍筋
        else:
            phi_rc = 0.65
            
        phi_s = 0.90
        
        phi_Pn = phi_rc * Pn_rc + phi_s * Pn_s  # kgf
        
        if debug:
            print(f"=== SRC 柱軸力強度 ===")
            print(f"  混凝土斷面積 Ac = {self.Ac:.1f} cm²")
            print(f"  鋼骨斷面積 As = {self.As_steel:.1f} cm²")
            print(f"  鋼筋面積 As(rebar) = {self.As:.1f} cm²")
            print(f"\n  RC 軸力強度 Pn_rc = {Pn_rc/1000:.1f} tf")
            print(f"  鋼骨軸力強度 Pn_s = {Pn_s/1000:.1f} tf")
            print(f"  總軸力強度 Pn = {Pn_total/1000:.1f} tf")
            print(f"  設計軸力強度 φPn = {phi_Pn/1000:.1f} tf")
        
        return {
            'Pn_rc': Pn_rc / 1000,     # tf
            'Pn_s': Pn_s / 1000,       # tf
            'Pn_total': Pn_total / 1000,  # tf
            'phi_Pn': phi_Pn / 1000    # tf
        }
    
    def design_PM_interaction(
        self, 
        Pu: float,    # 設計軸力 (tf)
        Mu: float,    # 設計彎矩 (tf-m)
        debug: bool = False
    ) -> dict:
        """
        軸力與彎矩共同作用檢核
        
        步驟：
        1. 依相對剛度分配 Pu 與 Mu
        2. 分別檢核鋼骨與 RC 部分
        """
        mat = self.mat
        
        # 計算剛度與分配比例
        stiff = self.calculate_stiffness()
        
        # 分配軸力與彎矩
        Pus = stiff['ratio_s'] * Pu  # 鋼骨部分軸力
        Purc = stiff['ratio_rc'] * Pu  # RC 部分軸力
        
        Mus = stiff['ratio_s'] * Mu  # 鋼骨部分彎矩
        Murc = stiff['ratio_rc'] * Mu  # RC 部分彎矩
        
        if debug:
            print(f"=== 軸力與彎矩分配 ===")
            print(f"  鋼骨分配比例 = {stiff['ratio_s']:.2%}")
            print(f"  RC 分配比例 = {stiff['ratio_rc']:.2%}")
            print(f"\n  Pu 分配:")
            print(f"    Pus = {Pus:.2f} tf")
            print(f"    Purc = {Purc:.2f} tf")
            print(f"\n  Mu 分配:")
            print(f"    Mus = {Mus:.2f} tf-m")
            print(f"    Murc = {Murc:.2f} tf-m")
        
        # ===== 鋼骨部分檢核 =====
        # 簡化：假設為軸心受壓 + 彎矩
        Pns = mat.fy_steel * self.As_steel / 1000  # tf
        Mns = mat.fy_steel * self.steel['Zx'] / 1e6  # tf-m
        
        phi_cs = 0.90  # 鋼骨折減因數
        phi_bs = 0.90
        
        # 互制公式 (簡化)
        if Purc > 0:
            ratio_s = Pus / (phi_cs * Pns)
            
            # 當 Pus/φPns ≥ 0.2
            if ratio_s >= 0.2:
                # P/φP + M/φM ≤ 1
                check_s = ratio_s + Mus / (phi_bs * Mns)
            else:
                # P/2φP + M/φM ≤ 1  
                check_s = Pus / (2 * phi_cs * Pns) + Mus / (phi_bs * Mns)
        else:
            check_s = Mus / (phi_bs * Mns)
        
        steel_safe = check_s <= 1.0
        
        if debug:
            print(f"\n=== 鋼骨部分檢核 ===")
            print(f"  標稱軸力 Pns = {Pns:.2f} tf")
            print(f"  標稱彎矩 Mns = {Mns:.2f} tf-m")
            print(f"  檢核值 = {check_s:.3f}")
            print(f"  安全? {'✓' if steel_safe else '✗'}")
        
        # ===== RC 部分檢核 =====
        # Pn_rc = 0.85 fc Ac + fy As
        # 正確計算 Ac (混凝土淨面積) = 總面積 - 鋼骨面積 - 鋼筋面積
        # 鋼骨斷面 30x30 cm = 900 cm²，板厚 1 cm，所以內徑約 28x28 cm
        Ac_steel = self.steel['A']  # cm² - this is actually wrong for box section
        
        # For box section, the concrete area inside the box
        bf = self.steel['bf']  # mm
        d = self.steel['d']   # mm
        tf = self.steel['tf']  # mm
        tw = self.steel['tw']  # mm
        
        # 箱型內部混凝土面積 (mm²)
        Ac_inner = (bf - 2*tw) * (d - 2*tf)  # mm²
        Ac_inner_cm2 = Ac_inner / 100  # cm²
        
        # 總混凝土斷面積
        Ac_total = self.b * self.h - self.As_steel - Ac_inner_cm2
        
        Pn_rc = (0.85 * mat.fc * Ac_total + 
                 mat.fy_rebar * self.As) / 1000  # tf
        
        # Mn_rc (簡化計算)
        d = self.h * 10 - self.cover * 10  # mm
        a = self.As * mat.fy_rebar / (0.85 * mat.fc * self.b * 10)  # cm
        a_mm = a * 10
        d_mm = d
        
        # 計算 Mn_rc (kgf-mm)
        Mn_rc_kgfmm = self.As * mat.fy_rebar * (d_mm - a_mm/2)
        # 轉換為 tf-m: kgf-mm / 1,000,000 = tf-m
        Mn_rc = Mn_rc_kgfmm / 1e6  # tf-m
        
        phi_c = 0.65
        phi_brc = 0.90
        
        if Purc > 0:
            ratio_rc = Purc / (phi_c * Pn_rc)
            
            if ratio_rc >= 0.1:
                check_rc = ratio_rc + Murc / (phi_brc * Mn_rc)
            else:
                check_rc = Purc / (2 * phi_c * Pn_rc) + Murc / (phi_brc * Mn_rc)
        else:
            check_rc = Murc / (phi_brc * Mn_rc)
        
        rc_safe = check_rc <= 1.0
        
        if debug:
            print(f"\n=== RC 部分檢核 ===")
            print(f"  標稱軸力 Pn_rc = {Pn_rc:.2f} tf")
            print(f"  標稱彎矩 Mn_rc = {Mn_rc:.2f} tf-m")
            print(f"  檢核值 = {check_rc:.3f}")
            print(f"  安全? {'✓' if rc_safe else '✗'}")
        
        # ===== 總檢核結果 =====
        is_safe = steel_safe and rc_safe
        
        if debug:
            print(f"\n=== 總檢核結果 ===")
            print(f"  {'✓ 安全' if is_safe else '✗ 不安全'}")
        
        return {
            'Pus': Pus,
            'Purc': Purc,
            'Mus': Mus,
            'Murc': Murc,
            'check_s': check_s,
            'steel_safe': steel_safe,
            'check_rc': check_rc,
            'rc_safe': rc_safe,
            'is_safe': is_safe,
            'ratio_s': stiff['ratio_s'],
            'ratio_rc': stiff['ratio_rc']
        }
    
    def calculate_pm_curve(
        self,
        rebar_positions: list = None,
        num_points: int = 30,
        debug: bool = False
    ) -> dict:
        """
        計算 SRC 柱 PM 曲線（軸力-彎矩互制圖）
        
        使用應變相容法（Strain Compatibility Method）：
        - 混凝土最大壓應變 εcu = 0.003
        - 鋼材應變與混凝土相同（握裹良好）
        - 鋼材應力-應變關係為理想彈塑性
        
        參考：鋼骨鋼筋混凝土構造設計規範與解說 第七章
        
        參數：
        - rebar_positions: 鋼筋位置列表 [y1, y2, y3, ...] (cm from top)
                           預設為 [cover, h/2, h-cover] 三層
        - num_points: PM 曲線的計算點數
        - debug: 是否顯示除錯資訊
        
        回傳：
        - pm_points: [(P, M), ...] 清單，P 為軸力(tf)，M 為彎矩(tf-m)
        - key_points: 關鍵點資訊
        """
        import numpy as np
        
        mat = self.mat
        fc = mat.fc           # kgf/cm²
        fy_steel = mat.fy_steel  # kgf/cm²
        fy_rebar = mat.fy_rebar  # kgf/cm²
        Es = mat.Es           # kgf/cm²
        eps_cu = 0.003        # 混凝土極限壓應變
        
        # 斷面幾何 (統一使用 cm 單位)
        b = self.b            # cm (寬度)
        h = self.h            # cm (深度)
        cover = self.cover   # cm
        
        # 鋼骨幾何 (mm → cm)
        steel = self.steel
        d_steel = steel['d'] / 10    # cm
        bf_steel = steel['bf'] / 10  # cm
        tf_steel = steel['tf'] / 10  # cm
        tw_steel = steel['tw'] / 10  # cm
        A_steel = steel['A']         # cm²
        
        # 鋼骨斷面位置 (從頂面算起)
        # 上翼板
        y_steel_top = tf_steel / 2
        # 下翼板
        y_steel_bot = d_steel - tf_steel / 2
        # 腹板 (頂部與底部)
        y_web_top = tf_steel
        y_web_bot = d_steel - tf_steel
        
        if debug:
            print(f"\n=== SRC PM 曲線計算 ===")
            print(f"  混凝土斷面: {b} x {h} cm")
            print(f"  鋼骨斷面: {steel} cm")
            print(f"  鋼骨尺寸: {d_steel} x {bf_steel} cm")
        
        # 鋼筋位置設定
        if rebar_positions is None:
            # 預設：三層鋼筋（頂、中、底）
            rebar_positions = [
                cover + 2,      # 頂層鋼筋
                h / 2,          # 中層鋼筋
                h - cover - 2   # 底層鋼筋
            ]
        
        # 鋼筋面積（假設每層等面積，總面積 self.As）
        n_rebar = len(rebar_positions)
        As_layer = self.As / n_rebar  # cm² 每層
        
        # 混凝土區域划分
        # 總高度 h cm，分為多個區域：
        # 1. 鋼骨上翼板區域
        # 2. 鋼骨腹板區域
        # 3. 鋼骨下翼板區域
        # 4. 純混凝土區域
        
        def get_concrete_regions(c: float) -> list:
            """
            根據中性軸深度 c 計算混凝土分區
            c: 中性軸深度 (cm from top)
            回傳: [(y_top, y_bottom, width), ...] 清單
            """
            regions = []
            
            # 鋼骨內部不計算混凝土（被鋼骨填充）
            # 混凝土只在外側
            
            # 左側純混凝土區 (寬度 b，位置在鋼骨左側)
            # 鋼骨左邊緣
            steel_left = (b - bf_steel) / 2
            steel_right = (b + bf_steel) / 2
            
            # 左側混凝土區
            if steel_left > 0:
                # 上部
                y1 = min(c, tf_steel)
                if y1 > 0:
                    regions.append((0, y1, steel_left))
                # 中部（鋼骨腹板區）
                y2 = min(c, y_web_bot)
                y3 = max(c, y_web_top) if c > y_web_top else y_web_top
                if y2 > y3:
                    regions.append((y3, y2, steel_left))
                # 下部
                if c > d_steel:
                    regions.append((d_steel, c, steel_left))
            
            # 右側純混凝土區
            if steel_right < b:
                # 上部
                y1 = min(c, tf_steel)
                if y1 > 0:
                    regions.append((0, y1, b - steel_right))
                # 中部
                y2 = min(c, y_web_bot)
                y3 = max(c, y_web_top) if c > y_web_top else y_web_top
                if y2 > y3:
                    regions.append((y3, y2, b - steel_right))
                # 下部
                if c > d_steel:
                    regions.append((d_steel, c, b - steel_right))
            
            return regions
        
        def calculate_strain_at_y(y: float, c: float) -> float:
            """計算位置 y 處的應變"""
            if y < c:
                # 壓應變
                return eps_cu * (c - y) / c
            else:
                # 拉應變
                if c < 0.1:  # 避免除以接近零
                    return eps_cu * 10  # 設定最大拉應變
                return eps_cu * (y - c) / c
        
        def get_steel_stress(y: float, c: float, fy: float) -> float:
            """計算位置 y 處的鋼材應力"""
            eps = calculate_strain_at_y(y, c)
            # 理想彈塑性模型
            if eps >= 0:  # 壓
                return min(Es * eps, fy)
            else:  # 拉
                return max(Es * eps, -fy)
        
        def calculate_pm_at_c(c: float) -> tuple:
            """
            計算指定中性軸深度 c 對應的 P, M
            c: 中性軸深度 (cm)
            回傳: (P_tf, M_tf_m)
            """
            # 1. 鋼骨貢獻
            # 鋼骨分為：上翼板、腹板、下翼板
            
            # 上翼板
            A_top = bf_steel * tf_steel
            f_top = get_steel_stress(y_steel_top, c, fy_steel)
            P_steel_top = A_top * f_top  # kgf
            M_steel_top = P_steel_top * (y_steel_top - h/2)  # kgf-cm
            
            # 下翼板
            A_bot = bf_steel * tf_steel
            f_bot = get_steel_stress(y_steel_bot, c, fy_steel)
            P_steel_bot = A_bot * f_bot
            M_steel_bot = P_steel_bot * (y_steel_bot - h/2)
            
            # 腹板
            A_web = tw_steel * (d_steel - 2*tf_steel)
            # 腹板應力取平均
            f_web_avg = get_steel_stress((y_web_top + y_web_bot)/2, c, fy_steel)
            P_steel_web = A_web * f_web_avg
            M_steel_web = P_steel_web * ((y_web_top + y_web_bot)/2 - h/2)
            
            P_steel = P_steel_top + P_steel_bot + P_steel_web
            M_steel = M_steel_top + M_steel_bot + M_steel_web
            
            # 2. 鋼筋貢獻
            P_rebar = 0
            M_rebar = 0
            for y_rebar in rebar_positions:
                f_rebar = get_steel_stress(y_rebar, c, fy_rebar)
                P_layer = As_layer * f_rebar
                M_layer = P_layer * (y_rebar - h/2)
                P_rebar += P_layer
                M_rebar += M_layer
            
            # 3. 混凝土貢獻
            # 使用等效矩形應力分佈
            beta1 = 0.85 if fc <= 280 else max(0.65, 0.85 - 0.008*(fc-280))
            a = beta1 * c  # 等效應力區塊深度
            
            P_conc = 0
            M_conc = 0
            
            # 計算各混凝土區域
            regions = get_concrete_regions(c)
            for y_top, y_bot, width in regions:
                # 該區域的混凝土面積
                A_region = width * (y_bot - y_top)  # cm²
                
                # 該區域的平均應變（簡化：取中間點）
                y_mid = (y_top + y_bot) / 2
                eps = calculate_strain_at_y(y_mid, c)
                
                # 混凝土應力（線性模型，壓應力為正）
                if eps >= 0:
                    # 壓區 - 使用應力塊
                    f_conc = 0.85 * fc
                else:
                    # 拉區 - 忽略混凝土抗拉
                    f_conc = 0
                
                P_region = A_region * f_conc
                M_region = P_region * (y_mid - h/2)
                
                P_conc += P_region
                M_conc += M_region
            
            # 總軸力與彎矩
            P_total = P_steel + P_rebar + P_conc  # kgf
            M_total = M_steel + M_rebar + M_conc  # kgf-cm
            
            return (P_total / 1000, M_total / 1e6)  # tf, tf-m
        
        # 計算 PM 曲線
        pm_points = []
        
        # 中性軸掃描範圍
        c_min = 0.5    # cm（幾乎全截面受拉）
        c_max = h * 3  # cm（全截面受壓）
        
        c_values = np.linspace(c_min, c_max, num_points)
        
        for c in c_values:
            P, M = calculate_pm_at_c(c)
            pm_points.append((P, M))
        
        # 排序（按軸力從大到小）
        pm_points.sort(key=lambda x: -x[0])
        
        # 關鍵點計算
        # 點1: 純壓 (Pmax)
        Pmax_conc = 0.85 * fc * (b * h - A_steel) / 1000  # tf
        Pmax_steel = fy_steel * A_steel / 1000
        Pmax = Pmax_conc + Pmax_steel + fy_rebar * self.As / 1000
        
        # 點2: 純彎 (Mmax) - 近似計算
        # 忽略軸力影響的純彎矩
        # Mmax ≈ 鋼骨貢獻 + RC 貢獻
        Z_s = steel['Zx']  # cm³
        Mns = Z_s * fy_steel / 1e6  # tf-m
        
        # RC 部分
        d_rc = h - cover
        a_rc = self.As * fy_rebar / (0.85 * fc * b)
        Mnrc = self.As * fy_rebar * (d_rc - a_rc/2) / 1e6
        Mmax = Mns + Mnrc
        
        # 點3: 平衡點 (近似)
        # 當鋼骨降伏且混凝土壓碎的瞬間
        c_b = d_steel * eps_cu / (eps_cu + fy_steel/Es) if fy_steel/Es > 0 else d_steel * 0.5
        P_bal, M_bal = calculate_pm_at_c(c_b)
        
        key_points = {
            'Pmax': Pmax,  # 純壓 tf
            'Mmax': Mmax,  # 純彎 tf-m
            'P_bal': P_bal,
            'M_bal': M_bal
        }
        
        if debug:
            print(f"\n  鋼骨斷面積: {A_steel:.2f} cm²")
            print(f"  鋼筋总面积: {self.As:.2f} cm²")
            print(f"  鋼筋位置: {rebar_positions} cm")
            print(f"\n  關鍵點:")
            print(f"    純壓 Pmax = {Pmax:.1f} tf")
            print(f"    純彎 Mmax = {Mmax:.1f} tf-m")
            print(f"    平衡點 ({P_bal:.1f}, {M_bal:.1f})")
        
        return {
            'pm_points': pm_points,
            'key_points': key_points,
            'rebar_positions': rebar_positions,
            'steel_geometry': {
                'd': d_steel,
                'bf': bf_steel,
                'tf': tf_steel,
                'tw': tw_steel
            }
        }
    
    def design_shear_strength(self, Vu: float, Pu: float = 0, debug: bool = False) -> dict:
        """
        設計剪力強度
        
        參考：鋼骨鋼筋混凝土構造設計規範與解說 5.5節
        
        設計剪力 Vu 由鋼骨與 RC 部分共同分擔：
        - 鋼骨部分：Vns = 0.6 × fys × Aw
        - RC 部分：Vc = 0.17 × √f'c × b × d × √(1 ± Pu/(14Ag))
        
        剪力分配比例依彎矩剛度比例分配
        
        參數：
        - Vu: 設計剪力 (tf)
        - Pu: 設計軸力 (tf)，壓力為正，拉力為負
        """
        mat = self.mat
        
        # ===== 計算剛度與分配比例 =====
        stiff = self.calculate_stiffness()
        
        # RC 部分分擔的軸力 (tf → kgf)
        Purc = stiff['ratio_rc'] * Pu * 1000  # kgf
        
        # ===== 剪力分配比例 (依彎矩強度比例) =====
        # 參考：鋼骨鋼筋混凝土構造設計規範與解說 5.5節 (公式 5.5-1, 5.5-2)
        # 剪力分配依彎矩強度比例：Vu_s = (Mns/Mn) × Vu
        # 計算鋼骨部分彎矩強度
        Z_s = self.steel['Zx']  # cm³
        Mns = Z_s * mat.fy_steel / 1e5  # tf-m (除以 100,000 從 kgf-cm 轉為 tf-m)
        
        # 計算 RC 部分彎矩強度
        d_rc = self.h * 10 - self.cover * 10  # mm
        a_rc = self.As * mat.fy_rebar / (0.85 * mat.fc * self.b * 10)  # cm
        a_rc_mm = a_rc * 10
        Mnrc = self.As * mat.fy_rebar * (d_rc - a_rc_mm/2) / 1e6  # tf-m
        
        Mn_total = Mns + Mnrc  # 總彎矩強度
        
        # 剪力分配比例 (依彎矩強度比例)
        if Mn_total > 0:
            Vns_ratio = Mns / Mn_total
            Vrc_ratio = Mnrc / Mn_total
        else:
            Vns_ratio = 0.5
            Vrc_ratio = 0.5
        
        # ===== 鋼骨部分剪力強度 =====
        # Vns = 0.6 × fys × Aw
        tw = self.steel['tw'] / 10  # cm
        d_steel = self.steel['d'] / 10  # cm
        Aw = tw * d_steel  # 腹板面積 cm²
        
        Vns = 0.6 * mat.fy_steel * Aw  # kgf
        phi_vs = 0.90
        phi_Vns = phi_vs * Vns / 1000  # tf
        
        # 鋼骨部分需承受剪力
        Vu_s = Vu * Vns_ratio  # tf
        
        if debug:
            print(f"=== 鋼骨部分剪力 ===")
            print(f"  鋼骨斷面: {list(STEEL_SECTIONS.keys())[list(STEEL_SECTIONS.values()).index(self.steel)]}")
            print(f"  腹板厚度 tw = {tw:.2f} cm")
            print(f"  腹板高度 d = {d_steel:.1f} cm")
            print(f"  腹板面積 Aw = {Aw:.2f} cm²")
            print(f"  標稱剪力強度 Vns = {Vns/1000:.2f} tf")
            print(f"  設計剪力強度 φVns = {phi_Vns:.2f} tf")
            print(f"  需要承受剪力 Vu = {Vu_s:.2f} tf")
        
        # ===== RC 部分剪力強度 =====
        # Vc = 0.17 × √f'c × b × d × √(1 ± Pu/(14Ag))
        # 參考：鋼骨鋼筋混凝土構造設計規範與解說 5.5.2節
        b = self.b  # cm
        d_rc = self.h * 10 - self.cover * 10  # mm
        d_rc_cm = d_rc / 10  # cm
        Ag = self.b * self.h  # cm² (全斷面積)
        
        # 基本 Vc
        Vc_base = 0.17 * math.sqrt(mat.fc) * b * d_rc_cm  # kgf
        
        # 軸力影響修正
        if Purc != 0:
            # Pu 為壓力時增加 Vc，為拉力時減少 Vc
            # 公式：√(1 ± Pu/(14Ag))，Pu 為 kgf
            factor = math.sqrt(1 + Purc / (14 * Ag * 1000))  # Purc 已轉換為 kgf
            Vc = Vc_base * factor  # kgf
            if debug:
                print(f"\n=== RC 部分剪力 (含軸力影響) ===")
                print(f"  混凝土寬度 b = {b} cm")
                print(f"  有效深度 d = {d_rc_cm:.1f} cm")
                print(f"  全斷面積 Ag = {Ag} cm²")
                print(f"  RC 部分軸力 Purc = {Purc/1000:.2f} tf ({'壓力' if Purc > 0 else '拉力'})")
                print(f"  軸力影響係數 = √(1 + {Purc/(14*Ag*1000):.4f}) = {factor:.3f}")
                print(f"  Vc = 0.17√{mat.fc} × {b} × {d_rc_cm:.1f} × {factor:.3f} = {Vc/1000:.2f} tf")
        else:
            Vc = Vc_base  # kgf
            if debug:
                print(f"\n=== RC 部分剪力 ===")
                print(f"  混凝土寬度 b = {b} cm")
                print(f"  有效深度 d = {d_rc_cm:.1f} cm")
                print(f"  Vc = 0.17√{mat.fc} × {b} × {d_rc_cm:.1f} = {Vc/1000:.2f} tf")
        
        phi_vrc = 0.75
        phi_Vc = phi_vrc * Vc / 1000  # tf
        
        # RC 部分需承受剪力
        Vu_rc = Vu * Vrc_ratio  # tf
        
        if debug:
            print(f"  設計剪力強度 φVc = {phi_Vc:.2f} tf")
            print(f"  需要承受剪力 Vu = {Vu_rc:.2f} tf")
        
        # ===== 總檢核 =====
        # 鋼骨部分檢核
        steel_shear_safe = phi_Vns >= Vu_s
        
        # RC 部分檢核
        rc_shear_safe = phi_Vc >= Vu_rc
        
        # 總剪力強度
        phi_Vn_total = phi_Vns + phi_Vc
        total_shear_safe = phi_Vn_total >= Vu
        
        if debug:
            print(f"\n=== 剪力檢核結果 ===")
            print(f"  鋼骨部分: φVns = {phi_Vns:.2f} tf ≥ Vu = {Vu_s:.2f} tf → {'✓ 安全' if steel_shear_safe else '✗ 不安全'}")
            print(f"  RC 部分: φVc = {phi_Vc:.2f} tf ≥ Vu = {Vu_rc:.2f} tf → {'✓ 安全' if rc_shear_safe else '✗ 不安全'}")
            print(f"  總計: φVn = {phi_Vn_total:.2f} tf ≥ Vu = {Vu:.2f} tf → {'✓ 安全' if total_shear_safe else '✗ 不安全'}")
        
        return {
            'Vns': Vns / 1000,           # tf
            'phi_Vns': phi_Vns,          # tf
            'Vu_s': Vu_s,                # tf
            'steel_shear_safe': steel_shear_safe,
            'Vc': Vc / 1000,             # tf
            'phi_Vc': phi_Vc,            # tf
            'Vu_rc': Vu_rc,              # tf
            'rc_shear_safe': rc_shear_safe,
            'phi_Vn_total': phi_Vn_total,  # tf
            'Vu': Vu,                    # tf
            'Pu': Pu,                    # tf
            'Purc': Purc / 1000,         # tf
            'is_safe': total_shear_safe,
            'Vns_ratio': Vns_ratio,
            'Vrc_ratio': Vrc_ratio,
            'Mns': Mns,                  # tf-m
            'Mnrc': Mnrc,                # tf-m
            'Mn_total': Mn_total         # tf-m
        }
    
    def shear_analysis_summary(self, Vu: float, Pu: float = 0) -> str:
        """
        產生 SRC 柱剪力分析成果摘要
        
        參考：鋼骨鋼筋混凝土構造設計規範與解說 5.5節
        """
        mat = self.mat
        result = self.design_shear_strength(Vu=Vu, Pu=Pu)
        
        # 取得鋼骨名稱
        steel_name = list(STEEL_SECTIONS.keys())[
            list(STEEL_SECTIONS.values()).index(self.steel)
        ]
        
        # 計算軸力狀態
        pu_status = "軸壓力" if Pu > 0 else ("軸拉力" if Pu < 0 else "無軸力")
        
        summary = f"""
╔══════════════════════════════════════════════════════════════╗
║              SRC 柱 剪力分析成果摘要                         ║
╠══════════════════════════════════════════════════════════════╣
║ 【設計條件】                                                  ║
║   鋼骨斷面: {steel_name:<20}                   ║
║   混凝土尺寸: {self.b}×{self.h} cm (寬×深)                        ║
║   保護層: {self.cover} cm                                             ║
║   鋼筋面積: As = {self.As:.2f} cm²                                ║
║   柱長度: L = {self.L} cm                                        ║
╠══════════════════════════════════════════════════════════════╣
║ 【材料性質】                                                  ║
║   鋼骨 Fys = {mat.fy_steel} kgf/cm²                             ║
║   鋼筋 fy = {mat.fy_rebar} kgf/cm²                               ║
║   混凝土 f'c = {mat.fc} kgf/cm²                                 ║
╠══════════════════════════════════════════════════════════════╣
║ 【彎矩強度】                                                  ║
║   鋼骨 Mns = {result['Mns']:.2f} tf-m                               ║
║   RC Mnrc = {result['Mnrc']:.2f} tf-m                             ║
║   總 Mn = {result['Mn_total']:.2f} tf-m                              ║
╠══════════════════════════════════════════════════════════════╣
║ 【外力作用】                                                  ║
║   設計剪力 Vu = {Vu:.2f} tf                                      ║
║   設計軸力 Pu = {Pu:.2f} tf ({pu_status})                    ║
╠══════════════════════════════════════════════════════════════╣
║ 【鋼骨部分剪力】                                              ║
║   分配比例: {result['Vns_ratio']*100:.1f}%                                              ║
║   需要剪力 Vu = {result['Vu_s']:.2f} tf                               ║
║   腹板面積 Aw = {self.steel['tw']*self.steel['d']/100:.2f} cm²                                 ║
║   標稱剪力 Vns = {result['Vns']:.2f} tf                             ║
║   設計剪力 φVns = {result['phi_Vns']:.2f} tf                          ║
║   檢核: {result['phi_Vns']:.2f} ≥ {result['Vu_s']:.2f} → {'✓ 安全' if result['steel_shear_safe'] else '✗ 不安全'}                ║
╠══════════════════════════════════════════════════════════════╣
║ 【RC 部分剪力】                                               ║
║   分配比例: {result['Vrc_ratio']*100:.1f}%                                             ║
║   需要剪力 Vu = {result['Vu_rc']:.2f} tf                              ║
║   有效深度 d = {self.h*10 - self.cover*10} mm                                       ║
║   混凝土寬度 b = {self.b} cm                                          ║
║   標稱剪力 Vc = {result['Vc']:.2f} tf                               ║
║   設計剪力 φVc = {result['phi_Vc']:.2f} tf                            ║
║   檢核: {result['phi_Vc']:.2f} ≥ {result['Vu_rc']:.2f} → {'✓ 安全' if result['rc_shear_safe'] else '✗ 不安全'}                ║
╠══════════════════════════════════════════════════════════════╣
║ 【總檢核】                                                    ║
║   總設計剪力 φVn = {result['phi_Vn_total']:.2f} tf                        ║
║   需要剪力 Vu = {Vu:.2f} tf                                      ║
║   結論: {'✓ 安全' if result['is_safe'] else '✗ 不安全'}                                    ║
╚══════════════════════════════════════════════════════════════╝
"""
        return summary


# ============================================================================
# 設計驗證範例
# ============================================================================

def example_beam_design():
    """SRC 梁設計範例"""
    print("=" * 60)
    print("SRC 梁設計範例 - 強度疊加法")
    print("=" * 60)
    
    # 設計條件
    # 鋼骨：H400x200x8x13
    # 混凝土：b=40cm, h=80cm, 保護層=5cm
    # 鋼筋：4-D16 (As = 4×2.01 = 8.04 cm²)
    
    beam = SRCBeam(
        section_name='H400x200x8x13',
        width=40,      # cm
        height=80,     # cm
        cover=5,       # cm
        As_rebar=8.04, # cm² (4-D16)
        material=DEFAULT_MATERIAL
    )
    
    print("\n設計條件:")
    print(f"  鋼骨: H400x200x8x13")
    print(f"  混凝土: {beam.b}×{beam.h} cm, 保護層 {beam.cover} cm")
    print(f"  鋼筋: As = {beam.As} cm² (4-D16)")
    print(f"  材料: fys = {DEFAULT_MATERIAL.fy_steel} kgf/cm², fy = {DEFAULT_MATERIAL.fy_rebar} kgf/cm², f'c = {DEFAULT_MATERIAL.fc} kgf/cm²")
    
    # 計算彎矩強度
    print("\n" + "-" * 40)
    Mn_result = beam.design_moment_strength(debug=True)
    
    print(f"\n【設計彎矩強度】")
    print(f"  φMn = {Mn_result['phi_Mn_total']:.2f} tf-m")
    
    # 計算剪力強度
    print("\n" + "-" * 40)
    print("【剪力檢核】")
    Vu = 15  # tf (假設)
    V_result = beam.design_shear_strength(Vu=Vu, debug=True)
    
    print(f"\n  結論: {'安全 ✓' if V_result['is_safe'] else '不安全 ✗'}")
    
    return Mn_result


def example_column_design():
    """SRC 柱設計範例"""
    print("\n" + "=" * 60)
    print("SRC 柱設計範例 - 相對剛度法")
    print("=" * 60)
    
    # 設計條件 - 純軸力設計檢核
    # 鋼骨：BOX300x300x10x10
    # 混凝土：b=50cm, h=50cm, 保護層=4cm
    # 鋼筋：8-D16 (8×2.01 = 16.08 cm²)
    # 柱長度：300cm
    
    column = SRCColumn(
        section_name='BOX300x300x10x10',
        width=50,       # cm
        depth=50,       # cm
        cover=4,        # cm
        As_rebar=16.08, # cm² (8-D16)
        length=300,     # cm
        K=1.0,
        material=DEFAULT_MATERIAL
    )
    
    print("\n設計條件:")
    print(f"  鋼骨: BOX300x300x10x10")
    print(f"  混凝土: {column.b}×{column.h} cm, 保護層 {column.cover} cm")
    print(f"  鋼筋: As = {column.As} cm² (8-D16)")
    print(f"  柱長度: {column.L} cm")
    print(f"  材料: fys = {DEFAULT_MATERIAL.fy_steel} kgf/cm², fy = {DEFAULT_MATERIAL.fy_rebar} kgf/cm², f'c = {DEFAULT_MATERIAL.fc} kgf/cm²")
    
    # 計算軸力強度
    print("\n" + "-" * 40)
    Pn_result = column.design_axial_strength(debug=True)
    
    # 軸力檢核 - 只檢核軸力
    print("\n" + "-" * 40)
    print("【軸力檢核】")
    Pu = 200   # tf (純軸力)
    
    print(f"\n設計軸力:")
    print(f"  Pu = {Pu} tf")
    
    is_safe_axial = Pn_result['phi_Pn'] >= Pu
    
    print(f"\n  設計軸力強度 φPn = {Pn_result['phi_Pn']:.1f} tf")
    print(f"  需要軸力 Pu = {Pu} tf")
    print(f"  結論: {'✓ 安全' if is_safe_axial else '✗ 不安全'}")
    
    return Pn_result


# ============================================================================
# 主程式
# ============================================================================

if __name__ == "__main__":
    print("\n" + "█" * 60)
    print("  SRC 鋼骨鋼筋混凝土結構設計程式")
    print("  Steel Reinforced Concrete Design Program")
    print("█" * 60)
    print("\n⚠️  本程式僅供設計初稿參考，實際設計應經專業結構技師確認。\n")
    
    # 執行範例
    example_beam_design()
    example_column_design()
    
    print("\n" + "=" * 60)
    print("  程式結束")
    print("=" * 60)
