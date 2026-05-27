"""
💰 定价专家 Agent — 自动化版
=============================
功能：从产品款式总表读取成本 → 结合竞品比价 → 输出三级定价方案

用法：
  python scripts/pricing_advisor.py                         # 分析所有产品
  python scripts/pricing_advisor.py SL07                     # 分析指定产品
  python scripts/pricing_advisor.py SL07 ST01                # 分析多个产品
  python scripts/pricing_advisor.py --report                 # 查看上次报告
"""

import os
import re
import sys
import json
import sqlite3
from datetime import datetime
from pathlib import Path

# 确保 Windows 终端能正确显示 UTF-8 字符
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except AttributeError:
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, 'Layer1_Permanent', '01_My_Shop', 'shop_data.db')
PRODUCT_TABLE = os.path.join(BASE_DIR, 'Layer1_Permanent', '02_Products', '产品款式总表.md')
INDUSTRY_DIR = os.path.join(BASE_DIR, 'Layer1_Permanent', '04_Industry')
OUTPUT_DIR = os.path.join(BASE_DIR, 'Layer2_Working')

# ====================== 定价参数 ======================
PLATFORM_COMMISSION = 0.05      # 平台佣金 5%
SHIPPING_COST = 30              # 菲律宾站运费估算 (PHP)
PACKAGING_COST = 5              # 包装费 (PHP)
EXCHANGE_RATE = 7.8             # RMB → PHP 汇率（参考）
TARGET_PROFIT_MARGIN = 0.40     # 目标利润率 40%
COMMISSION_RATES = [0.15, 0.20, 0.25]  # 达人佣金档位
PROMO_DISCOUNT = 0.15           # 活动促销折扣


def parse_product_table():
    """
    从 产品款式总表.md 解析产品数据
    返回 dict: {style_code: {name, category, cost_rmb, reference_price}}
    """
    if not os.path.exists(PRODUCT_TABLE):
        print(f"产品款式总表不存在: {PRODUCT_TABLE}")
        return {}

    products = {}
    with open(PRODUCT_TABLE, 'r', encoding='utf-8') as f:
        content = f.read()

    # 解析表格行
    table_pattern = re.findall(
        r'\|\s*([A-Z0-9]+)\s*\|\s*([^|]+)\s*\|\s*([^|]+)\s*\|\s*(\d+)\s*\|\s*([^|]+)\s*\|\s*([^|]+)\s*\|\s*([^|]+)\s*\|\s*([\d.]+)\s*\|\s*([\d.-]+)\s*\|',
        content
    )

    for match in table_pattern:
        code, category, material, sku_count, color, style, size, ref_price, cost = match
        cost_rmb = float(cost) if cost.replace('.', '', 1).lstrip('-').isdigit() else None
        ref_price_rmb = float(ref_price) if ref_price.replace('.', '', 1).lstrip('-').isdigit() else None

        products[code] = {
            'code': code,
            'category': category.strip(),
            'material': material.strip(),
            'sku_count': int(sku_count),
            'cost_rmb': cost_rmb if cost_rmb and cost_rmb > 0 else None,
            'ref_price_rmb': ref_price_rmb if ref_price_rmb and ref_price_rmb > 0 else None,
        }

    return products


