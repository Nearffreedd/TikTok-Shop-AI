import sys, re
sys.stdout.reconfigure(encoding='utf-8')

with open('scripts/fastmoss_debug_page.html', 'r', encoding='utf-8') as f:
    html = f.read()

print(f'HTML size: {len(html)} bytes')

# 查找 cnonce 相关
matches = re.findall(r'cnonce[^;]{0,200}', html)
print(f'\ncnonce matches: {len(matches)}')
for m in matches[:5]:
    print(f'  {m[:150]}')

# 查找 _time 相关
matches2 = re.findall(r'_time[^;]{0,200}', html)
print(f'\n_time matches: {len(matches2)}')
for m in matches2[:5]:
    print(f'  {m[:150]}')

# 查找签名/加密相关
matches3 = re.findall(r'(sign|encrypt|nonce|token|secret)[^;]{0,200}', html, re.I)
print(f'\nsign/encrypt matches: {len(matches3)}')
for m in matches3[:10]:
    print(f'  {m[:150]}')

# 查找 Next.js 数据
matches4 = re.findall(r'__NEXT_DATA__[^<]{0,500}', html)
print(f'\n__NEXT_DATA__: {len(matches4)}')
for m in matches4[:2]:
    print(f'  {m[:300]}')

# 查找 _N_E 相关
matches5 = re.findall(r'_N_E[^;]{0,200}', html)
print(f'\n_N_E matches: {len(matches5)}')
for m in matches5[:5]:
    print(f'  {m[:150]}')
