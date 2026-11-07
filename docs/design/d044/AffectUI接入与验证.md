# D044 Affect UI 执行详情接入

2026 年 11 月 5 日。

## 选型

Tool Call Card 适合一次实际命令的输入、执行状态、耗时和返回值。官方页面明确提供 MIT 版本，registry 源码没有额外运行依赖，当前 React 19 工程可以直接使用。Trace Waterfall 为 Pro 组件，本轮未接入。

来源 https://www.affectui.com/components/tool-call-card
注册表 https://www.affectui.com/r/tool-call-card.json

## 实现

ConsoleFlow 的检查详情中，执行详情与溯源内的命令列表使用上游组件。输入读取 commands.argv，输出显示真实 exit_code 和 evidence_ref；结束耗时由采集的开始、结束时间计算。标题、复制、展开和状态播报使用中文。样式继承现有浅色单列工作台。

命令结束时间缺失或退出码未知，显示“状态未确认”。仅当运行与当前检查同时处于执行中，才显示持续计时。非零退出码直接呈现数字，由原始报告解释是扫描命中还是执行错误。验收结果及门禁继续由现有结果契约决定。

保留原始证据、独立标准、缺陷详情、全文观察和报告校验入口。未增加单工具重试按钮，因为当前完整验收流程没有与该按钮匹配的独立重试接口。

## 验证

TypeScript 类型检查、生产构建与 4 项 Sites 包装测试通过。Python Playwright 使用真实 sqlite-utils 记录 int-fe2b255558a6465f，核对命令、复制、键盘展开和不同检查选择，390 与 768 像素宽度无页面横向溢出。另在浏览器响应副本移除结束时间和退出码，确认显示未知，未修改服务器历史记录。浏览器无页面脚本异常。

本轮复用了历史数据检查前端显示，未发起新的模型或目标仓库验收。样式检测器的上游字体和圆角建议由工作台作用域样式覆盖。

改动文件为 web/src/components/affect/ToolCallCard.tsx、web/src/ConsoleFlow.tsx、web/src/redesign.css、web/THIRD_PARTY_NOTICES.md。上游摘要见 affect-source.json，浏览器检查见 browser-results.json。许可证声明随源码保留。
