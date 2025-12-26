#!/usr/bin/env python3
"""
效率测试程序
评估目标网站的爬取性能，包括响应时间、并发性能、资源使用等
"""

import asyncio
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False
    print("警告: psutil 未安装，内存测试功能将受限")

from crawl4ai import AsyncWebCrawler
from crawl4ai.async_configs import BrowserConfig

from sites_config import get_all_configs, SiteConfig


class EfficiencyTester:
    """效率测试器"""
    
    def __init__(self):
        self.results = {}
        self.results_dir = Path("results")
        self.results_dir.mkdir(exist_ok=True)
        if HAS_PSUTIL:
            self.process = psutil.Process()
        else:
            self.process = None
    
    async def test_site(self, config: SiteConfig) -> Dict:
        """测试单个网站的效率"""
        print(f"\n{'='*70}")
        print(f"测试网站: {config.name} ({config.domain})")
        print(f"{'='*70}")
        
        result = {
            "site_name": config.name,
            "domain": config.domain,
            "test_time": datetime.now().isoformat(),
            "tests": {}
        }
        
        # 测试1: 单页爬取时间
        print("\n[1/6] 测试单页爬取时间...")
        single_page = await self._test_single_page(config)
        result["tests"]["single_page"] = single_page
        if single_page.get("success"):
            print(f"  平均响应时间: {single_page.get('avg_time', 0):.2f}秒")
            print(f"  最小响应时间: {single_page.get('min_time', 0):.2f}秒")
            print(f"  最大响应时间: {single_page.get('max_time', 0):.2f}秒")
        else:
            print(f"  测试失败: {single_page.get('error', 'Unknown')}")
        
        # 测试2: 并发性能
        print("\n[2/6] 测试并发性能...")
        concurrent = await self._test_concurrent(config)
        result["tests"]["concurrent"] = concurrent
        if concurrent.get("success"):
            print(f"  并发数: {concurrent.get('concurrent_count', 0)}")
            print(f"  总耗时: {concurrent.get('total_time', 0):.2f}秒")
            print(f"  平均每页: {concurrent.get('avg_time_per_page', 0):.2f}秒")
            print(f"  成功率: {concurrent.get('success_rate', 0):.1f}%")
        else:
            print(f"  测试失败: {concurrent.get('error', 'Unknown')}")
        
        # 测试3: 数据提取速度
        print("\n[3/6] 测试数据提取速度...")
        extraction = await self._test_extraction_speed(config)
        result["tests"]["extraction"] = extraction
        if extraction.get("success"):
            print(f"  提取时间: {extraction.get('extraction_time', 0):.3f}秒")
            print(f"  数据量: {extraction.get('data_size', 0)} 字符")
            print(f"  提取速度: {extraction.get('speed', 0):.0f} 字符/秒")
        else:
            print(f"  测试失败: {extraction.get('error', 'Unknown')}")
        
        # 测试4: 内存使用
        print("\n[4/6] 测试内存使用...")
        memory = await self._test_memory_usage(config)
        result["tests"]["memory"] = memory
        print(f"  初始内存: {memory.get('initial_memory', 0):.2f} MB")
        print(f"  峰值内存: {memory.get('peak_memory', 0):.2f} MB")
        print(f"  内存增长: {memory.get('memory_increase', 0):.2f} MB")
        
        # 测试5: 成功率
        print("\n[5/6] 测试成功率...")
        success_rate = await self._test_success_rate(config)
        result["tests"]["success_rate"] = success_rate
        print(f"  总请求数: {success_rate.get('total_requests', 0)}")
        print(f"  成功数: {success_rate.get('success_count', 0)}")
        print(f"  失败数: {success_rate.get('failure_count', 0)}")
        print(f"  成功率: {success_rate.get('rate', 0):.1f}%")
        
        # 测试6: 错误处理
        print("\n[6/6] 测试错误处理...")
        error_handling = await self._test_error_handling(config)
        result["tests"]["error_handling"] = error_handling
        print(f"  错误类型数: {len(error_handling.get('error_types', {}))}")
        print(f"  重试成功率: {error_handling.get('retry_success_rate', 0):.1f}%")
        
        # 计算综合效率评分
        print("\n计算综合效率评分...")
        scores = self._calculate_scores(result["tests"])
        result["scores"] = scores
        result["overall_efficiency"] = scores["overall"]
        
        print(f"\n{'='*70}")
        print(f"测试完成 - {config.name}")
        print(f"{'='*70}")
        print(f"响应速度评分: {scores['speed']}/10")
        print(f"并发性能评分: {scores['concurrency']}/10")
        print(f"稳定性评分: {scores['stability']}/10")
        print(f"资源效率评分: {scores['resource']}/10")
        print(f"综合效率评分: {scores['overall']}/10")
        print(f"{'='*70}\n")
        
        return result
    
    async def _test_single_page(self, config: SiteConfig) -> Dict:
        """测试单页爬取时间"""
        try:
            browser_config = BrowserConfig(
                headless=True,
                user_agent=config.user_agent,
            )
            
            times = []
            test_count = 3  # 测试3次取平均值
            
            async with AsyncWebCrawler(config=browser_config) as crawler:
                for i in range(test_count):
                    start_time = time.time()
                    result = await crawler.arun(
                        url=config.list_url,
                        timeout=config.timeout
                    )
                    end_time = time.time()
                    
                    if result.success:
                        elapsed = end_time - start_time
                        times.append(elapsed)
                    
                    # 请求间隔
                    if i < test_count - 1:
                        await asyncio.sleep(config.rate_limit)
            
            if not times:
                return {"success": False, "error": "所有请求都失败"}
            
            return {
                "success": True,
                "test_count": test_count,
                "success_count": len(times),
                "avg_time": sum(times) / len(times),
                "min_time": min(times),
                "max_time": max(times),
                "times": times
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _test_concurrent(self, config: SiteConfig) -> Dict:
        """测试并发性能"""
        try:
            browser_config = BrowserConfig(
                headless=True,
                user_agent=config.user_agent,
            )
            
            concurrent_count = min(config.max_concurrent, 3)  # 最多3个并发
            urls = [config.list_url] * concurrent_count  # 使用相同URL测试并发
            
            start_time = time.time()
            
            async with AsyncWebCrawler(config=browser_config) as crawler:
                tasks = [crawler.arun(url=url, timeout=config.timeout) for url in urls]
                results = await asyncio.gather(*tasks, return_exceptions=True)
            
            end_time = time.time()
            total_time = end_time - start_time
            
            success_count = sum(1 for r in results if not isinstance(r, Exception) and r.success)
            success_rate = (success_count / len(results)) * 100 if results else 0
            
            return {
                "success": True,
                "concurrent_count": concurrent_count,
                "total_time": total_time,
                "avg_time_per_page": total_time / concurrent_count if concurrent_count > 0 else 0,
                "success_count": success_count,
                "failure_count": len(results) - success_count,
                "success_rate": success_rate
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _test_extraction_speed(self, config: SiteConfig) -> Dict:
        """测试数据提取速度"""
        try:
            browser_config = BrowserConfig(
                headless=True,
                user_agent=config.user_agent,
            )
            
            async with AsyncWebCrawler(config=browser_config) as crawler:
                start_time = time.time()
                result = await crawler.arun(
                    url=config.list_url,
                    timeout=config.timeout
                )
                extraction_start = time.time()
                
                if not result.success:
                    return {"success": False, "error": "无法访问页面"}
                
                # 模拟数据提取（实际提取逻辑会更复杂）
                html = result.html
                markdown = result.markdown
                
                # 简单的数据提取测试
                import re
                # 提取价格
                prices = re.findall(r'[\$HK\$]?\s*[\d,]+', html)
                # 提取数字（可能是面积）
                numbers = re.findall(r'\d+', html)
                
                extraction_end = time.time()
                extraction_time = extraction_end - extraction_start
                
                data_size = len(html) + len(markdown)
                speed = data_size / extraction_time if extraction_time > 0 else 0
                
                return {
                    "success": True,
                    "extraction_time": extraction_time,
                    "data_size": data_size,
                    "speed": speed,
                    "prices_found": len(prices),
                    "numbers_found": len(numbers)
                }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _test_memory_usage(self, config: SiteConfig) -> Dict:
        """测试内存使用"""
        try:
            if not HAS_PSUTIL or self.process is None:
                return {
                    "success": False,
                    "error": "psutil 未安装，无法测试内存使用",
                    "initial_memory": 0,
                    "peak_memory": 0,
                    "memory_increase": 0
                }
            
            # 获取初始内存
            initial_memory = self.process.memory_info().rss / 1024 / 1024  # MB
            peak_memory = initial_memory
            
            browser_config = BrowserConfig(
                headless=True,
                user_agent=config.user_agent,
            )
            
            async with AsyncWebCrawler(config=browser_config) as crawler:
                # 执行多次请求以观察内存变化
                for i in range(3):
                    await crawler.arun(
                        url=config.list_url,
                        timeout=config.timeout
                    )
                    
                    # 检查当前内存
                    current_memory = self.process.memory_info().rss / 1024 / 1024
                    peak_memory = max(peak_memory, current_memory)
                    
                    await asyncio.sleep(0.5)
            
            if not HAS_PSUTIL or self.process is None:
                final_memory = initial_memory
            else:
                final_memory = self.process.memory_info().rss / 1024 / 1024
            memory_increase = final_memory - initial_memory
            
            return {
                "success": True,
                "initial_memory": initial_memory,
                "peak_memory": peak_memory,
                "final_memory": final_memory,
                "memory_increase": memory_increase
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _test_success_rate(self, config: SiteConfig) -> Dict:
        """测试成功率"""
        try:
            browser_config = BrowserConfig(
                headless=True,
                user_agent=config.user_agent,
            )
            
            test_count = 5
            success_count = 0
            failure_count = 0
            
            async with AsyncWebCrawler(config=browser_config) as crawler:
                for i in range(test_count):
                    result = await crawler.arun(
                        url=config.list_url,
                        timeout=config.timeout
                    )
                    
                    if result.success:
                        success_count += 1
                    else:
                        failure_count += 1
                    
                    # 请求间隔
                    if i < test_count - 1:
                        await asyncio.sleep(config.rate_limit)
            
            rate = (success_count / test_count) * 100 if test_count > 0 else 0
            
            return {
                "success": True,
                "total_requests": test_count,
                "success_count": success_count,
                "failure_count": failure_count,
                "rate": rate
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _test_error_handling(self, config: SiteConfig) -> Dict:
        """测试错误处理"""
        try:
            browser_config = BrowserConfig(
                headless=True,
                user_agent=config.user_agent,
            )
            
            error_types = {}
            retry_success = 0
            retry_total = 0
            
            async with AsyncWebCrawler(config=browser_config) as crawler:
                # 测试正常请求
                result1 = await crawler.arun(
                    url=config.list_url,
                    timeout=config.timeout
                )
                
                if not result1.success:
                    error_type = type(result1.error_message).__name__ if result1.error_message else "Unknown"
                    error_types[error_type] = error_types.get(error_type, 0) + 1
                    
                    # 测试重试
                    retry_total += 1
                    await asyncio.sleep(1)
                    result2 = await crawler.arun(
                        url=config.list_url,
                        timeout=config.timeout
                    )
                    if result2.success:
                        retry_success += 1
                
                # 测试无效URL（模拟错误）
                try:
                    result3 = await crawler.arun(
                        url=f"{config.list_url}/invalid-page-12345",
                        timeout=5
                    )
                    if not result3.success:
                        error_type = "404" if result3.status_code == 404 else "RequestError"
                        error_types[error_type] = error_types.get(error_type, 0) + 1
                except:
                    pass
            
            retry_success_rate = (retry_success / retry_total * 100) if retry_total > 0 else 100
            
            return {
                "success": True,
                "error_types": error_types,
                "retry_success": retry_success,
                "retry_total": retry_total,
                "retry_success_rate": retry_success_rate
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _calculate_scores(self, tests: Dict) -> Dict:
        """计算综合效率评分"""
        scores = {}
        
        # 响应速度评分 (0-10, 分数越高越快)
        single_page = tests.get("single_page", {})
        if single_page.get("success"):
            avg_time = single_page.get("avg_time", 999)
            # 10秒以内得10分，超过30秒得0分
            if avg_time <= 2:
                speed_score = 10
            elif avg_time <= 5:
                speed_score = 8
            elif avg_time <= 10:
                speed_score = 6
            elif avg_time <= 20:
                speed_score = 4
            elif avg_time <= 30:
                speed_score = 2
            else:
                speed_score = 0
        else:
            speed_score = 0
        scores["speed"] = speed_score
        
        # 并发性能评分 (0-10)
        concurrent = tests.get("concurrent", {})
        if concurrent.get("success"):
            success_rate = concurrent.get("success_rate", 0)
            avg_time_per_page = concurrent.get("avg_time_per_page", 999)
            
            # 基于成功率和速度
            concurrency_score = (success_rate / 10) * 5
            if avg_time_per_page <= 5:
                concurrency_score += 5
            elif avg_time_per_page <= 10:
                concurrency_score += 3
            elif avg_time_per_page <= 20:
                concurrency_score += 1
        else:
            concurrency_score = 0
        scores["concurrency"] = min(concurrency_score, 10)
        
        # 稳定性评分 (0-10)
        success_rate_test = tests.get("success_rate", {})
        if success_rate_test.get("success"):
            rate = success_rate_test.get("rate", 0)
            stability_score = rate / 10
        else:
            stability_score = 0
        scores["stability"] = stability_score
        
        # 资源效率评分 (0-10, 内存使用越少分数越高)
        memory = tests.get("memory", {})
        if memory.get("success"):
            memory_increase = memory.get("memory_increase", 999)
            # 内存增长小于100MB得10分，超过500MB得0分
            if memory_increase <= 50:
                resource_score = 10
            elif memory_increase <= 100:
                resource_score = 8
            elif memory_increase <= 200:
                resource_score = 6
            elif memory_increase <= 300:
                resource_score = 4
            elif memory_increase <= 500:
                resource_score = 2
            else:
                resource_score = 0
        else:
            resource_score = 5  # 无法测试时给中等分数
        scores["resource"] = resource_score
        
        # 综合效率评分
        overall = (
            scores["speed"] * 0.3 +
            scores["concurrency"] * 0.3 +
            scores["stability"] * 0.3 +
            scores["resource"] * 0.1
        )
        scores["overall"] = round(overall, 2)
        
        return scores
    
    async def run_all_tests(self):
        """运行所有测试"""
        print("="*70)
        print("香港房产网站效率测试")
        print("="*70)
        print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"目标网站数量: {len(get_all_configs())}")
        print("="*70)
        
        configs = get_all_configs()
        all_results = []
        
        for config in configs:
            try:
                result = await self.test_site(config)
                all_results.append(result)
            except Exception as e:
                print(f"\n测试 {config.name} 时发生错误: {str(e)}")
                all_results.append({
                    "site_name": config.name,
                    "error": str(e),
                    "test_time": datetime.now().isoformat()
                })
        
        # 保存结果
        report = {
            "test_summary": {
                "total_sites": len(configs),
                "test_time": datetime.now().isoformat(),
                "tested_sites": len(all_results)
            },
            "results": all_results
        }
        
        report_path = self.results_dir / "efficiency_report.json"
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        
        print("\n" + "="*70)
        print("所有测试完成！")
        print("="*70)
        print(f"测试报告已保存到: {report_path}")
        print("="*70)
        
        # 打印总结
        print("\n测试总结:")
        print("-" * 70)
        for result in all_results:
            if "scores" in result:
                print(f"{result['site_name']:15} - 效率评分: {result['scores']['overall']:.2f}/10")
            else:
                print(f"{result['site_name']:15} - 测试失败")
        print("-" * 70)


async def main():
    """主函数"""
    tester = EfficiencyTester()
    await tester.run_all_tests()


if __name__ == "__main__":
    asyncio.run(main())

