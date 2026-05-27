import openpyxl

def read_product_data(path):
    wb = openpyxl.load_workbook(path)
    ws = wb.active
    rows = []
    headers = [c.value for c in next(ws.iter_rows(min_row=3, max_row=3))]
    for row in ws.iter_rows(min_row=4, values_only=True):
        if row[0] is None:
            continue
        d = dict(zip(headers, row))
        # parse numeric values
        num_keys = ['GMV','成交件数','订单数','商城页 GMV','商城商品成交件数','商城页发品曝光次数',
                  '商城页面浏览次数','商城页去重页面浏览次数','商城页去重商品客户数',
                  '直播归因 GMV','直播归因成交件数','直播曝光次数','直播的页面浏览次数','直播的去重页面浏览次数','直播去重商品客户数',
                  '视频归因 GMV','视频归因成交件数','视频曝光次数','来自视频的页面浏览次数','来自视频的去重页面浏览次数','视频去重商品客户数',
                  '商品卡归因 GMV','商品卡归因成交件数','商品卡曝光次数','商品卡的页面浏览次数','商品卡的去重页面浏览次数','商品卡去重客户数']
        for k in num_keys:
            v = d.get(k, 0)
            if v is None or v == '' or v == '-':
                d[k] = 0
            else:
                try:
                    d[k] = float(str(v).replace('\u20b1','').replace(',',''))
                except:
                    d[k] = 0
        # parse percentage
        pct_keys = ['商城点击率','商城转化率','直播点击率','直播转化率','视频点击率','视频转化率','商品卡点击率','商品卡转化率']
        for k in pct_keys:
            v = d.get(k, '0%')
            if v is None or v == '' or v == '-':
                d[k] = 0.0
            else:
                try:
                    d[k] = float(str(v).replace('%','')) / 100
                except:
                    d[k] = 0.0
        rows.append(d)
    return rows

w1 = read_product_data('Layer2_Working/PNB-商品数据 20260518-20260517.xlsx')
w2 = read_product_data('Layer2_Working/PNB-商品数据 20260518-20260524.xlsx')

# Filter active products with GMV > 0
w1_active = [p for p in w1 if p['状态'] == 'Active' and p['GMV'] > 0]
w2_active = [p for p in w2 if p['状态'] == 'Active' and p['GMV'] > 0]
w1_zero = [p for p in w1 if p['状态'] == 'Active' and p['GMV'] == 0]
w2_zero = [p for p in w2 if p['状态'] == 'Active' and p['GMV'] == 0]

print('=== W1 (05/11-05/17) ===')
print('Active products:', len([p for p in w1 if p['状态']=='Active']))
print('With sales:', len(w1_active))
print('Zero sales:', len(w1_zero))
total_gmv_w1 = sum(p['GMV'] for p in w1_active)
total_units_w1 = sum(p['成交件数'] for p in w1_active)
print('Total GMV: PHP {:.2f}'.format(total_gmv_w1))
print('Total units:', total_units_w1)
print()

print('=== W2 (05/18-05/24) ===')
print('Active products:', len([p for p in w2 if p['状态']=='Active']))
print('With sales:', len(w2_active))
print('Zero sales:', len(w2_zero))
total_gmv_w2 = sum(p['GMV'] for p in w2_active)
total_units_w2 = sum(p['成交件数'] for p in w2_active)
print('Total GMV: PHP {:.2f}'.format(total_gmv_w2))
print('Total units:', total_units_w2)
print()

# Top products W2
print('=== W2 Top Products ===')
w2_sorted = sorted(w2_active, key=lambda x: x['GMV'], reverse=True)
for i, p in enumerate(w2_sorted[:10]):
    name = str(p['商品'])[:50]
    gmv = p['GMV']
    pct = gmv / total_gmv_w2 * 100
    units = int(p['成交件数'])
    video_gmv = p['视频归因 GMV']
    shop_gmv = p['商城页 GMV']
    card_gmv = p['商品卡归因 GMV']
    live_gmv = p['直播归因 GMV']
    channels = {'视频': video_gmv, '商城': shop_gmv, '商品卡': card_gmv, '直播': live_gmv}
    main_ch = max(channels, key=channels.get)
    main_pct = max(channels.values()) / gmv * 100 if gmv > 0 else 0
    print('{}. {}'.format(i+1, name))
    print('   GMV: PHP {:.2f} ({:.1f}%) | 件数: {} | 核心渠道: {}({:.0f}%)'.format(gmv, pct, units, main_ch, main_pct))
    print('   视频曝光: {:.0f} | 视频点击率: {:.2f}% | 视频转化率: {:.2f}%'.format(
        p['视频曝光次数'], p['视频点击率']*100, p['视频转化率']*100))
    print()

# Channel breakdown W2
print('=== W2 Channel Breakdown ===')
video_total = sum(p['视频归因 GMV'] for p in w2_active)
shop_total = sum(p['商城页 GMV'] for p in w2_active)
card_total = sum(p['商品卡归因 GMV'] for p in w2_active)
live_total = sum(p['直播归因 GMV'] for p in w2_active)
print('视频: PHP {:.2f} ({:.1f}%)'.format(video_total, video_total/total_gmv_w2*100))
print('商城: PHP {:.2f} ({:.1f}%)'.format(shop_total, shop_total/total_gmv_w2*100))
print('商品卡: PHP {:.2f} ({:.1f}%)'.format(card_total, card_total/total_gmv_w2*100))
print('直播: PHP {:.2f} ({:.1f}%)'.format(live_total, live_total/total_gmv_w2*100))
print()

# WoW Comparison
print('=== WoW Comparison ===')
w1_by_id = {p['ID']: p for p in w1_active}
w2_by_id = {p['ID']: p for p in w2_active}

common_ids = set(w1_by_id.keys()) & set(w2_by_id.keys())
for pid in common_ids:
    p1 = w1_by_id[pid]
    p2 = w2_by_id[pid]
    gmv_change = (p2['GMV'] - p1['GMV']) / p1['GMV'] * 100
    name = str(p1['商品'])[:40]
    print(name)
    print('  W1: PHP {:.2f} -> W2: PHP {:.2f} ({:+.1f}%)'.format(p1['GMV'], p2['GMV'], gmv_change))
    print('  视频曝光: {:.0f} -> {:.0f}'.format(p1['视频曝光次数'], p2['视频曝光次数']))
    print()

# New products in W2
new_ids = set(w2_by_id.keys()) - set(w1_by_id.keys())
if new_ids:
    print('=== New Products in W2 ===')
    for pid in new_ids:
        p = w2_by_id[pid]
        name = str(p['商品'])[:50]
        print('{} | GMV: PHP {:.2f} | 件数: {:.0f}'.format(name, p['GMV'], p['成交件数']))
    print()

# Zero data products
print('=== Zero Data Products (both weeks) ===')
w1_zero_ids = {p['ID'] for p in w1_zero}
w2_zero_ids = {p['ID'] for p in w2_zero}
both_zero = w1_zero_ids & w2_zero_ids
for pid in both_zero:
    p = next((p for p in w1_zero if p['ID'] == pid), None)
    if p:
        name = str(p['商品'])[:50]
        print(name)
print('Total: {} products with zero sales for 2 consecutive weeks'.format(len(both_zero)))
