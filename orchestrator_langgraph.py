"""
🧠 TikTok Shop AI LangGraph 监督者模式中枢
============================================
构建有向图（StateGraph）工作流编排，实现"总控Agent → 子专家 → 
自动知识同步"的完整闭环。

架构:
  用户输入 → 监督者(Supervisor) → [专家节点1, 专家节点2, ...] 
                                  → 汇总节点 → 输出报告
                                  → 知识同步节点(复盘时触发)

用法:
  python orchestrator_langgraph.py                         # 交互模式
  python orchestrator_langgraph.py "做个周度运营复盘"       # 单次任务
  python orchestrator_langgraph.py --visualize              # 导出工作流图

依赖:
  pip install langgraph langchain-core
"""

import os
import sys
import re
import json
import subprocess
from datetime import datetime
from typing import TypedDict, Annotated, List, Dict, Any, Optional, Literal
from pathlib import Path

# ====================== 条件导入 LangGraph ======================
try:
    from langgraph.graph import StateGraph, START, END, add_messages
    from langgraph.checkpoint.memory import MemorySaver
    LANGGRAPH_AVAILABLE = True
except ImportError:
    LANGGRAPH_AVAILABLE = False
    print("⚠️  LangGraph 未安装，请执行: pip install langgraph langchain-core")
    print("   回退到传统模式运行...")


# ====================== 路径配置 ======================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SCRIPTS_DIR = os.path.join(BASE_DIR, 'scripts')
LAYER1_DIR = os.path.join(BASE_DIR, 'Layer1_Permanent')
LAYER2_DIR = os.path.join(BASE_DIR, 'Layer2_Working')
INBOX_DIR = os.path.join(BASE_DIR, '0_Inbox')
MEMORY_FILE = os.path.join(BASE_DIR, 'MEMORY.md')
KNOWLEDGE_SYNC_SCRIPT = os.path.join(BASE_DIR, 'auto_knowledge_sync.py')


# ====================== 状态类型定义 ======================
class ExpertResult(TypedDict):
    """单个专家执行结果"""
    expert_name: str
    status: Literal["pending", "running", "done", "skip", "error"]
    summary: str
    artifacts: Dict[str, Any]
    output_file: Optional[str]


class OrchestratorState(TypedDict):
    """全局共享状态"""
    user_input: str                              # 用户原始输入
    intent: Optional[str]                        # 识别的意图
    workflow_name: Optional[str]                 # 当前工作流名称
    workflow_id: str                             # 工作流ID
    current_step: int                            # 当前步骤索引
    total_steps: int                             # 总步骤数
    experts: List[str]                           # 需要调度的专家列表
    results: Dict[str, ExpertResult]             # {expert_name: result}
    accumulated_context: Dict[str, str]          # 步骤间传递的上下文摘要
    report_path: Optional[str]                   # 生成的报告路径
    trigger_knowledge_sync: bool                 # 是否触发知识同步
    started_at: str                              # 开始时间
    completed_at: Optional[str]                  # 完成时间
    errors: List[str]                            # 错误列表


