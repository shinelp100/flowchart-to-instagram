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


# 关键词到emoji的智能映射表（产业链图谱专用）
EMOJI_KEYWORDS = {
    # 上游材料层
    '冷却液': '🧪', '氟化液': '🧪', '硅基液': '🧪', '液体': '🧪',
    '金属': '⚙️', '铜': '⚙️', '铝': '⚙️', '金刚石': '💎', '材料': '📦',
    '电子元器件': '🔌', '泵': '🔧', '阀': '🔧', '传感器': '📡', '元器件': '🔌',
    
    # 核心部件层
    '液冷板': '❄️', '冷板': '❄️', '微通道': '❄️',
    'CDU': '🎛️', '分配单元': '🎛️', '分配系统': '🎛️',
    '快接头': '🔗', '连接器': '🔗', 'UQD': '🔗',
    'Manifold': '🔀', '歧管': '🔀', '管路': '🔀', '管道': '🔀',
    
    # 系统集成层
    '服务器': '🖥️', '液冷服务器': '🖥️', '整机柜': '🗄️', '机柜': '🗄️',
    '温控': '🌡️', '温控系统': '🌡️', '数据中心': '🏢',
    
    # 下游应用层
    'AI': '🤖', '智算中心': '🤖', '大模型': '🧠', '训练': '🧠',
    '超算': '⚡', '科学计算': '⚡',
    '云计算': '☁️', '互联网': '🌐', '云服务': '☁️',
    
    # 通用产业
    '上游': '⬆️', '下游': '⬇️', '核心': '🎯', '系统': '🔧',
    '芯片': '💾', '存储': '💾', '内存': '💾', 'DRAM': '💾',
    '原厂': '🏭', '厂商': '🏭', '工厂': '🏭',
    '供应链': '🔗', '传导': '➡️', '终端': '📱',
    '手机': '📱', 'PC': '💻', '电脑': '💻', '消费电子': '📱',
    '需求': '📈', '供给': '📉', '涨价': '💰', '价格': '💰',
    '产能': '📊', '产量': '📊', '市场': '📊',
    
    # 技术相关
    '技术': '🔬', '研发': '🔬', '创新': '💡',
    '专利': '📜', '标准': '📋',
    
    # 金融相关
    '投资': '💵', '融资': '💵', '资金': '💵',
    '成本': '📉', '利润': '📈', '营收': '📈',
    
    # 时间相关
    '过去': '📅', '现在': '📅', '未来': '🔮',
    '周期': '🔄', '阶段': '📊',
    
    # 人物/角色
    '客户': '👥', '用户': '👥', '供应商': '🤝',
}


def auto_match_emoji(title: str) -> str:
    """
    根据标题关键词自动匹配emoji
    返回匹配度最高的emoji，如果没有匹配则返回空字符串
    """
    # 直接匹配
    for keyword, emoji in EMOJI_KEYWORDS.items():
        if keyword in title:
            return emoji
    
    # 部分匹配（标题包含关键词的一部分）
    for keyword, emoji in EMOJI_KEYWORDS.items():
        if any(k in title for k in keyword.split('/')):
            return emoji
    
    return ''


def remove_emoji(text: str) -> str:
    """
    移除文本中的 emoji 字符
    但保留 Font Awesome icon 格式（fa:xxx, fas:xxx 等）
    """
    # emoji unicode 范围
    emoji_pattern = re.compile(
        "["
        "\U0001F600-\U0001F64F"  # emoticons
        "\U0001F300-\U0001F5FF"  # symbols & pictographs
        "\U0001F680-\U0001F6FF"  # transport & map symbols
        "\U0001F700-\U0001F77F"  # alchemical symbols
        "\U0001F780-\U0001F7FF"  # Geometric Shapes Extended
        "\U0001F800-\U0001F8FF"  # Supplemental Arrows-C
        "\U0001F900-\U0001F9FF"  # Supplemental Symbols and Pictographs
        "\U0001FA00-\U0001FA6F"  # Chess Symbols
        "\U0001FA70-\U0001FAFF"  # Symbols and Pictographs Extended-A
        "\U00002702-\U000027B0"  # Dingbats
        # 移除包含中文的大范围 \U000024C2-\U0001F251，保留中文
        "]+",
        flags=re.UNICODE
    )
    return emoji_pattern.sub('', text)


