# r4 Flask 逐项复核

记录 int-5740126cbe21420e，85 条业务用例为 68 passed、9 failed、8 error；其中 18 条真实浏览器用例为 11 passed、6 failed、1 error。完整性核验有效，历史门禁为 inconclusive。下表是追加的复核意见，不改写原始结果，也不声称没有项目缺陷。

| 用例 | 实际问题与复核边界 |
| --- | --- |
| B4-script_root_rendered | 用 environ_base 注入 SCRIPT_NAME，实际请求未得到 /myapp。基础环境不等于最终覆盖环境；不能据此确认挂载根路径实现失败。 |
| B3-result-poll-flow | HTTP 回执为 status/headers/value 包装，用例却访问 /ready 等正文根字段。页面提交和首个 UI 结果已通过，轮询观察路径错误。 |
| B6-c-templates-static | 实际 CSS 为多行，预期压成单行后作字符 contains。相同声明的排版差异不证明静态服务或 CSS 语义错误。 |
| B8-getdb-rowfactory | 对 sqlite3.Row 用属性 x，而独立说明为按键读取；应区分属性与条目。原预期和异常保留。 |
| B8-timestamp-converter | 对 sqlite3.Row 用属性 created，错误发生在取得时间戳之前；不能证明时间转换器错误。 |
| B9-register-insert-redirect-scenario | 初始化辅助器先返回缺应用上下文，后续读取 user 表失败。不能把前置命令异常后的缺表直接确认为注册/数据库缺陷。辅助器适用前提仍需独立核对。 |
| B9-register-duplicate-scenario | 同一初始化异常导致后续注册 500 与缺 Location；前置失败需要先处理，不能单独确认重复注册逻辑有缺陷。 |
| B9-register-password-hash-scenario | 初始化异常后缺表，尚未取得密码字段，未完成密码散列断言。 |
| B10-login_errors | h1 同时匹配站点和内容标题，Playwright strict mode violation；用例定位器不唯一，平台错误地归为 failed。 |
| B10-login_required_flow | 同一非唯一 h1 问题，不能据此确认权限/跳转逻辑错误。 |
| B11-case_register_form | HAR、HTML 与失败观察均含正确 title，普通 head 文本断言却读取空。属于平台标题断言适配缺陷。 |
| B11-case_login_form | 同上，页面已有 Log In - Flaskr；候选修复改用成熟的 Playwright PageAssertions.toHaveTitle。 |
| B11-case_register_redirect | 非唯一 h1；不擅自挑第一个元素、不改项目或预期。 |
| B13-C-CREATE-UNAUTH-REDIRECT | 非唯一 h1；不能据此确认未登录保护失败。 |
| B15-runner_init_db | Click Result 明确为 exit_code=1、Working outside of application context。此测试辅助器入口与独立 flask 命令不等价，不扩大为 CLI 业务失败结论；保留辅助器局限待核。 |
| B16-C4 | 同一初始化入口问题；未创建 user 表后 fetchone 返回 None，随后下标错误是继发结果。 |
| B17-login-success-case | SecureCookieSession 是按键读取的映射，用例却取 user_id 属性；尚未完成声明的会话字段断言。 |

同轮 B6-c-init-db 真实运行 `flask --app flaskr init-db`，退出正常并输出 `Initialized the database.`。这条证据限定独立命令已成功，不代表上述辅助器上下文问题不存在。

9 条 failed 已通过现有追加式复核接口记录为 test_issue，回执见 r4-flask-recorded-reviews.json；历史失败和门禁不变。其余 error 以逐项账本保留，尚未自动确认为项目缺陷。

## 平台后续修正

候选修复仅在独立目录准备，当前执行不切换代码：

- 标题使用 Playwright page.toHaveTitle，原字符串预期不变；故意错误标题仍 failed。
- 非唯一定位器标记 case/error，不作为独立业务断言失败；拒绝自动选首个元素。
- 不合法的 HTTP 包装层观察路径标为 case/error，不猜测或改写原指针。
- JUnit 只写一份完整诊断正文，取消 JSON 重复拼接和截断；保留超长原始观察及分类。

两项候选回归已通过，覆盖 13 个真实 Chromium 子场景及超长结构化诊断。最终切换前仍需全量回归和三仓库复验。

参考：[Playwright 标题断言](https://playwright.dev/docs/api/class-pageassertions#page-assertions-to-have-title)、[Werkzeug 测试环境构建](https://werkzeug.palletsprojects.com/en/stable/test/)。


## 2026-10-31 追加更正：CLI 辅助器不能排除真实问题

此前将 B15-runner_init_db 判为 test_issue 的依据不足，现通过追加式复核恢复 needs_review，旧复核事件和历史门禁保留。2026-10-26 已完成的独立 Python 诊断（不经过场景执行器）直接导入冻结源码，公开调用 app.test_cli_runner().invoke(args=["init-db"])，实际同样返回 exit_code=1、空输出、数据库未创建；完整异常栈进入教程 db.py 的 init_db/get_db/g 后报应用上下文缺失。

教程原生 test_init_db_command 将 init_db 替换为 fake_init_db，因此该测试通过不能排除此真实初始化失败。B9 三条注册前置与 B16 也受同一失败影响，应保留候选及其继发结果，不能笼统归入用例误报。当前只确认公开调用失败可独立复现，尚未将其扩大为整个 Flask 框架缺陷。原件见 r6-independent-cli-repro，复核回执见 r6-cli-review-correction.json；不修改被验收项目。
