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
    '智能驾驶': '🚗', '自动驾驶': '🚗', '驾驶': '🚗',
    '具身机器人': '🤖', '机器人': '🤖',
    '科学研究': '🔬', '研究': '🔬', '科研': '🔬',
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
    direction: str = "TD"  # LR=Left-Right, TD=Top-Down
    subgraphs: List[Subgraph] = field(default_factory=list)
    raw_text: str = ""  # 原始文本，用于场景识别
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
    flowchart.raw_text = text  # 保存原始文本，用于场景识别
    
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
        
        # 检测 %%{init}%% 配置块（单行或多行）
        if line_stripped.startswith('%%{init'):
            # 检查是否是单行格式 %%{init: ... }%% 或 %%{init: ... }}%%
            if '%%' in line_stripped[line_stripped.find('{')+1:]:
                # 单行格式，直接跳过
                continue
            else:
                # 多行格式，进入 init_block 状态
                in_init_block = True
                continue
        
        # 检测 %%{init}%% 多行配置块结束
        if in_init_block:
            if '%%' in line_stripped and '}' in line_stripped:
                in_init_block = False
            continue
        
        # 跳过注释和空行
        if line_stripped.startswith('%%') or not line_stripped:
            continue
        
        # 解析 flowchart 定义行，提取方向（LR/TD）
        if line_stripped.startswith('flowchart') or line_stripped.startswith('graph'):
            # 提取方向：flowchart LR, flowchart TD, flowchart LR-down, etc.
            dir_match = re.search(r'(?:flowchart|graph)\s+(LR|TD|RL|BT|TB|LR-down|TD-left)', line_stripped, re.IGNORECASE)
            if dir_match:
                flowchart.direction = dir_match.group(1).upper()
            continue
        
        # 跳过 style 定义行
        if line_stripped.startswith('style'):
            continue
        
        # 检测 subgraph 开始 - 格式: subgraph SG_ID["标题"] 或 subgraph 中文ID["标题"]
        # 支持中文ID（如 "上游"、"中游"）
        sg_match = re.match(r'subgraph\s+(\S+)\s*\["([^"]+)"\]', line_stripped)
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
        
# 解析节点定义 - 格式: A["内容"] 或 A("内容") 或 A[内容]（无引号）
        # 使用 findall 找出所有节点定义（包括连接行中的）
        # 改进的正则，支持三种格式：
        # 1. A["content"] - 双引号方括号
        # 2. A("content") - 双引号圆括号
        # 3. A[content] - 无引号方括号（用户常用）
        node_matches = re.findall(r'([A-Za-z0-9_]+)\s*\[\"([^"]+)\"\]', line_stripped)
        if not node_matches:
            node_matches = re.findall(r'([A-Za-z0-9_]+)\s*\(\"([^"]+)\"\)', line_stripped)
        if not node_matches:
            # 支持无引号格式：A[内容]
            node_matches = re.findall(r'([A-Za-z0-9_]+)\s*\[([^\]]+)\]', line_stripped)
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
    
    # 检测跨subgraph汇聚节点（来自多个不同subgraph的连接）
    # 这些节点应作为独立总结卡片，不放入任何subgraph
    cross_sg_sink_nodes = []
    for node_id, node in flowchart.all_nodes.items():
        if node.subgraph:  # 已分配到subgraph，跳过
            continue
        # 检查该节点的所有入边来源
        incoming_sources = []
        for from_id, to_id in flowchart.all_connections:
            if to_id == node_id:
                source_node = flowchart.all_nodes.get(from_id)
                if source_node and source_node.subgraph:
                    incoming_sources.append(source_node.subgraph)
        # 如果来自多个不同subgraph，标记为跨subgraph汇聚节点
        unique_sources = set(incoming_sources)
        if len(unique_sources) >= 2:
            cross_sg_sink_nodes.append(node)
    
    # 其他未分配节点（非跨subgraph汇聚）：放入最后一个subgraph
    unassigned_nodes = [n for n in flowchart.all_nodes.values() 
                        if not n.subgraph and n not in cross_sg_sink_nodes]
    if unassigned_nodes and flowchart.subgraphs:
        last_sg = flowchart.subgraphs[-1]
        for node in unassigned_nodes:
            node.subgraph = last_sg.id
            last_sg.nodes.append(node)
    
    # 存储跨subgraph汇聚节点，供渲染时使用
    flowchart.cross_sg_sink_nodes = cross_sg_sink_nodes
    
    # 如果没有 subgraph，创建一个默认的
    if not flowchart.subgraphs and flowchart.all_nodes:
        default_sg = Subgraph(id="default", title=flowchart.title)
        for node in flowchart.all_nodes.values():
            node.subgraph = "default"
            default_sg.nodes.append(node)
        flowchart.subgraphs.append(default_sg)
    
    return flowchart


def detect_lr_scene_type(flowchart: Flowchart) -> str:
    """
    检测 LR 流程图的场景类型
    
    返回:
        'timeline' - 时间线（节点含年月日等时间标记）
        'process' - 流程步骤（单线连接，操作/分析类节点）
        'comparison' - 对比分析（分叉后汇聚结构）
        'linear' - 线性递进（默认，无特殊特征）
    """
    import re
    
    # 时间关键词模式
    time_patterns = [
        r'\d{4}年', r'\d{4}',  # 2020年, 2020
        r'\d{2}/\d{2}', r'\d{4}/\d{2}',  # 03/15, 2020/03
        r'\d{2}\.\d{2}', r'\d{4}\.\d{2}',  # 03.15, 2020.03
        r'Q[1-4]', r'第[一二三四]季度',  # Q1, 第一季度
        r'H[1-2]', r'上半年|下半年',  # H1, 上半年
        r'[一二三四]月', r'\d{1,2}月',  # 一月, 3月
        r'过去|现在|未来|初期|中期|后期|起步|发展|成熟',
    ]
    
    # 流程/操作关键词
    process_keywords = [
        '分析', '处理', '计算', '评估', '审核', '审批',
        '收集', '整理', '汇总', '统计', '筛选',
        '输入', '输出', '导入', '导出', '上传', '下载',
        '步骤', '流程', '阶段', '环节',
    ]
    
    # 收集所有节点标题 - 优先从 subgraphs 获取完整节点信息
    all_titles = []
    for sg in flowchart.subgraphs:
        for node in sg.nodes:
            # title + desc 组合
            node_text = node.title
            if node.desc:
                node_text += ' ' + node.desc
            all_titles.append(node_text)
    
    # 如果 subgraphs 为空，从 all_nodes 获取
    if not all_titles:
        all_titles = [n.title for n in flowchart.all_nodes.values()]
    
    # 补充：如果标题只是 ID（A、B 等），从原始连接中提取标签
    if all_titles and all(len(t) <= 2 and t.isalpha() for t in all_titles):
        # 从 flowchart 原始连接提取标签文本
        for conn in flowchart.all_connections:
            for node_id in conn:
                if node_id in flowchart.all_nodes:
                    node = flowchart.all_nodes[node_id]
                    if hasattr(node, 'label') and node.label:
                        all_titles.append(node.label)
    
    # 最后手段：检查 flowchart 是否有原始文本
    if hasattr(flowchart, 'raw_text') and flowchart.raw_text:
        # 从原始文本提取 [标签] 内容
        import re
        labels = re.findall(r'\[([^\]]+)\]', flowchart.raw_text)
        all_titles.extend(labels)
    
    combined_titles = ' '.join(all_titles)
    
    # 1. 检测时间线特征
    time_matches = 0
    for pattern in time_patterns:
        matches = re.findall(pattern, combined_titles)
        time_matches += len(matches)
    
    # 如果超过一半节点含时间标记 → 时间线
    if time_matches >= len(all_titles) * 0.5:
        return 'timeline'
    
    # 2. 检测对比特征（分叉后汇聚）
    # 统计每个节点的入边和出边数量
    in_degree = {}
    out_degree = {}
    
    for node_id in flowchart.all_nodes:
        in_degree[node_id] = 0
        out_degree[node_id] = 0
    
    for from_id, to_id in flowchart.all_connections:
        out_degree[from_id] = out_degree.get(from_id, 0) + 1
        in_degree[to_id] = in_degree.get(to_id, 0) + 1
    
    # 找分叉点（出边>=2）和汇聚点（入边>=2且来自不同来源）
    fork_nodes = [n for n, deg in out_degree.items() if deg >= 2]
    sink_nodes = [n for n, deg in in_degree.items() if deg >= 2]
    
    # 如果有分叉且有汇聚 → 对比
    if len(fork_nodes) >= 1 and len(sink_nodes) >= 1:
        return 'comparison'
    
    # 3. 检测流程特征
    process_matches = sum(1 for title in all_titles 
                          if any(kw in title for kw in process_keywords))
    
    # 如果超过30%节点含流程关键词 → 流程
    if process_matches >= len(all_titles) * 0.3:
        return 'process'
    
    # 4. 默认为线性递进
    return 'linear'


