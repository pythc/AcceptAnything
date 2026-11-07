# 标准词表资源准备契约

已安装Tiktoken注册表中的每个编码都应能在正式断网环境下实例化，并编码非空文本。准备过程使用包自身list_encoding_names/get_encoding及其缓存和下载哈希校验，不根据被验收项目名字选择编码，不改业务输入或预期。
官方实现：https://github.com/openai/tiktoken/blob/main/tiktoken/registry.py
缓存与哈希校验：https://github.com/openai/tiktoken/blob/main/tiktoken/load.py