def get_db_sales_data(style_code=None):
    """从数据库获取商品销售数据（近4周均价）"""
    if not os.path.exists(DB_PATH):
        return {}

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 获取款式对应的产品ID
    if style_code:
        cursor.execute('''
            SELECT sc.style_code, p.product_id, p.product_name
            FROM products p
            JOIN style_catalog sc ON p.style_id = sc.style_id
            WHERE sc.style_code = ?
        ''', (style_code,))
    else:
        cursor.execute('''
            SELECT sc.style_code, p.product_id, p.product_name
            FROM products p
            JOIN style_catalog sc ON p.style_id = sc.style_id
        ''')

    product_map = {}
    for row in cursor.fetchall():
        code, pid, name = row
        if code not in product_map:
            product_map[code] = {'product_id': pid, 'product_name': name}

    # 获取这些产品的销售数据
    if product_map:
        pids = [v['product_id'] for v in product_map.values()]
        placeholders = ','.join(['?'] * len(pids))
        cursor.execute(f'''
            SELECT product_id, AVG(shop_gmv + video_gmv + live_gmv) as avg_gmv,
                   AVG(units_sold) as avg_units
            FROM product_weekly
            WHERE product_id IN ({placeholders})
              AND week_start >= date('now', '-28 days')
            GROUP BY product_id
        ''', pids)

        for row in cursor.fetchall():
            pid, avg_gmv, avg_units = row
            for code, info in product_map.items():
                if info['product_id'] == pid:
                    info['avg_gmv'] = round(avg_gmv, 2) if avg_gmv else 0
                    info['avg_units'] = int(avg_units) if avg_units else 0

    conn.close()
    return product_map


def get_industry_price_data(category_name):
    """从 industry_saleslist 获取行业价格数据作为竞品参考"""
    if not os.path.exists(DB_PATH):
        return []

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute('''
        SELECT product_name, price_range, week_start
        FROM industry_saleslist
        WHERE category_name LIKE ?
        ORDER BY week_start DESC
        LIMIT 20
    ''', (f'%{category_name[:4]}%',))

    prices = cursor.fetchall()
    conn.close()
    return prices


def calculate_pricing(product, sales_data, industry_prices):
    """核心定价计算，返回完整的定价方案"""
    code = product['code']
    cost_rmb = product.get('cost_rmb')

    # 如果没有成本数据，尝试从信息卡读取
    info_card = os.path.join(BASE_DIR, 'Layer1_Permanent', '02_Products', '产品信息卡', f'{code}.md')
    if not cost_rmb and os.path.exists(info_card):
        with open(info_card, 'r', encoding='utf-8') as f:
            card_content = f.read()
        cost_match = re.search(r'成本\(RMB\):\s*([\d.]+)', card_content)
        if cost_match:
            cost_rmb = float(cost_match.group(1))

    # 转 PHP
    cost_php = round(cost_rmb * EXCHANGE_RATE, 2) if cost_rmb else None
    ref_price_php = round(product.get('ref_price_rmb', 0) * EXCHANGE_RATE, 2) if product.get('ref_price_rmb') else None

    # 计算保本价
    if cost_php:
        break_even = cost_php + (cost_php * PLATFORM_COMMISSION) + SHIPPING_COST + PACKAGING_COST
    else:
        break_even = None

    # 三级定价
    pricing = {
        'product_code': code,
        'product_name': f"{product['category']} ({code})",
        'category': product['category'],
        'sku_count': product['sku_count'],
        'cost_info': {
            'cost_rmb': cost_rmb,
            'cost_php': round(cost_php, 2) if cost_php else '未知',
            'exchange_rate': EXCHANGE_RATE,
            'platform_commission': f"{PLATFORM_COMMISSION*100}%",
            'shipping': SHIPPING_COST,
            'packaging': PACKAGING_COST,
        },
        'break_even': {
            'break_even_php': round(break_even, 2) if break_even else '未知',
            'formula': f"成本{round(cost_php,2) if cost_php else '?'} + 佣金{round(cost_php*PLATFORM_COMMISSION,2) if cost_php else '?'} + 运费{SHIPPING_COST} + 包装{PACKAGING_COST}"
        },
        'tiered_pricing': {},
        'profit_analysis': {},
    }

    if break_even:
        # 商城价（目标利润率 40%）
        shop_price = round(break_even * (1 + TARGET_PROFIT_MARGIN), 2)
        psychological_prices = _get_psychological_price(shop_price)
        shop_price_final = psychological_prices[0]
        actual_margin = round((shop_price_final - break_even) / shop_price_final * 100, 1)

        # 达人佣金价
        influencer_prices = {}
        for comm_rate in COMMISSION_RATES:
            comm_label = f"{int(comm_rate*100)}%佣金"
            inf_price = round(shop_price_final * (1 - comm_rate), 2)
            inf_margin = round((inf_price - break_even) / inf_price * 100, 1) if inf_price > break_even else 0
            influencer_prices[comm_label] = {
                'price': inf_price,
                'commission_amount': round(shop_price_final * comm_rate, 2),
                'influencer_margin': inf_margin,
            }

        # 活动价
        promo_price = round(break_even * 1.2, 2)

        # 竞品参考价
        competitor_ref = None
        if ref_price_php:
            competitor_ref = ref_price_php

        pricing['tiered_pricing'] = {
            'shop_price': {
                'recommended': shop_price_final,
                'psychological_options': psychological_prices,
                'actual_margin_pct': actual_margin,
                'margin_level': _get_margin_level(actual_margin),
            },
            'influencer_price': influencer_prices,
            'promo_price': {
                'price': promo_price,
                'margin_pct': round((promo_price - break_even) / promo_price * 100, 1),
            },
        }

        if competitor_ref:
            pricing['tiered_pricing']['competitor_reference'] = competitor_ref

        # 利润分析
        pricing['profit_analysis'] = {
            'break_even_php': round(break_even, 2),
            'shop_price_php': shop_price_final,
            'profit_per_unit': round(shop_price_final - break_even, 2),
            'profit_margin_pct': actual_margin,
            'roi_target': TARGET_PROFIT_MARGIN,
        }

    # 销售表现
    if sales_data:
        info = sales_data.get(code, {})
        pricing['sales_performance'] = {
            'avg_gmv': info.get('avg_gmv', 0),
            'avg_units': info.get('avg_units', 0),
        }

    # 行业参考价
    if industry_prices:
        pricing['industry_reference'] = [
            {'product': p[0][:20], 'price': p[1], 'week': p[2]}
            for p in industry_prices[:5]
        ]

    return pricing


