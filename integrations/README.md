# 成熟工具接入与质量门禁（D014 / 0.9.0）

这里是新增的通用接入层。原有 `assessment-local-v3` 业务、浏览器、ZAP、k6 和恢复验收继续保留。新增流程通过 **接入门禁** 页面操作；API 只启动已注册配置，不接受任意命令。

## 已实现的接入方式

- 执行：24 个固定配方，工具镜像 ID、工具版本、规则文件、源文件快照、执行日志和退出码留证。
- 导入：33 种报告格式/平台数据契约。兼容格式不等于验证过每个上游框架版本。
- 服务：DefectDojo Import/Reimport + 分页同步；ReportPortal launch/item 分页同步；SonarQube revision + measures + quality gate 同步。
- 判定：OPA 提供 allow / reject / inconclusive；指标、基线差值、新发现、许可证、必测用例、环境集合六类规则。
- 输出：JSON、JUnit、SARIF、Markdown；CLI 返回 0 / 1 / 2；可用于已有 CI 执行节点。

DefectDojo 和 ReportPortal 已部署本地隔离 OSS 实例实测。SonarQube 只有 HTTP 契约测试。商业平台、真实设备、云账号及模型能力没有因此变成“已接入”。

## 本机复跑

在项目根目录执行；Docker 需可用，`.venv` 为已安装锁定依赖的 Python 环境。

```sh
.venv/bin/python scripts/integrations.py catalog
.venv/bin/python scripts/integrations.py profiles
.venv/bin/python scripts/integrations.py register integrations/profiles/calibration-v2.json
.venv/bin/python scripts/integrations.py run integration-calibration-v2
```

校准输入含故意植入的缺陷，预期退出码为 1。正向输入可以用 `integration-positive-v1`，预期 0。配置不可覆盖；修改文件范围、策略或规则后使用新配置 ID，保留历史。

```sh
.venv/bin/python scripts/integration_ci.py integration-positive-v1 --output var/ci-positive
```

此命令真实执行、导出四类结果，并保留门禁退出码；不要在 CI 后面加 `|| true`。GitHub Actions、GitLab CI、Jenkins、Azure Pipelines 等需要用户自己的执行节点与凭据配置，本次没有连接这些远端账号，也没有修改任何远端分支保护。

## 在另一台执行节点准备环境

1. 安装根目录锁定的 Python 依赖，并准备 Docker、OPA（原验收框架使用的固定版本）。
2. 按 `images/Dockerfile.python`、`images/Dockerfile.node` 构建 `acceptance-python:d014`、`acceptance-node:d014`。Python/npm 精确依赖在对应 lock 文件中；基础镜像固定摘要。
3. 拉取 `toolchain.lock.json` 记录的上游镜像摘要。该文件同时保留本机实际 image ID；跨主机不能假设本机 image ID 已存在。
4. 执行 `scripts/integrations.py provision`，记录当前节点实际 image ID/版本；审阅新锁文件。该命令检查已安装镜像，不会自动构建所有镜像。
5. 调整 profile 的仓库绝对路径并给新 ID，明确列出文件和排除范围，再 register / run。

`network=none` 为默认；`registry` 仅允许固定的依赖数据库查询配方使用外网。它不是按域名强制过滤的 egress 白名单；不要把它当作生产级网络隔离。所有测试代码在只读源文件挂载和受限容器中运行，不能访问宿主 Docker socket。外部数据库缓存保存摘要；不同数据库版本的结果必须重新解释。

## 导入已有报告

创建 JSON manifest，`reports[].path` 相对 manifest 所在目录，`context` 为报告提供方声明的仓库/版本/快照/环境/范围。

