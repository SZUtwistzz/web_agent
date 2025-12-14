# agent.py
import json
import time
from openai import OpenAI
from config import API_KEY, BASE_URL, MODEL_NAME
from cleaner import get_simplified_html

client = OpenAI(api_key=API_KEY, base_url=BASE_URL)

def get_ai_decision(task_description, page, page_html, last_action_desc="None"):
    # 1. 清洗页面
    obs_text, _, clean_len = get_simplified_html(page, page_html)
    
    # 2. 构造 Prompt (核心修改：增加防循环逻辑)
    system_prompt = f"""
    你是一个全能 Web Agent。
    当前网页状态:
    ===
    {obs_text}
    ===
    
    总任务: "{task_description}"
    上一步操作: "{last_action_desc}"
    
    ⚠️ 必须严格遵守的决策逻辑:
    1. **禁止回退 (Anti-Loop)**: 
       - 如果上一步操作是 "key Enter" 或 "click search"，且当前 URL 已经发生变化（例如变成了 /search 或 /result），说明搜索已成功！
       - 此时，即使任务里写着“去某某网站”，也**绝对不要**再使用 "goto" 跳回首页！请直接在当前页面寻找结果。
    
    2. **域名检查 (Domain Check)**:
       - 如果任务要求去 "movie.douban.com"，而当前 URL 是 "search.douban.com"，这属于同一个网站的子页面，**视为已到达**，不需要再 goto。

    3. **常规操作**:
       - 输入检查: 如果 [输入框] 里的内容已正确，直接按 key Enter。
       - 滚动: 如果找不到目标，使用 "scroll"。
       - 结束: 找到答案后，输出 finish。
    
    输出 JSON:
    {{
        "action": "click" | "type" | "key" | "scroll" | "goto" | "finish",
        "id": "目标ID",
        "value": "内容",
        "reasoning": "解释为什么（例如：URL已变，搜索成功，不再跳转，开始寻找海报...）"
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