def _get_psychological_price(price, min_price=None):
    """生成心理定价选项"""
    options = []
    base = int(price)
    options.append(round(base * 1.0 + 0.99, 2))
    options.append(round(base * 1.1 + 0.99, 2))
    low_price = round(base * 0.9 + 0.99, 2)
    if min_price:
        low_price = max(low_price, round(min_price * 0.99, 2))
    options.append(low_price)
    return sorted(set(options))


def _get_margin_level(margin_pct):
    if margin_pct >= 40:
        return '[优秀]'
    elif margin_pct >= 30:
        return '[可接受]'
    elif margin_pct >= 20:
        return '[需优化]'
    else:
        return '[不建议]'


def generate_report(all_pricing, target_codes=None):
    """生成定价方案 Markdown 报告"""
    date_str = datetime.now().strftime('%Y-%m-%d %H:%M')

    report_lines = [
        f"# 定价方案报告 - {date_str}",
        f"",
        f"**定价依据**: 产品款式总表成本 + TikTok Shop 费率 + 竞品参考价",
        f"**核心公式**: 保本价 = 成本 + 平台佣金(5%) + 运费(30) + 包装(5)",
        f"**目标利润率**: >= {TARGET_PROFIT_MARGIN*100}%",
        f"**汇率**: 1 RMB = {EXCHANGE_RATE} PHP",
        f"",
        f"---",
        f"",
    ]

    for product in all_pricing:
        code = product['product_code']
        if target_codes and code not in target_codes:
            continue

        report_lines.extend([
            f"## {code} - {product['product_name']}",
            f"",
            f"### 成本信息",
            f"| 项目 | 金额 |",
            f"|:---|:---:|",
            f"| 商品成本 (RMB) | {product['cost_info']['cost_rmb'] or '未知'} |",
            f"| 商品成本 (PHP) | {product['cost_info']['cost_php']} |",
            f"| 平台佣金 | {product['cost_info']['platform_commission']} |",
            f"| 运费估算 | {product['cost_info']['shipping']} |",
            f"| 包装费 | {product['cost_info']['packaging']} |",
            f"",
            f"### 保本价",
            f"**保本价 = {product['break_even']['break_even_php']}**" if isinstance(product['break_even']['break_even_php'], (int, float)) else f"**保本价: {product['break_even']['break_even_php']}**",
            f"",
            f"### 三级定价方案",
            f"",
            f"| 渠道 | 建议售价 | 利润率 | 说明 |",
            f"|:---|:---:|:---:|:---|",
        ])

        tp = product.get('tiered_pricing', {})
        if tp:
            shop = tp.get('shop_price', {})
            report_lines.append(
                f"| **商城价** | **{shop.get('recommended', '?')}** | {shop.get('actual_margin_pct', '?')}% {shop.get('margin_level', '')} | 标价，给用户折扣空间 |"
            )

            for comm_label, inf_info in tp.get('influencer_price', {}).items():
                report_lines.append(
                    f"| 达人({comm_label}) | {inf_info['price']} | {inf_info['influencer_margin']}% | 达人可见价，含佣金{inf_info['commission_amount']} |"
                )

            promo = tp.get('promo_price', {})
            report_lines.append(
                f"| 活动促销价 | {promo.get('price', '?')} | {promo.get('margin_pct', '?')}% | 大促/限时折扣价 |"
            )

        report_lines.extend([
            f"",
            f"### 利润审核",
            f"| 指标 | 值 | 评级 |",
            f"|:---|:---:|:---:|",
        ])

        pa = product.get('profit_analysis', {})
        if pa:
            margin = pa.get('profit_margin_pct', 0)
            report_lines.extend([
                f"| 保本价 | {pa['break_even_php']} | - |",
                f"| 商城价 | {pa['shop_price_php']} | - |",
                f"| 单件利润 | {pa['profit_per_unit']} | - |",
                f"| 利润率 | {margin}% | {_get_margin_level(margin)} |",
            ])

        # 销售表现
        sp = product.get('sales_performance', {})
        if sp and (sp.get('avg_gmv') or sp.get('avg_units')):
            report_lines.extend([
                f"",
                f"### 近期销售表现",
                f"| 指标 | 值 |",
                f"|:---|:---:|",
                f"| 近4周平均GMV | {sp.get('avg_gmv', 0)} |",
                f"| 近4周平均销量 | {sp.get('avg_units', 0)} 件 |",
            ])

        # 行业参考价
        industry_ref = product.get('industry_reference', [])
        if industry_ref:
            report_lines.extend([
                f"",
                f"### 行业参考价 (Fastmoss)",
                f"| 商品 | 价格区间 | 周 |",
                f"|:---|:---:|:---:|",
            ])
            for ref in industry_ref[:3]:
                report_lines.append(f"| {ref['product']} | {ref['price']} | {ref['week']} |")

        report_lines.extend([f"", f"---", f"", f"**策略建议**: " + _get_strategy_recommendation(product)])

    report_lines.extend([
        f"",
        f"---",
        f"",
        f"*本报告由 定价专家 Agent 自动生成*",
        f"*数据来源: 产品款式总表 + shop_data.db + Fastmoss 行业数据*",
        f"*注意: 运费和包装费为估算值，请以实际物流成本为准*",
    ])

    return '\n'.join(report_lines)


