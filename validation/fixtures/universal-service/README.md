# 通用服务协议校准契约

这是平台验证夹具，不是第三方真实项目，源码不能用于设计预期。

- HTTP GET /health 必须返回 HTTP 200 和 JSON 对象 {"status":"ready"}。
- HTTP GET /unknown 必须返回 HTTP 404 和 JSON 对象 {"error":"missing"}。
- 浏览器打开 /，h1 元素的可见文本必须准确等于“验收协议校准服务”。这条必须通过真实浏览器验证，不能由 HTTP 获取 HTML 冒充。
- 运行使用 package.json 声明的 start 命令，监听环境变量 PORT 指定的端口。

没有给出性能和恢复标准，不产生其通过结果。
