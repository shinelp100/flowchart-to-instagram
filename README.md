# Flowchart to Instagram Card

将 Mermaid flowchart TD 或层级内容转换为 Instagram 风格信息图，适合微信公众号投放。

## 特性

- Instagram 经典渐变背景（紫→红→橙）
- 2×2 品牌水印布局
- 半透明毛玻璃卡片
- 柔和节点渐变色
- 纯文字设计，无 icon

## 使用方法

### 快速使用

1. 编辑 `templates/instagram-card.html`
2. 修改区块标题和节点内容
3. 浏览器打开，截图导出 PNG

### 设计规范

详见 `SKILL.md` 文档。

## 文件结构

```
flowchart-to-instagram/
├── README.md               # 项目说明
├── SKILL.md                # 设计规范文档
├── templates/
│   └── instagram-card.html # HTML 模板
└── scripts/                # 自动化脚本（待开发）
```

## 版本历史

### v1.0 (2026-04-11)
- 初始版本
- Instagram 风格渐变背景
- 2×2 水印布局
- 半透明毛玻璃卡片

## License

MIT