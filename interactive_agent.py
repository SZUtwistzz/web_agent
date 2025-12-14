# interactive_agent.py
import time
from playwright.sync_api import sync_playwright
from agent import get_ai_decision
from config import HEADLESS_MODE, ACTION_TIMEOUT

INJECT_JS = """
() => {
    let id_counter = 0;
    const elements = document.querySelectorAll('a, button, input, textarea, select, [role="button"], [role="link"], h3, span, div[role="textbox"]');
    elements.forEach(el => {
        const rect = el.getBoundingClientRect();
        const style = window.getComputedStyle(el);
        if (rect.width > 0 && rect.height > 0 && style.visibility !== 'hidden' && style.display !== 'none') {
            el.setAttribute('data-agent-id', id_counter.toString());
            if (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA') { el.setAttribute('value', el.value); }
            el.style.border = "2px solid red";
            el.setAttribute('title', `ID: ${id_counter}`);
            id_counter++;
        }
    });
    return id_counter;
}
"""

def run_autonomous_loop(user_goal):
    print(f"\n🚀 启动任务: {user_goal}")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        
        # 默认起始页
        try:
            page.goto("https://www.baidu.com")
        except:
            pass

        last_action = "None (Start)"
        
        for step in range(20):
            print(f"\n--- 💡 Step {step+1} ---")
            
            # 1. 注入 JS
            try:
                page.evaluate(INJECT_JS)
                time.sleep(0.5)
            except:
                pass

            # 2. 获取决策
            html = page.content()
            try:
                decision, tokens, latency, _ = get_ai_decision(user_goal, page, html, last_action)
            except TypeError:
                 print("❌ 请确保 agent.py 已更新")
                 break

            action = decision.get('action')
            target_id = decision.get('id')
            val = decision.get('value')
            reason = decision.get('reasoning')
            
            print(f"🧠 思维: {reason}")
            print(f"🤖 动作: {action} | ID: {target_id} | Val: {val}")
            
            if action == "finish":
                print("🎉 任务完成！")
                break
            
            # 3. 执行
            try:
                # === 新增：GOTO 跳转逻辑 ===
                if action == "goto":
                    url = val
                    # 帮用户补全 https
                    if not url.startswith("http"):
                        url = "https://" + url
                    print(f"  🌍 正在跳转至: {url}")
                    page.goto(url)
                    last_action = f"Navigated to {url}"
                    time.sleep(3) # 等待加载
                
                # === 滚动 ===
                elif action == "scroll":
                    direction = -500 if val == "up" else 500
                    page.evaluate(f"window.scrollBy(0, {direction})")
                    last_action = "Scrolled"
                    time.sleep(2)
                
                # === 键盘 ===
                elif action == "key":
                    if target_id:
                        selector = f'[data-agent-id="{target_id}"]'
                        if page.locator(selector).count() > 0:
                            page.locator(selector).first.press(val)
                    else:
                        page.keyboard.press(val)
                    last_action = f"Pressed key {val}"
                    time.sleep(3)
                    
                # === 点击/输入 ===
                elif target_id:
                    selector = f'[data-agent-id="{target_id}"]'
                    locator = page.locator(selector)
                    
                    if locator.count() == 0:
                        print("❌ 元素找不到")
                        last_action = "Element not found"
                        continue
                        
                    loc = locator.first
                    
                    if action == "click":
                        loc.click(timeout=3000)
                        last_action = f"Clicked {target_id}"
                    elif action == "type":
                        # 防呆
                        tag_name = loc.evaluate("el => el.tagName.toLowerCase()")
                        if tag_name not in ['input', 'textarea']:
                            loc.click(timeout=3000)
                            last_action = f"Clicked {target_id} (fallback)"
                        else:
                            loc.fill(val, timeout=3000)
                            last_action = f"Typed {val}"
                    
                    time.sleep(2)
                    
            except Exception as e:
                print(f"执行出错: {str(e)[:50]}")
                last_action = "Action Failed"

        print("流程结束。")
        input("按回车退出...")
        browser.close()

if __name__ == "__main__":
    while True:
        cmd = input("\n请输入指令 (q退出): ")
        if cmd == 'q': break
        run_autonomous_loop(cmd)