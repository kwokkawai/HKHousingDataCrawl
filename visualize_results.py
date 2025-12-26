#!/usr/bin/env python3
"""
测试结果可视化脚本
生成可行性测试和效率测试的可视化报告
"""

import json
from pathlib import Path
from typing import Dict, List, Optional

try:
    import matplotlib.pyplot as plt
    import matplotlib
    matplotlib.use('Agg')  # 使用非交互式后端
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False
    print("警告: matplotlib 未安装，将只生成文本报告")


class ResultVisualizer:
    """结果可视化器"""
    
    def __init__(self):
        self.results_dir = Path("results")
        self.output_dir = Path("results")
        self.output_dir.mkdir(exist_ok=True)
    
    def load_feasibility_report(self) -> Optional[Dict]:
        """加载可行性测试报告"""
        report_path = self.results_dir / "feasibility_report.json"
        if not report_path.exists():
            print(f"错误: 找不到可行性测试报告: {report_path}")
            return None
        
        with open(report_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def load_efficiency_report(self) -> Optional[Dict]:
        """加载效率测试报告"""
        report_path = self.results_dir / "efficiency_report.json"
        if not report_path.exists():
            print(f"错误: 找不到效率测试报告: {report_path}")
            return None
        
        with open(report_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def generate_text_report(self):
        """生成文本格式的综合报告"""
        print("="*70)
        print("香港房产网站爬取测试综合报告")
        print("="*70)
        
        # 加载报告
        feasibility_report = self.load_feasibility_report()
        efficiency_report = self.load_efficiency_report()
        
        if not feasibility_report and not efficiency_report:
            print("错误: 没有找到任何测试报告")
            return
        
        # 可行性报告
        if feasibility_report:
            print("\n" + "="*70)
            print("可行性测试结果")
            print("="*70)
            
            results = feasibility_report.get("results", [])
            for result in results:
                if "scores" in result:
                    print(f"\n{result['site_name']}:")
                    print(f"  可访问性: {result['scores'].get('accessibility', 0)}/10")
                    print(f"  反爬虫难度: {result['scores'].get('anti_crawl_difficulty', 0)}/10")
                    print(f"  数据提取难度: {result['scores'].get('extraction_difficulty', 0)}/10")
                    print(f"  综合可行性: {result['scores'].get('overall', 0)}/10")
                    
                    # 详细测试结果
                    tests = result.get("tests", {})
                    if "anti_crawl" in tests:
                        ac = tests["anti_crawl"]
                        print(f"  反爬虫检测:")
                        print(f"    - 验证码: {'是' if ac.get('has_captcha') else '否'}")
                        print(f"    - IP限制: {'是' if ac.get('has_ip_block') else '否'}")
                        print(f"    - UA检查: {'是' if ac.get('has_ua_check') else '否'}")
        
        # 效率报告
        if efficiency_report:
            print("\n" + "="*70)
            print("效率测试结果")
            print("="*70)
            
            results = efficiency_report.get("results", [])
            for result in results:
                if "scores" in result:
                    print(f"\n{result['site_name']}:")
                    print(f"  响应速度: {result['scores'].get('speed', 0)}/10")
                    print(f"  并发性能: {result['scores'].get('concurrency', 0)}/10")
                    print(f"  稳定性: {result['scores'].get('stability', 0)}/10")
                    print(f"  资源效率: {result['scores'].get('resource', 0)}/10")
                    print(f"  综合效率: {result['scores'].get('overall', 0)}/10")
                    
                    # 详细测试结果
                    tests = result.get("tests", {})
                    if "single_page" in tests and tests["single_page"].get("success"):
                        sp = tests["single_page"]
                        print(f"  单页性能:")
                        print(f"    - 平均响应时间: {sp.get('avg_time', 0):.2f}秒")
                        print(f"    - 最小响应时间: {sp.get('min_time', 0):.2f}秒")
                        print(f"    - 最大响应时间: {sp.get('max_time', 0):.2f}秒")
                    
                    if "success_rate" in tests and tests["success_rate"].get("success"):
                        sr = tests["success_rate"]
                        print(f"  成功率:")
                        print(f"    - 成功率: {sr.get('rate', 0):.1f}%")
                        print(f"    - 成功数: {sr.get('success_count', 0)}/{sr.get('total_requests', 0)}")
        
        # 综合对比
        print("\n" + "="*70)
        print("综合对比")
        print("="*70)
        
        if feasibility_report and efficiency_report:
            feasibility_results = {r["site_name"]: r for r in feasibility_report.get("results", []) if "scores" in r}
            efficiency_results = {r["site_name"]: r for r in efficiency_report.get("results", []) if "scores" in r}
            
            print(f"\n{'网站':<15} {'可行性':<10} {'效率':<10} {'综合推荐':<15}")
            print("-" * 70)
            
            all_sites = set(feasibility_results.keys()) | set(efficiency_results.keys())
            for site in sorted(all_sites):
                feasibility = feasibility_results.get(site, {}).get("scores", {}).get("overall", 0)
                efficiency = efficiency_results.get(site, {}).get("scores", {}).get("overall", 0)
                combined = (feasibility + efficiency) / 2
                
                recommendation = "推荐" if combined >= 7 else "一般" if combined >= 4 else "不推荐"
                
                print(f"{site:<15} {feasibility:<10.2f} {efficiency:<10.2f} {recommendation:<15}")
        
        print("\n" + "="*70)
        
        # 保存文本报告
        self._save_text_report(feasibility_report, efficiency_report)
    
    def _save_text_report(self, feasibility_report: Optional[Dict], efficiency_report: Optional[Dict]):
        """保存文本报告到文件"""
        report_path = self.output_dir / "comprehensive_report.txt"
        
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write("="*70 + "\n")
            f.write("香港房产网站爬取测试综合报告\n")
            f.write("="*70 + "\n\n")
            
            if feasibility_report:
                f.write("可行性测试结果\n")
                f.write("-"*70 + "\n")
                results = feasibility_report.get("results", [])
                for result in results:
                    if "scores" in result:
                        f.write(f"\n{result['site_name']}:\n")
                        f.write(f"  综合可行性: {result['scores'].get('overall', 0)}/10\n")
            
            if efficiency_report:
                f.write("\n效率测试结果\n")
                f.write("-"*70 + "\n")
                results = efficiency_report.get("results", [])
                for result in results:
                    if "scores" in result:
                        f.write(f"\n{result['site_name']}:\n")
                        f.write(f"  综合效率: {result['scores'].get('overall', 0)}/10\n")
        
        print(f"\n文本报告已保存到: {report_path}")
    
    def generate_charts(self):
        """生成图表（如果matplotlib可用）"""
        if not HAS_MATPLOTLIB:
            print("跳过图表生成（matplotlib 未安装）")
            return
        
        feasibility_report = self.load_feasibility_report()
        efficiency_report = self.load_efficiency_report()
        
        if not feasibility_report and not efficiency_report:
            return
        
        # 创建图表
        fig, axes = plt.subplots(2, 2, figsize=(14, 10))
        fig.suptitle('香港房产网站爬取测试结果', fontsize=16, fontweight='bold')
        
        # 1. 可行性评分对比
        if feasibility_report:
            ax1 = axes[0, 0]
            results = feasibility_report.get("results", [])
            sites = []
            scores = []
            for result in results:
                if "scores" in result:
                    sites.append(result["site_name"])
                    scores.append(result["scores"].get("overall", 0))
            
            if sites:
                ax1.bar(sites, scores, color=['#4CAF50', '#2196F3', '#FF9800'])
                ax1.set_title('可行性评分对比', fontweight='bold')
                ax1.set_ylabel('评分 (0-10)')
                ax1.set_ylim(0, 10)
                ax1.grid(axis='y', alpha=0.3)
                for i, v in enumerate(scores):
                    ax1.text(i, v + 0.2, f'{v:.2f}', ha='center', va='bottom')
        
        # 2. 效率评分对比
        if efficiency_report:
            ax2 = axes[0, 1]
            results = efficiency_report.get("results", [])
            sites = []
            scores = []
            for result in results:
                if "scores" in result:
                    sites.append(result["site_name"])
                    scores.append(result["scores"].get("overall", 0))
            
            if sites:
                ax2.bar(sites, scores, color=['#4CAF50', '#2196F3', '#FF9800'])
                ax2.set_title('效率评分对比', fontweight='bold')
                ax2.set_ylabel('评分 (0-10)')
                ax2.set_ylim(0, 10)
                ax2.grid(axis='y', alpha=0.3)
                for i, v in enumerate(scores):
                    ax2.text(i, v + 0.2, f'{v:.2f}', ha='center', va='bottom')
        
        # 3. 综合评分雷达图（简化版）
        if feasibility_report and efficiency_report:
            ax3 = axes[1, 0]
            feasibility_results = {r["site_name"]: r for r in feasibility_report.get("results", []) if "scores" in r}
            efficiency_results = {r["site_name"]: r for r in efficiency_report.get("results", []) if "scores" in r}
            
            all_sites = set(feasibility_results.keys()) | set(efficiency_results.keys())
            if all_sites:
                sites_list = sorted(list(all_sites))
                feasibility_scores = [feasibility_results.get(s, {}).get("scores", {}).get("overall", 0) for s in sites_list]
                efficiency_scores = [efficiency_results.get(s, {}).get("scores", {}).get("overall", 0) for s in sites_list]
                
                x = range(len(sites_list))
                width = 0.35
                ax3.bar([i - width/2 for i in x], feasibility_scores, width, label='可行性', color='#4CAF50')
                ax3.bar([i + width/2 for i in x], efficiency_scores, width, label='效率', color='#2196F3')
                ax3.set_title('可行性 vs 效率对比', fontweight='bold')
                ax3.set_ylabel('评分 (0-10)')
                ax3.set_xticks(x)
                ax3.set_xticklabels(sites_list, rotation=15, ha='right')
                ax3.legend()
                ax3.grid(axis='y', alpha=0.3)
                ax3.set_ylim(0, 10)
        
        # 4. 综合推荐度
        if feasibility_report and efficiency_report:
            ax4 = axes[1, 1]
            feasibility_results = {r["site_name"]: r for r in feasibility_report.get("results", []) if "scores" in r}
            efficiency_results = {r["site_name"]: r for r in efficiency_report.get("results", []) if "scores" in r}
            
            all_sites = set(feasibility_results.keys()) | set(efficiency_results.keys())
            if all_sites:
                sites_list = sorted(list(all_sites))
                combined_scores = []
                for site in sites_list:
                    feasibility = feasibility_results.get(site, {}).get("scores", {}).get("overall", 0)
                    efficiency = efficiency_results.get(site, {}).get("scores", {}).get("overall", 0)
                    combined_scores.append((feasibility + efficiency) / 2)
                
                colors = ['#4CAF50' if s >= 7 else '#FF9800' if s >= 4 else '#F44336' for s in combined_scores]
                x = range(len(sites_list))
                ax4.bar(x, combined_scores, color=colors)
                ax4.set_title('综合推荐度', fontweight='bold')
                ax4.set_ylabel('综合评分 (0-10)')
                ax4.set_xticks(x)
                ax4.set_xticklabels(sites_list, rotation=15, ha='right')
                ax4.grid(axis='y', alpha=0.3)
                ax4.set_ylim(0, 10)
                for i, v in enumerate(combined_scores):
                    ax4.text(i, v + 0.2, f'{v:.2f}', ha='center', va='bottom')
        
        plt.tight_layout()
        chart_path = self.output_dir / "test_results_charts.png"
        plt.savefig(chart_path, dpi=150, bbox_inches='tight')
        print(f"图表已保存到: {chart_path}")
        plt.close()
    
    def generate_summary(self):
        """生成总结报告"""
        feasibility_report = self.load_feasibility_report()
        efficiency_report = self.load_efficiency_report()
        
        if not feasibility_report and not efficiency_report:
            print("错误: 没有找到任何测试报告")
            return
        
        print("\n" + "="*70)
        print("测试总结和建议")
        print("="*70)
        
        if feasibility_report and efficiency_report:
            feasibility_results = {r["site_name"]: r for r in feasibility_report.get("results", []) if "scores" in r}
            efficiency_results = {r["site_name"]: r for r in efficiency_report.get("results", []) if "scores" in r}
            
            all_sites = set(feasibility_results.keys()) | set(efficiency_results.keys())
            
            print("\n各网站优缺点分析:")
            print("-" * 70)
            
            for site in sorted(all_sites):
                print(f"\n{site}:")
                feasibility = feasibility_results.get(site, {}).get("scores", {}).get("overall", 0)
                efficiency = efficiency_results.get(site, {}).get("scores", {}).get("overall", 0)
                combined = (feasibility + efficiency) / 2
                
                print(f"  综合评分: {combined:.2f}/10")
                
                # 优点
                advantages = []
                if feasibility >= 7:
                    advantages.append("可行性高")
                if efficiency >= 7:
                    advantages.append("效率高")
                if advantages:
                    print(f"  优点: {', '.join(advantages)}")
                
                # 缺点
                disadvantages = []
                if feasibility < 4:
                    disadvantages.append("可行性低")
                if efficiency < 4:
                    disadvantages.append("效率低")
                if disadvantages:
                    print(f"  缺点: {', '.join(disadvantages)}")
                
                # 建议
                if combined >= 7:
                    print(f"  建议: 优先考虑，适合作为主要数据源")
                elif combined >= 4:
                    print(f"  建议: 可作为补充数据源，需要额外处理")
                else:
                    print(f"  建议: 不推荐，爬取难度较大")
        
        print("\n" + "="*70)
    
    def run(self):
        """运行所有可视化任务"""
        print("生成测试结果可视化报告...")
        
        # 生成文本报告
        self.generate_text_report()
        
        # 生成图表
        self.generate_charts()
        
        # 生成总结
        self.generate_summary()
        
        print("\n可视化报告生成完成！")


def main():
    """主函数"""
    visualizer = ResultVisualizer()
    visualizer.run()


if __name__ == "__main__":
    main()


