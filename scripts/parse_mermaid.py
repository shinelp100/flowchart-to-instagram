#!/usr/bin/env python3
"""
Mermaid Flowchart TD 解析器
解析 Mermaid flowchart TD 语法，生成 Instagram 风格信息图 HTML

用法:
    python parse_mermaid.py input.mmd output.html
    python parse_mermaid.py --demo  # 使用示例数据
"""

import re
import sys
import argparse
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, field


@dataclass
class Node:
    """节点数据结构"""
    id: str
    title: str
    desc: str = ""
    subgraph: str = ""  # 所属 subgraph ID


@dataclass
class Subgraph:
    """Subgraph 数据结构"""
    id: str
    title: str
    nodes: List[Node] = field(default_factory=list)
    connections: List[Tuple[str, str]] = field(default_factory=list)  # (from_id, to_id)


@dataclass
class Flowchart:
    """完整流程图数据"""
    title: str = "产业链图谱"
    watermark: str = "题材调研员"
    subgraphs: List[Subgraph] = field(default_factory=list)
    all_nodes: Dict[str, Node] = field(default_factory=dict)
    all_connections: List[Tuple[str, str]] = field(default_factory=list)


def parse_node_content(content: str) -> Tuple[str, str]:
    """
    解析节点内容，提取标题和描述
    格式: "标题\\n描述" 或 "标题"
    """
    # 处理转义换行符
    content = content.replace('\\n', '\n')
    
    # 清理多余引号
    content = content.strip().strip('"').strip("'")
    
    if '\n' in content:
        parts = content.split('\n')
        title = parts[0].strip()
        desc = '\n'.join(parts[1:]).strip()
    else:
        title = content.strip()
        desc = ""
    
    return title, desc


def parse_mermaid(text: str) -> Flowchart:
    """
    解析 Mermaid flowchart TD 语法
    """
    flowchart = Flowchart()
    
    # 提取 title（如果有 %% title: xxx 注释）
    title_match = re.search(r'%%\s*title:\s*(.+)', text)
    if title_match:
        flowchart.title = title_match.group(1).strip()
    
    # 提取 watermark（如果有 %% watermark: xxx 注释）
    watermark_match = re.search(r'%%\s*watermark:\s*(.+)', text)
    if watermark_match:
        flowchart.watermark = watermark_match.group(1).strip()
    
    # 按行解析，跟踪当前所在的 subgraph
    lines = text.split('\n')
    current_subgraph = None
    node_order_in_sg = {}  # 记录节点在哪个 subgraph 以及顺序
    
    for line in lines:
        line_stripped = line.strip()
        
        # 跳过注释和空行
        if line_stripped.startswith('%%') or not line_stripped:
            continue
        
        # 跳过 flowchart 定义行
        if line_stripped.startswith('flowchart') or line_stripped.startswith('graph'):
            continue
        
        # 检测 subgraph 开始 - 格式: subgraph SG_ID["标题"]
        sg_match = re.match(r'subgraph\s+([A-Za-z0-9_]+)\s*[\[\("]+([^\]\)]+)[\]\)"]+', line_stripped)
        if sg_match:
            sg_id = sg_match.group(1)
            sg_title = parse_node_content(sg_match.group(2))[0]
            current_subgraph = Subgraph(id=sg_id, title=sg_title)
            flowchart.subgraphs.append(current_subgraph)
            continue
        
        # 检测 subgraph 结束
        if line_stripped == 'end':
            current_subgraph = None
            continue
        
        # 解析节点定义 - 格式: A["内容"] 或 A("内容")
        node_match = re.search(r'([A-Za-z0-9_]+)\s*[\[\("]+([^\]\)]+)[\]\)"]+', line_stripped)
        if node_match:
            node_id = node_match.group(1)
            content = node_match.group(2)
            title, desc = parse_node_content(content)
            
            # 创建节点
            node = Node(id=node_id, title=title, desc=desc)
            
            # 如果在 subgraph 内，分配到当前 subgraph
            if current_subgraph:
                node.subgraph = current_subgraph.id
                current_subgraph.nodes.append(node)
            
            # 记录到全局节点字典
            flowchart.all_nodes[node_id] = node
            continue
        
        # 解析连接关系（仅用于参考，不影响节点分配）
        conn_match = re.search(r'([A-Za-z0-9_]+)\s*[-<>]+\s*([A-Za-z0-9_]+)', line_stripped)
        if conn_match:
            from_id = conn_match.group(1)
            to_id = conn_match.group(2)
            flowchart.all_connections.append((from_id, to_id))
    
    # 处理未分配到任何 subgraph 的节点（放在最后一个 subgraph）
    unassigned_nodes = [n for n in flowchart.all_nodes.values() if not n.subgraph]
    if unassigned_nodes and flowchart.subgraphs:
        last_sg = flowchart.subgraphs[-1]
        for node in unassigned_nodes:
            node.subgraph = last_sg.id
            last_sg.nodes.append(node)
    
    # 如果没有 subgraph，创建一个默认的
    if not flowchart.subgraphs and flowchart.all_nodes:
        default_sg = Subgraph(id="default", title=flowchart.title)
        for node in flowchart.all_nodes.values():
            node.subgraph = "default"
            default_sg.nodes.append(node)
        flowchart.subgraphs.append(default_sg)
    
    return flowchart


