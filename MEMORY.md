# My TikTok Shop AI Operations System

## 1. 身份与角色
- 我是一名专注于 **[菲律宾]** 市场的TikTok Shop卖家。
- 我的核心类目是 **[时尚配件]**。
- 我的品牌定位是 **[为菲律宾人带去优质低价的产品]**。

## 2. 知识库地图
- **长期知识库(Layer 1)**：位于 `/Layer1_Permanent/`
  - 选品知识、竞品分析、产品信息、运营SOP都在这里。
- **工作区(Layer 2)**：位于 `/Layer2_Working/`
  - 当前正在处理的任务草稿、临时数据、决策中间件。
- **主控文件**：此文件 (`MEMORY.md`)

## 3. 总调度中枢 (Orchestrator)

### 🎯 运营总调度助理
- **脚本**: `orchestrator.py`
- **功能**: 作为统一对话入口，接收任务后自动调度对应的专家/工作流，支持多专家联动
- **用法**: 
  - `python orchestrator.py` — 启动交互式对话
  - `python orchestrator.py "你的任务"` — 单次任务模式
- **支持的工作流**:
  - **周度运营复盘**: 导入数据 → 商品分析 → 视频分析 → 竞品检查
  - **爆款视频复刻**: 视频分析 → 生成复刻脚本
  - **选品调研**: 竞品追踪 → 选品分析

### 📚 知识沉淀同步器
- **脚本**: `auto_knowledge_sync.py`
- **功能**: 解析复盘报告的"知识沉淀清单"，自动将未完成项追加到对应的SOP/知识库文件
- **用法**: 
  - `python auto_knowledge_sync.py "Layer2_Working/复盘报告_周度_20260526.md"` — 指定报告
  - `python auto_knowledge_sync.py --all` — 扫描所有复盘报告
  - `python auto_knowledge_sync.py --check "报告路径"` — 仅检查不写入
- **自动触发**: 复盘专家执行完毕后，orchestrator 自动调用此脚本同步知识

### 🧠 LangGraph 监督者模式 (已就绪)
- **脚本**: `orchestrator_langgraph.py`
- **功能**: 基于 LangGraph 构建有向图工作流，实现"总控Agent → 子专家 → 综合输出"的编排
- **核心特性**:
  - **StateGraph** 定义节点流转（用户输入 → 意图识别 → 专家调度 → 结果汇总）
  - **共享记忆**: 所有 Agent 通过 `obsidian_mcp` 读写 Obsidian 知识库
  - **后置动作钩子**: 复盘后自动触发知识沉淀同步
- **用法**:
  - `python orchestrator_langgraph.py` — 交互模式
  - `python orchestrator_langgraph.py "做个周度运营复盘"` — 单次任务
  - `python orchestrator_langgraph.py --visualize` — 导出工作流图

## 4. 专家 Agent 列表

### 🎬 爆款视频分析专家 Agent
- **脚本**: `scripts/viral_video_analyzer.py`
- **SOP**: `Layer1_Permanent/06_Operations/爆款视频分析SOP.md`
- **功能**: 上传爆款视频 → 自动转录文案 → 分析脚本结构（钩子/痛点/卖点/CTA）→ 存入爆款脚本库 → **沉淀爆款脚本知识库** → 生成1:1复刻 & 裂变脚本
- **脚本库**: `Layer1_Permanent/05_Campaigns/Viral_Scripts/`
- **爆款脚本知识库**: `Layer1_Permanent/06_Operations/爆款脚本知识库_<产品名>.md`（可复用的共性规律沉淀）
- **用法**: `python scripts/viral_video_analyzer.py --upload <视频> --product <产品名> --category <类目>`
- **知识沉淀流程**: 分析脚本 → 提取共性规律 → 更新知识库 → 基于知识库生成脚本
- **快速生成脚本**: 直接说"生成3个SL07的爆款脚本" → 自动读取知识库 → 选择模板 → 输出脚本