# ====================== LangGraph 节点函数 ======================
def detect_intent_node(state: OrchestratorState) -> dict:
    """节点1: 意图识别 — 分析用户输入，决定调度哪些专家"""
    user_input = state["user_input"]
    text_lower = user_input.lower()
    matched = []

    # 优先匹配预定义工作流
    if all(kw in text_lower for kw in ["周度", "运营", "复盘"]):
        matched = ["数据导入", "数据分析", "创意视频运营", "竞品追踪"]
        workflow_name = "周度运营复盘"
    elif all(kw in text_lower for kw in ["选品", "调研"]):
        matched = ["竞品追踪", "选品分析"]
        workflow_name = "选品调研"
    elif "复刻" in text_lower and ("视频" in text_lower or "爆款" in text_lower):
        matched = ["爆款视频分析", "内容脚本生成"]
        workflow_name = "爆款视频复刻"
    elif any(kw in text_lower for kw in ["复盘", "回顾", "总结"]):
        matched = ["复盘专家"]
        workflow_name = "手动复盘"
    elif any(kw in text_lower for kw in ["分析数据", "店铺数据", "商品数据"]):
        matched = ["数据分析"]
        workflow_name = "数据分析"
    elif any(kw in text_lower for kw in ["创意视频", "达人"]):
        matched = ["创意视频运营"]
        workflow_name = "创意视频分析"
    elif any(kw in text_lower for kw in ["导入", "import"]):
        matched = ["数据导入"]
        workflow_name = "数据导入"
    else:
        # 逐个匹配专家别名
        from orchestrator import EXPERT_REGISTRY
        for expert_name, info in EXPERT_REGISTRY.items():
            for alias in info["aliases"]:
                if alias.lower() in text_lower:
                    matched.append(expert_name)
                    break
        matched = list(dict.fromkeys(matched))[:1]  # 只取第一个
        workflow_name = matched[0] if matched else "未知"

    return {
        "intent": workflow_name,
        "workflow_name": workflow_name,
        "experts": matched,
        "total_steps": len(matched),
        "current_step": 0,
    }


def route_after_intent(state: OrchestratorState) -> str:
    """路由: 根据意图识别结果决定下一个专家节点"""
    if not state["experts"]:
        return "output_node"
    return f"expert_{state['experts'][0]}"


def make_expert_node(expert_name: str):
    """工厂函数: 生成专家执行节点"""
    def expert_node(state: OrchestratorState) -> dict:
        # 标记当前专家为运行中
        step_idx = state["current_step"]
        state["results"][expert_name] = {
            "expert_name": expert_name,
            "status": "running",
            "summary": "",
            "artifacts": {},
            "output_file": None,
        }

        print(f"\n{'='*50}")
        print(f"  📌 步骤 {step_idx+1}/{state['total_steps']}: {expert_name}")
        print(f"{'='*50}")

        # 从 orchestrator 导入执行逻辑
        from orchestrator import Orchestrator
        orch = Orchestrator()

        # 映射方法
        method_map = {
            "爆款视频分析": orch._run_viral_analysis,
            "内容脚本生成": orch._run_script_generation,
            "数据分析": orch._run_data_analysis,
            "创意视频运营": orch._run_creative_analysis,
            "选品分析": orch._run_product_selection,
            "竞品追踪": orch._run_competitor_tracking,
            "数据导入": orch._run_data_import,
            "复盘专家": orch._run_review,
            "定价专家": orch._run_pricing,
            "运营策略师": orch._run_strategy,
        }

        executor = method_map.get(expert_name)
        if executor:
            result = executor(state["user_input"])
        else:
            result = {"expert": expert_name, "status": "error", "summary": f"未知专家: {expert_name}", "artifacts": {}}

        # 更新累积上下文
        new_context = state["accumulated_context"].copy()
        new_context[expert_name] = result.get("summary", "")

        new_state = {
            "current_step": step_idx + 1,
            "results": {**state["results"], expert_name: {
                "expert_name": expert_name,
                "status": result.get("status", "done"),
                "summary": result.get("summary", ""),
                "artifacts": result.get("artifacts", {}),
                "output_file": result.get("output_file"),
            }},
            "accumulated_context": new_context,
        }

        # 如果执行中有错误
        if result.get("status") == "error":
            new_state["errors"] = state["errors"] + [f"{expert_name}: {result.get('summary', '')}"]

        return new_state

    return expert_node


def route_after_expert(state: OrchestratorState) -> str:
    """路由: 当前专家执行完后，决定下一个节点"""
    next_idx = state["current_step"]
    if next_idx < state["total_steps"]:
        return f"expert_{state['experts'][next_idx]}"

    # 所有专家执行完毕
    if "复盘专家" in state["experts"]:
        return "knowledge_sync_node"  # 复盘后做知识同步
    return "output_node"


