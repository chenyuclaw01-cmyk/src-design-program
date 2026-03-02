# SRC 鋼骨鋼筋混凝土結構設計程式

![Python](https://img.shields.io/badge/Python-3.10+-blue)
![License](https://img.shields.io/badge/License-MIT-green)

## 程式簡介

SRC (Steel Reinforced Concrete) 鋼骨鋼筋混凝土結構設計程式，依據台灣「鋼骨鋼筋混凝土構造設計規範與解說」進行設計計算。

## 功能特色

- ✅ SRC 梁設計 (強度疊加法)
- ✅ SRC 柱設計 (相對剛度法)  
- ✅ 完整計算報告輸出
- ✅ 設計規範來源標示
- ✅ 自動斷面選取
- ✅ 自訂斷面輸入
- ✅ Web UI 介面 (Streamlit)

## 設計依據

- 鋼骨鋼筋混凝土構造設計規範與解說
- 建築物混凝土結構設計規範 (112年版)
- 鋼結構極限設計法規範及解說

## 版本說明

| 版本 | 說明 |
|------|------|
| v1.0 | 基本設計功能 |
| v2.0 | 自動斷面選取、自訂斷面 |
| v3.0 | 完整計算報告、規範來源 |

## 安裝方式

```bash
# 複製專案
git clone https://github.com/chenyuclaw01-cmyk/src-design.git
cd src-design

# 安裝依賴 (Web UI 需要)
pip install streamlit
```

## 使用方式

### 命令列版本

```bash
# v3.0 完整版 (推薦)
python3 src_design_v3.py

# v2.0 版
python3 src_design_v2.py

# v1.0 版
python3 src_design.py
```

### Web UI 版本

```bash
streamlit run src_design_web.py
```

## 計算方法

### 梁 - 強度疊加法

$$\phi_b M_n = \phi_{bs} M_{ns} + \phi_{brc} M_{nrc}$$

- $M_{ns} = Z \times F_{ys}$ (鋼骨塑性彎矩)
- $M_{nrc} = A_s \times f_y \times (d - a/2)$ (RC彎矩)
- $\phi_{bs} = \phi_{brc} = 0.9$

### 柱 - 相對剛度法

1. 依相對剛度比例分配軸力與彎矩
2. 分別檢核鋼骨與 RC 部分
3. 使用 P-M 互制公式

## 預設材料

| 材料 | 規格 |
|------|------|
| 鋼骨 | SN280 (Fys = 2800 kgf/cm²) |
| 鋼筋 | SD420 (Fy = 4200 kgf/cm²) |
| 混凝土 | f'c = 280 kgf/cm² |

## 內建鋼骨資料庫

### H 型鋼
- H300x150x6.5x9 ~ H600x200x11x17

### 箱型鋼
- BOX200x200x9x9 ~ BOX500x500x16x16

## 輸出範例

```
===========================================================================
         SRC 鋼骨鋼筋混凝土結構設計計算書
===========================================================================

一、设计条件
【材料】
  鋼骨 Fys = 2800 kgf/cm²
  鋼筋 Fy  = 4200 kgf/cm²
  混凝土 fc'= 280 kgf/cm²

二、彎矩強度計算 (強度疊加法)
【規範來源】鋼骨鋼筋混凝土構造設計規範與解說 第五章 5.4.1 節
  公式：φbMn = φbsMns + φbrcMnrc

  φbMn = 23.94 tf-m
```

## ⚠️ 重要提醒

本程式僅供設計初稿參考，實際設計應經專業結構技師確認並符合最新法規規定。

## 授權

MIT License

## 作者

工程蝦一號 (AI 工程助手)
