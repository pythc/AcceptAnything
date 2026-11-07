# D040 逐项覆盖缺口账本

仅整理已终态、完整性验证通过的记录。模型分类仍标明来源；执行错误、缺少依据和未覆盖均不能视为确认产品缺陷。未自动删除语义相近的模型意见，原始条目数不等于不重复需求数或覆盖率。

## G001 · fastify · 平台能力不足

原文给出正确行为（自定义解析函数返回的文本用于启动日志），但核对需要捕获启动日志输出；提供的文档未说明日志采集方式（logger stream 配置位于未纳入范围的 Logging 文档），scenario 协议也没有读取日志的步骤，缺少观察协议。

- 分类来源：model
- 定位：listen-text-resolver
- 依据文档：docs/Reference/Server.md · docs/Reference/Server.md#chars=41939:45203
- [执行记录](http://127.0.0.1:18890/?run=int-715e14bb0b2b4705&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-715e14bb0b2b4705/artifacts/art-56b498e5721045e6)
- [response_ref](http://127.0.0.1:18890/api/runs/int-715e14bb0b2b4705/artifacts/art-4862cee1e9cf4ef2)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-715e14bb0b2b4705/artifacts/art-1bbc70662ef644ae)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-715e14bb0b2b4705/artifacts/art-d6c950b6b169430c)

## G002 · fastify · 平台能力不足

文档把根路由声明在 async routes 插件内并由主应用 register 加载。当前回调协议未明确支持在插件回调内部再声明另一个路由处理函数，无法构造注册插件后请求 GET / 的完整流程；需补充嵌套回调或可注入的公开插件接线。

- 分类来源：model
- 定位：plugin-register-route
- 依据文档：docs/Guides/Getting-Started.md · docs/Guides/Getting-Started.md#chars=0:4967
- [执行记录](http://127.0.0.1:18890/?run=int-715e14bb0b2b4705&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-715e14bb0b2b4705/artifacts/art-c9b073c2aeb24fd5)
- [response_ref](http://127.0.0.1:18890/api/runs/int-715e14bb0b2b4705/artifacts/art-c59bfeb6c1384fff)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-715e14bb0b2b4705/artifacts/art-65ceba3a73de4a14)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-715e14bb0b2b4705/artifacts/art-91593cac0ae34782)

## G003 · fastify · 缺少依据

当前可见的 Getting Started 片段在此截断，数据库连接、异步引导等后续内容未提供，无法确定其具体输入、预期输出和前置条件；需补全 D13 后续片段后再设计对应标准。

- 分类来源：model
- 定位：getting-started-continuation
- 依据文档：docs/Guides/Getting-Started.md · docs/Guides/Getting-Started.md#chars=0:4967
- [执行记录](http://127.0.0.1:18890/?run=int-715e14bb0b2b4705&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-715e14bb0b2b4705/artifacts/art-c9b073c2aeb24fd5)
- [response_ref](http://127.0.0.1:18890/api/runs/int-715e14bb0b2b4705/artifacts/art-c59bfeb6c1384fff)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-715e14bb0b2b4705/artifacts/art-65ceba3a73de4a14)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-715e14bb0b2b4705/artifacts/art-91593cac0ae34782)

## G004 · fastify · 平台能力不足

D22 仅限定范围；D23 明确要求插件按声明顺序加载且下一插件等待前一插件完成，但当前 scenario 回调无法创建可观测的异步挂起信号，也无法记录第二插件开始执行的时刻，故缺少执行/观察协议。

- 分类来源：model
- 定位：plugin_load_order
- 依据文档：docs/Guides/Getting-Started.md · docs/Guides/Getting-Started.md#chars=4967:9913
- [执行记录](http://127.0.0.1:18890/?run=int-715e14bb0b2b4705&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-715e14bb0b2b4705/artifacts/art-dc7dd320a5054465)
- [response_ref](http://127.0.0.1:18890/api/runs/int-715e14bb0b2b4705/artifacts/art-0495b7d8053a4536)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-715e14bb0b2b4705/artifacts/art-7dfdcd6ee88a4479)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-715e14bb0b2b4705/artifacts/art-d521b4a588d946cb)

## G005 · fastify · 环境未就绪

D22 仅限定范围；D23 要求安装并用 fastify-plugin 包装 dbConnector，但发现接口未提供 fastify-plugin 调用入口，环境也未准备该依赖，无法构造父作用域读回。

- 分类来源：model
- 定位：fastify_plugin_scope
- 依据文档：docs/Guides/Getting-Started.md · docs/Guides/Getting-Started.md#chars=4967:9913
- [执行记录](http://127.0.0.1:18890/?run=int-715e14bb0b2b4705&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-715e14bb0b2b4705/artifacts/art-dc7dd320a5054465)
- [response_ref](http://127.0.0.1:18890/api/runs/int-715e14bb0b2b4705/artifacts/art-0495b7d8053a4536)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-715e14bb0b2b4705/artifacts/art-7dfdcd6ee88a4479)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-715e14bb0b2b4705/artifacts/art-d521b4a588d946cb)

## G006 · fastify · 环境未就绪

D22 仅限定范围；D23 依赖 @fastify/mongodb 在实例上 decorate mongo，当前执行契约没有可连接的 MongoDB 服务与对应依赖，无法验证。

- 分类来源：model
- 定位：mongo_decorator
- 依据文档：docs/Guides/Getting-Started.md · docs/Guides/Getting-Started.md#chars=4967:9913
- [执行记录](http://127.0.0.1:18890/?run=int-715e14bb0b2b4705&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-715e14bb0b2b4705/artifacts/art-dc7dd320a5054465)
- [response_ref](http://127.0.0.1:18890/api/runs/int-715e14bb0b2b4705/artifacts/art-0495b7d8053a4536)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-715e14bb0b2b4705/artifacts/art-7dfdcd6ee88a4479)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-715e14bb0b2b4705/artifacts/art-d521b4a588d946cb)

## G007 · fastify · 环境未就绪

D22 仅限定范围；D23 需要可连接 MongoDB 并准备 test_collection：空集合应抛 No documents found，非空应返回 find().toArray() 结果。当前无 Mongo 服务/数据，且原文未规定文档完整字段形状，无法执行断言。

- 分类来源：model
- 定位：animals_route
- 依据文档：docs/Guides/Getting-Started.md · docs/Guides/Getting-Started.md#chars=4967:9913
- [执行记录](http://127.0.0.1:18890/?run=int-715e14bb0b2b4705&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-715e14bb0b2b4705/artifacts/art-dc7dd320a5054465)
- [response_ref](http://127.0.0.1:18890/api/runs/int-715e14bb0b2b4705/artifacts/art-0495b7d8053a4536)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-715e14bb0b2b4705/artifacts/art-7dfdcd6ee88a4479)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-715e14bb0b2b4705/artifacts/art-d521b4a588d946cb)

## G008 · fastify · 环境未就绪

D22 仅限定范围；D23 需要 MongoDB 中准备含/不含指定 animal 的文档：不存在时报 Invalid value，存在时返回 findOne 结果。当前无服务/数据，原文未给出完整文档形状。

- 分类来源：model
- 定位：animal_route
- 依据文档：docs/Guides/Getting-Started.md · docs/Guides/Getting-Started.md#chars=4967:9913
- [执行记录](http://127.0.0.1:18890/?run=int-715e14bb0b2b4705&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-715e14bb0b2b4705/artifacts/art-dc7dd320a5054465)
- [response_ref](http://127.0.0.1:18890/api/runs/int-715e14bb0b2b4705/artifacts/art-0495b7d8053a4536)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-715e14bb0b2b4705/artifacts/art-7dfdcd6ee88a4479)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-715e14bb0b2b4705/artifacts/art-d521b4a588d946cb)

## G009 · fastify · 缺少依据

D22 仅限定范围；D23 只给出 animalBodyJsonSchema 的 required/type，没有说明校验失败时的状态码或响应体；不能断言拒绝输出。

- 分类来源：model
- 定位：post_animals_schema
- 依据文档：docs/Guides/Getting-Started.md · docs/Guides/Getting-Started.md#chars=4967:9913
- [执行记录](http://127.0.0.1:18890/?run=int-715e14bb0b2b4705&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-715e14bb0b2b4705/artifacts/art-dc7dd320a5054465)
- [response_ref](http://127.0.0.1:18890/api/runs/int-715e14bb0b2b4705/artifacts/art-0495b7d8053a4536)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-715e14bb0b2b4705/artifacts/art-7dfdcd6ee88a4479)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-715e14bb0b2b4705/artifacts/art-d521b4a588d946cb)

## G010 · fastify · 环境未就绪

D22 仅限定范围；D23 需要 MongoDB 并准备 test_collection；原文只说明 insertOne({ animal: request.body.animal }) 的结果直接 return，未给出 insertedId 等字段，读回依赖数据库。

- 分类来源：model
- 定位：post_animals_insert
- 依据文档：docs/Guides/Getting-Started.md · docs/Guides/Getting-Started.md#chars=4967:9913
- [执行记录](http://127.0.0.1:18890/?run=int-715e14bb0b2b4705&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-715e14bb0b2b4705/artifacts/art-dc7dd320a5054465)
- [response_ref](http://127.0.0.1:18890/api/runs/int-715e14bb0b2b4705/artifacts/art-0495b7d8053a4536)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-715e14bb0b2b4705/artifacts/art-7dfdcd6ee88a4479)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-715e14bb0b2b4705/artifacts/art-d521b4a588d946cb)

## G011 · fastify · 缺少依据

D34 只展示匹配 schema 的处理器返回值，没有给出不匹配 body 的响应状态或错误体；D40 的选中片段也未规定拒绝输出，无法确定正确拒绝结果。

- 分类来源：model
- 定位：schema-invalid-body-rejection
- 依据文档：docs/Guides/Getting-Started.md · docs/Guides/Getting-Started.md#chars=9913:14902
- [执行记录](http://127.0.0.1:18890/?run=int-715e14bb0b2b4705&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-715e14bb0b2b4705/artifacts/art-bcb1d505e50e4a84)
- [response_ref](http://127.0.0.1:18890/api/runs/int-715e14bb0b2b4705/artifacts/art-cf1faab3a1fb4c0c)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-715e14bb0b2b4705/artifacts/art-1685d4f75a624292)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-715e14bb0b2b4705/artifacts/art-3b681de699e1433c)

## G012 · fastify · 平台能力不足

该约定依赖 fastify 单元测试的文件匹配正则来判定：名为 *.test.js 的文件会被命中，而名为 *-test.js 的文件不会。当前发现只给出原生测试命令，未声明可调用的收集器入口或用正则筛选文件并观察结果的协议，因此无法在隔离环境中验证命中与否，需补充执行与观察协议。

- 分类来源：model
- 定位：R4
- 依据文档：test/bundler/README.md · test/bundler/README.md#chars=0:1276
- [执行记录](http://127.0.0.1:18890/?run=int-715e14bb0b2b4705&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-715e14bb0b2b4705/artifacts/art-3e7f942b4d574272)
- [response_ref](http://127.0.0.1:18890/api/runs/int-715e14bb0b2b4705/artifacts/art-e2343b4958554f37)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-715e14bb0b2b4705/artifacts/art-084e73abbabe4eed)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-715e14bb0b2b4705/artifacts/art-f301923da80e4a94)

## G013 · fastify · 环境未就绪

要验证打包构建成功与打包后 fastify 应用可运行，需先安装 webpack/esbuild 栈依赖并具备 Node LTS 运行时；这两个组件只声明 native bundle/test 原生命令，没有已声明的 CLI 入口，文档也未约定打包产物路径、应用启动方式与可读回的响应，因此依赖与执行观察前提均未准备。

- 分类来源：model
- 定位：R5
- 依据文档：test/bundler/README.md · test/bundler/README.md#chars=0:1276
- [执行记录](http://127.0.0.1:18890/?run=int-715e14bb0b2b4705&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-715e14bb0b2b4705/artifacts/art-3e7f942b4d574272)
- [response_ref](http://127.0.0.1:18890/api/runs/int-715e14bb0b2b4705/artifacts/art-e2343b4958554f37)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-715e14bb0b2b4705/artifacts/art-084e73abbabe4eed)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-715e14bb0b2b4705/artifacts/art-f301923da80e4a94)

## G014 · fastify · 待分类

部分用例未完整执行

- 分类来源：execution-stage
- 定位：u-d935a3cdea-native
- [执行记录](http://127.0.0.1:18890/?run=int-715e14bb0b2b4705&tab=flow&evidence=run)
- [task-report](http://127.0.0.1:18890/api/runs/int-715e14bb0b2b4705/artifacts/art-1ed61cacb1a54530)

## G015 · flask · 环境未就绪

README 只说明访问 http://localhost:5000/ 用表单提交任务、页面会发起轮询请求并可在 devtools 与日志中观察，未给出表单字段、轮询请求路径或响应结构，也缺少可断言的页面文本或状态码依据；同时任务提交与完成依赖 Redis broker 与 Celery worker，当前环境未准备这些依赖服务，因此无法设计可核对业务输出的用例。

- 分类来源：model
- 定位：r-d2-forms-polling
- 依据文档：examples/celery/README.md · examples/celery/README.md#chars=0:950
- [执行记录](http://127.0.0.1:18890/?run=int-4e920c0d8f6646ed&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-4e920c0d8f6646ed/artifacts/art-b2213283535d4fa8)
- [response_ref](http://127.0.0.1:18890/api/runs/int-4e920c0d8f6646ed/artifacts/art-94a783efff294a96)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-4e920c0d8f6646ed/artifacts/art-e8cb19db4e6b4248)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-4e920c0d8f6646ed/artifacts/art-f930f1e122314a7f)

## G016 · flask · 平台能力不足

原文声明 celery_app.set_default() 使默认应用在每个请求中被看到，但现有公开入口只有前序步骤与模块导出函数的 call/get/item，无法读取 celery.current_app 或默认应用句柄，也没有请求内观察默认应用的协议；缺少观察手段，构造断言会变成猜测。

- 分类来源：model
- 定位：r-d3-set-default
- 依据文档：docs/patterns/celery.rst · docs/patterns/celery.rst#chars=0:4980
- [执行记录](http://127.0.0.1:18890/?run=int-4e920c0d8f6646ed&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-4e920c0d8f6646ed/artifacts/art-b2213283535d4fa8)
- [response_ref](http://127.0.0.1:18890/api/runs/int-4e920c0d8f6646ed/artifacts/art-94a783efff294a96)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-4e920c0d8f6646ed/artifacts/art-e8cb19db4e6b4248)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-4e920c0d8f6646ed/artifacts/art-f930f1e122314a7f)

## G017 · flask · 平台能力不足

原文说明任务函数运行时 app context 处于活动状态，但已索引的公开任务 add/block/process 不暴露上下文观察点，且协议禁止注入在任务体内检查 has_app_context 的自定义任务；真实运行任务还需 Redis broker 与 Celery worker，缺少可执行的观察路径，无法给出可核对业务输出。

- 分类来源：model
- 定位：r-d3-flasktask-context
- 依据文档：docs/patterns/celery.rst · docs/patterns/celery.rst#chars=0:4980
- [执行记录](http://127.0.0.1:18890/?run=int-4e920c0d8f6646ed&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-4e920c0d8f6646ed/artifacts/art-b2213283535d4fa8)
- [response_ref](http://127.0.0.1:18890/api/runs/int-4e920c0d8f6646ed/artifacts/art-94a783efff294a96)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-4e920c0d8f6646ed/artifacts/art-e8cb19db4e6b4248)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-4e920c0d8f6646ed/artifacts/art-f930f1e122314a7f)

## G018 · flask · 平台能力不足

原文要求 shared_task 创建的任务对象访问当前 Celery 应用；discovery 只提供任务函数 add 的普通调用签名，没有读取任务对象绑定 app 或验证 set_default 效果的公开观察入口，无法确认该绑定行为。

- 分类来源：model
- 定位：celery-shared-task-current-app
- 依据文档：docs/patterns/celery.rst · docs/patterns/celery.rst#chars=4980:8670
- [执行记录](http://127.0.0.1:18890/?run=int-4e920c0d8f6646ed&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-4e920c0d8f6646ed/artifacts/art-e91c440d212f4989)
- [response_ref](http://127.0.0.1:18890/api/runs/int-4e920c0d8f6646ed/artifacts/art-1d2bb624eb0d4447)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-4e920c0d8f6646ed/artifacts/art-6040c3c3596b4fcf)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-4e920c0d8f6646ed/artifacts/art-f3f73c5278bb4284)

## G019 · flask · 环境未就绪

原文要求该加法任务不忽略结果以便后续读取返回值；执行需 Celery worker 和结果后端，且 discovery 未暴露任务对象 ignore_result 属性或后端查询入口，当前无法观察结果是否被保留。

- 分类来源：model
- 定位：celery-ignore-result
- 依据文档：docs/patterns/celery.rst · docs/patterns/celery.rst#chars=4980:8670
- [执行记录](http://127.0.0.1:18890/?run=int-4e920c0d8f6646ed&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-4e920c0d8f6646ed/artifacts/art-e91c440d212f4989)
- [response_ref](http://127.0.0.1:18890/api/runs/int-4e920c0d8f6646ed/artifacts/art-1d2bb624eb0d4447)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-4e920c0d8f6646ed/artifacts/art-6040c3c3596b4fcf)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-4e920c0d8f6646ed/artifacts/art-f3f73c5278bb4284)

## G020 · flask · 环境未就绪

原文规定简单后台调用使用 delay(*args, **kwargs)，且必须有 Celery worker 运行；当前执行契约不能启动 worker，也未提供任务对象 delay 的公开调用与观察步骤，无法验证任务被提交并异步执行。

- 分类来源：model
- 定位：celery-delay-background
- 依据文档：docs/patterns/celery.rst · docs/patterns/celery.rst#chars=4980:8670
- [执行记录](http://127.0.0.1:18890/?run=int-4e920c0d8f6646ed&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-4e920c0d8f6646ed/artifacts/art-e91c440d212f4989)
- [response_ref](http://127.0.0.1:18890/api/runs/int-4e920c0d8f6646ed/artifacts/art-1d2bb624eb0d4447)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-4e920c0d8f6646ed/artifacts/art-6040c3c3596b4fcf)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-4e920c0d8f6646ed/artifacts/art-f3f73c5278bb4284)

## G021 · flask · 环境未就绪

原文规定以表单整数 a、b 调用 add_together.delay，并立即返回 result.id；执行需要 Redis broker 与 Celery worker，当前契约不能准备长驻服务，且无公开替代注入接口，无法验证返回的 result_id 及不等待结果的行为。

- 分类来源：model
- 定位：celery-add-endpoint
- 依据文档：docs/patterns/celery.rst · docs/patterns/celery.rst#chars=4980:8670
- [执行记录](http://127.0.0.1:18890/?run=int-4e920c0d8f6646ed&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-4e920c0d8f6646ed/artifacts/art-e91c440d212f4989)
- [response_ref](http://127.0.0.1:18890/api/runs/int-4e920c0d8f6646ed/artifacts/art-1d2bb624eb0d4447)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-4e920c0d8f6646ed/artifacts/art-6040c3c3596b4fcf)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-4e920c0d8f6646ed/artifacts/art-f3f73c5278bb4284)

## G022 · flask · 环境未就绪

原文规定按任务 id 返回 ready、successful，以及仅在 ready 时的 value（否则 None）；要构造真实已完成任务需要 worker 和结果后端，当前未准备，不能猜测具体 ready/successful/value 值。

- 分类来源：model
- 定位：celery-result-endpoint
- 依据文档：docs/patterns/celery.rst · docs/patterns/celery.rst#chars=4980:8670
- [执行记录](http://127.0.0.1:18890/?run=int-4e920c0d8f6646ed&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-4e920c0d8f6646ed/artifacts/art-e91c440d212f4989)
- [response_ref](http://127.0.0.1:18890/api/runs/int-4e920c0d8f6646ed/artifacts/art-1d2bb624eb0d4447)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-4e920c0d8f6646ed/artifacts/art-6040c3c3596b4fcf)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-4e920c0d8f6646ed/artifacts/art-f3f73c5278bb4284)

## G023 · flask · 环境未就绪

原文要求先通过 /add 启动任务，再通过 /result/<id> 轮询完成状态，以证明请求不被阻塞；需要可运行的 Celery worker 和结果后端产生从未完成到完成的状态变化，当前环境无法表达该前置状态。

- 分类来源：model
- 定位：celery-polling-flow
- 依据文档：docs/patterns/celery.rst · docs/patterns/celery.rst#chars=4980:8670
- [执行记录](http://127.0.0.1:18890/?run=int-4e920c0d8f6646ed&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-4e920c0d8f6646ed/artifacts/art-e91c440d212f4989)
- [response_ref](http://127.0.0.1:18890/api/runs/int-4e920c0d8f6646ed/artifacts/art-1d2bb624eb0d4447)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-4e920c0d8f6646ed/artifacts/art-6040c3c3596b4fcf)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-4e920c0d8f6646ed/artifacts/art-f3f73c5278bb4284)

## G024 · flask · 平台能力不足

原文只说明演示目标（不跳转页面地提交表单数据并处理 JSON 响应），未给出请求路径、表单字段名、JSON 响应结构，也没有浏览器执行与页面观察协议；discovery 的 index/add 视图签名只描述调用能力，不是正确输出，无法据此断言具体业务结果。

- 分类来源：model
- 定位：js-example-ajax-demo
- 依据文档：examples/javascript/README.rst · examples/javascript/README.rst#chars=0:1086
- [执行记录](http://127.0.0.1:18890/?run=int-4e920c0d8f6646ed&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-4e920c0d8f6646ed/artifacts/art-217edee267de45a5)
- [response_ref](http://127.0.0.1:18890/api/runs/int-4e920c0d8f6646ed/artifacts/art-2ed76e6d7c884c1f)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-4e920c0d8f6646ed/artifacts/art-0976c3c334994b9a)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-4e920c0d8f6646ed/artifacts/art-99bfd740c5cd4958)

## G025 · flask · 缺少依据

原文只说“简单部署下根 URL 是 /”，未规定 request.script_root 在默认请求上下文中经 tojson 序列化后的确切字符串（是 "/" 还是空串），缺少可直接断言的正确输出，故不猜测预期值。

- 分类来源：model
- 定位：script-root-for-js
- 依据文档：docs/patterns/javascript.rst · docs/patterns/javascript.rst#chars=0:4935
- [执行记录](http://127.0.0.1:18890/?run=int-4e920c0d8f6646ed&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-4e920c0d8f6646ed/artifacts/art-217edee267de45a5)
- [response_ref](http://127.0.0.1:18890/api/runs/int-4e920c0d8f6646ed/artifacts/art-2ed76e6d7c884c1f)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-4e920c0d8f6646ed/artifacts/art-0976c3c334994b9a)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-4e920c0d8f6646ed/artifacts/art-99bfd740c5cd4958)

## G026 · flask · 平台能力不足

该行为依赖浏览器执行页面 JavaScript 并观察 Promise/response.json() 结果；原文只给代码片段，未提供可运行页面、请求端点与 JSON 响应示例，现有场景协议只能在进程内调用 Python 接口，缺少执行与观察协议。

- 分类来源：model
- 定位：fetch-promise-get
- 依据文档：docs/patterns/javascript.rst · docs/patterns/javascript.rst#chars=0:4935
- [执行记录](http://127.0.0.1:18890/?run=int-4e920c0d8f6646ed&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-4e920c0d8f6646ed/artifacts/art-217edee267de45a5)
- [response_ref](http://127.0.0.1:18890/api/runs/int-4e920c0d8f6646ed/artifacts/art-2ed76e6d7c884c1f)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-4e920c0d8f6646ed/artifacts/art-0976c3c334994b9a)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-4e920c0d8f6646ed/artifacts/art-99bfd740c5cd4958)

## G027 · flask · 平台能力不足

原文只说明 FormData 与 HTML 表单同格式、并可在视图中通过 request.form 读取；场景协议无法声明读取请求体的视图主体，也没有构造表单/多段请求后观察表单字段的公开入口，缺观察协议。

- 分类来源：model
- 定位：formdata-request-form
- 依据文档：docs/patterns/javascript.rst · docs/patterns/javascript.rst#chars=0:4935
- [执行记录](http://127.0.0.1:18890/?run=int-4e920c0d8f6646ed&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-4e920c0d8f6646ed/artifacts/art-217edee267de45a5)
- [response_ref](http://127.0.0.1:18890/api/runs/int-4e920c0d8f6646ed/artifacts/art-2ed76e6d7c884c1f)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-4e920c0d8f6646ed/artifacts/art-0976c3c334994b9a)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-4e920c0d8f6646ed/artifacts/art-99bfd740c5cd4958)

## G028 · flask · 平台能力不足

D12 要求检查 response.redirected 并在需要时把 window.location 设为 response.url；当前执行协议没有可观察 response.redirected/window.location 的浏览器步骤，示例也未提供 /login 重定向端点，因此缺少执行与观察协议。

- 分类来源：model
- 定位：fetch-follow-redirect
- 依据文档：docs/patterns/javascript.rst · docs/patterns/javascript.rst#chars=4935:9038
- [执行记录](http://127.0.0.1:18890/?run=int-4e920c0d8f6646ed&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-4e920c0d8f6646ed/artifacts/art-dcb745b5a41140da)
- [response_ref](http://127.0.0.1:18890/api/runs/int-4e920c0d8f6646ed/artifacts/art-49d033cfa6264884)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-4e920c0d8f6646ed/artifacts/art-a777fc5ddf174659)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-4e920c0d8f6646ed/artifacts/art-4ff4c1c7b6814a0d)

## G029 · flask · 环境未就绪

D12 示例依赖 geology_fact 端点、geology_fact.html 模板和 #geology-fact 元素，并用 fetch 返回文本设置 innerHTML；当前发现未声明这些页面或端点，缺少可准备的前置数据与服务。

- 分类来源：model
- 定位：replace-div-content
- 依据文档：docs/patterns/javascript.rst · docs/patterns/javascript.rst#chars=4935:9038
- [执行记录](http://127.0.0.1:18890/?run=int-4e920c0d8f6646ed&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-4e920c0d8f6646ed/artifacts/art-dcb745b5a41140da)
- [response_ref](http://127.0.0.1:18890/api/runs/int-4e920c0d8f6646ed/artifacts/art-49d033cfa6264884)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-4e920c0d8f6646ed/artifacts/art-a777fc5ddf174659)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-4e920c0d8f6646ed/artifacts/art-4ff4c1c7b6814a0d)

## G030 · flask · 缺少依据

D15 仅概述可创建、编辑或删除自己的帖子；可见 D27 在 create 的错误分支处截断，docs/tutorial/blog.rst#chars=4980:9975 等上下文被省略，无法确定创建成功、编辑/删除路由、权限和输出。需对应分片补充后设计，不能断言整个仓库没有依据。

- 分类来源：model
- 定位：D15-post-owner-actions
- 依据文档：docs/tutorial/index.rst · docs/tutorial/index.rst#chars=0:2061
- [执行记录](http://127.0.0.1:18890/?run=int-4e920c0d8f6646ed&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-4e920c0d8f6646ed/artifacts/art-d610c1c5b3de4009)
- [response_ref](http://127.0.0.1:18890/api/runs/int-4e920c0d8f6646ed/artifacts/art-5b0d8c8d281d4dcc)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-4e920c0d8f6646ed/artifacts/art-5de5578d7bab44c0)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-4e920c0d8f6646ed/artifacts/art-df67a3c4e4214025)

## G031 · flask · 平台能力不足

D16 还要求 tests/ 目录和安装文件，但当前公开契约只能从导入名取得包根路径，inspect_path 不能拼接父目录或枚举项目文件；缺少项目根路径或目录枚举协议，无法验证 tests/ 与 pyproject.toml。

- 分类来源：model
- 定位：D16-tests-install-layout
- 依据文档：docs/tutorial/layout.rst · docs/tutorial/layout.rst#chars=0:2658
- [执行记录](http://127.0.0.1:18890/?run=int-4e920c0d8f6646ed&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-4e920c0d8f6646ed/artifacts/art-d610c1c5b3de4009)
- [response_ref](http://127.0.0.1:18890/api/runs/int-4e920c0d8f6646ed/artifacts/art-5b0d8c8d281d4dcc)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-4e920c0d8f6646ed/artifacts/art-5de5578d7bab44c0)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-4e920c0d8f6646ed/artifacts/art-df67a3c4e4214025)

## G032 · flask · 平台能力不足

已有 from_pyfile('config.py', silent=True) 的正确行为依据，但当前协议无法在调用 create_app 前把 config.py 放到 app.instance_path；需补充实例目录夹具或路径注入协议后才能验证加载与静默行为。

- 分类来源：model
- 定位：instance-config-load
- 依据文档：docs/tutorial/factory.rst · docs/tutorial/factory.rst#chars=0:4995
- [执行记录](http://127.0.0.1:18890/?run=int-4e920c0d8f6646ed&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-4e920c0d8f6646ed/artifacts/art-096bd3dd36f54b9a)
- [response_ref](http://127.0.0.1:18890/api/runs/int-4e920c0d8f6646ed/artifacts/art-4725a31ce3554a9a)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-4e920c0d8f6646ed/artifacts/art-b40bad14201e4d40)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-4e920c0d8f6646ed/artifacts/art-33309ecf057a4e3d)

## G033 · flask · 平台能力不足

D44 说明默认配置下文件位于项目 instance 目录；当前隔离协议可验证 test_config 的临时 DATABASE 文件，但未提供把 Flask 默认 instance 路径重定向到临时目录并清理写入文件的观察/清理方式，直接运行会改动仓库内 instance，故该落点项本批未执行。

- 分类来源：model
- 定位：db_instance_file_location
- 依据文档：docs/tutorial/database.rst · docs/tutorial/database.rst#chars=4957:7028
- [执行记录](http://127.0.0.1:18890/?run=int-4e920c0d8f6646ed&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-4e920c0d8f6646ed/artifacts/art-8b6f9af52f5644f0)
- [response_ref](http://127.0.0.1:18890/api/runs/int-4e920c0d8f6646ed/artifacts/art-ff7731be72db4f43)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-4e920c0d8f6646ed/artifacts/art-9433d0cf6bd24c87)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-4e920c0d8f6646ed/artifacts/art-faaffe59618146fe)

## G034 · flask · 用例契约问题

引用不能在指定文档中唯一定位

- 分类来源：contract-validation
- 定位：views_auth_url
- 依据文档：docs/tutorial/views.rst · docs/tutorial/views.rst#chars=0:4937
- [执行记录](http://127.0.0.1:18890/?run=int-4e920c0d8f6646ed&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-4e920c0d8f6646ed/artifacts/art-434c7359209c46f3)
- [response_ref](http://127.0.0.1:18890/api/runs/int-4e920c0d8f6646ed/artifacts/art-39188858846a48d5)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-4e920c0d8f6646ed/artifacts/art-b24253e9eff84c30)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-4e920c0d8f6646ed/artifacts/art-809cd965f5804209)

## G035 · flask · 用例契约问题

引用不能在指定文档中唯一定位

- 分类来源：contract-validation
- 定位：views_login_errors
- 依据文档：docs/tutorial/views.rst · docs/tutorial/views.rst#chars=0:4937
- [执行记录](http://127.0.0.1:18890/?run=int-4e920c0d8f6646ed&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-4e920c0d8f6646ed/artifacts/art-434c7359209c46f3)
- [response_ref](http://127.0.0.1:18890/api/runs/int-4e920c0d8f6646ed/artifacts/art-39188858846a48d5)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-4e920c0d8f6646ed/artifacts/art-b24253e9eff84c30)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-4e920c0d8f6646ed/artifacts/art-809cd965f5804209)

## G036 · flask · 用例契约问题

引用不能在指定文档中唯一定位

- 分类来源：contract-validation
- 定位：views_login_success
- 依据文档：docs/tutorial/views.rst · docs/tutorial/views.rst#chars=0:4937
- [执行记录](http://127.0.0.1:18890/?run=int-4e920c0d8f6646ed&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-4e920c0d8f6646ed/artifacts/art-434c7359209c46f3)
- [response_ref](http://127.0.0.1:18890/api/runs/int-4e920c0d8f6646ed/artifacts/art-39188858846a48d5)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-4e920c0d8f6646ed/artifacts/art-b24253e9eff84c30)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-4e920c0d8f6646ed/artifacts/art-809cd965f5804209)

## G037 · flask · 用例契约问题

引用不能在指定文档中唯一定位

- 分类来源：contract-validation
- 定位：views_logout
- 依据文档：docs/tutorial/views.rst · docs/tutorial/views.rst#chars=0:4937
- [执行记录](http://127.0.0.1:18890/?run=int-4e920c0d8f6646ed&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-4e920c0d8f6646ed/artifacts/art-434c7359209c46f3)
- [response_ref](http://127.0.0.1:18890/api/runs/int-4e920c0d8f6646ed/artifacts/art-39188858846a48d5)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-4e920c0d8f6646ed/artifacts/art-b24253e9eff84c30)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-4e920c0d8f6646ed/artifacts/art-809cd965f5804209)

## G038 · flask · 用例契约问题

引用不能在指定文档中唯一定位

- 分类来源：contract-validation
- 定位：views_load_user
- 依据文档：docs/tutorial/views.rst · docs/tutorial/views.rst#chars=0:4937
- [执行记录](http://127.0.0.1:18890/?run=int-4e920c0d8f6646ed&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-4e920c0d8f6646ed/artifacts/art-434c7359209c46f3)
- [response_ref](http://127.0.0.1:18890/api/runs/int-4e920c0d8f6646ed/artifacts/art-39188858846a48d5)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-4e920c0d8f6646ed/artifacts/art-b24253e9eff84c30)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-4e920c0d8f6646ed/artifacts/art-809cd965f5804209)

## G039 · flask · 用例契约问题

引用不能在指定文档中唯一定位

- 分类来源：contract-validation
- 定位：views_login_required
- 依据文档：docs/tutorial/views.rst · docs/tutorial/views.rst#chars=0:4937
- [执行记录](http://127.0.0.1:18890/?run=int-4e920c0d8f6646ed&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-4e920c0d8f6646ed/artifacts/art-434c7359209c46f3)
- [response_ref](http://127.0.0.1:18890/api/runs/int-4e920c0d8f6646ed/artifacts/art-39188858846a48d5)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-4e920c0d8f6646ed/artifacts/art-b24253e9eff84c30)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-4e920c0d8f6646ed/artifacts/art-809cd965f5804209)

## G040 · flask · 缺少依据

D72只说明已载入用户时调用原视图并正常继续，但本批次 focus 未给出受保护视图的具体响应输出；不能自建视图，当前仅能断言未登录分支。context_omitted 中 blog 其余片段待补后再设计正向放行断言。

- 分类来源：model
- 定位：login-required-allows-loaded-user
- 依据文档：docs/tutorial/views.rst · docs/tutorial/views.rst#chars=9909:10924
- [执行记录](http://127.0.0.1:18890/?run=int-4e920c0d8f6646ed&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-4e920c0d8f6646ed/artifacts/art-c75576b76017412d)
- [response_ref](http://127.0.0.1:18890/api/runs/int-4e920c0d8f6646ed/artifacts/art-0b3111f2b8f64064)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-4e920c0d8f6646ed/artifacts/art-9ef8e46718e540c9)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-4e920c0d8f6646ed/artifacts/art-a15124ee953f4eb1)

## G041 · flask · 用例契约问题

引用不能在指定文档中唯一定位

- 分类来源：contract-validation
- 定位：title_block_in_header
- 依据文档：docs/tutorial/templates.rst · docs/tutorial/templates.rst#chars=0:4961
- [执行记录](http://127.0.0.1:18890/?run=int-4e920c0d8f6646ed&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-4e920c0d8f6646ed/artifacts/art-f20c8211d09b42a5)
- [response_ref](http://127.0.0.1:18890/api/runs/int-4e920c0d8f6646ed/artifacts/art-9a17a4fde999461d)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-4e920c0d8f6646ed/artifacts/art-9a57b5485cb741e0)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-4e920c0d8f6646ed/artifacts/art-7bd9c7642fbf4bc5)

## G042 · flask · 平台能力不足

需要真实浏览器点击空表单并读取浏览器原生校验气泡；现有 browser 用例协议只能断言页面文本或选择器，无法稳定观察原生 validation UI。服务端兜底校验已由空表单 flash 用例覆盖，原生浏览器提示仍需补充执行与观察协议。

- 分类来源：model
- 定位：browser_required_validation
- 依据文档：docs/tutorial/templates.rst · docs/tutorial/templates.rst#chars=4961:6962
- [执行记录](http://127.0.0.1:18890/?run=int-4e920c0d8f6646ed&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-4e920c0d8f6646ed/artifacts/art-f20c8211d09b42a5)
- [response_ref](http://127.0.0.1:18890/api/runs/int-4e920c0d8f6646ed/artifacts/art-9a17a4fde999461d)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-4e920c0d8f6646ed/artifacts/art-9a57b5485cb741e0)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-4e920c0d8f6646ed/artifacts/art-7bd9c7642fbf4bc5)

## G043 · flask · 平台能力不足

D99 要求登录页外观与截图一致，但当前缺少浏览器截图对比或计算样式观察协议，且独立浏览器验证需要部署服务；仅凭页面文本无法断言 CSS 已加载并呈现截图外观。

- 分类来源：model
- 定位：login_page_visual_style
- 依据文档：docs/tutorial/static.rst · docs/tutorial/static.rst#chars=0:3170
- [执行记录](http://127.0.0.1:18890/?run=int-4e920c0d8f6646ed&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-4e920c0d8f6646ed/artifacts/art-e5d6580866df4499)
- [response_ref](http://127.0.0.1:18890/api/runs/int-4e920c0d8f6646ed/artifacts/art-5a61848e59494c48)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-4e920c0d8f6646ed/artifacts/art-c5728479e67e4224)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-4e920c0d8f6646ed/artifacts/art-d6c54ce9a13d4282)

## G044 · flask · 用例契约问题

引用不能在指定文档中唯一定位

- 分类来源：contract-validation
- 定位：static_cache_refresh_hint
- 依据文档：docs/tutorial/static.rst · docs/tutorial/static.rst#chars=0:3170
- [执行记录](http://127.0.0.1:18890/?run=int-4e920c0d8f6646ed&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-4e920c0d8f6646ed/artifacts/art-e5d6580866df4499)
- [response_ref](http://127.0.0.1:18890/api/runs/int-4e920c0d8f6646ed/artifacts/art-5a61848e59494c48)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-4e920c0d8f6646ed/artifacts/art-c5728479e67e4224)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-4e920c0d8f6646ed/artifacts/art-d6c54ce9a13d4282)

## G045 · flask · 平台能力不足

D113 要求 'most recent first'，但当前观察协议只能对 HTML 文本做正向子串包含，无法表达两个标题的先后顺序；需要能提取有序标题列表或比较子串位置的观察协议。因此该项暂不生成可执行用例。

- 分类来源：model
- 定位：index_order_desc
- 依据文档：docs/tutorial/blog.rst · docs/tutorial/blog.rst#chars=0:4980
- [执行记录](http://127.0.0.1:18890/?run=int-4e920c0d8f6646ed&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-4e920c0d8f6646ed/artifacts/art-77c70a6131c74326)
- [response_ref](http://127.0.0.1:18890/api/runs/int-4e920c0d8f6646ed/artifacts/art-d68674d1de2c4af2)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-4e920c0d8f6646ed/artifacts/art-c03ecbe7116544a2)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-4e920c0d8f6646ed/artifacts/art-32f0b5af799c470d)

## G046 · flask · 平台能力不足

D113 的模板条件明确只有作者显示 Edit；但非作者不显示属于否定断言，当前协议只有正向 contains/equals，缺少从 HTML 提取链接集合并断言其不包含 Edit 的能力。update 路由的具体定义也在 context_omitted 中，本项仅就非作者不出现 Edit 链接提出观察缺口。

- 分类来源：model
- 定位：index_edit_only_author
- 依据文档：docs/tutorial/blog.rst · docs/tutorial/blog.rst#chars=0:4980
- [执行记录](http://127.0.0.1:18890/?run=int-4e920c0d8f6646ed&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-4e920c0d8f6646ed/artifacts/art-77c70a6131c74326)
- [response_ref](http://127.0.0.1:18890/api/runs/int-4e920c0d8f6646ed/artifacts/art-d68674d1de2c4af2)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-4e920c0d8f6646ed/artifacts/art-c03ecbe7116544a2)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-4e920c0d8f6646ed/artifacts/art-32f0b5af799c470d)

## G047 · flask · 平台能力不足

D142 要求能通过 pip list 观察到 flaskr 1.0.0，并能在项目目录外调用应用；当前协议没有 pip 命令入口、工作目录切换或发行元数据读取接口，且缺少不写实例数据库的可观察命令，无法在本批安全验证安装位置、版本和跨目录导入。

- 分类来源：model
- 定位：R142-PIP-LIST-ANYWHERE
- 依据文档：docs/tutorial/install.rst · docs/tutorial/install.rst#chars=0:2838
- [执行记录](http://127.0.0.1:18890/?run=int-4e920c0d8f6646ed&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-4e920c0d8f6646ed/artifacts/art-26ad6717488b4176)
- [response_ref](http://127.0.0.1:18890/api/runs/int-4e920c0d8f6646ed/artifacts/art-83a190f691d640bc)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-4e920c0d8f6646ed/artifacts/art-cddbca096a164ed9)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-4e920c0d8f6646ed/artifacts/art-578eb36d6d224f08)

## G048 · flask · 平台能力不足

原文用 monkeypatch 把 flaskr.db.init_db 替换为 fake_init_db，并断言 Recorder.called；当前 scenario 协议不支持替换模块函数或注入回调来观察该内部调用，因此无法验证“调用了 init_db”这一断言。

- 分类来源：model
- 定位：R8
- 依据文档：docs/tutorial/tests.rst · docs/tutorial/tests.rst#chars=4999:9946
- [执行记录](http://127.0.0.1:18890/?run=int-4e920c0d8f6646ed&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-4e920c0d8f6646ed/artifacts/art-735300a9ea5f4280)
- [response_ref](http://127.0.0.1:18890/api/runs/int-4e920c0d8f6646ed/artifacts/art-05efe1583df4470e)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-4e920c0d8f6646ed/artifacts/art-6fe348667d6b4e8a)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-4e920c0d8f6646ed/artifacts/art-7f82a410b98747bc)

## G049 · flask · 缺少依据

当前 focus 片段只笼统要求无效数据时显示错误信息，未给出错误文案、可比较输出或具体断言；后续 test_update 片段在 context_omitted 中，需补全上下文后才能确定预期。

- 分类来源：model
- 定位：invalid-data-error-message
- 依据文档：docs/tutorial/tests.rst · docs/tutorial/tests.rst#chars=9946:14899
- [执行记录](http://127.0.0.1:18890/?run=int-4e920c0d8f6646ed&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-4e920c0d8f6646ed/artifacts/art-d7db99d3b7c54821)
- [response_ref](http://127.0.0.1:18890/api/runs/int-4e920c0d8f6646ed/artifacts/art-84158be2a2c94663)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-4e920c0d8f6646ed/artifacts/art-064fa02ebd914794)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-4e920c0d8f6646ed/artifacts/art-1340fbdcd1d4471f)

## G050 · flask · 平台能力不足

原文要求在保留的请求上下文中读取 g.user['username'] 为 test；当前公开测试客户端可读 session，但 discovery 未提供读取请求内 g.user 的公开入口，需补充观察协议或适用夹具。

- 分类来源：model
- 定位：logged-in-g-user-observation
- 依据文档：docs/tutorial/tests.rst · docs/tutorial/tests.rst#chars=9946:14899
- [执行记录](http://127.0.0.1:18890/?run=int-4e920c0d8f6646ed&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-4e920c0d8f6646ed/artifacts/art-d7db99d3b7c54821)
- [response_ref](http://127.0.0.1:18890/api/runs/int-4e920c0d8f6646ed/artifacts/art-84158be2a2c94663)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-4e920c0d8f6646ed/artifacts/art-064fa02ebd914794)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-4e920c0d8f6646ed/artifacts/art-1340fbdcd1d4471f)

## G051 · flask · 环境未就绪

需要把随机 SECRET_KEY 写入 create_app 所读取的实例目录 config.py；当前协议只能写用例临时目录，无法在 flaskr 现有实例路径放置该文件并读回配置，缺少可表达的实例文件夹具。

- 分类来源：model
- 定位：D185-instance-config-secret
- 依据文档：docs/tutorial/deploy.rst · docs/tutorial/deploy.rst#chars=0:3699
- [执行记录](http://127.0.0.1:18890/?run=int-4e920c0d8f6646ed&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-4e920c0d8f6646ed/artifacts/art-1776003880fc4a74)
- [response_ref](http://127.0.0.1:18890/api/runs/int-4e920c0d8f6646ed/artifacts/art-64f8e0b2b4584cf2)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-4e920c0d8f6646ed/artifacts/art-07bd45cfa1034aa8)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-4e920c0d8f6646ed/artifacts/art-74bbaee9fb5d4d10)

## G052 · flask · 环境未就绪

需要已安装（非 editable）的 flaskr 轮子及可写的 .venv/var/flaskr-instance 实例目录，才能验证安装后 init-db 在该目录建库；当前发现单元是源码路径，无法准备或观察该安装态实例目录。

- 分类来源：model
- 定位：D185-init-db-installed
- 依据文档：docs/tutorial/deploy.rst · docs/tutorial/deploy.rst#chars=0:3699
- [执行记录](http://127.0.0.1:18890/?run=int-4e920c0d8f6646ed&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-4e920c0d8f6646ed/artifacts/art-1776003880fc4a74)
- [response_ref](http://127.0.0.1:18890/api/runs/int-4e920c0d8f6646ed/artifacts/art-64f8e0b2b4584cf2)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-4e920c0d8f6646ed/artifacts/art-07bd45cfa1034aa8)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-4e920c0d8f6646ed/artifacts/art-74bbaee9fb5d4d10)

## G053 · flask · 缺少依据

这些条目明确是“ideas for what to try next”，属于可选后续开发，不是当前 Flaskr 已实现行为；原文未给出路由、请求方法、表单字段、数据模型、页面标记、分页导航或响应内容等契约。例如“Only show 5 posts per page”也未说明索引页 URL、文章排序和翻页参数。缺少正确输出与适用条件，无法为本批次生成 required 用例。

- 分类来源：model
- 定位：D198-future-ideas-no-contract
- 依据文档：docs/tutorial/next.rst · docs/tutorial/next.rst#chars=0:1631
- [执行记录](http://127.0.0.1:18890/?run=int-4e920c0d8f6646ed&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-4e920c0d8f6646ed/artifacts/art-b739ccee377c4c1a)
- [response_ref](http://127.0.0.1:18890/api/runs/int-4e920c0d8f6646ed/artifacts/art-b7dde8b577b2469c)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-4e920c0d8f6646ed/artifacts/art-4180d44fdeee44cd)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-4e920c0d8f6646ed/artifacts/art-0b469f327f844eb1)

## G054 · flask · 缺少依据

原文只声明该目录代码可供 Quart 等替代 Flask 实现使用，没有给出具体公开入口、输入、返回值或可观察的替代实现行为；接口索引只能说明调用接线，不能替代正确输出，因此缺少可核对的验收依据。

- 分类来源：model
- 定位：R1
- 依据文档：src/flask/sansio/README.md · src/flask/sansio/README.md#chars=0:229
- [执行记录](http://127.0.0.1:18890/?run=int-4e920c0d8f6646ed&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-4e920c0d8f6646ed/artifacts/art-852e56777fa8421d)
- [response_ref](http://127.0.0.1:18890/api/runs/int-4e920c0d8f6646ed/artifacts/art-d41ec13dffaf493c)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-4e920c0d8f6646ed/artifacts/art-9b6f86c091064fca)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-4e920c0d8f6646ed/artifacts/art-f8b9c3099a7143be)

## G055 · flask · 平台能力不足

原文禁止执行 IO 以及成为可能 IO 路径的一部分，但未说明可通过哪些公开 API 触发或观察该约束；当前执行契约没有 IO/系统调用拦截、网络观测或“非 IO 路径”判定协议，无法设计有依据的输入与预期。

- 分类来源：model
- 定位：R2
- 依据文档：src/flask/sansio/README.md · src/flask/sansio/README.md#chars=0:229
- [执行记录](http://127.0.0.1:18890/?run=int-4e920c0d8f6646ed&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-4e920c0d8f6646ed/artifacts/art-852e56777fa8421d)
- [response_ref](http://127.0.0.1:18890/api/runs/int-4e920c0d8f6646ed/artifacts/art-d41ec13dffaf493c)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-4e920c0d8f6646ed/artifacts/art-9b6f86c091064fca)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-4e920c0d8f6646ed/artifacts/art-f8b9c3099a7143be)

## G056 · flask · 平台能力不足

原文禁止使用 Flask globals，但没有列出需检查的公开入口、允许的上下文条件或可观察结果；现有协议无法证明某次调用未读取 Flask 全局代理，缺少执行与观察协议。

- 分类来源：model
- 定位：R3
- 依据文档：src/flask/sansio/README.md · src/flask/sansio/README.md#chars=0:229
- [执行记录](http://127.0.0.1:18890/?run=int-4e920c0d8f6646ed&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-4e920c0d8f6646ed/artifacts/art-852e56777fa8421d)
- [response_ref](http://127.0.0.1:18890/api/runs/int-4e920c0d8f6646ed/artifacts/art-d41ec13dffaf493c)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-4e920c0d8f6646ed/artifacts/art-9b6f86c091064fca)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-4e920c0d8f6646ed/artifacts/art-f8b9c3099a7143be)

## G057 · flask · 待分类

该组件没有经过依据校验的业务用例；其他任务继续，缺口保留

- 分类来源：execution-stage
- 定位：u-b6b2594aef-business
- [执行记录](http://127.0.0.1:18890/?run=int-4e920c0d8f6646ed&tab=flow&evidence=run)

## G058 · flask · 待分类

B16-c_register_post · 有效注册重定向到登录页且用户可查询：该用例未完整执行，查看逐步原件

- 分类来源：execution-stage
- 定位：B16-c_register_post
- [执行记录](http://127.0.0.1:18890/?run=int-4e920c0d8f6646ed&tab=flow&evidence=run)
- [task-report](http://127.0.0.1:18890/api/runs/int-4e920c0d8f6646ed/artifacts/art-20156d7ca01346e8)
- [u-6d5d23e8a9-business/cases.json](http://127.0.0.1:18890/api/runs/int-4e920c0d8f6646ed/artifacts/art-b48e41234ee54f3e)

## G059 · flask · 待分类

B16-c_register_invalid · 三种无效注册输入返回对应错误消息：该用例未完整执行，查看逐步原件

- 分类来源：execution-stage
- 定位：B16-c_register_invalid
- [执行记录](http://127.0.0.1:18890/?run=int-4e920c0d8f6646ed&tab=flow&evidence=run)
- [task-report](http://127.0.0.1:18890/api/runs/int-4e920c0d8f6646ed/artifacts/art-20156d7ca01346e8)
- [u-6d5d23e8a9-business/cases.json](http://127.0.0.1:18890/api/runs/int-4e920c0d8f6646ed/artifacts/art-b48e41234ee54f3e)

## G060 · sqlite-utils · 缺少依据

D2 给出 base64 输入结构，但未给出插入后的 BLOB 列 schema、可读输出或二进制比较方式，无法确定可核对预期。

- 分类来源：model
- 定位：d2-binary-base64
- 依据文档：docs/cli.rst · docs/cli.rst#chars=32824:37727
- [执行记录](http://127.0.0.1:18890/?run=int-5aece2f0ce6f4be7&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-5aece2f0ce6f4be7/artifacts/art-ef207deea2fd415a)
- [response_ref](http://127.0.0.1:18890/api/runs/int-5aece2f0ce6f4be7/artifacts/art-90606b6338da4bce)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-5aece2f0ce6f4be7/artifacts/art-4a32deaeb5d047c7)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-5aece2f0ce6f4be7/artifacts/art-eba139a8f47841d5)

## G061 · sqlite-utils · 缺少依据

D2 只说明运行 ANALYZE，未说明可观察输出、统计表内容或检查方式，无法设计独立业务断言。

- 分类来源：model
- 定位：d2-analyze-option
- 依据文档：docs/cli.rst · docs/cli.rst#chars=32824:37727
- [执行记录](http://127.0.0.1:18890/?run=int-5aece2f0ce6f4be7&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-5aece2f0ce6f4be7/artifacts/art-ef207deea2fd415a)
- [response_ref](http://127.0.0.1:18890/api/runs/int-5aece2f0ce6f4be7/artifacts/art-90606b6338da4bce)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-5aece2f0ce6f4be7/artifacts/art-4a32deaeb5d047c7)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-5aece2f0ce6f4be7/artifacts/art-eba139a8f47841d5)

## G062 · sqlite-utils · 用例契约问题

引用不能在指定文档中唯一定位

- 分类来源：contract-validation
- 定位：no_detect_types
- 依据文档：docs/cli.rst · docs/cli.rst#chars=38471:43379
- [执行记录](http://127.0.0.1:18890/?run=int-5aece2f0ce6f4be7&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-5aece2f0ce6f4be7/artifacts/art-535129f238654b4c)
- [response_ref](http://127.0.0.1:18890/api/runs/int-5aece2f0ce6f4be7/artifacts/art-70469a71d04742bb)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-5aece2f0ce6f4be7/artifacts/art-1c3d7e14dc4e417e)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-5aece2f0ce6f4be7/artifacts/art-6cbb9cb82d4a4673)

## G063 · sqlite-utils · 缺少依据

原文只说“尝试检测分隔符”，没有保证某类夹具会得到某个检测结果或适用条件，无法确定可断言正确输出；显式 --delimiter/--quotechar 已另项覆盖。

- 分类来源：model
- 定位：sniff_unresolved
- 依据文档：docs/cli.rst · docs/cli.rst#chars=38471:43379
- [执行记录](http://127.0.0.1:18890/?run=int-5aece2f0ce6f4be7&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-5aece2f0ce6f4be7/artifacts/art-535129f238654b4c)
- [response_ref](http://127.0.0.1:18890/api/runs/int-5aece2f0ce6f4be7/artifacts/art-70469a71d04742bb)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-5aece2f0ce6f4be7/artifacts/art-1c3d7e14dc4e417e)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-5aece2f0ce6f4be7/artifacts/art-6cbb9cb82d4a4673)

## G064 · sqlite-utils · 平台能力不足

进度条是否显示依赖终端/TTY，CLI 回执只能看到 stdout/stderr，缺少对进度条展示或隐藏的观察协议；--silent 不改变业务数据，不能据此设计通过标准。

- 分类来源：model
- 定位：silent_progress_unresolved
- 依据文档：docs/cli.rst · docs/cli.rst#chars=38471:43379
- [执行记录](http://127.0.0.1:18890/?run=int-5aece2f0ce6f4be7&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-5aece2f0ce6f4be7/artifacts/art-535129f238654b4c)
- [response_ref](http://127.0.0.1:18890/api/runs/int-5aece2f0ce6f4be7/artifacts/art-70469a71d04742bb)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-5aece2f0ce6f4be7/artifacts/art-1c3d7e14dc4e417e)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-5aece2f0ce6f4be7/artifacts/art-6cbb9cb82d4a4673)

## G065 · sqlite-utils · 缺少依据

D41 只说明 enable-fts/--fts4 会建立并填充索引，未给出 FTS 表 schema、search 输出或可断言的退出码，缺少正确输出与观察协议。

- 分类来源：model
- 定位：fts_enable_default
- 依据文档：docs/cli.rst · docs/cli.rst#chars=88191:89984
- [执行记录](http://127.0.0.1:18890/?run=int-5aece2f0ce6f4be7&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-5aece2f0ce6f4be7/artifacts/art-ba13d051840f4450)
- [response_ref](http://127.0.0.1:18890/api/runs/int-5aece2f0ce6f4be7/artifacts/art-8617775c805242f2)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-5aece2f0ce6f4be7/artifacts/art-b4ba3a54adc1469f)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-5aece2f0ce6f4be7/artifacts/art-67b25b1bb1504bb4)

## G066 · sqlite-utils · 缺少依据

文档要求后续数据需 populate-fts，但未给出填充后可查询的结果或索引状态，无法断言业务输出。

- 分类来源：model
- 定位：fts_populate_after_insert
- 依据文档：docs/cli.rst · docs/cli.rst#chars=88191:89984
- [执行记录](http://127.0.0.1:18890/?run=int-5aece2f0ce6f4be7&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-5aece2f0ce6f4be7/artifacts/art-ba13d051840f4450)
- [response_ref](http://127.0.0.1:18890/api/runs/int-5aece2f0ce6f4be7/artifacts/art-8617775c805242f2)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-5aece2f0ce6f4be7/artifacts/art-b4ba3a54adc1469f)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-5aece2f0ce6f4be7/artifacts/art-67b25b1bb1504bb4)

## G067 · sqlite-utils · 缺少依据

文档只说明 --create-triggers 自动更新索引，未给出触发器名称/schema 或搜索读回结果。

- 分类来源：model
- 定位：fts_create_triggers
- 依据文档：docs/cli.rst · docs/cli.rst#chars=88191:89984
- [执行记录](http://127.0.0.1:18890/?run=int-5aece2f0ce6f4be7&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-5aece2f0ce6f4be7/artifacts/art-ba13d051840f4450)
- [response_ref](http://127.0.0.1:18890/api/runs/int-5aece2f0ce6f4be7/artifacts/art-8617775c805242f2)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-5aece2f0ce6f4be7/artifacts/art-b4ba3a54adc1469f)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-5aece2f0ce6f4be7/artifacts/art-67b25b1bb1504bb4)

## G068 · sqlite-utils · 缺少依据

文档只说明 disable-fts 移除 FTS 表与触发器，未给出移除前后的可观察 schema/查询输出。

- 分类来源：model
- 定位：fts_disable
- 依据文档：docs/cli.rst · docs/cli.rst#chars=88191:89984
- [执行记录](http://127.0.0.1:18890/?run=int-5aece2f0ce6f4be7&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-5aece2f0ce6f4be7/artifacts/art-ba13d051840f4450)
- [response_ref](http://127.0.0.1:18890/api/runs/int-5aece2f0ce6f4be7/artifacts/art-8617775c805242f2)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-5aece2f0ce6f4be7/artifacts/art-b4ba3a54adc1469f)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-5aece2f0ce6f4be7/artifacts/art-67b25b1bb1504bb4)

## G069 · sqlite-utils · 缺少依据

文档只说明 rebuild-fts 可重建单表或全部 FTS 表，未给出重建后的搜索/索引可观察结果。

- 分类来源：model
- 定位：fts_rebuild
- 依据文档：docs/cli.rst · docs/cli.rst#chars=88191:89984
- [执行记录](http://127.0.0.1:18890/?run=int-5aece2f0ce6f4be7&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-5aece2f0ce6f4be7/artifacts/art-ba13d051840f4450)
- [response_ref](http://127.0.0.1:18890/api/runs/int-5aece2f0ce6f4be7/artifacts/art-8617775c805242f2)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-5aece2f0ce6f4be7/artifacts/art-b4ba3a54adc1469f)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-5aece2f0ce6f4be7/artifacts/art-67b25b1bb1504bb4)

## G070 · sqlite-utils · 缺少依据

文档只说明 --tokenize=porter 设置分词器，未给出分词差异的可观察查询输出。

- 分类来源：model
- 定位：fts_tokenize
- 依据文档：docs/cli.rst · docs/cli.rst#chars=88191:89984
- [执行记录](http://127.0.0.1:18890/?run=int-5aece2f0ce6f4be7&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-5aece2f0ce6f4be7/artifacts/art-ba13d051840f4450)
- [response_ref](http://127.0.0.1:18890/api/runs/int-5aece2f0ce6f4be7/artifacts/art-8617775c805242f2)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-5aece2f0ce6f4be7/artifacts/art-b4ba3a54adc1469f)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-5aece2f0ce6f4be7/artifacts/art-67b25b1bb1504bb4)

## G071 · sqlite-utils · 用例契约问题

观察调用必须独立断言其实际异常或返回结果，不能仅检查旁路状态：obs

- 分类来源：contract-validation
- 定位：failed_migration_rolls_back
- 依据文档：docs/migrations.rst · docs/migrations.rst#chars=0:4982
- [执行记录](http://127.0.0.1:18890/?run=int-5aece2f0ce6f4be7&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-5aece2f0ce6f4be7/artifacts/art-41b11c1c06094f5b)
- [response_ref](http://127.0.0.1:18890/api/runs/int-5aece2f0ce6f4be7/artifacts/art-5e85e7aae29e4644)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-5aece2f0ce6f4be7/artifacts/art-72e29873588943a0)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-5aece2f0ce6f4be7/artifacts/art-127464e0f7684246)

## G072 · sqlite-utils · 用例契约问题

观察调用必须独立断言其实际异常或返回结果，不能仅检查旁路状态：obs

- 分类来源：contract-validation
- 定位：nontransactional_partial_persists
- 依据文档：docs/migrations.rst · docs/migrations.rst#chars=0:4982
- [执行记录](http://127.0.0.1:18890/?run=int-5aece2f0ce6f4be7&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-5aece2f0ce6f4be7/artifacts/art-41b11c1c06094f5b)
- [response_ref](http://127.0.0.1:18890/api/runs/int-5aece2f0ce6f4be7/artifacts/art-5e85e7aae29e4644)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-5aece2f0ce6f4be7/artifacts/art-72e29873588943a0)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-5aece2f0ce6f4be7/artifacts/art-127464e0f7684246)

## G073 · sqlite-utils · 平台能力不足

已有只读语义依据，但缺少对不存在路径做未创建观察的协议，无法断言数据库文件和 _sqlite_migrations 表均未创建。

- 分类来源：model
- 定位：list_readonly_no_create
- 依据文档：docs/migrations.rst · docs/migrations.rst#chars=4982:7816
- [执行记录](http://127.0.0.1:18890/?run=int-5aece2f0ce6f4be7&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-5aece2f0ce6f4be7/artifacts/art-41b11c1c06094f5b)
- [response_ref](http://127.0.0.1:18890/api/runs/int-5aece2f0ce6f4be7/artifacts/art-5e85e7aae29e4644)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-5aece2f0ce6f4be7/artifacts/art-72e29873588943a0)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-5aece2f0ce6f4be7/artifacts/art-127464e0f7684246)

## G074 · sqlite-utils · 缺少依据

文档只说明会以错误退出，未给出退出码数值或 stderr 文本格式，无法断言具体错误回执。

- 分类来源：model
- 定位：stop_before_error_signal
- 依据文档：docs/migrations.rst · docs/migrations.rst#chars=4982:7816
- [执行记录](http://127.0.0.1:18890/?run=int-5aece2f0ce6f4be7&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-5aece2f0ce6f4be7/artifacts/art-41b11c1c06094f5b)
- [response_ref](http://127.0.0.1:18890/api/runs/int-5aece2f0ce6f4be7/artifacts/art-5e85e7aae29e4644)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-5aece2f0ce6f4be7/artifacts/art-72e29873588943a0)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-5aece2f0ce6f4be7/artifacts/art-127464e0f7684246)

## G075 · sqlite-utils · 缺少依据

文档只说明显示迁移前后 schema 和变更时的 unified diff，未给出可断言的标题、边界或 diff 文本格式。

- 分类来源：model
- 定位：verbose_schema_diff
- 依据文档：docs/migrations.rst · docs/migrations.rst#chars=4982:7816
- [执行记录](http://127.0.0.1:18890/?run=int-5aece2f0ce6f4be7&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-5aece2f0ce6f4be7/artifacts/art-41b11c1c06094f5b)
- [response_ref](http://127.0.0.1:18890/api/runs/int-5aece2f0ce6f4be7/artifacts/art-5e85e7aae29e4644)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-5aece2f0ce6f4be7/artifacts/art-72e29873588943a0)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-5aece2f0ce6f4be7/artifacts/art-127464e0f7684246)

## G076 · sqlite-utils · 环境未就绪

需要一个已安装并实现 Database 钩子的插件才能观察插件是否被禁用；当前环境没有此类插件，文档也未给出可读回的 execute_plugins 状态字段，因此无法验证退出效果。

- 分类来源：model
- 定位：database-execute-plugins-opt-out
- 依据文档：docs/plugins.rst · docs/plugins.rst#chars=0:4608
- [执行记录](http://127.0.0.1:18890/?run=int-5aece2f0ce6f4be7&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-5aece2f0ce6f4be7/artifacts/art-46aaeab15970483e)
- [response_ref](http://127.0.0.1:18890/api/runs/int-5aece2f0ce6f4be7/artifacts/art-4dc56598a7fe4cc7)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-5aece2f0ce6f4be7/artifacts/art-b9fa189754394630)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-5aece2f0ce6f4be7/artifacts/art-074c0b6c6f394ac7)

## G077 · sqlite-utils · 环境未就绪

验证需要安装一个通过 sqlite_utils 入口点加载并实现 register_commands 的插件；当前环境没有该插件，且不能仅靠调用无实现的 hookspec 观察命令注册。

- 分类来源：model
- 定位：register-commands-hook
- 依据文档：docs/plugins.rst · docs/plugins.rst#chars=0:4608
- [执行记录](http://127.0.0.1:18890/?run=int-5aece2f0ce6f4be7&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-5aece2f0ce6f4be7/artifacts/art-46aaeab15970483e)
- [response_ref](http://127.0.0.1:18890/api/runs/int-5aece2f0ce6f4be7/artifacts/art-4dc56598a7fe4cc7)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-5aece2f0ce6f4be7/artifacts/art-b9fa189754394630)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-5aece2f0ce6f4be7/artifacts/art-074c0b6c6f394ac7)

## G078 · sqlite-utils · 环境未就绪

文档承诺 prepare_connection 由插件在新 SQLite 连接创建时调用并注册 hello；当前没有安装实现该钩子的插件，无法在 Database 连接上观察 select hello("world") 返回 Hello, world!。

- 分类来源：model
- 定位：prepare-connection-hook
- 依据文档：docs/plugins.rst · docs/plugins.rst#chars=0:4608
- [执行记录](http://127.0.0.1:18890/?run=int-5aece2f0ce6f4be7&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-5aece2f0ce6f4be7/artifacts/art-46aaeab15970483e)
- [response_ref](http://127.0.0.1:18890/api/runs/int-5aece2f0ce6f4be7/artifacts/art-4dc56598a7fe4cc7)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-5aece2f0ce6f4be7/artifacts/art-b9fa189754394630)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-5aece2f0ce6f4be7/artifacts/art-074c0b6c6f394ac7)

## G079 · sqlite-utils · 环境未就绪

需要已安装的 hello-world 插件入口点；当前环境只有 sqlite-utils 本体，没有该插件，无法执行 sqlite-utils hello-world 或检查 --help 列表。

- 分类来源：model
- 定位：plugin-command-availability
- 依据文档：docs/plugins.rst · docs/plugins.rst#chars=0:4608
- [执行记录](http://127.0.0.1:18890/?run=int-5aece2f0ce6f4be7&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-5aece2f0ce6f4be7/artifacts/art-46aaeab15970483e)
- [response_ref](http://127.0.0.1:18890/api/runs/int-5aece2f0ce6f4be7/artifacts/art-4dc56598a7fe4cc7)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-5aece2f0ce6f4be7/artifacts/art-b9fa189754394630)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-5aece2f0ce6f4be7/artifacts/art-074c0b6c6f394ac7)

## G080 · sqlite-utils · 平台能力不足

需要可注册的插件命令、click.Context.invoke 和 memory 命令返回 Database 的执行/观察协议；当前 scenario 只能调用已声明公开接口，未提供注册任意插件命令或构造 click 上下文调用 memory 的能力。

- 分类来源：model
- 定位：plugin-memory-return-db
- 依据文档：docs/plugins.rst · docs/plugins.rst#chars=0:4608
- [执行记录](http://127.0.0.1:18890/?run=int-5aece2f0ce6f4be7&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-5aece2f0ce6f4be7/artifacts/art-46aaeab15970483e)
- [response_ref](http://127.0.0.1:18890/api/runs/int-5aece2f0ce6f4be7/artifacts/art-4dc56598a7fe4cc7)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-5aece2f0ce6f4be7/artifacts/art-b9fa189754394630)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-5aece2f0ce6f4be7/artifacts/art-074c0b6c6f394ac7)

## G081 · sqlite-utils · 待分类

B3-mem-type-disabled · --no-detect-types 使 age 为 TEXT：该用例未完整执行，查看逐步原件

- 分类来源：execution-stage
- 定位：B3-mem-type-disabled
- [执行记录](http://127.0.0.1:18890/?run=int-5aece2f0ce6f4be7&tab=flow&evidence=run)
- [task-report](http://127.0.0.1:18890/api/runs/int-5aece2f0ce6f4be7/artifacts/art-9206ff8961994387)
- [u-22b112d0be-business/cases.json](http://127.0.0.1:18890/api/runs/int-5aece2f0ce6f4be7/artifacts/art-dad7076e702d4c4a)

## G082 · sqlite-utils · 待分类

B6-unknown_stop_no_apply · 未知停止名不建表：该用例未完整执行，查看逐步原件

- 分类来源：execution-stage
- 定位：B6-unknown_stop_no_apply
- [执行记录](http://127.0.0.1:18890/?run=int-5aece2f0ce6f4be7&tab=flow&evidence=run)
- [task-report](http://127.0.0.1:18890/api/runs/int-5aece2f0ce6f4be7/artifacts/art-9206ff8961994387)
- [u-22b112d0be-business/cases.json](http://127.0.0.1:18890/api/runs/int-5aece2f0ce6f4be7/artifacts/art-dad7076e702d4c4a)

## G083 · sqlite-utils · 待分类

B6-applied_stop_no_pending_apply · 已应用停止名不执行待处理迁移：该用例未完整执行，查看逐步原件

- 分类来源：execution-stage
- 定位：B6-applied_stop_no_pending_apply
- [执行记录](http://127.0.0.1:18890/?run=int-5aece2f0ce6f4be7&tab=flow&evidence=run)
- [task-report](http://127.0.0.1:18890/api/runs/int-5aece2f0ce6f4be7/artifacts/art-9206ff8961994387)
- [u-22b112d0be-business/cases.json](http://127.0.0.1:18890/api/runs/int-5aece2f0ce6f4be7/artifacts/art-dad7076e702d4c4a)
