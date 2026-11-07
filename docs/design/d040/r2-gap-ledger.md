# D040 逐项覆盖缺口账本

仅整理已终态、完整性验证通过的记录。模型分类仍标明来源；执行错误、缺少依据和未覆盖均不能视为确认产品缺陷。未自动删除语义相近的模型意见，原始条目数不等于不重复需求数或覆盖率。

## G001 · fastify · 用例契约问题

1 validation error for Case
flow
  Value error, 只允许公开属性或方法名 [type=value_error, input_value={'steps': [{'id': 'app', ...rison': 'json_stream'}]}, input_type=dict]
    For further information visit https://errors.pydantic.dev/2.14/v/value_error

- 分类来源：contract-validation
- 定位：d1_async_json_route
- 依据文档：README.md · README.md#chars=0:16376
- [执行记录](http://127.0.0.1:18890/?run=int-b5e17ff98d8445c4&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-b5e17ff98d8445c4/artifacts/art-31e33aea1fab4cc0)
- [response_ref](http://127.0.0.1:18890/api/runs/int-b5e17ff98d8445c4/artifacts/art-bd2c652f532e40eb)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-b5e17ff98d8445c4/artifacts/art-fbaa785dff5b43fd)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-b5e17ff98d8445c4/artifacts/art-794aad7cae084b00)

## G002 · fastify · 待分类

该需求没有经契约校验的可执行用例；具体原因见逐项诊断

- 分类来源：model
- 定位：D1-ASYNC-JSON
- 依据文档：README.md · README.md#chars=0:16376
- [执行记录](http://127.0.0.1:18890/?run=int-b5e17ff98d8445c4&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-b5e17ff98d8445c4/artifacts/art-31e33aea1fab4cc0)
- [response_ref](http://127.0.0.1:18890/api/runs/int-b5e17ff98d8445c4/artifacts/art-bd2c652f532e40eb)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-b5e17ff98d8445c4/artifacts/art-fbaa785dff5b43fd)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-b5e17ff98d8445c4/artifacts/art-794aad7cae084b00)

## G003 · fastify · 平台能力不足

文档要求端口为随机可用端口并通过 server.address().port 观察，但当前 checks 只支持 equals/one_of/contains/json_stream 等比较，无法表达“大于 0 且非零”的动态数值关系；缺少关系比较协议，不能把具体随机端口写成固定预期。

- 分类来源：model
- 定位：D2-RANDOM-PORT
- 依据文档：docs/Reference/Server.md · docs/Reference/Server.md#chars=41939:45203
- [执行记录](http://127.0.0.1:18890/?run=int-b5e17ff98d8445c4&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-b5e17ff98d8445c4/artifacts/art-31e33aea1fab4cc0)
- [response_ref](http://127.0.0.1:18890/api/runs/int-b5e17ff98d8445c4/artifacts/art-bd2c652f532e40eb)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-b5e17ff98d8445c4/artifacts/art-fbaa785dff5b43fd)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-b5e17ff98d8445c4/artifacts/art-794aad7cae084b00)

## G004 · fastify · 平台能力不足

该标准要求观察 listen 成功后的启动日志文本，但当前执行协议没有日志流捕获或日志断言能力，无法核对自定义 resolver 是否替代默认日志。

- 分类来源：model
- 定位：D2-LISTEN-TEXT-RESOLVER
- 依据文档：docs/Reference/Server.md · docs/Reference/Server.md#chars=41939:45203
- [执行记录](http://127.0.0.1:18890/?run=int-b5e17ff98d8445c4&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-b5e17ff98d8445c4/artifacts/art-31e33aea1fab4cc0)
- [response_ref](http://127.0.0.1:18890/api/runs/int-b5e17ff98d8445c4/artifacts/art-bd2c652f532e40eb)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-b5e17ff98d8445c4/artifacts/art-fbaa785dff5b43fd)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-b5e17ff98d8445c4/artifacts/art-794aad7cae084b00)

## G005 · fastify · 用例契约问题

1 validation error for Case
flow
  Value error, 只允许公开属性或方法名 [type=value_error, input_value={'steps': [{'id': 'app', ...rison': 'json_stream'}]}, input_type=dict]
    For further information visit https://errors.pydantic.dev/2.14/v/value_error

- 分类来源：contract-validation
- 定位：d3_first_server_reply_send
- 依据文档：docs/Guides/Getting-Started.md · docs/Guides/Getting-Started.md#chars=0:9994
- [执行记录](http://127.0.0.1:18890/?run=int-b5e17ff98d8445c4&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-b5e17ff98d8445c4/artifacts/art-31e33aea1fab4cc0)
- [response_ref](http://127.0.0.1:18890/api/runs/int-b5e17ff98d8445c4/artifacts/art-bd2c652f532e40eb)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-b5e17ff98d8445c4/artifacts/art-fbaa785dff5b43fd)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-b5e17ff98d8445c4/artifacts/art-794aad7cae084b00)

## G006 · fastify · 待分类

该需求没有经契约校验的可执行用例；具体原因见逐项诊断

- 分类来源：model
- 定位：D3-FIRST-SERVER-REPLY-SEND
- 依据文档：docs/Guides/Getting-Started.md · docs/Guides/Getting-Started.md#chars=0:9994
- [执行记录](http://127.0.0.1:18890/?run=int-b5e17ff98d8445c4&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-b5e17ff98d8445c4/artifacts/art-31e33aea1fab4cc0)
- [response_ref](http://127.0.0.1:18890/api/runs/int-b5e17ff98d8445c4/artifacts/art-bd2c652f532e40eb)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-b5e17ff98d8445c4/artifacts/art-fbaa785dff5b43fd)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-b5e17ff98d8445c4/artifacts/art-794aad7cae084b00)

## G007 · fastify · 用例契约问题

引用不能在指定文档中唯一定位

- 分类来源：contract-validation
- 定位：D3-SCHEMA-VALIDATION-400
- 依据文档：docs/Guides/Getting-Started.md · docs/Guides/Getting-Started.md#chars=0:9994
- [执行记录](http://127.0.0.1:18890/?run=int-b5e17ff98d8445c4&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-b5e17ff98d8445c4/artifacts/art-31e33aea1fab4cc0)
- [response_ref](http://127.0.0.1:18890/api/runs/int-b5e17ff98d8445c4/artifacts/art-bd2c652f532e40eb)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-b5e17ff98d8445c4/artifacts/art-fbaa785dff5b43fd)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-b5e17ff98d8445c4/artifacts/art-794aad7cae084b00)

## G008 · fastify · 用例契约问题

引用不能在指定文档中唯一定位

- 分类来源：contract-validation
- 定位：D3-RESPONSE-SCHEMA-FILTER
- 依据文档：docs/Guides/Getting-Started.md · docs/Guides/Getting-Started.md#chars=0:9994
- [执行记录](http://127.0.0.1:18890/?run=int-b5e17ff98d8445c4&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-b5e17ff98d8445c4/artifacts/art-31e33aea1fab4cc0)
- [response_ref](http://127.0.0.1:18890/api/runs/int-b5e17ff98d8445c4/artifacts/art-bd2c652f532e40eb)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-b5e17ff98d8445c4/artifacts/art-fbaa785dff5b43fd)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-b5e17ff98d8445c4/artifacts/art-794aad7cae084b00)

## G009 · fastify · 用例契约问题

引用不能在指定文档中唯一定位

- 分类来源：contract-validation
- 定位：D3-JSON-BODY-PARSING
- 依据文档：docs/Guides/Getting-Started.md · docs/Guides/Getting-Started.md#chars=0:9994
- [执行记录](http://127.0.0.1:18890/?run=int-b5e17ff98d8445c4&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-b5e17ff98d8445c4/artifacts/art-31e33aea1fab4cc0)
- [response_ref](http://127.0.0.1:18890/api/runs/int-b5e17ff98d8445c4/artifacts/art-bd2c652f532e40eb)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-b5e17ff98d8445c4/artifacts/art-fbaa785dff5b43fd)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-b5e17ff98d8445c4/artifacts/art-794aad7cae084b00)

## G010 · fastify · 用例契约问题

引用不能在指定文档中唯一定位

- 分类来源：contract-validation
- 定位：D3-CLI-EXCLUDED
- 依据文档：docs/Guides/Getting-Started.md · docs/Guides/Getting-Started.md#chars=0:9994
- [执行记录](http://127.0.0.1:18890/?run=int-b5e17ff98d8445c4&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-b5e17ff98d8445c4/artifacts/art-31e33aea1fab4cc0)
- [response_ref](http://127.0.0.1:18890/api/runs/int-b5e17ff98d8445c4/artifacts/art-bd2c652f532e40eb)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-b5e17ff98d8445c4/artifacts/art-fbaa785dff5b43fd)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-b5e17ff98d8445c4/artifacts/art-794aad7cae084b00)

## G011 · fastify · 用例契约问题

1 validation error for Case
flow
  Value error, 只允许公开属性或方法名 [type=value_error, input_value={'version': 1, 'steps': [...ot', 'expected': True}]}, input_type=dict]
    For further information visit https://errors.pydantic.dev/2.14/v/value_error

- 分类来源：contract-validation
- 定位：decorator-scope-isolation
- 依据文档：docs/Guides/Plugins-Guide.md · docs/Guides/Plugins-Guide.md#chars=0:9991
- [执行记录](http://127.0.0.1:18890/?run=int-b5e17ff98d8445c4&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-b5e17ff98d8445c4/artifacts/art-7791ab1aafda411d)
- [response_ref](http://127.0.0.1:18890/api/runs/int-b5e17ff98d8445c4/artifacts/art-09646a7af5a440fa)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-b5e17ff98d8445c4/artifacts/art-9fc1bec34d2f47dd)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-b5e17ff98d8445c4/artifacts/art-ee2a529894c34a52)

## G012 · fastify · 待分类

该需求没有经契约校验的可执行用例；具体原因见逐项诊断

- 分类来源：model
- 定位：plugin-encapsulation
- 依据文档：docs/Guides/Plugins-Guide.md · docs/Guides/Plugins-Guide.md#chars=0:9991
- [执行记录](http://127.0.0.1:18890/?run=int-b5e17ff98d8445c4&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-b5e17ff98d8445c4/artifacts/art-7791ab1aafda411d)
- [response_ref](http://127.0.0.1:18890/api/runs/int-b5e17ff98d8445c4/artifacts/art-09646a7af5a440fa)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-b5e17ff98d8445c4/artifacts/art-9fc1bec34d2f47dd)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-b5e17ff98d8445c4/artifacts/art-ee2a529894c34a52)

## G013 · fastify · 平台能力不足

文档示例要求处理器返回 request.body，需要向 inject 提供 POST 请求体并在处理函数中动态读取 request.body。当前 execution_contract 未说明 inject 请求体的输入字段，也未提供从回调参数读取 request.body 的声明方式；D36 只展示无请求体的 GET inject，因此无法构造可核对的请求体回显用例。

- 分类来源：model
- 定位：payload-parsing
- 依据文档：docs/Guides/Getting-Started.md · docs/Guides/Getting-Started.md#chars=9994:15919
- [执行记录](http://127.0.0.1:18890/?run=int-b5e17ff98d8445c4&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-b5e17ff98d8445c4/artifacts/art-7791ab1aafda411d)
- [response_ref](http://127.0.0.1:18890/api/runs/int-b5e17ff98d8445c4/artifacts/art-09646a7af5a440fa)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-b5e17ff98d8445c4/artifacts/art-9fc1bec34d2f47dd)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-b5e17ff98d8445c4/artifacts/art-ee2a529894c34a52)

## G014 · fastify · 平台能力不足

文档对文件命名给出明确规则（否则会被 fastify 单元测试的正则收集），但当前执行协议只能调用公开模块/CLI 并观察其输出，缺少枚举 test/bundler 下文件清单或查看单测收集结果的观察协议，无法把该命名约定变成可断言的检查。

- 分类来源：model
- 定位：bundler-test-file-naming
- 依据文档：test/bundler/README.md · test/bundler/README.md#chars=0:1276
- [执行记录](http://127.0.0.1:18890/?run=int-b5e17ff98d8445c4&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-b5e17ff98d8445c4/artifacts/art-bfa21b2920564428)
- [response_ref](http://127.0.0.1:18890/api/runs/int-b5e17ff98d8445c4/artifacts/art-40242d24731447d7)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-b5e17ff98d8445c4/artifacts/art-68293a5b0c82482a)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-b5e17ff98d8445c4/artifacts/art-76d67bffa6594994)

## G015 · fastify · 用例契约问题

执行组件或协议不可用

- 分类来源：contract-validation
- 定位：webpack-bundler-test
- 依据文档：test/bundler/README.md · test/bundler/README.md#chars=0:1276
- [执行记录](http://127.0.0.1:18890/?run=int-b5e17ff98d8445c4&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-b5e17ff98d8445c4/artifacts/art-bfa21b2920564428)
- [response_ref](http://127.0.0.1:18890/api/runs/int-b5e17ff98d8445c4/artifacts/art-40242d24731447d7)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-b5e17ff98d8445c4/artifacts/art-68293a5b0c82482a)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-b5e17ff98d8445c4/artifacts/art-76d67bffa6594994)

## G016 · fastify · 待分类

该需求没有经契约校验的可执行用例；具体原因见逐项诊断

- 分类来源：model
- 定位：webpack-bundler-test-runs
- 依据文档：test/bundler/README.md · test/bundler/README.md#chars=0:1276
- [执行记录](http://127.0.0.1:18890/?run=int-b5e17ff98d8445c4&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-b5e17ff98d8445c4/artifacts/art-bfa21b2920564428)
- [response_ref](http://127.0.0.1:18890/api/runs/int-b5e17ff98d8445c4/artifacts/art-40242d24731447d7)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-b5e17ff98d8445c4/artifacts/art-68293a5b0c82482a)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-b5e17ff98d8445c4/artifacts/art-76d67bffa6594994)

## G017 · fastify · 待分类

部分用例未完整执行

- 分类来源：execution-stage
- 定位：u-d935a3cdea-native
- [执行记录](http://127.0.0.1:18890/?run=int-b5e17ff98d8445c4&tab=flow&evidence=run)
- [task-report](http://127.0.0.1:18890/api/runs/int-b5e17ff98d8445c4/artifacts/art-7714fb3e24914dcf)

## G018 · flask · 缺少依据

文档仅给出定性定位（轻量、WSGI 框架、不强制依赖与项目布局），未给出可直接观察的输入输出契约或预期结果，无法据此设计独立核对标准。

- 分类来源：model
- 定位：R3
- 依据文档：README.md · README.md#chars=0:1639
- [执行记录](http://127.0.0.1:18890/?run=int-cc4290eb3ed94f4d&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-cc4290eb3ed94f4d/artifacts/art-9debeccd519c49a5)
- [response_ref](http://127.0.0.1:18890/api/runs/int-cc4290eb3ed94f4d/artifacts/art-014ea6b9d7014568)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-cc4290eb3ed94f4d/artifacts/art-b7f5944e615746b2)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-cc4290eb3ed94f4d/artifacts/art-9f3d5fd22b354915)

## G019 · flask · 用例契约问题

调用入口不在公开语法索引中，或别名存在歧义

- 分类来源：contract-validation
- 定位：celery-init-app
- 依据文档：docs/patterns/celery.rst · docs/patterns/celery.rst#chars=0:8670
- [执行记录](http://127.0.0.1:18890/?run=int-cc4290eb3ed94f4d&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-cc4290eb3ed94f4d/artifacts/art-fb4b6e95fc7e4a4c)
- [response_ref](http://127.0.0.1:18890/api/runs/int-cc4290eb3ed94f4d/artifacts/art-94e2c5c7350d43be)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-cc4290eb3ed94f4d/artifacts/art-45b7d60809fe4067)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-cc4290eb3ed94f4d/artifacts/art-8632d7f27cbf4940)

## G020 · flask · 环境未就绪

D2 要求提交任务的 API；D3 明确 /add 读取表单 a、b 并立即返回 result_id。执行该路由需要 Redis broker 和运行中的 Celery worker；当前 examples/celery 未声明 worker CLI 入口，平台也未预置这些服务。

- 分类来源：model
- 定位：submit-api
- 依据文档：docs/patterns/celery.rst · docs/patterns/celery.rst#chars=0:8670
- [执行记录](http://127.0.0.1:18890/?run=int-cc4290eb3ed94f4d&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-cc4290eb3ed94f4d/artifacts/art-fb4b6e95fc7e4a4c)
- [response_ref](http://127.0.0.1:18890/api/runs/int-cc4290eb3ed94f4d/artifacts/art-94e2c5c7350d43be)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-cc4290eb3ed94f4d/artifacts/art-45b7d60809fe4067)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-cc4290eb3ed94f4d/artifacts/art-8632d7f27cbf4940)

## G021 · flask · 环境未就绪

D2 要求轮询结果 API；D3 明确 /result/<id> 返回 ready、successful 和 value。要取得真实 AsyncResult 需要运行中的 worker 与结果后端，当前环境未准备。

- 分类来源：model
- 定位：result-api
- 依据文档：docs/patterns/celery.rst · docs/patterns/celery.rst#chars=0:8670
- [执行记录](http://127.0.0.1:18890/?run=int-cc4290eb3ed94f4d&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-cc4290eb3ed94f4d/artifacts/art-fb4b6e95fc7e4a4c)
- [response_ref](http://127.0.0.1:18890/api/runs/int-cc4290eb3ed94f4d/artifacts/art-94e2c5c7350d43be)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-cc4290eb3ed94f4d/artifacts/art-45b7d60809fe4067)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-cc4290eb3ed94f4d/artifacts/art-8632d7f27cbf4940)

## G022 · flask · 环境未就绪

D2 说明后台任务；D3 明确提交路由不应等待任务完成，只返回 result id。要观察请求立即返回与后台完成，需要已运行 worker 和 broker，当前无法执行该有状态流程。

- 分类来源：model
- 定位：nonblocking-background
- 依据文档：docs/patterns/celery.rst · docs/patterns/celery.rst#chars=0:8670
- [执行记录](http://127.0.0.1:18890/?run=int-cc4290eb3ed94f4d&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-cc4290eb3ed94f4d/artifacts/art-fb4b6e95fc7e4a4c)
- [response_ref](http://127.0.0.1:18890/api/runs/int-cc4290eb3ed94f4d/artifacts/art-94e2c5c7350d43be)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-cc4290eb3ed94f4d/artifacts/art-45b7d60809fe4067)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-cc4290eb3ed94f4d/artifacts/art-8632d7f27cbf4940)

## G023 · flask · 平台能力不足

D2 要求浏览器首页用表单提交任务并观察轮询；原文未给出表单字段标签、选择器或页面结果文本，且任务完成仍依赖 worker/broker，当前无法形成可执行浏览器断言。

- 分类来源：model
- 定位：browser-forms
- 依据文档：examples/celery/README.md · examples/celery/README.md#chars=0:950
- [执行记录](http://127.0.0.1:18890/?run=int-cc4290eb3ed94f4d&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-cc4290eb3ed94f4d/artifacts/art-fb4b6e95fc7e4a4c)
- [response_ref](http://127.0.0.1:18890/api/runs/int-cc4290eb3ed94f4d/artifacts/art-94e2c5c7350d43be)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-cc4290eb3ed94f4d/artifacts/art-45b7d60809fe4067)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-cc4290eb3ed94f4d/artifacts/art-8632d7f27cbf4940)

## G024 · flask · 缺少依据

D4 只声明示例效果，没有给出提交路径、表单字段、响应 JSON 结构或页面可观察状态；D5 的 FormData 示例使用 room_url 与 name/description，但未绑定 js_example 的路由和返回数据，因此无法确定可执行输入与预期输出。

- 分类来源：model
- 定位：js_ajax_form_json
- 依据文档：examples/javascript/README.rst · examples/javascript/README.rst#chars=0:1086
- [执行记录](http://127.0.0.1:18890/?run=int-cc4290eb3ed94f4d&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-cc4290eb3ed94f4d/artifacts/art-4df29568dd004db3)
- [response_ref](http://127.0.0.1:18890/api/runs/int-cc4290eb3ed94f4d/artifacts/art-a393820dc19243f5)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-cc4290eb3ed94f4d/artifacts/art-b0d9d3ac8e0247b8)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-cc4290eb3ed94f4d/artifacts/art-71717784adf548b2)

## G025 · flask · 缺少依据

D4 仅列出三种 API，未给出页面脚本位置、网络请求或可观察输出；D5 说明现代文档只聚焦 fetch 且 XHR/jQuery 已非必需，但未说明 js_example 中三者的具体调用和结果。

- 分类来源：model
- 定位：js_ajax_libraries
- 依据文档：examples/javascript/README.rst · examples/javascript/README.rst#chars=0:1086
- [执行记录](http://127.0.0.1:18890/?run=int-cc4290eb3ed94f4d&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-cc4290eb3ed94f4d/artifacts/art-4df29568dd004db3)
- [response_ref](http://127.0.0.1:18890/api/runs/int-cc4290eb3ed94f4d/artifacts/art-a393820dc19243f5)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-cc4290eb3ed94f4d/artifacts/art-b0d9d3ac8e0247b8)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-cc4290eb3ed94f4d/artifacts/art-71717784adf548b2)

## G026 · flask · 平台能力不足

D5 明确给出 name/description 表单字段及 request.form 访问方式，但当前 scenario 只能让视图回调返回字面量或引用，无法在视图内读取 request.form；浏览器端 fetch 也缺少页面与执行观察协议。

- 分类来源：model
- 定位：formdata_request_form
- 依据文档：docs/patterns/javascript.rst · docs/patterns/javascript.rst#chars=0:9038
- [执行记录](http://127.0.0.1:18890/?run=int-cc4290eb3ed94f4d&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-cc4290eb3ed94f4d/artifacts/art-4df29568dd004db3)
- [response_ref](http://127.0.0.1:18890/api/runs/int-cc4290eb3ed94f4d/artifacts/art-a393820dc19243f5)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-cc4290eb3ed94f4d/artifacts/art-b0d9d3ac8e0247b8)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-cc4290eb3ed94f4d/artifacts/art-71717784adf548b2)

## G027 · flask · 平台能力不足

文档要求创建 app.instance_path 指向的实例目录，但当前执行协议没有对动态实例目录做存在性观察的步骤；只能读取配置和临时目录文件，无法对该目录已创建作出断言。

- 分类来源：model
- 定位：D9-instance-folder
- 依据文档：docs/tutorial/factory.rst · docs/tutorial/factory.rst#chars=0:5878
- [执行记录](http://127.0.0.1:18890/?run=int-cc4290eb3ed94f4d&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-cc4290eb3ed94f4d/artifacts/art-173f555887af41ac)
- [response_ref](http://127.0.0.1:18890/api/runs/int-cc4290eb3ed94f4d/artifacts/art-419aed0a68104cf0)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-cc4290eb3ed94f4d/artifacts/art-8f631a60b43c45c8)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-cc4290eb3ed94f4d/artifacts/art-481661a2d7824fb7)

## G028 · flask · 平台能力不足

README 的 Run 步骤要求执行 flask --app flaskr init-db，D10 补充成功输出为 Initialized the database.；但 discovery 中示例单元 u-6d5d23e8a9 未声明 cli_commands，无法生成 entry=flask 的 CLI 步骤来观察该命令输出和退出状态。

- 分类来源：model
- 定位：D6-init-db-command
- 依据文档：examples/tutorial/README.rst · examples/tutorial/README.rst#chars=0:1273
- [执行记录](http://127.0.0.1:18890/?run=int-cc4290eb3ed94f4d&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-cc4290eb3ed94f4d/artifacts/art-173f555887af41ac)
- [response_ref](http://127.0.0.1:18890/api/runs/int-cc4290eb3ed94f4d/artifacts/art-419aed0a68104cf0)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-cc4290eb3ed94f4d/artifacts/art-8f631a60b43c45c8)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-cc4290eb3ed94f4d/artifacts/art-481661a2d7824fb7)

## G029 · flask · 平台能力不足

D23 要求 close_db 关闭连接，并由 init_app 注册为 teardown_appcontext；当前执行协议只能读取字段或调用普通方法，缺少异常捕获和连接关闭状态观察，无法在上下文退出后断言 sqlite3.ProgrammingError 或 closed 状态。

- 分类来源：model
- 定位：R4
- 依据文档：docs/tutorial/database.rst · docs/tutorial/database.rst#chars=0:7028
- [执行记录](http://127.0.0.1:18890/?run=int-cc4290eb3ed94f4d&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-cc4290eb3ed94f4d/artifacts/art-3fcb24c5e6b9435d)
- [response_ref](http://127.0.0.1:18890/api/runs/int-cc4290eb3ed94f4d/artifacts/art-afb3ae1e47194145)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-cc4290eb3ed94f4d/artifacts/art-458a13bdaca24dbe)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-cc4290eb3ed94f4d/artifacts/art-9ba84aef8eac4f62)

## G030 · flask · 用例契约问题

引用不能在指定文档中唯一定位

- 分类来源：contract-validation
- 定位：base-nav-unauth
- 依据文档：docs/tutorial/templates.rst · docs/tutorial/templates.rst#chars=0:6962
- [执行记录](http://127.0.0.1:18890/?run=int-cc4290eb3ed94f4d&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-cc4290eb3ed94f4d/artifacts/art-7304231df3f04ed0)
- [response_ref](http://127.0.0.1:18890/api/runs/int-cc4290eb3ed94f4d/artifacts/art-76cdb3a1e22742a6)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-cc4290eb3ed94f4d/artifacts/art-77b51665b950466a)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-cc4290eb3ed94f4d/artifacts/art-69e8487b91694b19)

## G031 · flask · 用例契约问题

引用不能在指定文档中唯一定位

- 分类来源：contract-validation
- 定位：base-nav-auth
- 依据文档：docs/tutorial/templates.rst · docs/tutorial/templates.rst#chars=0:6962
- [执行记录](http://127.0.0.1:18890/?run=int-cc4290eb3ed94f4d&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-cc4290eb3ed94f4d/artifacts/art-7304231df3f04ed0)
- [response_ref](http://127.0.0.1:18890/api/runs/int-cc4290eb3ed94f4d/artifacts/art-76cdb3a1e22742a6)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-cc4290eb3ed94f4d/artifacts/art-77b51665b950466a)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-cc4290eb3ed94f4d/artifacts/art-69e8487b91694b19)

## G032 · flask · 用例契约问题

引用不能在指定文档中唯一定位

- 分类来源：contract-validation
- 定位：R71-index
- 依据文档：docs/tutorial/blog.rst · docs/tutorial/blog.rst#chars=0:9975
- [执行记录](http://127.0.0.1:18890/?run=int-cc4290eb3ed94f4d&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-cc4290eb3ed94f4d/artifacts/art-376506a67a0a400c)
- [response_ref](http://127.0.0.1:18890/api/runs/int-cc4290eb3ed94f4d/artifacts/art-3ac9c4806d8d4409)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-cc4290eb3ed94f4d/artifacts/art-8c4284cc9d814f76)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-cc4290eb3ed94f4d/artifacts/art-02e61164dd4748fa)

## G033 · flask · 环境未就绪

原文明确安装后可在任意目录导入 flaskr；当前执行契约没有构建 wheel 或在独立虚拟环境执行 pip 安装并切换工作目录导入的步骤，离线缓存也不保证提供 flit_core 等构建依赖，因此保留为环境缺口，不能声明导入行为已覆盖。

- 分类来源：model
- 定位：R73-install-import
- 依据文档：docs/tutorial/install.rst · docs/tutorial/install.rst#chars=0:2838
- [执行记录](http://127.0.0.1:18890/?run=int-cc4290eb3ed94f4d&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-cc4290eb3ed94f4d/artifacts/art-376506a67a0a400c)
- [response_ref](http://127.0.0.1:18890/api/runs/int-cc4290eb3ed94f4d/artifacts/art-3ac9c4806d8d4409)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-cc4290eb3ed94f4d/artifacts/art-8c4284cc9d814f76)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-cc4290eb3ed94f4d/artifacts/art-02e61164dd4748fa)

## G034 · flask · 用例契约问题

引用不能在指定文档中唯一定位

- 分类来源：contract-validation
- 定位：d87_hello
- 依据文档：docs/tutorial/tests.rst · docs/tutorial/tests.rst#chars=0:9946
- [执行记录](http://127.0.0.1:18890/?run=int-cc4290eb3ed94f4d&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-cc4290eb3ed94f4d/artifacts/art-823c206fa7f64498)
- [response_ref](http://127.0.0.1:18890/api/runs/int-cc4290eb3ed94f4d/artifacts/art-fbd8f8b6365747ee)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-cc4290eb3ed94f4d/artifacts/art-4275c9bf4d5140e2)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-cc4290eb3ed94f4d/artifacts/art-6e4f3aeb75b14a89)

## G035 · flask · 平台能力不足

D87 要求 db is get_db() 以及退出上下文后执行触发 sqlite3.ProgrammingError 且含 closed；当前 scenario 只有值读取与正向断言，不能表达对象同一性和预期异常，故缺少观察协议。

- 分类来源：model
- 定位：d87_db_get_close
- 依据文档：docs/tutorial/tests.rst · docs/tutorial/tests.rst#chars=0:9946
- [执行记录](http://127.0.0.1:18890/?run=int-cc4290eb3ed94f4d&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-cc4290eb3ed94f4d/artifacts/art-823c206fa7f64498)
- [response_ref](http://127.0.0.1:18890/api/runs/int-cc4290eb3ed94f4d/artifacts/art-fbd8f8b6365747ee)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-cc4290eb3ed94f4d/artifacts/art-4275c9bf4d5140e2)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-cc4290eb3ed94f4d/artifacts/art-6e4f3aeb75b14a89)

## G036 · flask · 平台能力不足

D87 通过 monkeypatch 替换 flaskr.db.init_db 并断言 Recorder.called；当前协议禁止任意脚本或 monkeypatch，无法直接记录该内部调用，缺少调用拦截观察协议。

- 分类来源：model
- 定位：d87_init_db_call
- 依据文档：docs/tutorial/tests.rst · docs/tutorial/tests.rst#chars=0:9946
- [执行记录](http://127.0.0.1:18890/?run=int-cc4290eb3ed94f4d&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-cc4290eb3ed94f4d/artifacts/art-823c206fa7f64498)
- [response_ref](http://127.0.0.1:18890/api/runs/int-cc4290eb3ed94f4d/artifacts/art-fbd8f8b6365747ee)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-cc4290eb3ed94f4d/artifacts/art-4275c9bf4d5140e2)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-cc4290eb3ed94f4d/artifacts/art-6e4f3aeb75b14a89)

## G037 · flask · 用例契约问题

引用不能在指定文档中唯一定位

- 分类来源：contract-validation
- 定位：d103-factory-config
- 依据文档：docs/tutorial/tests.rst · docs/tutorial/tests.rst#chars=9946:18268
- [执行记录](http://127.0.0.1:18890/?run=int-cc4290eb3ed94f4d&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-cc4290eb3ed94f4d/artifacts/art-e6e8ca4b164646d2)
- [response_ref](http://127.0.0.1:18890/api/runs/int-cc4290eb3ed94f4d/artifacts/art-5076628d9b3f45dc)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-cc4290eb3ed94f4d/artifacts/art-dc5c4be9f6ae41b0)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-cc4290eb3ed94f4d/artifacts/art-a6fe9c9262f34af7)

## G038 · flask · 用例契约问题

引用不能在指定文档中唯一定位

- 分类来源：contract-validation
- 定位：d103-init-db-command
- 依据文档：docs/tutorial/tests.rst · docs/tutorial/tests.rst#chars=9946:18268
- [执行记录](http://127.0.0.1:18890/?run=int-cc4290eb3ed94f4d&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-cc4290eb3ed94f4d/artifacts/art-e6e8ca4b164646d2)
- [response_ref](http://127.0.0.1:18890/api/runs/int-cc4290eb3ed94f4d/artifacts/art-5076628d9b3f45dc)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-cc4290eb3ed94f4d/artifacts/art-dc5c4be9f6ae41b0)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-cc4290eb3ed94f4d/artifacts/art-a6fe9c9262f34af7)

## G039 · flask · 用例契约问题

引用不能在指定文档中唯一定位

- 分类来源：contract-validation
- 定位：d103-register-view
- 依据文档：docs/tutorial/tests.rst · docs/tutorial/tests.rst#chars=9946:18268
- [执行记录](http://127.0.0.1:18890/?run=int-cc4290eb3ed94f4d&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-cc4290eb3ed94f4d/artifacts/art-e6e8ca4b164646d2)
- [response_ref](http://127.0.0.1:18890/api/runs/int-cc4290eb3ed94f4d/artifacts/art-5076628d9b3f45dc)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-cc4290eb3ed94f4d/artifacts/art-dc5c4be9f6ae41b0)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-cc4290eb3ed94f4d/artifacts/art-a6fe9c9262f34af7)

## G040 · flask · 用例契约问题

引用不能在指定文档中唯一定位

- 分类来源：contract-validation
- 定位：d103-get-db-lifecycle
- 依据文档：docs/tutorial/tests.rst · docs/tutorial/tests.rst#chars=9946:18268
- [执行记录](http://127.0.0.1:18890/?run=int-cc4290eb3ed94f4d&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-cc4290eb3ed94f4d/artifacts/art-e6e8ca4b164646d2)
- [response_ref](http://127.0.0.1:18890/api/runs/int-cc4290eb3ed94f4d/artifacts/art-5076628d9b3f45dc)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-cc4290eb3ed94f4d/artifacts/art-dc5c4be9f6ae41b0)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-cc4290eb3ed94f4d/artifacts/art-a6fe9c9262f34af7)

## G041 · flask · 平台能力不足

需要把 config.py 写入 create_app() 自动选择的 instance 目录并读回 SECRET_KEY；scenario 只能写入临时工作目录，create_app 未暴露 instance_path 参数，缺少准备该文件并观察配置的协议。

- 分类来源：model
- 定位：d104-secret-config
- 依据文档：docs/tutorial/deploy.rst · docs/tutorial/deploy.rst#chars=0:3699
- [执行记录](http://127.0.0.1:18890/?run=int-cc4290eb3ed94f4d&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-cc4290eb3ed94f4d/artifacts/art-e6e8ca4b164646d2)
- [response_ref](http://127.0.0.1:18890/api/runs/int-cc4290eb3ed94f4d/artifacts/art-5076628d9b3f45dc)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-cc4290eb3ed94f4d/artifacts/art-dc5c4be9f6ae41b0)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-cc4290eb3ed94f4d/artifacts/art-a6fe9c9262f34af7)

## G042 · flask · 环境未就绪

D104 要求以 Waitress 作为生产 WSGI 服务器运行 create_app；当前组件未声明 Waitress 服务或对应端口，进程内测试客户端和开发服务器不能替代该部署行为。

- 分类来源：model
- 定位：d104-waitress-server
- 依据文档：docs/tutorial/deploy.rst · docs/tutorial/deploy.rst#chars=0:3699
- [执行记录](http://127.0.0.1:18890/?run=int-cc4290eb3ed94f4d&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-cc4290eb3ed94f4d/artifacts/art-e6e8ca4b164646d2)
- [response_ref](http://127.0.0.1:18890/api/runs/int-cc4290eb3ed94f4d/artifacts/art-5076628d9b3f45dc)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-cc4290eb3ed94f4d/artifacts/art-dc5c4be9f6ae41b0)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-cc4290eb3ed94f4d/artifacts/art-a6fe9c9262f34af7)

## G043 · flask · 缺少依据

原文只说明该目录代码可供替代 Flask 实现使用，未给出公开类/工厂、调用方式或可观察的正确结果；当前无法为“可复用”设计有依据的输入与预期。

- 分类来源：model
- 定位：sansio-alt-impl
- 依据文档：src/flask/sansio/README.md · src/flask/sansio/README.md#chars=0:229
- [执行记录](http://127.0.0.1:18890/?run=int-cc4290eb3ed94f4d&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-cc4290eb3ed94f4d/artifacts/art-8c3ddad61a424ac0)
- [response_ref](http://127.0.0.1:18890/api/runs/int-cc4290eb3ed94f4d/artifacts/art-e03f602acca94eec)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-cc4290eb3ed94f4d/artifacts/art-a63305869db14c24)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-cc4290eb3ed94f4d/artifacts/art-a4d586f5d82e4281)

## G044 · flask · 平台能力不足

禁止 IO 是架构约束，原文未给出可调用入口或预期输出；要判定代码路径未发生 IO，需要 IO 追踪或静态分析等观察协议，当前 execution_contract 未提供。

- 分类来源：model
- 定位：sansio-no-io
- 依据文档：src/flask/sansio/README.md · src/flask/sansio/README.md#chars=0:229
- [执行记录](http://127.0.0.1:18890/?run=int-cc4290eb3ed94f4d&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-cc4290eb3ed94f4d/artifacts/art-8c3ddad61a424ac0)
- [response_ref](http://127.0.0.1:18890/api/runs/int-cc4290eb3ed94f4d/artifacts/art-e03f602acca94eec)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-cc4290eb3ed94f4d/artifacts/art-a63305869db14c24)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-cc4290eb3ed94f4d/artifacts/art-a4d586f5d82e4281)

## G045 · flask · 平台能力不足

“可能 IO 路径”没有定义边界，也没有可核对的调用链或观察协议；无法确定应调用哪个公开入口以及何种结果能证明未进入 IO 路径。

- 分类来源：model
- 定位：sansio-not-io-path
- 依据文档：src/flask/sansio/README.md · src/flask/sansio/README.md#chars=0:229
- [执行记录](http://127.0.0.1:18890/?run=int-cc4290eb3ed94f4d&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-cc4290eb3ed94f4d/artifacts/art-8c3ddad61a424ac0)
- [response_ref](http://127.0.0.1:18890/api/runs/int-cc4290eb3ed94f4d/artifacts/art-e03f602acca94eec)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-cc4290eb3ed94f4d/artifacts/art-a63305869db14c24)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-cc4290eb3ed94f4d/artifacts/art-a4d586f5d82e4281)

## G046 · flask · 平台能力不足

原文未列出需检查的 Flask 全局名称或可调用入口，当前也没有导入/静态检查协议来确认代码未使用 Flask 全局对象。

- 分类来源：model
- 定位：sansio-no-flask-globals
- 依据文档：src/flask/sansio/README.md · src/flask/sansio/README.md#chars=0:229
- [执行记录](http://127.0.0.1:18890/?run=int-cc4290eb3ed94f4d&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-cc4290eb3ed94f4d/artifacts/art-8c3ddad61a424ac0)
- [response_ref](http://127.0.0.1:18890/api/runs/int-cc4290eb3ed94f4d/artifacts/art-e03f602acca94eec)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-cc4290eb3ed94f4d/artifacts/art-a63305869db14c24)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-cc4290eb3ed94f4d/artifacts/art-a4d586f5d82e4281)

## G047 · flask · 环境未就绪

服务没有在声明端口就绪；只影响此服务依赖的验证

- 分类来源：execution-stage
- 定位：u-0116fba010-service
- [执行记录](http://127.0.0.1:18890/?run=int-cc4290eb3ed94f4d&tab=flow&evidence=run)

## G048 · flask · 待分类

部分用例未完整执行

- 分类来源：execution-stage
- 定位：u-0116fba010-business
- [执行记录](http://127.0.0.1:18890/?run=int-cc4290eb3ed94f4d&tab=flow&evidence=run)
- [task-report](http://127.0.0.1:18890/api/runs/int-cc4290eb3ed94f4d/artifacts/art-c39daabaeea94a00)
- [u-0116fba010-business/cases.json](http://127.0.0.1:18890/api/runs/int-cc4290eb3ed94f4d/artifacts/art-dfa48472b9e1485b)

## G049 · flask · 待分类

该组件没有经过依据校验的业务用例；其他任务继续，缺口保留

- 分类来源：execution-stage
- 定位：u-b6b2594aef-business
- [执行记录](http://127.0.0.1:18890/?run=int-cc4290eb3ed94f4d&tab=flow&evidence=run)

## G050 · flask · 待分类

部分用例未完整执行

- 分类来源：execution-stage
- 定位：u-6d5d23e8a9-business
- [执行记录](http://127.0.0.1:18890/?run=int-cc4290eb3ed94f4d&tab=flow&evidence=run)
- [task-report](http://127.0.0.1:18890/api/runs/int-cc4290eb3ed94f4d/artifacts/art-a57bd1898f364e8c)
- [u-6d5d23e8a9-business/cases.json](http://127.0.0.1:18890/api/runs/int-cc4290eb3ed94f4d/artifacts/art-651693c8feb348b4)

## G051 · sqlite-utils · 缺少依据

D2 只说 --analyze 会对表运行 ANALYZE，未说明可观察的 CLI 输出或业务状态；不能依据实现私有的 sqlite_stat1 表断言，故保留未决。

- 分类来源：model
- 定位：D2-analyze
- 依据文档：docs/cli.rst · docs/cli.rst#chars=32824:38471
- [执行记录](http://127.0.0.1:18890/?run=int-d8e4048aab7a4b92&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-d8e4048aab7a4b92/artifacts/art-799dea49c86c4d89)
- [response_ref](http://127.0.0.1:18890/api/runs/int-d8e4048aab7a4b92/artifacts/art-94f3224308a7459b)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-d8e4048aab7a4b92/artifacts/art-04d2143b2a314a48)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-d8e4048aab7a4b92/artifacts/art-ecdec9a031564cf9)

## G052 · sqlite-utils · 环境未就绪

D3 的 --encoding=latin-1 需要非 UTF-8 字节文件；当前 write_file 只提供文本/UTF-8 夹具，无法构造 latin-1 字节流，故保留未决。

- 分类来源：model
- 定位：D3-encoding
- 依据文档：docs/cli.rst · docs/cli.rst#chars=38471:43638
- [执行记录](http://127.0.0.1:18890/?run=int-d8e4048aab7a4b92&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-d8e4048aab7a4b92/artifacts/art-799dea49c86c4d89)
- [response_ref](http://127.0.0.1:18890/api/runs/int-d8e4048aab7a4b92/artifacts/art-94f3224308a7459b)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-d8e4048aab7a4b92/artifacts/art-04d2143b2a314a48)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-d8e4048aab7a4b92/artifacts/art-ecdec9a031564cf9)

## G053 · sqlite-utils · 缺少依据

D3 只说 --sniff 会“attempt”检测分隔符，未给出保证输出或可核对的固定夹具；显式 --delimiter/--quotechar 已有用例，sniff 检测结果需补充确定输出。

- 分类来源：model
- 定位：D3-sniff
- 依据文档：docs/cli.rst · docs/cli.rst#chars=38471:43638
- [执行记录](http://127.0.0.1:18890/?run=int-d8e4048aab7a4b92&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-d8e4048aab7a4b92/artifacts/art-799dea49c86c4d89)
- [response_ref](http://127.0.0.1:18890/api/runs/int-d8e4048aab7a4b92/artifacts/art-94f3224308a7459b)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-d8e4048aab7a4b92/artifacts/art-04d2143b2a314a48)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-d8e4048aab7a4b92/artifacts/art-ecdec9a031564cf9)

## G054 · sqlite-utils · 平台能力不足

模型响应未完整结束；请求 760512d3-870d-410c-9fc5-d9019055b985

- 分类来源：contract-validation
- 定位：batch-2
- [执行记录](http://127.0.0.1:18890/?run=int-d8e4048aab7a4b92&tab=flow&evidence=run)

## G055 · sqlite-utils · 平台能力不足

列表内容可由 CLI 观察，但“未创建数据库文件或 _sqlite_migrations 表”需要对文件不存在/表不存在的负向文件系统观察；当前 scenario 只声明 stdout/stderr/exit_code 与公开 API 读回，缺少此类负向状态断言协议。

- 分类来源：model
- 定位：migrate-list-read-only
- 依据文档：docs/migrations.rst · docs/migrations.rst#chars=0:7816
- [执行记录](http://127.0.0.1:18890/?run=int-d8e4048aab7a4b92&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-d8e4048aab7a4b92/artifacts/art-f708cf1eef3042fc)
- [response_ref](http://127.0.0.1:18890/api/runs/int-d8e4048aab7a4b92/artifacts/art-035c9aa29e824fac)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-d8e4048aab7a4b92/artifacts/art-23551a78c8064476)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-d8e4048aab7a4b92/artifacts/art-aa4269b54c974ae8)

## G056 · sqlite-utils · 平台能力不足

文档要求迁移函数是接收 Database 的 Python 函数并由 Migrations 注册；当前协议只能写文本文件和调用公开方法，不能定义函数体或把自定义迁移函数注册到 Migrations 实例，缺少可执行接线。

- 分类来源：model
- 定位：migrations-python-api-apply
- 依据文档：docs/migrations.rst · docs/migrations.rst#chars=0:7816
- [执行记录](http://127.0.0.1:18890/?run=int-d8e4048aab7a4b92&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-d8e4048aab7a4b92/artifacts/art-f708cf1eef3042fc)
- [response_ref](http://127.0.0.1:18890/api/runs/int-d8e4048aab7a4b92/artifacts/art-035c9aa29e824fac)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-d8e4048aab7a4b92/artifacts/art-23551a78c8064476)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-d8e4048aab7a4b92/artifacts/art-aa4269b54c974ae8)

## G057 · sqlite-utils · 平台能力不足

需要声明会抛异常的迁移并观察回滚、无记录、先前迁移保持；文档未给出 CLI 退出码或错误输出，当前协议未声明失败步骤后继续执行及负向状态检查，无法形成稳定断言。

- 分类来源：model
- 定位：migrations-transaction-rollback
- 依据文档：docs/migrations.rst · docs/migrations.rst#chars=0:7816
- [执行记录](http://127.0.0.1:18890/?run=int-d8e4048aab7a4b92&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-d8e4048aab7a4b92/artifacts/art-f708cf1eef3042fc)
- [response_ref](http://127.0.0.1:18890/api/runs/int-d8e4048aab7a4b92/artifacts/art-035c9aa29e824fac)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-d8e4048aab7a4b92/artifacts/art-23551a78c8064476)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-d8e4048aab7a4b92/artifacts/art-aa4269b54c974ae8)

## G058 · sqlite-utils · 平台能力不足

文档只说明“退出并报错”，未承诺具体退出码或错误文本；当前协议无法在未知退出码下稳定断言错误，也无法直接证明没有应用后续待迁移。

- 分类来源：model
- 定位：migrate-stop-before-invalid
- 依据文档：docs/migrations.rst · docs/migrations.rst#chars=0:7816
- [执行记录](http://127.0.0.1:18890/?run=int-d8e4048aab7a4b92&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-d8e4048aab7a4b92/artifacts/art-f708cf1eef3042fc)
- [response_ref](http://127.0.0.1:18890/api/runs/int-d8e4048aab7a4b92/artifacts/art-035c9aa29e824fac)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-d8e4048aab7a4b92/artifacts/art-23551a78c8064476)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-d8e4048aab7a4b92/artifacts/art-aa4269b54c974ae8)

## G059 · sqlite-utils · 用例契约问题

CLI预期必须为字符串或明确退出码

- 分类来源：contract-validation
- 定位：plugins-list-empty
- 依据文档：docs/plugins.rst · docs/plugins.rst#chars=0:4608
- [执行记录](http://127.0.0.1:18890/?run=int-d8e4048aab7a4b92&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-d8e4048aab7a4b92/artifacts/art-371f33420d3248c7)
- [response_ref](http://127.0.0.1:18890/api/runs/int-d8e4048aab7a4b92/artifacts/art-493a2474407e4d90)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-d8e4048aab7a4b92/artifacts/art-f4afdb55b3d049ab)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-d8e4048aab7a4b92/artifacts/art-ba20bb5ad87d4f95)

## G060 · sqlite-utils · 待分类

该需求没有经契约校验的可执行用例；具体原因见逐项诊断

- 分类来源：model
- 定位：plugins_json_list
- 依据文档：docs/plugins.rst · docs/plugins.rst#chars=0:4608
- [执行记录](http://127.0.0.1:18890/?run=int-d8e4048aab7a4b92&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-d8e4048aab7a4b92/artifacts/art-371f33420d3248c7)
- [response_ref](http://127.0.0.1:18890/api/runs/int-d8e4048aab7a4b92/artifacts/art-493a2474407e4d90)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-d8e4048aab7a4b92/artifacts/art-f4afdb55b3d049ab)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-d8e4048aab7a4b92/artifacts/art-ba20bb5ad87d4f95)

## G061 · sqlite-utils · 环境未就绪

需要已加载的 register_commands 插件入口点才能执行 hello-world 并读取 Hello world!；当前隔离环境没有可安装或预置的自定义插件夹具。

- 分类来源：model
- 定位：register_commands_hello
- 依据文档：docs/plugins.rst · docs/plugins.rst#chars=0:4608
- [执行记录](http://127.0.0.1:18890/?run=int-d8e4048aab7a4b92&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-d8e4048aab7a4b92/artifacts/art-371f33420d3248c7)
- [response_ref](http://127.0.0.1:18890/api/runs/int-d8e4048aab7a4b92/artifacts/art-493a2474407e4d90)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-d8e4048aab7a4b92/artifacts/art-f4afdb55b3d049ab)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-d8e4048aab7a4b92/artifacts/art-ba20bb5ad87d4f95)

## G062 · sqlite-utils · 环境未就绪

需先安装带 hello-world 命令的插件，才能验证该命令可执行并出现在 --help；当前缺少插件分发、安装和回滚夹具。

- 分类来源：model
- 定位：installed_plugin_command_help
- 依据文档：docs/plugins.rst · docs/plugins.rst#chars=0:4608
- [执行记录](http://127.0.0.1:18890/?run=int-d8e4048aab7a4b92&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-d8e4048aab7a4b92/artifacts/art-371f33420d3248c7)
- [response_ref](http://127.0.0.1:18890/api/runs/int-d8e4048aab7a4b92/artifacts/art-493a2474407e4d90)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-d8e4048aab7a4b92/artifacts/art-f4afdb55b3d049ab)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-d8e4048aab7a4b92/artifacts/art-ba20bb5ad87d4f95)

## G063 · sqlite-utils · 环境未就绪

需安装带 prepare_connection 钩子的插件并建立 Database 连接，才能查询 hello('world') 并观察返回值；平台未提供该插件入口点夹具，无法验证自定义函数注册。

- 分类来源：model
- 定位：prepare_connection_sql_function
- 依据文档：docs/plugins.rst · docs/plugins.rst#chars=0:4608
- [执行记录](http://127.0.0.1:18890/?run=int-d8e4048aab7a4b92&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-d8e4048aab7a4b92/artifacts/art-371f33420d3248c7)
- [response_ref](http://127.0.0.1:18890/api/runs/int-d8e4048aab7a4b92/artifacts/art-493a2474407e4d90)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-d8e4048aab7a4b92/artifacts/art-f4afdb55b3d049ab)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-d8e4048aab7a4b92/artifacts/art-ba20bb5ad87d4f95)

## G064 · sqlite-utils · 环境未就绪

需有能产生可观察连接效果的插件，并用启用/禁用插件的两个 Database 实例对比；当前没有插件入口点夹具，无法证明逐实例生效，也无法观察 execute_plugins=False 的退出效果。

- 分类来源：model
- 定位：prepare_connection_per_database_optout
- 依据文档：docs/plugins.rst · docs/plugins.rst#chars=0:4608
- [执行记录](http://127.0.0.1:18890/?run=int-d8e4048aab7a4b92&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-d8e4048aab7a4b92/artifacts/art-371f33420d3248c7)
- [response_ref](http://127.0.0.1:18890/api/runs/int-d8e4048aab7a4b92/artifacts/art-493a2474407e4d90)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-d8e4048aab7a4b92/artifacts/art-f4afdb55b3d049ab)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-d8e4048aab7a4b92/artifacts/art-ba20bb5ad87d4f95)

## G065 · sqlite-utils · 环境未就绪

该行为位于插件命令内部，需要安装插件、准备 CSV/JSON 输入并执行 show_schema_for_files 才能观察 return_db=True 与 schema 输出；平台不能执行自定义插件代码，也没有对应命令入口。

- 分类来源：model
- 定位：context_invoke_memory_return_db
- 依据文档：docs/plugins.rst · docs/plugins.rst#chars=0:4608
- [执行记录](http://127.0.0.1:18890/?run=int-d8e4048aab7a4b92&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-d8e4048aab7a4b92/artifacts/art-371f33420d3248c7)
- [response_ref](http://127.0.0.1:18890/api/runs/int-d8e4048aab7a4b92/artifacts/art-493a2474407e4d90)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-d8e4048aab7a4b92/artifacts/art-f4afdb55b3d049ab)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-d8e4048aab7a4b92/artifacts/art-ba20bb5ad87d4f95)
