#!/usr/bin/env python3
"""
SRC 鋼骨鋼筋混凝土結構設計程式 (完整版)
Steel Reinforced Concrete Design Program

設計依據：
- 鋼骨鋼筋混凝土構造設計規範與解說
- 建築物混凝土結構設計規範 (112年版)
- 鋼結構極限設計法規範及解說

版本：v2.0
更新：
- 公式檢核功能
- 自動斷面選取
- 自訂斷面輸入

⚠️ 重要提醒：本程式僅供設計初稿參考，實際設計應經專業結構技師確認。
"""

import math
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Tuple
from enum import Enum

# ============================================================================
# 設計規範常數
# ============================================================================

class DesignCode:
    """設計規範常數"""
    
    # 折減因數
    PHI_FLEXURE = 0.90      # 撓曲
    PHI_SHEAR = 0.75        # 剪力
    PHI_AXIAL_SPIRAL = 0.75 # 軸力 (螺旋箍筋)
    PHI_AXIAL_TIE = 0.65    # 軸力 (普通箍筋)
    PHI_ANCHOR = 0.75       # 錨定
    
    # 鋼筋比限制
    RHO_MIN = 1.4 / 4200    # 最小鋼筋比
    
    # 混凝土
    LAMBDA_NORMAL = 1.0     # 一般混凝土
    LAMBDA_LIGHT = 0.75     # 輕質混凝土
    
    # 鋼骨
    FYS_MAX = 3520          # 鋼骨最大降伏應力 (kgf/cm²)
    FYR_MAX = 5600          # 鋼筋最大降伏應力 (kgf/cm²)
    FC_MIN = 210            # 混凝土最小抗壓強度


@dataclass
class MaterialProperties:
    """材料性質"""
    fy_steel: float = 2800   # 鋼骨降伏應力 (kgf/cm²)
    fy_rebar: float = 4200    # 鋼筋降伏應力 (kgf/cm²)
    fc: float = 280           # 混凝土設計抗壓強度 (kgf/cm²)
    Es: float = 2.04e6        # 鋼材彈性模數 (kgf/cm²)
    Ec: float = field(init=False)  # 混凝土彈性模數
    
    def __post_init__(self):
        # Ec = 4700 * sqrt(f'c) (ACI 318 / 台灣規範)
        self.Ec = 4700 * math.sqrt(self.fc) * 10  # kgf/cm²


@dataclass 
class SteelSection:
    """鋼骨斷面資料"""
    name: str
    section_type: str  # 'H' or 'BOX'
    bf: float          # 翼板寬度 (mm)
    tf: float          # 翼板厚度 (mm)
    tw: float          # 腹板厚度 (mm)
    d: float           # 深度 (mm)
    Ix: float          # 慣性矩 (cm⁴)
    Zx: float          # 塑性斷面模數 (cm³)
    A: float           # 斷面積 (cm²)
    rx: float = field(init=False)  # 迴轉半徑 (cm)
    
    def __post_init__(self):
        self.rx = math.sqrt(self.Ix / self.A) if self.A > 0 else 0


