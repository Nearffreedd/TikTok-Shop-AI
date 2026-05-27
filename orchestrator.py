"""
🎯 TikTok Shop AI 运营总调度助理 (Orchestrator)
================================================
功能：作为你的统一对话入口，接收任务后自动调度对应的专家/工作流，
      支持多专家联动完成复杂任务。

用法：
  python orchestrator.py                    # 启动交互式对话
  python orchestrator.py "你的任务描述"      # 单次任务模式

示例：
  "帮我分析上周的店铺数据" → 调度 数据分析专家
  "看看竞品有什么新品" → 调度 竞品追踪专家
  "这个视频帮我分析一下，再生成一个复刻脚本" → 联动 爆款视频分析 + 内容脚本
  "帮我看看上周数据，再分析一下有什么选品机会" → 联动 数据分析 + 选品
"""

import os
import sys
import re
import json
import subprocess
import shutil
from datetime import datetime
from pathlib import Path

# ====================== 路径配置 ======================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SCRIPTS_DIR = os.path.join(BASE_DIR, 'scripts')
LAYER1_DIR = os.path.join(BASE_DIR, 'Layer1_Permanent')
LAYER2_DIR = os.path.join(BASE_DIR, 'Layer2_Working')
INBOX_DIR = os.path.join(BASE_DIR, '0_Inbox')
MEMORY_FILE = os.path.join(BASE_DIR, 'MEMORY.md')
KNOWLEDGE_SYNC_SCRIPT = os.path.join(BASE_DIR, 'auto_knowledge_sync.py')

