# 无模型验证复现说明

本目录是选型研究夹具，不是完整验收平台。包含故意带缺陷的回环 HTTP 服务、固定验收用例、上游函数反例和 OPA 策略原型。不得把夹具部署到公网。

主文档：[验收 Agent 调研与框架设计](/Users/alex/Documents/ChatGPT/竞赛/docs/验收Agent-调研与框架设计.md)。

## 运行环境与依赖

本次实测 macOS arm64、Node 24.19.0、Python 3.12.14、Docker 29.4.3。脚本中的 Bun 二进制路径对应 macOS arm64；其他平台须选对应 Bun 包路径。Node 版本需满足 axe 包要求，本次不使用宿主默认的 Node 20。

工作目录固定为 `/Users/alex/Documents/ChatGPT/竞赛`。依赖见 [package-lock.json](/Users/alex/Documents/ChatGPT/竞赛/validation/package-lock.json) 和 [requirements.lock.txt](/Users/alex/Documents/ChatGPT/竞赛/validation/requirements.lock.txt)。

```sh
cd /Users/alex/Documents/ChatGPT/竞赛
uv venv --python 3.12 validation/.venv
uv pip install --python validation/.venv/bin/python -r validation/requirements.lock.txt
npm ci --ignore-scripts --prefix validation
```

确保 npm 也使用 Node 24。浏览器安装使用本轮实际运行时：

```sh
/Users/alex/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node validation/node_modules/playwright/cli.js install chromium
```

## 上游快照

[upstream-manifest.json](/Users/alex/Documents/ChatGPT/竞赛/research/evidence/upstream-manifest.json) 记录六个仓库的完整 SHA。Gauntlet、Strix、Playwright 通过浅克隆取得；另三个最初 Git 克隆超时、GitHub API 限流，改用源码归档，并从 Git 归档的 PAX comment 核实 commit SHA；二次下载核对归档哈希一致。

源码保存在 `/Users/alex/Documents/ChatGPT/竞赛/research/upstream`，已被本项目 Git 忽略。源码归档也保留在该目录。跨机器复现需按清单指定 SHA 获取；不要把新的 main 分支当成本次快照。

运行组件脚本需要本地 `/Users/alex/Documents/ChatGPT/竞赛/research/upstream/gauntlet` 对应清单 SHA，以便直接调用上游校验函数。上游代码只用于研究，未复制进我们的生产实现。

## 正式组件对比

端口 18871、18872 必须空闲。服务只监听 127.0.0.1，测试结束关闭。每次复现请选择新的输出目录，不覆盖已有记录：

```sh
cd /Users/alex/Documents/ChatGPT/竞赛
RESEARCH_EVIDENCE_DIR="$PWD/research/evidence/my-new-run" validation/.venv/bin/python validation/run_components.py
```

脚本运行缺陷版与修正版，分别调用 Playwright、axe、Schemathesis、Bandit，并对 Gauntlet 校验函数做四个反例。若使用其他 Node 24 路径，可设置 `RESEARCH_NODE`。退出 0 代表**实验符合预期**，不是缺陷版应用通过验收。

预期：

- Playwright 缺陷版 6 失败/1 通过，修正版 7 通过；没有跳过或 flaky。
- Schemathesis 与 Bandit 缺陷版退出 1，修正版退出 0。
- 对比前后验收测试文件 SHA-256 一致。
- Gauntlet 拒绝空证据和总分项矛盾；该函数接受非空的虚构文件引用与改写后的 criterion 文本。

Bandit 只运行 B602；Schemathesis 只运行一个操作的 response_schema_conformance；axe 只运行 label。不要从这些结果推导全量安全或无障碍合规。

首次人工校准的 Playwright 定位歧义保存在 `/Users/alex/Documents/ChatGPT/竞赛/research/evidence/initial-calibration`。正式记录在 `/Users/alex/Documents/ChatGPT/竞赛/research/evidence`；最后一次脚本复现检查在其 `repro-check` 子目录。

## OPA 与 Gitleaks

镜像已按 digest 固定；运行阶段关闭容器网络，输入只读挂载。第一次使用需单独取得清单中对应镜像。脚本构造的 token 只是无效格式样本，扫描报告启用 100% 脱敏。

```sh
RESEARCH_EVIDENCE_DIR="$PWD/research/evidence/my-policy-run" validation/.venv/bin/python validation/run_policy_and_secrets.py
```

OPA 21 项策略测试应全部通过；Gitleaks 缺陷目录检出 1 条，修正目录 0 条。本研究 policy 仍是原型：Schema 校验、可信采集器和签名验证尚未整合，不能直接作为生产准入服务。

## 上游单元测试

Gauntlet（96 项）：

```sh
cd /Users/alex/Documents/ChatGPT/竞赛/research/upstream/gauntlet
/Users/alex/Documents/ChatGPT/竞赛/validation/node_modules/@oven/bun-darwin-aarch64/bin/bun test test/agent/validators.test.ts test/evidence/logger.test.ts test/evidence/writer.test.ts test/format/story-card.test.ts test/runs/run-set-aggregate.test.ts
```

Strix（56 项）：

```sh
cd /Users/alex/Documents/ChatGPT/竞赛/research/upstream/strix
PYTHONPATH="$PWD" /Users/alex/Documents/ChatGPT/竞赛/validation/.venv/bin/python -m pytest tests/test_sarif.py tests/test_report_coverage.py tests/test_sarif_stride.py -q
```

本次完整安装 Strix 的 Go TUI 构建遇到 proxy.golang.org 下载超时；所选纯 Python 模块使用源码路径和最小依赖执行，没有把完整安装说成成功。

Test-Agent（56 项）：

```sh
cd /Users/alex/Documents/ChatGPT/竞赛/research/upstream/test-agent-source/Test-Agent-HEAD
PYTHONPATH="$PWD" TAGENT_REAL_LLM=0 /Users/alex/Documents/ChatGPT/竞赛/validation/.venv/bin/python -m pytest runtime/tests/test_utils_evidence_chain.py runtime/tests/test_utils_quality_gate.py -q
```

证据函数边界实验：

```sh
cd /Users/alex/Documents/ChatGPT/竞赛
PYTHONPATH=research/upstream/test-agent-source/Test-Agent-HEAD validation/.venv/bin/python validation/test_agent_probe.py
```

这几个上游测试只覆盖选定模块，不证明自主 Agent 的实际规划/漏洞发现能力。没有调用模型接口。

## 证据校验

[artifact-index.json](/Users/alex/Documents/ChatGPT/竞赛/research/evidence/artifact-index.json) 包含最终研究文件的大小和 SHA-256；它自身不纳入摘要清单，不存在递归哈希。此清单未签名，能够复核文件是否变化，不能独立认证作者或运行真实性。

```sh
cd /Users/alex/Documents/ChatGPT/竞赛
validation/.venv/bin/python validation/review_bundle.py
```

该脚本检查实际统计、上游测试结果、OPA 结果、源码快照引用、本地文档链接及产物摘要。它不会调用模型或外部业务接口。
