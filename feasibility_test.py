#!/usr/bin/env python3
"""
可行性测试程序
检查目标网站的爬取可行性，包括可访问性、反爬虫机制、页面结构等
"""

import asyncio
import json
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from crawl4ai import AsyncWebCrawler
from crawl4ai.async_configs import BrowserConfig

from sites_config import get_all_configs, SiteConfig

# #region agent log
import os
LOG_PATH = "/Users/pkwok/Projects/48. Crawl4AI/hk_housing/code/.cursor/debug.log"
def _log(hypothesis_id, location, message, data=None):
    try:
        import json
        log_entry = {
            "sessionId": "debug-session",
            "runId": "run1",
            "hypothesisId": hypothesis_id,
            "location": location,
            "message": message,
            "data": data or {},
            "timestamp": int(time.time() * 1000)
        }
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry) + "\n")
    except: pass
# #endregion


class FeasibilityTester:
    """可行性测试器"""
    
    def __init__(self):
        self.results = {}
        self.results_dir = Path("results")
        self.results_dir.mkdir(exist_ok=True)
    
    async def test_site(self, config: SiteConfig) -> Dict:
        """测试单个网站的可行性"""
        print(f"\n{'='*70}")
        print(f"测试网站: {config.name} ({config.domain})")
        print(f"{'='*70}")
        
        result = {
            "site_name": config.name,
            "domain": config.domain,
            "test_time": datetime.now().isoformat(),
            "tests": {}
        }
        
        # 测试1: 可访问性
        print("\n[1/7] 测试可访问性...")
        accessibility = await self._test_accessibility(config)
        result["tests"]["accessibility"] = accessibility
        print(f"  结果: {'✓ 可访问' if accessibility['accessible'] else '✗ 不可访问'}")
        if not accessibility['accessible']:
            print(f"  错误: {accessibility.get('error', 'Unknown')}")
            return result
        
        # 测试2: 反爬虫机制
        print("\n[2/7] 检测反爬虫机制...")
        anti_crawl = await self._test_anti_crawl(config)
        result["tests"]["anti_crawl"] = anti_crawl
        print(f"  检测到验证码: {'是' if anti_crawl.get('has_captcha') else '否'}")
        print(f"  检测到IP限制: {'是' if anti_crawl.get('has_ip_block') else '否'}")
        print(f"  检测到User-Agent检查: {'是' if anti_crawl.get('has_ua_check') else '否'}")
        
        # 测试3: 页面结构
        print("\n[3/7] 分析页面结构...")
        structure = await self._test_page_structure(config)
        result["tests"]["page_structure"] = structure
        print(f"  HTML长度: {structure.get('html_length', 0)} 字符")
        print(f"  是否包含房产相关关键词: {'是' if structure.get('has_property_keywords') else '否'}")
        print(f"  链接数量: {structure.get('link_count', 0)}")
        
        # 测试4: JavaScript渲染
        print("\n[4/7] 检查JavaScript渲染需求...")
        js_rendering = await self._test_js_rendering(config)
        result["tests"]["js_rendering"] = js_rendering
        print(f"  需要JS渲染: {'是' if js_rendering.get('requires_js') else '否'}")
        if js_rendering.get('requires_js'):
            print(f"  JS框架: {js_rendering.get('js_frameworks', 'Unknown')}")
        
        # 测试5: 数据提取难度
        print("\n[5/7] 评估数据提取难度...")
        extraction = await self._test_data_extraction(config)
        result["tests"]["data_extraction"] = extraction
        print(f"  找到价格字段: {'是' if extraction.get('found_price') else '否'}")
        print(f"  找到面积字段: {'是' if extraction.get('found_area') else '否'}")
        print(f"  找到位置字段: {'是' if extraction.get('found_location') else '否'}")
        print(f"  找到房型字段: {'是' if extraction.get('found_type') else '否'}")
        
        # 测试6: 分页机制
        print("\n[6/7] 分析分页机制...")
        pagination = await self._test_pagination(config)
        result["tests"]["pagination"] = pagination
        print(f"  分页类型: {pagination.get('type', 'Unknown')}")
        if pagination.get('has_pagination'):
            print(f"  分页元素: {'找到' if pagination.get('found_pagination') else '未找到'}")
        
        # 测试7: 请求限制
        print("\n[7/7] 测试请求限制...")
        rate_limit = await self._test_rate_limit(config)
        result["tests"]["rate_limit"] = rate_limit
        print(f"  快速请求测试: {'通过' if rate_limit.get('fast_request_ok') else '可能有限制'}")
        
        # 计算综合评分
        print("\n计算综合评分...")
        scores = self._calculate_scores(result["tests"])
        result["scores"] = scores
        result["overall_feasibility"] = scores["overall"]
        
        print(f"\n{'='*70}")
        print(f"测试完成 - {config.name}")
        print(f"{'='*70}")
        print(f"可访问性评分: {scores['accessibility']}/10")
        print(f"反爬虫难度: {scores['anti_crawl_difficulty']}/10 (分数越高越难)")
        print(f"数据提取难度: {scores['extraction_difficulty']}/10 (分数越高越难)")
        print(f"综合可行性评分: {scores['overall']}/10")
        print(f"{'='*70}\n")
        
        return result
    
    async def _test_accessibility(self, config: SiteConfig) -> Dict:
        """测试网站可访问性"""
        try:
            # #region agent log
            _log("A", "feasibility_test.py:118", "Creating BrowserConfig", {"user_agent": config.user_agent})
            # #endregion
            browser_config = BrowserConfig(
                headless=True,
                user_agent=config.user_agent,
            )
            
            # #region agent log
            _log("A", "feasibility_test.py:123", "Before AsyncWebCrawler init", {"param_name": "config", "param_type": type(browser_config).__name__, "runId": "post-fix"})
            # #endregion
            async with AsyncWebCrawler(config=browser_config) as crawler:
                # #region agent log
                _log("A", "feasibility_test.py:127", "AsyncWebCrawler created successfully", {})
                # #endregion
                result = await crawler.arun(
                    url=config.list_url,
                    timeout=config.timeout
                )
                
                # #region agent log
                _log("A", "feasibility_test.py:133", "Crawl result", {"success": result.success})
                # #endregion
                return {
                    "accessible": result.success,
                    "status_code": result.status_code if result.success else None,
                    "error": result.error_message if not result.success else None,
                    "response_time": getattr(result, 'response_time', None)
                }
        except Exception as e:
            # #region agent log
            _log("C", "feasibility_test.py:139", "Exception caught", {"error_type": type(e).__name__, "error_msg": str(e)})
            # #endregion
            error_msg = str(e)
            
            # 检查是否是 Playwright 浏览器未安装的错误
            if "Executable doesn't exist" in error_msg or "playwright install" in error_msg.lower():
                # #region agent log
                _log("PLAYWRIGHT", "feasibility_test.py:145", "Playwright browser not installed", {"error": error_msg[:200]})
                # #endregion
                return {
                    "accessible": False,
                    "error": "Playwright 浏览器未安装。请运行: playwright install 或 python -m playwright install",
                    "error_type": "playwright_not_installed",
                    "suggestion": "运行 'playwright install' 或 'python -m playwright install' 来安装浏览器"
                }
            
            return {
                "accessible": False,
                "error": error_msg
            }
    
    async def _test_anti_crawl(self, config: SiteConfig) -> Dict:
        """检测反爬虫机制"""
        try:
            browser_config = BrowserConfig(
                headless=True,
                user_agent=config.user_agent,
            )
            
            async with AsyncWebCrawler(config=browser_config) as crawler:
                result = await crawler.arun(
                    url=config.list_url,
                    timeout=config.timeout
                )
                
                if not result.success:
                    return {
                        "has_captcha": False,
                        "has_ip_block": False,
                        "has_ua_check": False,
                        "error": "无法访问页面"
                    }
                
                html = result.html.lower()
                markdown = result.markdown.lower()
                
                # 检测验证码关键词
                captcha_keywords = ['captcha', '验证码', 'recaptcha', 'hcaptcha', '验证']
                has_captcha = any(keyword in html or keyword in markdown for keyword in captcha_keywords)
                
                # 检测IP封禁关键词
                block_keywords = ['blocked', 'forbidden', 'access denied', '禁止访问', '封禁']
                has_ip_block = any(keyword in html or keyword in markdown for keyword in block_keywords)
                
                # 检测403状态码
                if result.status_code == 403:
                    has_ip_block = True
                
                # 检测User-Agent检查（通过检查页面内容）
                ua_keywords = ['please enable javascript', 'browser not supported', '不支持']
                has_ua_check = any(keyword in html or keyword in markdown for keyword in ua_keywords)
                
                return {
                    "has_captcha": has_captcha,
                    "has_ip_block": has_ip_block,
                    "has_ua_check": has_ua_check,
                    "status_code": result.status_code
                }
        except Exception as e:
            return {
                "has_captcha": False,
                "has_ip_block": False,
                "has_ua_check": False,
                "error": str(e)
            }
    
    async def _test_page_structure(self, config: SiteConfig) -> Dict:
        """分析页面结构"""
        try:
            browser_config = BrowserConfig(
                headless=True,
                user_agent=config.user_agent,
            )
            
            async with AsyncWebCrawler(config=browser_config) as crawler:
                result = await crawler.arun(
                    url=config.list_url,
                    timeout=config.timeout
                )
                
                if not result.success:
                    return {"error": "无法访问页面"}
                
                html = result.html
                markdown = result.markdown
                
                # 检查房产相关关键词
                property_keywords = ['property', '房产', '物业', '楼盘', '单位', 'price', '价格', 'area', '面积']
                has_property_keywords = any(keyword.lower() in html.lower() or keyword.lower() in markdown.lower() 
                                          for keyword in property_keywords)
                
                # 统计链接数量
                link_pattern = r'<a\s+[^>]*href=["\']([^"\']+)["\']'
                links = re.findall(link_pattern, html, re.IGNORECASE)
                link_count = len(links)
                
                # 检查是否有列表结构
                list_patterns = [r'<ul[^>]*>', r'<ol[^>]*>', r'class=["\'][^"\']*list[^"\']*["\']']
                has_list_structure = any(re.search(pattern, html, re.IGNORECASE) for pattern in list_patterns)
                
                return {
                    "html_length": len(html),
                    "markdown_length": len(markdown),
                    "has_property_keywords": has_property_keywords,
                    "link_count": link_count,
                    "has_list_structure": has_list_structure
                }
        except Exception as e:
            return {"error": str(e)}
    
    async def _test_js_rendering(self, config: SiteConfig) -> Dict:
        """检查JavaScript渲染需求"""
        try:
            browser_config = BrowserConfig(
                headless=True,
                user_agent=config.user_agent,
            )
            
            async with AsyncWebCrawler(config=browser_config) as crawler:
                # 先测试无JS渲染
                result_no_js = await crawler.arun(
                    url=config.list_url,
                    timeout=config.timeout,
                    js_code=""  # 禁用JS
                )
                
                # 再测试有JS渲染
                result_with_js = await crawler.arun(
                    url=config.list_url,
                    timeout=config.timeout
                )
                
                if not result_with_js.success:
                    return {"error": "无法访问页面"}
                
                # 比较内容差异
                content_diff = abs(len(result_with_js.html) - len(result_no_js.html if result_no_js.success else ""))
                requires_js = content_diff > 1000  # 如果差异大于1000字符，可能需要JS
                
                # 检测JS框架
                html = result_with_js.html.lower()
                js_frameworks = []
                if 'react' in html or 'react-dom' in html:
                    js_frameworks.append('React')
                if 'vue' in html or 'vue.js' in html:
                    js_frameworks.append('Vue')
                if 'angular' in html:
                    js_frameworks.append('Angular')
                if 'jquery' in html:
                    js_frameworks.append('jQuery')
                
                return {
                    "requires_js": requires_js or config.requires_js,
                    "content_diff": content_diff,
                    "js_frameworks": js_frameworks if js_frameworks else ["Unknown"]
                }
        except Exception as e:
            return {
                "requires_js": config.requires_js,
                "error": str(e)
            }
    
    async def _test_data_extraction(self, config: SiteConfig) -> Dict:
        """评估数据提取难度"""
        try:
            browser_config = BrowserConfig(
                headless=True,
                user_agent=config.user_agent,
            )
            
            async with AsyncWebCrawler(config=browser_config) as crawler:
                result = await crawler.arun(
                    url=config.list_url,
                    timeout=config.timeout
                )
                
                if not result.success:
                    return {"error": "无法访问页面"}
                
                html = result.html.lower()
                markdown = result.markdown.lower()
                
                # 查找价格相关关键词
                price_keywords = ['price', '价格', '價', 'hk$', 'hkd', '$', '萬', '万']
                found_price = any(keyword in html or keyword in markdown for keyword in price_keywords)
                
                # 查找面积相关关键词
                area_keywords = ['area', '面积', '面積', 'sqft', 'sq.ft', '平方', '呎']
                found_area = any(keyword in html or keyword in markdown for keyword in area_keywords)
                
                # 查找位置相关关键词
                location_keywords = ['location', '位置', '地址', 'address', 'district', '区域', '區域']
                found_location = any(keyword in html or keyword in markdown for keyword in location_keywords)
                
                # 查找房型相关关键词
                type_keywords = ['type', '房型', '房', 'bedroom', 'bed', 'room', '室']
                found_type = any(keyword in html or keyword in markdown for keyword in type_keywords)
                
                # 尝试使用配置的选择器（如果可能）
                # 这里只是简单检查，实际提取需要更复杂的逻辑
                
                return {
                    "found_price": found_price,
                    "found_area": found_area,
                    "found_location": found_location,
                    "found_type": found_type,
                    "extraction_possible": found_price and found_area and found_location
                }
        except Exception as e:
            return {"error": str(e)}
    
    async def _test_pagination(self, config: SiteConfig) -> Dict:
        """分析分页机制"""
        try:
            browser_config = BrowserConfig(
                headless=True,
                user_agent=config.user_agent,
            )
            
            async with AsyncWebCrawler(config=browser_config) as crawler:
                result = await crawler.arun(
                    url=config.list_url,
                    timeout=config.timeout
                )
                
                if not result.success:
                    return {"error": "无法访问页面"}
                
                html = result.html.lower()
                
                # 查找分页相关元素
                pagination_patterns = [
                    r'page[=\s]+(\d+)',
                    r'pagination',
                    r'next[^>]*>',
                    r'上一页|下一页',
                    r'page\s*\d+',
                ]
                
                found_pagination = any(re.search(pattern, html, re.IGNORECASE) for pattern in pagination_patterns)
                
                # 检查URL参数中的分页
                has_url_param = 'page=' in config.list_url.lower() or 'p=' in config.list_url.lower()
                
                # 检查是否有"加载更多"按钮（无限滚动）
                has_load_more = 'load more' in html or '加载更多' in html or '查看更多' in html
                
                pagination_type = "unknown"
                if has_url_param:
                    pagination_type = "url_param"
                elif has_load_more:
                    pagination_type = "infinite_scroll"
                elif found_pagination:
                    pagination_type = "pagination_links"
                
                return {
                    "has_pagination": found_pagination or has_url_param or has_load_more,
                    "found_pagination": found_pagination,
                    "type": pagination_type,
                    "has_url_param": has_url_param,
                    "has_load_more": has_load_more
                }
        except Exception as e:
            return {"error": str(e)}
    
    async def _test_rate_limit(self, config: SiteConfig) -> Dict:
        """测试请求限制"""
        try:
            browser_config = BrowserConfig(
                headless=True,
                user_agent=config.user_agent,
            )
            
            async with AsyncWebCrawler(config=browser_config) as crawler:
                # 快速连续请求测试
                results = []
                for i in range(3):
                    result = await crawler.arun(
                        url=config.list_url,
                        timeout=config.timeout
                    )
                    results.append(result.success)
                    await asyncio.sleep(0.5)  # 短暂延迟
                
                fast_request_ok = all(results)
                
                return {
                    "fast_request_ok": fast_request_ok,
                    "success_count": sum(results),
                    "total_requests": len(results)
                }
        except Exception as e:
            return {
                "fast_request_ok": False,
                "error": str(e)
            }
    
    def _calculate_scores(self, tests: Dict) -> Dict:
        """计算综合评分"""
        scores = {}
        
        # 可访问性评分 (0-10)
        accessibility = tests.get("accessibility", {})
        if accessibility.get("accessible"):
            scores["accessibility"] = 10
        else:
            scores["accessibility"] = 0
        
        # 反爬虫难度评分 (0-10, 分数越高越难)
        anti_crawl = tests.get("anti_crawl", {})
        difficulty = 0
        if anti_crawl.get("has_captcha"):
            difficulty += 4
        if anti_crawl.get("has_ip_block"):
            difficulty += 4
        if anti_crawl.get("has_ua_check"):
            difficulty += 2
        scores["anti_crawl_difficulty"] = min(difficulty, 10)
        
        # 数据提取难度评分 (0-10, 分数越高越难)
        extraction = tests.get("data_extraction", {})
        extraction_difficulty = 0
        if not extraction.get("found_price"):
            extraction_difficulty += 3
        if not extraction.get("found_area"):
            extraction_difficulty += 3
        if not extraction.get("found_location"):
            extraction_difficulty += 2
        if not extraction.get("found_type"):
            extraction_difficulty += 2
        scores["extraction_difficulty"] = min(extraction_difficulty, 10)
        
        # 综合可行性评分 (0-10, 分数越高越可行)
        if scores["accessibility"] == 0:
            overall = 0
        else:
            # 基础分：可访问性
            base_score = scores["accessibility"] * 0.4
            
            # 反爬虫难度影响（难度越高，分数越低）
            anti_crawl_penalty = scores["anti_crawl_difficulty"] * 0.3
            
            # 数据提取难度影响
            extraction_penalty = scores["extraction_difficulty"] * 0.3
            
            overall = max(0, base_score - anti_crawl_penalty - extraction_penalty)
        
        scores["overall"] = round(overall, 2)
        
        return scores
    
    async def run_all_tests(self):
        """运行所有测试"""
        print("="*70)
        print("香港房产网站可行性测试")
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
        
        report_path = self.results_dir / "feasibility_report.json"
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
                print(f"{result['site_name']:15} - 可行性评分: {result['scores']['overall']:.2f}/10")
            else:
                print(f"{result['site_name']:15} - 测试失败")
        print("-" * 70)


async def main():
    """主函数"""
    tester = FeasibilityTester()
    await tester.run_all_tests()


if __name__ == "__main__":
    asyncio.run(main())


