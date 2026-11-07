# 验收 Agent

Agent 工具入口：[MCP 接入、12 项工具及状态语义](docs/Agent工具接入.md)。使用官方 SDK 的本机 stdio 连接，默认只读，写操作采用持久请求回执；结果与验证见 D045。

当前实施记录：[D043 · 结果契约、反例、历史索引与任务恢复](docs/design/d043/平台可信基础实现与验证.md)。本地/远程通用入口、模型提供方和能力边界以最新文档为准；下文 D001–D031 等章节是历史增量记录，旧文件数/体积上限已取消。项目尚未完成成熟开源发布认证。

主文档：[开源调研、验证与框架设计](/Users/alex/Documents/ChatGPT/竞赛/docs/验收Agent-调研与框架设计.md)。

范围：基于成熟组件做验收集成、独立标准管理、证据归纳和溯源。已实现第一版本地闭环，包含 React 三 Tab 工作台、FastAPI、Playwright/axe/Bandit 执行、OPA 门禁、证据校验、历史和报告下载。已支持任意本地仓库按确认的检查计划接入；业务用例仍需项目标准和环境。现已支持独立需求/契约→结构化测试方案→新用例生成→隔离执行→证据与门禁；已配置本地GPT-6 Thinking High模型接口；真实验证结果见D021记录。WorkSwarm与生产部署尚未实现。

当前远程入口（D031）：本地路径或 github.com/gitlab.com HTTPS 仓库，支持分支/完整提交，固定源码后进入既有完整验收；业务覆盖仍需独立标准与配方。GMAH分支和指定提交均已实跑，质量结论仍reject。详见 https://knowledge.110-lab.cn/p/8VoWbrazCB 。

