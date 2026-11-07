# Hugging Face 官方离线模式校准

正式断网验证使用 HF_HUB_OFFLINE=1。
依据官方环境变量说明，HfApi.model_info 应直接抛出 OfflineModeIsEnabled，不尝试请求远程API。
https://huggingface.co/docs/huggingface_hub/package_reference/environment_variables#hfhuboffline
该项目不提供模型权重或目标仓库专用逻辑。