def _get_strategy_recommendation(product):
    """根据定价结果给出策略建议"""
    pa = product.get('profit_analysis', {})
    margin = pa.get('profit_margin_pct', 0)
    sp = product.get('sales_performance', {})
    gmv = sp.get('avg_gmv', 0)

    if margin >= 40:
        if gmv >= 5000:
            return "[爆款品策略]：可在不触发竞品跟进的前提下逐步提价 5%-15%，测试转化率变化找到最优价格点。"
        elif gmv > 0:
            return "[增长品策略]：保持当前定价，加大达人合作（15-20%佣金档位），快速提升销量。"
        else:
            return "[新品策略]：首周可设置较低达人佣金价（15%）吸引达人合作，快速积累销量和评论。"
    elif margin >= 30:
        return "[优化策略]：利润率可接受，建议关注竞品价格，必要时微调。可测试提价5%观察转化率变化。"
    elif margin >= 20:
        return "[降本策略]：寻找降本空间（替代材料/优化包装/批量采购），或小幅提价5-10%测试市场接受度。"
    else:
        return "[评估策略]：利润率不足20%，建议重新评估产品可行性。如果必要品，可考虑作为引流款配合捆绑销售。"


def save_report(report, target_codes=None):
    """保存定价报告到文件"""
    today = datetime.now().strftime('%Y%m%d')
    label = '_'.join(target_codes) if target_codes else '全品类'
    filename = f'定价方案_{label}_{today}.md'
    filepath = os.path.join(OUTPUT_DIR, filename)

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(report)

    print(f"\n定价方案报告已生成: {filepath}")
    return filepath