@dataclass
class Node:
    """节点数据结构"""
    id: str
    title: str
    desc: str = ""
    icon: str = ""  # Font Awesome icon，格式: fa:icon-name
    subgraph: str = ""  # 所属 subgraph ID


@dataclass
class Subgraph:
    """Subgraph 数据结构"""
    id: str
    title: str
    icon: str = ""  # Font Awesome icon，格式: fa:icon-name 或 emoji
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


def parse_node_content(content: str) -> Tuple[str, str, str]:
    """
    解析节点内容，提取图标、标题和描述
    格式: "fa:icon 标题\\n描述" 或 "🏭 标题\\n描述" 或 "标题\\n描述" 或 "标题"
    返回: (icon, title, desc)

    支持的 icon 格式:
    - fa:icon-name (Font Awesome 通用)
    - fas:icon-name (Font Awesome Solid)
    - fab:icon-name (Font Awesome Brands)
    - far:icon-name (Font Awesome Regular)
    - emoji (开头的 emoji 字符)
    """
    # 处理转义换行符
    content = content.replace('\\n', '\n')

    # 清理多余引号
    content = content.strip().strip('"').strip("'")

    icon = ""

    # 1. 先提取 Font Awesome icon (格式: fa:xxx 或 fas:xxx 等)
    fa_pattern = r'^\s*(fa[sbr]?:[a-z0-9-]+)\s+'
    fa_match = re.match(fa_pattern, content)
    if fa_match:
        icon = fa_match.group(1)
        content = content[fa_match.end():].strip()

    # 2. 提取开头的 emoji 作为 icon（如果没有 Font Awesome icon）
    if not icon:
        # 更完整的 emoji unicode 范围，包含 variation selectors
        emoji_pattern = re.compile(
            "["
            "\\U0001F600-\\U0001F64F"  # emoticons
            "\\U0001F300-\\U0001F5FF"  # symbols & pictographs
            "\\U0001F680-\\U0001F6FF"  # transport & map symbols
            "\\U0001F700-\\U0001F77F"  # alchemical symbols
            "\\U0001F780-\\U0001F7FF"  # Geometric Shapes Extended
            "\\U0001F800-\\U0001F8FF"  # Supplemental Arrows-C
            "\\U0001F900-\\U0001F9FF"  # Supplemental Symbols and Pictographs
            "\\U0001FA00-\\U0001FA6F"  # Chess Symbols
            "\\U0001FA70-\\U0001FAFF"  # Symbols and Pictographs Extended-A
            "\\U00002600-\\U000027BF"  # Miscellaneous Symbols + Dingbats (包括 ⚙ U+2699)
            "\\U00002B50-\\U00002B55"  # Stars (⭐)
            "\\U0000FE00-\\U0000FE0F"  # Variation Selectors (用于文本符号变emoji)
            "\\U0001F1E0-\\U0001F1FF"  # Flags (区域性符号)
            "]+",
            flags=re.UNICODE
        )
        emoji_match = emoji_pattern.match(content)
        if emoji_match:
            icon = emoji_match.group(0)  # 保留 emoji 作为 icon
            content = content[emoji_match.end():].strip()

    # 3. 剩余内容移除其他 emoji（只保留标题文本）
    content = remove_emoji(content)

    # 提取标题和描述
    if '\n' in content:
        parts = content.split('\n')
        title = parts[0].strip()
        desc = '\n'.join(parts[1:]).strip()
    else:
        title = content.strip()
        desc = ""

    # 4. 如果没有icon，自动根据标题关键词匹配emoji
    if not icon:
        icon = auto_match_emoji(title)

    return icon, title, desc


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
    
    # 跟踪是否在 %%{init}%% 配置块内
    in_init_block = False
    
    for line in lines:
        line_stripped = line.strip()
        
        # 检测 %%{init}%% 配置块开始
        if line_stripped.startswith('%%{init'):
            in_init_block = True
            continue
        
        # 检测 %%{init}%% 配置块结束
        if in_init_block:
            if '%%' in line_stripped and '}' in line_stripped:
                in_init_block = False
            continue
        
        # 跳过注释和空行
        if line_stripped.startswith('%%') or not line_stripped:
            continue
        
        # 跳过 flowchart 定义行
        if line_stripped.startswith('flowchart') or line_stripped.startswith('graph'):
            continue
        
        # 跳过 style 定义行
        if line_stripped.startswith('style'):
            continue
        
        # 检测 subgraph 开始 - 格式: subgraph SG_ID["标题"] 或 subgraph 中文ID["标题"]
        # 支持中文ID（如 "上游"、"中游"）
        sg_match = re.match(r'subgraph\s+(\S+)\s*[\[\("]+([^\]\)]+)[\]\)"]+', line_stripped)
        if sg_match:
            sg_id = sg_match.group(1)
            sg_title_raw = sg_match.group(2)
            # 解析 subgraph 标题，保留 icon（emoji 或 fa:xxx）
            sg_icon, sg_title, _ = parse_node_content(sg_title_raw)
            current_subgraph = Subgraph(id=sg_id, title=sg_title, icon=sg_icon)
            flowchart.subgraphs.append(current_subgraph)
            continue
        
        # 检测 subgraph 结束
        if line_stripped == 'end':
            current_subgraph = None
            continue
        
        # 解析节点定义 - 格式: A["内容"] 或 A("内容")
        # 使用 findall 找出所有节点定义（包括连接行中的）
        # 改进的正则，精确匹配节点定义格式 A["content"] 或 A("content")
        node_matches = re.findall(r'([A-Za-z0-9_]+)\s*\[\"([^\"]+)\"\]', line_stripped)
        # 如果没有找到方括号格式，尝试圆括号格式
        if not node_matches:
            node_matches = re.findall(r'([A-Za-z0-9_]+)\s*\(\"([^\"]+)\"\)', line_stripped)
        for node_id, content in node_matches:
            if node_id not in flowchart.all_nodes:
                icon, title, desc = parse_node_content(content)
                node = Node(id=node_id, title=title, desc=desc, icon=icon)
                
                if current_subgraph:
                    node.subgraph = current_subgraph.id
                    current_subgraph.nodes.append(node)
                
                flowchart.all_nodes[node_id] = node
        
        # 解析连接关系 - 使用 findall 找出所有连接
        # 匹配连接符号前后的节点（可能带有内容定义）
        # 格式: A --> B 或 A["..."] --> B["..."]
        # 简化策略：先去除节点内容定义，再匹配连接
        line_clean = re.sub(r'\[[^\]]+\]', '', line_stripped)  # 去除 [...] 内容
        line_clean = re.sub(r'\([^\)]+\)', '', line_clean)      # 去除 (...) 内容
        conn_matches = re.findall(r'([A-Za-z0-9_]+)\s*(?:-{2,}>?|->|--)\s*([A-Za-z0-9_]+)', line_clean)
        for from_id, to_id in conn_matches:
            flowchart.all_connections.append((from_id, to_id))
            
            # 如果节点没有定义内容，创建一个占位节点
            if from_id not in flowchart.all_nodes:
                placeholder_node = Node(id=from_id, title=from_id)
                if current_subgraph:
                    placeholder_node.subgraph = current_subgraph.id
                    current_subgraph.nodes.append(placeholder_node)
                flowchart.all_nodes[from_id] = placeholder_node
            
            if to_id not in flowchart.all_nodes:
                placeholder_node = Node(id=to_id, title=to_id)
                if current_subgraph:
                    placeholder_node.subgraph = current_subgraph.id
                    current_subgraph.nodes.append(placeholder_node)
                flowchart.all_nodes[to_id] = placeholder_node
    
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


