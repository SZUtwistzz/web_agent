# agent.py
import json
import time
from openai import OpenAI
from config import API_KEY, BASE_URL, MODEL_NAME
from cleaner import get_simplified_html

client = OpenAI(api_key=API_KEY, base_url=BASE_URL)

def get_ai_decision(task_description, page_html, last_action_desc="None"):
    # 1. 清洗页面
    obs_text, _, clean_len = get_simplified_html(page_html)
    
    # 2. 构造 Prompt (增加记忆和回车指令)
    system_prompt = f"""
    你是一个Web自动化助手。
    下面是网页当前状态。
    ===
    {obs_text}
    ===
    
    你的任务: "{task_description}"
    上一步你的操作是: "{last_action_desc}"
    
    ⚠️ 决策逻辑：
    1. 如果你在 [输入框] 里看到了 CURRENT_VALUE 等于你要输的内容，**不要再 type 了**！
    2. 搜索时，输入完文字后，推荐使用 **"key"** 动作按 **"Enter"** 键，这比点击按钮更稳健。
    3. 如果上一步操作失败了，请尝试不同的方法。
    
    请输出 JSON:
    {{
        "action": "click" | "type" | "key" | "finish",
        "id": "目标ID",
        "value": "输入内容 OR 按键名称(如 Enter)",
        "reasoning": "理由"
    }}
    """
    
    start_time = time.time()
    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[{"role": "user", "content": system_prompt}],
            response_format={"type": "json_object"},
            temperature=0.0
        )
        content = response.choices[0].message.content
        decision = json.loads(content)
        
        if 'id' in decision and isinstance(decision['id'], int):
            decision['id'] = str(decision['id'])
            
        return decision, response.usage.total_tokens, time.time() - start_time, clean_len
        
    except Exception as e:
        print(f"LLM Error: {e}")
        return {"action": "finish", "reasoning": "Error"}, 0, 0, 0