def generate_html(flowchart: Flowchart) -> str:
    """
    生成 Instagram 风格 HTML
    """
    
    # 节点配色类
    node_colors = ['node-1', 'node-2', 'node-3', 'node-4', 'node-5', 'node-6']
    
    # 卡片配色类
    card_colors = ['card-1', 'card-2', 'card-3', 'card-4']
    
    html_parts = []
    
    # HTML 头部
    html_parts.append('''<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>''' + flowchart.title + ''' - ''' + flowchart.watermark + '''</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <link href="https://fonts.googleapis.com/css2?family=Noto+Sans+SC:wght@400;500;600;700&display=swap" rel="stylesheet">
  <style>
    * { font-family: 'Noto Sans SC', 'PingFang SC', 'Microsoft YaHei', sans-serif; }
    body {
      background: linear-gradient(135deg, #833ab4 0%, #fd1d1d 50%, #fcb045 100%);
      min-height: 100vh;
    }
    .watermark-bg {
      position: fixed; top: 0; left: 0; width: 100%; height: 100%;
      pointer-events: none; z-index: 0;
      display: grid;
      grid-template-columns: repeat(2, 1fr);
      grid-template-rows: repeat(2, 1fr);
      align-items: center; justify-items: center;
    }
    .watermark-text {
      font-size: 180px; font-weight: 700;
      color: rgba(255, 255, 255, 0.06);
      white-space: nowrap;
      transform: rotate(-20deg);
      user-select: none;
    }
    .card {
      background: linear-gradient(135deg, rgba(255,255,255,0.88) 0%, rgba(255,255,255,0.92) 50%, rgba(255,255,255,0.88) 100%);
      backdrop-filter: blur(16px); -webkit-backdrop-filter: blur(16px);
      border-radius: 16px;
      box-shadow: 0 8px 32px rgba(0,0,0,0.1);
      border: 1px solid rgba(255,255,255,0.3);
    }
    .card-1 { background: linear-gradient(135deg, rgba(255,240,250,0.9) 0%, rgba(255,245,255,0.92) 50%, rgba(255,250,245,0.9) 100%); }
    .card-2 { background: linear-gradient(135deg, rgba(255,235,245,0.9) 0%, rgba(255,240,250,0.92) 50%, rgba(255,245,240,0.9) 100%); }
    .card-3 { background: linear-gradient(135deg, rgba(255,230,240,0.9) 0%, rgba(255,235,245,0.92) 50%, rgba(255,240,235,0.9) 100%); }
    .card-4 { background: linear-gradient(135deg, rgba(255,235,235,0.9) 0%, rgba(255,230,240,0.92) 50%, rgba(255,240,230,0.9) 100%); }
    .node-card {
      background: rgba(255,255,255,0.95);
      border-radius: 12px;
      box-shadow: 0 3px 12px rgba(0,0,0,0.05);
      border: 1px solid rgba(255,255,255,0.5);
    }
    .section-title { font-size: 20px; font-weight: 700; color: #1a1a1a; margin-bottom: 14px; }
    .node-title { font-size: 19px; font-weight: 600; color: #1a1a1a; line-height: 1.4; }
    .node-desc { font-size: 15px; font-weight: 400; color: #3a3a3a; line-height: 1.5; margin-top: 6px; }
    .node-1 { background: linear-gradient(135deg, #fef7f7 0%, #fce8e8 100%); }
    .node-2 { background: linear-gradient(135deg, #fef9f3 0%, #fde9d9 100%); }
    .node-3 { background: linear-gradient(135deg, #fef8f0 0%, #fde5cc 100%); }
    .node-4 { background: linear-gradient(135deg, #f4fef7 0%, #dcf8e3 100%); }
    .node-5 { background: linear-gradient(135deg, #f3f7fe 0%, #dce5f8 100%); }
    .node-6 { background: linear-gradient(135deg, #f8f5fe 0%, #e8dcf8 100%); }
  </style>
</head>
<body class="p-5">
  <div class="watermark-bg">
    <div class="watermark-text">''' + flowchart.watermark + '''</div>
    <div class="watermark-text">''' + flowchart.watermark + '''</div>
    <div class="watermark-text">''' + flowchart.watermark + '''</div>
    <div class="watermark-text">''' + flowchart.watermark + '''</div>
  </div>
  <div class="relative z-10 max-w-[800px] mx-auto space-y-5">
''')
    
    # 生成每个 subgraph 的卡片
    for idx, sg in enumerate(flowchart.subgraphs):
        card_class = card_colors[idx % len(card_colors)]
        
        # 计算节点布局
        node_count = len(sg.nodes)
        
        if node_count <= 3:
            # 横向布局
            nodes_html = '<div class="flex items-center justify-between gap-4">'
            for n_idx, node in enumerate(sg.nodes):
                node_class = node_colors[n_idx % len(node_colors)]
                desc_html = f'<div class="node-desc">{node.desc}</div>' if node.desc else ''
                nodes_html += f'''
                <div class="node-card {node_class} p-5 flex-1 text-center">
                  <div class="node-title">{node.title}</div>
                  {desc_html}
                </div>'''
            nodes_html += '</div>'
        
        elif node_count <= 6:
            # 两行布局
            first_row = sg.nodes[:3]
            second_row = sg.nodes[3:]
            
            nodes_html = '<div class="space-y-4">'
            # 第一行
            nodes_html += '<div class="flex gap-4">'
            for n_idx, node in enumerate(first_row):
                node_class = node_colors[n_idx % len(node_colors)]
                desc_html = f'<div class="node-desc">{node.desc}</div>' if node.desc else ''
                nodes_html += f'''
                <div class="node-card {node_class} p-4 flex-1 text-center">
                  <div class="node-title">{node.title}</div>
                  {desc_html}
                </div>'''
            nodes_html += '</div>'
            
            # 第二行
            if second_row:
                nodes_html += '<div class="flex gap-4">'
                for n_idx, node in enumerate(second_row):
                    node_class = node_colors[(n_idx + 3) % len(node_colors)]
                    desc_html = f'<div class="node-desc">{node.desc}</div>' if node.desc else ''
                    nodes_html += f'''
                    <div class="node-card {node_class} p-4 flex-1 text-center">
                      <div class="node-title">{node.title}</div>
                      {desc_html}
                    </div>'''
                nodes_html += '</div>'
            
            nodes_html += '</div>'
        
        else:
            # 多行布局
            nodes_html = '<div class="space-y-4">'
            rows = []
            for i in range(0, node_count, 3):
                rows.append(sg.nodes[i:i+3])
            
            for row_idx, row in enumerate(rows):
                nodes_html += '<div class="flex gap-4">'
                for n_idx, node in enumerate(row):
                    node_class = node_colors[(row_idx * 3 + n_idx) % len(node_colors)]
                    desc_html = f'<div class="node-desc">{node.desc}</div>' if node.desc else ''
                    nodes_html += f'''
                    <div class="node-card {node_class} p-4 flex-1 text-center">
                      <div class="node-title">{node.title}</div>
                      {desc_html}
                    </div>'''
                nodes_html += '</div>'
            nodes_html += '</div>'
        
        # 生成卡片
        html_parts.append(f'''
    <div class="card {card_class} p-6">
      <div class="section-title">{sg.title}</div>
      {nodes_html}
    </div>
''')
    
    # HTML 尾部
    html_parts.append('''
  </div>
</body>
</html>''')
    
    return '\n'.join(html_parts)


