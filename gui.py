import gradio as gr
import time
import os
import threading
import queue
from playwright.sync_api import sync_playwright
# 确保你的 agent.py 和 config.py 在同一目录下
from agent import get_ai_decision
from config import ACTION_TIMEOUT

print(f"Gradio Version: {gr.__version__}")

# === 1. JS 注入代码 ===
INJECT_JS = """
() => {
    let id_counter = 0;
    document.querySelectorAll('a[target="_blank"]').forEach(el => el.removeAttribute('target'));
    const elements = document.querySelectorAll('a, button, input, textarea, select, [role="button"], [role="link"], h3, span, div[role="textbox"], .rating_num');
    elements.forEach(el => {
        const rect = el.getBoundingClientRect();
        const style = window.getComputedStyle(el);
        if (rect.width > 0 && rect.height > 0 && style.visibility !== 'hidden' && style.display !== 'none') {
            el.setAttribute('data-agent-id', id_counter.toString());
            if (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA') { el.setAttribute('value', el.value); }
            el.style.border = "2px solid red";
            el.style.backgroundColor = "rgba(255, 0, 0, 0.1)";
            el.setAttribute('title', `ID: ${id_counter}`);
            id_counter++;
        }
    });
    return id_counter;
}
"""

# === 2. 线程通信队列 ===
# command_queue: Gradio -> Browser Thread (发送用户指令)
# result_queue: Browser Thread -> Gradio (返回执行日志和截图)
command_queue = queue.Queue()
result_queue = queue.Queue()

# === 3. 浏览器工作线程 (后台独立运行) ===
def browser_worker():
    """这是唯一一个允许接触 Playwright 对象的线程"""
    print("🚀 浏览器后台线程已启动...")
    
    playwright = sync_playwright().start()
    browser = playwright.chromium.launch(headless=False)
    context = browser.new_context()
    page = context.new_page()
    page.set_viewport_size({"width": 1280, "height": 800})
    
    # 初始化页面
    try:
        page.goto("https://www.baidu.com")
    except:
        pass

    last_action = "None (Start)"

    while True:
        # 1. 等待指令
        try:
            user_message = command_queue.get() 
        except:
            continue
            
        logs = ""
        
        # 定义截图辅助函数 (只在当前线程运行)
        def capture_screen():
            path = os.path.abspath("current_view.png")
            try:
                page.bring_to_front()
                page.screenshot(path=path)
                return path
            except:
                return None

        # 2. 开始执行步骤
        for step in range(20):
            step_info = f"\n🔵 **Step {step+1}**"
            logs += step_info + "\n"
            
            # 发送当前状态给 UI
            result_queue.put(("running", logs, capture_screen()))
            
            try:
                page.evaluate(INJECT_JS)
                time.sleep(1.0)
            except:
                pass
            
            # 二次刷新状态
            result_queue.put(("running", logs, capture_screen()))

            html = page.content()
            
            # --- AI 决策核心 ---
            try:
                decision, tokens, latency, _ = get_ai_decision(user_message, page, html, last_action)
            except Exception as e:
                logs += f"❌ 决策错误: {str(e)}\n"
                result_queue.put(("running", logs, capture_screen()))
                break

            action = decision.get('action')
            target_id = decision.get('id')
            val = decision.get('value')
            reason = decision.get('reasoning')

            logs += f"🧠 **思维**: {reason}\n🤖 **动作**: `{action}` | ID: `{target_id}` | Val: `{val}`\n"
            result_queue.put(("running", logs, capture_screen()))

            if action == "finish":
                logs += "\n✅ **任务完成！**"
                result_queue.put(("running", logs, capture_screen()))
                break

            # --- 执行动作 ---
            try:
                if action == "goto":
                    url = val if val.startswith("http") else "https://" + val
                    logs += f"🌍 跳转: {url}\n"
                    page.goto(url)
                    last_action = f"Navigated to {url}"
                elif action == "scroll":
                    direction = -500 if val == "up" else 500
                    page.evaluate(f"window.scrollBy(0, {direction})")
                    last_action = "Scrolled"
                    time.sleep(1)
                elif action == "key":
                    if target_id:
                        selector = f'[data-agent-id="{target_id}"]'
                        if page.locator(selector).count() > 0:
                            page.locator(selector).first.press(val)
                    else:
                        page.keyboard.press(val)
                    last_action = f"Pressed key {val}"
                    time.sleep(3)
                elif target_id:
                    selector = f'[data-agent-id="{target_id}"]'
                    if page.locator(selector).count() == 0:
                        logs += "⚠️ 元素找不到，跳过...\n"
                        continue
                    loc = page.locator(selector).first
                    if action == "click":
                        loc.click(timeout=5000)
                        last_action = f"Clicked {target_id}"
                    elif action == "type":
                        tag_name = loc.evaluate("el => el.tagName.toLowerCase()")
                        if tag_name not in ['input', 'textarea']:
                            loc.click()
                        else:
                            loc.fill(val)
                        last_action = f"Typed {val}"
                    time.sleep(2)
                
                result_queue.put(("running", logs, capture_screen()))
                
            except Exception as e:
                logs += f"⚠️ 执行警告: {str(e)[:100]}\n"
                last_action = "Failed"
                result_queue.put(("running", logs, capture_screen()))

        # 3. 任务结束信号
        result_queue.put(("done", logs, capture_screen()))

# === 4. 启动后台线程 ===
# daemon=True 意味着主程序关闭时，这个线程也会自动关闭
t = threading.Thread(target=browser_worker, daemon=True)
t.start()

# === 5. UI 构建 ===
with gr.Blocks(title="LightWeb Agent") as demo: 
    gr.Markdown("# 🤖 LightWeb Agent 可视化控制台 (Thread-Safe版)")
    
    with gr.Row():
        with gr.Column(scale=1):
            # Gradio 6.x 默认 messages 格式，无需 type 参数
            chatbot = gr.Chatbot(
                label="执行日志", 
                height=500,
                avatar_images=(None, "https://cdn-icons-png.flaticon.com/512/4712/4712035.png") 
            )
            msg = gr.Textbox(label="输入指令", placeholder="例如：去豆瓣搜奥本海默...")
            clear = gr.ClearButton([msg, chatbot])
        
        with gr.Column(scale=1):
            browser_view = gr.Image(label="浏览器视角", interactive=False)

    def user(user_message, history):
        if history is None:
            history = []
        return "", history + [{"role": "user", "content": user_message}]

    def bot(history):
        if not history:
            yield history, None
            return

        user_message = history[-1]["content"]
        
        # 添加助手回复占位符
        history.append({"role": "assistant", "content": "⏳ Agent 正在启动..."})
        yield history, None

        # 1. 将指令放入队列，发送给后台线程
        command_queue.put(user_message)
        
        # 2. 循环读取后台线程的返回结果
        while True:
            try:
                # 阻塞读取，直到有新消息
                status, logs, screenshot = result_queue.get()
                
                # 更新 UI
                history[-1]["content"] = logs
                yield history, screenshot
                
                # 如果任务完成，退出循环
                if status == "done":
                    break
            except Exception as e:
                print(f"UI Error: {e}")
                break

    msg.submit(user, [msg, chatbot], [msg, chatbot]).then(
        bot, [chatbot], [chatbot, browser_view]
    )

if __name__ == "__main__":
    demo.queue() # 必须开启队列
    print("启动中... 请访问 http://127.0.0.1:7860")
    demo.launch(server_name="127.0.0.1")