正式文档空间：[项目文档](https://knowledge.110-lab.cn/p/m4OHJGqujs)。

## 本地运行

环境：Python 3.12、Node 24+、Docker。依赖锁文件为 requirements.lock.txt、web/package-lock.json 与 validation 的现有锁文件。安装：

```sh
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -r requirements.lock.txt
npm ci --prefix web
```

准备本地执行器（不需要下载六个上游 Agent 仓库，不需要模型密钥）。以下 npm/node 命令使用 Node 24+：

```sh
uv venv --python 3.12 validation/.venv
uv pip install --python validation/.venv/bin/python -r validation/requirements.lock.txt
npm ci --ignore-scripts --prefix validation
node validation/node_modules/playwright/cli.js install chromium
docker pull openpolicyagent/opa@sha256:35615020f7224b7da7ccfe76dc3cb93bc43aab8a3b42099f32edc42cdbca27bf
```

然后启动：

```sh
.venv/bin/python scripts/start.py --seed
```

服务只监听回环地址，默认端口 18890。可用 ACCEPTANCE_NODE 指定 Node 24+ 二进制。只有空数据目录才创建缺陷/修正两次真实执行；后续从页面“重新验证”创建新记录。var/ 保存运行产物，不覆盖 research/evidence/。

```sh
.venv/bin/python -m pytest tests -q
cd web
npx tsc --noEmit
npm run build
```

本地夹具基线：8 项必验；缺陷版 7 条发现，修正版 8 项通过。性能/恢复未执行，“所选基线通过”仅限这一范围。证据摘要校验没有可信签名，不构成完整来源认证。

复现入口：[验证说明](/Users/alex/Documents/ChatGPT/竞赛/validation/README.md)。

D004 的交付复核与用户模拟见 docs/verification/交付复核与用户模拟.md；该批交付包为 v0.3（当前为 D008/v0.6.0），保留较早版本作历史资料。v0.3 补齐前端构建必需的 web/.openai/hosting.json，并提供当前组件夹具、固定用例和锁文件；依赖、模型密钥和其他项目不随包分发。

## D008 · 当前版本 0.6.0

支持本地夹具与已登记 Node 项目；首个真实对象为 110lab-assessment 的 20 个业务规则测试。标准/输入按执行冻结，统一核验原始报告后由 OPA 判定。详见 docs/verification/判定内核与真实项目接入.md。

登记：`.venv/bin/python scripts/project.py register projects/assessment-core.json`；运行：`.venv/bin/python scripts/project.py run assessment-core`。新项目配置需显式选择文件、标准与测试名称；项目在无外网、只读受限容器执行，要求本机已有固定 Node 镜像。当前不是通用构建/服务平台，也未完成全项目安全/性能/恢复验收。


## D009 · 扩展验证

对首个真实对象进一步补验：152 项测试中 149 通过、2 失败、1 跳过；三部分构建、6 项浏览器操作和 35 表逻辑恢复检查完成。总体尚未通过完整验收，依赖告警与未覆盖项保留。详情见 [扩展验证与遗漏复盘](/Users/alex/Documents/ChatGPT/竞赛/docs/verification/真实项目扩展验证与遗漏复盘.md)。本轮是验证与文档更新，产品仍为 0.6.0；这些扩展检查尚未自动接入工作台，原 20 项历史执行保持原范围。

## 0.7.0 · 分层验收接入

新增 `assessment-expanded-v1` 项目配置：从工作台自动运行构建、现有回归、数据库/接口、浏览器、依赖与密钥扫描和逻辑恢复。未覆盖必验项显式阻断放行。真实执行 `run-349355b487aa` 为 7 项通过、3 项失败、6 项未完成；不是全项目验收通过。详见 [集成与复验说明](docs/verification/分层自动验收集成与复验.md)。

## D011 · 本地可执行检查全部接入

用户授权排除真实外部服务、原生 Windows 和缺少真实环境的生产指标；排除范围单独冻结，不算用例。本次新增 Semgrep/njsscan、Bandit、ZAP、k6、候选人完整流程及数据库与文件联合恢复。17 项检查全部执行：11 通过、6 失败、0 未完成，最终 reject；失败与扫描命中保留待复核。实际执行 run-bfaaba5641dc，产品 0.8.0。详情：[本地完整验收与排除范围](docs/verification/本地完整验收与排除范围.md)。

## 0.9.0 · 广度接入与统一门禁

新增24个固定执行配方、33种报告/平台契约、DefectDojo与ReportPortal真实API桥、六类OPA门禁及接入工作台。校准与成熟项目实跑保留全部原件。执行完成不等于验收通过；商业/设备/云/AI能力未冒充已完成。

[实现与验证](docs/architecture/广度接入实现-D014.md) · [接入与复跑](integrations/README.md)。入口：`http://127.0.0.1:18890/?view=integrations`。


## D019 · 实时检查与本地仓库入口

从工作台“新建验收 → 验收其他本地仓库”填写绝对路径，识别文件/技术栈，检查门禁与排除范围，再按计划启动。可以选择访问公共漏洞库和运行已识别的现有测试；不自动安装项目依赖。代码、范围或执行器改变后需重新识别。单次5000文件/128MiB，较大仓库可选子目录。

运行中的检查、阶段、耗时和结果分别呈现；原“用例准备”改称“用例登记”，核对已有标准和用例并产生可查看的登记清单。登记本身不表示测试执行或通过。新仓库与历史纳入主目录。

当前验证：250项后端、17项前端、TypeScript与构建通过；真实项目17项完整执行，另以通用入口完成7项扫描，原始报告与门禁均有效。目标项目仍有失败检查，门禁拒绝放行。详见[本批技术与验证](docs/design/d019/实现与验证.md)及[设计验收](design-qa.md)。

## D020 · 独立设计并生成验收用例

入口：“新建验收 → 设计验收用例”。选择本地仓库，读取需求/契约或补充业务规则；导入或编辑结构化测试方案，再查看生成的标准覆盖、用例输入/预期、测试代码、检查与排除范围。确认后冻结执行，结果页“方案与用例”可追到依据和步骤证据。仓库原测试文件不会被复制成新用例。

支持数据表、矩阵、数值边界展开，使用 pytest、Playwright、Schemathesis；扫描器仍可同时运行。模块函数支持 Node/TypeScript 与 Python；服务入口必须能在现有固定镜像中直接启动，复杂依赖与服务编排需另做适配，不执行任意宿主脚本。性能/恢复不由普通请求冒充，仍使用既有执行配方；真实邮箱等明确排除且不计入用例。

没有模型密钥也可使用结构化方案。可选自然语言规划器使用 OpenAI 兼容接口，在服务环境设置 `ACCEPTANCE_PLANNER_BASE_URL`、`ACCEPTANCE_PLANNER_MODEL`，需要密钥时设置 `ACCEPTANCE_PLANNER_KEY_FILE` 指向本机密钥文件，再启动服务。密钥不放入前端或方案；不要在聊天中发送密钥。模型只生成待核对草稿，预期引用必须匹配独立原文，模型未知信息标为待确认并阻断执行。模型草稿的语义仍需人工核对。

验证：292项后端、19项前端及类型/构建通过；成熟考核项目39个新增业务规则用例全通过，6项扫描完成且仍有38条发现，整体门禁reject。校准服务5个用例通过，故意出错版检出3类违反契约的问题。详见[本批实现与验证](docs/design/d020/实现与验证.md)。

## D021 · 接入 GPT-6 Thinking High

模型连接已持久保存到被忽略的本机配置，页面显示“GPT-6 Thinking · High”。请求明确使用gpt-6-thinking/high，响应需通过实际型号、extended强度、完整结束及业务Schema校验。配置不接受Pro/auto或其他强度；不自动重试或切换模型。密钥直接读取既有本机网关配置，未写入前端或文档。详见[接入与真实验证](docs/design/d021/接入与验证.md)。

本次真实方案联调在600.162秒读取超时，尚无网关终态，未取得最终方案。当前保留未知请求阻断，需核对终态后继续；配置完成不代表模型联调通过。

## D022 · 统一完整验收

统一“新建验收”入口与三Tab详情。完整流程编排需求/模型设计、新生成测试、扫描、构建回归、数据库/API、浏览器业务、k6 和数据库/文件联合恢复；子任务绑定冻结源码与原始收据。模型或任一必验层级缺失时，状态是“验收未完成”，不把扫描完成当成验收完成。任意路径可做准备识别，但完整运行需已核验的环境配方。

本次真实执行 run-34f63bd1b76a：39项生成测试通过，17项项目检查11通过6失败，性能/联合恢复通过；模型旧请求未知导致整体验收未完成。详见[本批方案](docs/design/d022/方案与变更.md)与[实跑验证](docs/design/d022/实跑与验证.md)。


D022后续实测：已授权停止旧共享网关，修复版GPT-6 Thinking High五批实际生成31条用例（28通过、3预期不一致），加39条结构化用例、7项扫描与17项项目检查。完整执行run-80ffca2d641a耗时398.19秒，流程完整、门禁reject；30项检查18通过12失败，802项证据，原仓库未改动。339项后端、20项前端回归通过；详情见上述D022文档。知识库服务仍不可用，本批仅完成本地归档。


## D023 · 失败复核、中文模型与单行流水线

[12项逐项复核](docs/design/d023/12项失败逐项复核.md)区分重复扫描、已核实误报、旧用例问题和真实待处理风险。新增精确且全仓上下文绑定的冻结复核层，原工具报告及旧失败不改写；补齐模型适用前提和中文输出校验。流水线任何宽度均为单行横向滚动。

完整复跑run-42e8761aa719，418.75秒；31模型+39结构化用例全通过；30项检查有效26通过4阻断、0未完成，仍reject；807项证据完整性通过，原仓库未修改。[实现、自审与复跑](docs/design/d023/实现与自审.md)。知识库服务不可用，本批尚未远端同步。
# 最新通用验收验证

2026-10-19 完成本轮通用执行器修复及 Headroom、Flask、Fastify 三仓库实际重跑。目标源码未修改，原件完整性与环境清理均已复核；三个门禁保持 inconclusive，未覆盖范围不算通过。详见 [D038 最终验证报告](docs/design/d038/最终验证报告.md)、[实现自审](docs/design/d038/实现自审.md)及同目录原始证据与逐项对比。本轮知识库服务暂时不可用，最新资料先保留在本地。