def main():
    parser = argparse.ArgumentParser(description='Mermaid Flowchart TD 解析器')
    parser.add_argument('input', nargs='?', help='输入 Mermaid 文件路径 (.mmd)')
    parser.add_argument('output', nargs='?', help='输出 HTML 文件路径')
    parser.add_argument('--demo', action='store_true', help='使用示例数据演示')
    
    args = parser.parse_args()
    
    if args.demo:
        # 示例 Mermaid 数据
        demo_mermaid = '''
%% title: 储能产业链
%% watermark: 题材调研员

flowchart TD
subgraph SG1["上游：材料与电芯"]
    A1["碳酸锂\\n锂精矿"]
    A2["正极材料\\n负极材料\\n隔膜电解液"]
    A3["电芯制造\\n宁德时代\\n比亚迪·亿纬"]
    A1 --> A2
    A2 --> A3
end

subgraph SG2["中游：系统集成与变流器"]
    B1["储能电池系统\\nPACK + BMS"]
    B2["储能变流器\\nPCS\\n阳光电源·华为"]
    B3["系统集成商\\n海博思创\\n远景·电工时代"]
    A3 --> B1
    B1 --> B2
    B2 --> B3
end

subgraph SG3["下游：应用场景"]
    C1["电源侧\\n新能源配储"]
    C2["电网侧\\n独立储能/调频"]
    C3["用户侧\\n工商业/家庭"]
    C4["电力市场交易"]
    C5["虚拟电厂\\n聚合调度"]
    B3 --> C1
    B3 --> C2
    B3 --> C3
end
'''
        flowchart = parse_mermaid(demo_mermaid)
        html = generate_html(flowchart)
        
        output_path = '/tmp/demo-flowchart.html'
        Path(output_path).write_text(html)
        print(f'Demo HTML generated: {output_path}')
        return
    
    if not args.input:
        parser.print_help()
        return
    
    # 读取输入文件
    input_path = Path(args.input)
    if not input_path.exists():
        print(f'Error: Input file not found: {input_path}')
        sys.exit(1)
    
    mermaid_text = input_path.read_text()
    
    # 解析
    flowchart = parse_mermaid(mermaid_text)
    
    # 生成 HTML
    html = generate_html(flowchart)
    
    # 输出
    if args.output:
        output_path = Path(args.output)
    else:
        output_path = input_path.with_suffix('.html')
    
    output_path.write_text(html)
    print(f'HTML generated: {output_path}')
    print(f'  Title: {flowchart.title}')
    print(f'  Watermark: {flowchart.watermark}')
    print(f'  Subgraphs: {len(flowchart.subgraphs)}')
    print(f'  Nodes: {len(flowchart.all_nodes)}')


if __name__ == '__main__':
    main()