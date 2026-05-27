import sys, re
sys.stdout.reconfigure(encoding='utf-8')

with open('scripts/fastmoss_debug_page.html', 'r', encoding='utf-8') as f:
    html = f.read()

# 查找所有 script 标签
scripts = re.findall(r'<script[^>]*src="([^"]+)"[^>]*>', html)
print(f'External scripts: {len(scripts)}')
for s in scripts[:20]:
    print(f'  {s}')

# 查找内联 script
inline = re.findall(r'<script[^>]*>(.*?)</script>', html, re.DOTALL)
print(f'\nInline scripts: {len(inline)}')
for i, s in enumerate(inline):
    if len(s) > 50:
        print(f'  [{i}] {len(s)} bytes: {s[:100]}...')
