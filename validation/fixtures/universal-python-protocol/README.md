平台协议校准：request_summary(3)和model_summary(3)的JSON表示均为{"method":"GET","value":6}，只构造请求，不发送网络流量。
GET / 返回h1文本“验收校准”。GET /large返回超过2MiB的JSON，最后字段tail为“完整末尾”，不得截断。
