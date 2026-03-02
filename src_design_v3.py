#!/usr/bin/env python3
"""
SRC 鋼骨鋼筋混凝土結構設計程式 (完整計算報告版)
Steel Reinforced Concrete Design Program

設計依據：
- 鋼骨鋼筋混凝土構造設計規範與解說
- 建築物混凝土結構設計規範 (112年版)
- 鋼結構極限設計法規範及解說

版本：v3.0 - 完整計算過程與規範來源

⚠️ 重要提醒：本程式僅供設計初稿參考，實際設計應經專業結構技師確認。
"""

import math
from dataclasses import dataclass, field
from typing import Dict
from datetime import datetime

# ============================================================================
# 設計規範常數
# ============================================================================

class DesignCodeRef:
    """設計規範來源"""
    SRC_CH5 = "鋼骨鋼筋混凝土構造設計規範與解說 第五章"
    SRC_CH6 = "鋼骨鋼筋混凝土構造設計規範與解說 第六章"
    SRC_CH7 = "鋼骨鋼筋混凝土構造設計規範與解說 第七章"
    ACI_318 = "建築物混凝土結構設計規範 (112年版)"
    AISC_LRFD = "鋼結構極限設計法規範及解說"


@dataclass
class MaterialProperties:
    fy_steel: float = 2800
    fy_rebar: float = 4200
    fc: float = 280
    Es: float = 2.04e6
    Ec: float = field(init=False)
    
    def __post_init__(self):
        self.Ec = 4700 * math.sqrt(self.fc) * 10


@dataclass
class SteelSection:
    name: str
    section_type: str
    bf: float
    tf: float
    tw: float
    d: float
    Ix: float
    Zx: float
    A: float
    rx: float = field(init=False)
    
    def __post_init__(self):
        self.rx = math.sqrt(self.Ix / self.A) if self.A > 0 else 0


# ============================================================================
# 鋼骨資料庫
# ============================================================================

STEEL_SECTIONS_DB = {
    'H300x150x6.5x9': SteelSection('H300x150x6.5x9', 'H', 150, 9, 6.5, 300, 3770, 251, 46.78),
    'H350x175x7x11': SteelSection('H350x175x7x11', 'H', 175, 11, 7, 350, 7890, 450, 62.91),
    'H400x200x8x13': SteelSection('H400x200x8x13', 'H', 200, 13, 8, 400, 13400, 670, 84.12),
    'H450x200x9x14': SteelSection('H450x200x9x14', 'H', 200, 14, 9, 450, 18700, 831, 96.76),
    'H500x200x10x16': SteelSection('H500x200x10x16', 'H', 200, 16, 10, 500, 25500, 1120, 114.2),
    'H600x200x11x17': SteelSection('H600x200x11x17', 'H', 200, 17, 11, 600, 36200, 1490, 134.4),
    'BOX200x200x9x9': SteelSection('BOX200x200x9x9', 'BOX', 200, 9, 9, 200, 2620, 290, 57.36),
    'BOX250x250x9x9': SteelSection('BOX250x250x9x9', 'BOX', 250, 9, 9, 250, 5200, 576, 71.36),
    'BOX300x300x10x10': SteelSection('BOX300x300x10x10', 'BOX', 300, 10, 10, 300, 8950, 1080, 95.36),
    'BOX350x350x12x12': SteelSection('BOX350x350x12x12', 'BOX', 350, 12, 12, 350, 14300, 1588, 129.36),
    'BOX400x400x14x14': SteelSection('BOX400x400x14x14', 'BOX', 400, 14, 14, 400, 21400, 2370, 169.36),
    'BOX500x500x16x16': SteelSection('BOX500x500x16x16', 'BOX', 500, 16, 16, 500, 43800, 4850, 249.0),
}


# ============================================================================
# SRC 梁設計
# ============================================================================