def knowledge_sync_node(state: OrchestratorState) -> dict:
    """节点: 知识沉淀同步 — 自动将复盘结论同步到SOP"""
    print(f"\n{'='*50}")
    print(f"  📚 自动知识沉淀同步")
    print(f"{'='*50}")

    if not os.path.exists(KNOWLEDGE_SYNC_SCRIPT):
        print(f"  ⚠️ 知识同步脚本不存在: {KNOWLEDGE_SYNC_SCRIPT}")
        return {"trigger_knowledge_sync": False, "errors": state["errors"] + ["知识同步脚本不存在"]}

    report_files = []
    if os.path.exists(LAYER2_DIR):
        report_files = [os.path.join(LAYER2_DIR, f) for f in os.listdir(LAYER2_DIR)
                       if f.startswith("复盘报告_") and f.endswith(".md")]

    if not report_files:
        print(f"  ⚠️ 未找到复盘报告，跳过知识同步")
        return {"trigger_knowledge_sync": False}

    latest = max(report_files, key=os.path.getmtime)
    print(f"  📄 扫描最新复盘报告: {os.path.basename(latest)}")

    cmd = f'python "{KNOWLEDGE_SYNC_SCRIPT}" "{latest}"'
    exit_code = os.system(cmd)

    if exit_code == 0:
        print(f"  ✅ 知识沉淀同步完成！")
        return {"trigger_knowledge_sync": True}
    else:
        print(f"  ⚠️ 知识沉淀同步出错")
        return {"trigger_knowledge_sync": False, "errors": state["errors"] + ["知识同步执行出错"]}


def output_node(state: OrchestratorState) -> dict:
    """节点: 输出汇总 — 生成最终报告"""
    print(f"\n{'='*50}")
    print(f"  📋 生成最终输出报告")
    print(f"{'='*50}")

    now = datetime.now()
    wf_id = state["workflow_id"]
    report_path = os.path.join(
        LAYER2_DIR,
        f"工作流报告_{state['workflow_name']}_{now.strftime('%Y%m%d_%H%M%S')}.md"
    )

    # 构建报告内容
    lines = [
        f"# 🧠 LangGraph 工作流报告",
        f"",
        f"- **工作流**: {state['workflow_name']}",
        f"- **工作流ID**: {wf_id}",
        f"- **开始时间**: {state['started_at']}",
        f"- **完成时间**: {now.strftime('%Y-%m-%d %H:%M:%S')}",
        f"- **用户输入**: {state['user_input']}",
        f"",
        f"## 执行步骤摘要",
        f"",
    ]

    for i, expert_name in enumerate(state["experts"], 1):
        result = state["results"].get(expert_name, {})
        status_icon = {"done": "✅", "skip": "⏭️", "error": "❌", "running": "🔄", "pending": "⏳"}
        icon = status_icon.get(result.get("status", "pending"), "❓")
        lines.append(f"### {icon} 步骤{i}: {expert_name}")
        lines.append(f"- **状态**: {result.get('status', 'unknown')}")
        lines.append(f"- **摘要**: {result.get('summary', '（无摘要）')}")
        artifacts = result.get("artifacts", {})
        findings = artifacts.get("key_findings", [])
        if findings:
            lines.append(f"- **关键发现**:")
            for f in findings:
                lines.append(f"  - {f}")
        lines.append("")

    if state["errors"]:
        lines.append(f"## ⚠️ 错误列表")
        for err in state["errors"]:
            lines.append(f"- ❌ {err}")
        lines.append("")

    lines.append(f"## 综合建议")
    lines.append(f"> 此报告由 LangGraph 监督者模式中枢自动生成")
    lines.append(f"> 基于 {len(state['experts'])} 个专家节点的输出整合而成。")
    lines.append(f"> 复盘相关的知识沉淀已{'自动同步' if state['trigger_knowledge_sync'] else '未触发'}。")

    # 写入文件
    os.makedirs(os.path.dirname(report_path), exist_ok=True)
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write("\n".join(lines))

    print(f"\n  ✅ 报告已生成: {report_path}")

    return {
        "completed_at": now.strftime('%Y-%m-%d %H:%M:%S'),
        "report_path": report_path,
    }


