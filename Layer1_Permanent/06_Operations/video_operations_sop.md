---
tags:
  - SOP
  - 视频
  - 运营
  - 已完成
---
# 创意视频数据运营 SOP

> 版本：v1.0
> 创建日期：2026-05-26
> 适用范围：TikTok Shop 东南亚市场

---

## 一、数据导入流程

### 1.1 获取数据源
- 从 TikTok Shop 后台 → 数据 → 创意视频数据 → 导出 Excel
- 导出范围：按周导出（建议每周一导出上周数据）
- 文件命名规范：`Creatives video data YYYYMMDD - YYYYMMDD.xlsx`

### 1.2 导入数据库
```bash
# 导入单周数据
python scripts/import_creative_videos.py "Layer2_Working/Creatives video data 20260518 - 20260524.xlsx"

# 导入后验证
python -c "
import sqlite3
conn = sqlite3.connect('Layer1_Permanent/01_My_Shop/shop_data.db')
c = conn.cursor()
for t in ['video_creatives','video_product_link','video_weekly_perf']:
    cnt = c.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0]
    print(f'{t}: {cnt} rows')
conn.close()
"
```

### 1.3 增量导入规则
- 同周数据重复导入会自动覆盖（按 `video_id + week_start + week_end + platform_product_id` 唯一键）
- 跨周数据会自动追加
- 商品 ID = "0" 的分桶行会保留但不关联到 products 表

---

## 二、分析报告生成

### 2.1 创意视频分析报告
```bash
# 分析最近 2 周
python scripts/analyze_creatives.py 2

# 分析最近 4 周
python scripts/analyze_creatives.py 4
```

**报告内容：**
| 章节 | 内容 | 用途 |
|:---|:---|:---|
| 整体概览 | 视频总数、有产出数、总收入、ROI | 快速了解视频渠道健康度 |
| 商品视频表现 | 各商品关联的视频数、达人、收入 | 发现视频覆盖不足的商品 |
| 达人表现 | Top 达人、ROI 排名、授权类型 | 识别高价值达人 |
| 视频质量分析 | 2秒/6秒播放率分布、高转化特征 | 优化视频内容质量 |
| 授权类型分布 | 联盟/商业/官方表现对比 | 调整达人招募策略 |
| 行动建议 | 基于数据的可执行建议 | 直接指导运营动作 |

### 2.2 商品分析报告（含视频联动）
```bash
python scripts/generate_product_report.py PNB 2
```

**新增视频联动内容：**
- 各商品视频渠道表现（视频数、达人、收入、ROI）
- Top 5 视频创意（达人、标题、收入、播放率）
- Top 5 达人（视频数、收入、ROI）

---

## 三、关键指标解读

### 3.1 视频健康度评估

| 指标 | 优秀 | 良好 | 待优化 | 差 |
|:---|:---|:---|:---|:---|
| 有产出视频占比 | >50% | 30-50% | 15-30% | <15% |
| 平均 ROI | >3x | 2-3x | 1-2x | <1x |
| 2 秒播放率 | >40% | 25-40% | 15-25% | <15% |
| 6 秒播放率 | >25% | 15-25% | 5-15% | <5% |

### 3.2 达人质量评估

| 类型 | ROI 基准 | 建议策略 |
|:---|:---|:---|
| 联盟达人 | ROI > 2 | 追加合作，提供更多商品 |
| 商业中心 | ROI > 1.5 | 评估投放效率，优化素材 |
| 官方账号 | ROI > 3 | 持续产出，作为标杆内容 |

---

## 四、运营行动指南

### 4.1 每周例行操作

**周一：**
1. 导出上周创意视频数据
2. 运行 `import_creative_videos.py` 导入
3. 运行 `analyze_creatives.py` 生成分析报告
4. 运行 `generate_product_report.py` 生成商品周报
5. 阅读报告，标记行动项

**周二-周五：**
- 根据行动建议执行达人招募、视频优化
- 记录执行情况到 Layer2_Working

### 4.2 异常处理

| 场景 | 处理方式 |
|:---|:---|
| 视频收入突降 | 检查广告投放是否中断、达人是否删除视频 |
| 某商品视频数骤减 | 检查联盟佣金是否调整、商品是否下架 |
| ROI 持续低于 1 | 暂停该视频广告投放，分析素材问题 |
| 2 秒播放率 < 10% | 视频开头需要重新剪辑，前 3 秒必须强钩子 |

### 4.3 达人管理

**高 ROI 达人（ROI > 3）：**
- 追加合作：提供更多商品链接
- 专属优惠码：提升转化率
- 长期合作：签订月度框架协议

**中等 ROI 达人（ROI 1-3）：**
- 优化素材：提供更好的视频模板
- 调整佣金：适当提高联盟佣金
- 增加频次：鼓励每周多发视频

**低 ROI 达人（ROI < 1）：**
- 评估是否继续合作
- 检查商品匹配度
- 考虑更换合作方式

---

## 五、数据库表结构参考

### video_creatives（视频主表）
```sql
video_id TEXT PRIMARY KEY,          -- TikTok 视频 ID
video_title TEXT,                    -- 视频标题/文案
username TEXT,                       -- 达人用户名
publish_date TEXT,                   -- 发布时间
video_source TEXT,                   -- 来源
first_seen_week TEXT,                -- 首次出现周
last_seen_week TEXT,                 -- 最后出现周
```

### video_product_link（视频↔商品关联）
```sql
video_id TEXT NOT NULL,              -- FK → video_creatives
platform_product_id TEXT NOT NULL,   -- FK → products
authorization_type TEXT,             -- 授权类型
authorization_status TEXT,           -- 授权状态
UNIQUE(video_id, platform_product_id)
```

### video_weekly_perf（视频周表现）
```sql
video_id TEXT NOT NULL,              -- FK → video_creatives
week_start TEXT,                     -- 周开始
week_end TEXT,                       -- 周结束
platform_product_id TEXT,            -- 关联商品 ID
revenue REAL,                        -- 总收入
sku_orders INTEGER,                  -- SKU 订单数
cost REAL,                           -- 成本/花费
roi REAL,                            -- ROI
ad_impressions INTEGER,              -- 广告曝光
ad_clicks INTEGER,                   -- 广告点击
play_2s_rate REAL,                   -- 2秒播放率
play_6s_rate REAL,                   -- 6秒播放率
tag_label TEXT,                      -- 标签
UNIQUE(video_id, week_start, week_end, platform_product_id)
```

---

## 六、常见问题

### Q: 导入时报错 "no such table"
A: 需要先运行 `python scripts/init_database.py` 初始化数据库

### Q: 数据重复导入会怎样？
A: 按唯一键覆盖，不会产生重复记录

### Q: 如何查看历史数据？
A: 运行 `analyze_creatives.py 4` 查看最近 4 周，或 `analyze_creatives.py 8` 查看最近 8 周

### Q: 商品 ID = "0" 是什么意思？
A: 表示该视频数据是"分桶"行，无法关联到具体商品，但仍保留用于统计

---

## 七、版本历史

| 版本 | 日期 | 变更内容 |
|:---|:---|:---|
| v1.0 | 2026-05-26 | 初始版本，包含数据导入、分析、运营指南 |