class SRCBeamDesigner:
    def __init__(self, material=None):
        self.mat = material or MaterialProperties()
        
    def verify_materials(self):
        issues = []
        if self.mat.fy_steel > 3520:
            issues.append(f"鋼骨 {self.mat.fy_steel} > 3520")
        if self.mat.fy_rebar > 5600:
            issues.append(f"鋼筋 {self.mat.fy_rebar} > 5600")
        if self.mat.fc < 210:
            issues.append(f"混凝土 {self.mat.fc} < 210")
        return {'valid': len(issues) == 0, 'issues': issues}
    
    def calculate_moment(self, steel, width, height, cover, As):
        d_rc = height * 10 - cover * 10
        d_rc_cm = d_rc / 10
        Mns = steel.Zx * self.mat.fy_steel / 1e6
        phi_Mns = 0.9 * Mns
        a = As * self.mat.fy_rebar / (0.85 * self.mat.fc * width)
        Mnrc = As * self.mat.fy_rebar * (d_rc - a*10/2) / 1e6
        phi_Mnrc = 0.9 * Mnrc
        phi_Mn_total = phi_Mns + phi_Mnrc
        return {
            'phi_Mn_total': phi_Mn_total,
            'Mns': Mns, 'phi_Mns': phi_Mns,
            'Mnrc': Mnrc, 'phi_Mnrc': phi_Mnrc,
            'rho': As / (width * d_rc_cm), 'd_rc': d_rc_cm, 'a': a
        }
    
    def generate_report(self, steel, width, height, cover, As, Mu, Vu=0):
        """產生完整計算報告"""
        mat = self.mat
        code = DesignCodeRef()
        
        # 計算
        d_rc = height * 10 - cover * 10
        d_rc_cm = d_rc / 10
        Mns = steel.Zx * mat.fy_steel / 1e6
        phi_Mns = 0.9 * Mns
        a = As * mat.fy_rebar / (0.85 * mat.fc * width)
        Mnrc = As * mat.fy_rebar * (d_rc - a*10/2) / 1e6
        phi_Mnrc = 0.9 * Mnrc
        phi_Mn_total = phi_Mns + phi_Mnrc
        rho = As / (width * d_rc_cm)
        
        # 剪力
        tw_cm = steel.tw / 10
        d_cm = steel.d / 10
        Aw = tw_cm * d_cm
        Vns = 0.6 * mat.fy_steel * Aw / 1000
        phi_Vns = 0.75 * Vns
        Vc = 0.17 * math.sqrt(mat.fc) * width * d_rc_cm / 1000
        phi_Vc = 0.75 * Vc
        phi_Vn = phi_Vns + phi_Vc
        
        lines = []
        lines.append("=" * 75)
        lines.append("         SRC 鋼骨鋼筋混凝土結構設計計算書")
        lines.append("=" * 75)
        lines.append(f"產生日期：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("")
        
        # 一、設計條件
        lines.append("一、設計條件")
        lines.append("-" * 75)
        lines.append(f"""
【材料】
  鋼骨 Fys = {mat.fy_steel} kgf/cm²  (規範：≤ 3520 kgf/cm²，{code.SRC_CH5})
  鋼筋 Fy  = {mat.fy_rebar} kgf/cm²  (規範：≤ 5600 kgf/cm²)
  混凝土 fc'= {mat.fc} kgf/cm²       (規範：≥ 210 kgf/cm²，{code.ACI_318} 第19章)

【鋼骨斷面】{steel.name}
  bf={steel.bf}mm, tf={steel.tf}mm, tw={steel.tw}mm, d={steel.d}mm
  A={steel.A}cm², Ix={steel.Ix}cm⁴, Zx={steel.Zx}cm³

【混凝土斷面】
  b={width}cm, h={height}cm, 保護層={cover}cm

【鋼筋】As={As}cm², d={d_rc_cm:.1f}cm
""")
        
        # 二、彎矩強度
        lines.append("二、彎矩強度計算 (強度疊加法)")
        lines.append("-" * 75)
        lines.append(f"""
【規範來源】{code.SRC_CH5} 5.4.1 節
  公式：φbMn = φbsMns + φbrcMnrc
        = 0.9×Mns + 0.9×Mnrc

─────────────────────────────────────────────────────────────────────────────
2.1 鋼骨部分 [Mns = Z × Fys]
─────────────────────────────────────────────────────────────────────────────
  Mns = {steel.Zx}cm³ × {mat.fy_steel}kgf/cm² 
      = {steel.Zx * mat.fy_steel:,}kgf·cm = {Mns:.2f}tf·m
  
  φMns = 0.9 × {Mns:.2f} = {phi_Mns:.2f}tf·m

─────────────────────────────────────────────────────────────────────────────
2.2 RC部分 [a = As·fy / (0.85·fc'·b), Mnrc = As·fy·(d-a/2)]
─────────────────────────────────────────────────────────────────────────────
  a = {As} × {mat.fy_rebar} / (0.85 × {mat.fc} × {width})
    = {a:.4f}cm
  
  Mnrc = {As} × {mat.fy_rebar} × ({d_rc_cm:.1f} - {a:.4f}/2)
       = {Mnrc:.2f}tf·m
  
  φMnrc = 0.9 × {Mnrc:.2f} = {phi_Mnrc:.2f}tf·m

─────────────────────────────────────────────────────────────────────────────
2.3 疊加
─────────────────────────────────────────────────────────────────────────────
  φbMn = {phi_Mns:.2f} + {phi_Mnrc:.2f} = {phi_Mn_total:.2f}tf·m

─────────────────────────────────────────────────────────────────────────────
2.4 鋼筋比檢核 [ρmin = 1.4/fy]
─────────────────────────────────────────────────────────────────────────────
  ρ = As/(b×d) = {As}/({width}×{d_rc_cm:.1f}) = {rho:.4f}
  ρmin = 1.4/{mat.fy_rebar} = {1.4/mat.fy_rebar:.4f}
  結果：{'✓ 符合' if rho >= 1.4/mat.fy_rebar else '✗ 不足'}
""")
        
        # 三、檢核
        lines.append("三、彎矩檢核")
        lines.append("-" * 75)
        lines.append(f"""
  需要彎矩 Mu = {Mu:.2f}tf·m
  設計強度 φMn = {phi_Mn_total:.2f}tf·m
  結論：{'✓ 彎矩檢核通過' if phi_Mn_total >= Mu else '✗ 彎矩不足'}
""")
        
        # 四、剪力
        if Vu > 0:
            lines.append("四、剪力強度計算")
            lines.append("-" * 75)
            lines.append(f"""
【規範來源】{code.SRC_CH5} 5.5節
  鋼骨：Vns = 0.6×Fys×Aw
  RC：Vc = 0.17×√fc'×b×d

─────────────────────────────────────────────────────────────────────────────
4.1 鋼骨剪力 [Aw = tw×d]
─────────────────────────────────────────────────────────────────────────────
  Aw = {tw_cm:.2f} × {d_cm:.2f} = {Aw:.2f}cm²
  
  Vns = 0.6 × {mat.fy_steel} × {Aw:.2f}
      = {Vns:.2f}tf
  φVns = 0.75 × {Vns:.2f} = {phi_Vns:.2f}tf

─────────────────────────────────────────────────────────────────────────────
4.2 RC剪力
─────────────────────────────────────────────────────────────────────────────
  Vc = 0.17 × √{mat.fc} × {width} × {d_rc_cm:.1f}
      = {Vc:.2f}tf
  φVc = 0.75 × {Vc:.2f} = {phi_Vc:.2f}tf

─────────────────────────────────────────────────────────────────────────────
4.3 總計
─────────────────────────────────────────────────────────────────────────────
  φVn = {phi_Vns:.2f} + {phi_Vc:.2f} = {phi_Vn:.2f}tf
  需要 Vu = {Vu:.2f}tf
  結論：{'✓ 剪力檢核通過' if phi_Vn >= Vu else '✗ 剪力不足'}
""")
        
        # 五、結論
        lines.append(f"{'四' if Vu > 0 else '三'}、設計結論")
        lines.append("-" * 75)
        lines.append(f"""
  ┌─────────────────────────────────────────────────────────────────────────┐
  │  項目       │  需要值      │  設計強度   │  結果                       │
  ├─────────────────────────────────────────────────────────────────────────┤
  │  彎矩       │  {Mu:>6.2f}tf·m │  {phi_Mn_total:>7.2f}tf·m │  {'✓' if phi_Mn_total >= Mu else '✗'}                        │
  {"│  剪力       │  {Vu:>6.2f}tf   │  {phi_Vn:>7.2f}tf   │  {'✓' if phi_Vn >= Vu else '✗'}                        │" if Vu > 0 else ""}
  └─────────────────────────────────────────────────────────────────────────┘

═══════════════════════════════════════════════════════════════════════════════
備註：
1. 彎矩計算依據：{code.SRC_CH5} 5.4.1 節 (強度疊加法)
2. 剪力計算依據：{code.SRC_CH5} 5.5 節
3. 本計算僅供設計初稿參考，實際設計應經專業結構技師確認
═══════════════════════════════════════════════════════════════════════════════
""")
        
        return "\n".join(lines)
    
    def auto_select(self, Mu, width, height, cover, As, stype='H'):
        candidates = []
        for name, steel in STEEL_SECTIONS_DB.items():
            if stype.upper() in name.upper():
                r = self.calculate_moment(steel, width, height, cover, As)
                if r['phi_Mn_total'] >= Mu:
                    candidates.append({'name': name, 'phi_Mn': r['phi_Mn_total'], 
                                      'weight': steel.A, 'steel': steel})
        if candidates:
            candidates.sort(key=lambda x: x['weight'])
            return {'found': True, 'selected': candidates[0], 'candidates': candidates}
        return {'found': False}


# ============================================================================
# SRC 柱設計
# ============================================================================

class SRCColumnDesigner:
    def __init__(self, material=None):
        self.mat = material or MaterialProperties()
        
    def calculate_axial(self, steel, width, depth, cover, As):
        bf, d, tf, tw = steel.bf, steel.d, steel.tf, steel.tw
        Ac_inner = (bf - 2*tw) * (d - 2*tf) / 100
        Ac = width * depth - steel.A - Ac_inner
        Pn_rc = (0.85 * self.mat.fc * Ac + self.mat.fy_rebar * As) / 1000
        Pn_s = self.mat.fy_steel * steel.A / 1000
        phi_Pn = 0.75 * Pn_rc + 0.9 * Pn_s
        return {'phi_Pn': phi_Pn, 'Ac': Ac, 'Pn_rc': Pn_rc, 'Pn_s': Pn_s}
    
    def calculate_PM(self, steel, width, depth, cover, As, Pu, Mu):
        mat = self.mat
        EsIs = mat.Es * steel.Ix
        I_rc = width * (depth*10)**3 / 12 / 1e4
        EcIc = mat.Ec * I_rc
        
        ratio_s = EsIs / (EsIs + EcIc)
        ratio_rc = EcIc / (EsIs + EcIc)
        
        Pus = ratio_s * Pu
        Purc = ratio_rc * Pu
        Mus = ratio_s * Mu
        Murc = ratio_rc * Mu
        
        Pns = mat.fy_steel * steel.A / 1000
        Mns = mat.fy_steel * steel.Zx / 1e6
        
        if Pus > 0:
            ratio = Pus / (0.9 * Pns)
            check_s = ratio + Mus / (0.9 * Mns) if ratio >= 0.2 else Pus/(1.8*Pns) + Mus/(0.9*Mns)
        else:
            check_s = Mus / (0.9 * Mns)
        steel_safe = check_s <= 1.0
        
        d_rc = depth * 10 - cover * 10
        a = As * mat.fy_rebar / (0.85 * mat.fc * width * 10)
        
        bf, d, tf, tw = steel.bf, steel.d, steel.tf, steel.tw
        Ac_inner = (bf - 2*tw) * (d - 2*tf) / 100
        Ac = width * depth - steel.A - Ac_inner
        
        Pn_rc_val = (0.85 * mat.fc * Ac + mat.fy_rebar * As) / 1000
        Mn_rc = As * mat.fy_rebar * (d_rc - a*10/2) / 1e6
        
        if Purc > 0:
            ratio = Purc / (0.65 * Pn_rc_val)
            check_rc = ratio + Murc/(0.9*Mn_rc) if ratio >= 0.1 else Purc/(1.3*Pn_rc_val) + Murc/(0.9*Mn_rc)
        else:
            check_rc = Murc / (0.9 * Mn_rc)
        rc_safe = check_rc <= 1.0
        
        return {
            'ratio_s': ratio_s, 'ratio_rc': ratio_rc,
            'Pus': Pus, 'Purc': Purc, 'Mus': Mus, 'Murc': Murc,
            'check_s': check_s, 'steel_safe': steel_safe,
            'check_rc': check_rc, 'rc_safe': rc_safe,
            'is_safe': steel_safe and rc_safe,
            'Ac': Ac, 'Pns': Pns, 'Mns': Mns,
            'Pn_rc': Pn_rc_val, 'Mn_rc': Mn_rc
        }
    
    def generate_report(self, steel, width, depth, cover, As, Pu, Mu):
        """產生完整計算報告"""
        mat = self.mat
        code = DesignCodeRef()
        
        # 軸力
        bf, d, tf, tw = steel.bf, steel.d, steel.tf, steel.tw
        Ac_inner = (bf - 2*tw) * (d - 2*tf) / 100
        Ac = width * depth - steel.A - Ac_inner
        Pn_rc = (0.85 * mat.fc * Ac + mat.fy_rebar * As) / 1000
        Pn_s = mat.fy_steel * steel.A / 1000
        Pn_total = Pn_rc + Pn_s
        phi_Pn = 0.75 * Pn_rc + 0.9 * Pn_s
        
        # P-M
        result = self.calculate_PM(steel, width, depth, cover, As, Pu, Mu)
        
        lines = []
        lines.append("=" * 75)
        lines.append("         SRC 鋼骨鋼筋混凝土柱設計計算書")
        lines.append("=" * 75)
        lines.append(f"產生日期：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("")
        
        # 一、設計條件
        lines.append("一、設計條件")
        lines.append("-" * 75)
        lines.append(f"""
【材料】
  鋼骨 Fys={mat.fy_steel}kgf/cm², 鋼筋 Fy={mat.fy_rebar}kgf/cm², 混凝土 fc'={mat.fc}kgf/cm²

【鋼骨】{steel.name}
  bf={steel.bf}mm, tf={steel.tf}mm, tw={steel.tw}mm, d={steel.d}mm
  A={steel.A}cm², Ix={steel.Ix}cm⁴, Zx={steel.Zx}cm³

【混凝土】b={width}cm, h={depth}cm, 保護層={cover}cm
【鋼筋】As={As}cm²
【載重】Pu={Pu}tf, Mu={Mu}tf·m
""")
        
        # 二、軸力強度
        lines.append("二、軸力強度計算")
        lines.append("-" * 75)
        lines.append(f"""
【規範來源】{code.SRC_CH6} 6.4節
  公式：Pn = Pn_rc + Pns
        = 0.85×fc'×Ac + fy×As + fys×As

─────────────────────────────────────────────────────────────────────────────
2.1 混凝土淨面積
─────────────────────────────────────────────────────────────────────────────
  內部：({bf}-2×{tw})×({d}-2×{tf}) = {bf-2*tw}×{d-2*tf}mm = {Ac_inner:.2f}cm²
  
  Ac = {width}×{depth} - {steel.A} - {Ac_inner:.2f}
     = {Ac:.2f}cm²

─────────────────────────────────────────────────────────────────────────────
2.2 RC部分軸力
─────────────────────────────────────────────────────────────────────────────
  Pn_rc = 0.85×{mat.fc}×{Ac:.2f} + {mat.fy_rebar}×{As}
        = {Pn_rc:.2f}tf

─────────────────────────────────────────────────────────────────────────────
2.3 鋼骨部分軸力
─────────────────────────────────────────────────────────────────────────────
  Pns = {mat.fy_steel}×{steel.A} = {Pn_s:.2f}tf

─────────────────────────────────────────────────────────────────────────────
2.4 總軸力
─────────────────────────────────────────────────────────────────────────────
  Pn = {Pn_rc:.2f} + {Pn_s:.2f} = {Pn_total:.2f}tf
  φPn = 0.75×{Pn_rc:.2f} + 0.9×{Pn_s:.2f} = {phi_Pn:.2f}tf
""")
        
        # 三、P-M檢核
        lines.append("三、P-M 互制檢核 (相對剛度法)")
        lines.append("-" * 75)
        lines.append(f"""
【規範來源】{code.SRC_CH7} 7.3節
  依相對剛度分配軸力與彎矩，分別檢核鋼骨與RC部分

─────────────────────────────────────────────────────────────────────────────
3.1 剛度與分配
─────────────────────────────────────────────────────────────────────────────
  Es×Is = {mat.Es:.0f}×{steel.Ix:,} = {mat.Es*steel.Ix:,.0f}
  Ec×Ic = {mat.Ec:.0f}×{result['Ac']*depth**3*1000/12:,.0f}
  
  鋼骨分配：{result['ratio_s']:.1%} = {result['Pus']:.2f}tf, {result['Mus']:.2f}tf·m
  RC分配：  {result['ratio_rc']:.1%} = {result['Purc']:.2f}tf, {result['Murc']:.2f}tf·m

─────────────────────────────────────────────────────────────────────────────
3.2 鋼骨檢核
─────────────────────────────────────────────────────────────────────────────
  Pns={result['Pns']:.2f}tf, Mns={result['Mns']:.2f}tf·m
  檢核值 = {result['check_s']:.4f} {'≤1.0 ✓' if result['steel_safe'] else '>1.0 ✗'}

─────────────────────────────────────────────────────────────────────────────
3.3 RC檢核
─────────────────────────────────────────────────────────────────────────────
  Pn_rc={result['Pn_rc']:.2f}tf, Mn_rc={result['Mn_rc']:.2f}tf·m
  檢核值 = {result['check_rc']:.4f} {'≤1.0 ✓' if result['rc_safe'] else '>1.0 ✗'}
""")
        
        # 四、結論
        lines.append("四、檢核結論")
        lines.append("-" * 75)
        lines.append(f"""
  ┌─────────────────────────────────────────────────────────────────────────┐
  │  項目       │  檢核值      │  限值      │  結果                       │
  ├─────────────────────────────────────────────────────────────────────────┤
  │  鋼骨P-M    │  {result['check_s']:>8.4f}   │  ≤1.0     │  {'✓' if result['steel_safe'] else '✗'}                        │
  │  RCP-M      │  {result['check_rc']:>8.4f}   │  ≤1.0     │  {'✓' if result['rc_safe'] else '✗'}                        │
  └─────────────────────────────────────────────────────────────────────────┘

  軸力：Pu={Pu}tf ≤ φPn={phi_Pn:.1f}tf {'✓' if phi_Pn >= Pu else '✗'}
  
  結論：{'✓ 設計安全' if result['is_safe'] else '✗ 設計不安全'}

═══════════════════════════════════════════════════════════════════════════════
備註：
1. 軸力計算依據：{code.SRC_CH6} 6.4節
2. P-M檢核依據：{code.SRC_CH7} 7.3節 (相對剛度法)
3. 本計算僅供設計初稿參考，實際設計應經專業結構技師確認
═══════════════════════════════════════════════════════════════════════════════
""")
        
        return "\n".join(lines)


# ============================================================================
# 主程式
# ============================================================================

def main():
    print("=" * 60)
    print("  SRC 結構設計程式 v3.0")
    print("  - 完整計算過程")
    print("  - 設計規範來源")
    print("=" * 60)
    print("\n⚠️  本程式僅供設計初稿參考，實際設計應經專業結構技師確認。\n")
    
    beam = SRCBeamDesigner()
    column = SRCColumnDesigner()
    
    # ===== 梁設計範例 =====
    print("【SRC梁設計】")
    print("-" * 40)
    steel = STEEL_SECTIONS_DB['H400x200x8x13']
    result = beam.calculate_moment(steel, 40, 80, 5, 8.04)
    print(f"  斷面: {steel.name}, b=40cm, h=80cm, As=8.04cm²")
    print(f"  φMn = {result['phi_Mn_total']:.2f} tf-m")
    
    # 產生完整報告
    print("\n" + "="*60)
    print("【完整計算報告】")
    print("="*60)
    report = beam.generate_report(steel, 40, 80, 5, 8.04, Mu=15, Vu=10)
    print(report)
    
    # 自動選取
    print("\n【自動選取斷面】")
    auto = beam.auto_select(Mu=15, width=40, height=80, cover=5, As=8.04, stype='H')
    if auto['found']:
        print(f"  推薦: {auto['selected']['name']}")
        print(f"  φMn = {auto['selected']['phi_Mn']:.2f} tf-m")
        print("  候選:")
        for c in auto['candidates'][:5]:
            print(f"    {c['name']}: {c['phi_Mn']:.2f} tf-m, {c['weight']:.1f} kg/m")
    
    # ===== 柱設計範例 =====
    print("\n" + "="*60)
    print("【SRC柱設計】")
    print("-" * 40)
    steel_col = STEEL_SECTIONS_DB['BOX300x300x10x10']
    result_col = column.calculate_axial(steel_col, 50, 50, 4, 16.08)
    print(f"  斷面: {steel_col.name}, b=50cm, h=50cm, As=16.08cm²")
    print(f"  φPn = {result_col['phi_Pn']:.1f} tf")
    
    # 完整報告
    print("\n【完整計算報告】")
    report_col = column.generate_report(steel_col, 50, 50, 4, 16.08, Pu=80, Mu=15)
    print(report_col)
    
    print("\n" + "="*60)
    print("  程式結束")
    print("="*60)


if __name__ == "__main__":
    main()