```json
{
  "request_id": "d0140000-0000-4000-8000-000000000001",
  "name": "已有 CI 的单元测试",
  "context": {
    "repository": "my-repo",
    "revision": "实际提交 SHA",
    "snapshot_digest": "替换为实际文件清单 SHA256（64 位十六进制）",
    "environment": "实际执行环境",
    "scope": "冻结的必测范围"
  },
  "reports": [{"id": "unit", "format": "junit", "path": "junit.xml"}],
  "rules": [
    {"id": "failures", "kind": "metric", "tasks": ["unit"], "metric": "tests.failed", "threshold": 0},
    {"id": "count", "kind": "metric", "tasks": ["unit"], "metric": "tests.total", "operator": "ge", "threshold": 1}
  ]
}
```

每份报告可增加 `environment` 字段，例如chromium/firefox；它会冻结到导入清单，并参与幂等内容校验和 environments 门禁。外部标签仍由调用方声明，不是我方独立验证的设备事实。

执行 `scripts/integrations.py import manifest.json`。同一 request_id 内容必须一致。报告不完整、跳过/异常、缺指标、缺基线均不通过。Allure 目前导入 result JSON 数组（保留附件引用）；附件文件没有自动同步，不能声称附件已验证。原始报告可下载，预览截断不影响原件。

## 平台桥接

`sync` 配置包含 `service`、`url`、`token_env`、`request_id`、`name`、`context` 和 `rules`；同步任务固定 ID 为 `remote`。额外参数：

| 平台 | 必需字段 | 已验证范围 |
|---|---|---|
| defectdojo | test_id | 分页读回；发现项绑定同一 test；导入/重导入不关闭旧发现 |
| reportportal | project、launch_id | 结束 launch 的可计数 item；保留 issue 字段；不冒充其付费质量门禁 |
| sonarqube | project、branch；context.revision | 校验 revision，拉取指标和门禁后再检查分析身份；未有真实实例认证 |

`token_env` 只写环境变量名称，例如 `ACCEPTANCE_DOJO_TOKEN`，密钥由运行环境提供。不要把密钥写入配置、版本库或上传知识库。仅 HTTPS 和回环 HTTP 可用；不跟随跨源分页和重定向；写操作失败不自动重试。

```sh
.venv/bin/python scripts/integrations.py sync path/to/service.json
.venv/bin/python scripts/integrations.py service-import path/to/dojo-import.json path/to/report.json
```

Dojo import 配置为 `url`、`token_env`、`scan_type` 和 `engagement`；重导入用 `test_id` 替代 engagement。可将已在实例注册的报告类型交给官方解析器；393 个类型不是393 个已认证扫描器，本轮实测 Generic、Bandit、Semgrep、Trivy、Grype 五类。

## 本地 OSS 验证实例

`services/*/upstream.json` 固定官方 Compose 来源，`prepare.py` 生成专用本地配置与0600临时凭据文件；镜像按本机实际 ID 固定。其配置只用于本次隔离验证，不能当生产部署。

- Dojo：`var/integrations/defectdojo/compose.json`；回环端口18894；项目名 `acceptance-dojo-d014`。
- ReportPortal：`var/integrations/reportportal/compose.json`；回环端口18895；项目名 `acceptance-rp-d014`。只部署核心 API 依赖，不含 UI/ML analyzer。
- 两者使用专用子网 `10.231.250.0/24`、`10.231.251.0/24`；启动前核对没有与本机网络重叠。
- 使用对应 `local.env` 与 `compose.json` 执行 `docker compose ... up -d`；等待各服务健康后运行各自 `verify.py`。停止只对专用 project 执行 stop，保留卷与验证证据。
- ReportPortal prepare 依赖 PyYAML，可用 `validation/.venv/bin/python`。完整镜像版本与验证结果见 D014 记录。

## 当前边界

这是单机、本地受控工作台，没有分布式调度、多租户、SSO、远端 PR/工单回写、豁免审批、长期稳定性历史窗口或自动修复。报告哈希是本地完整性检查，不是可信签名。新解析器语义与旧记录不一致时历史会显示无法确认，原件保留；后续需做版本化解析器回放，不能静默改写旧报告。
