#!/usr/bin/env python3
"""
Markdown Mermaid 批量转换器

从 Markdown 文件中提取所有 Mermaid 代码块，转换为图片。

用法:
    python md2images.py input.md                    # 输出到 output/ 目录
    python md2images.py input.md -o ./images/       # 指定输出目录
    python md2images.py input.md --prefix chart_    # 指定文件名前缀
    python md2images.py input.md --update           # 更新 markdown，替换代码块为图片链接
    python md2images.py input.md --theme hand-drawn-edu  # 指定主题

输出:
    - 默认输出到 input 文件同目录下的 output/ 文件夹
    - 文件命名: {prefix}{index}.png (如 chart_1.png, chart_2.png)
"""

import re
import sys
import argparse
import subprocess
from pathlib import Path
from typing import List, Tuple

# 导入现有的解析器
try:
    from parse_mermaid import parse_mermaid, generate_html, THEMES
except ImportError:
    # 如果直接运行，添加父目录到路径
    import sys
    sys.path.insert(0, str(Path(__file__).parent))
    from parse_mermaid import parse_mermaid, generate_html, THEMES


def extract_mermaid_blocks(markdown_text: str) -> List[Tuple[str, int, int]]:
    """
    从 Markdown 文本中提取所有 Mermaid 代码块
    
    返回: [(代码块内容, 起始位置, 结束位置), ...]
    """
    pattern = r'```mermaid\s*\n(.*?)```'
    matches = re.finditer(pattern, markdown_text, re.DOTALL)
    
    blocks = []
    for match in matches:
        code = match.group(1).strip()
        start = match.start()
        end = match.end()
        blocks.append((code, start, end))
    
    return blocks


def mermaid_to_png(mermaid_code: str, output_path: Path, theme: str = 'hand-drawn-edu') -> bool:
    """
    将单个 Mermaid 代码块转换为 PNG 图片
    
    返回: True 成功, False 失败
    """
    # 生成 HTML
    try:
        flowchart = parse_mermaid(mermaid_code)
        html = generate_html(flowchart, theme=theme)
    except Exception as e:
        print(f"  解析 Mermaid 失败: {e}")
        return False
    
    # 写入临时 HTML
    temp_html = output_path.with_suffix('.html')
    temp_html.write_text(html)
    
    # 调用 screenshot.mjs 生成 PNG
    script_dir = Path(__file__).parent
    screenshot_script = script_dir / 'screenshot.mjs'
    
    try:
        result = subprocess.run(
            ['node', str(screenshot_script), str(temp_html), str(output_path)],
            capture_output=True,
            text=True,
            timeout=60
        )
        
        if result.returncode != 0:
            print(f"  截图失败: {result.stderr}")
            return False
        
        # 删除临时 HTML
        temp_html.unlink()
        return True
        
    except subprocess.TimeoutExpired:
        print("  截图超时")
        return False
    except Exception as e:
        print(f"  截图出错: {e}")
        return False


def process_markdown(
    input_path: Path,
    output_dir: Path,
    prefix: str = 'chart_',
    theme: str = 'hand-drawn-edu',
    update_markdown: bool = False
) -> List[Path]:
    """
    处理 Markdown 文件，转换所有 Mermaid 代码块为图片
    
    返回: 生成的图片路径列表
    """
    # 读取 markdown
    markdown_text = input_path.read_text()
    
    # 提取代码块
    blocks = extract_mermaid_blocks(markdown_text)
    
    if not blocks:
        print("未找到 Mermaid 代码块")
        return []
    
    print(f"找到 {len(blocks)} 个 Mermaid 代码块")
    
    # 确保输出目录存在
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # 转换每个代码块
    generated_images = []
    
    for i, (code, start, end) in enumerate(blocks, 1):
        output_name = f"{prefix}{i}.png"
        output_path = output_dir / output_name
        
        print(f"\n[{i}/{len(blocks)}] 生成: {output_name}")
        print(f"  主题: {THEMES[theme]['name']}")
        
        if mermaid_to_png(code, output_path, theme):
            generated_images.append(output_path)
            print(f"  ✓ 成功: {output_path}")
        else:
            print(f"  ✗ 失败")
    
    # 如果需要更新 markdown
    if update_markdown and generated_images:
        print(f"\n更新 Markdown 文件...")
        
        # 从后往前替换，避免位置偏移
        replacements = []
        for i, (code, start, end) in enumerate(blocks, 1):  # 从1开始编号
            if i <= len(generated_images):
                img_path = generated_images[i-1]  # 数组索引从0开始
                # 使用相对路径
                rel_path = img_path.relative_to(input_path.parent)
                replacement = f'![图{i}]({rel_path})'
                replacements.append((start, end, replacement))
        
        # 从后往前替换
        for start, end, replacement in reversed(replacements):
            markdown_text = markdown_text[:start] + replacement + markdown_text[end:]
        
        # 写回文件
        input_path.write_text(markdown_text)
        print(f"  已更新: {input_path}")
    
    return generated_images


def main():
    parser = argparse.ArgumentParser(
        description='Markdown Mermaid 批量转换器 - 提取所有 Mermaid 代码块并转换为图片',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
示例:
  %(prog)s report.md                      # 转换所有 mermaid 代码块
  %(prog)s report.md -o ./images/         # 指定输出目录
  %(prog)s report.md --prefix fig_        # 文件名前缀
  %(prog)s report.md --update             # 更新 markdown，替换代码块为图片
  %(prog)s report.md --theme instagram    # 使用 instagram 主题
        '''
    )
    
    parser.add_argument('input', help='输入 Markdown 文件路径')
    parser.add_argument('-o', '--output-dir', help='输出目录 (默认: 输入文件同目录下的 output/)')
    parser.add_argument('--prefix', default='chart_', help='输出文件名前缀 (默认: chart_)')
    parser.add_argument('--theme', choices=list(THEMES.keys()), default='hand-drawn-edu',
                        help=f'主题风格 (默认: hand-drawn-edu)')
    parser.add_argument('--update', action='store_true', 
                        help='更新 Markdown 文件，将代码块替换为图片链接')
    parser.add_argument('--list-themes', action='store_true', help='列出所有可用主题')
    
    # 提前处理 --list-themes（不需要 input 参数）
    if '--list-themes' in sys.argv:
        print('可用主题:')
        for theme_id, theme_config in THEMES.items():
            print(f'  {theme_id}: {theme_config["name"]}')
        return
    
    args = parser.parse_args()
    
    # 列出主题
    if args.list_themes:
        print('可用主题:')
        for theme_id, theme_config in THEMES.items():
            print(f'  {theme_id}: {theme_config["name"]}')
        return
    
    # 检查输入文件
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"错误: 文件不存在: {input_path}")
        sys.exit(1)
    
    # 确定输出目录
    if args.output_dir:
        output_dir = Path(args.output_dir)
    else:
        output_dir = input_path.parent / 'output'
    
    print(f"输入文件: {input_path}")
    print(f"输出目录: {output_dir}")
    print(f"文件前缀: {args.prefix}")
    print(f"主题风格: {THEMES[args.theme]['name']}")
    print("-" * 50)
    
    # 处理
    images = process_markdown(
        input_path=input_path,
        output_dir=output_dir,
        prefix=args.prefix,
        theme=args.theme,
        update_markdown=args.update
    )
    
    print("\n" + "=" * 50)
    print(f"完成! 共生成 {len(images)} 张图片")
    for img in images:
        print(f"  {img}")
    
    if args.update:
        print(f"\nMarkdown 已更新: {input_path}")


if __name__ == '__main__':
    main()