# ====================== 构建 LangGraph ======================
def build_langgraph() -> StateGraph:
    """构建 LangGraph StateGraph 工作流"""
    if not LANGGRAPH_AVAILABLE:
        return None

    workflow = StateGraph(OrchestratorState)

    # 添加节点
    workflow.add_node("detect_intent_node", detect_intent_node)

    # 动态创建专家节点
    from orchestrator import EXPERT_REGISTRY
    for expert_name in EXPERT_REGISTRY:
        node_name = f"expert_{expert_name}"
        workflow.add_node(node_name, make_expert_node(expert_name))

    workflow.add_node("knowledge_sync_node", knowledge_sync_node)
    workflow.add_node("output_node", output_node)

    # 添加边
    workflow.add_edge(START, "detect_intent_node")
    workflow.add_conditional_edges(
        "detect_intent_node",
        route_after_intent,
        {f"expert_{e}": f"expert_{e}" for e in EXPERT_REGISTRY} | {"output_node": "output_node"}
    )

    # 每个专家节点后的条件路由
    from orchestrator import EXPERT_REGISTRY
    for expert_name in EXPERT_REGISTRY:
        node_name = f"expert_{expert_name}"
        workflow.add_conditional_edges(
            node_name,
            route_after_expert,
            {f"expert_{e}": f"expert_{e}" for e in EXPERT_REGISTRY} | {"output_node": "output_node", "knowledge_sync_node": "knowledge_sync_node"}
        )

    # 知识同步 → 输出
    workflow.add_edge("knowledge_sync_node", "output_node")
    workflow.add_edge("output_node", END)

    return workflow


# ====================== 状态初始化 ======================
def init_state(user_input: str) -> OrchestratorState:
    """初始化全局状态"""
    return {
        "user_input": user_input,
        "intent": None,
        "workflow_name": None,
        "workflow_id": f"lg_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        "current_step": 0,
        "total_steps": 0,
        "experts": [],
        "results": {},
        "accumulated_context": {},
        "report_path": None,
        "trigger_knowledge_sync": False,
        "started_at": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        "completed_at": None,
        "errors": [],
    }


# ====================== 运行入口 ======================
def run_langgraph(user_input: str):
    """运行 LangGraph 工作流"""
    if not LANGGRAPH_AVAILABLE:
        print("❌ LangGraph 不可用，请安装: pip install langgraph langchain-core")
        return

    try:
        # 构建图
        graph = build_langgraph()
        if graph is None:
            print("❌ 构建LangGraph失败")
            return

        # 编译
        app = graph.compile(checkpointer=MemorySaver())

        print(f"""
╔══════════════════════════════════════════════════════╗
║     🧠 LangGraph 监督者模式工作流已启动              ║
║                                                     ║
║  输入: {user_input[:50]}{'...' if len(user_input) > 50 else ''}
╚══════════════════════════════════════════════════════╝
""")

        # 执行
        initial = init_state(user_input)
        result = app.invoke(initial, {"configurable": {"thread_id": initial["workflow_id"]}})

        # 输出结果
        print(f"\n{'='*50}")
        print(f"  ✅ LangGraph 工作流执行完成！")
        print(f"  📄 报告: {result.get('report_path', '（无报告）')}")
        print(f"{'='*50}")

        return result

    except Exception as e:
        print(f"❌ LangGraph 执行出错: {e}")
        import traceback
        traceback.print_exc()
        return None


def run_traditional(user_input: str):
    """回退到传统 orchestrator 模式"""
    print(f"\n🔄 回退到传统 Orchestrator 模式...\n")
    from orchestrator import Orchestrator
    orch = Orchestrator()
    orch.run(user_input)


