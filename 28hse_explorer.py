#!/usr/bin/env python3
"""
28Hse.com 数据结构探索脚本
用于检查实际页面结构，确定正确的CSS选择器
"""

import asyncio
import json
import re
from pathlib import Path
from crawl4ai import AsyncWebCrawler
from crawl4ai.async_configs import BrowserConfig
from sites_config import HSE28_CONFIG

async def explore_28hse_structure():
    """探索28Hse.com页面结构"""
    print("="*70)
    print("探索28Hse.com页面结构")
    print("="*70)
    
    browser_config = BrowserConfig(
        headless=True,
        user_agent=HSE28_CONFIG.user_agent,
    )
    
    async with AsyncWebCrawler(config=browser_config) as crawler:
        # 爬取列表页
        print(f"\n正在访问列表页: {HSE28_CONFIG.list_url}")
        result = await crawler.arun(
            url=HSE28_CONFIG.list_url,
            timeout=HSE28_CONFIG.timeout
        )
        
        if not result.success:
            print(f"✗ 无法访问页面: {result.error_message}")
            return
        
        print(f"✓ 成功访问页面")
        print(f"  URL: {result.url}")
        print(f"  HTML长度: {len(result.html)} 字符")
        print(f"  Markdown长度: {len(result.markdown)} 字符")
        
        # 保存HTML用于分析
        output_dir = Path("exploration")
        output_dir.mkdir(exist_ok=True)
        
        html_file = output_dir / "28hse_list_page.html"
        with open(html_file, 'w', encoding='utf-8') as f:
            f.write(result.html)
        print(f"  HTML已保存到: {html_file}")
        
        # 保存Markdown用于分析
        md_file = output_dir / "28hse_list_page.md"
        with open(md_file, 'w', encoding='utf-8') as f:
            f.write(result.markdown)
        print(f"  Markdown已保存到: {md_file}")
        
        # 使用BeautifulSoup分析HTML结构
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(result.html, 'html.parser')
            
            print("\n" + "="*70)
            print("分析页面结构")
            print("="*70)
            
            # 查找可能的房产列表容器
            print("\n1. 查找房产列表容器...")
            possible_selectors = [
                '.property-list',
                '.listing-list',
                '.result-list',
                '.property-item',
                '.listing-item',
                '.house-item',
                '[class*="property"]',
                '[class*="listing"]',
                '[class*="house"]',
                '[class*="item"]',
                '[class*="card"]',
            ]
            
            found_containers = []
            for selector in possible_selectors:
                elements = soup.select(selector)
                if elements:
                    found_containers.append((selector, len(elements)))
                    print(f"  ✓ '{selector}': 找到 {len(elements)} 个元素")
                    if elements:
                        first = elements[0]
                        classes = first.get('class', [])
                        print(f"    类名: {classes}")
                        print(f"    标签: {first.name}")
                        print(f"    子元素数: {len(first.find_all())}")
            
            if not found_containers:
                print("  ⚠ 未找到明显的列表容器，可能需要检查实际HTML结构")
            
            # 查找价格模式
            print("\n2. 查找价格信息...")
            price_patterns = [
                (r'[\$HK\$]?\s*[\d,]+萬?', '港币价格（万）'),
                (r'[\d,]+万', '中文万'),
                (r'[\d,]+萬', '繁体万'),
                (r'HK\$\s*[\d,]+', 'HK$格式'),
                (r'[\d,]+\.?\d*\s*萬', '带小数点的万'),
            ]
            
            for pattern, desc in price_patterns:
                matches = re.findall(pattern, result.html)
                if matches:
                    unique_matches = list(set(matches))[:5]
                    print(f"  ✓ {desc} ('{pattern}'): 找到 {len(matches)} 个匹配")
                    print(f"    示例: {unique_matches}")
            
            # 查找面积模式
            print("\n3. 查找面积信息...")
            area_patterns = [
                (r'[\d.]+?\s*呎', '平方呎'),
                (r'[\d.]+?\s*平方呎', '平方呎（完整）'),
                (r'[\d.]+?\s*sqft', 'sqft'),
                (r'[\d.]+?\s*平方', '平方'),
                (r'[\d.]+?\s*尺', '尺'),
            ]
            
            for pattern, desc in area_patterns:
                matches = re.findall(pattern, result.html, re.IGNORECASE)
                if matches:
                    unique_matches = list(set(matches))[:5]
                    print(f"  ✓ {desc} ('{pattern}'): 找到 {len(matches)} 个匹配")
                    print(f"    示例: {unique_matches}")
            
            # 查找链接（房产详情页）
            print("\n4. 查找房产详情链接...")
            links = soup.find_all('a', href=True)
            
            # 可能的链接模式
            link_patterns = [
                '/property/',
                '/listing/',
                '/house/',
                '/unit/',
                '/buy/',
                '/rent/',
                'property',
                'listing',
            ]
            
            property_links = []
            for link in links:
                href = link.get('href', '')
                for pattern in link_patterns:
                    if pattern in href.lower():
                        if not href.startswith('http'):
                            href = HSE28_CONFIG.base_url + href
                        property_links.append((href, link.get_text(strip=True)[:50]))
                        break
            
            # 去重
            unique_links = {}
            for href, text in property_links:
                if href not in unique_links:
                    unique_links[href] = text
            
            print(f"  找到 {len(unique_links)} 个可能的房产详情链接")
            if unique_links:
                print("  前5个链接:")
                for i, (href, text) in enumerate(list(unique_links.items())[:5], 1):
                    print(f"    {i}. {href}")
                    print(f"       文本: {text}")
            
            # 查找分页元素
            print("\n5. 查找分页元素...")
            pagination_selectors = [
                '.pagination',
                '.pager',
                '.page-nav',
                '[class*="pagination"]',
                '[class*="pager"]',
                '[class*="page"]',
            ]
            
            for selector in pagination_selectors:
                elements = soup.select(selector)
                if elements:
                    print(f"  ✓ '{selector}': 找到 {len(elements)} 个元素")
                    page_links = elements[0].find_all('a', href=True)
                    if page_links:
                        print(f"    包含 {len(page_links)} 个链接")
                        for link in page_links[:5]:
                            href = link.get('href', '')
                            text = link.get_text(strip=True)
                            print(f"      {text}: {href}")
            
            # 保存分析结果摘要
            summary = {
                "url": HSE28_CONFIG.list_url,
                "html_length": len(result.html),
                "markdown_length": len(result.markdown),
                "found_containers": found_containers,
                "property_links_count": len(unique_links),
                "sample_links": list(unique_links.items())[:10],
            }
            
            summary_file = output_dir / "28hse_analysis_summary.json"
            with open(summary_file, 'w', encoding='utf-8') as f:
                json.dump(summary, f, ensure_ascii=False, indent=2)
            print(f"\n✓ 分析摘要已保存到: {summary_file}")
            
        except ImportError:
            print("\n⚠ BeautifulSoup 未安装，跳过HTML结构分析")
            print("  可以安装: pip install beautifulsoup4")
        except Exception as e:
            print(f"\n✗ 分析过程中出错: {str(e)}")
        
        print("\n" + "="*70)
        print("探索完成！")
        print("="*70)
        print("\n下一步:")
        print("1. 检查保存的HTML文件，确认实际的CSS选择器")
        print("2. 根据分析结果更新 sites_config.py 中的选择器")
        print("3. 更新 28hse_crawler.py 中的数据提取逻辑")
        print("4. 运行 28hse_crawler.py 进行实际爬取")

if __name__ == "__main__":
    asyncio.run(explore_28hse_structure())