def main():
    import argparse
    parser = argparse.ArgumentParser(description='定价专家 Agent - 自动化定价方案')
    parser.add_argument('products', nargs='*', help='产品代码 (如 SL07 ST01)，留空=全部分析')
    parser.add_argument('--report', action='store_true', help='查看上次生成的报告')
    args = parser.parse_args()

    print("""
+===========================================+
|  定价专家 Agent 已启动                       |
|                                            |
|  数据源: 产品款式总表 + shop_data.db          |
|  定价模型: 成本+ -> 保本 -> 三级定价           |
+===========================================+
""")

    if args.report:
        reports = [f for f in os.listdir(OUTPUT_DIR) if f.startswith('定价方案_') and f.endswith('.md')]
        if reports:
            latest = max(reports, key=lambda f: os.path.getmtime(os.path.join(OUTPUT_DIR, f)))
            print(f"最近的定价报告: {latest}")
            with open(os.path.join(OUTPUT_DIR, latest), 'r', encoding='utf-8') as f:
                print(f.read()[:2000])
        else:
            print("还没有定价报告，请先运行: python scripts/pricing_advisor.py")
        return

    # 1. 解析产品数据
    print("正在读取产品款式总表...")
    products = parse_product_table()
    if not products:
        print("未能读取到产品数据")
        return
    print(f"   读取到 {len(products)} 个款式")

    # 2. 获取数据库销售数据
    print("正在查询数据库销售数据...")
    sales_data = get_db_sales_data()
    print(f"   获取到 {len(sales_data)} 个产品的销售数据")

    # 3. 计算定价
    target_codes = [c.upper() for c in args.products] if args.products else None
    all_pricing = []

    if target_codes:
        codes_to_analyze = [c for c in target_codes if c in products]
        not_found = [c for c in target_codes if c not in products]
        if not_found:
            print(f"   未找到产品: {', '.join(not_found)}")
    else:
        codes_to_analyze = list(products.keys())

    for code in codes_to_analyze:
        product = products[code]
        category = product['category'][:4] if product['category'] else '首饰'
        industry_prices = get_industry_price_data(category)
        pricing = calculate_pricing(product, sales_data, industry_prices)
        all_pricing.append(pricing)

        be = pricing['break_even']['break_even_php']
        margin = pricing.get('profit_analysis', {}).get('profit_margin_pct', 0)
        print(f"\n  {code} ({product['category']})")
        print(f"    成本: {pricing['cost_info']['cost_php']} -> 保本价: {be}")
        print(f"    商城价: {pricing.get('tiered_pricing', {}).get('shop_price', {}).get('recommended', '?')} (利润率 {margin}%)")
        if industry_prices:
            print(f"    行业参考: {industry_prices[0][1] if industry_prices[0][1] else '无数据'}")

    # 4. 生成报告
    report = generate_report(all_pricing, target_codes=set(codes_to_analyze))
    filepath = save_report(report, codes_to_analyze)

    print(f"\n{'='*50}")
    print(f"  定价分析完成！共分析 {len(codes_to_analyze)} 个产品")
    print(f"  报告路径: {filepath}")
    print(f"  提示: 可通过 orchestrator 调用")
    print(f"{'='*50}")


if __name__ == '__main__':
    main()
