# debug_check.py
import agent

print("正在检查 agent.py 的内容...")
print(f"文件路径: {agent.__file__}")

# 看看 agent 里面到底有什么
print("agent 里面包含的函数和变量有:")
print(dir(agent))

if 'get_ai_decision' in dir(agent):
    print("\n[成功] 找到 get_ai_decision 函数了。")
else:
    print("\n[失败] agent.py 里没有 get_ai_decision。")
    print("请确认你是否保存了文件 (Ctrl+S)？")