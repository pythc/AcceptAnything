---
name: 验收工作台
description: 浅色、简约、单列的验收记录与证据工作台。
colors:
  cyan: '#5658c7'
  accent-soft: '#efeffa'
  red: '#b8373e'
  green: '#327358'
  amber: '#876223'
  danger-soft: '#fcf2f2'
  bg: '#ffffff'
  surface: '#f7f8fa'
  text: '#252830'
  muted: '#646b77'
  line: '#e6e8ed'
  nav-active: '#e9ebf0'
  action-ink: '#272a33'
  action-hover: '#3b3e47'
  idle: '#7d8490'
  border-hover: '#c9cdd6'
typography:
  title:
    fontFamily: -apple-system, BlinkMacSystemFont, "PingFang SC", "Microsoft YaHei", sans-serif
    fontSize: 32px
    fontWeight: 650
    lineHeight: 1.4
    letterSpacing: -0.025em
  headline:
    fontFamily: -apple-system, BlinkMacSystemFont, "PingFang SC", "Microsoft YaHei", sans-serif
    fontSize: 28px
    fontWeight: 600
    lineHeight: 1.45
    letterSpacing: -0.02em
  section:
    fontFamily: -apple-system, BlinkMacSystemFont, "PingFang SC", "Microsoft YaHei", sans-serif
    fontSize: 20px
    fontWeight: 600
  check:
    fontFamily: -apple-system, BlinkMacSystemFont, "PingFang SC", "Microsoft YaHei", sans-serif
    fontSize: 17px
    fontWeight: 550
    lineHeight: 1.6
  body:
    fontFamily: -apple-system, BlinkMacSystemFont, "PingFang SC", "Microsoft YaHei", sans-serif
    fontSize: 14px
    fontWeight: 400
    lineHeight: 1.7
  label:
    fontFamily: -apple-system, BlinkMacSystemFont, "PingFang SC", "Microsoft YaHei", sans-serif
    fontSize: 13px
    fontWeight: 400
  code:
    fontFamily: ui-monospace, SFMono-Regular, Menlo, monospace
    fontSize: 12px
rounded:
  small: 4px
  field: 5px
  control: 6px
  menu: 8px
  dialog: 10px
spacing:
  space-4: 4px
  space-8: 8px
  space-12: 12px
  space-16: 16px
  space-18: 18px
  space-20: 20px
  space-24: 24px
  space-28: 28px
  space-32: 32px
components:
  button-primary:
    backgroundColor: '{colors.action-ink}'
    textColor: '{colors.bg}'
    rounded: '{rounded.control}'
    padding: 8px 13px
  button-primary-hover:
    backgroundColor: '{colors.action-hover}'
  button-outline:
    backgroundColor: '{colors.bg}'
    textColor: '{colors.text}'
    rounded: '{rounded.control}'
    padding: 8px 13px
  button-outline-hover:
    backgroundColor: '{colors.surface}'
  button-quiet:
    backgroundColor: transparent
    textColor: '{colors.text}'
    rounded: '{rounded.control}'
    padding: 8px 13px
  button-text:
    backgroundColor: transparent
    textColor: '{colors.cyan}'
    padding: '0'
  input-search:
    backgroundColor: '{colors.bg}'
    textColor: '{colors.text}'
    rounded: '{rounded.control}'
    padding: 9px 12px
    typography: '{typography.label}'
  nav-item:
    textColor: '{colors.muted}'
    rounded: '{rounded.control}'
    padding: 10px 12px
  nav-item-active:
    backgroundColor: '{colors.nav-active}'
    textColor: '{colors.text}'
  tab:
    backgroundColor: transparent
    textColor: '{colors.muted}'
    padding: 14px 0
  tab-selected:
    textColor: '{colors.text}'
  priority-tag:
    backgroundColor: transparent
    textColor: '{colors.text}'
    rounded: '{rounded.small}'
    padding: 3px 6px
  live-status-panel:
    backgroundColor: '{colors.surface}'
    rounded: '{rounded.control}'
    padding: 12px 14px
    typography: '{typography.label}'
  pipeline-stage:
    backgroundColor: transparent
    textColor: '{colors.text}'
    rounded: '{rounded.field}'
    padding: 10px 6px
  pipeline-stage-selected:
    backgroundColor: '{colors.accent-soft}'
  check-row:
    backgroundColor: transparent
    textColor: '{colors.text}'
    padding: 17px 6px
    typography: '{typography.check}'
  pipeline-scroll-control:
    textColor: '{colors.text}'
    rounded: '{rounded.field}'
    width: 32px
    height: 32px
---

