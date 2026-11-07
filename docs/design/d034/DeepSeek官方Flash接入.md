# D034 · DeepSeek 官方 Flash 接入

2026-10-19。用户明确改用 DeepSeek 官方 Flash，替代后续新设计的 GPT-6 High 连接。

## 实现

- 服务端配置 provider=deepseek，官方 https://api.deepseek.com，model=deepseek-flash，thinking.type=enabled，reasoning_effort=high。请求单次、不隐式重试、不降级 Pro。接口要求 JSON 输出，截断/缺少 stop/错误型号不接受。
- 模型目录真实 GET /models 返回 deepseek-flash 与 deepseek-v4-pro；选择 Flash。新提供方只允许官方 HTTPS 根路径或 /v1，拒绝相似域名、其他代理路径及 Pro。
- 密钥独立保存在本机被忽略的 var/secrets，文件0600；不写入代码、前端、模型输入、报告、知识库或本归档。原连接私下保留用于恢复，未停止共享模型网关。
- 请求发送 High，但官方响应没有回传 actual_thinking_effort。证据只证明官方 HTTPS 来源、返回型号和正常结束，不声称实际 High 强度得到独立验证。界面明确显示“High（请求设置）”。
- 通用自动验收、现有完整业务流程和 GMAH 展示统一复用按提供方核验与标签；历史 GPT 记录按自己的原连接显示。归档重新核对原始响应型号、摘要、终态、方案投影和连接一致性，未降低门禁。
- 原 GPT 请求9dd4798d-01c3-4c07-9b73-ba9f619efba0 已由精确网关终态502审计更新为 gateway_ended；没有把旧失败改成成功，也没有重新提交旧请求。

## 真实验证

- gojq 源码：5728e862130e428261a0b5780ae6b24e1d6f5f8d，仅使用其 README 独立示例。复用本地冻结目录识别，未再次拉取或更改源码/原测试/锁文件。
- 真实请求 bbaef0b3-24a0-4039-ac32-9184e80a691a；官方返回 model=deepseek-flash，finish_reason=stop，耗时17,038ms；接口未提供请求ID响应头，以本机请求ID与原响应摘要溯源。
- 方案 auto-92fa7a6f92d340a8：4条中文用例——读取字段、大整数精度、无效查询错误、无效JSON错误；引文经系统核对，输入和预期未按实际结果改写。
- 实际运行 int-59e1988852184a83：11/11检查已执行，9通过、2未通过；原生Go测试1,188/1,188通过，模型用例4/4通过。执行用时23.8秒，与模型设计17秒分别展示。所声明CLI范围完整性true，证据完整性true，门禁reject。扫描发现保留待复核；未为换模型放行。
- 源码快照未变化；旧 GPT 运行 int-60815c3a6f244972 的证据完整性仍true。真实新运行和源码、前端构建产物、D034文档中没有匹配到密钥。
- 93项后端定向测试通过：旧GPT型号/High约束、截断/错误模型、官方域名限制、无实际强度回传、自动方案冻结/篡改、完整工作流、GMAH回归。34项前端测试、TypeScript与生产构建通过。保留既有TestClient弃用警告。
- 浏览器核实模型阶段和4条中文用例均展示DeepSeek Flash；实际执行结果可追溯。截图为窄窗口真实页面。

## 范围

本批切换模型连接与核验，未实现23份文档自动拆批或全仓库需求覆盖。Go CLI验证不证明Headroom全业务已验收，也不证明所有新仓库均能零配置运行。质量reject与流程执行完整性分开保留。

官方依据：[首次调用API](https://api-docs.deepseek.com/zh-cn/)、[思考模式](https://api-docs.deepseek.com/zh-cn/guides/thinking_mode/)。
