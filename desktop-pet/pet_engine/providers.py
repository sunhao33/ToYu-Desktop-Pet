"""模型服务商配置（引擎层）。

放在 pet_engine 而不是 ui：`pet_ai.py` 需要用到本机地址白名单做 https
校验，而**引擎层不应该反向依赖界面层**（`from ui.xxx import`）。
界面要展示的服务商列表也从这里取，保持单一来源。

ToYu 走的是 **OpenAI 兼容**的 /chat/completions 接口，所以只要能对上
这个协议的厂商都能直接用，不限于某一家。
"""

# 允许走明文 http 的主机（本机回环）。
#
# 为什么需要例外：API Key 放在请求头里，远程走 http 会让它在网络上暴露，
# 所以要强制 https。但本机地址数据不出本机、没有中间人风险，而本地推理
# 服务（Ollama 等）默认就是 http —— 一刀切会把本地模型挡在门外。
LOCAL_HOSTS = frozenset({"localhost", "127.0.0.1", "::1", "0.0.0.0"})

# 服务商预设：(显示名, API 地址, 默认模型)
AI_PROVIDERS = (
    ("DeepSeek（深度求索）", "https://api.deepseek.com/v1", "deepseek-chat"),
    ("阿里云百炼 · 通义千问",
     "https://dashscope.aliyuncs.com/compatible-mode/v1", "qwen-plus"),
    ("月之暗面 Kimi", "https://api.moonshot.cn/v1", "moonshot-v1-8k"),
    ("智谱 GLM", "https://open.bigmodel.cn/api/paas/v4", "glm-4-flash"),
    ("OpenAI", "https://api.openai.com/v1", "gpt-4o-mini"),
    ("硅基流动 SiliconFlow", "https://api.siliconflow.cn/v1",
     "Qwen/Qwen2.5-7B-Instruct"),
    ("本地 Ollama（本机）", "http://localhost:11434/v1", "qwen2.5:7b"),
)