def analyze_hierarchical_structure(nodes: List[Node], connections: List[Tuple[str, str]]) -> List[List[Node]]:
    """
    分析层级结构（父节点→多个子节点）
    
    适用于树形结构，如 A→A1, A→A2, B→B1, B→B2
    每个父节点和其所有子节点组成一个"列"，父节点在上，子节点在下
    
    返回: 列列表，每列是节点列表（父节点+子节点）
    """
    node_ids = [n.id for n in nodes]
    node_map = {n.id: n for n in nodes}
    
    # 找出 subgraph 内的连接
    sg_connections = [(from_id, to_id) for from_id, to_id in connections 
                      if from_id in node_ids and to_id in node_ids]
    
    # 构建父子关系映射
    parent_to_children = {}
    child_to_parent = {}
    
    for from_id, to_id in sg_connections:
        if from_id not in parent_to_children:
            parent_to_children[from_id] = []
        parent_to_children[from_id].append(to_id)
        child_to_parent[to_id] = from_id
    
    # 找出父节点（有子节点但自己不是子节点）
    parent_nodes = [n for n in nodes if n.id in parent_to_children and n.id not in child_to_parent]
    
    # 找出中间节点（既是父节点又是子节点）
    middle_nodes = [n for n in nodes if n.id in parent_to_children and n.id in child_to_parent]
    
    # 找出叶子节点（只有父节点没有子节点）
    leaf_nodes = [n for n in nodes if n.id not in parent_to_children and n.id in child_to_parent]
    
    # 找出孤立节点（既没有父节点也没有子节点）
    orphan_nodes = [n for n in nodes if n.id not in parent_to_children and n.id not in child_to_parent]
    
    columns = []
    used_nodes = set()
    
    # 处理父节点列
    for parent in parent_nodes:
        column = [parent]
        used_nodes.add(parent.id)
        
        # 添加所有子节点
        children_ids = parent_to_children.get(parent.id, [])
        for child_id in children_ids:
            child = node_map.get(child_id)
            if child and child_id not in used_nodes:
                column.append(child)
                used_nodes.add(child_id)
        
        columns.append(column)
    
    # 处理中间节点（作为子节点跟随其父节点）
    for middle in middle_nodes:
        if middle.id not in used_nodes:
            # 找出其父节点
            parent_id = child_to_parent.get(middle.id)
            if parent_id:
                # 找出父节点所在的列，添加中间节点
                for col in columns:
                    if col[0].id == parent_id:
                        col.append(middle)
                        used_nodes.add(middle.id)
                        # 添加中间节点的子节点
                        children_ids = parent_to_children.get(middle.id, [])
                        for child_id in children_ids:
                            child = node_map.get(child_id)
                            if child and child_id not in used_nodes:
                                col.append(child)
                                used_nodes.add(child_id)
                        break
    
    # 处理叶子节点（跟随其父节点）
    for leaf in leaf_nodes:
        if leaf.id not in used_nodes:
            parent_id = child_to_parent.get(leaf.id)
            if parent_id:
                for col in columns:
                    if col[0].id == parent_id:
                        col.append(leaf)
                        used_nodes.add(leaf.id)
                        break
    
    # 处理孤立节点
    for orphan in orphan_nodes:
        if orphan.id not in used_nodes:
            columns.append([orphan])
            used_nodes.add(orphan.id)
    
    return columns