# Design System: 验收工作台

## Overview

**Creative North Star: "浅色简约单列工作台"**

以用户已选定的浅色简约单列工作台为方向：淡中性侧栏、白色阅读画布和深色文字构成基础，靛蓝只承担链接、选择与焦点反馈。视觉层级服务于核对事实和执行操作，保留清晰的仓库与版本上下文。

本文件从当前实现提取规范，核心页面为验收流程、缺陷详情、证据溯源。现有代码按 styles.css、console.css、redesign.css 的顺序加载，最后一层决定本轮浅色覆盖。用户已确认设计方向并授权实现；本文件不表示用户已验收最终实现，也不声明任何目标仓库、模型或生产环境已通过验证。

**Key Characteristics:**

- 淡中性侧栏与白色画布，深色正文，克制的靛蓝交互强调。
- 验收结论优先，完整流水线始终保持一行并允许横向滚动。
- 需要处理的检查优先阅读，详情行内展开，已通过项折叠保留。
- 缺陷与证据采用单列阅读，次要列表、技术信息与复核操作按需展开。
- 短促状态反馈与展开动效，响应减少动态效果偏好。

## Colors

### Primary

`cyan` 保留源码已有名称，实际是克制的靛蓝，用于链接、选中标签下划线、运行中状态与焦点；`accent-soft` 用于已选流水线阶段和列表项的浅底。不要根据历史变量名恢复青色。

红、绿与赭色是语义反馈色：`red` 表达失败、执行异常及受阻状态，`green` 表达通过，`amber` 表达无法下结论；`danger-soft` 为错误信息提供浅底。它们不是装饰性品牌配色。

### Neutral

`bg` 是白色主画布，`surface` 是淡中性侧栏、次级内容和代码背景，`text` 承担主要阅读，`muted` 承担次级说明，`line` 用作细分隔。`nav-active` 区分侧栏活动项；`action-ink` 与 `action-hover` 用于深色主要操作，`idle` 用于等待或未执行图标，`border-hover` 用于描边按钮悬停。

**The Semantic Status Rule.** 状态颜色必须与图标及文字同时表达结果；失败、执行异常、未完成与未执行保持各自的实际含义。

## Typography

**Body Font:** 使用 frontmatter 中的系统字体栈，优先当前平台字体与中文系统字体，不依赖远程字体加载。**Label/Mono Font:** 原件、路径片段与代码采用 `code` 字体栈；时长使用等宽数字，流水线时长回到界面字体。

### Hierarchy

- `title`：仓库名称；宽度收窄时逐步缩小。
- `headline`：验收结论。
- `section`：当前检查分组。
- `check`：可展开的检查名称。
- `body`：常规说明段落；重点预期与实际使用更宽松的阅读行距。
- `label`：控件与次级信息；更细的路径、编号、辅助说明保持较小字号。
- `code`：原始片段与技术标识，不代替中文检查名。

结论说明的最大阅读长度为 78ch，检查事实为 82ch，缺陷摘要为 85ch。长标识允许在需要时断行，原始代码保留自己的滚动区域。

**The Readable Hierarchy Rule.** 让仓库、验收结论和检查名称形成递进层级；技术标识与采集元数据使用较小的次级文字，不放大为装饰标题。

## Layout

桌面主框架采用固定左导航与右侧工作区，默认导航宽度为 232px、页面水平留白为 32px。仓库面包屑、仓库与版本信息、三个主标签在核心页面保持一致。三个主标签的实际名称为“验收流程”“缺陷详情”“证据溯源”。验收页先给结论，再给完整流水线和需要处理的检查；缺陷与证据为单列内容，选择器展开后位于正文上方。

流水线采用按列自动排列的网格，阶段最小宽度为 168px，阶段间隔为 18px；横向溢出保留滚动条，并显示真实阶段数与前后滚动按钮。检查行在桌面保留名称、状态、耗时与展开指示；手机将耗时下移，事实标签收窄，操作允许换行。

| 最大视口宽度 | 已实现的适配 |
| --- | --- |
| 1100px | 导航缩至 184px，水平留白缩至 26px，仓库标题缩小。 |
| 800px | 导航缩至 60px 图标轨，水平留白为 22px；目录页面改为上下排列。 |
| 560px | 导航进入顶部横排，工作区占满宽度，水平留白为 18px；主标签仍可横向滚动。 |

页面最低宽度为 320px。流水线在手机上固定每阶段 168px，继续单行滚动；小于等于 700px 时，选择阶段后可滚到对应详情。以上断点说明当前工作台实现，不要求其他功能页面无条件复用同一版式。