# ====================== 专家注册表 ======================
EXPERT_REGISTRY = {
    "爆款视频分析": {
        "aliases": ["视频分析", "分析视频", "爆款分析", "脚本分析", "viral"],
        "script": os.path.join(SCRIPTS_DIR, 'viral_video_analyzer.py'),
        "sop": "Layer1_Permanent/06_Operations/爆款视频分析SOP.md",
        "description": "上传爆款视频 → 转录文案 → 分析脚本结构 → 存入脚本库",
        "capabilities": ["视频转录", "脚本结构分析", "钩子识别", "卖点提取"],
        "output_type": "脚本分析报告",
        "output_dir": "Layer1_Permanent/05_Campaigns/Viral_Scripts/",
    },
    "内容脚本生成": {
        "aliases": ["生成脚本", "写脚本", "复刻脚本", "裂变脚本", "脚本创作", "content"],
        "script": os.path.join(SCRIPTS_DIR, 'viral_video_analyzer.py'),
        "sop": ".clinerules/content-script.md",
        "description": "基于爆款脚本生成1:1复刻或裂变版本",
        "capabilities": ["复刻脚本", "裂变脚本", "多语言脚本"],
        "output_type": "视频脚本",
        "output_dir": "Layer2_Working/",
    },
    "数据分析": {
        "aliases": ["数据", "销量", "GMV", "店铺数据", "商品数据", "周报", "分析数据", "data"],
        "scripts": {
            "商品分析": os.path.join(SCRIPTS_DIR, 'generate_product_report.py'),
            "创意视频分析": os.path.join(SCRIPTS_DIR, 'analyze_creatives.py'),
            "数据导入": os.path.join(SCRIPTS_DIR, 'auto_import.py'),
        },
        "sop": "Layer1_Permanent/06_Operations/商品数据分析SOP.md",
        "description": "分析店铺销售/商品/视频数据，输出可执行优化建议",
        "capabilities": ["商品ABC分析", "渠道归因", "流量效率", "周环比", "异常检测", "视频质量分析"],
        "output_type": "数据分析报告",
        "output_dir": "Layer2_Working/",
    },
    "创意视频运营": {
        "aliases": ["视频数据", "创意视频", "达人分析", "视频运营", "creative"],
        "script": os.path.join(SCRIPTS_DIR, 'analyze_creatives.py'),
        "sop": "Layer1_Permanent/06_Operations/video_operations_sop.md",
        "description": "分析创意视频数据、达人表现、视频质量",
        "capabilities": ["达人ROI分析", "视频播放率分析", "授权类型分布"],
        "output_type": "创意视频分析报告",
        "output_dir": "Layer2_Working/",
    },
    "选品分析": {
        "aliases": ["选品", "选什么品", "新品推荐", "产品选择", "product selection"],
        "script": None,
        "sop": "Layer1_Permanent/06_Operations/选品SOP.md",
        "description": "数据驱动的选品决策，从市场热度/利润/展示力/竞争/供应链评估",
        "capabilities": ["市场热度分析", "利润测算", "竞争评估"],
        "output_type": "选品分析报告",
        "output_dir": "Layer2_Working/",
    },
    "竞品追踪": {
        "aliases": ["竞品", "竞争对手", "competitor", "竞品分析"],
        "script": None,
        "sop": ".clinerules/competitor-track.md",
        "description": "监控竞品动态（新品/价格/销量/视频/直播）",
        "capabilities": ["新品监控", "价格变动", "销量估算", "视频互动分析"],
        "output_type": "竞品周报",
        "output_dir": "Layer2_Working/",
    },
    "数据导入": {
        "aliases": ["导入", "导入数据", "上传数据", "import"],
        "script": os.path.join(SCRIPTS_DIR, 'auto_import.py'),
        "sop": "Layer1_Permanent/06_Operations/商品数据分析SOP.md",
        "description": "自动识别并导入 Layer2_Working 中的 Excel 数据文件",
        "capabilities": ["商品数据导入", "店铺数据导入", "自动备份"],
        "output_type": "数据导入确认",
        "output_dir": "Layer1_Permanent/01_My_Shop/",
    },
    "运营日志助理": {
        "aliases": ["日志", "记录", "今天", "操作", "笔记", "回忆", "log", "运营日志", "记一下"],
        "script": os.path.join(BASE_DIR, 'ops_logger.py'),
        "sop": None,
        "description": "记录日常运营操作（视频更新/折扣/活动/广告等），自我学习运营习惯，主动提醒",
        "capabilities": ["操作记录", "历史查询", "习惯分析", "异常检测", "周度汇总"],
        "output_type": "运营日志",
        "output_dir": "Layer2_Working/运营日志/",
    },
    "复盘专家": {
        "aliases": ["复盘", "回顾", "总结", "反思", "review", "retrospect", "复盘分析", "周度复盘", "月度复盘"],
        "script": None,
        "sop": ".clinerules/review-expert.md",
        "description": "系统性复盘运营数据，总结成功经验（沉淀为SOP）和失败教训（避免踩坑），输出改进方案",
        "capabilities": ["数据收集与整理", "关键指标对比", "成功经验提炼", "失败教训总结", "行动建议输出", "知识沉淀"],
        "output_type": "复盘报告",
        "output_dir": "Layer2_Working/",
        "post_action": "knowledge_sync",
    },
    "定价专家": {
        "aliases": ["定价", "价格", "定价策略", "价格分析", "利润测算", "pricing"],
        "script": os.path.join(SCRIPTS_DIR, 'pricing_advisor.py'),
        "sop": ".clinerules/pricing-expert.md",
        "description": "基于成本和竞品价格，自动计算最优定价策略（商城/达人/活动三级定价）",
        "capabilities": ["成本利润测算", "竞品比价", "分层定价", "动态调价提醒"],
        "output_type": "定价方案报告",
        "output_dir": "Layer2_Working/",
    },
    "运营策略师": {
        "aliases": ["策略", "运营策略", "下周计划", "制定策略", "行动方案", "strategy"],
        "script": os.path.join(SCRIPTS_DIR, 'strategy_generator.py'),
        "sop": ".clinerules/strategy-planner.md",
        "description": "自动整合复盘/数据分析/竞品动态，输出下周具体运营策略和行动方案",
        "capabilities": ["现状诊断", "目标设定", "策略制定", "资源分配", "风险预警"],
        "output_type": "运营策略报告",
        "output_dir": "Layer2_Working/",
    },
}

# ====================== 任务模板 ======================
WORKFLOW_TEMPLATES = {
    "周度运营复盘": {
        "description": "每周一完整复盘：导入数据 → 分析商品 → 分析视频 → 竞品检查 → 运营策略",
        "steps": [
            {"expert": "数据导入", "params": {"mode": "--all"}, "description": "导入上周所有新数据"},
            {"expert": "数据分析", "params": {"type": "商品分析", "args": ["PNB", "2"]}, "description": "商品数据分析"},
            {"expert": "创意视频运营", "params": {"args": ["2"]}, "description": "创意视频数据分析"},
            {"expert": "竞品追踪", "params": {}, "description": "竞品动态检查"},
            {"expert": "运营策略师", "params": {}, "description": "基于复盘结果制定下周运营策略"},
        ],
        "output": "Layer2_Working/周度运营复盘_{日期}.md",
    },

    "爆款视频复刻": {
        "description": "分析一个爆款视频 → 生成复刻脚本 → 存入脚本库",
        "steps": [
            {"expert": "爆款视频分析", "params": {}, "description": "上传并分析爆款视频"},
            {"expert": "内容脚本生成", "params": {"type": "clone"}, "description": "生成1:1复刻脚本"},
        ],
        "output": "Layer2_Working/复刻脚本_{产品}_{日期}.md",
    },
    "选品调研": {
        "description": "结合竞品动态和行业趋势进行选品分析",
        "steps": [
            {"expert": "竞品追踪", "params": {}, "description": "查看竞品新品动态"},
            {"expert": "选品分析", "params": {}, "description": "综合评估选品机会"},
        ],
        "output": "Layer2_Working/选品报告_{日期}.md",
    },
}


