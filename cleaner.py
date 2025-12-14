# cleaner.py
from bs4 import BeautifulSoup

def get_simplified_html(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    
    lines = []
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
            
        # === 核心修改：获取输入框当前的 value ===
        # 这让 AI 知道它是否已经输入过内容了
        current_value = tag.get('value', '')
        
        text = tag.get_text(strip=True)[:30]
        placeholder = tag.get('placeholder', '')
        aria = tag.get('aria-label', '') or tag.get('title', '')
        
        desc = f"ID: {tag_id} | 类型: {element_type} | <{tag_name}"
        
        info = ""
        if text: info += f" Text='{text}'"
        # 如果输入框里有字，重点标出来
        if current_value: info += f" CURRENT_VALUE='{current_value}'"
        if placeholder: info += f" Placeholder='{placeholder}'"
        if aria: info += f" Label='{aria}'"
        
        desc += info + ">"
        
        if not info and element_type != "[输入框]":
            continue
            
        lines.append(desc)
        
    return "\n".join(lines), len(html_content), len(lines)