# run_experiment.py
import time
import pandas as pd
from playwright.sync_api import sync_playwright
from agent import get_ai_decision
from config import HEADLESS_MODE, RESULT_FILE, ACTION_TIMEOUT

EXPERIMENT_TASKS = [
    {
        "id": 1,
        "name": "Baidu Search",
        "url": "https://www.baidu.com",
        "goal": "在搜索框输入 'DeepSeek'，然后按回车搜索", # 提示改得更明确
        "max_steps": 5
    },
    {
        "id": 2,
        "name": "Wiki Search",
        "url": "https://en.wikipedia.org/wiki/Main_Page",
        "goal": "在右上角搜索框输入 'AI' 并按回车",
        "max_steps": 5
    }
]

# === 核心 JS：注入ID + 同步Input值 ===
INJECT_JS = """
() => {
    let id_counter = 0;
    const elements = document.querySelectorAll('a, button, input, textarea, select, [role="button"], [role="link"]');
    
    elements.forEach(el => {
        const rect = el.getBoundingClientRect();
        const style = window.getComputedStyle(el);
        if (rect.width > 0 && rect.height > 0 && style.visibility !== 'hidden' && style.display !== 'none') {
            
            el.setAttribute('data-agent-id', id_counter.toString());
            
            // 关键：把当前输入框的值显式写到 HTML 属性里，这样 Python 才能读到
            if (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA') {
                el.setAttribute('value', el.value);
            }

            el.style.border = "2px solid red";
            el.setAttribute('title', `ID: ${id_counter}`);
            id_counter++;
        }
    });
    return id_counter;
}
"""

def execute_task(task, browser_context):
    print(f"\n🚀 开始任务: {task['name']}")
    page = browser_context.new_page()
    
    try:
        page.goto(task['url'], timeout=30000)
        page.wait_for_load_state("domcontentloaded")
    except Exception as e:
        print(f"  ❌ 加载失败: {e}")
        page.close()
        return None

    task_data = {
        "task_name": task['name'],
        "success": False,
        "steps_taken": 0,
        "total_tokens": 0,
        "total_latency": 0
    }
    
    # 记录上一步的操作，传给 AI
    last_action_desc = "None (Start)"

    for step in range(task['max_steps']):
        print(f"  Step {step+1}...", end="", flush=True)
        
        try:
            page.evaluate(INJECT_JS)
            time.sleep(0.5)
        except:
            pass

        html = page.content()
        # 传入 last_action_desc
        decision, tokens, latency, _ = get_ai_decision(task['goal'], html, last_action_desc)
        
        task_data['total_tokens'] += tokens
        task_data['total_latency'] += latency
        
        action = decision.get('action')
        target_id = decision.get('id')
        val = decision.get('value')
        
        print(f" 🤖 决策: {action} | ID: {target_id} | Val: {val}")
        
        # 更新记忆
        last_action_desc = f"{action} on ID {target_id} with value '{val}'"
        
        if action == "finish":
            print("  ✅ 任务完成")
            task_data['success'] = True
            break
            
        try:
            # === 新增：键盘操作 (回车) ===
            if action == "key":
                # 按键操作通常不需要 ID，直接按当前焦点
                # 如果 AI 给了 ID，我们可以先点一下那个元素聚焦，再按回车
                if target_id:
                    selector = f'[data-agent-id="{target_id}"]'
                    if page.locator(selector).count() > 0:
                         page.locator(selector).first.press(val)
                    else:
                        page.keyboard.press(val)
                else:
                    page.keyboard.press(val)
                    
                print(f"  ⌨️ 按键: {val}")
                time.sleep(3) # 等待搜索跳转
                
            elif target_id:
                selector = f'[data-agent-id="{target_id}"]'
                if page.locator(selector).count() == 0:
                    print("  ❌ 元素丢失")
                    continue
                
                loc = page.locator(selector).first
                
                if action == "click":
                    loc.click(timeout=ACTION_TIMEOUT)
                elif action == "type":
                    # 防呆检查
                    tag_name = loc.evaluate("el => el.tagName.toLowerCase()")
                    if tag_name not in ['input', 'textarea']:
                        print("  ⚠️ 不是输入框，尝试点击...")
                        loc.click(timeout=ACTION_TIMEOUT)
                    else:
                        loc.fill(val, timeout=ACTION_TIMEOUT)
                
                time.sleep(2)
                
        except Exception as e:
            print(f"  ❌ 执行出错: {str(e).splitlines()[0]}")
            
        task_data['steps_taken'] += 1
        
    page.close()
    return task_data

def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=HEADLESS_MODE)
        context = browser.new_context()
        results = []
        for task in EXPERIMENT_TASKS:
            data = execute_task(task, context)
            if data: results.append(data)
        browser.close()
    
    if results:
        df = pd.DataFrame(results)
        df.to_csv(RESULT_FILE, index=False)
        print(f"\n✅ 结果已保存: {RESULT_FILE}")
        print(df)

if __name__ == "__main__":
    main()