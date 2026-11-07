# D041 r6 逐项覆盖缺口账本

仅整理已终态、完整性验证通过的记录。模型分类仍标明来源；执行错误、缺少依据和未覆盖均不能视为确认产品缺陷。未自动删除语义相近的模型意见，原始条目数不等于不重复需求数或覆盖率。

## G001 · fastify · 平台能力不足

文档规定 callback 接收 (err, address)，但当前 scenario 对带 callback 的 listen 没有可等待的 Promise，也缺少等待回调触发并独立观察 err/address 参数的协议；不能只检查监听端口替代回调参数验收。

- 分类来源：model
- 定位：d2-listen-callback
- 依据文档：docs/Reference/Server.md · docs/Reference/Server.md#chars=41939:45203
- [执行记录](http://127.0.0.1:18890/?run=int-a2544c9302be4123&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-a2544c9302be4123/artifacts/art-21ef10c1510f4fde)
- [response_ref](http://127.0.0.1:18890/api/runs/int-a2544c9302be4123/artifacts/art-58b2c34981804bf5)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-a2544c9302be4123/artifacts/art-e4155b22c9214426)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-a2544c9302be4123/artifacts/art-8912622683df49df)

## G002 · fastify · 平台能力不足

文档要求自定义启动日志文本，但当前执行契约未声明日志流或日志观察协议；无法捕获并比较 listen 成功后实际输出的日志文本，不能把配置了 listenTextResolver 当作覆盖。

- 分类来源：model
- 定位：d2-listen-text-resolver
- 依据文档：docs/Reference/Server.md · docs/Reference/Server.md#chars=41939:45203
- [执行记录](http://127.0.0.1:18890/?run=int-a2544c9302be4123&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-a2544c9302be4123/artifacts/art-21ef10c1510f4fde)
- [response_ref](http://127.0.0.1:18890/api/runs/int-a2544c9302be4123/artifacts/art-58b2c34981804bf5)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-a2544c9302be4123/artifacts/art-e4155b22c9214426)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-a2544c9302be4123/artifacts/art-8912622683df49df)

## G003 · fastify · 环境未就绪

要验证服务器在异步数据库连接完成前不接受连接，需要一个可挂起且可观察完成的连接插件，并在完成前尝试连接。当前 service_graph 无 MongoDB 节点，@fastify/mongodb 未索引，scenario 没有延迟或挂起夹具，无法准备该前置条件。

- 分类来源：model
- 定位：async-connector-before-listen
- 依据文档：docs/Guides/Getting-Started.md · docs/Guides/Getting-Started.md#chars=4967:9913
- [执行记录](http://127.0.0.1:18890/?run=int-a2544c9302be4123&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-a2544c9302be4123/artifacts/art-eaeec93fc57b47b7)
- [response_ref](http://127.0.0.1:18890/api/runs/int-a2544c9302be4123/artifacts/art-d2141082556b4cb9)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-a2544c9302be4123/artifacts/art-29791e8ea2e04a43)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-a2544c9302be4123/artifacts/art-0e48dde9113f448e)

## G004 · fastify · 平台能力不足

需要在两个插件加载过程中记录顺序与前一个完成信号；当前 scenario 回调只能调用公开方法且不能共享可变序列，fastify-plugin 与 skip-override 未索引，无法构造可观察的加载顺序夹具。

- 分类来源：model
- 定位：plugin-order
- 依据文档：docs/Guides/Getting-Started.md · docs/Guides/Getting-Started.md#chars=4967:9913
- [执行记录](http://127.0.0.1:18890/?run=int-a2544c9302be4123&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-a2544c9302be4123/artifacts/art-eaeec93fc57b47b7)
- [response_ref](http://127.0.0.1:18890/api/runs/int-a2544c9302be4123/artifacts/art-d2141082556b4cb9)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-a2544c9302be4123/artifacts/art-29791e8ea2e04a43)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-a2544c9302be4123/artifacts/art-0e48dde9113f448e)

## G005 · fastify · 环境未就绪

该标准依赖 fastify-plugin 包装和 @fastify/mongodb 的 mongo 装饰器；discovery.interfaces 未索引这两个包，service_graph 无 MongoDB，无法注册可用的 dbConnector 并在 routes 插件读取 fastify.mongo。需先准备依赖与服务。

- 分类来源：model
- 定位：fastify-plugin-scope
- 依据文档：docs/Guides/Getting-Started.md · docs/Guides/Getting-Started.md#chars=4967:9913
- [执行记录](http://127.0.0.1:18890/?run=int-a2544c9302be4123&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-a2544c9302be4123/artifacts/art-eaeec93fc57b47b7)
- [response_ref](http://127.0.0.1:18890/api/runs/int-a2544c9302be4123/artifacts/art-d2141082556b4cb9)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-a2544c9302be4123/artifacts/art-29791e8ea2e04a43)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-a2544c9302be4123/artifacts/art-0e48dde9113f448e)

## G006 · fastify · 环境未就绪

需要 MongoDB test_database/test_collection 预置文档、空集合和无匹配 animal 三种状态；当前无 MongoDB 服务与驱动索引，无法播种和读回。文档只给出 throw 错误文本，未给 HTTP 状态与错误响应序列化，观察协议也需先确定。

- 分类来源：model
- 定位：animals-read-routes
- 依据文档：docs/Guides/Getting-Started.md · docs/Guides/Getting-Started.md#chars=4967:9913
- [执行记录](http://127.0.0.1:18890/?run=int-a2544c9302be4123&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-a2544c9302be4123/artifacts/art-eaeec93fc57b47b7)
- [response_ref](http://127.0.0.1:18890/api/runs/int-a2544c9302be4123/artifacts/art-d2141082556b4cb9)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-a2544c9302be4123/artifacts/art-29791e8ea2e04a43)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-a2544c9302be4123/artifacts/art-0e48dde9113f448e)

## G007 · fastify · 缺少依据

文档只给出 body schema 与 insertOne 调用，未规定非法 body 的 HTTP 状态或错误体，也未规定 insertOne 返回结果的可观察结构；同时无 MongoDB 服务与集合夹具。需补充这些输出契约并准备数据库。

- 分类来源：model
- 定位：animals-post-schema
- 依据文档：docs/Guides/Getting-Started.md · docs/Guides/Getting-Started.md#chars=4967:9913
- [执行记录](http://127.0.0.1:18890/?run=int-a2544c9302be4123&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-a2544c9302be4123/artifacts/art-eaeec93fc57b47b7)
- [response_ref](http://127.0.0.1:18890/api/runs/int-a2544c9302be4123/artifacts/art-d2141082556b4cb9)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-a2544c9302be4123/artifacts/art-29791e8ea2e04a43)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-a2544c9302be4123/artifacts/art-0e48dde9113f448e)

## G008 · fastify · 缺少依据

原文只说明使用 JSON Schema 验证请求，未给出不满足 body schema 时的状态码、错误体或可观察处理结果；无法为校验失败设计独立预期。

- 分类来源：model
- 定位：R-D34-validation-failure-gap
- 依据文档：docs/Guides/Getting-Started.md · docs/Guides/Getting-Started.md#chars=9913:14902
- [执行记录](http://127.0.0.1:18890/?run=int-a2544c9302be4123&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-a2544c9302be4123/artifacts/art-ce47d4f74d014c68)
- [response_ref](http://127.0.0.1:18890/api/runs/int-a2544c9302be4123/artifacts/art-c9027d6e8c7b4adc)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-a2544c9302be4123/artifacts/art-f9cf6096397c4e81)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-a2544c9302be4123/artifacts/art-82ed7c3e09c14aaf)

## G009 · fastify · 缺少依据

原文给出推荐加载顺序，但没有规定违反顺序时的错误或可观察结果，无法形成独立通过/失败标准。

- 分类来源：model
- 定位：R-D34-plugin-load-order-gap
- 依据文档：docs/Guides/Getting-Started.md · docs/Guides/Getting-Started.md#chars=9913:14902
- [执行记录](http://127.0.0.1:18890/?run=int-a2544c9302be4123&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-a2544c9302be4123/artifacts/art-ce47d4f74d014c68)
- [response_ref](http://127.0.0.1:18890/api/runs/int-a2544c9302be4123/artifacts/art-c9027d6e8c7b4adc)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-a2544c9302be4123/artifacts/art-f9cf6096397c4e81)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-a2544c9302be4123/artifacts/art-82ed7c3e09c14aaf)

## G010 · fastify · 缺少依据

原文只提出不得破坏打包构建的目标，并提示特性可能表现不同；没有给出具体 bundler 配置、输入样例、构建产物或可观察成功信号，且无 support 文档补足，故无法设计具体正向用例。

- 分类来源：model
- 定位：R1
- 依据文档：test/bundler/README.md · test/bundler/README.md#chars=0:1276
- [执行记录](http://127.0.0.1:18890/?run=int-a2544c9302be4123&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-a2544c9302be4123/artifacts/art-a714d6402eea4d2b)
- [response_ref](http://127.0.0.1:18890/api/runs/int-a2544c9302be4123/artifacts/art-dc622fa901c74cc8)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-a2544c9302be4123/artifacts/art-46082ce8b68e4f0a)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-a2544c9302be4123/artifacts/art-8eda859ce3ac4ad1)

## G011 · fastify · 平台能力不足

这是测试文件命名约定，需要检查仓库文件名并复现 Fastify 单元测试正则命中关系；当前只提供临时目录/隔离仓库的路径观察，缺少目录枚举与正则匹配执行协议，故保留未决。

- 分类来源：model
- 定位：R7
- 依据文档：test/bundler/README.md · test/bundler/README.md#chars=0:1276
- [执行记录](http://127.0.0.1:18890/?run=int-a2544c9302be4123&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-a2544c9302be4123/artifacts/art-a714d6402eea4d2b)
- [response_ref](http://127.0.0.1:18890/api/runs/int-a2544c9302be4123/artifacts/art-dc622fa901c74cc8)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-a2544c9302be4123/artifacts/art-46082ce8b68e4f0a)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-a2544c9302be4123/artifacts/art-8eda859ce3ac4ad1)

## G012 · fastify · 缺少依据

原文只规定测试应验证构建成功和 Fastify 应用可运行，并限定无需深度测试；没有给出具体应用入口、请求/响应或启动成功输出，且无 support 文档补足，无法形成可断言用例。

- 分类来源：model
- 定位：R8
- 依据文档：test/bundler/README.md · test/bundler/README.md#chars=0:1276
- [执行记录](http://127.0.0.1:18890/?run=int-a2544c9302be4123&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-a2544c9302be4123/artifacts/art-a714d6402eea4d2b)
- [response_ref](http://127.0.0.1:18890/api/runs/int-a2544c9302be4123/artifacts/art-dc622fa901c74cc8)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-a2544c9302be4123/artifacts/art-46082ce8b68e4f0a)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-a2544c9302be4123/artifacts/art-8eda859ce3ac4ad1)

## G013 · fastify · 待分类

部分用例未完整执行

- 分类来源：execution-stage
- 定位：u-d935a3cdea-native
- [执行记录](http://127.0.0.1:18890/?run=int-a2544c9302be4123&tab=flow&evidence=run)
- [task-report](http://127.0.0.1:18890/api/runs/int-a2544c9302be4123/artifacts/art-70ee9158feba46b3)

## G014 · fastify · 环境未就绪

依赖安装失败；查看该组件安装日志

- 分类来源：execution-stage
- 定位：u-e3391e5438-prepare
- [执行记录](http://127.0.0.1:18890/?run=int-a2544c9302be4123&tab=flow&evidence=run)

## G015 · fastify · 待分类

仅此分支前置条件未满足：u-e3391e5438-prepare

- 分类来源：execution-stage
- 定位：u-e3391e5438-build
- [执行记录](http://127.0.0.1:18890/?run=int-a2544c9302be4123&tab=flow&evidence=run)

## G016 · fastify · 待分类

仅此分支前置条件未满足：u-e3391e5438-prepare

- 分类来源：execution-stage
- 定位：u-e3391e5438-native
- [执行记录](http://127.0.0.1:18890/?run=int-a2544c9302be4123&tab=flow&evidence=run)

## G017 · fastify · 待分类

B1-d2-listen-default-case · 空 options 时使用随机端口和 localhost：该用例未完整执行，查看逐步原件

- 分类来源：execution-stage
- 定位：B1-d2-listen-default-case
- [执行记录](http://127.0.0.1:18890/?run=int-a2544c9302be4123&tab=flow&evidence=run)
- [task-report](http://127.0.0.1:18890/api/runs/int-a2544c9302be4123/artifacts/art-0982d665a33c41dc)
- [u-d935a3cdea-business/cases.json](http://127.0.0.1:18890/api/runs/int-a2544c9302be4123/artifacts/art-e8292724ef164e11)

## G018 · fastify · 待分类

B1-d2-listen-ready-case · listen 完成时注册插件已 decorate：该用例未完整执行，查看逐步原件

- 分类来源：execution-stage
- 定位：B1-d2-listen-ready-case
- [执行记录](http://127.0.0.1:18890/?run=int-a2544c9302be4123&tab=flow&evidence=run)
- [task-report](http://127.0.0.1:18890/api/runs/int-a2544c9302be4123/artifacts/art-0982d665a33c41dc)
- [u-d935a3cdea-business/cases.json](http://127.0.0.1:18890/api/runs/int-a2544c9302be4123/artifacts/art-e8292724ef164e11)

## G019 · flask · 用例契约问题

1 validation error for Case
journey
  Value error, 最后一次页面操作后必须核对页面结果；不能只核对接口 [type=value_error, input_value={'setup': [{'id': 'app', ...value', 'expected': 6}]}, input_type=dict]
    For further information visit https://errors.pydantic.dev/2.14/v/value_error

- 分类来源：contract-validation
- 定位：C2
- 依据文档：examples/celery/README.md · examples/celery/README.md#chars=0:950
- [执行记录](http://127.0.0.1:18890/?run=int-364f0c4ce50b4ef8&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-364f0c4ce50b4ef8/artifacts/art-9ba0c13a8f70444a)
- [response_ref](http://127.0.0.1:18890/api/runs/int-364f0c4ce50b4ef8/artifacts/art-3ffdb7d3aea2483c)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-364f0c4ce50b4ef8/artifacts/art-82c6d750999347fb)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-364f0c4ce50b4ef8/artifacts/art-6c9fc62afc2f4577)

## G020 · flask · 用例契约问题

用例编号重复

- 分类来源：contract-validation
- 定位：C1
- 依据文档：docs/patterns/celery.rst · docs/patterns/celery.rst#chars=0:4980
- [执行记录](http://127.0.0.1:18890/?run=int-364f0c4ce50b4ef8&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-364f0c4ce50b4ef8/artifacts/art-9ba0c13a8f70444a)
- [response_ref](http://127.0.0.1:18890/api/runs/int-364f0c4ce50b4ef8/artifacts/art-3ffdb7d3aea2483c)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-364f0c4ce50b4ef8/artifacts/art-82c6d750999347fb)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-364f0c4ce50b4ef8/artifacts/art-6c9fc62afc2f4577)

## G021 · flask · 用例契约问题

用例编号重复

- 分类来源：contract-validation
- 定位：C1
- 依据文档：docs/patterns/celery.rst · docs/patterns/celery.rst#chars=0:4980
- [执行记录](http://127.0.0.1:18890/?run=int-364f0c4ce50b4ef8&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-364f0c4ce50b4ef8/artifacts/art-9ba0c13a8f70444a)
- [response_ref](http://127.0.0.1:18890/api/runs/int-364f0c4ce50b4ef8/artifacts/art-3ffdb7d3aea2483c)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-364f0c4ce50b4ef8/artifacts/art-82c6d750999347fb)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-364f0c4ce50b4ef8/artifacts/art-6c9fc62afc2f4577)

## G022 · flask · 平台能力不足

D3 focus 说明 FlaskTask 在 app.app_context() 内运行任务；验证这一点需要调用一个在任务中观察 current_app 或应用上下文的公开任务，但 discovery 未提供可核对的此类任务入口，也不能注入任意任务代码。当前缺少观察协议或公开任务夹具。

- 分类来源：model
- 定位：R6
- 依据文档：docs/patterns/celery.rst · docs/patterns/celery.rst#chars=0:4980
- [执行记录](http://127.0.0.1:18890/?run=int-364f0c4ce50b4ef8&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-364f0c4ce50b4ef8/artifacts/art-9ba0c13a8f70444a)
- [response_ref](http://127.0.0.1:18890/api/runs/int-364f0c4ce50b4ef8/artifacts/art-3ffdb7d3aea2483c)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-364f0c4ce50b4ef8/artifacts/art-82c6d750999347fb)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-364f0c4ce50b4ef8/artifacts/art-6c9fc62afc2f4577)

## G023 · flask · 缺少依据

D6 只给出 Celery 参数序列化与最小数据传递的设计原则，并附 generate_user_archive 伪代码；D5 的 examples/celery 未提供该归档任务或对应路由，无法从现有公开接口确定可执行输入、正确输出或复杂对象应被拒绝的适用条件。

- 分类来源：model
- 定位：req-pass-data
- 依据文档：docs/patterns/celery.rst · docs/patterns/celery.rst#chars=4980:8670
- [执行记录](http://127.0.0.1:18890/?run=int-364f0c4ce50b4ef8&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-364f0c4ce50b4ef8/artifacts/art-16d86c143a824c42)
- [response_ref](http://127.0.0.1:18890/api/runs/int-364f0c4ce50b4ef8/artifacts/art-e8f5576b0dde48ce)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-364f0c4ce50b4ef8/artifacts/art-62e8f46cbb694278)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-364f0c4ce50b4ef8/artifacts/art-2f72a5030ac54823)

## G024 · flask · 缺少依据

D8 只声明演示目标，未给出表单字段、请求路径、JSON 响应结构或提交后的页面可见结果；discovery 中 js_example 的 route_bindings 为空，无法确定浏览器业务验收的正确输出。

- 分类来源：model
- 定位：js_ajax_primary_demo
- 依据文档：examples/javascript/README.rst · examples/javascript/README.rst#chars=0:1086
- [执行记录](http://127.0.0.1:18890/?run=int-364f0c4ce50b4ef8&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-364f0c4ce50b4ef8/artifacts/art-6afe7f72e1cd4af4)
- [response_ref](http://127.0.0.1:18890/api/runs/int-364f0c4ce50b4ef8/artifacts/art-9c686d492aa24c14)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-364f0c4ce50b4ef8/artifacts/art-32d524b0afeb4622)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-364f0c4ce50b4ef8/artifacts/art-64f124a7504e48ed)

## G025 · flask · 缺少依据

D8 未说明三种方式各自对应的 URL、触发控件或响应内容；现有 ui_bindings 只提供静态链接接线，不能作为正确业务输出。

- 分类来源：model
- 定位：js_ajax_three_clients
- 依据文档：examples/javascript/README.rst · examples/javascript/README.rst#chars=0:1086
- [执行记录](http://127.0.0.1:18890/?run=int-364f0c4ce50b4ef8&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-364f0c4ce50b4ef8/artifacts/art-6afe7f72e1cd4af4)
- [response_ref](http://127.0.0.1:18890/api/runs/int-364f0c4ce50b4ef8/artifacts/art-9c686d492aa24c14)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-364f0c4ce50b4ef8/artifacts/art-32d524b0afeb4622)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-364f0c4ce50b4ef8/artifacts/art-64f124a7504e48ed)

## G026 · flask · 缺少依据

D9 只给出 fetch 默认 GET 和 then(response.json()) 的客户端模式，未定义 room_detail 路由、room.id 输入或 JSON 响应内容；js_example 的 route_bindings 为空，无法确定浏览器验收输出。

- 分类来源：model
- 定位：fetch_get_json
- 依据文档：docs/patterns/javascript.rst · docs/patterns/javascript.rst#chars=0:4935
- [执行记录](http://127.0.0.1:18890/?run=int-364f0c4ce50b4ef8&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-364f0c4ce50b4ef8/artifacts/art-6afe7f72e1cd4af4)
- [response_ref](http://127.0.0.1:18890/api/runs/int-364f0c4ce50b4ef8/artifacts/art-9c686d492aa24c14)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-364f0c4ce50b4ef8/artifacts/art-32d524b0afeb4622)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-364f0c4ce50b4ef8/artifacts/art-64f124a7504e48ed)

## G027 · flask · 平台能力不足

D12 给出无效 JSON 返回 400、非 application/json 返回 415 的明确结果，但当前 scenario 协议无法注册会访问 request.json 的视图并观察属性访问抛出的 400/415；缺少可捕获解析失败的公开观察协议。

- 分类来源：model
- 定位：R-json-errors
- 依据文档：docs/patterns/javascript.rst · docs/patterns/javascript.rst#chars=4935:9038
- [执行记录](http://127.0.0.1:18890/?run=int-364f0c4ce50b4ef8&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-364f0c4ce50b4ef8/artifacts/art-eb598df14c4e41e7)
- [response_ref](http://127.0.0.1:18890/api/runs/int-364f0c4ce50b4ef8/artifacts/art-fee8f5f8469e4af8)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-364f0c4ce50b4ef8/artifacts/art-8e72b25dffa4443b)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-364f0c4ce50b4ef8/artifacts/art-d69e69d57a854a29)

## G028 · flask · 缺少依据

D12 描述浏览器端 fetch 重定向处理，但 D11 示例及 discovery 未提供登录/重定向路由、对应页面脚本和提交后页面预期；无法形成真实浏览器业务断言。

- 分类来源：model
- 定位：R-redirect
- 依据文档：docs/patterns/javascript.rst · docs/patterns/javascript.rst#chars=4935:9038
- [执行记录](http://127.0.0.1:18890/?run=int-364f0c4ce50b4ef8&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-364f0c4ce50b4ef8/artifacts/art-eb598df14c4e41e7)
- [response_ref](http://127.0.0.1:18890/api/runs/int-364f0c4ce50b4ef8/artifacts/art-fee8f5f8469e4af8)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-364f0c4ce50b4ef8/artifacts/art-8e72b25dffa4443b)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-364f0c4ce50b4ef8/artifacts/art-d69e69d57a854a29)

## G029 · flask · 缺少依据

D12 展示用响应文本替换 div 的浏览器流程，但 D11 示例未提供 geology-fact 类 div、对应路由及替换后的页面文本预期，缺少适用页面条件与可核对输出。

- 分类来源：model
- 定位：R-replace
- 依据文档：docs/patterns/javascript.rst · docs/patterns/javascript.rst#chars=4935:9038
- [执行记录](http://127.0.0.1:18890/?run=int-364f0c4ce50b4ef8&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-364f0c4ce50b4ef8/artifacts/art-eb598df14c4e41e7)
- [response_ref](http://127.0.0.1:18890/api/runs/int-364f0c4ce50b4ef8/artifacts/art-fee8f5f8469e4af8)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-364f0c4ce50b4ef8/artifacts/art-8e72b25dffa4443b)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-364f0c4ce50b4ef8/artifacts/art-d69e69d57a854a29)

## G030 · flask · 缺少依据

D15 声明作者可编辑或删除自己的帖子，但提供的 blog.rst 片段在 create 视图处截断，缺少 update/delete 的具体输入输出、作者校验和删除后回显依据，无法确定预期。

- 分类来源：model
- 定位：r-d15-edit-delete
- 依据文档：docs/tutorial/index.rst · docs/tutorial/index.rst#chars=0:2061
- [执行记录](http://127.0.0.1:18890/?run=int-364f0c4ce50b4ef8&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-364f0c4ce50b4ef8/artifacts/art-04003e98146f4808)
- [response_ref](http://127.0.0.1:18890/api/runs/int-364f0c4ce50b4ef8/artifacts/art-21e970410d394551)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-364f0c4ce50b4ef8/artifacts/art-f429c8bf5faf429f)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-364f0c4ce50b4ef8/artifacts/art-31efafb2956b45b7)

## G031 · flask · 用例契约问题

引用不能在指定文档中唯一定位

- 分类来源：contract-validation
- 定位：dev-server-startup-excluded
- 依据文档：docs/tutorial/factory.rst · docs/tutorial/factory.rst#chars=4995:5878
- [执行记录](http://127.0.0.1:18890/?run=int-364f0c4ce50b4ef8&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-364f0c4ce50b4ef8/artifacts/art-a73d584a01674110)
- [response_ref](http://127.0.0.1:18890/api/runs/int-364f0c4ce50b4ef8/artifacts/art-cfca3a82ba6247dc)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-364f0c4ce50b4ef8/artifacts/art-628111b828de44ae)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-364f0c4ce50b4ef8/artifacts/art-807af91c56e74192)

## G032 · flask · 用例契约问题

具体HTTP状态码 200 缺少引用原文数值依据；不能将重定向等文字猜成固定状态码

- 分类来源：contract-validation
- 定位：case_base_nav_logged_out
- 依据文档：docs/tutorial/templates.rst · docs/tutorial/templates.rst#chars=0:4961
- [执行记录](http://127.0.0.1:18890/?run=int-364f0c4ce50b4ef8&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-364f0c4ce50b4ef8/artifacts/art-a4401002e47c4b1a)
- [response_ref](http://127.0.0.1:18890/api/runs/int-364f0c4ce50b4ef8/artifacts/art-6fd49791e7544fcb)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-364f0c4ce50b4ef8/artifacts/art-535f4485c8af4e6d)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-364f0c4ce50b4ef8/artifacts/art-6bdce25f721447be)

## G033 · flask · 用例契约问题

具体HTTP状态码 302 缺少引用原文数值依据；不能将重定向等文字猜成固定状态码

- 分类来源：contract-validation
- 定位：case_base_nav_logged_in
- 依据文档：docs/tutorial/templates.rst · docs/tutorial/templates.rst#chars=0:4961
- [执行记录](http://127.0.0.1:18890/?run=int-364f0c4ce50b4ef8&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-364f0c4ce50b4ef8/artifacts/art-a4401002e47c4b1a)
- [response_ref](http://127.0.0.1:18890/api/runs/int-364f0c4ce50b4ef8/artifacts/art-6fd49791e7544fcb)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-364f0c4ce50b4ef8/artifacts/art-535f4485c8af4e6d)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-364f0c4ce50b4ef8/artifacts/art-6bdce25f721447be)

## G034 · flask · 用例契约问题

具体HTTP状态码 200 缺少引用原文数值依据；不能将重定向等文字猜成固定状态码

- 分类来源：contract-validation
- 定位：case_flash_render
- 依据文档：docs/tutorial/templates.rst · docs/tutorial/templates.rst#chars=0:4961
- [执行记录](http://127.0.0.1:18890/?run=int-364f0c4ce50b4ef8&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-364f0c4ce50b4ef8/artifacts/art-a4401002e47c4b1a)
- [response_ref](http://127.0.0.1:18890/api/runs/int-364f0c4ce50b4ef8/artifacts/art-6fd49791e7544fcb)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-364f0c4ce50b4ef8/artifacts/art-535f4485c8af4e6d)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-364f0c4ce50b4ef8/artifacts/art-6bdce25f721447be)

## G035 · flask · 用例契约问题

具体HTTP状态码 200 缺少引用原文数值依据；不能将重定向等文字猜成固定状态码

- 分类来源：contract-validation
- 定位：case_server_validation
- 依据文档：docs/tutorial/templates.rst · docs/tutorial/templates.rst#chars=4961:6962
- [执行记录](http://127.0.0.1:18890/?run=int-364f0c4ce50b4ef8&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-364f0c4ce50b4ef8/artifacts/art-a4401002e47c4b1a)
- [response_ref](http://127.0.0.1:18890/api/runs/int-364f0c4ce50b4ef8/artifacts/art-6fd49791e7544fcb)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-364f0c4ce50b4ef8/artifacts/art-535f4485c8af4e6d)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-364f0c4ce50b4ef8/artifacts/art-6bdce25f721447be)

## G036 · flask · 用例契约问题

具体HTTP状态码 302 缺少引用原文数值依据；不能将重定向等文字猜成固定状态码

- 分类来源：contract-validation
- 定位：case_login_errors
- 依据文档：docs/tutorial/views.rst · docs/tutorial/views.rst#chars=4937:9909
- [执行记录](http://127.0.0.1:18890/?run=int-364f0c4ce50b4ef8&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-364f0c4ce50b4ef8/artifacts/art-a4401002e47c4b1a)
- [response_ref](http://127.0.0.1:18890/api/runs/int-364f0c4ce50b4ef8/artifacts/art-6fd49791e7544fcb)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-364f0c4ce50b4ef8/artifacts/art-535f4485c8af4e6d)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-364f0c4ce50b4ef8/artifacts/art-6bdce25f721447be)

## G037 · flask · 用例契约问题

具体HTTP状态码 302 缺少引用原文数值依据；不能将重定向等文字猜成固定状态码

- 分类来源：contract-validation
- 定位：case_autoescape_duplicate
- 依据文档：docs/tutorial/templates.rst · docs/tutorial/templates.rst#chars=0:4961
- [执行记录](http://127.0.0.1:18890/?run=int-364f0c4ce50b4ef8&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-364f0c4ce50b4ef8/artifacts/art-a4401002e47c4b1a)
- [response_ref](http://127.0.0.1:18890/api/runs/int-364f0c4ce50b4ef8/artifacts/art-6fd49791e7544fcb)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-364f0c4ce50b4ef8/artifacts/art-535f4485c8af4e6d)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-364f0c4ce50b4ef8/artifacts/art-6bdce25f721447be)

## G038 · flask · 缺少依据

文档只泛称 JavaScript 或 logo 等静态文件放在 flaskr/static 并用 url_for('static', filename='...') 引用，未给出具体文件名、内容或可观察预期；当前快照的 flaskr/static 只有 style.css，无法在不修改仓库的前提下构造第二个静态资源并核对引用结果。

- 分类来源：model
- 定位：R-other-static-assets
- 依据文档：docs/tutorial/static.rst · docs/tutorial/static.rst#chars=0:3170
- [执行记录](http://127.0.0.1:18890/?run=int-364f0c4ce50b4ef8&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-364f0c4ce50b4ef8/artifacts/art-243c6fa81fdb482d)
- [response_ref](http://127.0.0.1:18890/api/runs/int-364f0c4ce50b4ef8/artifacts/art-ea344fa4c7284056)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-364f0c4ce50b4ef8/artifacts/art-c87e89b9fa4c4d89)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-364f0c4ce50b4ef8/artifacts/art-f905fed5abe542fb)

## G039 · flask · 平台能力不足

原文要求登录页外观与截图一致，但截图未在文本中提供可比较基线，且执行协议没有视觉/像素比较能力；只能验证页面结构与静态资源链接，无法断言“看起来像截图”这一视觉效果。

- 分类来源：model
- 定位：R-login-visual
- 依据文档：docs/tutorial/static.rst · docs/tutorial/static.rst#chars=0:3170
- [执行记录](http://127.0.0.1:18890/?run=int-364f0c4ce50b4ef8&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-364f0c4ce50b4ef8/artifacts/art-243c6fa81fdb482d)
- [response_ref](http://127.0.0.1:18890/api/runs/int-364f0c4ce50b4ef8/artifacts/art-ea344fa4c7284056)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-364f0c4ce50b4ef8/artifacts/art-c87e89b9fa4c4d89)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-364f0c4ce50b4ef8/artifacts/art-f905fed5abe542fb)

## G040 · flask · 缺少依据

D113 可见开头只说明作者可编辑或删除自己的文章；update/delete 视图和模板段落属于 context_omitted，缺少可核对的表单字段、提交后重定向、删除确认与删除后的页面结果，不能臆测正确输出。待补 D113 的 update/delete 上下文后再设计独立用例。

- 分类来源：model
- 定位：R-AUTHOR-EDIT-DELETE-DETAILS
- 依据文档：docs/tutorial/blog.rst · docs/tutorial/blog.rst#chars=0:4980
- [执行记录](http://127.0.0.1:18890/?run=int-364f0c4ce50b4ef8&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-364f0c4ce50b4ef8/artifacts/art-70cd1df0e40c452a)
- [response_ref](http://127.0.0.1:18890/api/runs/int-364f0c4ce50b4ef8/artifacts/art-a486a8cd6e25410d)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-364f0c4ce50b4ef8/artifacts/art-8b0c80cd9efb4544)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-364f0c4ce50b4ef8/artifacts/art-0fca90847b1d4904)

## G041 · flask · 用例契约问题

引用不能在指定文档中唯一定位

- 分类来源：contract-validation
- 定位：R1_create_post
- 依据文档：docs/tutorial/blog.rst · docs/tutorial/blog.rst#chars=4980:9975
- [执行记录](http://127.0.0.1:18890/?run=int-364f0c4ce50b4ef8&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-364f0c4ce50b4ef8/artifacts/art-cc65994504d84e75)
- [response_ref](http://127.0.0.1:18890/api/runs/int-364f0c4ce50b4ef8/artifacts/art-f27ad8910342431c)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-364f0c4ce50b4ef8/artifacts/art-8f0f617718724da4)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-364f0c4ce50b4ef8/artifacts/art-090d88bc686241f4)

## G042 · flask · 用例契约问题

1 validation error for Case
journey.steps.20
  Value error, 浏览器动作需要CSS定位器 [type=value_error, input_value={'id': 'expect_updated_ti...comparison': 'contains'}, input_type=dict]
    For further information visit https://errors.pydantic.dev/2.14/v/value_error

- 分类来源：contract-validation
- 定位：C2_update_journey
- 依据文档：docs/tutorial/blog.rst · docs/tutorial/blog.rst#chars=4980:9975
- [执行记录](http://127.0.0.1:18890/?run=int-364f0c4ce50b4ef8&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-364f0c4ce50b4ef8/artifacts/art-cc65994504d84e75)
- [response_ref](http://127.0.0.1:18890/api/runs/int-364f0c4ce50b4ef8/artifacts/art-f27ad8910342431c)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-364f0c4ce50b4ef8/artifacts/art-8f0f617718724da4)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-364f0c4ce50b4ef8/artifacts/art-090d88bc686241f4)

## G043 · flask · 平台能力不足

AuthActions 是 tests/conftest.py 中的测试辅助类，当前发现接口未提供该类或 auth fixture 的可调用入口；原文只说用默认 test/test 调用 login，未给出 login/logout 调用本身的独立响应断言。需补充夹具契约或可观察的会话/页面结果后才能设计业务验收。

- 分类来源：model
- 定位：R5
- 依据文档：docs/tutorial/tests.rst · docs/tutorial/tests.rst#chars=4999:9946
- [执行记录](http://127.0.0.1:18890/?run=int-364f0c4ce50b4ef8&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-364f0c4ce50b4ef8/artifacts/art-0661d21f55ab413f)
- [response_ref](http://127.0.0.1:18890/api/runs/int-364f0c4ce50b4ef8/artifacts/art-f4bfec9bce074323)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-364f0c4ce50b4ef8/artifacts/art-813bd4ae186d4c07)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-364f0c4ce50b4ef8/artifacts/art-4a4b9e4d76be4109)

## G044 · flask · 用例契约问题

具体HTTP状态码 200 缺少引用原文数值依据；不能将重定向等文字猜成固定状态码

- 分类来源：contract-validation
- 定位：C5
- 依据文档：docs/tutorial/tests.rst · docs/tutorial/tests.rst#chars=4999:9946
- [执行记录](http://127.0.0.1:18890/?run=int-364f0c4ce50b4ef8&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-364f0c4ce50b4ef8/artifacts/art-0661d21f55ab413f)
- [response_ref](http://127.0.0.1:18890/api/runs/int-364f0c4ce50b4ef8/artifacts/art-f4bfec9bce074323)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-364f0c4ce50b4ef8/artifacts/art-813bd4ae186d4c07)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-364f0c4ce50b4ef8/artifacts/art-4a4b9e4d76be4109)

## G045 · flask · 平台能力不足

D170 要求非作者首页不出现编辑链接，但当前执行协议没有 not_contains 或子串缺失断言，无法在不猜测整页文本的情况下验证该否定条件。

- 分类来源：model
- 定位：no-edit-link
- 依据文档：docs/tutorial/tests.rst · docs/tutorial/tests.rst#chars=9946:14899
- [执行记录](http://127.0.0.1:18890/?run=int-364f0c4ce50b4ef8&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-364f0c4ce50b4ef8/artifacts/art-b2172560a382415e)
- [response_ref](http://127.0.0.1:18890/api/runs/int-364f0c4ce50b4ef8/artifacts/art-3354c8019066405a)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-364f0c4ce50b4ef8/artifacts/art-a007e5118b9b4e9f)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-364f0c4ce50b4ef8/artifacts/art-333c87d5c4a64c7c)

## G046 · flask · 缺少依据

D170 只说无效数据应显示错误信息，但未给出无效输入及具体错误文案，无法确定可核对的页面输出。

- 分类来源：model
- 定位：invalid-data-error
- 依据文档：docs/tutorial/tests.rst · docs/tutorial/tests.rst#chars=9946:14899
- [执行记录](http://127.0.0.1:18890/?run=int-364f0c4ce50b4ef8&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-364f0c4ce50b4ef8/artifacts/art-b2172560a382415e)
- [response_ref](http://127.0.0.1:18890/api/runs/int-364f0c4ce50b4ef8/artifacts/art-3354c8019066405a)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-364f0c4ce50b4ef8/artifacts/art-a007e5118b9b4e9f)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-364f0c4ce50b4ef8/artifacts/art-333c87d5c4a64c7c)

## G047 · flask · 平台能力不足

需要执行 python -m build --wheel 并检查 dist/flaskr-1.0.0-py3-none-any.whl 产物，但平台 cli_commands 未声明 build/python 构建入口，缺少执行与产物观察协议。

- 分类来源：model
- 定位：build-wheel-artifact
- 依据文档：docs/tutorial/deploy.rst · docs/tutorial/deploy.rst#chars=0:3699
- [执行记录](http://127.0.0.1:18890/?run=int-364f0c4ce50b4ef8&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-364f0c4ce50b4ef8/artifacts/art-9ed11ef3b05c4612)
- [response_ref](http://127.0.0.1:18890/api/runs/int-364f0c4ce50b4ef8/artifacts/art-ada6c42311a84459)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-364f0c4ce50b4ef8/artifacts/art-a48991b2daa54ef1)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-364f0c4ce50b4ef8/artifacts/art-4d9e7b43194d4599)

## G048 · flask · 环境未就绪

需先构建并安装 wheel 到独立虚拟环境，再运行 flask --app flaskr init-db 并核对 .venv/var/flaskr-instance 中的数据库文件；平台未准备 wheel 安装后的非 editable 实例环境。

- 分类来源：model
- 定位：installed-init-db-instance-path
- 依据文档：docs/tutorial/deploy.rst · docs/tutorial/deploy.rst#chars=0:3699
- [执行记录](http://127.0.0.1:18890/?run=int-364f0c4ce50b4ef8&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-364f0c4ce50b4ef8/artifacts/art-9ed11ef3b05c4612)
- [response_ref](http://127.0.0.1:18890/api/runs/int-364f0c4ce50b4ef8/artifacts/art-ada6c42311a84459)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-364f0c4ce50b4ef8/artifacts/art-a48991b2daa54ef1)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-364f0c4ce50b4ef8/artifacts/art-4d9e7b43194d4599)

## G049 · flask · 平台能力不足

需要将 config.py 写入部署实例文件夹并重新调用 create_app 读取 SECRET_KEY；当前场景写文件路径不能引用动态 app.instance_path，且不能修改仓库实例目录，缺少该配置读取的观察协议。

- 分类来源：model
- 定位：config-secret-key-file
- 依据文档：docs/tutorial/deploy.rst · docs/tutorial/deploy.rst#chars=0:3699
- [执行记录](http://127.0.0.1:18890/?run=int-364f0c4ce50b4ef8&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-364f0c4ce50b4ef8/artifacts/art-9ed11ef3b05c4612)
- [response_ref](http://127.0.0.1:18890/api/runs/int-364f0c4ce50b4ef8/artifacts/art-ada6c42311a84459)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-364f0c4ce50b4ef8/artifacts/art-a48991b2daa54ef1)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-364f0c4ce50b4ef8/artifacts/art-4d9e7b43194d4599)

## G050 · flask · 环境未就绪

需要 waitress 依赖和可访问的部署服务来执行 waitress-serve --call 'flaskr:create_app' 并观察 HTTP 行为；平台 service_graph 未声明 waitress 节点，也未准备该长驻生产服务。

- 分类来源：model
- 定位：waitress-production-server
- 依据文档：docs/tutorial/deploy.rst · docs/tutorial/deploy.rst#chars=0:3699
- [执行记录](http://127.0.0.1:18890/?run=int-364f0c4ce50b4ef8&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-364f0c4ce50b4ef8/artifacts/art-9ed11ef3b05c4612)
- [response_ref](http://127.0.0.1:18890/api/runs/int-364f0c4ce50b4ef8/artifacts/art-ada6c42311a84459)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-364f0c4ce50b4ef8/artifacts/art-a48991b2daa54ef1)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-364f0c4ce50b4ef8/artifacts/art-4d9e7b43194d4599)

## G051 · flask · 平台能力不足

文档仅声明该目录代码可供 Quart 等替代实现使用，未给出替代实现的公开接入入口、调用参数和可观察输出；当前发现结果也没有 Quart 适配器或兼容性观察协议，无法形成真实替代实现的验收用例。

- 分类来源：model
- 定位：R1
- 依据文档：src/flask/sansio/README.md · src/flask/sansio/README.md#chars=0:229
- [执行记录](http://127.0.0.1:18890/?run=int-364f0c4ce50b4ef8&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-364f0c4ce50b4ef8/artifacts/art-7ac004a4c6594c15)
- [response_ref](http://127.0.0.1:18890/api/runs/int-364f0c4ce50b4ef8/artifacts/art-124e4ad9d1814950)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-364f0c4ce50b4ef8/artifacts/art-7e640dc364524743)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-364f0c4ce50b4ef8/artifacts/art-8750630953c24518)

## G052 · flask · 平台能力不足

文档禁止该目录代码执行任何 IO，但未提供文件、网络或流操作的监控清单，也没有 IO 调用追踪协议；仅导入模块或调用普通函数不能证明整个目录无 IO，缺少执行观察契约。

- 分类来源：model
- 定位：R2
- 依据文档：src/flask/sansio/README.md · src/flask/sansio/README.md#chars=0:229
- [执行记录](http://127.0.0.1:18890/?run=int-364f0c4ce50b4ef8&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-364f0c4ce50b4ef8/artifacts/art-7ac004a4c6594c15)
- [response_ref](http://127.0.0.1:18890/api/runs/int-364f0c4ce50b4ef8/artifacts/art-124e4ad9d1814950)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-364f0c4ce50b4ef8/artifacts/art-7e640dc364524743)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-364f0c4ce50b4ef8/artifacts/art-8750630953c24518)

## G053 · flask · 缺少依据

文档未界定“likely IO path”的依赖规则、允许的导入关系或判定标准，也没有依赖图观察协议，无法确定哪些调用图或依赖边属于违规路径。

- 分类来源：model
- 定位：R3
- 依据文档：src/flask/sansio/README.md · src/flask/sansio/README.md#chars=0:229
- [执行记录](http://127.0.0.1:18890/?run=int-364f0c4ce50b4ef8&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-364f0c4ce50b4ef8/artifacts/art-7ac004a4c6594c15)
- [response_ref](http://127.0.0.1:18890/api/runs/int-364f0c4ce50b4ef8/artifacts/art-124e4ad9d1814950)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-364f0c4ce50b4ef8/artifacts/art-7e640dc364524743)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-364f0c4ce50b4ef8/artifacts/art-8750630953c24518)

## G054 · flask · 平台能力不足

文档禁止使用 Flask globals，但未列出需检查的 globals 范围、访问检测方式或脱离应用与请求上下文的公开断言；现有协议不能观察跨模块的全局访问，无法证明不存在使用。

- 分类来源：model
- 定位：R4
- 依据文档：src/flask/sansio/README.md · src/flask/sansio/README.md#chars=0:229
- [执行记录](http://127.0.0.1:18890/?run=int-364f0c4ce50b4ef8&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-364f0c4ce50b4ef8/artifacts/art-7ac004a4c6594c15)
- [response_ref](http://127.0.0.1:18890/api/runs/int-364f0c4ce50b4ef8/artifacts/art-124e4ad9d1814950)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-364f0c4ce50b4ef8/artifacts/art-7e640dc364524743)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-364f0c4ce50b4ef8/artifacts/art-8750630953c24518)

## G055 · flask · 用例契约问题

B3-result-poll-flow · 首页表单提交任务并轮询结果接口：该用例未完整执行，查看逐步原件

- 分类来源：execution-stage
- 定位：B3-result-poll-flow
- [执行记录](http://127.0.0.1:18890/?run=int-364f0c4ce50b4ef8&tab=flow&evidence=run)
- [task-report](http://127.0.0.1:18890/api/runs/int-364f0c4ce50b4ef8/artifacts/art-5140c0563edc4597)
- [u-0116fba010-business/cases.json](http://127.0.0.1:18890/api/runs/int-364f0c4ce50b4ef8/artifacts/art-eb0fbe88b0c34358)

## G056 · flask · 待分类

该组件没有经过依据校验的业务用例；其他任务继续，缺口保留

- 分类来源：execution-stage
- 定位：u-b6b2594aef-business
- [执行记录](http://127.0.0.1:18890/?run=int-364f0c4ce50b4ef8&tab=flow&evidence=run)

## G057 · flask · 待分类

B8-getdb-rowfactory · get_db 返回可按列名读取的连接且 DATABASE 指向 instance 下的 flaskr.sqlite：该用例未完整执行，查看逐步原件

- 分类来源：execution-stage
- 定位：B8-getdb-rowfactory
- [执行记录](http://127.0.0.1:18890/?run=int-364f0c4ce50b4ef8&tab=flow&evidence=run)
- [task-report](http://127.0.0.1:18890/api/runs/int-364f0c4ce50b4ef8/artifacts/art-b91bee8d336545ca)
- [u-6d5d23e8a9-business/cases.json](http://127.0.0.1:18890/api/runs/int-364f0c4ce50b4ef8/artifacts/art-da6fc6a4d7ed4f4c)

## G058 · flask · 待分类

B8-timestamp-converter · 读取 post.created 后可取得 datetime 的 year 属性：该用例未完整执行，查看逐步原件

- 分类来源：execution-stage
- 定位：B8-timestamp-converter
- [执行记录](http://127.0.0.1:18890/?run=int-364f0c4ce50b4ef8&tab=flow&evidence=run)
- [task-report](http://127.0.0.1:18890/api/runs/int-364f0c4ce50b4ef8/artifacts/art-b91bee8d336545ca)
- [u-6d5d23e8a9-business/cases.json](http://127.0.0.1:18890/api/runs/int-364f0c4ce50b4ef8/artifacts/art-da6fc6a4d7ed4f4c)

## G059 · flask · 待分类

B9-register-insert-redirect-scenario · 有效注册返回登录页重定向且数据库可读回用户：该用例未完整执行，查看逐步原件

- 分类来源：execution-stage
- 定位：B9-register-insert-redirect-scenario
- [执行记录](http://127.0.0.1:18890/?run=int-364f0c4ce50b4ef8&tab=flow&evidence=run)
- [task-report](http://127.0.0.1:18890/api/runs/int-364f0c4ce50b4ef8/artifacts/art-b91bee8d336545ca)
- [u-6d5d23e8a9-business/cases.json](http://127.0.0.1:18890/api/runs/int-364f0c4ce50b4ef8/artifacts/art-da6fc6a4d7ed4f4c)

## G060 · flask · 用例契约问题

B9-register-duplicate-scenario · 同一用户名第二次注册返回已注册错误文本：声明的观察字段或比较协议不可用

- 分类来源：execution-stage
- 定位：B9-register-duplicate-scenario
- [执行记录](http://127.0.0.1:18890/?run=int-364f0c4ce50b4ef8&tab=flow&evidence=run)
- [task-report](http://127.0.0.1:18890/api/runs/int-364f0c4ce50b4ef8/artifacts/art-b91bee8d336545ca)
- [u-6d5d23e8a9-business/cases.json](http://127.0.0.1:18890/api/runs/int-364f0c4ce50b4ef8/artifacts/art-da6fc6a4d7ed4f4c)

## G061 · flask · 待分类

B9-register-password-hash-scenario · 注册后读回密码字段不为明文 secret：该用例未完整执行，查看逐步原件

- 分类来源：execution-stage
- 定位：B9-register-password-hash-scenario
- [执行记录](http://127.0.0.1:18890/?run=int-364f0c4ce50b4ef8&tab=flow&evidence=run)
- [task-report](http://127.0.0.1:18890/api/runs/int-364f0c4ce50b4ef8/artifacts/art-b91bee8d336545ca)
- [u-6d5d23e8a9-business/cases.json](http://127.0.0.1:18890/api/runs/int-364f0c4ce50b4ef8/artifacts/art-da6fc6a4d7ed4f4c)

## G062 · flask · 用例契约问题

B10-login_errors · 错误用户名与错误密码提示：该用例未完整执行，查看逐步原件

- 分类来源：execution-stage
- 定位：B10-login_errors
- [执行记录](http://127.0.0.1:18890/?run=int-364f0c4ce50b4ef8&tab=flow&evidence=run)
- [task-report](http://127.0.0.1:18890/api/runs/int-364f0c4ce50b4ef8/artifacts/art-b91bee8d336545ca)
- [u-6d5d23e8a9-business/cases.json](http://127.0.0.1:18890/api/runs/int-364f0c4ce50b4ef8/artifacts/art-da6fc6a4d7ed4f4c)

## G063 · flask · 用例契约问题

B10-login_required_flow · 未登录访问创建页被重定向，登录后可访问：该用例未完整执行，查看逐步原件

- 分类来源：execution-stage
- 定位：B10-login_required_flow
- [执行记录](http://127.0.0.1:18890/?run=int-364f0c4ce50b4ef8&tab=flow&evidence=run)
- [task-report](http://127.0.0.1:18890/api/runs/int-364f0c4ce50b4ef8/artifacts/art-b91bee8d336545ca)
- [u-6d5d23e8a9-business/cases.json](http://127.0.0.1:18890/api/runs/int-364f0c4ce50b4ef8/artifacts/art-da6fc6a4d7ed4f4c)

## G064 · flask · 用例契约问题

B11-case_register_form · 访问注册页看到标题、必需字段和注册按钮：该用例未完整执行，查看逐步原件

- 分类来源：execution-stage
- 定位：B11-case_register_form
- [执行记录](http://127.0.0.1:18890/?run=int-364f0c4ce50b4ef8&tab=flow&evidence=run)
- [task-report](http://127.0.0.1:18890/api/runs/int-364f0c4ce50b4ef8/artifacts/art-b91bee8d336545ca)
- [u-6d5d23e8a9-business/cases.json](http://127.0.0.1:18890/api/runs/int-364f0c4ce50b4ef8/artifacts/art-da6fc6a4d7ed4f4c)

## G065 · flask · 用例契约问题

B11-case_login_form · 访问登录页看到标题、必需字段和登录按钮：该用例未完整执行，查看逐步原件

- 分类来源：execution-stage
- 定位：B11-case_login_form
- [执行记录](http://127.0.0.1:18890/?run=int-364f0c4ce50b4ef8&tab=flow&evidence=run)
- [task-report](http://127.0.0.1:18890/api/runs/int-364f0c4ce50b4ef8/artifacts/art-b91bee8d336545ca)
- [u-6d5d23e8a9-business/cases.json](http://127.0.0.1:18890/api/runs/int-364f0c4ce50b4ef8/artifacts/art-da6fc6a4d7ed4f4c)

## G066 · flask · 用例契约问题

B11-case_register_redirect · 提交有效注册表单后跳转到登录页：该用例未完整执行，查看逐步原件

- 分类来源：execution-stage
- 定位：B11-case_register_redirect
- [执行记录](http://127.0.0.1:18890/?run=int-364f0c4ce50b4ef8&tab=flow&evidence=run)
- [task-report](http://127.0.0.1:18890/api/runs/int-364f0c4ce50b4ef8/artifacts/art-b91bee8d336545ca)
- [u-6d5d23e8a9-business/cases.json](http://127.0.0.1:18890/api/runs/int-364f0c4ce50b4ef8/artifacts/art-da6fc6a4d7ed4f4c)

## G067 · flask · 用例契约问题

B13-C-CREATE-UNAUTH-REDIRECT · 未登录访问 /create 重定向到登录页：该用例未完整执行，查看逐步原件

- 分类来源：execution-stage
- 定位：B13-C-CREATE-UNAUTH-REDIRECT
- [执行记录](http://127.0.0.1:18890/?run=int-364f0c4ce50b4ef8&tab=flow&evidence=run)
- [task-report](http://127.0.0.1:18890/api/runs/int-364f0c4ce50b4ef8/artifacts/art-b91bee8d336545ca)
- [u-6d5d23e8a9-business/cases.json](http://127.0.0.1:18890/api/runs/int-364f0c4ce50b4ef8/artifacts/art-da6fc6a4d7ed4f4c)

## G068 · flask · 待分类

B16-C4 · init-db 输出 Initialized 并创建 user 表：该用例未完整执行，查看逐步原件

- 分类来源：execution-stage
- 定位：B16-C4
- [执行记录](http://127.0.0.1:18890/?run=int-364f0c4ce50b4ef8&tab=flow&evidence=run)
- [task-report](http://127.0.0.1:18890/api/runs/int-364f0c4ce50b4ef8/artifacts/art-b91bee8d336545ca)
- [u-6d5d23e8a9-business/cases.json](http://127.0.0.1:18890/api/runs/int-364f0c4ce50b4ef8/artifacts/art-da6fc6a4d7ed4f4c)

## G069 · flask · 待分类

B17-login-success-case · 成功登录后重定向并写入会话：该用例未完整执行，查看逐步原件

- 分类来源：execution-stage
- 定位：B17-login-success-case
- [执行记录](http://127.0.0.1:18890/?run=int-364f0c4ce50b4ef8&tab=flow&evidence=run)
- [task-report](http://127.0.0.1:18890/api/runs/int-364f0c4ce50b4ef8/artifacts/art-b91bee8d336545ca)
- [u-6d5d23e8a9-business/cases.json](http://127.0.0.1:18890/api/runs/int-364f0c4ce50b4ef8/artifacts/art-da6fc6a4d7ed4f4c)

## G070 · sqlite-utils · 平台能力不足

原文说明可将第一个 sqlite-utils 查询的 --nl 输出通过管道传给第二个 insert；当前执行契约没有 shell/管道步骤，也不能把 cli 步骤 stdout 直接作为后续 stdin，且原示例依赖外部 sf-trees.db。仅当前协议缺管道编排能力，不能断言仓库无其他依据。

- 分类来源：model
- 定位：d2-pipe-composition
- 依据文档：docs/cli.rst · docs/cli.rst#chars=32824:37727
- [执行记录](http://127.0.0.1:18890/?run=int-fe2b255558a6465f&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-fe2b255558a6465f/artifacts/art-c90449649cee40eb)
- [response_ref](http://127.0.0.1:18890/api/runs/int-fe2b255558a6465f/artifacts/art-fc12a766f357452c)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-fe2b255558a6465f/artifacts/art-c971dc1175d64dee)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-fe2b255558a6465f/artifacts/art-1c148562a67447c8)

## G071 · sqlite-utils · 缺少依据

原文只说明 --analyze 会在插入后运行 ANALYZE，没有给出可核对的输出或指定的 sqlite_stat1 断言；缺少正确输出与观察协议，不能仅凭实现猜测分析结果。

- 分类来源：model
- 定位：d2-analyze-option
- 依据文档：docs/cli.rst · docs/cli.rst#chars=32824:37727
- [执行记录](http://127.0.0.1:18890/?run=int-fe2b255558a6465f&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-fe2b255558a6465f/artifacts/art-c90449649cee40eb)
- [response_ref](http://127.0.0.1:18890/api/runs/int-fe2b255558a6465f/artifacts/art-fc12a766f357452c)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-fe2b255558a6465f/artifacts/art-c971dc1175d64dee)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-fe2b255558a6465f/artifacts/art-1c148562a67447c8)

## G072 · sqlite-utils · 用例契约问题

引用不能在指定文档中唯一定位

- 分类来源：contract-validation
- 定位：R7
- 依据文档：docs/cli.rst · docs/cli.rst#chars=38471:43379
- [执行记录](http://127.0.0.1:18890/?run=int-fe2b255558a6465f&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-fe2b255558a6465f/artifacts/art-242fd65bad104251)
- [response_ref](http://127.0.0.1:18890/api/runs/int-fe2b255558a6465f/artifacts/art-261bd9d72f784506)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-fe2b255558a6465f/artifacts/art-5039f7b573044068)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-fe2b255558a6465f/artifacts/art-676c9372c0d745dc)

## G073 · sqlite-utils · 平台能力不足

D15 说明进度条显示及 --silent 隐藏，但未定义进度条文本、输出流和出现条件；CLI 回执虽含 stdout/stderr，仍缺稳定观察协议，无法可靠断言显示或隐藏。

- 分类来源：model
- 定位：R18
- 依据文档：docs/cli.rst · docs/cli.rst#chars=38471:43379
- [执行记录](http://127.0.0.1:18890/?run=int-fe2b255558a6465f&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-fe2b255558a6465f/artifacts/art-242fd65bad104251)
- [response_ref](http://127.0.0.1:18890/api/runs/int-fe2b255558a6465f/artifacts/art-261bd9d72f784506)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-fe2b255558a6465f/artifacts/art-5039f7b573044068)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-fe2b255558a6465f/artifacts/art-676c9372c0d745dc)

## G074 · sqlite-utils · 用例契约问题

CLI预期必须为字符串或明确退出码

- 分类来源：contract-validation
- 定位：mem-direct-sql-case
- 依据文档：docs/cli.rst · docs/cli.rst#chars=11600:16561
- [执行记录](http://127.0.0.1:18890/?run=int-fe2b255558a6465f&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-fe2b255558a6465f/artifacts/art-aa0133cbfe8c442e)
- [response_ref](http://127.0.0.1:18890/api/runs/int-fe2b255558a6465f/artifacts/art-b5ad3e63e78a4041)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-fe2b255558a6465f/artifacts/art-5322cd6009f44a00)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-fe2b255558a6465f/artifacts/art-3058fc8ad25646f0)

## G075 · sqlite-utils · 用例契约问题

CLI预期必须为字符串或明确退出码

- 分类来源：contract-validation
- 定位：mem-stdin-t1-case
- 依据文档：docs/cli.rst · docs/cli.rst#chars=11600:16561
- [执行记录](http://127.0.0.1:18890/?run=int-fe2b255558a6465f&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-fe2b255558a6465f/artifacts/art-aa0133cbfe8c442e)
- [response_ref](http://127.0.0.1:18890/api/runs/int-fe2b255558a6465f/artifacts/art-b5ad3e63e78a4041)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-fe2b255558a6465f/artifacts/art-5322cd6009f44a00)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-fe2b255558a6465f/artifacts/art-3058fc8ad25646f0)

## G076 · sqlite-utils · 用例契约问题

CLI文本字段需要字符串预期或json_stream比较

- 分类来源：contract-validation
- 定位：fts5-default
- 依据文档：docs/cli.rst · docs/cli.rst#chars=88191:89984
- [执行记录](http://127.0.0.1:18890/?run=int-fe2b255558a6465f&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-fe2b255558a6465f/artifacts/art-60e11d644672413e)
- [response_ref](http://127.0.0.1:18890/api/runs/int-fe2b255558a6465f/artifacts/art-8d6b802f6ffc41c0)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-fe2b255558a6465f/artifacts/art-c1561527d3794890)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-fe2b255558a6465f/artifacts/art-894cba4f25e34b6a)

## G077 · sqlite-utils · 用例契约问题

CLI文本字段需要字符串预期或json_stream比较

- 分类来源：contract-validation
- 定位：fts4-option
- 依据文档：docs/cli.rst · docs/cli.rst#chars=88191:89984
- [执行记录](http://127.0.0.1:18890/?run=int-fe2b255558a6465f&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-fe2b255558a6465f/artifacts/art-60e11d644672413e)
- [response_ref](http://127.0.0.1:18890/api/runs/int-fe2b255558a6465f/artifacts/art-8d6b802f6ffc41c0)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-fe2b255558a6465f/artifacts/art-c1561527d3794890)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-fe2b255558a6465f/artifacts/art-894cba4f25e34b6a)

## G078 · sqlite-utils · 用例契约问题

CLI文本字段需要字符串预期或json_stream比较

- 分类来源：contract-validation
- 定位：fts-create-triggers-case
- 依据文档：docs/cli.rst · docs/cli.rst#chars=88191:89984
- [执行记录](http://127.0.0.1:18890/?run=int-fe2b255558a6465f&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-fe2b255558a6465f/artifacts/art-60e11d644672413e)
- [response_ref](http://127.0.0.1:18890/api/runs/int-fe2b255558a6465f/artifacts/art-8d6b802f6ffc41c0)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-fe2b255558a6465f/artifacts/art-c1561527d3794890)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-fe2b255558a6465f/artifacts/art-894cba4f25e34b6a)

## G079 · sqlite-utils · 平台能力不足

需要证明 enable-fts 初始化索引及 populate-fts 补录后续文档，但聚焦章节未给出查询 FTS 索引内容或 search 回执的公开输出，当前无法对索引命中做独立断言。

- 分类来源：model
- 定位：fts-populate
- 依据文档：docs/cli.rst · docs/cli.rst#chars=88191:89984
- [执行记录](http://127.0.0.1:18890/?run=int-fe2b255558a6465f&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-fe2b255558a6465f/artifacts/art-60e11d644672413e)
- [response_ref](http://127.0.0.1:18890/api/runs/int-fe2b255558a6465f/artifacts/art-8d6b802f6ffc41c0)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-fe2b255558a6465f/artifacts/art-c1561527d3794890)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-fe2b255558a6465f/artifacts/art-894cba4f25e34b6a)

## G080 · sqlite-utils · 平台能力不足

需要确认 --tokenize=porter 的 tokenizer 生效，但聚焦章节未给出索引 schema 或检索结果等可观察输出。

- 分类来源：model
- 定位：fts-tokenize
- 依据文档：docs/cli.rst · docs/cli.rst#chars=88191:89984
- [执行记录](http://127.0.0.1:18890/?run=int-fe2b255558a6465f&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-fe2b255558a6465f/artifacts/art-60e11d644672413e)
- [response_ref](http://127.0.0.1:18890/api/runs/int-fe2b255558a6465f/artifacts/art-8d6b802f6ffc41c0)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-fe2b255558a6465f/artifacts/art-c1561527d3794890)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-fe2b255558a6465f/artifacts/art-894cba4f25e34b6a)

## G081 · sqlite-utils · 平台能力不足

需要确认 rebuild-fts 重建索引，但聚焦章节未给出重建前后可查询的索引状态或输出。

- 分类来源：model
- 定位：fts-rebuild
- 依据文档：docs/cli.rst · docs/cli.rst#chars=88191:89984
- [执行记录](http://127.0.0.1:18890/?run=int-fe2b255558a6465f&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-fe2b255558a6465f/artifacts/art-60e11d644672413e)
- [response_ref](http://127.0.0.1:18890/api/runs/int-fe2b255558a6465f/artifacts/art-8d6b802f6ffc41c0)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-fe2b255558a6465f/artifacts/art-c1561527d3794890)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-fe2b255558a6465f/artifacts/art-894cba4f25e34b6a)

## G082 · sqlite-utils · 平台能力不足

进度条是否显示依赖交互式终端或专用进度输出观察；当前 CLI 回执只有 stdout/stderr，非 TTY 执行无法据此证明进度条未显示，缺少可核对的观察协议。

- 分类来源：model
- 定位：extract-silent-progress
- 依据文档：docs/cli.rst · docs/cli.rst#chars=76858:80659
- [执行记录](http://127.0.0.1:18890/?run=int-fe2b255558a6465f&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-fe2b255558a6465f/artifacts/art-38e94c6fe7e8440a)
- [response_ref](http://127.0.0.1:18890/api/runs/int-fe2b255558a6465f/artifacts/art-015770d6fac345ff)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-fe2b255558a6465f/artifacts/art-110fd904e0e34659)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-fe2b255558a6465f/artifacts/art-efaccdc6fafb403c)

## G083 · sqlite-utils · 用例契约问题

1 validation error for Case
flow
  Value error, 回调须选择return或return_undefined:true，不能同时指定 [type=value_error, input_value={'version': 1, 'steps': [..., {'name': 'weight'}]}]}, input_type=dict]
    For further information visit https://errors.pydantic.dev/2.14/v/value_error

- 分类来源：contract-validation
- 定位：python-apply-order-repeat
- 依据文档：docs/migrations.rst · docs/migrations.rst#chars=0:4982
- [执行记录](http://127.0.0.1:18890/?run=int-fe2b255558a6465f&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-fe2b255558a6465f/artifacts/art-7fa765b51b4b47f9)
- [response_ref](http://127.0.0.1:18890/api/runs/int-fe2b255558a6465f/artifacts/art-6188da70b3804f49)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-fe2b255558a6465f/artifacts/art-be53c4a8ffd340b8)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-fe2b255558a6465f/artifacts/art-a0c0b9a7a5a04878)

## G084 · sqlite-utils · 用例契约问题

1 validation error for Case
flow
  Value error, 回调须选择return或return_undefined:true，不能同时指定 [type=value_error, input_value={'version': 1, 'steps': [..., {'name': 'weight'}]}]}, input_type=dict]
    For further information visit https://errors.pydantic.dev/2.14/v/value_error

- 分类来源：contract-validation
- 定位：python-stop-before
- 依据文档：docs/migrations.rst · docs/migrations.rst#chars=0:4982
- [执行记录](http://127.0.0.1:18890/?run=int-fe2b255558a6465f&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-fe2b255558a6465f/artifacts/art-7fa765b51b4b47f9)
- [response_ref](http://127.0.0.1:18890/api/runs/int-fe2b255558a6465f/artifacts/art-6188da70b3804f49)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-fe2b255558a6465f/artifacts/art-be53c4a8ffd340b8)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-fe2b255558a6465f/artifacts/art-a0c0b9a7a5a04878)

## G085 · sqlite-utils · 用例契约问题

引用不能在指定文档中唯一定位

- 分类来源：contract-validation
- 定位：cli-migrate-directory
- 依据文档：docs/migrations.rst · docs/migrations.rst#chars=4982:7816
- [执行记录](http://127.0.0.1:18890/?run=int-fe2b255558a6465f&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-fe2b255558a6465f/artifacts/art-7fa765b51b4b47f9)
- [response_ref](http://127.0.0.1:18890/api/runs/int-fe2b255558a6465f/artifacts/art-6188da70b3804f49)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-fe2b255558a6465f/artifacts/art-be53c4a8ffd340b8)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-fe2b255558a6465f/artifacts/art-a0c0b9a7a5a04878)

## G086 · sqlite-utils · 缺少依据

文档只说明 --verbose 会显示迁移前后 schema 和统一 diff，没有给出具体输出格式或可核对片段，无法确定断言文本；需要补充示例输出或明确可观察字段后才能设计验收。

- 分类来源：model
- 定位：cli-migrate-verbose
- 依据文档：docs/migrations.rst · docs/migrations.rst#chars=4982:7816
- [执行记录](http://127.0.0.1:18890/?run=int-fe2b255558a6465f&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-fe2b255558a6465f/artifacts/art-7fa765b51b4b47f9)
- [response_ref](http://127.0.0.1:18890/api/runs/int-fe2b255558a6465f/artifacts/art-6188da70b3804f49)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-fe2b255558a6465f/artifacts/art-be53c4a8ffd340b8)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-fe2b255558a6465f/artifacts/art-a0c0b9a7a5a04878)

## G087 · sqlite-utils · 缺少依据

文档只说明 plugins 命令输出为已安装插件的 JSON 列表，未给出字段名、元素结构或具体值，无法设计可核对的具体输出预期。

- 分类来源：model
- 定位：plugin_list_json
- 依据文档：docs/plugins.rst · docs/plugins.rst#chars=0:4608
- [执行记录](http://127.0.0.1:18890/?run=int-fe2b255558a6465f&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-fe2b255558a6465f/artifacts/art-9dd97036b4584f96)
- [response_ref](http://127.0.0.1:18890/api/runs/int-fe2b255558a6465f/artifacts/art-10eeb638d79e43ec)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-fe2b255558a6465f/artifacts/art-a18d4e8fd5174360)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-fe2b255558a6465f/artifacts/art-de041903d32d430c)

## G088 · sqlite-utils · 待分类

B2-C09 · --type zipcode TeXt 生成 TEXT 列：该用例未完整执行，查看逐步原件

- 分类来源：execution-stage
- 定位：B2-C09
- [执行记录](http://127.0.0.1:18890/?run=int-fe2b255558a6465f&tab=flow&evidence=run)
- [task-report](http://127.0.0.1:18890/api/runs/int-fe2b255558a6465f/artifacts/art-3cbc9c7789c241cb)
- [u-22b112d0be-business/cases.json](http://127.0.0.1:18890/api/runs/int-fe2b255558a6465f/artifacts/art-a88ed52a6eab4f70)

## G089 · sqlite-utils · 待分类

B3-mem-attach-existing-db-case · attach trees.db 后按 stdin id 过滤：该用例未完整执行，查看逐步原件

- 分类来源：execution-stage
- 定位：B3-mem-attach-existing-db-case
- [执行记录](http://127.0.0.1:18890/?run=int-fe2b255558a6465f&tab=flow&evidence=run)
- [task-report](http://127.0.0.1:18890/api/runs/int-fe2b255558a6465f/artifacts/art-3cbc9c7789c241cb)
- [u-22b112d0be-business/cases.json](http://127.0.0.1:18890/api/runs/int-fe2b255558a6465f/artifacts/art-a88ed52a6eab4f70)
