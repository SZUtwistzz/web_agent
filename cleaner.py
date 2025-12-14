# cleaner.py
from bs4 import BeautifulSoup

def get_simplified_html(page, html_content):
    """
    接收 page 对象以获取 URL 和 Title，
    接收 html_content 以解析 DOM
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # 1. 获取全局状态 (解决死循环的关键)
    try:
        current_url = page.url
        page_title = page.title()
    except:
        current_url = "Unknown"
        page_title = "Unknown"
    
    lines = []
    lines.append(f"PAGE_INFO: URL='{current_url}' | TITLE='{page_title}'")
    lines.append("-" * 30)

    # 2. 提取带有 ID 的元素
    elements = soup.find_all(attrs={"data-agent-id": True})
    
    for tag in elements:
        tag_id = tag['data-agent-id']
        tag_name = tag.name
        
        # 判断类型
        element_type = "[未知]"
        if tag_name in ['input', 'textarea']:
            element_type = "[输入框]"
        elif tag_name in ['a', 'button', 'select'] or tag.get('role') in ['button', 'link']:
            element_type = "[按钮]"
            
        # 读取值
        current_value = tag.get('value', '')
        text = tag.get_text(strip=True)[:50]
        placeholder = tag.get('placeholder', '')
        aria = tag.get('aria-label', '') or tag.get('title', '')
        
        desc = f"ID: {tag_id} | 类型: {element_type} | <{tag_name}"
        
        info = ""
        if text: info += f" Text='{text}'"
        if current_value: info += f" CURRENT_VALUE='{current_value}'"
        if placeholder: info += f" Placeholder='{placeholder}'"
        
        desc += info + ">"
        
        if not info and element_type != "[输入框]":
            continue
            
        lines.append(desc)
        
    return "\n".join(lines), len(html_content), len(lines)