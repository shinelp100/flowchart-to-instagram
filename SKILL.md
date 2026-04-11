---
name: flowchart-to-instagram
description: 将 Mermaid flowchart TD 或层级内容转换为 Instagram 风格信息图，适合微信公众号投放。解析结构而非简单渲染，设计层级递进的视觉卡片。
tags: [flowchart, instagram, wechat, 公众号, 信息图, infographic, 题材调研员]
global: true
---

# flowchart-to-instagram

将 Mermaid flowchart TD 或层级内容转换为 Instagram 风格信息图，适合微信公众号投放。

## 核心功能

- **解析而非渲染**：提取内容结构和层级关系
- **Instagram 风格设计**：渐变背景、毛玻璃卡片、柔和配色
- **层级递进布局**：根据分组智能排版
- **品牌水印**：2×2 网格，透明度 6%，旋转 -20°

## 设计规范（v1.0 最终版）

### 背景渐变
```css
background: linear-gradient(135deg, 
  #833ab4 0%, 
  #fd1d1d 50%, 
  #fcb045 100%
);
```
紫 → 红 → 橧，Instagram 经典配色。

### 水印样式
- 2×2 网格布局（4个水印）
- 字体大小：180px
- 透明度：6%
- 旋转：-20°
- 颜色：rgba(255, 255, 255, 0.06)

### 卡片样式
- 半透明毛玻璃效果
- 渐变方向与背景一致（135deg）
- 不同区块有微色调呼应背景：
  - 上游：粉紫色调
  - 中游：红粉色调
  - 下游：橙红色调
  - 出海/政策：橙黄色调

### 字体规范
- **大标题**：20px，font-weight: 700，#1a1a1a
- **节点标题**：19px，font-weight: 600，#1a1a1a
- **描述文字**：15px，font-weight: 400，#3a3a3a

### 布局规范
- 最大宽度：800px
- 卡片内边距：p-6（24px）
- 节点内边距：p-5（20px）或 p-4（16px）
- 卡片间距：gap-5（20px）

### 节点配色（柔和渐变）
```
node-1: #fef7f7 → #fce8e8（粉红）
node-2: #fef9f3 → #fde9d9（橙粉）
node-3: #fef8f0 → #fde5cc（橙黄）
node-4: #f4fef7 → #dcf8e3（绿）
node-5: #f3f7fe → #dce5f8（蓝）
node-6: #f8f5fe → #e8dcf8（紫）
```

### 卡片底色（与背景呼应）
```css
/* 上游 - 粉紫色调 */
.card-1: rgba(255,240,250,0.9) → rgba(255,245,255,0.92) → rgba(255,250,245,0.9)

/* 中游 - 红粉色调 */
.card-2: rgba(255,235,245,0.9) → rgba(255,240,250,0.92) → rgba(255,245,240,0.9)

/* 下游 - 橙红色调 */
.card-3: rgba(255,230,240,0.9) → rgba(255,235,245,0.92) → rgba(255,240,235,0.9)

/* 出海/政策 - 橙黄色调 */
.card-4: rgba(255,235,235,0.9) → rgba(255,230,240,0.92) → rgba(255,240,230,0.9)
```

## 使用方法

### 方法一：修改模板文件

1. 编辑 `templates/instagram-card.html`
2. 修改内容区块（标题、节点）
3. 用浏览器打开，截图导出

### 方法二：自动化脚本（待开发）

```bash
python scripts/generate.py --input data/flowchart.json --output output/card.png
```

## 文件结构

```
~/.hermes/skills/flowchart-to-instagram/
├── SKILL.md                    # 本文档
├── templates/
│   └── instagram-card.html     # HTML 模板（v1.0 最终版）
└── scripts/
    └── generate.py             # 自动化脚本（待开发）
```

## 迭代记录

### v1.0 (2026-04-11)
- Instagram 风格渐变背景（紫→红→橙）
- 2×2 水印布局，180px 字体
- 半透明毛玻璃卡片，底色与背景呼应
- 柔和节点渐变色（6种配色方案）
- 字体规范确立（标题20px、节点19px、描述15px）
- 移除所有 icon，纯文字设计

## GitHub 管理

建议将此 skill 复制到独立 Git 仓库迭代：

```bash
# 创建仓库
mkdir flowchart-to-instagram && cd flowchart-to-instagram
git init

# 复制 skill 文件
cp -r ~/.hermes/skills/flowchart-to-instagram/* .

# 推送到 GitHub
git add .
git commit -m "v1.0: Instagram-style flowchart card generator"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/flowchart-to-instagram.git
git push -u origin main
```

## 待开发功能

- [ ] 自动解析 Mermaid flowchart TD 语法
- [ ] 自动解析 Markdown 层级结构
- [ ] 一键生成 PNG（Puppeteer/Playwright）
- [ ] 支持自定义品牌水印文字
- [ ] 支持多主题切换（小红书、商务简报等）
- [ ] CLI 命令行工具