# 內建鋼骨資料庫
STEEL_SECTIONS_DB: Dict[str, SteelSection] = {
    # H型鋼 (mm)
    'H300x150x6.5x9': SteelSection('H300x150x6.5x9', 'H', 150, 9, 6.5, 300, 3770, 251, 46.78),
    'H350x175x7x11': SteelSection('H350x175x7x11', 'H', 175, 11, 7, 350, 7890, 450, 62.91),
    'H400x200x8x13': SteelSection('H400x200x8x13', 'H', 200, 13, 8, 400, 13400, 670, 84.12),
    'H450x200x9x14': SteelSection('H450x200x9x14', 'H', 200, 14, 9, 450, 18700, 831, 96.76),
    'H500x200x10x16': SteelSection('H500x200x10x16', 'H', 200, 16, 10, 500, 25500, 1120, 114.2),
    'H600x200x11x17': SteelSection('H600x200x11x17', 'H', 200, 17, 11, 600, 36200, 1490, 134.4),
    'H700x300x13x24': SteelSection('H700x300x13x24', 'H', 300, 24, 13, 700, 55700, 2270, 260.0),
    
    # 箱型鋼 (mm)
    'BOX200x200x9x9': SteelSection('BOX200x200x9x9', 'BOX', 200, 9, 9, 200, 2620, 290, 57.36),
    'BOX250x250x9x9': SteelSection('BOX250x250x9x9', 'BOX', 250, 9, 9, 250, 5200, 576, 71.36),
    'BOX300x300x10x10': SteelSection('BOX300x300x10x10', 'BOX', 300, 10, 10, 300, 8950, 1080, 95.36),
    'BOX350x350x12x12': SteelSection('BOX350x350x12x12', 'BOX', 350, 12, 12, 350, 14300, 1588, 129.36),
    'BOX400x400x14x14': SteelSection('BOX400x400x14x14', 'BOX', 400, 14, 14, 400, 21400, 2370, 169.36),
    'BOX500x500x16x16': SteelSection('BOX500x500x16x16', 'BOX', 500, 16, 16, 500, 43800, 4850, 249.0),
    'BOX600x600x20x20': SteelSection('BOX600x600x20x20', 'BOX', 600, 20, 20, 600, 76800, 8540, 368.0),
}

# 鋼筋資料庫
REBAR_DB = {
    'D10': {'A': 0.71, 'd': 10},
    'D13': {'A': 1.27, 'd': 13},
    'D16': {'A': 2.01, 'd': 16},
    'D19': {'A': 2.87, 'd': 19},
    'D22': {'A': 3.87, 'd': 22},
    'D25': {'A': 5.07, 'd': 25},
    'D29': {'A': 6.51, 'd': 29},
    'D32': {'A': 8.04, 'd': 32},
}


# ============================================================================
# 自訂鋼骨斷面
# ============================================================================

def create_custom_steel_section(
    name: str,
    section_type: str,
    bf: float,  # mm
    tf: float,  # mm  
    tw: float,  # mm
    d: float,   # mm
    fy: float = 2800  # kgf/cm²
) -> SteelSection:
    """
    建立自訂鋼骨斷面
    
    計算慣性矩與塑性斷面模數
    """
    bf_cm = bf / 10
    tf_cm = tf / 10
    tw_cm = tw / 10
    d_cm = d / 10
    
    A = (bf_cm * tf_cm * 2 + tw_cm * (d_cm - 2*tf_cm)) / 100  # cm²
    
    if section_type.upper() == 'H':
        # H型鋼慣性矩
        Ix = (bf_cm * d_cm**3 - (bf_cm - tw_cm) * (d_cm - 2*tf_cm)**3) / 12
        # 簡化塑性斷面模數
        Zx = 1.1 * Ix / (d_cm / 2)
    else:  # BOX
        # 箱型慣性矩
        Ix = (bf_cm * d_cm**3 - (bf_cm - 2*tw_cm) * (d_cm - 2*tf_cm)**3) / 12
        Zx = 1.15 * Ix / (d_cm / 2)
    
    return SteelSection(name, section_type.upper(), bf, tf, tw, d, Ix, Zx, A * 100)


# ============================================================================
# SRC 梁設計類別
# ============================================================================