def analyze_hierarchical_structure(nodes: List[Node], connections: List[Tuple[str, str]]) -> List[List[Node]]:
    """
    分析层级结构，使用链路追踪方法
    
    从每个根节点（无入边的节点）开始，追踪完整链路
    支持多层级链：A→B→C→D
    支持分叉：A→B, A→C（形成多条链路）
    
    返回: 链路列表，每条链路是节点列表（按连接顺序）
    """
    node_ids = [n.id for n in nodes]
    node_map = {n.id: n for n in nodes}
    
    # 找出 subgraph 内的连接
    sg_connections = [(from_id, to_id) for from_id, to_id in connections 
                      if from_id in node_ids and to_id in node_ids]
    
    # 构建父子关系映射
    parent_to_children: Dict[str, List[str]] = {}
    child_to_parent: Dict[str, str] = {}
    
    for from_id, to_id in sg_connections:
        if from_id not in parent_to_children:
            parent_to_children[from_id] = []
        parent_to_children[from_id].append(to_id)
        child_to_parent[to_id] = from_id
    
    # 找出根节点（没有父节点的节点）
    root_nodes = [n for n in nodes if n.id not in child_to_parent]
    
    # 找出孤立节点（既没有父节点也没有子节点）
    orphan_nodes = [n for n in nodes if n.id not in parent_to_children and n.id not in child_to_parent]
    
    chains = []
    used_nodes = set()
    
    # 从每个根节点追踪链路（支持分叉成多条链）
    for root in root_nodes:
        if root.id in used_nodes:
            continue
        
        # BFS追踪：从根节点开始，每个子节点形成新链
        # 使用队列：(当前节点, 当前链路)
        queue = [(root.id, [root])]
        used_nodes.add(root.id)
        
        while queue:
            current_id, current_chain = queue.pop(0)
            
            children = parent_to_children.get(current_id, [])
            
            if not children:
                # 叶子节点，链路结束
                chains.append(current_chain)
            else:
                # 有子节点，继续追踪
                for child_id in children:
                    if child_id in used_nodes:
                        # 子节点已被其他链使用，当前链结束
                        chains.append(current_chain)
                    else:
                        child_node = node_map.get(child_id)
                        if child_node:
                            new_chain = current_chain + [child_node]
                            used_nodes.add(child_id)
                            queue.append((child_id, new_chain))
    
    # 处理孤立节点
    for orphan in orphan_nodes:
        if orphan.id not in used_nodes:
            chains.append([orphan])
            used_nodes.add(orphan.id)
    
    # 处理未被追踪的节点（可能是中间节点被跳过）
    for node in nodes:
        if node.id not in used_nodes:
            chains.append([node])
            used_nodes.add(node.id)
    
    return chains


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
    
    注意: 当前已禁用所有 icon 显示，始终返回空字符串
    """
    # 禁用所有 icon 显示
    return ""
    
    # 以下代码保留但不会执行（方便以后恢复）
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


def generate_sketchy_arrow(direction='down', label='', is_sketchy=False, progress_index=0, total_nodes=1):
    """
    生成手绘风格箭头 SVG
    
    direction: 'down' (向下), 'right' (向右), 'wavy' (波浪)
    label: 头旁边的简短关系词
    is_sketchy: 是否使用手绘风格
    progress_index: 当前箭头在流程中的位置索引（0-based）
    total_nodes: 总节点数，用于计算渐变进度
    """
    # 渐变色阶：蓝 → 紫 → 红 → 橙（表示进度推进）
    gradient_colors = ['#3498DB', '#9B59B6', '#E74C3C', '#F39C12']
    
    # 计算当前箭头颜色
    if total_nodes > 1:
        # 根据进度位置选择颜色
        progress_ratio = progress_index / (total_nodes - 1)  # 0 → 1
        color_idx = min(int(progress_ratio * len(gradient_colors)), len(gradient_colors) - 1)
        arrow_color = gradient_colors[color_idx]
    else:
        arrow_color = gradient_colors[0]  # 默认蓝色
    
    if not is_sketchy:
        # 非手绘风格：简单字符箭头（带渐变颜色）
        if direction == 'down':
            return f'<div class="text-center text-xl" style="color:{arrow_color}">↓</div>'
        elif direction == 'right':
            return f'<div class="text-xl self-center" style="color:{arrow_color}">→</div>'
        else:
            return f'<div class="text-center text-xl" style="color:{arrow_color}">↓</div>'
    
    # 手绘风格：SVG 波浪箭头（带渐变颜色）
    if direction == 'down':
        svg = f'''<svg class="sketchy-arrow-svg" width="40" height="30" viewBox="0 0 40 30" style="display:block;margin:8px auto;">
          <path d="M20 5 Q15 10 20 15 Q25 20 20 25" stroke="{arrow_color}" stroke-width="2" fill="none" stroke-linecap="round"/>
          <path d="M15 22 L20 28 L25 22" stroke="{arrow_color}" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>'''
        if label:
            return f'<div class="text-center"><span class="sketchy-arrow-label text-xs" style="color:#6B6B6B;margin-bottom:4px;">{label}</span>{svg}</div>'
        return svg
    elif direction == 'right':
        return f'''<div class="flex items-center"><svg class="sketchy-arrow-svg" width="40" height="24" viewBox="0 0 40 24" style="display:block;">
          <path d="M5 12 Q10 8 15 12 Q20 16 25 12 Q30 8 35 12" stroke="{arrow_color}" stroke-width="2" fill="none" stroke-linecap="round"/>
          <path d="M32 8 L38 12 L32 16" stroke="{arrow_color}" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round"/>
        </svg></div>'''
    else:
        return f'''<svg class="sketchy-arrow-svg" width="40" height="30" viewBox="0 0 40 30" style="display:block;margin:8px auto;">
          <path d="M20 5 Q15 10 20 15 Q25 20 20 25" stroke="{arrow_color}" stroke-width="2" fill="none" stroke-linecap="round"/>
          <path d="M15 22 L20 28 L25 22" stroke="{arrow_color}" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>'''


def get_semantic_color(text: str, theme_config: dict) -> str:
    """
    根据文本内容语义返回对应的节点颜色类名
    
    参数:
        text: 节点标题/描述文本
        theme_config: 主题配置字典
    
    返回:
        节点颜色类名（如 'node-blue', 'node-mint' 等）或 None（使用默认轮换）
    """
    semantic_keywords = theme_config.get('semantic_keywords', {})
    if not semantic_keywords:
        return None
    
    text_lower = text.lower()
    
    # 技术类 -> 蓝色
    if any(kw in text for kw in semantic_keywords.get('tech', [])):
        return 'node-blue'
    
    # 增长类 -> 薄荷绿
    if any(kw in text for kw in semantic_keywords.get('growth', [])):
        return 'node-mint'
    
    # 概念类 -> 薰衣草紫
    if any(kw in text for kw in semantic_keywords.get('concept', [])):
        return 'node-lavender'
    
    # 警告类 -> 珊瑚红
    if any(kw in text for kw in semantic_keywords.get('warning', [])):
        return 'node-peach'
    
    return None


# 主题配置字典（多主题切换 v1.9）
THEMES = {
    'instagram': {
        'name': 'Instagram 风格',
        'background': 'linear-gradient(135deg, #833ab4 0%, #fd1d1d 50%, #fcb045 100%)',
        'watermark_color': 'rgba(255,255,255,0.06)',
        'card_base': 'linear-gradient(135deg, rgba(255,250,245,0.85) 0%, rgba(255,252,248,0.88) 50%, rgba(250,245,255,0.85) 100%)',
        'card_1': 'linear-gradient(135deg, rgba(250,245,255,0.82) 0%, rgba(255,250,245,0.85) 50%, rgba(255,245,250,0.82) 100%)',
        'card_2': 'linear-gradient(135deg, rgba(255,245,250,0.82) 0%, rgba(250,255,245,0.85) 50%, rgba(245,250,255,0.82) 100%)',
        'card_3': 'linear-gradient(135deg, rgba(245,250,255,0.82) 0%, rgba(250,245,255,0.85) 50%, rgba(255,250,245,0.82) 100%)',
        'card_4': 'linear-gradient(135deg, rgba(255,250,245,0.82) 0%, rgba(245,255,250,0.85) 50%, rgba(250,245,255,0.82) 100%)',
        'node_card': 'rgba(255,255,255,0.88)',
        'node_border': 'rgba(255,255,255,0.6)',
        'node_1': 'linear-gradient(135deg, #fef7f7 0%, #fce8e8 100%)',
        'node_2': 'linear-gradient(135deg, #fef9f3 0%, #fde9d9 100%)',
        'node_3': 'linear-gradient(135deg, #fef8f0 0%, #fde5cc 100%)',
        'node_4': 'linear-gradient(135deg, #f4fef7 0%, #dcf8e3 100%)',
        'node_5': 'linear-gradient(135deg, #f3f7fe 0%, #dce5f8 100%)',
        'node_6': 'linear-gradient(135deg, #f8f5fe 0%, #e8dcf8 100%)',
        'title_color': '#1a1a1a',
        'desc_color': '#3a3a3a',
        'icon_color': '#833ab4',
        'arrow_color': 'text-gray-400',
        'accent': '#833ab4',
    },
    'xiaohongshu': {
        'name': '小红书风格',
        'background': 'linear-gradient(135deg, #ff6b81 0%, #ff8a9b 40%, #ffc3d0 100%)',
        'watermark_color': 'rgba(255,255,255,0.08)',
        'card_base': 'linear-gradient(135deg, rgba(255,255,255,0.92) 0%, rgba(255,250,250,0.94) 50%, rgba(250,255,255,0.92) 100%)',
        'card_1': 'linear-gradient(135deg, rgba(255,245,250,0.9) 0%, rgba(255,250,255,0.92) 50%, rgba(255,255,250,0.9) 100%)',
        'card_2': 'linear-gradient(135deg, rgba(255,250,255,0.9) 0%, rgba(255,255,250,0.92) 50%, rgba(255,245,250,0.9) 100%)',
        'card_3': 'linear-gradient(135deg, rgba(255,255,250,0.9) 0%, rgba(255,245,250,0.92) 50%, rgba(250,255,255,0.9) 100%)',
        'card_4': 'linear-gradient(135deg, rgba(250,255,255,0.9) 0%, rgba(255,255,250,0.92) 50%, rgba(255,250,255,0.9) 100%)',
        'node_card': 'rgba(255,255,255,0.95)',
        'node_border': 'rgba(255,180,200,0.3)',
        'node_1': 'linear-gradient(135deg, #fff5f5 0%, #ffe8ec 100%)',
        'node_2': 'linear-gradient(135deg, #fff8f5 0%, #ffece8 100%)',
        'node_3': 'linear-gradient(135deg, #fffcf5 0%, #fff5ec 100%)',
        'node_4': 'linear-gradient(135deg, #f5fff8 0%, #e8ffec 100%)',
        'node_5': 'linear-gradient(135deg, #f5f8ff 0%, #e8ecff 100%)',
        'node_6': 'linear-gradient(135deg, #fff8f5 0%, #ffe8ec 100%)',
        'title_color': '#2d2d2d',
        'desc_color': '#5a5a5a',
        'icon_color': '#ff6b81',
        'arrow_color': 'text-pink-400',
        'accent': '#ff6b81',
    },
    'business': {
        'name': '商务简报风格',
        'background': 'linear-gradient(135deg, #1a365d 0%, #2c5282 50%, #3182ce 100%)',
        'watermark_color': 'rgba(255,255,255,0.05)',
        'card_base': 'linear-gradient(135deg, rgba(255,255,255,0.95) 0%, rgba(245,250,255,0.96) 50%, rgba(240,245,250,0.95) 100%)',
        'card_1': 'linear-gradient(135deg, rgba(245,250,255,0.92) 0%, rgba(240,248,255,0.94) 50%, rgba(235,245,255,0.92) 100%)',
        'card_2': 'linear-gradient(135deg, rgba(240,255,250,0.92) 0%, rgba(235,255,248,0.94) 50%, rgba(240,255,245,0.92) 100%)',
        'card_3': 'linear-gradient(135deg, rgba(255,250,245,0.92) 0%, rgba(255,248,240,0.94) 50%, rgba(255,245,235,0.92) 100%)',
        'card_4': 'linear-gradient(135deg, rgba(255,255,250,0.92) 0%, rgba(255,255,245,0.94) 50%, rgba(255,255,240,0.92) 100%)',
        'node_card': 'rgba(255,255,255,0.96)',
        'node_border': 'rgba(200,210,220,0.4)',
        'node_1': 'linear-gradient(135deg, #f0f5ff 0%, #e0e8f5 100%)',
        'node_2': 'linear-gradient(135deg, #f5f8ff 0%, #e8ecf5 100%)',
        'node_3': 'linear-gradient(135deg, #f8faff 0%, #ecf0f5 100%)',
        'node_4': 'linear-gradient(135deg, #f5fff5 0%, #e8f5e8 100%)',
        'node_5': 'linear-gradient(135deg, #fffaf5 0%, #f5eae0 100%)',
        'node_6': 'linear-gradient(135deg, #f5f0ff 0%, #e8e0f5 100%)',
        'title_color': '#1a365d',
        'desc_color': '#4a5568',
        'icon_color': '#2c5282',
        'arrow_color': 'text-blue-600',
        'accent': '#2c5282',
    },
    'darktech': {
        'name': '暗黑科技风格',
        'background': 'linear-gradient(135deg, #0d0d0d 0%, #1a1a2e 50%, #16213e 100%)',
        'watermark_color': 'rgba(100,100,150,0.08)',
        'card_base': 'linear-gradient(135deg, rgba(30,30,50,0.88) 0%, rgba(40,40,60,0.9) 50%, rgba(35,35,55,0.88) 100%)',
        'card_1': 'linear-gradient(135deg, rgba(35,35,55,0.85) 0%, rgba(45,45,65,0.88) 50%, rgba(40,40,60,0.85) 100%)',
        'card_2': 'linear-gradient(135deg, rgba(40,40,60,0.85) 0%, rgba(50,50,70,0.88) 50%, rgba(45,45,65,0.85) 100%)',
        'card_3': 'linear-gradient(135deg, rgba(45,45,65,0.85) 0%, rgba(55,55,75,0.88) 50%, rgba(50,50,70,0.85) 100%)',
        'card_4': 'linear-gradient(135deg, rgba(50,50,70,0.85) 0%, rgba(60,60,80,0.88) 50%, rgba(55,55,75,0.85) 100%)',
        'node_card': 'rgba(50,50,70,0.92)',
        'node_border': 'rgba(100,100,150,0.3)',
        'node_1': 'linear-gradient(135deg, #252545 0%, #353565 100%)',
        'node_2': 'linear-gradient(135deg, #303050 0%, #404060 100%)',
        'node_3': 'linear-gradient(135deg, #353555 0%, #454565 100%)',
        'node_4': 'linear-gradient(135deg, #2a3545 0%, #3a4555 100%)',
        'node_5': 'linear-gradient(135deg, #353050 0%, #454060 100%)',
        'node_6': 'linear-gradient(135deg, #302545 0%, #403555 100%)',
        'title_color': '#e0e0e8',
        'desc_color': '#a0a0b0',
        'icon_color': '#8b5cf6',
        'arrow_color': 'text-violet-400',
        'accent': '#8b5cf6',
    },
    'warm': {
        'name': '温暖柔和风格',
        'background': 'linear-gradient(135deg, #fef3c7 0%, #fcd9b8 50%, #fbbf24 100%)',
        'watermark_color': 'rgba(255,255,255,0.08)',
        'card_base': 'linear-gradient(135deg, rgba(255,255,255,0.92) 0%, rgba(255,250,245,0.94) 50%, rgba(255,245,240,0.92) 100%)',
        'card_1': 'linear-gradient(135deg, rgba(255,250,245,0.9) 0%, rgba(255,245,240,0.92) 50%, rgba(250,245,240,0.9) 100%)',
        'card_2': 'linear-gradient(135deg, rgba(255,245,240,0.9) 0%, rgba(250,240,245,0.92) 50%, rgba(245,240,250,0.9) 100%)',
        'card_3': 'linear-gradient(135deg, rgba(250,245,240,0.9) 0%, rgba(245,240,250,0.92) 50%, rgba(240,250,245,0.9) 100%)',
        'card_4': 'linear-gradient(135deg, rgba(245,250,240,0.9) 0%, rgba(240,255,245,0.92) 50%, rgba(250,255,240,0.9) 100%)',
        'node_card': 'rgba(255,255,255,0.95)',
        'node_border': 'rgba(250,200,150,0.3)',
        'node_1': 'linear-gradient(135deg, #fffaf5 0%, #fff0e5 100%)',
        'node_2': 'linear-gradient(135deg, #fff8f0 0%, #ffe8d8 100%)',
        'node_3': 'linear-gradient(135deg, #fff5eb 0%, #ffe5d5 100%)',
        'node_4': 'linear-gradient(135deg, #f5fff0 0%, #e8ffd8 100%)',
        'node_5': 'linear-gradient(135deg, #f0fff5 0%, #d8ffe8 100%)',
        'node_6': 'linear-gradient(135deg, #fff0f5 0%, #ffd8e8 100%)',
        'title_color': '#5a4030',
        'desc_color': '#7a6050',
        'icon_color': '#f59e0b',
        'arrow_color': 'text-amber-500',
        'accent': '#f59e0b',
    },
    'minimal': {
        'name': '极简黑白风格',
        'background': 'linear-gradient(135deg, #ffffff 0%, #f5f5f5 50%, #e8e8e8 100%)',
        'watermark_color': 'rgba(0,0,0,0.04)',
        'card_base': 'linear-gradient(135deg, rgba(255,255,255,0.98) 0%, rgba(250,250,250,0.99) 50%, rgba(245,245,245,0.98) 100%)',
        'card_1': 'linear-gradient(135deg, rgba(255,255,255,0.96) 0%, rgba(250,250,250,0.98) 50%, rgba(248,248,248,0.96) 100%)',
        'card_2': 'linear-gradient(135deg, rgba(250,250,255,0.96) 0%, rgba(248,248,255,0.98) 50%, rgba(245,245,255,0.96) 100%)',
        'card_3': 'linear-gradient(135deg, rgba(255,250,250,0.96) 0%, rgba(255,248,248,0.98) 50%, rgba(255,245,245,0.96) 100%)',
        'card_4': 'linear-gradient(135deg, rgba(250,255,250,0.96) 0%, rgba(248,255,248,0.98) 50%, rgba(245,255,245,0.96) 100%)',
        'node_card': 'rgba(255,255,255,0.98)',
        'node_border': 'rgba(0,0,0,0.08)',
        'node_1': 'linear-gradient(135deg, #ffffff 0%, #f8f8f8 100%)',
        'node_2': 'linear-gradient(135deg, #f8f8f8 0%, #f0f0f0 100%)',
        'node_3': 'linear-gradient(135deg, #f0f0f0 0%, #e8e8e8 100%)',
        'node_4': 'linear-gradient(135deg, #f5f5f5 0%, #ebebeb 100%)',
        'node_5': 'linear-gradient(135deg, #fafafa 0%, #f5f5f5 100%)',
        'node_6': 'linear-gradient(135deg, #f8f8f8 0%, #f2f2f2 100%)',
        'title_color': '#1a1a1a',
        'desc_color': '#4a4a4a',
        'icon_color': '#404040',
        'arrow_color': 'text-gray-500',
        'accent': '#404040',
    },
    # 手绘风教育插画风格 - 基于 sketch-notes + macaron 规范
    'hand-drawn-edu': {
        'name': '手绘风教育插画',
        # 暖奶油背景 + 微妙纸张纹理（SVG pattern）
        'background': '#F5F0E8',
        'background_texture': True,  # 启用纸张纹理
        'watermark_color': 'rgba(45,45,45,0.06)',
        # 卡片：纯白 + 手绘边框（无模糊）
        'card_base': '#FFFFFF',
        'card_1': '#FFFFFF',
        'card_2': '#FFFFFF',
        'card_3': '#FFFFFF',
        'card_4': '#FFFFFF',
        'card_border': '2px solid #2C3E50',  # 手绘边框
        'card_border_radius': '12px',
        # 节点：马卡龙色系（语义编码）
        'node_card': '#FFFFFF',
        'node_border': '2px solid #2C3E50',
        # 语义颜色：技术蓝、增长绿、概念紫、温暖桃
        'node_blue': '#A8D8EA',      # 技术/信息类
        'node_mint': '#B5E5CF',      # 增长/正向类
        'node_lavender': '#D5C6E0',  # 概念/抽象类
        'node_peach': '#FFD5C2',     # 温暖类
        'node_1': '#A8D8EA',         # 默认轮换
        'node_2': '#B5E5CF',
        'node_3': '#D5C6E0',
        'node_4': '#FFD5C2',
        'node_5': '#A8D8EA',
        'node_6': '#B5E5CF',
        # 文字颜色
        'title_color': '#2D2D2D',    # 深炭灰
        'desc_color': '#6B6B6B',     # 暖灰（辅助标注）
        'icon_color': '#E8655A',     # 珊瑚红（强调色）
        'arrow_color': '#2C3E50',    # 手绘箭头颜色
        'accent': '#E8655A',         # 场景样式强调色
        # 手绘特效
        'sketchy_filter': True,      # 启用手绘抖动
        'hand_drawn_border': True,   # 启用不规则边框
        'is_sketchy': True,          # 启用手绘风格箭头
        # 颜色语义编码关键词映射
        'semantic_keywords': {
            'tech': ['技术', '芯片', '算法', '系统', '软件', 'AI', '智能', '数据', '云计算'],
            'growth': ['增长', '收入', '利润', '上升', '扩张', '投资', '融资', '市场'],
            'concept': ['概念', '模式', '框架', '逻辑', '理念', '思维', '方法'],
            'warning': ['风险', '挑战', '竞争', '压力', '下滑', '亏损'],
        },
    },
}


def generate_html(flowchart: Flowchart, theme: str = 'hand-drawn-edu') -> str:
    """
    生成指定主题风格的 HTML
    theme: instagram, xiaohongshu, business, darktech, warm, minimal
    """
    
    # 获取主题配置
    t = THEMES.get(theme, THEMES['instagram'])
    
    # LR 模式场景检测
    lr_scene_type = None
    if flowchart.direction == 'LR':
        lr_scene_type = detect_lr_scene_type(flowchart)
    
    # 节点配色类
    node_colors = ['node-1', 'node-2', 'node-3', 'node-4', 'node-5', 'node-6']
    
    # 卡片配色类
    card_colors = ['card-1', 'card-2', 'card-3', 'card-4']
    
    html_parts = []
    
    # 检测是否是手绘风格主题
    is_sketchy = theme == 'hand-drawn-edu'
    
    # 手绘风格特殊样式
    sketchy_css = ''
    if is_sketchy:
        sketchy_css = '''
    /* 手绘抖动 SVG filter */
    .sketchy-filter { filter: url(#sketchy); }
    /* 手绘边框 - 使用 SVG stroke-dasharray 模拟不规则 */
    .hand-drawn-border {
      border: 2px solid #2C3E50;
      border-radius: 8px 12px 10px 14px;
      box-shadow: 2px 3px 0 rgba(44,62,80,0.15);
    }
    /* 马卡龙色块不完全填满 - 留白边 */
    .macaron-fill {
      background-size: 95% 95%;
      background-position: center;
    }
    /* 手绘箭头 */
    .sketchy-arrow {
      stroke: #2C3E50;
      stroke-width: 2;
      fill: none;
      stroke-linecap: round;
      stroke-linejoin: round;
    }
    /* 涂鸦装饰 */
    .doodle-star { color: #E8655A; opacity: 0.6; }
    .doodle-underline {
      border-bottom: 2px wavy #E8655A;
      opacity: 0.5;
    }
'''
    
    # HTML 头部 - 使用主题样式
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
      background: ''' + (t['background'] if t.get('background_texture', False) else t['background']) + ''';
      padding-bottom: 20px;
}''' + ('''
    /* 纸张纹理 */
    body::before {
      content: "";
      position: fixed;
      top: 0; left: 0; right: 0; bottom: 0;
      background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 200 200' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noise'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.8' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noise)' opacity='0.08'/%3E%3C/svg%3E");
      pointer-events: none;
      z-index: 0;
    }''' if t.get('background_texture', False) else '') + '''
    /* SVG水印层 - 自动重复铺满 */
    .watermark-svg {
      position: absolute; top: 0; left: 0; width: 100%; height: 100%;
      pointer-events: none; z-index: 100;
    }
    .content-wrapper {
      position: relative;
      min-height: fit-content;
    }
    .card {
      background: ''' + t['card_base'] + ''';
      ''' + ('''border: 2px solid #2C3E50;
      border-radius: 12px 16px 14px 18px;
      box-shadow: 3px 4px 0 rgba(44,62,80,0.2);''' if is_sketchy else '''backdrop-filter: blur(16px); -webkit-backdrop-filter: blur(16px);
      border-radius: 16px;
      box-shadow: 0 8px 32px rgba(0,0,0,0.12);
      border: 1px solid ''' + t['node_border']) + ''';
    }
    .card-1 { background: ''' + t['card_1'] + '''; }
    .card-2 { background: ''' + t['card_2'] + '''; }
    .card-3 { background: ''' + t['card_3'] + '''; }
    .card-4 { background: ''' + t['card_4'] + '''; }
    .node-card {
      background: ''' + t['node_card'] + ''';
      ''' + ('''border: 2px solid #2C3E50;
      border-radius: 8px 12px 10px 14px;
      box-shadow: 2px 3px 0 rgba(44,62,80,0.15);''' if is_sketchy else '''border-radius: 12px;
      box-shadow: 0 3px 12px rgba(0,0,0,0.08);
      border: 1px solid ''' + t['node_border']) + ''';
    }
    .section-title { font-size: 24px; font-weight: 700; color: ''' + t['title_color'] + '''; margin-bottom: 14px; text-align: center; ''' + ('''text-shadow: 1px 1px 0 rgba(44,62,80,0.1);''' if is_sketchy else '') + '''}
    .node-title { font-size: 19px; font-weight: 600; color: ''' + t['title_color'] + '''; line-height: 1.4; }
    .node-desc { font-size: 15px; font-weight: 400; color: ''' + t['desc_color'] + '''; line-height: 1.5; margin-top: 6px; }
    .node-icon { color: ''' + t['icon_color'] + '''; opacity: 0.85; margin-bottom: 8px; }
    /* Timeline 场景样式 */
    .timeline-node { position: relative; padding-left: 32px; }
    .timeline-node::before {
      content: '';
      position: absolute;
      left: 12px;
      top: 0;
      bottom: 0;
      width: 2px;
      background: linear-gradient(to bottom, ''' + t['card_1'] + ''', ''' + t['card_2'] + ''');
    }
    .timeline-node::after {
      content: '';
      position: absolute;
      left: 6px;
      top: 24px;
      width: 14px;
      height: 14px;
      border-radius: 50%;
      background: ''' + t['accent'] + ''';
      border: 3px solid ''' + t['node_border'] + ''';
    }
    /* LR 横向时间线样式 */
    .lr-timeline-card {
      position: relative;
      padding-top: 24px;
      border-radius: 12px;
      background: linear-gradient(135deg, ''' + t['card_1'] + ''' 0%, ''' + t['card_2'] + ''' 100%);
    }
    .lr-timeline-card::before {
      content: '';
      position: absolute;
      top: 8px;
      left: 50%;
      transform: translateX(-50%);
      width: 16px;
      height: 16px;
      border-radius: 50%;
      background: ''' + t['accent'] + ''';
      border: 3px solid ''' + t['node_border'] + ''';
      z-index: 2;
      box-shadow: 0 2px 8px rgba(0,0,0,0.15);
    }
    .lr-timeline-label {
      position: absolute;
      top: -10px;
      left: 50%;
      transform: translateX(-50%);
      font-size: 14px;
      font-weight: 700;
      color: ''' + t['accent'] + ''';
      white-space: nowrap;
      background: ''' + t.get('bg', '#FFFFFF') + ''';
      padding: 2px 8px;
      border-radius: 4px;
    }
    /* 时间线描述区域 */
    .lr-timeline-desc {
      font-size: 13px;
      color: ''' + t['desc_color'] + ''';
      margin-top: 4px;
      line-height: 1.4;
    }
    /* Process 场景样式 */
    .process-step { position: relative; }
    .process-step .step-number {
      position: absolute;
      top: -8px;
      left: -8px;
      width: 28px;
      height: 28px;
      border-radius: 50%;
      background: ''' + t['accent'] + ''';
      color: white;
      font-weight: 700;
      font-size: 14px;
      display: flex;
      align-items: center;
      justify-content: center;
    }
    /* LR 里程碑样式 - 大编号 */
    .lr-milestone-card {
      position: relative;
      padding: 24px;
      padding-left: 64px;
      border-left: 4px solid ''' + t['accent'] + ''';
      background: linear-gradient(135deg, ''' + t['card_1'] + ''' 0%, ''' + t['card_2'] + ''' 100%);
    }
    .lr-milestone-number {
      position: absolute;
      left: 16px;
      top: 50%;
      transform: translateY(-50%);
      width: 36px;
      height: 36px;
      border-radius: 50%;
      background: linear-gradient(135deg, ''' + t['accent'] + ''' 0%, ''' + t['node_border'] + ''' 100%);
      color: white;
      font-size: 18px;
      font-weight: 800;
      display: flex;
      align-items: center;
      justify-content: center;
      box-shadow: 0 4px 12px rgba(0,0,0,0.15);
    }
    /* Comparison 场景样式 */
    .comparison-node { border-width: 2px; }
    .comparison-pro { border-color: #10B981; background: rgba(16, 185, 129, 0.08); }
    .comparison-con { border-color: #EF4444; background: rgba(239, 68, 68, 0.08); }
    .node-1 { background: ''' + t['node_1'] + '''; }
    .node-2 { background: ''' + t['node_2'] + '''; }
    .node-3 { background: ''' + t['node_3'] + '''; }
    .node-4 { background: ''' + t['node_4'] + '''; }
    .node-5 { background: ''' + t['node_5'] + '''; }
    .node-6 { background: ''' + t['node_6'] + '''; }
    /* 语义颜色类（手绘风格专用） */
    .node-blue { background: ''' + t.get('node_blue', t['node_1']) + '''; }
    .node-mint { background: ''' + t.get('node_mint', t['node_2']) + '''; }
    .node-lavender { background: ''' + t.get('node_lavender', t['node_3']) + '''; }
    .node-peach { background: ''' + t.get('node_peach', t['node_4']) + '''; }
    /* 主题箭头颜色 */
    .arrow-color { color: ''' + t['arrow_color'] + '''; opacity: 0.7; }
    ''' + sketchy_css + '''
    /* LR 多行布局样式 */
    .lr-row {
      display: flex;
      gap: 16px;
      align-items: flex-start;
      justify-content: flex-start;
      flex-wrap: wrap;
    }
    .lr-card {
      min-width: 320px;
      /* 不限制 max-width，让卡片自适应内容 */
    }
    .lr-row-arrow {
      width: 100%;
      display: flex;
      justify-content: center;
      padding: 12px 0;
    }
  </style>
</head>
<body class="p-5">
  <div class="content-wrapper">
    <!-- SVG defs for sketchy filter -->
    ''' + ('''<svg style="position:absolute;width:0;height:0;" xmlns="http://www.w3.org/2000/svg">
      <defs>
        <filter id="sketchy">
          <feTurbulence type="fractalNoise" baseFrequency="0.02" numOctaves="3" result="noise"/>
          <feDisplacementMap in="SourceGraphic" in2="noise" scale="1" xChannelSelector="R" yChannelSelector="G"/>
        </filter>
      </defs>
    </svg>''' if is_sketchy else '') + '''
    <svg class="watermark-svg" xmlns="http://www.w3.org/2000/svg">
      <defs>
        <pattern id="watermark-pattern" patternUnits="userSpaceOnUse" width="450" height="300" patternTransform="rotate(-20)">
          <text x="30" y="150" font-size="60" font-weight="700" fill="''' + t['watermark_color'] + '''" font-family="'Noto Sans SC', 'PingFang SC', sans-serif">''' + flowchart.watermark + '''</text>
        </pattern>
      </defs>
      <rect width="100%" height="100%" fill="url(#watermark-pattern)"/>
    </svg>
    ''' + ('''<!-- LR 横向布局容器 - 不限制宽度 -->
    <div class="relative z-10" style="width: 100%" id="content">''' if flowchart.direction == 'LR' else '''<div class="relative z-10 mx-auto space-y-5" style="max-width: 800px" id="content">''') + '''
''')
    
    # 生成每个 subgraph 的卡片
    for idx, sg in enumerate(flowchart.subgraphs):
        card_class = card_colors[idx % len(card_colors)]
        
        # 分析节点连接关系
        node_ids = [n.id for n in sg.nodes]
        node_map = {n.id: n for n in sg.nodes}
        
        # 找出 subgraph 内的连接
        sg_connections = [(from_id, to_id) for from_id, to_id in flowchart.all_connections 
                          if from_id in node_ids and to_id in node_ids]
        
        # 构建父子关系映射
        parent_to_children: Dict[str, List[str]] = {}
        child_to_parent: Dict[str, str] = {}
        for from_id, to_id in sg_connections:
            if from_id not in parent_to_children:
                parent_to_children[from_id] = []
            parent_to_children[from_id].append(to_id)
            child_to_parent[to_id] = from_id
        
        # 找出分叉节点（有多个子节点的节点）
        fork_nodes = [n for n in sg.nodes if len(parent_to_children.get(n.id, [])) >= 2]
        
        # 找出孤立节点（无连接）
        orphan_nodes = [n for n in sg.nodes if n.id not in parent_to_children and n.id not in child_to_parent]
        
        # 检测是否是"终端应用"类型：
        # 1. 全是孤立节点，节点数>=4
        # 2. 或者：只有1个孤立节点，但节点内容有多行（换行分隔>=3行）
        is_terminal_style = False
        terminal_items = []
        
        if len(orphan_nodes) >= 4 and len(sg_connections) == 0:
            is_terminal_style = True
            terminal_items = [(n.title, n.desc, n.icon) for n in orphan_nodes]
        elif len(orphan_nodes) == 1 and len(sg.nodes) == 1:
            # 单节点多行内容：拆分成小方块
            single_node = orphan_nodes[0]
            # 检查title或desc是否有多行
            all_content = (single_node.title + '\n' + (single_node.desc or '')).strip()
            lines = [l.strip() for l in all_content.split('\n') if l.strip()]
            if len(lines) >= 3:
                is_terminal_style = True
                # 每项根据标题关键词自动匹配emoji
                terminal_items = []
                for line in lines:
                    matched_icon = auto_match_emoji(line)
                    terminal_items.append((line, '', matched_icon))
        
        # 检测是否有分叉结构
        has_fork = len(fork_nodes) > 0
        
        # 检测是否有多条独立分支（链路之间无连接）
        # 两种情况：
        # 1. 多个独立分叉：每个分叉节点及其子节点形成独立分支
        # 2. 多个独立线性链路：无分叉，但有多个根节点
        independent_branches = []
        has_parallel_branches = False
        
        if has_fork and len(fork_nodes) >= 2:
            # 检测是否是"多个独立分叉"：分叉节点之间无连接
            fork_ids = [f.id for f in fork_nodes]
            forks_connected = False
            for from_id, to_id in sg_connections:
                if from_id in fork_ids and to_id in fork_ids:
                    forks_connected = True
                    break
            
            if not forks_connected:
                # 每个分叉节点及其所有子节点（含子节点的子节点）形成独立分支
                used_in_branch = set()
                for fork in fork_nodes:
                    if fork.id in used_in_branch:
                        continue
                    branch_nodes = [fork]
                    used_in_branch.add(fork.id)
                    # 收集所有子节点（递归）
                    children_ids = parent_to_children.get(fork.id, [])
                    for child_id in children_ids:
                        if child_id not in used_in_branch:
                            child_node = node_map.get(child_id)
                            if child_node:
                                branch_nodes.append(child_node)
                                used_in_branch.add(child_id)
                            # 继续收集子节点的子节点
                            sub_children_ids = parent_to_children.get(child_id, [])
                            for sub_child_id in sub_children_ids:
                                if sub_child_id not in used_in_branch:
                                    sub_child_node = node_map.get(sub_child_id)
                                    if sub_child_node:
                                        branch_nodes.append(sub_child_node)
                                        used_in_branch.add(sub_child_id)
                    
                    independent_branches.append(branch_nodes)
                
                if len(independent_branches) >= 2:
                    has_parallel_branches = True
        
        elif not has_fork and len(sg_connections) > 0:
            # 无分叉，但有多个根节点 → 多条独立线性链路
            root_ids = [n.id for n in sg.nodes if n.id not in child_to_parent]
            used_in_branch = set()
            for root_id in root_ids:
                if root_id in used_in_branch:
                    continue
                branch_nodes = []
                current_id = root_id
                while current_id:
                    if current_id in used_in_branch:
                        break
                    node = node_map.get(current_id)
                    if node:
                        branch_nodes.append(node)
                        used_in_branch.add(current_id)
                    children = parent_to_children.get(current_id, [])
                    current_id = children[0] if children else None
                
                if branch_nodes:
                    independent_branches.append(branch_nodes)
            
            if len(independent_branches) >= 2:
                has_parallel_branches = True
        
        nodes_html = ''
        
        # LR模式：节点横向排列，真正实现 Left-Right
        if flowchart.direction == 'LR':
            import re
            
            # 横向 flex 布局，节点并排，超出时换行
            nodes_html = '<div class="flex gap-5 items-stretch flex-1 flex-wrap">'
            
            for node_idx, node in enumerate(sg.nodes):
                node_class = node_colors[node_idx % len(node_colors)]
                
                title_br = node.title.replace('\n', '<br>')
                desc_br = node.desc.replace('\n', '<br>') if node.desc else ''
                desc_html = f'<div class="node-desc">{desc_br}</div>' if desc_br else ''
                icon_html = icon_to_html(node.icon) if node.icon else ''
                icon_div = f'<div class="node-icon text-xl mb-1">{icon_html}</div>' if icon_html else ''
                
                # 根据场景选择不同的节点设计
                if lr_scene_type == 'timeline':
                    # 时间线样式：顶部时间标签 + 圆点装饰
                    time_match = re.search(r'(\d{4}年|\d{4}|\d+月|\d{2}/\d{2})', title_br)
                    time_label = time_match.group(1) if time_match else ''
                    
                    # 提取事件描述（去掉时间部分）
                    event_text = title_br.replace(time_label, '').strip() if time_label else title_br
                    
                    nodes_html += f'''
                    <div class="node-card {node_class} lr-timeline-card p-5 text-center min-w-[200px] max-w-[280px] relative">
                      <div class="lr-timeline-label">{time_label}</div>
                      {icon_div}<div class="node-title text-lg font-semibold">{event_text}</div>
                      {desc_html}
                    </div>'''
                    
                elif lr_scene_type == 'process':
                    # 里程碑样式：大编号 + 标题
                    nodes_html += f'''
                    <div class="node-card {node_class} lr-milestone-card p-6 text-left min-w-[220px] max-w-[300px] relative">
                      <div class="lr-milestone-number">{node_idx + 1}</div>
                      {icon_div}<div class="node-title text-xl font-semibold">{title_br}</div>
                      {desc_html}
                    </div>'''
                    
                elif lr_scene_type == 'comparison':
                    # 对比样式：pro/con 颜色区分
                    scene_class = 'comparison-node'
                    title_lower = title_br.lower()
                    if any(kw in title_lower for kw in ['多', '利好', '优势', '正面', '看涨', 'bull', '买入', '增持']):
                        scene_class += ' comparison-pro'
                    elif any(kw in title_lower for kw in ['空', '利空', '风险', '劣势', '负面', '看跌', 'bear', '卖出', '减持']):
                        scene_class += ' comparison-con'
                    
                    nodes_html += f'''
                    <div class="node-card {node_class} {scene_class} p-6 text-center min-w-[200px] max-w-[280px]">
                      {icon_div}<div class="node-title text-xl font-semibold">{title_br}</div>
                      {desc_html}
                    </div>'''
                    
                else:
                    # 默认线性样式：标准卡片
                    nodes_html += f'''
                    <div class="node-card {node_class} p-6 text-center min-w-[200px] max-w-[280px]">
                      {icon_div}<div class="node-title text-xl font-semibold">{title_br}</div>
                      {desc_html}
                    </div>'''
                
                # 节点之间添加向右箭头（横向，带渐变色）
                if node_idx < len(sg.nodes) - 1:
                    nodes_html += generate_sketchy_arrow('right', '', is_sketchy, 
                                                         progress_index=node_idx, 
                                                         total_nodes=len(sg.nodes))
            
            nodes_html += '</div>'
        
        elif has_parallel_branches:
            # 多分支并排卡片布局：每个分叉节点一个卡片，父节点顶部，子节点并列下方
            # 分支数>=4时用grid布局（2行2列），否则用flex横向排列
            if len(independent_branches) >= 4:
                nodes_html = '<div class="grid grid-cols-2 gap-4">'
            else:
                nodes_html = '<div class="flex gap-4 items-stretch">'
            
            for branch_idx, branch in enumerate(independent_branches):
                # 每个分支一个小卡片
                branch_card_class = card_colors[branch_idx % len(card_colors)]
                nodes_html += f'<div class="card {branch_card_class} p-4 flex-1">'
                
                # 分支内：父节点 → 箭头 → 子节点并列
                nodes_html += '<div class="space-y-3">'
                
                # 找出分支中的父节点（第一个节点，有子节点）和子节点
                parent_node = branch[0] if branch else None
                child_nodes = branch[1:] if len(branch) > 1 else []
                
                # 渲染父节点
                if parent_node:
                    node_class = node_colors[branch_idx % len(node_colors)]
                    title_br = parent_node.title.replace('\n', '<br>')
                    desc_br = parent_node.desc.replace('\n', '<br>') if parent_node.desc else ''
                    desc_html = f'<div class="node-desc text-sm">{desc_br}</div>' if desc_br else ''
                    icon_html = icon_to_html(parent_node.icon) if parent_node.icon else ''
                    icon_div = f'<div class="node-icon text-lg mb-1">{icon_html}</div>' if icon_html else ''
                    
                    nodes_html += f'''
                    <div class="node-card {node_class} p-3 text-center">
                      {icon_div}<div class="node-title text-base">{title_br}</div>
                      {desc_html}
                    </div>'''
                
                # 箭头
                if child_nodes:
                    nodes_html += generate_sketchy_arrow('down', '', is_sketchy)
                    
                    # 子节点并列
                    nodes_html += '<div class="flex gap-2 justify-center">'
                    for child_idx, child_node in enumerate(child_nodes):
                        node_class = node_colors[(branch_idx + child_idx + 1) % len(node_colors)]
                        title_br = child_node.title.replace('\n', '<br>')
                        desc_br = child_node.desc.replace('\n', '<br>') if child_node.desc else ''
                        desc_html = f'<div class="node-desc text-xs">{desc_br}</div>' if desc_br else ''
                        # 三级节点不显示icon
                        icon_div = ''

                        nodes_html += f'''
                        <div class="node-card {node_class} p-2 text-center" style="min-width: 80px;">
                          <div class="node-title text-sm">{title_br}</div>
                          {desc_html}
                        </div>'''
                    nodes_html += '</div>'
                
                nodes_html += '</div></div>'
            
            nodes_html += '</div>'
        
        elif is_terminal_style:
            # 终端应用布局：所有项用小方块并排
            # 检查是否需要渲染描述（如果有desc非空）
            has_desc = any(desc for _, desc, _ in terminal_items)
            
            nodes_html = '<div class="flex gap-3 justify-center flex-wrap">'
            for n_idx, (title, desc, icon) in enumerate(terminal_items):
                node_class = node_colors[n_idx % len(node_colors)]
                title_br = title.replace('\n', '<br>')
                desc_br = desc.replace('\n', '<br>') if desc else ''
                desc_html = f'<div class="node-desc text-sm">{desc_br}</div>' if desc_br else ''
                icon_html = icon_to_html(icon) if icon else ''
                icon_div = f'<div class="node-icon text-lg mb-1">{icon_html}</div>' if icon_html else ''
                # 有描述时增加内边距
                padding = 'p-4' if has_desc else 'p-3'
                nodes_html += f'''
                <div class="node-card {node_class} {padding} text-center" style="min-width: 140px;">
                  {icon_div}<div class="node-title text-base">{title_br}</div>
                  {desc_html}
                </div>'''
            nodes_html += '</div>'
        
        elif has_fork:
            # 分叉结构布局：父节点大块 + 箭头 + 子节点并排小方块
            nodes_html = '<div class="space-y-4">'
            
            rendered_nodes = set()
            
            # 找出完全孤立的节点（没有任何连接，应该和父节点并列）
            fully_orphan_nodes = [n for n in orphan_nodes 
                                  if n.id not in parent_to_children and n.id not in child_to_parent]
            
            for fork_idx, fork in enumerate(fork_nodes):
                if fork.id in rendered_nodes:
                    continue
                
                # 第一行：父节点 + 孤立节点并列显示
                if fork_idx == 0 and fully_orphan_nodes:
                    # 父节点和孤立节点并列
                    nodes_html += '<div class="flex gap-3 justify-center flex-wrap">'
                    
                    # 渲染父节点
                    node_class = node_colors[0]
                    title_br = fork.title.replace('\n', '<br>')
                    desc_br = fork.desc.replace('\n', '<br>') if fork.desc else ''
                    desc_html = f'<div class="node-desc text-sm">{desc_br}</div>' if desc_br else ''
                    icon_html = icon_to_html(fork.icon) if fork.icon else ''
                    icon_div = f'<div class="node-icon text-lg mb-1">{icon_html}</div>' if icon_html else ''
                    nodes_html += f'''
                    <div class="node-card {node_class} p-4 text-center" style="min-width: 160px;">
                      {icon_div}<div class="node-title text-base">{title_br}</div>
                      {desc_html}
                    </div>'''
                    rendered_nodes.add(fork.id)
                    
                    # 渲染孤立节点（并列）
                    for o_idx, orphan in enumerate(fully_orphan_nodes):
                        node_class = node_colors[(o_idx + 1) % len(node_colors)]
                        title_br = orphan.title.replace('\n', '<br>')
                        desc_br = orphan.desc.replace('\n', '<br>') if orphan.desc else ''
                        desc_html = f'<div class="node-desc text-sm">{desc_br}</div>' if desc_br else ''
                        icon_html = icon_to_html(orphan.icon) if orphan.icon else ''
                        icon_div = f'<div class="node-icon text-lg mb-1">{icon_html}</div>' if icon_html else ''
                        nodes_html += f'''
                        <div class="node-card {node_class} p-4 text-center" style="min-width: 160px;">
                          {icon_div}<div class="node-title text-base">{title_br}</div>
                          {desc_html}
                        </div>'''
                        rendered_nodes.add(orphan.id)
                    
                    nodes_html += '</div>'
                else:
                    # 非第一行或无孤立节点：父节点单独居中
                    node_class = node_colors[0]
                    title_br = fork.title.replace('\n', '<br>')
                    desc_br = fork.desc.replace('\n', '<br>') if fork.desc else ''
                    desc_html = f'<div class="node-desc">{desc_br}</div>' if desc_br else ''
                    icon_html = icon_to_html(fork.icon) if fork.icon else ''
                    icon_div = f'<div class="node-icon text-xl mb-1">{icon_html}</div>' if icon_html else ''
                    
                    nodes_html += f'''
                    <div class="node-card {node_class} p-5 text-center mx-auto" style="max-width: 300px;">
                      {icon_div}<div class="node-title">{title_br}</div>
                      {desc_html}
                    </div>'''
                    rendered_nodes.add(fork.id)
                
                # 向下箭头
                nodes_html += generate_sketchy_arrow('down', '', is_sketchy)
                
                # 子节点并排小方块
                children_ids = parent_to_children.get(fork.id, [])
                children_nodes = [node_map.get(c_id) for c_id in children_ids if node_map.get(c_id)]
                
                nodes_html += '<div class="flex gap-3 justify-center flex-wrap">'
                for c_idx, child in enumerate(children_nodes):
                    node_class = node_colors[(c_idx + 1) % len(node_colors)]
                    title_br = child.title.replace('\n', '<br>')
                    desc_br = child.desc.replace('\n', '<br>') if child.desc else ''
                    desc_html = f'<div class="node-desc text-sm">{desc_br}</div>' if desc_br else ''
                    # 三级节点不显示icon
                    icon_div = ''

                    nodes_html += f'''
                    <div class="node-card {node_class} p-3 text-center" style="min-width: 120px;">
                      <div class="node-title text-base">{title_br}</div>
                      {desc_html}
                    </div>'''
                    rendered_nodes.add(child.id)
                    
                    # 递归处理子节点的子节点（如果有）
                    sub_children_ids = parent_to_children.get(child.id, [])
                    if sub_children_ids:
                        sub_children = [node_map.get(s_id) for s_id in sub_children_ids if node_map.get(s_id)]
                        # 关闭当前flex容器，添加箭头和新的子节点行
                        nodes_html += '</div>'
                        nodes_html += generate_sketchy_arrow('down', '', is_sketchy)
                        nodes_html += '<div class="flex gap-3 justify-center flex-wrap mt-2">'
                        for sc_idx, sub_child in enumerate(sub_children):
                            if sub_child.id not in rendered_nodes:
                                node_class = node_colors[(c_idx + sc_idx + 2) % len(node_colors)]
                                title_br = sub_child.title.replace('\n', '<br>')
                                desc_br = sub_child.desc.replace('\n', '<br>') if sub_child.desc else ''
                                desc_html = f'<div class="node-desc text-sm">{desc_br}</div>' if desc_br else ''
                                # 四级节点不显示icon
                                icon_div = ''
                                nodes_html += f'''
                                <div class="node-card {node_class} p-3 text-center" style="min-width: 120px;">
                                  <div class="node-title text-base">{title_br}</div>
                                  {desc_html}
                                </div>'''
                                rendered_nodes.add(sub_child.id)
                
                nodes_html += '</div>'
            
            # 处理未渲染的节点（孤立节点或非分叉链路）
            unrendered = [n for n in sg.nodes if n.id not in rendered_nodes]
            if unrendered:
                # 检查是否形成链路
                chains = analyze_hierarchical_structure(unrendered, flowchart.all_connections)
                
                for chain in chains:
                    nodes_html += '<div class="flex gap-4 justify-center mt-3">'
                    for n_idx, node in enumerate(chain):
                        node_class = node_colors[n_idx % len(node_colors)]
                        title_br = node.title.replace('\n', '<br>')
                        desc_br = node.desc.replace('\n', '<br>') if node.desc else ''
                        desc_html = f'<div class="node-desc">{desc_br}</div>' if desc_br else ''
                        # 链路中：首节点保留icon（二级），其余移除（三级）
                        if n_idx == 0:
                            icon_html = icon_to_html(node.icon) if node.icon else ''
                            icon_div = f'<div class="node-icon text-xl mb-1">{icon_html}</div>' if icon_html else ''
                        else:
                            icon_div = ''
                        nodes_html += f'''
                        <div class="node-card {node_class} p-4 text-center">
                          {icon_div}<div class="node-title">{title_br}</div>
                          {desc_html}
                        </div>'''
                        if n_idx < len(chain) - 1:
                            nodes_html += generate_sketchy_arrow('right', '', is_sketchy,
                                                                 progress_index=n_idx,
                                                                 total_nodes=len(chain))
                    nodes_html += '</div>'
            
            nodes_html += '</div>'
        
        else:
            # 无分叉：使用链路布局
            chains = analyze_hierarchical_structure(sg.nodes, flowchart.all_connections)
            
            if len(chains) == 1 and len(chains[0]) <= 3:
                # 单链路、短：横向布局（无箭头）
                chain = chains[0]
                nodes_html = '<div class="flex items-center justify-between gap-4">'
                for n_idx, node in enumerate(chain):
                    node_class = node_colors[n_idx % len(node_colors)]
                    title_br = node.title.replace('\n', '<br>')
                    desc_br = node.desc.replace('\n', '<br>') if node.desc else ''
                    desc_html = f'<div class="node-desc">{desc_br}</div>' if desc_br else ''
                    # 链路首节点保留icon（二级），其余移除（三级）
                    if n_idx == 0:
                        icon_html = icon_to_html(node.icon) if node.icon else ''
                        icon_div = f'<div class="node-icon text-xl mb-1">{icon_html}</div>' if icon_html else ''
                    else:
                        icon_div = ''
                    nodes_html += f'''
                    <div class="node-card {node_class} p-5 flex-1 text-center">
                      {icon_div}<div class="node-title">{title_br}</div>
                      {desc_html}
                    </div>'''
                nodes_html += '</div>'
            
            else:
                # 多链路或长链路：横向并排，每条链路纵向递进
                nodes_html = '<div class="flex gap-6 items-start">'
                for chain_idx, chain in enumerate(chains):
                    nodes_html += '<div class="flex-1 space-y-3">'
                    for node_idx, node in enumerate(chain):
                        node_class = node_colors[(chain_idx + node_idx) % len(node_colors)]
                        title_br = node.title.replace('\n', '<br>')
                        desc_br = node.desc.replace('\n', '<br>') if node.desc else ''
                        desc_html = f'<div class="node-desc">{desc_br}</div>' if desc_br else ''
                        # 链路首节点保留icon（二级），其余移除（三级）
                        if node_idx == 0:
                            icon_html = icon_to_html(node.icon) if node.icon else ''
                            icon_div = f'<div class="node-icon text-xl mb-1">{icon_html}</div>' if icon_html else ''
                        else:
                            icon_div = ''
                        
                        nodes_html += f'''
                        <div class="node-card {node_class} p-4 text-center">
                          {icon_div}<div class="node-title">{title_br}</div>
                          {desc_html}
                        </div>'''
                        
                        if node_idx < len(chain) - 1:
                            nodes_html += generate_sketchy_arrow('down', '', is_sketchy)
                    
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
        
        # LR模式：卡片flex-1等宽，内部纵向布局，支持多行
        card_extra_class = 'flex-1 flex flex-col' if flowchart.direction == 'LR' else ''
        
        # LR 布局：添加水平箭头和分行逻辑
        if flowchart.direction == 'LR':
            ITEMS_PER_ROW = 3  # 每行最多 3 个卡片
            current_row = idx // ITEMS_PER_ROW
            current_col = idx % ITEMS_PER_ROW
            
            # 新行开始：添加行容器和向下箭头
            if current_col == 0:
                if idx > 0:
                    # 不是第一行，添加向下箭头
                    html_parts.append('''
    </div>
    <div class="lr-row-arrow">
      <svg width="32" height="32" viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path d="M16 4 L16 24 M8 18 L16 26 L24 18" stroke="''' + t['arrow_color'] + '''" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" stroke-dasharray="4 2"/>
      </svg>
    </div>
    <div class="lr-row">
''')
                else:
                    # 第一行开始
                    html_parts.append('''
    <div class="lr-row">
''')
            
            # 添加卡片
            html_parts.append(f'''
      <div class="card {card_class} p-6 lr-card">
        <div class="section-title">{sg_icon_html}{sg.title}</div>
        {nodes_html}
      </div>
''')
            
            # 同一行内，非最后一个卡片后添加水平箭头
            if current_col < ITEMS_PER_ROW - 1 and idx < len(flowchart.subgraphs) - 1:
                html_parts.append('''
      <div class="flex items-center self-center"><svg width="28" height="24" viewBox="0 0 28 24" fill="none" xmlns="http://www.w3.org/2000/svg" style="display:block;">
        <path d="M4 12 L20 12 M14 6 L22 12 L14 18" stroke="''' + t['arrow_color'] + '''" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" stroke-dasharray="3 2"/>
      </svg></div>
''')
        else:
            # TD 布局：原有逻辑
            html_parts.append(f'''
    <div class="card {card_class} p-6 {card_extra_class}">
      <div class="section-title">{sg_icon_html}{sg.title}</div>
      {nodes_html}
    </div>
''')
    
    # 渲染跨subgraph汇聚节点（独立总结卡片）
    cross_sg_sink_nodes = getattr(flowchart, 'cross_sg_sink_nodes', [])
    if cross_sg_sink_nodes:
        # 创建一个居中的总结卡片
        nodes_html = '<div class="flex justify-center gap-4">'
        for node_idx, node in enumerate(cross_sg_sink_nodes):
            node_class = node_colors[node_idx % len(node_colors)]
            title_br = node.title.replace('\n', '<br>')
            desc_br = node.desc.replace('\n', '<br>') if node.desc else ''
            desc_html = f'<div class="node-desc">{desc_br}</div>' if desc_br else ''
            icon_html = icon_to_html(node.icon) if node.icon else ''
            icon_div = f'<div class="node-icon text-xl mb-1">{icon_html}</div>' if icon_html else ''
            
            nodes_html += f'''
            <div class="node-card {node_class} p-5 text-center" style="min-width: 200px;">
              {icon_div}<div class="node-title">{title_br}</div>
              {desc_html}
            </div>'''
        
        nodes_html += '</div>'
        
        # 总结卡片使用特殊颜色（金色渐变）
        summary_card_class = 'card-4'
        html_parts.append(f'''
    <div class="card {summary_card_class} p-6">
      <div class="section-title">📊 综合评价</div>
      {nodes_html}
    </div>
''')
    
    # HTML 尾部
    # LR 布局：关闭最后一行的容器
    if flowchart.direction == 'LR' and len(flowchart.subgraphs) > 0:
        html_parts.append('''
    </div>''')  # 关闭 lr-row
    html_parts.append('''
    </div>
    <script>
      // 动态计算水印高度：根据内容区域高度
      function updateWatermarkHeight() {
        const content = document.getElementById('content');
        const watermark = document.getElementById('watermark-bg');
        if (content && watermark) {
          const contentHeight = content.scrollHeight + 40;
          watermark.style.height = contentHeight + 'px';
        }
      }
      // 页面加载和字体加载后更新
      updateWatermarkHeight();
      document.fonts.ready.then(updateWatermarkHeight);
      window.addEventListener('load', updateWatermarkHeight);
    </script>
  </div>
</body>
</html>''')
    
    return '\n'.join(html_parts)


def parse_markdown(text: str) -> Flowchart:
    """
    解析 Markdown 层级结构
    
    支持的格式:
    - # 一级标题 → 整体标题 (可选，默认"产业链图谱")
    - ## 二级标题 → subgraph 区块
    - ### 三级标题 → 节点标题，下一行作为描述
    - 列表项 `- xxx` → 节点标题（无描述）
    - `→ xxx` 或 `--> xxx` → 表示当前区块连接到下一个区块
    - 空行分隔不同区块
    
    特殊语法:
    - 标题开头的emoji自动识别为icon (如 `## 🏭 上游材料层`)
    - 标题中的 `|` 分隔标题和描述 (如 `### 冷却液 | 氟化液/硅基液`)
    
    示例:
    # 液冷产业链
    
    ## 上游材料层
    
    ### 冷却液
    氟化液/硅基液
    
    ### 金属材料
    铜/铝/金刚石铜
    
    → 核心部件层
    
    ## 核心部件层
    
    ### 液冷板
    微通道结构
    
    ### CDU
    分配单元
    
    → 系统集成层
    
    ## 系统集成层
    
    ### 液冷服务器
    整机柜方案
    
    ## 下游应用层
    
    - AI智算中心
    - 科学研究
    - 云计算互联网
    """
    flowchart = Flowchart()
    
    lines = text.split('\n')
    current_subgraph: Optional[Subgraph] = None
    current_node: Optional[Node] = None
    node_counter = 0  # 用于生成节点ID
    pending_connection_to: Optional[str] = None  # 待处理的跨区块连接
    
    for line in lines:
        line_stripped = line.strip()
        
        # 跳过空行
        if not line_stripped:
            # 空行结束当前节点描述收集
            current_node = None
            continue
        
        # 一级标题 → 整体标题
        if line_stripped.startswith('# ') and not line_stripped.startswith('##'):
            title = line_stripped[2:].strip()
            # 移除可能的emoji
            title = remove_emoji(title)
            flowchart.title = title
            continue
        
        # 二级标题 → subgraph 区块
        if line_stripped.startswith('## ') and not line_stripped.startswith('###'):
            # 先处理跨区块连接（如果有）
            if pending_connection_to and current_subgraph:
                # 当前subgraph的最后一个节点连接到目标subgraph
                if current_subgraph.nodes:
                    last_node_id = current_subgraph.nodes[-1].id
                    flowchart.all_connections.append((last_node_id, pending_connection_to))
                pending_connection_to = None
            
            # 开始新的subgraph
            sg_title_raw = line_stripped[3:].strip()
            sg_icon, sg_title, _ = parse_node_content(sg_title_raw)
            sg_id = f"sg{len(flowchart.subgraphs) + 1}"
            current_subgraph = Subgraph(id=sg_id, title=sg_title, icon=sg_icon)
            flowchart.subgraphs.append(current_subgraph)
            current_node = None
            continue
        
        # 三级标题 → 节点标题（下一行作为描述）
        if line_stripped.startswith('### '):
            if current_subgraph is None:
                # 没有##标题时创建默认subgraph
                current_subgraph = Subgraph(id="sg1", title=flowchart.title)
                flowchart.subgraphs.append(current_subgraph)
            
            node_counter += 1
            node_id = f"n{node_counter}"
            
            # 解析标题
            title_raw = line_stripped[4:].strip()
            
            # 支持 `|` 分隔标题和描述
            if '|' in title_raw:
                parts = title_raw.split('|', 1)
                title_part = parts[0].strip()
                desc_part = parts[1].strip() if len(parts) > 1 else ''
                icon, title, _ = parse_node_content(title_part)
                desc = desc_part
            else:
                icon, title, desc = parse_node_content(title_raw)
                # 描述可能由下一行提供，暂时设为空
                desc = ""
            
            current_node = Node(id=node_id, title=title, desc=desc, icon=icon, subgraph=current_subgraph.id)
            current_subgraph.nodes.append(current_node)
            flowchart.all_nodes[node_id] = current_node
            continue
        
        # 列表项 `- xxx` → 节点（无描述）
        if line_stripped.startswith('- ') or line_stripped.startswith('* '):
            if current_subgraph is None:
                # 没有##标题时创建默认subgraph
                current_subgraph = Subgraph(id="sg1", title=flowchart.title)
                flowchart.subgraphs.append(current_subgraph)
            
            node_counter += 1
            node_id = f"n{node_counter}"
            
            title_raw = line_stripped[2:].strip()
            # 支持 `|` 分隔标题和描述
            if '|' in title_raw:
                parts = title_raw.split('|', 1)
                title_part = parts[0].strip()
                desc_part = parts[1].strip() if len(parts) > 1 else ''
                icon, title, _ = parse_node_content(title_part)
                desc = desc_part
            else:
                icon, title, desc = parse_node_content(title_raw)
            
            node = Node(id=node_id, title=title, desc=desc, icon=icon, subgraph=current_subgraph.id)
            current_subgraph.nodes.append(node)
            flowchart.all_nodes[node_id] = node
            current_node = None  # 列表项不收集描述
            continue
        
        # 跨区块连接 `→ xxx` 或 `--> xxx`
        if line_stripped.startswith('→') or line_stripped.startswith('-->'):
            # 提取目标区块名称
            target_name = line_stripped.replace('→', '').replace('-->', '').strip()
            # 目标subgraph的ID（将在后续解析时确定）
            pending_connection_to = target_name  # 临时存储目标名称
            current_node = None
            continue
        
        # 其他行 → 可能是当前节点的描述
        if current_node and current_subgraph:
            # 如果当前节点还没有描述，这一行作为描述
            if not current_node.desc:
                current_node.desc = line_stripped
            else:
                # 多行描述用换行符连接
                current_node.desc += '\n' + line_stripped
    
    # 处理最后的跨区块连接
    if pending_connection_to and current_subgraph and current_subgraph.nodes:
        # 找到目标subgraph
        target_sg = next((sg for sg in flowchart.subgraphs if sg.title == pending_connection_to or pending_connection_to in sg.title), None)
        if target_sg and target_sg.nodes:
            last_node_id = current_subgraph.nodes[-1].id
            first_node_id = target_sg.nodes[0].id
            flowchart.all_connections.append((last_node_id, first_node_id))
    
    # 自动建立subgraph间的连接（如果subgraph标题包含"上游"、"中游"、"下游"等顺序词）
    order_keywords = ['上游', '中游', '下游', '材料', '部件', '系统', '应用', '第一', '第二', '第三', '核心', '集成']
    for i in range(len(flowchart.subgraphs) - 1):
        sg1 = flowchart.subgraphs[i]
        sg2 = flowchart.subgraphs[i + 1]
        
        # 检查是否已有连接
        sg1_node_ids = [n.id for n in sg1.nodes]
        sg2_node_ids = [n.id for n in sg2.nodes]
        has_connection = any(f in sg1_node_ids and t in sg2_node_ids for f, t in flowchart.all_connections)
        
        if not has_connection and sg1.nodes and sg2.nodes:
            # 自动连接：前一区块最后一个节点 → 后一区块第一个节点
            flowchart.all_connections.append((sg1.nodes[-1].id, sg2.nodes[0].id))
    
    # 如果没有subgraph，创建一个默认的
    if not flowchart.subgraphs and flowchart.all_nodes:
        default_sg = Subgraph(id="default", title=flowchart.title)
        for node in flowchart.all_nodes.values():
            node.subgraph = "default"
            default_sg.nodes.append(node)
        flowchart.subgraphs.append(default_sg)
    
    return flowchart


def split_flowchart_for_lr(flowchart: Flowchart, max_per_page: int = 4) -> List[Flowchart]:
    """
    将过长的 LR 布局 flowchart 拆分成多个部分
    
    Args:
        flowchart: 原始 flowchart
        max_per_page: 每页最多包含的 subgraph 数量
        
    Returns:
        拆分后的 Flowchart 列表，每个代表一页
    """
    if flowchart.direction != 'LR':
        return [flowchart]
    
    if len(flowchart.subgraphs) <= max_per_page:
        return [flowchart]
    
    # 拆分 subgraphs
    pages = []
    for i in range(0, len(flowchart.subgraphs), max_per_page):
        page_subgraphs = flowchart.subgraphs[i:i + max_per_page]
        
        # 创建新的 Flowchart
        page_num = i // max_per_page + 1
        total_pages = (len(flowchart.subgraphs) + max_per_page - 1) // max_per_page
        
        # 标题添加页码
        if total_pages > 1:
            title = f"{flowchart.title} ({page_num}/{total_pages})"
        else:
            title = flowchart.title
        
        page_fc = Flowchart(
            title=title,
            watermark=flowchart.watermark,
            direction='LR',
            subgraphs=page_subgraphs,
            raw_text=flowchart.raw_text,
            all_nodes=flowchart.all_nodes.copy(),
            all_connections=flowchart.all_connections.copy()
        )
        pages.append(page_fc)
    
    return pages


def main():
    parser = argparse.ArgumentParser(description='产业链图谱解析器 - 支持Mermaid和Markdown格式')
    parser.add_argument('input', nargs='?', help='输入文件路径 (.mmd 或 .md)')
    parser.add_argument('output', nargs='?', help='输出 HTML 文件路径')
    parser.add_argument('--demo', action='store_true', help='使用示例数据演示')
    parser.add_argument('--demo-md', action='store_true', help='使用Markdown示例数据演示')
    parser.add_argument('--theme', choices=list(THEMES.keys()), default='hand-drawn-edu',
                        help=f'主题风格: {", ".join(THEMES.keys())} (默认: hand-drawn-edu)')
    parser.add_argument('--list-themes', action='store_true', help='列出所有可用主题')
    parser.add_argument('--max-lr', type=int, default=4, 
                        help='LR布局每页最大subgraph数量 (默认: 4, 0表示不拆分)')
    
    args = parser.parse_args()
    
    # 列出所有主题
    if args.list_themes:
        print('可用主题:')
        for theme_id, theme_config in THEMES.items():
            print(f'  {theme_id}: {theme_config["name"]}')
        return
    
    if args.demo:
        # Mermaid 示例
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
        html = generate_html(flowchart, theme=args.theme)
        
        output_path = Path('/tmp/demo-flowchart.html')
        output_path.write_text(html)
        print(f'Mermaid Demo HTML generated: {output_path}')
        return
    
    if args.demo_md:
        # Markdown 示例
        demo_md = '''
# 液冷产业链

## 🏭 上游材料层

### 冷却液 | 氟化液/硅基液

### 金属材料
铜/铝/金刚石铜

### 电子元器件 | 泵/阀/传感器

→ 核心部件层

## ❄️ 核心部件层

### 液冷板 | 微通道结构

### CDU | 分配单元

### 快接头 | UQD连接器

→ 系统集成层

## 🖥️ 系统集成层

### 液冷服务器 | 整机柜方案

### 温控系统 | 冷量分配

→ 下游应用层

## 🤖 下游应用层

- AI智算中心 | 大模型训练
- 科学研究 | 超算中心
- 云计算互联网 | 数据中心
'''
        flowchart = parse_markdown(demo_md)
        html = generate_html(flowchart, theme=args.theme)
        
        output_path = Path('/tmp/demo-markdown.html')
        output_path.write_text(html)
        print(f'Markdown Demo HTML generated: {output_path}')
        print(f'  Theme: {THEMES[args.theme]["name"]}')
        print(f'  Title: {flowchart.title}')
        print(f'  Subgraphs: {len(flowchart.subgraphs)}')
        print(f'  Nodes: {len(flowchart.all_nodes)}')
        return
    
    if not args.input:
        parser.print_help()
        return
    
    # 读取输入文件
    input_path = Path(args.input)
    if not input_path.exists():
        print(f'Error: Input file not found: {input_path}')
        sys.exit(1)
    
    input_text = input_path.read_text()
    
    # 根据文件扩展名选择解析器
    if input_path.suffix.lower() == '.md':
        flowchart = parse_markdown(input_text)
        print('Using Markdown parser')
    else:
        flowchart = parse_mermaid(input_text)
        print('Using Mermaid parser')
    
    # 拆分 LR 布局（如果需要）
    max_lr = args.max_lr if args.max_lr > 0 else 999  # 0 表示不拆分
    flowchart_pages = split_flowchart_for_lr(flowchart, max_per_page=max_lr)
    
    # 输出
    if args.output:
        output_path = Path(args.output)
    else:
        output_path = input_path.with_suffix('.html')
    
    # 生成多个 HTML 文件（如果拆分了）
    if len(flowchart_pages) > 1:
        print(f'LR layout split into {len(flowchart_pages)} pages')
        for i, page_fc in enumerate(flowchart_pages, 1):
            html = generate_html(page_fc, theme=args.theme)
            # 文件名: name-1.html, name-2.html
            page_output = output_path.with_stem(f'{output_path.stem}-{i}')
            page_output.write_text(html)
            print(f'Page {i} HTML: {page_output}')
            print(f'  Title: {page_fc.title}')
            print(f'  Subgraphs: {len(page_fc.subgraphs)}')
    else:
        # 单页输出
        html = generate_html(flowchart_pages[0], theme=args.theme)
        output_path.write_text(html)
        print(f'HTML generated: {output_path}')
        print(f'  Theme: {THEMES[args.theme]["name"]}')
        print(f'  Title: {flowchart.title}')
        print(f'  Watermark: {flowchart.watermark}')
        print(f'  Subgraphs: {len(flowchart.subgraphs)}')
        print(f'  Nodes: {len(flowchart.all_nodes)}')


if __name__ == '__main__':
    main()