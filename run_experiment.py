# run_experiment.py
import time
import pandas as pd
from playwright.sync_api import sync_playwright
from agent import get_ai_decision
from config import HEADLESS_MODE, RESULT_FILE, ACTION_TIMEOUT

# === 🔥 升级版复杂任务集 ===
EXPERIMENT_TASKS = [
    {
        "id": 1,
        "name": "Shopping Demo (Login & Add Cart)",
        "url": "https://www.saucedemo.com/",
        # 这个任务非常长，考验 Agent 的连续逻辑能力
        "goal": "1. 登录(用户名: standard_user, 密码: secret_sauce). 2. 找到 'Sauce Labs Backpack' 并点击 'Add to cart'. 3. 点击右上角的购物车图标.",
        "max_steps": 8 # 步骤给多一点
    },
    {
        "id": 2,
        "name": "Douban Movie Search",
        "url": "https://movie.douban.com/",
        "goal": "在搜索框输入 '肖申克的救赎' 并回车。在结果页中点击第一个电影标题(通常是带有海报的那个)。",
        "max_steps": 6
    },
    # 保留一个简单的做对比
    {
        "id": 3,
        "name": "Baidu Search",
        "url": "https://www.baidu.com",
        "goal": "在搜索框输入 'DeepSeek'，然后按回车", 
        "max_steps": 4
    }
]

# JS 注入逻辑保持不变
INJECT_JS = """
() => {
    let id_counter = 0;
    const elements = document.querySelectorAll('a, button, input, textarea, select, [role="button"], [role="link"], .inventory_item_name'); 
    // .inventory_item_name 是专门为 SauceDemo 加的，方便 AI 识别商品名
    
    elements.forEach(el => {
        const rect = el.getBoundingClientRect();
        const style = window.getComputedStyle(el);
        if (rect.width > 0 && rect.height > 0 && style.visibility !== 'hidden' && style.display !== 'none') {
            
            el.setAttribute('data-agent-id', id_counter.toString());
            
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
    
    last_action_desc = "None (Start)"

    for step in range(task['max_steps']):
        print(f"  Step {step+1}...", end="", flush=True)
        
        try:
            page.evaluate(INJECT_JS)
            time.sleep(0.5)
        except:
            pass

        html = page.content()
        decision, tokens, latency, _ = get_ai_decision(task['goal'], page, html, last_action_desc)
        
        task_data['total_tokens'] += tokens
        task_data['total_latency'] += latency
        
        action = decision.get('action')
        target_id = decision.get('id')
        val = decision.get('value')
        
        print(f" 🤖 决策: {action} | ID: {target_id} | Val: {val}")
        last_action_desc = f"{action} {target_id} val={val}"
        
        if action == "finish":
            print("  ✅ 任务完成")
            task_data['success'] = True
            break
            
        try:
            # === 新增：滚动操作 ===
            if action == "scroll":
                if val == "up":
                    page.evaluate("window.scrollBy(0, -500)")
                else: # 默认向下滚
                    page.evaluate("window.scrollBy(0, 500)")
                print("  📜 滚动页面...")
                time.sleep(2)
                
            # === 键盘操作 ===
            elif action == "key":
                if target_id: # 如果给了ID，先聚焦再按键
                    selector = f'[data-agent-id="{target_id}"]'
                    if page.locator(selector).count() > 0:
                         page.locator(selector).first.press(val)
                    else:
                        page.keyboard.press(val)
                else:
                    page.keyboard.press(val)
                print(f"  ⌨️ 按键: {val}")
                time.sleep(3) 
                
            # === 点击与输入 ===
            elif target_id:
                selector = f'[data-agent-id="{target_id}"]'
                if page.locator(selector).count() == 0:
                    print("  ❌ 元素丢失")
                    continue
                
                loc = page.locator(selector).first
                
                if action == "click":
                    loc.click(timeout=ACTION_TIMEOUT)
                elif action == "type":
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
        # headless=False 非常重要，你要看着它登录和买东西！
        browser = p.chromium.launch(headless=False)
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