class SRCBeamDesigner:
    """
    SRC 梁設計 (強度疊加法)
    
    依據：鋼骨鋼筋混凝土構造設計規範與解說 第五章
    """
    
    def __init__(self, material: MaterialProperties = None):
        self.mat = material or MaterialProperties()
        self.code = DesignCode()
        
    def verify_materials(self) -> Dict:
        """檢核材料是否符合規範"""
        issues = []
        
        if self.mat.fy_steel > self.code.FYS_MAX:
            issues.append(f"鋼骨降伏應力 {self.mat.fy_steel} > {self.code.FYS_MAX} kgf/cm²")
        
        if self.mat.fy_rebar > self.code.FYR_MAX:
            issues.append(f"鋼筋降伏應力 {self.mat.fy_rebar} > {self.code.FYR_MAX} kgf/cm²")
            
        if self.mat.fc < self.code.FC_MIN:
            issues.append(f"混凝土抗壓強度 {self.mat.fc} < {self.code.FC_MIN} kgf/cm²")
            
        return {
            'valid': len(issues) == 0,
            'issues': issues
        }
        
    def calculate_moment(
        self, 
        steel: SteelSection,
        width: float,    # cm
        height: float,   # cm
        cover: float,   # cm
        As: float       # cm²
    ) -> Dict:
        """
        計算彎矩強度
        
        公式檢�：
        φbMn = φbsMns + φbrcMnrc
        
        Mns = Z × Fys (鋼骨塑性彎矩)
        Mnrc = As × fy × (d - a/2) (RC彎矩)
        a = (As × fy) / (0.85 × fc × b)
        """
        mat = self.mat
        
        # ===== 鋼骨部分 =====
        # Mns = Z × Fys
        Mns = steel.Zx * mat.fy_steel / 1e6  # tf-m
        phi_Mns = self.code.PHI_FLEXURE * Mns
        
        # ===== RC 部分 =====
        d_rc = height * 10 - cover * 10  # mm
        d_rc_cm = d_rc / 10  # cm
        
        # a = (As × fy) / (0.85 × fc × b)
        a = (As * mat.fy_rebar) / (0.85 * mat.fc * width)  # cm
        
        # Mnrc = As × fy × (d - a/2)
        Mnrc = As * mat.fy_rebar * (d_rc - a*10/2) / 1e6  # tf-m
        phi_Mnrc = self.code.PHI_FLEXURE * Mnrc
        
        # ===== 疊加 =====
        phi_Mn_total = phi_Mns + phi_Mnrc
        
        # 鋼筋比
        rho = As / (width * d_rc_cm)
        rho_min = self.code.RHO_MIN
        
        return {
            'steel_section': steel.name,
            'concrete': {'b': width, 'h': height, 'cover': cover},
            'rebar': {'As': As, 'rho': rho},
            
            # 鋼骨部分
            'Mns': Mns,
            'phi_Mns': phi_Mns,
            
            # RC部分
            'd_rc': d_rc_cm,
            'a': a,
            'Mnrc': Mnrc,
            'phi_Mnrc': phi_Mnrc,
            
            # 總計
            'phi_Mn_total': phi_Mn_total,
            
            # 檢核
            'rho_ok': rho >= rho_min,
            'rho_min': rho_min
        }
    
    def calculate_shear(
        self,
        steel: SteelSection,
        width: float,
        height: float,
        cover: float,
        As: float,
        Vu: float
    ) -> Dict:
        """
        計算剪力強度
        
        公式檢核：
        鋼骨：Vns = 0.6 × Fys × Aw
        RC：Vc = 0.17 × √fc × b × d
        """
        mat = self.mat
        
        # 鋼骨腹板面積
        tw_cm = steel.tw / 10
        d_cm = steel.d / 10
        Aw = tw_cm * d_cm  # cm²
        
        # Vns = 0.6 × Fys × Aw
        Vns = 0.6 * mat.fy_steel * Aw / 1000  # tf
        phi_Vns = self.code.PHI_SHEAR * Vns
        
        # Vc = 0.17 × √fc × b × d
        d_rc = height * 10 - cover * 10  # mm
        d_rc_cm = d_rc / 10
        Vc = 0.17 * math.sqrt(mat.fc) * width * d_rc_cm / 1000  # tf
        phi_Vc = self.code.PHI_SHEAR * Vc
        
        # 總設計剪力強度
        phi_Vn = phi_Vns + phi_Vc
        
        return {
            'Vu': Vu,
            'steel': {'Aw': Aw, 'Vns': Vns, 'phi_Vns': phi_Vns},
            'rc': {'Vc': Vc, 'phi_Vc': phi_Vc},
            'phi_Vn': phi_Vn,
            'is_safe': phi_Vn >= Vu
        }
    
    def auto_select_section(
        self,
        Mu: float,      # tf-m
        width: float,   # cm
        height: float,  # cm
        cover: float,   # cm
        As: float,      # cm²
        section_type: str = 'H'
    ) -> Dict:
        """
        自動選取鋼骨斷面
        
        遍歷資料庫，選取滿足設計彎矩需求的最經濟斷面
        """
        candidates = []
        
        for name, steel in STEEL_SECTIONS_DB.items():
            if section_type.upper() in name.upper():
                result = self.calculate_moment(steel, width, height, cover, As)
                
                if result['phi_Mn_total'] >= Mu:
                    candidates.append({
                        'name': name,
                        'phi_Mn': result['phi_Mn_total'],
                        'weight': steel.A,
                        'steel': steel
                    })
        
        if candidates:
            # 依重量排序，選最輕的
            candidates.sort(key=lambda x: x['weight'])
            best = candidates[0]
            
            return {
                'found': True,
                'selected': best['name'],
                'phi_Mn': best['phi_Mn'],
                'weight': best['weight'],
                'candidates': candidates[:5]  # 前5個候選
            }
        
        return {'found': False, 'candidates': candidates}


