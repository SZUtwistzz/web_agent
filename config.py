# config.py
import os

# === API 配置 (DeepSeek) ===
API_KEY = "sk-b38bca71114c41c38dd6415277d6dcf7"  # ⚠️ 把你的 Key 填在这里
BASE_URL = "https://api.deepseek.com"
MODEL_NAME = "deepseek-chat"

# === 实验配置 ===
RESULT_FILE = "experiment_results.csv"
HEADLESS_MODE = False  # 设置为 False，你可以看到浏览器自动操作
ACTION_TIMEOUT = 5000  # 动作超时时间 (毫秒)，5秒点不到就报错，不傻等
