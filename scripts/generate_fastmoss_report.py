import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import fix_encoding
import json
from collections import Counter

# 读取数据
f = open('scripts/fastmoss_ph_fashion_daily.json', 'r', encoding='utf-8')
data = json.load(f)
f.close()
p = data['products']

# 排序
by_sales = sorted(p, key=lambda x: x['sale_amount'], reverse=True)
by_vol = sorted(p, key=lambda x: x['sold_count'], reverse=True)
by_growth = sorted(p, key=lambda x: float(x['sold_count_inc_rate'].rstrip('%')), reverse=True)

lines = []
lines.append('# Fastmoss 行业数据报告 — 菲律宾 Fashion Accessories 日榜')
lines.append('')
lines.append('> 数据日期：2026-05-26 | 数据来源：Fastmoss API | 品类：Fashion Accessories (l1_cid=8)')
lines.append('')
lines.append('---')
lines.append('')
lines.append('## 一、数据概览')
lines.append('')
lines.append(f'- 抓取商品数：{len(p)} 个')
lines.append(f'- 总销量（TOP50合计）：{sum(x["sold_count"] for x in p):,}')
lines.append(f'- 总销售额（TOP50合计）：PHP {sum(x["sale_amount"] for x in p):,.0f}')
lines.append(f'- 平均日销：{sum(x["sold_count"] for x in p)//len(p):,}')
lines.append(f'- 平均客单价：PHP {sum(x["sale_amount"] for x in p)//sum(x["sold_count"] for x in p):,.0f}')
lines.append('')
lines.append('---')
lines.append('')
lines.append('## 二、销售额 TOP 10')
lines.append('')
lines.append('| # | 商品名 | 日销量 | 日销售额(PHP) | 累计销售额 | 佣金率 | 店铺 | 达人数量 |')
lines.append('|---|------|:-----:|:-----------:|:---------:|:-----:|:----:|:-------:|')
for i, x in enumerate(by_sales[:10]):
    title = x['title'][:40].replace('|', '/')
    lines.append(f'| {i+1} | {title} | {x["sold_count"]} | {x["sale_amount"]:,.0f} | {x["total_sale_amount"]:,.0f} | {x["commission_rate"]} | {x["shop_info"]["name"]} | {x["total_author_count"]} |')

lines.append('')
lines.append('---')
lines.append('')
lines.append('## 三、销量 TOP 10')
lines.append('')
lines.append('| # | 商品名 | 日销量 | 日销售额(PHP) | 增长率 | 佣金率 | 店铺 |')
lines.append('|---|------|:-----:|:-----------:|:-----:|:-----:|:----:|')
for i, x in enumerate(by_vol[:10]):
    title = x['title'][:40].replace('|', '/')
    lines.append(f'| {i+1} | {title} | {x["sold_count"]} | {x["sale_amount"]:,.0f} | {x["sold_count_inc_rate"]} | {x["commission_rate"]} | {x["shop_info"]["name"]} |')

lines.append('')
lines.append('---')
lines.append('')
lines.append('## 四、增长最快 TOP 10')
lines.append('')
lines.append('| # | 商品名 | 日销量 | 增长率 | 日销售额(PHP) | 佣金率 | 店铺 |')
lines.append('|---|------|:-----:|:-----:|:-----------:|:-----:|:----:|')
for i, x in enumerate(by_growth[:10]):
    title = x['title'][:40].replace('|', '/')
    lines.append(f'| {i+1} | {title} | {x["sold_count"]} | {x["sold_count_inc_rate"]} | {x["sale_amount"]:,.0f} | {x["commission_rate"]} | {x["shop_info"]["name"]} |')

lines.append('')
lines.append('---')
lines.append('')
lines.append('## 五、品类分布')
lines.append('')
cats = Counter()
for x in p:
    for c in x.get('category_name', []):
        cats[c.strip()] += 1
lines.append('| 子品类 | 商品数 |')
lines.append('|------|:-----:|')
for cat, cnt in cats.most_common():
    lines.append(f'| {cat} | {cnt} |')

lines.append('')
lines.append('---')
lines.append('')
lines.append('## 六、关键洞察')
lines.append('')
lines.append('### 高佣金机会品')
# 安全获取佣金率
def get_comm_rate(x):
    try:
        return int(x['commission_rate'].rstrip('%'))
    except:
        return 0

lines.append(f'- 最高佣金率：{max(get_comm_rate(x) for x in p)}%')
high_comm = [x for x in p if get_comm_rate(x) >= 15]
for x in high_comm[:5]:
    lines.append(f'  - {x["title"][:40]} | 佣金 {x["commission_rate"]} | 日销 {x["sold_count"]} | PHP {x["sale_amount"]:,.0f}')
lines.append('')
lines.append('### 爆款店铺')
shop_sales = {}
for x in p:
    n = x['shop_info']['name']
    shop_sales[n] = shop_sales.get(n, 0) + x['sale_amount']
lines.append('| 店铺 | 上榜商品数 | 总日销售额(PHP) |')
lines.append('|-----|:--------:|:-------------:|')
for name, total in sorted(shop_sales.items(), key=lambda kv: -kv[1])[:10]:
    cnt = sum(1 for x in p if x['shop_info']['name'] == name)
    lines.append(f'| {name} | {cnt} | {total:,.0f} |')

lines.append('')
lines.append('---')
lines.append('')
lines.append('## 七、原始数据')
lines.append('')
lines.append('```json')
lines.append(json.dumps(data, ensure_ascii=False, indent=2)[:5000])
lines.append('```')

# 保存到 Layer2_Working
output_path = 'e:/BaiduSyncdisk/Obsidian/Tiktok/Layer2_Working/Fastmoss行业数据报告_20260526.md'
f = open(output_path, 'w', encoding='utf-8')
f.write('\n'.join(lines))
f.close()
print(f'Report saved to: {output_path}')
print(f'Total products: {len(p)}')
print(f'Total sales: PHP {sum(x["sale_amount"] for x in p):,.0f}')
print(f'Total sold: {sum(x["sold_count"] for x in p):,}')