# ============================================================================
# SRC 柱設計類別
# ============================================================================

class SRCColumnDesigner:
    """
    SRC 柱設計 (相對剛度法)
    
    依據：鋼骨鋼筋混凝土構造設計規範與解說 第七章
    """
    
    def __init__(self, material: MaterialProperties = None):
        self.mat = material or MaterialProperties()
        self.code = DesignCode()
        
    def calculate_axial(
        self,
        steel: SteelSection,
        width: float,   # cm
        depth: float,  # cm
        cover: float,  # cm
        As: float      # cm²
    ) -> Dict:
        """
        計算軸力強度
        
        公式檢核：
        Pn = Pn_rc + Pns
        Pn_rc = 0.85 × fc' × Ac + fy × As
        Pns = fys × As_steel
        """
        mat = self.mat
        
        # 計算混凝土淨面積
        bf = steel.bf
        d = steel.d
        tf = steel.tf
        tw = steel.tw
        
        # 箱型內部混凝土面積
        Ac_inner = (bf - 2*tw) * (d - 2*tf) / 100  # cm²
        Ac = width * depth - steel.A - Ac_inner  # 混凝土淨面積
        
        # Pn_rc = 0.85 × fc' × Ac + fy × As
        Pn_rc = (0.85 * mat.fc * Ac + mat.fy_rebar * As) / 1000  # tf
        
        # Pns = fys × As_steel
        Pn_s = mat.fy_steel * steel.A / 1000  # tf
        
        # 總軸力
        Pn_total = Pn_rc + Pn_s
        
        # 設計軸力強度
        phi_Pn = self.code.PHI_AXIAL_SPIRAL * Pn_rc + self.code.PHI_FLEXURE * Pn_s
        
        return {
            'Ac': Ac,
            'Ac_inner': Ac_inner,
            'Pn_rc': Pn_rc,
            'Pn_s': Pn_s,
            'Pn_total': Pn_total,
            'phi_Pn': phi_Pn
        }
    
    def calculate_PM(
        self,
        steel: SteelSection,
        width: float,
        depth: float,
        cover: float,
        As: float,
        Pu: float,
        Mu: float
    ) -> Dict:
        """
        軸力與彎矩共同作用檢核
        
        公式檢核：
        1. 依相對剛度分配 Pu 與 Mu
        2. 分別檢核鋼骨與 RC 部分
        
        鋼骨：P/φP + M/φM ≤ 1 (或簡化公式)
        RC：同上
        """
        mat = self.mat
        
        # ===== 計算剛度 =====
        EsIs = mat.Es * steel.Ix
        I_rc = width * (depth * 10)**3 / 12 / 1e4
        EcIc = mat.Ec * I_rc
        
        ratio_s = EsIs / (EsIs + EcIc)
        ratio_rc = EcIc / (EsIs + EcIc)
        
        # ===== 分配力 =====
        Pus = ratio_s * Pu
        Purc = ratio_rc * Pu
        Mus = ratio_s * Mu
        Murc = ratio_rc * Mu
        
        # ===== 鋼骨檢核 =====
        Pns = mat.fy_steel * steel.A / 1000  # tf
        Mns = mat.fy_steel * steel.Zx / 1e6  # tf-m
        
        phi_Ps = self.code.PHI_FLEXURE
        phi_Ms = self.code.PHI_FLEXURE
        
        if Pus > 0:
            ratio = Pus / (phi_Ps * Pns)
            if ratio >= 0.2:
                check_s = ratio + Mus / (phi_Ms * Mns)
            else:
                check_s = Pus / (2 * phi_Ps * Pns) + Mus / (phi_Ms * Mns)
        else:
            check_s = Mus / (phi_Ms * Mns) if Mns > 0 else 0
            
        steel_safe = check_s <= 1.0
        
        # ===== RC 檢核 =====
        bf = steel.bf
        d_st = steel.d
        tf = steel.tf
        tw = steel.tw
        
        Ac_inner = (bf - 2*tw) * (d_st - 2*tf) / 100
        Ac = width * depth - steel.A - Ac_inner
        
        Pn_rc = (0.85 * mat.fc * Ac + mat.fy_rebar * As) / 1000
        
        d_rc = depth * 10 - cover * 10
        a = As * mat.fy_rebar / (0.85 * mat.fc * width * 10)
        Mn_rc = As * mat.fy_rebar * (d_rc - a*10/2) / 1e6
        
        phi_Prc = self.code.PHI_AXIAL_TIE
        phi_Mrc = self.code.PHI_FLEXURE
        
        if Purc > 0:
            ratio = Purc / (phi_Prc * Pn_rc)
            if ratio >= 0.1:
                check_rc = ratio + Murc / (phi_Mrc * Mn_rc)
            else:
                check_rc = Purc / (2 * phi_Prc * Pn_rc) + Murc / (phi_Mrc * Mn_rc)
        else:
            check_rc = Murc / (phi_Mrc * Mn_rc) if Mn_rc > 0 else 0
            
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
    
    def auto_select_section(
        self,
        Pu: float,
        Mu: float,
        width: float,
        depth: float,
        cover: float,
        As: float,
        section_type: str = 'BOX'
    ) -> Dict:
        """自動選取鋼骨斷面"""
        candidates = []
        
        for name, steel in STEEL_SECTIONS_DB.items():
            if section_type.upper() in name.upper():
                result = self.calculate_PM(steel, width, depth, cover, As, Pu, Mu)
                
                if result['is_safe']:
                    candidates.append({
                        'name': name,
                        'weight': steel.A,
                        'phi_Pn': self.calculate_axial(steel, width, depth, cover, As)['phi_Pn'],
                        'steel': steel
                    })
        
        if candidates:
            candidates.sort(key=lambda x: x['weight'])
            best = candidates[0]
            
            return {
                'found': True,
                'selected': best['name'],
                'phi_Pn': best['phi_Pn'],
                'weight': best['weight'],
                'candidates': candidates[:5]
            }
        
        return {'found': False}