### 📊 商品数据分析系统
- **脚本**: `scripts/generate_product_report.py` / `scripts/auto_import.py`
- **SOP**: `Layer1_Permanent/06_Operations/商品数据分析SOP.md`
- **功能**: 导入周数据 → SQLite数据库 → ABC分类分析（渠道归因/流量效率/周环比/异常检测）
- **用法**: `python scripts/generate_product_report.py PNB 2`

### 📹 创意视频数据运营系统
- **脚本**: `scripts/analyze_creatives.py` / `scripts/import_creative_videos.py`
- **SOP**: `Layer1_Permanent/06_Operations/video_operations_sop.md`
- **功能**: 导入创意视频数据 → 分析达人表现/视频质量/ROI/授权类型分布
- **用法**: `python scripts/analyze_creatives.py 2`

### 🎯 选品分析
- **SOP**: `Layer1_Permanent/06_Operations/选品SOP.md`
- **功能**: 数据驱动选品决策，5维度评分（市场需求/利润/展示力/竞争/供应链）
- **状态**: 基于SOP的手动模式

### 🔍 竞品追踪
- **SOP**: `.clinerules/competitor-track.md`
- **功能**: 监控竞品动态（新品/价格/销量/视频/直播）
- **状态**: 基于SOP的手动模式

### ✍️ 内容脚本生成
- **SOP**: `.clinerules/content-script.md`
- **功能**: 生成TikTok带货短视频脚本（30-45秒），支持菲律宾语
- **状态**: 基于SOP的手动模式（可通过爆款视频分析脚本生成复刻/裂变）

### 📋 运营日志助理
- **脚本**: `ops_logger.py`
- **功能**: 记录日常运营操作（视频更新/折扣/活动/广告等），自我学习运营习惯，主动提醒
- **用法**: 
  - `python ops_logger.py` — 交互式对话模式
  - `python ops_logger.py "今天更新了SL07的视频"` — 单次记录模式
  - `python ops_logger.py --summary` — 查看今日摘要
  - `python ops_logger.py --weekly` — 生成周度汇总
  - `python ops_logger.py --analyze` — 分析运营习惯
  - `python ops_logger.py --ask "SL07最近更新了吗"` — 查询历史
- **数据存储**:
  - `Layer2_Working/运营日志/` — 每日日志文件
  - `Layer1_Permanent/01_My_Shop/ops_journal.json` — 结构化数据库
  - `Layer1_Permanent/06_Operations/运营周志/` — 周度归档
- **自我学习**: 记录操作频率/账号偏好/折扣习惯 → 异常检测 → 主动提醒

## 5. 全局规则 (.clinerules/)
| 规则文件 | 角色 | 核心职责 |
| :--- | :--- | :--- |
| `tiktok-operations.md` | 🧠 核心运营系统 | 三层记忆结构、工作流程、输出格式、自我进化 |
| `competitor-track.md` | 🔍 竞品追踪专家 | 监控竞品动态，每周一生成竞品周报 |
| `content-script.md` | ✍️ 内容脚本专家 | 生成带货短视频脚本，支持多语言 |
| `data-analysis.md` | 📊 数据分析专家 | 分析销售/广告/商品数据，输出优化建议 |
| `product-selection.md` | 🎯 选品专家 | 数据驱动选品决策，5维度评分 |
| `review-expert.md` | 🔄 复盘专家 | 系统性复盘运营数据，总结成功经验与失败教训，输出改进方案 |

## 6. 协作规则
- **新任务启动时**：请先读取此文件，理解我的背景和知识库结构。
- **调用知识时**：始终优先从 `/Layer1_Permanent/` 中查找相关信息。
- **生成内容时**：草稿请存入 `/Layer2_Working/`，确认后我会引导你将其归档到Layer 1。
- **提交任务时**：可以直接在对话中描述任务，我会自动调度对应的专家或工作流。
- **自我进化**：每次完成一个重要任务后，请总结关键步骤和经验，提交给我审阅后更新到Layer 1的运营SOP中。
