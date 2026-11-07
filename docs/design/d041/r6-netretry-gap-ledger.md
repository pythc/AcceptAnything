# D041 r6 Fastify 同版追加复跑 逐项覆盖缺口账本

仅整理已终态、完整性验证通过的记录。模型分类仍标明来源；执行错误、缺少依据和未覆盖均不能视为确认产品缺陷。未自动删除语义相近的模型意见，原始条目数不等于不重复需求数或覆盖率。

## G001 · fastify · 平台能力不足

文档规定 callback 接收 (err, address)，但当前 scenario 对带 callback 的 listen 没有可等待的 Promise，也缺少等待回调触发并独立观察 err/address 参数的协议；不能只检查监听端口替代回调参数验收。

- 分类来源：model
- 定位：d2-listen-callback
- 依据文档：docs/Reference/Server.md · docs/Reference/Server.md#chars=41939:45203
- [执行记录](http://127.0.0.1:18890/?run=int-9ebeca89d0194c8d&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-9ebeca89d0194c8d/artifacts/art-28fe2984bafc4a23)
- [response_ref](http://127.0.0.1:18890/api/runs/int-9ebeca89d0194c8d/artifacts/art-69228a2baf014a43)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-9ebeca89d0194c8d/artifacts/art-6009345421a74d99)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-9ebeca89d0194c8d/artifacts/art-de74e1aad6304021)

## G002 · fastify · 平台能力不足

文档要求自定义启动日志文本，但当前执行契约未声明日志流或日志观察协议；无法捕获并比较 listen 成功后实际输出的日志文本，不能把配置了 listenTextResolver 当作覆盖。

- 分类来源：model
- 定位：d2-listen-text-resolver
- 依据文档：docs/Reference/Server.md · docs/Reference/Server.md#chars=41939:45203
- [执行记录](http://127.0.0.1:18890/?run=int-9ebeca89d0194c8d&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-9ebeca89d0194c8d/artifacts/art-28fe2984bafc4a23)
- [response_ref](http://127.0.0.1:18890/api/runs/int-9ebeca89d0194c8d/artifacts/art-69228a2baf014a43)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-9ebeca89d0194c8d/artifacts/art-6009345421a74d99)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-9ebeca89d0194c8d/artifacts/art-de74e1aad6304021)

## G003 · fastify · 环境未就绪

要验证服务器在异步数据库连接完成前不接受连接，需要一个可挂起且可观察完成的连接插件，并在完成前尝试连接。当前 service_graph 无 MongoDB 节点，@fastify/mongodb 未索引，scenario 没有延迟或挂起夹具，无法准备该前置条件。

- 分类来源：model
- 定位：async-connector-before-listen
- 依据文档：docs/Guides/Getting-Started.md · docs/Guides/Getting-Started.md#chars=4967:9913
- [执行记录](http://127.0.0.1:18890/?run=int-9ebeca89d0194c8d&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-9ebeca89d0194c8d/artifacts/art-515d0dca921e4a7b)
- [response_ref](http://127.0.0.1:18890/api/runs/int-9ebeca89d0194c8d/artifacts/art-4e6782f0abd94a73)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-9ebeca89d0194c8d/artifacts/art-adef1f0522ee4dbc)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-9ebeca89d0194c8d/artifacts/art-e81a3e40ad8843da)

## G004 · fastify · 平台能力不足

需要在两个插件加载过程中记录顺序与前一个完成信号；当前 scenario 回调只能调用公开方法且不能共享可变序列，fastify-plugin 与 skip-override 未索引，无法构造可观察的加载顺序夹具。

- 分类来源：model
- 定位：plugin-order
- 依据文档：docs/Guides/Getting-Started.md · docs/Guides/Getting-Started.md#chars=4967:9913
- [执行记录](http://127.0.0.1:18890/?run=int-9ebeca89d0194c8d&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-9ebeca89d0194c8d/artifacts/art-515d0dca921e4a7b)
- [response_ref](http://127.0.0.1:18890/api/runs/int-9ebeca89d0194c8d/artifacts/art-4e6782f0abd94a73)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-9ebeca89d0194c8d/artifacts/art-adef1f0522ee4dbc)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-9ebeca89d0194c8d/artifacts/art-e81a3e40ad8843da)

## G005 · fastify · 环境未就绪

该标准依赖 fastify-plugin 包装和 @fastify/mongodb 的 mongo 装饰器；discovery.interfaces 未索引这两个包，service_graph 无 MongoDB，无法注册可用的 dbConnector 并在 routes 插件读取 fastify.mongo。需先准备依赖与服务。

- 分类来源：model
- 定位：fastify-plugin-scope
- 依据文档：docs/Guides/Getting-Started.md · docs/Guides/Getting-Started.md#chars=4967:9913
- [执行记录](http://127.0.0.1:18890/?run=int-9ebeca89d0194c8d&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-9ebeca89d0194c8d/artifacts/art-515d0dca921e4a7b)
- [response_ref](http://127.0.0.1:18890/api/runs/int-9ebeca89d0194c8d/artifacts/art-4e6782f0abd94a73)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-9ebeca89d0194c8d/artifacts/art-adef1f0522ee4dbc)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-9ebeca89d0194c8d/artifacts/art-e81a3e40ad8843da)

## G006 · fastify · 环境未就绪

需要 MongoDB test_database/test_collection 预置文档、空集合和无匹配 animal 三种状态；当前无 MongoDB 服务与驱动索引，无法播种和读回。文档只给出 throw 错误文本，未给 HTTP 状态与错误响应序列化，观察协议也需先确定。

- 分类来源：model
- 定位：animals-read-routes
- 依据文档：docs/Guides/Getting-Started.md · docs/Guides/Getting-Started.md#chars=4967:9913
- [执行记录](http://127.0.0.1:18890/?run=int-9ebeca89d0194c8d&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-9ebeca89d0194c8d/artifacts/art-515d0dca921e4a7b)
- [response_ref](http://127.0.0.1:18890/api/runs/int-9ebeca89d0194c8d/artifacts/art-4e6782f0abd94a73)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-9ebeca89d0194c8d/artifacts/art-adef1f0522ee4dbc)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-9ebeca89d0194c8d/artifacts/art-e81a3e40ad8843da)

## G007 · fastify · 缺少依据

文档只给出 body schema 与 insertOne 调用，未规定非法 body 的 HTTP 状态或错误体，也未规定 insertOne 返回结果的可观察结构；同时无 MongoDB 服务与集合夹具。需补充这些输出契约并准备数据库。

- 分类来源：model
- 定位：animals-post-schema
- 依据文档：docs/Guides/Getting-Started.md · docs/Guides/Getting-Started.md#chars=4967:9913
- [执行记录](http://127.0.0.1:18890/?run=int-9ebeca89d0194c8d&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-9ebeca89d0194c8d/artifacts/art-515d0dca921e4a7b)
- [response_ref](http://127.0.0.1:18890/api/runs/int-9ebeca89d0194c8d/artifacts/art-4e6782f0abd94a73)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-9ebeca89d0194c8d/artifacts/art-adef1f0522ee4dbc)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-9ebeca89d0194c8d/artifacts/art-e81a3e40ad8843da)

## G008 · fastify · 缺少依据

原文只说明使用 JSON Schema 验证请求，未给出不满足 body schema 时的状态码、错误体或可观察处理结果；无法为校验失败设计独立预期。

- 分类来源：model
- 定位：R-D34-validation-failure-gap
- 依据文档：docs/Guides/Getting-Started.md · docs/Guides/Getting-Started.md#chars=9913:14902
- [执行记录](http://127.0.0.1:18890/?run=int-9ebeca89d0194c8d&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-9ebeca89d0194c8d/artifacts/art-e33f36dfc37b4200)
- [response_ref](http://127.0.0.1:18890/api/runs/int-9ebeca89d0194c8d/artifacts/art-7e3466dfcca24c9f)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-9ebeca89d0194c8d/artifacts/art-65912d3d0f3b4de9)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-9ebeca89d0194c8d/artifacts/art-4809c292309046a6)

## G009 · fastify · 缺少依据

原文给出推荐加载顺序，但没有规定违反顺序时的错误或可观察结果，无法形成独立通过/失败标准。

- 分类来源：model
- 定位：R-D34-plugin-load-order-gap
- 依据文档：docs/Guides/Getting-Started.md · docs/Guides/Getting-Started.md#chars=9913:14902
- [执行记录](http://127.0.0.1:18890/?run=int-9ebeca89d0194c8d&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-9ebeca89d0194c8d/artifacts/art-e33f36dfc37b4200)
- [response_ref](http://127.0.0.1:18890/api/runs/int-9ebeca89d0194c8d/artifacts/art-7e3466dfcca24c9f)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-9ebeca89d0194c8d/artifacts/art-65912d3d0f3b4de9)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-9ebeca89d0194c8d/artifacts/art-4809c292309046a6)

## G010 · fastify · 缺少依据

原文只提出不得破坏打包构建的目标，并提示特性可能表现不同；没有给出具体 bundler 配置、输入样例、构建产物或可观察成功信号，且无 support 文档补足，故无法设计具体正向用例。

- 分类来源：model
- 定位：R1
- 依据文档：test/bundler/README.md · test/bundler/README.md#chars=0:1276
- [执行记录](http://127.0.0.1:18890/?run=int-9ebeca89d0194c8d&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-9ebeca89d0194c8d/artifacts/art-41d65b98c24d465f)
- [response_ref](http://127.0.0.1:18890/api/runs/int-9ebeca89d0194c8d/artifacts/art-bda1c0561a3f4f2c)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-9ebeca89d0194c8d/artifacts/art-4adf353d3ced485d)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-9ebeca89d0194c8d/artifacts/art-88e9e4cf821342d3)

## G011 · fastify · 平台能力不足

这是测试文件命名约定，需要检查仓库文件名并复现 Fastify 单元测试正则命中关系；当前只提供临时目录/隔离仓库的路径观察，缺少目录枚举与正则匹配执行协议，故保留未决。

- 分类来源：model
- 定位：R7
- 依据文档：test/bundler/README.md · test/bundler/README.md#chars=0:1276
- [执行记录](http://127.0.0.1:18890/?run=int-9ebeca89d0194c8d&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-9ebeca89d0194c8d/artifacts/art-41d65b98c24d465f)
- [response_ref](http://127.0.0.1:18890/api/runs/int-9ebeca89d0194c8d/artifacts/art-bda1c0561a3f4f2c)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-9ebeca89d0194c8d/artifacts/art-4adf353d3ced485d)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-9ebeca89d0194c8d/artifacts/art-88e9e4cf821342d3)

## G012 · fastify · 缺少依据

原文只规定测试应验证构建成功和 Fastify 应用可运行，并限定无需深度测试；没有给出具体应用入口、请求/响应或启动成功输出，且无 support 文档补足，无法形成可断言用例。

- 分类来源：model
- 定位：R8
- 依据文档：test/bundler/README.md · test/bundler/README.md#chars=0:1276
- [执行记录](http://127.0.0.1:18890/?run=int-9ebeca89d0194c8d&tab=flow&evidence=run)
- [input_ref](http://127.0.0.1:18890/api/runs/int-9ebeca89d0194c8d/artifacts/art-41d65b98c24d465f)
- [response_ref](http://127.0.0.1:18890/api/runs/int-9ebeca89d0194c8d/artifacts/art-bda1c0561a3f4f2c)
- [draft_ref](http://127.0.0.1:18890/api/runs/int-9ebeca89d0194c8d/artifacts/art-4adf353d3ced485d)
- [receipt_ref](http://127.0.0.1:18890/api/runs/int-9ebeca89d0194c8d/artifacts/art-88e9e4cf821342d3)

## G013 · fastify · 待分类

部分用例未完整执行

- 分类来源：execution-stage
- 定位：u-d935a3cdea-native
- [执行记录](http://127.0.0.1:18890/?run=int-9ebeca89d0194c8d&tab=flow&evidence=run)
- [task-report](http://127.0.0.1:18890/api/runs/int-9ebeca89d0194c8d/artifacts/art-d396f4655d53445b)

## G014 · fastify · 待分类

B1-d2-listen-default-case · 空 options 时使用随机端口和 localhost：该用例未完整执行，查看逐步原件

- 分类来源：execution-stage
- 定位：B1-d2-listen-default-case
- [执行记录](http://127.0.0.1:18890/?run=int-9ebeca89d0194c8d&tab=flow&evidence=run)
- [task-report](http://127.0.0.1:18890/api/runs/int-9ebeca89d0194c8d/artifacts/art-585dc3c1106f4051)
- [u-d935a3cdea-business/cases.json](http://127.0.0.1:18890/api/runs/int-9ebeca89d0194c8d/artifacts/art-579f15710137446d)

## G015 · fastify · 待分类

B1-d2-listen-ready-case · listen 完成时注册插件已 decorate：该用例未完整执行，查看逐步原件

- 分类来源：execution-stage
- 定位：B1-d2-listen-ready-case
- [执行记录](http://127.0.0.1:18890/?run=int-9ebeca89d0194c8d&tab=flow&evidence=run)
- [task-report](http://127.0.0.1:18890/api/runs/int-9ebeca89d0194c8d/artifacts/art-585dc3c1106f4051)
- [u-d935a3cdea-business/cases.json](http://127.0.0.1:18890/api/runs/int-9ebeca89d0194c8d/artifacts/art-579f15710137446d)