# ============================================================================
# 主程式範例
# ============================================================================

def main():
    print("=" * 60)
    print("  SRC 結構設計程式 v2.0")
    print("  - 公式檢核")
    print("  - 自動斷面選取")
    print("  - 自訂斷面輸入")
    print("=" * 60)
    print("\n⚠️  本程式僅供設計初稿參考，實際設計應經專業結構技師確認。\n")
    
    # 建立設計工具
    beam = SRCBeamDesigner()
    column = SRCColumnDesigner()
    
    # ===== 1. 材料檢核 =====
    print("【1. 材料檢核】")
    mat_check = beam.verify_materials()
    if mat_check['valid']:
        print("  ✓ 材料符合規範")
    else:
        for issue in mat_check['issues']:
            print(f"  ✗ {issue}")
    
    # ===== 2. SRC 梁設計 =====
    print("\n" + "=" * 60)
    print("【2. SRC 梁設計】")
    print("=" * 60)
    
    # 使用自訂斷面
    custom_steel = create_custom_steel_section(
        name='Custom-H400',
        section_type='H',
        bf=200, tf=13, tw=8, d=400
    )
    print(f"\n自訂鋼骨斷面: {custom_steel.name}")
    print(f"  斷面積: {custom_steel.A:.1f} cm²")
    print(f"  Ix: {custom_steel.Ix:.0f} cm⁴")
    print(f"  Zx: {custom_steel.Zx:.1f} cm³")
    
    # 計算彎矩
    result = beam.calculate_moment(
        steel=custom_steel,
        width=40, height=80, cover=5,
        As=8.04  # 4-D16
    )
    
    print(f"\n設計結果:")
    print(f"  鋼骨 Mns = {result['Mns']:.2f} tf-m")
    print(f"  RC Mnrc = {result['Mnrc']:.2f} tf-m")
    print(f"  總 φMn = {result['phi_Mn_total']:.2f} tf-m")
    print(f"  鋼筋比 ρ = {result['rebar']['rho']:.4f} (min: {result['rho_min']:.4f})")
    print(f"  {'✓ OK' if result['rho_ok'] else '✗ 不足'}")
    
    # 自動選取
    print("\n【自動選取斷面】")
    auto = beam.auto_select_section(
        Mu=15, width=40, height=80, cover=5,
        As=8.04, section_type='H'
    )
    
    if auto['found']:
        print(f"  推薦: {auto['selected']}")
        print(f"  φMn = {auto['phi_Mn']:.2f} tf-m")
        print(f"  候選:")
        for c in auto['candidates']:
            print(f"    - {c['name']}: φMn = {c['phi_Mn']:.2f} tf-m, 重量 = {c['weight']:.1f} kg/m")
    
    # ===== 3. SRC 柱設計 =====
    print("\n" + "=" * 60)
    print("【3. SRC 柱設計】")
    print("=" * 60)
    
    # 使用資料庫斷面
    steel_box = STEEL_SECTIONS_DB['BOX300x300x10x10']
    
    # 計算軸力
    axial = column.calculate_axial(
        steel=steel_box,
        width=50, depth=50, cover=4,
        As=16.08  # 8-D16
    )
    
    print(f"\n軸力強度 ({steel_box.name}):")
    print(f"  φPn = {axial['phi_Pn']:.1f} tf")
    
    # P-M 檢核
    pm = column.calculate_PM(
        steel=steel_box,
        width=50, depth=50, cover=4,
        As=16.08, Pu=80, Mu=15
    )
    
    print(f"\nP-M 檢核 (Pu={80}tf, Mu={15}tf-m):")
    print(f"  鋼骨分配: {pm['ratio_s']:.1%}")
    print(f"  RC分配: {pm['ratio_rc']:.1%}")
    print(f"  鋼骨檢核: {pm['check_s']:.3f} ({'✓' if pm['steel_safe'] else '✗'})")
    print(f"  RC檢核: {pm['check_rc']:.3f} ({'✓' if pm['rc_safe'] else '✗'})")
    print(f"  結論: {'✓ 安全' if pm['is_safe'] else '✗ 不安全'}")
    
    # 自動選取
    print("\n【自動選取柱斷面】")
    auto_col = column.auto_select_section(
        Pu=80, Mu=15, width=50, depth=50, cover=4,
        As=16.08, section_type='BOX'
    )
    
    if auto_col['found']:
        print(f"  推薦: {auto_col['selected']}")
        print(f"  φPn = {auto_col['phi_Pn']:.1f} tf")
    else:
        print("  找不到符合條件的斷面，請增大斷面或增加鋼筋")
    
    print("\n" + "=" * 60)
    print("  程式結束")
    print("=" * 60)


if __name__ == "__main__":
    main()