def visualize_workflow():
    """导出工作流图（Mermaid格式）"""
    print("""
📊 LangGraph 工作流图 (Mermaid格式)
====================================

```mermaid
graph TD
    START([Start]) --> detect_intent[意图识别]
    detect_intent -->|有匹配专家| route{条件路由}
    detect_intent -->|无匹配| output[输出提示]
    
    subgraph 专家集群
        expert1[数据分析专家]
        expert2[创意视频专家]
        expert3[选品专家]
        expert4[竞品追踪专家]
        expert5[复盘专家]
        expert6[视频分析专家]
        expert7[内容脚本专家]
        expert8[数据导入专家]
    end
    
    route -->|步骤0| expert_i
    expert_i -->|还有下个专家| expert_j
    expert_i -->|全部完成且含复盘| knowledge_sync[知识沉淀同步]
    expert_i -->|全部完成| output_report[生成输出报告]
    knowledge_sync --> output_report
    output_report --> END([End])
```

    执行: python orchestrator_langgraph.py "你的任务"
""")

    # 尝试导出一份Mermaid文件
    mermaid_path = os.path.join(BASE_DIR, "Layer2_Working", "langgraph_workflow.md")
    with open(mermaid_path, 'w', encoding='utf-8') as f:
        f.write("""# LangGraph 工作流图

```mermaid
graph TD
    START([Start]) -->|用户输入| detect_intent[意图识别节点]
    detect_intent -->|路由: 有匹配专家| condition{还有下个专家?}
    detect_intent -->|路由: 无匹配| output_fallback[输出提示信息]
    
    subgraph 专家集群 Expert Nodes
        expert_data[数据分析专家]
        expert_creative[创意视频运营专家]
        expert_selection[选品分析专家]
        expert_competitor[竞品追踪专家]
        expert_review[复盘专家]
        expert_viral[爆款视频分析专家]
        expert_script[内容脚本生成专家]
        expert_import[数据导入专家]
    end
    
    condition -->|是| expert_current[执行当前专家]
    condition -->|否且含复盘| knowledge_sync[知识沉淀同步节点]
    condition -->|否| output_report[输出汇总节点]
    
    expert_current -->|更新状态 + 累积上下文| condition
    knowledge_sync -->|自动同步复盘结论到SOP| output_report
    output_report -->|生成Markdown报告文件| END([End])
```

## 节点说明

| 节点 | 功能 | 输出 |
|:---|:---|:---|
| detect_intent | 分析用户输入，识别意图，决定调度哪些专家 | experts列表 |
| expert_* | 执行单个专家任务 | 结构化结果 + key_findings |
| knowledge_sync | 解析复盘报告，将知识沉淀项同步到SOP文件 | 同步状态 |
| output_report | 汇总所有专家输出，生成综合报告 | 报告文件(.md) |

## 状态传递

工作流通过 `OrchestratorState` 在各节点间传递:
- `accumulated_context`: 步骤间传递摘要，供后续专家参考
- `results`: 每个专家的完整执行结果
- `errors`: 执行过程中的错误列表
- `trigger_knowledge_sync`: 控制是否触发知识同步
""")
    print(f"  📄 Mermaid 工作流图已导出: {mermaid_path}")


# ====================== 主程序 ======================
if __name__ == "__main__":
    if len(sys.argv) > 1:
        arg = " ".join(sys.argv[1:])
        if arg == "--visualize":
            visualize_workflow()
        elif arg.startswith("--"):
            print(f"❌ 未知参数: {arg}")
            print("用法: python orchestrator_langgraph.py [任务描述|--visualize]")
        else:
            if LANGGRAPH_AVAILABLE:
                run_langgraph(arg)
            else:
                run_traditional(arg)
    else:
        # 交互模式
        print("""
🧠 LangGraph 监督者模式工作流中枢
═══════════════════════════════════════
  输入任务描述，或:
    --visualize     导出工作流Mermaid图
    exit / quit     退出
═══════════════════════════════════════
""")
        while True:
            try:
                user_input = input("\n💬 你: ").strip()
                if user_input.lower() in ["退出", "exit", "quit"]:
                    print("👋 再见！")
                    break
                elif user_input == "--visualize":
                    visualize_workflow()
                elif not user_input:
                    continue
                else:
                    if LANGGRAPH_AVAILABLE:
                        run_langgraph(user_input)
                    else:
                        run_traditional(user_input)
            except KeyboardInterrupt:
                print("\n👋 再见！")
                break
            except EOFError:
                break
            except Exception as e:
                print(f"❌ 错误: {e}")