def analyze_chains_in_subgraph(nodes: List[Node], connections: List[Tuple[str, str]]) -> List[List[Node]]:
    """
    分析 subgraph 内的线性链路
    
    根据连接关系将节点分组为多条链路（每条链路是一条线性递进路径）
    例如: M1→M2, M3→M4, M5→M6 会生成 3 条链路
    
    返回: 链路列表，每条链路是节点列表（按连接顺序排列）
    """
    node_ids = [n.id for n in nodes]
    
    # 找出 subgraph 内的连接
    sg_connections = [(from_id, to_id) for from_id, to_id in connections 
                      if from_id in node_ids and to_id in node_ids]
    
    # 构建链路：找出起始节点（没有入边的节点）
    incoming = {to_id for _, to_id in sg_connections}
    start_nodes = [n for n in nodes if n.id not in incoming]
    
    chains = []
    used_nodes = set()
    
    for start_node in start_nodes:
        # 从起始节点追踪链路
        chain = [start_node]
        used_nodes.add(start_node.id)
        current_id = start_node.id
        
        while True:
            # 找出当前节点的下一个节点
            next_id = None
            for from_id, to_id in sg_connections:
                if from_id == current_id and to_id not in used_nodes:
                    next_id = to_id
                    break
            
            if next_id:
                next_node = next((n for n in nodes if n.id == next_id), None)
                if next_node:
                    chain.append(next_node)
                    used_nodes.add(next_id)
                    current_id = next_id
            else:
                break
        
        chains.append(chain)
    
    # 处理没有被链路包含的节点（孤立节点）
    orphan_nodes = [n for n in nodes if n.id not in used_nodes]
    for node in orphan_nodes:
        chains.append([node])
    
    return chains


