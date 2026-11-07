# 当前设计 QA

0.8 上传阅读、结果确认与页边批注 QA：`../docs/数学论文评审-0.8设计QA.md`。本轮观察通过，验证边界见该文档；以下内容为历史记录。

# M0 设计对照验收

0.7 最新设计 QA 见 ../docs/数学论文评审-0.7设计QA.md；以下保留 M0 历史，不代表当前缺口。

0.4.0 最新 QA 见 `../docs/数学论文评审-0.4设计QA.md`，范围与义务的实际页面证据随 M3 归档。以下保留历史。

本页保留 M0 历史。0.2.0 的结论优先布局、实际任务和窄屏 QA 另记于知识库“0.2 设计 QA”，并与 M1 用户模拟和原始截图一起归档。

0.3.0 当前 QA 见 `../docs/数学论文评审-0.3设计QA.md` 与 `evidence/m2-user-simulation.md`。以下 M0 导入/选区缺口已有新的局部验收证据，历史记录不追改；跨行选择及复杂 PDF 仍需检查。

final result: passed

passed 只指本轮视觉及已观测交互，不代表整个 M0 功能验收通过；导入测试缺口见 REVIEW.md。

## 基线与证据

- source visual truth：../design/math-review/03-margin-review.png，1487×1058。
- implementation：evidence/workbench-final.png，1440×1024；http://127.0.0.1:4178/。
- viewport：1440×1024 CSS px，DPR=1。设计稿等比缩至 1440 宽约 1024 高，实现 1:1 截图；在同一组合图中并排比较。
- state：第 3 页、125%、F-01 展开、浅色。实现为真实教学 PDF，保留一条浏览器自测人工批注；纸面文字及列表内容与生成稿存在明确差别。
- 全图：evidence/design-comparison-final.png；局部：evidence/design-detail-final.png，聚焦右栏字号、协作与依据。
- 其他：evidence/evidence-trace-final.png、evidence/manual-note-restored.png、evidence/workbench-mobile.png。窄屏视口 390×844，截图为完整页面，非单屏。

## 迭代

1. 初始 evidence/design-comparison-initial.png：次级字号与角色图标偏小，P2。调整右栏 490px、展开标题 20px、正文 14px、角色图标 46px，并配置断点。
2. 窄屏发现图标按钮名称随标签隐藏、论据两行截断，P2。补充 aria-label/aria-pressed，移除选中论据截断。
3. 修复后重拍桌面、窄屏、全图与局部并排对照。先前 P2 已处理，无仍需阻断预览的视觉 P0/P1/P2。

## 五项保真检查

| 项目 | 结果 |
| --- | --- |
| 字体 | Georgia 品牌/论文衬线与 Noto Sans SC/系统中文 UI，层级接近稿件；次级字号略小为 P3。PDF 字体由真实文档决定。 |
| 间距布局 | 窄导航、原文、约 34% 页边区及状态条保持结构。自测批注影响列表位置，属于真实内容差异。 |
| 色彩 | 酒红 #873749、暖白、粉/砂/蓝/橄榄角色色；没有用通过色暗示未运行检查。 |
| 图像 | 真实 PDF Canvas 按 DPR 渲染，文本层可选；Phosphor 标准图标。没有把设计图整张铺作页面，没有需还原的装饰插图。 |
| 文案 | 原文—协作—依据层级保留。教学演示与未运行标记明确，数学正文使用可核查原创反例，替换生成图中的不可靠公式排版。 |

## 交互与余项

实际检查：PDF、翻页、重开、搜索、原文定位、产物、证据、框选、保存恢复、筛选和 JSON 下载。生命周期修复后观察未见新 error/warn。导入自动化障碍另记，不能推断通过。

P3：次级浅色文字对比与角色字号可继续打磨。小屏 PDF 目前横向滚动，适宽模式留后续。

## Implementation Checklist

- [x] 查看同一输入中的全图及局部比较。
- [x] 检查五项保真面；修复 P2 后重拍。
- [x] 桌面/窄屏结构及演示状态清晰。
- [ ] 功能余项：另一 PDF 导入、文本选区新增完整端到端。
