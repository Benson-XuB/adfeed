"""
AdFeed AI — Phase 0 验证入口脚本

使用方法:
    python main.py                   # 使用模拟数据运行完整流程
    python main.py input.xlsx        # 使用真实 Excel 文件运行

输出:
    output/feed_us.xml               # GMC 标准 Feed XML
    output/comparison_report.xlsx    # 优化前后对比报告
    output/summary.json              # 处理统计摘要
"""

from adfeed.pipeline import run

if __name__ == "__main__":
    import sys

    excel_path = sys.argv[1] if len(sys.argv) > 1 else None
    run(excel_path=excel_path, countries=["US"])