def icon_to_html(icon: str) -> str:
    """
    将 icon 字符串转换为 HTML
    
    支持的格式:
    - fa:icon-name → <i class="fas fa-icon-name"></i>
    - fas:icon-name → <i class="fas fa-icon-name"></i>
    - fab:icon-name → <i class="fab fa-icon-name"></i>
    - far:icon-name → <i class="far fa-icon-name"></i>
    - emoji → 直接返回 emoji 字符
    """
    if not icon:
        return ""
    
    # 如果是 Font Awesome icon
    if ':' in icon:
        parts = icon.split(':')
        if len(parts) != 2:
            return ""
        
        prefix = parts[0]
        icon_name = parts[1]
        
        if prefix == 'fa':
            class_name = f"fas fa-{icon_name}"
        elif prefix in ['fas', 'fab', 'far', 'fal', 'fad']:
            class_name = f"{prefix} fa-{icon_name}"
        else:
            return ""
        
        return f'<i class="{class_name}"></i>'
    
    # 如果是 emoji，直接返回
    return icon


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
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css">
  <style>
    * { font-family: 'Noto Sans SC', 'PingFang SC', 'Microsoft YaHei', sans-serif; }
    body {
      background: linear-gradient(135deg, #833ab4 0%, #fd1d1d 50%, #fcb045 100%);
      padding-bottom: 20px;
    }
    .watermark-bg {
      position: fixed; top: 0; left: 0; width: 100vw; height: 100vh;
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
      background: linear-gradient(135deg, rgba(255,250,245,0.85) 0%, rgba(255,252,248,0.88) 50%, rgba(250,245,255,0.85) 100%);
      backdrop-filter: blur(16px); -webkit-backdrop-filter: blur(16px);
      border-radius: 16px;
      box-shadow: 0 8px 32px rgba(0,0,0,0.12);
      border: 1px solid rgba(255,255,255,0.4);
    }
    .card-1 { background: linear-gradient(135deg, rgba(250,245,255,0.82) 0%, rgba(255,250,245,0.85) 50%, rgba(255,245,250,0.82) 100%); }
    .card-2 { background: linear-gradient(135deg, rgba(255,245,250,0.82) 0%, rgba(250,255,245,0.85) 50%, rgba(245,250,255,0.82) 100%); }
    .card-3 { background: linear-gradient(135deg, rgba(245,250,255,0.82) 0%, rgba(250,245,255,0.85) 50%, rgba(255,250,245,0.82) 100%); }
    .card-4 { background: linear-gradient(135deg, rgba(255,250,245,0.82) 0%, rgba(245,255,250,0.85) 50%, rgba(250,245,255,0.82) 100%); }
    .node-card {
      background: rgba(255,255,255,0.88);
      border-radius: 12px;
      box-shadow: 0 3px 12px rgba(0,0,0,0.08);
      border: 1px solid rgba(255,255,255,0.6);
    }
    .section-title { font-size: 24px; font-weight: 700; color: #1a1a1a; margin-bottom: 14px; text-align: center; }
    .node-title { font-size: 19px; font-weight: 600; color: #1a1a1a; line-height: 1.4; }
    .node-desc { font-size: 15px; font-weight: 400; color: #3a3a3a; line-height: 1.5; margin-top: 6px; }
    .node-icon { color: #833ab4; opacity: 0.85; margin-bottom: 8px; }
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
        
        # 优先尝试层级结构分析（树形：父→多子）
        columns = analyze_hierarchical_structure(sg.nodes, flowchart.all_connections)
        
        # 如果只有单列且每列只有1-2节点，可能是线性链路，改用链路分析
        if len(columns) == 1 or (len(columns) > 1 and all(len(col) <= 2 for col in columns)):
            chains = analyze_chains_in_subgraph(sg.nodes, flowchart.all_connections)
            use_hierarchy = False
        else:
            use_hierarchy = True
        
        # 根据 use_hierarchy 决定布局
        if use_hierarchy:
            # 层级布局：父节点在上（横向），子节点在下（横向并列）
            # 第一行：所有父节点横向排列
            nodes_html = '<div class="space-y-4">'
            
            # 第一行：父节点横向排列
            nodes_html += '<div class="flex gap-4 justify-center">'
            for col_idx, column in enumerate(columns):
                parent = column[0]  # 第一个节点是父节点
                node_class = node_colors[col_idx % len(node_colors)]
                title_br = parent.title.replace('\n', '<br>')
                desc_br = parent.desc.replace('\n', '<br>') if parent.desc else ''
                desc_html = f'<div class="node-desc">{desc_br}</div>' if desc_br else ''
                icon_html = icon_to_html(parent.icon) if parent.icon else ''
                icon_div = f'<div class="node-icon text-xl mb-1">{icon_html}</div>' if icon_html else ''
                
                nodes_html += f'''
                <div class="node-card {node_class} p-4 text-center flex-1">
                  {icon_div}<div class="node-title">{title_br}</div>
                  {desc_html}
                </div>'''
            nodes_html += '</div>'
            
            # 向下箭头行
            nodes_html += '<div class="flex gap-4 justify-center">'
            for col_idx, column in enumerate(columns):
                nodes_html += '<div class="flex-1 text-center"><span class="text-gray-400 text-xl">↓</span></div>'
            nodes_html += '</div>'
            
            # 第二行：每个父节点的子节点横向并列（在各自的分组内）
            nodes_html += '<div class="flex gap-4">'
            for col_idx, column in enumerate(columns):
                children = column[1:]  # 后面的节点是子节点
                nodes_html += '<div class="flex-1 flex gap-2 justify-center">'
                for child_idx, child in enumerate(children):
                    node_class = node_colors[(col_idx + child_idx) % len(node_colors)]
                    title_br = child.title.replace('\n', '<br>')
                    desc_br = child.desc.replace('\n', '<br>') if child.desc else ''
                    desc_html = f'<div class="node-desc">{desc_br}</div>' if desc_br else ''
                    icon_html = icon_to_html(child.icon) if child.icon else ''
                    icon_div = f'<div class="node-icon text-xl mb-1">{icon_html}</div>' if icon_html else ''
                    
                    nodes_html += f'''
                    <div class="node-card {node_class} p-3 text-center">
                      {icon_div}<div class="node-title text-base">{title_br}</div>
                      {desc_html}
                    </div>'''
                nodes_html += '</div>'
            nodes_html += '</div>'
            
            nodes_html += '</div>'
        
        elif len(chains) == 1 and len(chains[0]) <= 3:
            # 单链路、短：横向布局（无箭头）
            chain = chains[0]
            nodes_html = '<div class="flex items-center justify-between gap-4">'
            for n_idx, node in enumerate(chain):
                node_class = node_colors[n_idx % len(node_colors)]
                title_br = node.title.replace('\n', '<br>')
                desc_br = node.desc.replace('\n', '<br>') if node.desc else ''
                desc_html = f'<div class="node-desc">{desc_br}</div>' if desc_br else ''
                # icon 渲染
                icon_html = icon_to_html(node.icon) if node.icon else ''
                icon_div = f'<div class="node-icon text-xl mb-1">{icon_html}</div>' if icon_html else ''
                nodes_html += f'''
                <div class="node-card {node_class} p-5 flex-1 text-center">
                  {icon_div}<div class="node-title">{title_br}</div>
                  {desc_html}
                </div>'''
            nodes_html += '</div>'
        
        else:
            # 多链路或长链路：横向并排，每条链路上下递进
            nodes_html = '<div class="flex gap-6 items-start">'
            for chain_idx, chain in enumerate(chains):
                # 每条链路是一个列
                nodes_html += '<div class="flex-1 space-y-3">'
                for node_idx, node in enumerate(chain):
                    node_class = node_colors[(chain_idx + node_idx) % len(node_colors)]
                    title_br = node.title.replace('\n', '<br>')
                    desc_br = node.desc.replace('\n', '<br>') if node.desc else ''
                    desc_html = f'<div class="node-desc">{desc_br}</div>' if desc_br else ''
                    # icon 渲染
                    icon_html = icon_to_html(node.icon) if node.icon else ''
                    icon_div = f'<div class="node-icon text-xl mb-1">{icon_html}</div>' if icon_html else ''
                    
                    # 节点卡片
                    nodes_html += f'''
                    <div class="node-card {node_class} p-4 text-center">
                      {icon_div}<div class="node-title">{title_br}</div>
                      {desc_html}
                    </div>'''
                    
                    # 如果不是链路最后一个节点，添加向下箭头
                    if node_idx < len(chain) - 1:
                        nodes_html += '<div class="text-center text-gray-400 text-xl">↓</div>'
                
                nodes_html += '</div>'
            nodes_html += '</div>'
        
        # 生成卡片
        # 渲染 subgraph icon（emoji 或 Font Awesome）
        sg_icon_html = ""
        if sg.icon:
            if sg.icon.startswith('fa'):
                sg_icon_html = f'<span class="mr-2">{icon_to_html(sg.icon)}</span>'
            else:
                # emoji 直接显示
                sg_icon_html = f'<span class="mr-2">{sg.icon}</span>'
        
        html_parts.append(f'''
    <div class="card {card_class} p-6">
      <div class="section-title">{sg_icon_html}{sg.title}</div>
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