**The Continuous Pipeline Rule.** 核心验收流水线在所有宽度下保持单行；用滚动与溢出按钮访问其余阶段，不删阶段、不换行。

## Elevation & Depth

阅读主体以平面为主，通过底色、留白和细分隔线区分内容。侧栏、流水线和检查行没有常驻卡片投影。悬浮菜单、原生对话框和 toast 分别使用现有阴影；仓库来源切换中被选项保留微弱阴影。精确阴影值记录在设计侧车中，避免将悬浮效果扩散到普通阅读内容。

**The Flat Reading Rule.** 常驻阅读内容使用白底、浅底和细分隔线建立层级；悬浮菜单、弹窗与提示使用各自的阴影，仓库来源切换的选中项保留现有微弱阴影。

## Shapes

使用小幅圆角和细边线。frontmatter 的 `small` 用于优先级标签与小型列表项，`field` 用于阶段、字段与滚动控制，`control` 用于按钮和导航，`menu` 用于浮出菜单，`dialog` 用于对话框。检查分隔线保持直线；状态图标的圆形来自语义图标，不扩展成装饰性大圆圈。

## Components

### Buttons

主要操作采用深色底与白字；次要操作采用白底细描边；轻量操作保留无底文字。工作台按钮最小高度为 40px，文本操作使用靛蓝。主要与描边按钮具有各自的悬停色，并继承当前亮度反馈；禁用状态降低透明度并停止接收指针操作。键盘焦点使用 2px 靛蓝外框，实际偏移由对应控件样式决定。

### Chips

优先级标签采用小圆角、细边框和紧凑文字；P0/P1 使用语义红。建议优先级必须保留“建议”提示；没有依据时保留“待分级”，不能靠颜色暗示已完成复核。

### Cards / Containers

主体使用无卡片包裹的阅读区域。现有运行状态面板以浅底、细边框和控件圆角区分临时状态；代码片段、展开的完成信息使用浅底。常驻内容不沿用弹窗阴影。

### Inputs / Fields

字段采用白底、细中性边线和小圆角，搜索框以包裹容器承载边框；搜索聚焦时边线变靛蓝，外围出现浅靛蓝提示。常规表单与搜索使用各自现有内边距，长文本字段允许纵向调整。复用浏览器原生输入语义，不用静态文字模拟可输入控件。

### Navigation

左侧导航使用浅中性底，活动项提高字重并加中性底色。三个主标签以靛蓝细下划线标记当前页，支持键盘左右方向键切换。窄屏导航隐藏文字时保留图标和可访问名称；移动端改为顶部横排。

### Pipeline and checks

阶段按钮保留名称、真实状态与时长，选中阶段使用浅靛蓝底。溢出按钮只在存在可滚动内容时出现，边界方向禁用。检查由整行按钮控制展开，`aria-expanded` 与关联区域同步；预期、实际、原始证据和独立标准在行内阅读。已通过检查放入默认折叠的完成组，仍可展开核对。

缺陷列表和证据目录默认收起，打开后呈现于单列正文上方。哈希、内部编号、采集元数据和复核编辑维持各自的按需展开入口；必要的证据说明仍应先于原始文件阅读。

交互颜色反馈使用 160ms；检查详情、选择器和对话框出现使用 200ms。展开指示旋转与内容淡入使用现有缓出曲线。加载占位的透明度循环为 1.4s，仅服务真实加载状态；原有运行图标保留状态旋转。减少动态效果模式将动画与过渡缩至 0.01ms、循环次数设为 1，并禁用平滑滚动；阶段切换与流水线滚动也读取同一偏好。

**The Traceable Disclosure Rule.** 折叠只改变默认可见内容；冻结预期、实际结果、已通过检查和原件入口继续可达。

## Do's and Don'ts

### Do:

- Do 使用现有语义颜色、系统中文字体和紧凑控件。
- Do 在三个主标签中保持相同的仓库上下文、标签位置和阅读起点。
- Do 让检查整行响应展开，同时保留独立的原件与标准操作。
- Do 为窄屏、长名称、路径和实际结果保留换行或局部滚动。
- Do 为交互提供可见焦点、状态文字与减少动态效果支持。

### Don't:

- Don't 用生成图中的数量、时长、人员或示例响应替换真实记录。
- Don't 把执行结束、单阶段完成或扫描结束显示为完整验收通过。
- Don't 为简洁隐藏必要的仓库、版本、范围、未完成项或原件入口。
- Don't 恢复已被本轮方向替代的深色主工作台与常驻左右详情分栏。
- Don't 加入粒子、装饰性动画、夸张字号或解释设计理念的产品文案。