# ====================== 总调度助理 ======================
class Orchestrator:
    def __init__(self):
        self.context = {
            "workflow_id": None,
            "user_input": "",
            "steps": [],
            "summaries": {},
            "artifacts": {},
        }
        self.task_history = []
        print("""
╔══════════════════════════════════════════════════╗
║     🎯 TikTok Shop AI 运营总调度助理 已就位       ║
║                                                  ║
║  你可以这样找我：                                  ║
║  • "帮我分析上周的店铺数据"                        ║
║  • "看看竞品有什么新动作"                          ║
║  • "这个视频帮我分析一下，再生成复刻脚本"           ║
║  • "帮我做一次周度运营复盘"                        ║
║  • "我想选品，有什么推荐"                          ║
║  • "导入新数据"                                   ║
║  • "帮助" — 查看完整指令清单                      ║
╚══════════════════════════════════════════════════╝
""")

    def run(self, task=None):
        """主入口：支持交互式对话和单次任务模式"""
        if task:
            self._process_task(task)
        else:
            while True:
                try:
                    user_input = input("\n💬 你: ").strip()
                    if user_input.lower() in ["退出", "exit", "quit"]:
                        print("👋 再见！")
                        break
                    elif user_input.lower() in ["帮助", "help", "?"]:
                        self._show_help()
                    else:
                        self._process_task(user_input)
                except KeyboardInterrupt:
                    print("\n👋 再见！")
                    break
                except EOFError:
                    break

    def _show_help(self):
        """显示帮助信息"""
        print("""
📋 指令清单
═══════════════════════════════════════

🔍 数据分析类
  "分析上周数据" / "看下PNB店铺数据" → 商品数据分析
  "分析创意视频" / "看看达人表现" → 创意视频运营分析
  "导入新数据" / "导入Excel" → 数据导入

🎬 视频脚本类
  "分析这个视频" → 爆款视频分析（需先放视频到 0_Inbox/Video_Raw/）
  "生成复刻脚本" / "生成裂变脚本" → 内容脚本生成
  "分析视频并生成复刻" → 联动：分析+生成

🎯 选品竞品类
  "有什么选品推荐" → 选品分析
  "看看竞品动态" → 竞品追踪
  "竞品有什么新品" → 竞品新品监控

🔄 复盘类
  "帮我复盘上周运营" → 复盘专家（周度复盘）
  "总结一下这个月的经验教训" → 复盘专家（月度复盘）
  "这个活动做得怎么样" → 复盘专家（活动复盘）

� 定价与策略类
  "帮我给SL07定个价" → 定价专家（成本+竞品+分层定价）
  "制定下周运营策略" → 运营策略师（整合复盘/数据，制定计划）

�🔄 复杂工作流（多专家联动）
  "做一次周度运营复盘" → 导入数据+商品分析+视频分析+竞品检查
  "帮我选品调研" → 竞品追踪+选品分析
  "分析这个爆款并复刻" → 视频分析+脚本生成

📖 其他
  "帮助" / "?" → 显示此清单
  "退出" / "exit" → 退出
═══════════════════════════════════════
""")

    def _process_task(self, user_input):
        """处理用户任务：识别意图 → 调度专家 → 返回结果"""
        print(f"\n🤔 正在理解你的任务...")
        intent = self._detect_intent(user_input)
        if not intent:
            print("""
❌ 抱歉，我没能理解你的任务意图。
请尝试更明确的表述，例如：
  • "分析上周的店铺数据"
  • "分析这个视频并生成复刻脚本"
  • "看看竞品有什么新动作"
  • 输入 "帮助" 查看完整指令清单
""")
            return
        if isinstance(intent, list) and len(intent) > 1:
            self._execute_workflow(intent, user_input)
        else:
            expert_name = intent[0] if isinstance(intent, list) else intent
            self._execute_single(expert_name, user_input)

    def _detect_intent(self, text):
        """智能识别用户意图"""
        text_lower = text.lower()
        matched_experts = []
        for wf_name, wf_config in WORKFLOW_TEMPLATES.items():
            keywords = wf_name.lower().split()
            if all(kw in text_lower for kw in keywords):
                return [wf_name]
        for expert_name, expert_info in EXPERT_REGISTRY.items():
            for alias in expert_info["aliases"]:
                if alias.lower() in text_lower:
                    matched_experts.append(expert_name)
                    break
        matched_experts = list(dict.fromkeys(matched_experts))
        if "爆款视频分析" in matched_experts and "内容脚本生成" in matched_experts:
            if "复刻" in text_lower or "裂变" in text_lower or "生成" in text_lower:
                return ["爆款视频分析", "内容脚本生成"]
        if "数据分析" in matched_experts and "创意视频运营" in matched_experts:
            return ["数据分析", "创意视频运营"]
        return matched_experts[:1] if matched_experts else None

    def _execute_single(self, expert_name, user_input, prev_context=None):
        """执行单个专家任务，返回结构化结果"""
        expert = EXPERT_REGISTRY.get(expert_name)
        if not expert:
            print(f"❌ 未知专家: {expert_name}")
            return {"expert": expert_name, "status": "error", "summary": "未知专家", "artifacts": {}}
        if prev_context:
            print(f"\n  📎 前序步骤摘要:")
            for prev_name, prev_summary in prev_context.items():
                if prev_summary:
                    print(f"     ↳ {prev_name}: {prev_summary[:80]}...")
        print(f"\n{'='*50}")
        print(f"  🎯 正在调度: {expert_name}")
        print(f"  📋 功能: {expert['description']}")
        print(f"{'='*50}\n")
        if expert_name == "爆款视频分析":
            result = self._run_viral_analysis(user_input)
        elif expert_name == "内容脚本生成":
            result = self._run_script_generation(user_input)
        elif expert_name == "数据分析":
            result = self._run_data_analysis(user_input)
        elif expert_name == "创意视频运营":
            result = self._run_creative_analysis(user_input)
        elif expert_name == "选品分析":
            result = self._run_product_selection(user_input)
        elif expert_name == "竞品追踪":
            result = self._run_competitor_tracking(user_input)
        elif expert_name == "数据导入":
            result = self._run_data_import(user_input)
        elif expert_name == "复盘专家":
            result = self._run_review(user_input)
        elif expert_name == "定价专家":
            result = self._run_pricing(user_input)
        elif expert_name == "运营策略师":
            result = self._run_strategy(user_input)
        else:
            print(f"⚠️  {expert_name} 专家尚未实现自动化脚本，请参考 SOP 手动操作。")
            print(f"   SOP 路径: {expert['sop']}")
            result = {"expert": expert_name, "status": "skip", "summary": f"手动模式，参考SOP: {expert['sop']}", "artifacts": {}}
        self.context["summaries"][expert_name] = result.get("summary", "")
        self.context["artifacts"][expert_name] = result.get("artifacts", {})
        self.context["steps"].append(result)
        # 如果专家配置了后置动作，自动执行
        if expert.get("post_action") == "knowledge_sync":
            self._auto_sync_knowledge(expert_name)
        return result

    def _execute_workflow(self, experts, user_input):
        """执行多专家联动工作流"""
        self.context["workflow_id"] = f"wf_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        self.context["user_input"] = user_input
        self.context["steps"] = []
        self.context["summaries"] = {}
        self.context["artifacts"] = {}
        print(f"\n{'='*50}")
        print(f"  🔗 检测到多专家联动任务")
        print(f"  涉及专家: {' → '.join(experts)}")
        print(f"{'='*50}\n")
        wf_name = experts[0] if experts[0] in WORKFLOW_TEMPLATES else None
        if wf_name:
            wf = WORKFLOW_TEMPLATES[wf_name]
            print(f"  📋 工作流: {wf_name}")
            print(f"  📝 {wf['description']}")
            print(f"\n  执行步骤:")
            for i, step in enumerate(wf['steps'], 1):
                print(f"    {i}. {step['description']}")
            confirm = input(f"\n  是否执行此工作流? (y/n): ").strip().lower()
            if confirm == 'y':
                accumulated_context = {}
                for i, step in enumerate(wf['steps'], 1):
                    print(f"\n  {'='*45}")
                    print(f"  📌 步骤 {i}/{len(wf['steps'])}: {step['description']}")
                    print(f"  {'='*45}")
                    step_result = self._execute_single(step['expert'], user_input, prev_context=accumulated_context)
                    accumulated_context[step['expert']] = step_result.get("summary", "")
                self._generate_workflow_report(wf_name, wf)
                print(f"\n  ✅ 工作流「{wf_name}」执行完成！")
            else:
                print("  ⏭️  已取消")
        else:
            print(f"  将依次执行: {' → '.join(experts)}")
            confirm = input(f"  是否继续? (y/n): ").strip().lower()
            if confirm == 'y':
                accumulated_context = {}
                for expert_name in experts:
                    step_result = self._execute_single(expert_name, user_input, prev_context=accumulated_context)
                    accumulated_context[expert_name] = step_result.get("summary", "")

    def _auto_sync_knowledge(self, expert_name):
        """自动执行知识沉淀同步"""
        print(f"\n  📚 检测到复盘完成，自动同步知识沉淀...")
        if os.path.exists(KNOWLEDGE_SYNC_SCRIPT):
            # 扫描 Layer2_Working 中最新复盘报告
            report_files = []
            if os.path.exists(LAYER2_DIR):
                report_files = [os.path.join(LAYER2_DIR, f) for f in os.listdir(LAYER2_DIR)
                               if f.startswith("复盘报告_") and f.endswith(".md")]
            if report_files:
                latest = max(report_files, key=os.path.getmtime)
                print(f"  📄 扫描最新复盘报告: {os.path.basename(latest)}")
                cmd = f'python "{KNOWLEDGE_SYNC_SCRIPT}" "{latest}"'
                exit_code = os.system(cmd)
                if exit_code == 0:
                    print(f"  ✅ 知识沉淀同步完成！")
                else:
                    print(f"  ⚠️ 知识沉淀同步出错，请手动运行: python auto_knowledge_sync.py \"{latest}\"")
            else:
                print(f"  ⚠️ 未找到复盘报告文件，跳过知识同步")
        else:
            print(f"  ⚠️ 知识同步脚本不存在: {KNOWLEDGE_SYNC_SCRIPT}")

    def _run_review(self, user_input):
        """复盘专家（输出SOP指导 + 自动知识同步）"""
        print("""
🔄 复盘专家
═══════════════════════════════════════
参考 SOP: .clinerules/review-expert.md

复盘分析框架（5步法）:
  1. 📊 数据收集与整理 — 收集周期内所有相关数据
  2. 📈 关键指标对比 — GMV/转化率/客单价/退款率/广告ROI
  3. ✅ 成功经验提炼 — 做对了什么？可复用条件？
  4. ❌ 失败教训总结 — 踩了什么坑？预警信号？
  5. 🎯 行动建议输出 — P0/P1/P2 可执行行动项

推荐数据源:
  • Layer1_Permanent/01_My_Shop/Daily_Reports/ — 日报/周报
  • Layer2_Working/运营日志/ — 日常操作记录（用于理解"做了什么"）
  • Layer1_Permanent/02_Products/产品数据/ — 商品表现
  • Layer2_Working/ — 竞品周报、分析报告

自动触发: 复盘结束后将自动执行"知识沉淀同步"
═══════════════════════════════════════
""")
        return {
            "expert": "复盘专家",
            "status": "skip",
            "summary": "手动模式，参考SOP进行复盘分析，完成后自动同步知识沉淀",
            "artifacts": {},
        }

    def _run_viral_analysis(self, user_input):
        """调度爆款视频分析专家"""
        video_dir = os.path.join(INBOX_DIR, 'Video_Raw')
        if not os.path.exists(video_dir):
            print("❌ Video_Raw 目录不存在")
            return {"expert": "爆款视频分析", "status": "error", "summary": "Video_Raw 目录不存在", "artifacts": {}}
        videos = [f for f in os.listdir(video_dir) if f.lower().endswith(('.mp4', '.mov', '.avi'))]
        if not videos:
            print("""
⚠️  Video_Raw 文件夹中没有找到视频文件。
请先将视频放入: 0_Inbox/Video_Raw/
然后重新运行此命令。
""")
            return {"expert": "爆款视频分析", "status": "skip", "summary": "未找到视频文件", "artifacts": {}}
        if len(videos) == 1:
            video_file = videos[0]
        else:
            print("📁 找到以下视频文件:")
            for i, v in enumerate(videos, 1):
                print(f"  {i}. {v}")
            try:
                choice = int(input("请选择要分析的视频 (编号): ").strip())
                video_file = videos[choice - 1]
            except (ValueError, IndexError):
                print("❌ 无效选择")
                return {"expert": "爆款视频分析", "status": "error", "summary": "无效选择", "artifacts": {}}
        video_path = os.path.join(video_dir, video_file)
        product = self._extract_product_name(user_input, video_file)
        cmd = f'python "{EXPERT_REGISTRY["爆款视频分析"]["script"]}" --upload "{video_path}" --product "{product}" --category "时尚配件"'
        print(f"\n🔧 执行: {cmd}\n")
        exit_code = os.system(cmd)
        return {
            "expert": "爆款视频分析",
            "status": "done" if exit_code == 0 else "error",
            "summary": f"分析了视频 {video_file}，产品: {product}",
            "artifacts": {"files": [video_file], "key_findings": [f"视频分析完成: {video_file}"]},
        }

    def _run_script_generation(self, user_input):
        """调度内容脚本生成专家"""
        script_path = EXPERT_REGISTRY["内容脚本生成"]["script"]
        if "裂变" in user_input:
            os.system(f'python "{script_path}" --list')
            script_id = input("\n请输入要裂变的脚本ID: ").strip()
            remix_type = input("裂变类型 (short/long/hook/tone/structure, 默认short): ").strip() or "short"
            product = self._extract_product_name(user_input, "")
            cmd = f'python "{script_path}" --remix {script_id} --type {remix_type} --product "{product}"'
            exit_code = os.system(cmd)
            return {"expert": "内容脚本生成", "status": "done" if exit_code == 0 else "error", "summary": f"基于脚本{script_id}生成裂变版本，产品: {product}", "artifacts": {"key_findings": [f"裂变脚本生成完成"]}}
        elif "复刻" in user_input or "clone" in user_input:
            os.system(f'python "{script_path}" --list')
            script_id = input("\n请输入要复刻的脚本ID: ").strip()
            product = self._extract_product_name(user_input, "")
            cmd = f'python "{script_path}" --clone {script_id} --product "{product}"'
            exit_code = os.system(cmd)
            return {"expert": "内容脚本生成", "status": "done" if exit_code == 0 else "error", "summary": f"基于脚本{script_id}生成复刻版本，产品: {product}", "artifacts": {"key_findings": [f"复刻脚本生成完成"]}}
        else:
            print("""
📝 内容脚本生成（手动模式）
请提供以下信息:
  1. 产品名称
  2. 核心卖点 (2-3个)
  3. 目标人群
  4. 参考爆款视频链接 (可选)
参考 SOP: .clinerules/content-script.md
草稿将存入: Layer2_Working/
""")
            return {"expert": "内容脚本生成", "status": "skip", "summary": "手动模式，需要用户提供产品信息", "artifacts": {}}

    def _run_data_analysis(self, user_input):
        """调度数据分析专家"""
        scripts = EXPERT_REGISTRY["数据分析"]["scripts"]
        shop_code = self._extract_shop_code(user_input)
        weeks = self._extract_weeks(user_input)
        findings = []
        if "商品" in user_input or "店铺" in user_input or "GMV" in user_input.upper():
            cmd = f'python "{scripts["商品分析"]}" {shop_code} {weeks}'
            print(f"\n🔧 执行: {cmd}\n")
            exit_code = os.system(cmd)
            findings.append(f"商品分析完成（店铺:{shop_code}, 周数:{weeks}）")
        elif "创意" in user_input or "视频" in user_input:
            cmd = f'python "{scripts["创意视频分析"]}" {weeks}'
            print(f"\n🔧 执行: {cmd}\n")
            exit_code = os.system(cmd)
            findings.append(f"创意视频分析完成（周数:{weeks}）")
        else:
            print("📊 执行全面数据分析...")
            print(f"\n--- 商品数据分析 ---")
            cmd1 = f'python "{scripts["商品分析"]}" {shop_code} {weeks}'
            exit_code1 = os.system(cmd1)
            print(f"\n--- 创意视频数据分析 ---")
            cmd2 = f'python "{scripts["创意视频分析"]}" {weeks}'
            exit_code2 = os.system(cmd2)
            findings.append(f"商品分析完成（店铺:{shop_code}）")
            findings.append(f"创意视频分析完成（周数:{weeks}）")
        return {"expert": "数据分析", "status": "done", "summary": f"分析了店铺{shop_code}过去{weeks}周的数据", "artifacts": {"key_findings": findings, "metrics": {"shop_code": shop_code, "weeks": weeks}}}

    def _run_creative_analysis(self, user_input):
        """调度创意视频运营专家"""
        script = EXPERT_REGISTRY["创意视频运营"]["script"]
        weeks = self._extract_weeks(user_input)
        cmd = f'python "{script}" {weeks}'
        print(f"\n🔧 执行: {cmd}\n")
        exit_code = os.system(cmd)
        return {"expert": "创意视频运营", "status": "done" if exit_code == 0 else "error", "summary": f"创意视频分析完成（周数:{weeks}）", "artifacts": {"key_findings": [f"分析了{weeks}周的创意视频数据"]}}

    def _run_product_selection(self, user_input):
        """选品分析（基于SOP的手动模式）"""
        print("""
🎯 选品分析
═══════════════════════════════════════
参考 SOP: Layer1_Permanent/06_Operations/选品SOP.md
选品评估维度:
  1. 📈 市场需求 (30%) — TikTok话题热度、搜索量增长
  2. 💰 利润空间 (25%) — 售价-成本-平台费用 >= 30%毛利
  3. 🎬 展示潜力 (20%) — 适合短视频展示、视觉冲击力
  4. ⚔️ 竞争程度 (15%) — 头部卖家数量、价格战情况
  5. 🔗 供应链稳定性 (10%) — 1688货源、发货时效
推荐阅读:
  • Layer1_Permanent/04_Industry/ — 行业趋势、热销榜
  • Layer1_Permanent/03_Competitors/ — 竞品新品动态
  • Layer1_Permanent/02_Products/ — 现有产品库（避免重复）
输出格式: Layer2_Working/选品报告_YYYYMMDD.md
═══════════════════════════════════════
""")
        return {"expert": "选品分析", "status": "skip", "summary": "手动模式，参考SOP进行选品分析", "artifacts": {}}

    def _run_pricing(self, user_input):
        """定价专家（自动化脚本模式）"""
        script = EXPERT_REGISTRY["定价专家"]["script"]
        # 从用户输入提取产品代码
        product_codes = re.findall(r'\b([A-Z]{2}\d{2})\b', user_input.upper())
        if product_codes:
            cmd = f'python "{script}" {" ".join(product_codes)}'
        else:
            cmd = f'python "{script}"'
        print(f"\n🔧 执行: {cmd}\n")
        exit_code = os.system(cmd)
        return {
            "expert": "定价专家",
            "status": "done" if exit_code == 0 else "error",
            "summary": f"完成产品{' '.join(product_codes) if product_codes else '全品类'}定价分析",
            "artifacts": {"key_findings": [f"定价分析完成，产出报告存入 Layer2_Working/"]},
        }

    def _run_strategy(self, user_input):
        """运营策略师（自动化脚本模式）"""
        script = EXPERT_REGISTRY["运营策略师"]["script"]
        if "自定义" in user_input or "--draft" in user_input:
            # 提取用户提供的总结文本
            draft_text = user_input.replace("自定义", "").strip()[:100]
            cmd = f'python "{script}" --draft "{draft_text}"'
        else:
            cmd = f'python "{script}"'
        print(f"\n🔧 执行: {cmd}\n")
        exit_code = os.system(cmd)
        return {
            "expert": "运营策略师",
            "status": "done" if exit_code == 0 else "error",
            "summary": "基于复盘报告+数据库+竞品动态自动生成运营策略",
            "artifacts": {"key_findings": [f"运营策略报告已生成，存入 Layer2_Working/"]},
        }

    def _run_competitor_tracking(self, user_input):
        """竞品追踪（基于SOP的手动模式）"""
        print("""
🔍 竞品追踪
═══════════════════════════════════════
参考 SOP: .clinerules/competitor-track.md
监控指标:
  1. 🆕 新品上架 — 最近7天新增商品
  2. 💲 价格变动 — 主推品价格调整记录
  3. 📊 销量估算 — 联盟销量、商品卡销量
  4. 📱 视频互动率 — 近3天发布视频的点赞/评论/分享
  5. 🔴 直播频次 — 开播时间、时长、峰值人数
竞品列表: Layer1_Permanent/03_Competitors/competitor_list.md
输出格式: Layer2_Working/竞品周报_日期.md
═══════════════════════════════════════
""")
        return {"expert": "竞品追踪", "status": "skip", "summary": "手动模式，参考SOP进行竞品分析", "artifacts": {}}

    def _run_data_import(self, user_input):
        """调度数据导入"""
        script = EXPERT_REGISTRY["数据导入"]["script"]
        imported_files = []
        if os.path.exists(LAYER2_DIR):
            excel_files = [f for f in os.listdir(LAYER2_DIR) if f.endswith('.xlsx')]
            if excel_files:
                print(f"📁 发现 {len(excel_files)} 个 Excel 文件:")
                for f in excel_files:
                    print(f"  • {f}")
        if "全部" in user_input or "--all" in user_input:
            cmd = f'python "{script}" --all'
        elif "状态" in user_input or "status" in user_input:
            cmd = f'python "{script}" --status'
        else:
            keywords = re.findall(r'[\u4e00-\u9fa5A-Za-z0-9]+数据', user_input)
            if keywords:
                cmd = f'python "{script}" "{keywords[0]}"'
            else:
                cmd = f'python "{script}" --all'
        print(f"\n🔧 执行: {cmd}\n")
        exit_code = os.system(cmd)
        return {"expert": "数据导入", "status": "done" if exit_code == 0 else "error", "summary": "数据导入完成", "artifacts": {"files": imported_files, "key_findings": [f"数据导入{'成功' if exit_code == 0 else '失败'}"]}}

    def _generate_workflow_report(self, wf_name, wf):
        """生成工作流综合报告"""
        today = datetime.now().strftime("%Y%m%d")
        output_path = wf['output'].format(日期=today)
        full_path = os.path.join(BASE_DIR, output_path)
        step_summaries = ""
        for i, step in enumerate(wf['steps'], 1):
            expert = step['expert']
            summary = self.context["summaries"].get(expert, "（无摘要）")
            artifacts = self.context["artifacts"].get(expert, {})
            files = artifacts.get("files", [])
            findings = artifacts.get("key_findings", [])
            step_summaries += f"### 步骤{i}: {expert}\n"
            step_summaries += f"- **说明**: {step['description']}\n"
            step_summaries += f"- **执行结果**: {summary}\n"
            if files:
                step_summaries += f"- **产出文件**: {', '.join(files)}\n"
            if findings:
                step_summaries += f"- **关键发现**:\n"
                for f in findings:
                    step_summaries += f"  - {f}\n"
            step_summaries += "\n"
        all_findings = []
        for expert_name, artifacts in self.context["artifacts"].items():
            findings = artifacts.get("key_findings", [])
            all_findings.extend([f"【{expert_name}】{f}" for f in findings])
        findings_section = "\n".join([f"- {f}" for f in all_findings]) if all_findings else "（请查看各步骤详细报告）"
        report = f"""# {wf_name} — {datetime.now().strftime("%Y-%m-%d %H:%M")}

## 执行摘要
- **工作流**: {wf_name}
- **描述**: {wf['description']}
- **执行时间**: {datetime.now().strftime("%Y-%m-%d %H:%M")}
- **工作流ID**: {self.context.get('workflow_id', 'N/A')}

## 各步骤执行详情

{step_summaries}

## 跨步骤综合发现
{findings_section}

## 综合建议
> 此报告由 🎯 TikTok Shop AI 运营总调度助理 自动生成
> 基于各专家输出的数据整合而成。
"""
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, 'w', encoding='utf-8') as f:
            f.write(report)
        print(f"\n📄 工作流报告已生成: {output_path}")

    # ====================== 辅助方法 ======================
    def _extract_product_name(self, user_input, filename):
        product_codes = {'SL07': 'SL07 Citrine Bracelet', 'SL06': 'SL06 Bible Bracelet', 'ST01': 'ST01 Clover Set', 'MJ01': 'MJ01 Sunglasses'}
        for code, name in product_codes.items():
            if code.lower() in user_input.lower() or code.lower() in filename.lower():
                return name
        name = os.path.splitext(filename)[0]
        name = re.sub(r'_\d{8}', '', name)
        name = re.sub(r'^\d+', '', name).strip()
        return name if name else "未知产品"

    def _extract_shop_code(self, user_input):
        codes = re.findall(r'\b(PNB|SHOP[A-Z]?)\b', user_input, re.I)
        return codes[0].upper() if codes else "PNB"

    def _extract_weeks(self, user_input):
        nums = re.findall(r'(\d+)\s*周', user_input)
        return nums[0] if nums else "2"


# ====================== 主程序 ======================
if __name__ == "__main__":
    orchestrator = Orchestrator()
    if len(sys.argv) > 1:
        task = " ".join(sys.argv[1:])
        orchestrator.run(task)
    else:
        orchestrator.run()
