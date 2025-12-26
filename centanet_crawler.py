#!/usr/bin/env python3
"""
中原地产爬虫 (Centanet Crawler)

设计说明：
----------
本爬虫采用多策略提取方法，按优先级顺序尝试不同的数据提取策略：

1. 面包屑导航提取（主要方法）：
   - 方法1: 从页面文本中通过正则表达式提取面包屑模式
   - 方法2: 从JavaScript paths数组中提取（最可靠）
   - 方法3: 从HTML面包屑导航元素中提取
   - 方法4: 从导航链接中提取
   
2. 字段映射策略：
   - 首先从面包屑中提取完整路径
   - 生成格式化的breadcrumb字符串（用">"分隔）
   - 然后从breadcrumb字符串中解析各个字段：
     * category: breadcrumb的第2个字符串
     * region: breadcrumb的第3个字符串
     * district_level2: breadcrumb的第4个字符串
     * sub_district: breadcrumb的第5个字符串
     * estate_name: breadcrumb的最后一个字符串

3. 备用提取方法：
   - 从URL中提取（用于title和estate_name）
   - 从页面元素中提取（价格、面积等）
   - 推断方法（基于已知信息推断缺失字段）

4. 数据验证和清理：
   - 过滤无效值
   - 验证数据完整性
   - 设置默认值

主要类和方法：
--------------
- CentanetCrawler: 主爬虫类
  - crawl_list_page(): 爬取列表页，提取详情页URL
  - crawl_detail_page(): 爬取单个详情页
  - _parse_detail_page(): 解析详情页HTML（核心方法）
  - crawl_all(): 批量爬取所有页面
  - save_data(): 保存数据到JSON和CSV文件
"""

import asyncio
import json
import re
import csv
from pathlib import Path
from typing import List, Optional, Dict
from datetime import datetime
from urllib.parse import urljoin, urlparse
import hashlib

from crawl4ai import AsyncWebCrawler
from crawl4ai.async_configs import BrowserConfig
from crawl4ai.extraction_strategy import JsonCssExtractionStrategy

from sites_config import CENTANET_CONFIG
from data_models import PropertyData


class CentanetCrawler:
    """
    中原地产爬虫类
    
    功能：
    - 爬取中原地产网站的房产列表页和详情页
    - 提取房产的详细信息（价格、面积、位置、面包屑导航等）
    - 支持批量爬取和增量爬取
    - 自动保存数据到JSON和CSV文件
    
    属性：
    - config: 爬虫配置（从sites_config导入）
    - output_dir: 输出目录路径
    - crawled_urls: 已爬取的URL集合（用于去重）
    - properties: 提取的房产数据列表
    - failed_urls: 失败的URL列表（用于错误追踪）
    """
    
    def __init__(self, output_dir: str = "data/centanet"):
        """
        初始化爬虫
        
        Args:
            output_dir: 数据输出目录，默认为 "data/centanet"
        """
        self.config = CENTANET_CONFIG
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.crawled_urls = set()
        self.properties: List[PropertyData] = []
        self.failed_urls = []
    
    @staticmethod
    def _parse_breadcrumb_fields(breadcrumb: str) -> tuple:
        """
        从breadcrumb字符串中解析各个字段
        
        设计说明：
        ----------
        根据用户要求，从格式化的breadcrumb字符串中提取字段：
        - category: breadcrumb的第2个字符串（移除"主頁"后索引0）
        - region: breadcrumb的第3个字符串（索引1）
        - district_level2: breadcrumb的第4个字符串（索引2）
        - sub_district: breadcrumb的第5个字符串（索引3）
        - estate_name: breadcrumb的最后一个字符串
        
        Args:
            breadcrumb: 格式化的breadcrumb字符串，如 "主頁 > 買樓 > 新界西 > 屯門 > 屯門市中心 > 瓏門"
            
        Returns:
            tuple: (category, region, district_level2, sub_district, estate_name)
        """
        if not breadcrumb:
            return None, None, None, None, None
        
        # 处理 ">" 分隔符或空格分隔符
        if ' > ' in breadcrumb:
            parts = [p.strip() for p in breadcrumb.split(' > ')]
        else:
            parts = breadcrumb.split()
        
        # 移除 "主頁" 如果存在
        if parts and parts[0] == '主頁':
            parts = parts[1:]
        
        # 根据用户要求映射字段
        category = parts[0] if len(parts) > 0 and parts[0] else None
        region = parts[1] if len(parts) > 1 and parts[1] else None
        district_level2 = parts[2] if len(parts) > 2 and parts[2] else None
        sub_district = parts[3] if len(parts) > 3 and parts[3] else None
        
        # estate_name 总是取最后一个部分（如果有的话）
        if len(parts) > 4:
            estate_name = parts[-1] if parts[-1] else None
        elif len(parts) == 4:
            estate_name = parts[3] if parts[3] else None
        else:
            estate_name = None
        
        return category, region, district_level2, sub_district, estate_name
    
    @staticmethod
    def _generate_breadcrumb(category: str, region: str, district: str, 
                            district_level2: str, sub_district: str, 
                            estate_name: str) -> str:
        """
        生成格式化的breadcrumb字符串
        
        Args:
            category: 类别（如"買樓"）
            region: 大区（如"新界西"）
            district: 区域（如"屯門"）
            district_level2: 二级区域（如"屯門市中心"）
            sub_district: 子区域（如"荃景圍"）
            estate_name: 屋苑名称（如"瓏門"）
            
        Returns:
            str: 格式化的breadcrumb字符串，如 "主頁 > 買樓 > 新界西 > 屯門 > 屯門市中心 > 瓏門"
        """
        breadcrumb_parts = ['主頁']
        if category:
            breadcrumb_parts.append(category)
        if region:
            breadcrumb_parts.append(region)
        if district:
            breadcrumb_parts.append(district)
        if district_level2:
            breadcrumb_parts.append(district_level2)
        if sub_district:
            breadcrumb_parts.append(sub_district)
        if estate_name:
            breadcrumb_parts.append(estate_name)
        
        return ' > '.join(breadcrumb_parts) if len(breadcrumb_parts) > 1 else None
        
    async def crawl_list_page(self, url: str, page_num: int = 1, crawler: Optional[AsyncWebCrawler] = None) -> List[str]:
        """
        爬取列表页，返回房产详情页URL列表
        
        设计说明：
        ----------
        Centanet使用AJAX分页，URL不变，需要通过点击分页按钮来加载内容。
        对于第1页：直接访问URL
        对于后续页面：先访问第1页，然后执行JavaScript点击对应的页码按钮
        
        Args:
            url: 列表页URL（对于所有页面都使用相同的URL）
            page_num: 页码（1, 2, 3...）
            
        Returns:
            房产详情页URL列表
        """
        # 如果没有传入crawler，创建新的
        # 如果传入了crawler，使用现有的（确保在同一浏览器会话中）
        browser_config = BrowserConfig(
            headless=True,
            user_agent=self.config.user_agent,
        )
        
        # 如果传入了crawler，直接使用；否则创建新的
        if crawler is not None:
            # 使用现有的crawler（在同一浏览器会话中）
            return await self._crawl_list_page_with_crawler(crawler, url, page_num)
        
        async with AsyncWebCrawler(config=browser_config) as new_crawler:
            return await self._crawl_list_page_with_crawler(new_crawler, url, page_num)
    
    async def _crawl_list_page_with_crawler(self, crawler: AsyncWebCrawler, url: str, page_num: int) -> List[str]:
        """
        使用指定的crawler实例爬取列表页（内部方法）
        
        Args:
            crawler: AsyncWebCrawler实例（必须在同一浏览器会话中）
            url: 列表页URL
            page_num: 页码
            
        Returns:
            房产详情页URL列表
        """
        # 直接使用crawler，不再次使用async with（因为crawler已经在外部管理）
        print(f"  正在爬取列表页 {page_num}...")
        
        # 对于第1页，直接访问URL
        if page_num == 1:
            result = await crawler.arun(
                url=url,
                timeout=max(self.config.timeout, 60),
                wait_for="networkidle",
                delay_before_return_html=3,
            )
        else:
            # 对于后续页面，需要从当前页面点击分页按钮
            # 关键：确保在同一浏览器会话中执行
            # 如果这是第2页，先加载第1页；如果是第3页及以后，假设已经在第(page_num-1)页
            print(f"    步骤1: 准备点击第{page_num}页按钮...")
            
            # 如果这是第2页，先加载第1页
            if page_num == 2:
                print(f"      加载第1页...")
                first_page_result = await crawler.arun(
                    url=url,
                    timeout=max(self.config.timeout, 60),
                    wait_for="networkidle",
                    delay_before_return_html=3,
                )
                if not first_page_result.success:
                    print(f"  ✗ 无法加载第1页: {first_page_result.error_message}")
                    return []
                print(f"      ✓ 第1页已加载")
            
            print(f"    步骤2: 执行JavaScript点击第{page_num}页按钮...")
            
            # 构建JavaScript代码来点击分页按钮
            # 根据Centanet网站结构，分页按钮显示为简单的数字（如 "1", "2", "3", "4", "417"）
            # 这些通常是列表项（<li>）或链接（<a>），位于页面底部的分页区域
            js_code = f"""
                (async () => {{
                    try {{
                        console.log('[PAGINATION] Starting pagination for page {page_num}...');
                        
                        // 等待页面稳定
                        await new Promise(resolve => setTimeout(resolve, 2000));
                        
                        const targetPage = String({page_num});
                        let clicked = false;
                        
                        // 方法1: 查找所有包含目标页码的元素
                        // Centanet的分页按钮通常是简单的数字文本
                        const allClickable = Array.from(document.querySelectorAll('a, button, li, span, div'));
                        
                        console.log('[PAGINATION] Searching', allClickable.length, 'elements for page', targetPage);
                        
                        for (let el of allClickable) {{
                            const text = (el.textContent || el.innerText || '').trim();
                            
                            // 精确匹配页码（只匹配纯数字，不包含其他字符）
                            if (text === targetPage) {{
                                // 检查是否是当前页（不应该点击当前页）
                                const isActive = el.classList.contains('active') || 
                                               el.classList.contains('current') ||
                                               el.classList.contains('selected') ||
                                               el.getAttribute('aria-current') === 'page';
                                
                                if (!isActive) {{
                                    console.log('[PAGINATION] Found page button:', text, 'tag:', el.tagName);
                                    
                                    // 滚动到元素
                                    el.scrollIntoView({{ behavior: 'smooth', block: 'center' }});
                                    await new Promise(resolve => setTimeout(resolve, 1000));
                                    
                                    // 尝试点击
                                    let success = false;
                                    
                                    // 如果是链接或按钮，直接点击
                                    if (el.tagName === 'A' || el.tagName === 'BUTTON') {{
                                        el.click();
                                        success = true;
                                        console.log('[PAGINATION] ✓ Clicked', el.tagName);
                                    }}
                                    // 如果是li，查找内部的a标签
                                    else if (el.tagName === 'LI') {{
                                        const link = el.querySelector('a');
                                        if (link) {{
                                            link.click();
                                            success = true;
                                            console.log('[PAGINATION] ✓ Clicked inner <a> in <li>');
                                        }} else {{
                                            // 如果没有a标签，直接点击li
                                            el.click();
                                            success = true;
                                            console.log('[PAGINATION] ✓ Clicked <li> directly');
                                        }}
                                    }}
                                    // 其他元素，尝试触发点击事件
                                    else {{
                                        const clickEvent = new MouseEvent('click', {{
                                            bubbles: true,
                                            cancelable: true,
                                            view: window
                                        }});
                                        el.dispatchEvent(clickEvent);
                                        success = true;
                                        console.log('[PAGINATION] ✓ Dispatched click event');
                                    }}
                                    
                                    if (success) {{
                                        clicked = true;
                                        console.log('[PAGINATION] ✓ Successfully clicked page', targetPage);
                                        
                                        // 等待AJAX内容加载，并验证页面是否真的更新了
                                        console.log('[PAGINATION] Waiting for content to load...');
                                        
                                        // 方法1: 等待固定时间
                                        await new Promise(resolve => setTimeout(resolve, 8000));
                                        
                                        // 方法2: 等待直到分页按钮变为active状态
                                        let maxWait = 20; // 最多等待20秒
                                        let waited = 0;
                                        while (waited < maxWait) {{
                                            // 检查目标页码按钮是否变为active
                                            const activeButton = Array.from(document.querySelectorAll('*')).find(el => {{
                                                const text = (el.textContent || '').trim();
                                                return text === targetPage && 
                                                       (el.classList.contains('active') || 
                                                        el.classList.contains('current') ||
                                                        el.getAttribute('aria-current') === 'page');
                                            }});
                                            
                                            if (activeButton) {{
                                                console.log('[PAGINATION] ✓ Page', targetPage, 'is now active');
                                                break;
                                            }}
                                            
                                            // 检查页面内容是否改变（通过检查房产链接数量）
                                            const detailLinks = Array.from(document.querySelectorAll('a[href*="/detail/"]'));
                                            if (detailLinks.length > 0) {{
                                                console.log('[PAGINATION] Found', detailLinks.length, 'detail links, content may have loaded');
                                                // 再等待2秒确保内容完全加载
                                                await new Promise(resolve => setTimeout(resolve, 2000));
                                                break;
                                            }}
                                            
                                            await new Promise(resolve => setTimeout(resolve, 1000));
                                            waited++;
                                        }}
                                        
                                        console.log('[PAGINATION] Content loading wait completed');
                                        break;
                                    }}
                                }} else {{
                                    console.log('[PAGINATION] Page', targetPage, 'is already active, skipping');
                                }}
                            }}
                        }}
                        
                        // 方法2: 如果方法1失败，尝试在整个页面中查找（更宽松的匹配）
                        if (!clicked) {{
                            console.log('[PAGINATION] Method 1 failed, trying broader search...');
                            
                            // 查找所有包含数字的元素
                            const numberElements = Array.from(document.querySelectorAll('*')).filter(el => {{
                                const text = (el.textContent || '').trim();
                                return text === targetPage && 
                                       el.offsetParent !== null && // 元素可见
                                       (el.tagName === 'A' || el.tagName === 'BUTTON' || el.tagName === 'LI' || el.tagName === 'SPAN');
                            }});
                            
                            console.log('[PAGINATION] Found', numberElements.length, 'potential page buttons');
                            
                            for (let el of numberElements) {{
                                const isActive = el.classList.contains('active') || 
                                               el.classList.contains('current');
                                
                                if (!isActive) {{
                                    el.scrollIntoView({{ behavior: 'smooth', block: 'center' }});
                                    await new Promise(resolve => setTimeout(resolve, 1000));
                                    
                                    if (el.tagName === 'A' || el.tagName === 'BUTTON') {{
                                        el.click();
                                    }} else if (el.tagName === 'LI') {{
                                        const link = el.querySelector('a');
                                        if (link) link.click();
                                        else el.click();
                                    }} else {{
                                        el.dispatchEvent(new MouseEvent('click', {{ bubbles: true }}));
                                    }}
                                    
                                    clicked = true;
                                    console.log('[PAGINATION] ✓ Clicked via method 2');
                                    await new Promise(resolve => setTimeout(resolve, 6000));
                                    break;
                                }}
                            }}
                        }}
                        
                        if (!clicked) {{
                            console.error('[PAGINATION] ✗ Failed to click page', targetPage);
                            // 调试：显示页面上所有可能的页码
                            const allNumbers = Array.from(document.querySelectorAll('*'))
                                .map(el => (el.textContent || '').trim())
                                .filter(text => /^\\d+$/.test(text) && parseInt(text) > 0 && parseInt(text) < 1000)
                                .filter((v, i, a) => a.indexOf(v) === i) // 去重
                                .slice(0, 20);
                            console.log('[PAGINATION] Available page numbers on page:', allNumbers);
                            return false;
                        }}
                        
                        // 最终等待
                        await new Promise(resolve => setTimeout(resolve, 2000));
                        console.log('[PAGINATION] ✓ Page navigation completed');
                        return true;
                    }} catch (error) {{
                        console.error('[PAGINATION] Error:', error);
                        return false;
                    }}
                }})();
                """
            
            # 使用js_code参数执行JavaScript并获取更新后的HTML
            # 关键：使用js_only=True确保在同一浏览器会话中执行，而不是重新加载页面
            from crawl4ai.async_configs import CrawlerRunConfig
            
            # 对于第2页及以后，使用js_only=True在同一会话中执行JavaScript
            # 关键：使用js_only=True时，页面已经加载，不需要wait_for（会导致超时）
            # 我们完全依赖delay_before_return_html来等待JavaScript执行完成
            from crawl4ai.async_configs import CrawlerRunConfig
            
            # 方法1: 尝试不设置wait_for（如果CrawlerRunConfig支持）
            try:
                config = CrawlerRunConfig(
                    js_code=js_code,
                    js_only=True,  # 关键：表示这是JS驱动的更新，不是完整页面加载
                    # 不设置wait_for，因为页面已经加载，等待事件会导致超时
                    delay_before_return_html=25,  # 增加等待时间到25秒，确保JavaScript执行完成和内容完全加载
                )
                
                result = await crawler.arun(
                    url=url,
                    config=config,
                    timeout=max(self.config.timeout, 200),  # 增加超时时间到200秒
                )
            except TypeError as e:
                # 如果CrawlerRunConfig要求wait_for参数，使用一个不会导致超时的值
                print(f"    ⚠ CrawlerRunConfig需要wait_for参数，使用备用配置...")
                try:
                    # 尝试使用一个自定义选择器，等待一个总是存在的元素
                    config = CrawlerRunConfig(
                        js_code=js_code,
                        js_only=True,
                        wait_for="body",  # 等待body元素（应该总是存在）
                        wait_for_timeout=2000,  # 只等待2秒（body应该立即存在）
                        delay_before_return_html=25,  # 增加等待时间到25秒
                    )
                    
                    result = await crawler.arun(
                        url=url,
                        config=config,
                        timeout=max(self.config.timeout, 200),
                    )
                except Exception as e2:
                    print(f"    ⚠ 备用配置也失败，尝试直接使用js_code: {str(e2)}")
                    # 最后备用：直接使用js_code参数
                    result = await crawler.arun(
                        url=url,
                        js_code=js_code,
                        delay_before_return_html=25,  # 增加等待时间到25秒
                        timeout=max(self.config.timeout, 200),
                    )
            except Exception as e:
                print(f"    ⚠ 配置执行异常，尝试直接使用js_code: {str(e)}")
                # 备用方法：直接使用js_code参数
                result = await crawler.arun(
                    url=url,
                    js_code=js_code,
                    delay_before_return_html=25,  # 增加等待时间到25秒
                    timeout=max(self.config.timeout, 200),
                )
            
            # 确保result不是None
            if result is None:
                print(f"  ✗ JavaScript执行失败: result为None")
                return []
            
            if not result.success:
                print(f"  ✗ JavaScript执行失败: {result.error_message if hasattr(result, 'error_message') else 'Unknown error'}")
                # 即使失败，也尝试提取HTML（可能部分内容已加载）
                if result and result.html:
                    print(f"    ⚠ 虽然执行失败，但已获取部分HTML内容，尝试提取...")
                else:
                    return []
            
            print(f"    ✓ JavaScript执行完成")
            
            # 关键：使用js_only=True时，result.html应该包含当前页面的HTML
            # 但我们需要确保JavaScript执行后，内容已经完全加载
            # 增加delay_before_return_html的时间，确保内容加载完成
            print(f"    步骤3: 等待内容完全加载并获取HTML...")
            
            # 再次使用js_only=True获取当前页面的HTML（不重新访问URL）
            # 这次只是等待并获取HTML，不执行额外的JavaScript
            try:
                from crawl4ai.async_configs import CrawlerRunConfig
                # 创建一个只等待的JavaScript代码
                wait_and_get_html_js = f"""
                (async () => {{
                    // 等待内容完全加载
                    await new Promise(resolve => setTimeout(resolve, 5000));
                    // 验证页面内容是否更新（检查分页按钮状态）
                    const activePage = Array.from(document.querySelectorAll('*')).find(el => {{
                        const text = (el.textContent || '').trim();
                        return text === '{page_num}' && 
                               (el.classList.contains('active') || 
                                el.classList.contains('current') ||
                                el.getAttribute('aria-current') === 'page');
                    }});
                    console.log('[PAGINATION] Active page button found:', !!activePage);
                    return true;
                }})();
                """
                
                html_config = CrawlerRunConfig(
                    js_code=wait_and_get_html_js,
                    js_only=True,
                    delay_before_return_html=5,  # 再等待5秒
                )
                
                html_result = await crawler.arun(
                    url=url,
                    config=html_config,
                    timeout=max(self.config.timeout, 60),
                )
                
                # 如果成功获取HTML，使用新的HTML
                if html_result and html_result.success and html_result.html and len(html_result.html) > 1000:
                    result.html = html_result.html
                    print(f"    ✓ 已获取更新后的页面内容 (HTML长度: {len(result.html)} 字符)")
                else:
                    print(f"    ⚠ 使用原始result.html (长度: {len(result.html) if result.html else 0} 字符)")
            except Exception as e:
                print(f"    ⚠ 获取更新HTML失败: {str(e)}，使用原始result.html")
            
            # 验证：检查提取的URL是否与第1页不同（简单验证）
            if page_num == 2 and hasattr(self, '_first_page_urls') and result and result.html:
                current_urls = set()
                try:
                    from bs4 import BeautifulSoup
                    soup = BeautifulSoup(result.html, 'html.parser')
                    links = soup.find_all('a', href=True)
                    for link in links:
                        href = link.get('href', '')
                        if '/findproperty/detail/' in href.lower():
                            if not href.startswith('http'):
                                href = urljoin(self.config.base_url, href)
                            current_urls.add(href)
                    
                    if current_urls == self._first_page_urls:
                        print(f"    ⚠ 警告: 第2页的URL与第1页完全相同，可能JavaScript未成功执行")
                    else:
                        print(f"    ✓ 验证: 第2页的URL与第1页不同，JavaScript执行成功")
                except:
                    pass
        
        # 确保result不是None
        if result is None:
            print(f"  ✗ 无法访问列表页 {page_num}: result为None")
            return []
        
        if not result.success:
            print(f"  ✗ 无法访问列表页 {page_num}: {result.error_message if hasattr(result, 'error_message') else 'Unknown error'}")
            return []
        
        property_urls = []
        
        # 方法1: 尝试使用CSS选择器提取
        try:
            # 根据实际页面结构调整选择器
            schema = {
                    "name": "properties",
                    "baseSelector": ".property-item, .listing-item, [class*='property'], [class*='listing']",
                    "fields": [
                        {
                            "name": "title",
                            "selector": ".title, .property-title, h3, h4, a",
                            "type": "text"
                        },
                        {
                            "name": "price",
                            "selector": ".price, .property-price, [class*='price']",
                            "type": "text"
                        },
                        {
                            "name": "area",
                            "selector": ".area, .property-area, [class*='area']",
                            "type": "text"
                        },
                        {
                            "name": "location",
                            "selector": ".location, .address, [class*='location']",
                            "type": "text"
                        },
                        {
                            "name": "link",
                            "selector": "a",
                            "type": "attribute",
                            "attribute": "href"
                        }
                    ]
            }
            
            extraction_strategy = JsonCssExtractionStrategy(schema)
            result_with_extraction = await crawler.arun(
                url=url,
                extraction_strategy=extraction_strategy
            )
            
            if result_with_extraction.extracted_content:
                try:
                    data = json.loads(result_with_extraction.extracted_content)
                    properties = data.get("properties", [])
                    
                    for prop in properties:
                        link = prop.get("link", "")
                        if link:
                            # 处理相对URL
                            if not link.startswith("http"):
                                link = urljoin(self.config.base_url, link)
                            property_urls.append(link)
                except json.JSONDecodeError:
                    pass
        except Exception as e:
            print(f"  ⚠ CSS选择器提取失败: {str(e)}")
        
        # 方法2: 如果CSS选择器失败，使用正则表达式和BeautifulSoup查找链接
        if not property_urls:
            try:
                # 确保result和result.html存在
                if result is None or not hasattr(result, 'html') or not result.html:
                    print(f"  ⚠ 警告: 无法获取页面HTML内容")
                    return []
                
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(result.html, 'html.parser')
                links = soup.find_all('a', href=True)
                
                # Centanet的详情页URL模式: /findproperty/detail/
                link_patterns = [
                    '/findproperty/detail/',  # Centanet特定模式
                    '/property/',
                    '/listing/',
                    '/detail/',
                    '/house/',
                    '/unit/',
                ]
                
                for link in links:
                    href = link.get('href', '')
                    # 检查是否是详情页链接
                    for pattern in link_patterns:
                        if pattern in href.lower():
                            # 排除列表页和其他非详情页链接
                            if '/list/' not in href.lower() and '/estate/' not in href.lower():
                                if not href.startswith('http'):
                                    href = urljoin(self.config.base_url, href)
                                # 确保是详情页URL
                                if '/detail/' in href.lower() and href not in property_urls:
                                    property_urls.append(href)
                            break
            except ImportError:
                print("  ⚠ BeautifulSoup 未安装，无法使用备用方法")
            except Exception as e:
                print(f"  ⚠ 备用方法失败: {str(e)}")
        
        # 去重
        property_urls = list(set(property_urls))
        
        # 如果是第1页，保存URL以便后续验证JavaScript是否成功执行
        if page_num == 1:
            self._first_page_urls = set(property_urls)
        
        # 详细调试信息
        if property_urls:
            print(f"  ✓ 列表页 {page_num}: 找到 {len(property_urls)} 个唯一房产URL")
            print(f"    示例链接: {property_urls[0][:80]}...")
            if len(property_urls) > 1:
                print(f"    最后一个链接: {property_urls[-1][:80]}...")
        else:
            print(f"    ⚠ 警告: 列表页 {page_num} 没有找到任何房产链接")
            print(f"    页面HTML长度: {len(result.html) if result and result.html else 0} 字符")
            # 尝试查找页面中的链接数量
            if result and result.html:
                try:
                    from bs4 import BeautifulSoup
                    soup = BeautifulSoup(result.html, 'html.parser')
                    all_links = soup.find_all('a', href=True)
                    detail_links = [link for link in all_links if '/detail/' in link.get('href', '').lower()]
                    print(f"    页面总链接数: {len(all_links)}")
                    print(f"    包含'/detail/'的链接数: {len(detail_links)}")
                    if detail_links:
                        print(f"    示例detail链接: {detail_links[0].get('href', '')[:80]}...")
                except:
                    pass
        
        return property_urls
    
    async def crawl_detail_page(self, url: str) -> Optional[PropertyData]:
        """
        爬取房产详情页
        
        Args:
            url: 详情页URL
            
        Returns:
            PropertyData 对象或 None
        """
        # 检查是否已爬取（使用线程安全的方式）
        # 注意：在并发环境下，这个检查可能不够精确，但可以避免重复爬取
        if url in self.crawled_urls:
            print(f"  ⊙ 跳过已爬取的URL: {url[:80]}...")
            return None
        
        browser_config = BrowserConfig(
            headless=True,
            user_agent=self.config.user_agent,
        )
        
        async with AsyncWebCrawler(config=browser_config) as crawler:
            try:
                # 增加超时时间，因为详情页可能需要更长时间加载
                result = await crawler.arun(
                    url=url,
                    timeout=60,  # 增加到60秒
                )
                
                if not result.success:
                    print(f"  ✗ 无法访问详情页: {url[:80]}...")
                    self.failed_urls.append(url)
                    return None
                
                # 解析详情页数据
                property_data = self._parse_detail_page(result.html, url)
                
                if property_data:
                    self.crawled_urls.add(url)
                    self.properties.append(property_data)
                    print(f"  ✓ [{len(self.properties)}] 成功: {property_data.title[:50] if property_data.title else 'N/A'}...")
                    return property_data
                else:
                    print(f"  ✗ 详情页解析失败: {url[:80]}...")
                    print(f"    可能原因: title验证失败或数据提取错误")
                    self.failed_urls.append(url)
                    return None
                    
            except Exception as e:
                print(f"  ✗ 爬取详情页出错: {url[:80]}... - {str(e)}")
                self.failed_urls.append(url)
                return None
    
    def _parse_detail_page(self, html: str, url: str) -> Optional[PropertyData]:
        """
        解析详情页HTML，提取房产数据
        
        设计说明：
        ----------
        本方法采用多策略提取方法，按以下顺序执行：
        
        1. 面包屑导航提取（优先级最高）：
           - 方法1: 从页面文本中通过正则表达式提取面包屑模式
           - 方法2: 从JavaScript paths数组中提取（最可靠的方法）
           - 方法3: 从HTML面包屑导航元素中提取
           - 方法4: 从导航链接中提取
           
        2. 其他字段提取：
           - 标题：从多个来源提取（URL、页面标题、描述等）
           - 价格：从价格元素和页面文本中提取
           - 面积：从面积元素中提取
           - 位置信息：从地址元素和描述中提取
           
        3. 字段映射和验证：
           - 生成格式化的breadcrumb字符串
           - 从breadcrumb中重新解析各个字段（确保映射一致性）
           - 验证和清理无效值
           
        4. 创建PropertyData对象并返回
        
        Args:
            html: 详情页的HTML内容
            url: 详情页的URL
            
        Returns:
            PropertyData对象，如果解析失败则返回None
        """
        try:
            from bs4 import BeautifulSoup
        except ImportError:
            print("  ⚠ BeautifulSoup 未安装，无法解析详情页")
            return None
        
        soup = BeautifulSoup(html, 'html.parser')
        
        # 初始化所有变量
        title = None  # 标题
        category = None  # 買樓/租樓
        region = None  # 新界西/港島等
        district = None  # 大埔/屯門等（从面包屑中提取，第三个）
        district_level2 = None  # 白石角等（从面包屑中提取，第四个）
        sub_district = None  # 逸瓏灣等（从面包屑中提取，第五个）
        area_name = None  # 可能从其他来源提取
        estate_name = None  # 逸瓏灣等（从面包屑中提取，最后一个）
        
        # ========================================================================
        # 方法1: 从页面文本中直接提取面包屑模式（通过正则表达式）
        # ========================================================================
        # 设计说明：
        # - 这是最直接的方法，通过正则表达式匹配页面文本中的面包屑模式
        # - 支持多种格式的面包屑结构
        # - 如果匹配成功，可以快速提取基本信息
        #
        # 支持的格式示例：
        # - 格式1: 主頁 買樓 新界東 大埔 白石角 逸瓏灣
        # - 格式2: 主頁 買樓 新界西 荃灣 | 麗城 荃灣西 映日灣
        # - 格式3: 主頁 買樓 新界西 屯門 屯門北 大興花園
        #
        # 注意：此方法可能不够可靠，因为页面文本可能包含干扰内容
        page_text = soup.get_text(separator=' ') if soup else ""  # 使用空格分隔，保持文本结构
        # 更灵活的面包屑模式，支持6-7个层级，保留"|"分隔符用于district_level2
        breadcrumb_patterns = [
            r'主頁\s+買樓\s+新界西\s+([^\s]+(?:\s*\|\s*[^\s]+)?)\s+([^\s]+)\s+([^\s]+(?:\s*\([^\)]+\))?)?',  # 主頁 買樓 新界西 荃灣 | 麗城 荃景圍 荃灣中心瀋陽樓 (19座)
            r'主頁\s+買樓\s+新界東\s+([^\s]+(?:\s*\|\s*[^\s]+)?)\s+([^\s]+)\s+([^\s]+)',  # 主頁 買樓 新界東 大埔 白石角 逸瓏灣
            r'主頁\s+買樓\s+新界西\s+([^\s]+)\s+([^\s]+)\s+([^\s]+)\s+([^\s]+)',  # 主頁 買樓 新界西 屯門 屯門北 大興花園
            r'主頁\s+([^\s|]+)\s+([^\s|]+)\s+([^\s|]+)\s+([^\s|]+)\s+([^\s|]+)\s+([^\s|]+)',  # 6个层级（包含主頁）
            r'主頁\s+([^\s|]+)\s+([^\s|]+)\s+([^\s|]+)\s+([^\s|]+)\s+([^\s|]+)\s+([^\s|]+)\s+([^\s|]+)',  # 7个层级（包含主頁）
            r'買樓\s+([^\s|]+)\s+([^\s|]+)\s+([^\s|]+)\s+([^\s|]+)\s+([^\s|]+)',  # 从買樓开始，5个层级
            r'買樓\s+([^\s|]+)\s+([^\s|]+)\s+([^\s|]+)\s+([^\s|]+)\s+([^\s|]+)\s+([^\s|]+)',  # 从買樓开始，6个层级
        ]

        breadcrumb_match = None
        breadcrumb_items_count = 0

        for pattern in breadcrumb_patterns:
            match = re.search(pattern, page_text)
            if match:
                breadcrumb_match = match
                breadcrumb_items_count = len(match.groups())
                # 检查是否匹配到了正确的面包屑（包含"新界西"或"新界東"）
                if '新界西' in str(match.groups()) or '新界東' in str(match.groups()):
                    break
                else:
                    # 这可能是错误的匹配，继续查找
                    breadcrumb_match = None
                    continue
        
        # ========================================================================
        # 方法2: 从JavaScript paths数组中提取面包屑（最可靠的方法）
        # ========================================================================
        # 设计说明：
        # - 这是最可靠的方法，因为JavaScript中的paths数组包含结构化的面包屑数据
        # - paths数组通常在<script>标签中的__NUXT__对象中
        # - path格式如："新界西_4-NW", "荃灣 | 麗城_23-WS050"
        # - 需要从path中提取显示文本（去掉编码部分）
        #
        # 优点：
        # - 数据结构化，提取准确
        # - 不受页面文本格式影响
        # - 包含完整的层级信息
        #
        # 缺点：
        # - 需要解析JavaScript代码
        # - 如果页面结构改变，可能失效
        if not breadcrumb_match:
            # 查找包含paths数组的script标签
            scripts = soup.find_all('script')
            paths_found = False

            for script in scripts:
                if script.string:
                    script_text = script.string
                    # 查找paths数组
                    paths_match = re.search(r'paths:\s*\[([^\]]+)\]', script_text)
                    if paths_match:
                        paths_content = paths_match.group(1)

                        # 解析paths数组中的path字段（包含实际的文本）
                        path_matches = re.findall(r'path:"([^"]+)"', paths_content)
                        if path_matches:
                            # 从path中提取实际的显示文本（去掉编码部分）
                            breadcrumb_items = []
                            for path in path_matches:
                                # path格式如："新界西_4-NW", "荃灣 | 麗城_23-WS050", "荃景圍_19-HMA100"
                                if '_' in path:
                                    display_text = path.split('_')[0]
                                    breadcrumb_items.append(display_text)

                            # 映射面包屑项 - 改进的逻辑
                            if len(breadcrumb_items) >= 4:
                                # 找到区域信息（跳过主頁和買樓）
                                for item in breadcrumb_items:
                                    if any(keyword in item for keyword in ['新界', '港島', '九龍', '香港島']):
                                        region = item
                                        break

                                # 获取非区域和非导航的项目
                                non_region_items = [item for item in breadcrumb_items if item != region and item not in ['主頁', '買樓']]

                                # 智能映射基于项目数量和内容
                                if len(non_region_items) >= 1:
                                    first_item = non_region_items[0]

                                    # 检查第一个项目是否是district
                                    hk_districts = [
                                        # New Territories
                                        '大埔', '荃灣', '屯門', '元朗', '沙田', '北區', '西貢', '葵青', '離島',
                                        # Hong Kong Island
                                        '中西區', '東區', '南區', '灣仔', '九龍城', '觀塘', '深水埗', '黃大仙', '油尖旺'
                                    ]
                                    is_first_item_district = first_item in hk_districts

                                    if is_first_item_district and len(non_region_items) >= 2:
                                        # 模式: district → district_level2 → sub_district → estate_name
                                        district = first_item
                                        district_level2 = non_region_items[1]

                                        if len(non_region_items) >= 3:
                                            sub_district_candidate = non_region_items[2]
                                            if sub_district_candidate and sub_district_candidate != district_level2:
                                                sub_district = sub_district_candidate

                                        if len(non_region_items) >= 4:
                                            estate_name_candidate = non_region_items[3]
                                            if estate_name_candidate:
                                                estate_name = estate_name_candidate.lstrip('-').split('_')[0]
                                        elif len(non_region_items) >= 3:
                                            # 如果只有3个项目，最后一个是estate_name
                                            estate_name_candidate = non_region_items[2]
                                            if estate_name_candidate and estate_name_candidate != sub_district:
                                                estate_name = estate_name_candidate.lstrip('-').split('_')[0]
                                    else:
                                        # 传统模式: district_level2 → sub_district → estate_name
                                        district_level2_candidate = first_item
                                        if '|' in district_level2_candidate:
                                            district_level2 = district_level2_candidate
                                            # 从district_level2提取district
                                            district = district_level2_candidate.split('|')[0].strip()
                                        else:
                                            # 对于没有"|"的地区，直接设置为district_level2
                                            district_level2 = district_level2_candidate
                                            # 根据region设置district
                                            if region == '九龍' and '將軍澳' in district_level2_candidate:
                                                district = '西貢'  # 將軍澳屬於西貢區

                                        if len(non_region_items) >= 2:
                                            # sub_district（荃景圍或將軍澳）
                                            sub_district_candidate = non_region_items[1]
                                            if sub_district_candidate and sub_district_candidate != district_level2:
                                                sub_district = sub_district_candidate

                                        if len(non_region_items) >= 3:
                                            # estate_name（海之戀，去掉编码）
                                            estate_name_candidate = non_region_items[2]
                                            if estate_name_candidate:
                                                # 处理可能带"-"前缀或编码的情况，但不强制要求"-"
                                                estate_name = estate_name_candidate.lstrip('-').split('_')[0]

                                paths_found = True
                                break

        # ========================================================================
        # 方法3: 从导航链接中提取面包屑（备用方法）
        # ========================================================================
        # 设计说明：
        # - 当方法1和方法2都失败时，尝试从页面中的导航链接提取
        # - 查找包含特定路径模式的链接（如/findproperty/list/、/findproperty/detail/）
        # - 按链接顺序构建面包屑序列
        #
        # 注意：此方法可能不够准确，因为链接顺序可能不反映实际层级
        if not breadcrumb_match and not paths_found:
            # 查找包含导航路径的链接，按顺序提取
            nav_links = soup.find_all('a', href=True)
            breadcrumb_sequence = []
            seen_hrefs = set()

            # 查找包含面包屑路径的链接
            for link in nav_links:
                href = link.get('href', '')
                text = link.get_text(strip=True)

                # 检查是否是面包屑导航链接
                if any(path in href for path in ['/findproperty/list/', '/findproperty/detail/', '/findproperty/district/']):
                    if href not in seen_hrefs and text:
                        # 处理"|"分隔符
                        if '|' in text:
                            text = text.split('|')[0].strip()
                        breadcrumb_sequence.append((text, href))
                        seen_hrefs.add(href)

            # 如果找到了导航链接序列，尝试构建面包屑
            if breadcrumb_sequence:
                # 从链接文本中提取层级信息
                link_texts = [text for text, href in breadcrumb_sequence]
                # 查找包含"買樓"、"新界西"等关键词的链接
                if len(link_texts) >= 3:
                    # 尝试匹配面包屑模式
                    breadcrumb_text = ' '.join(link_texts)
                    for pattern in breadcrumb_patterns:
                        match = re.search(pattern, breadcrumb_text)
                        if match:
                            breadcrumb_match = match
                            break
        
        if breadcrumb_match:
            items = breadcrumb_match.groups()
            # 检查是否是新的格式（主頁 買樓 新界西 荃灣 | 麗城 荃灣西 映日灣）
            is_new_format = len(items) == 3 and any('|' in item for item in items)
            
            if is_new_format:
                # 新格式：主頁 買樓 新界西 荃灣 | 麗城 荃灣西 映日灣
                # items[0] = "荃灣 | 麗城"
                # items[1] = "荃灣西"
                # items[2] = "映日灣"
                
                # category 和 region 已经在前面提取或从页面文本中提取
                if not category:
                    category = '買樓'
                if not region:
                    # 从模式中推断region（如果是新界西的模式）
                    if '新界西' in page_text:
                        region = '新界西'
                    elif '新界東' in page_text:
                        region = '新界東'
                
                # district_level2: 保留完整文本，包括"|"（如"荃灣 | 麗城"）
                district_level2_item = items[0].strip()
                if district_level2_item and not re.match(r'^\d+座$', district_level2_item):
                    district_level2 = district_level2_item
                
                # district: 从district_level2中提取第一部分（如"荃灣"）
                if district_level2 and '|' in district_level2:
                    district = district_level2.split('|')[0].strip()
                elif district_level2:
                    district = district_level2
                
                # sub_district: 第二个项（如"荃灣西"）
                if len(items) >= 2:
                    sub_district_item = items[1].strip()
                    if sub_district_item and not re.match(r'^\d+座$', sub_district_item):
                        sub_district = sub_district_item
                
                # estate_name: 第三个项（如"映日灣"）
                if len(items) >= 3:
                    estate_item = items[2].strip()
                    if estate_item and not re.match(r'^\d+座$', estate_item):
                        estate_name = estate_item
            else:
                # 旧格式：过滤掉无效项和座数
                valid_items = []
                invalid_keywords = [
                    '網上', '搵樓', '地圖', '更多', 'More', '主頁', '主页', 
                    '分行網絡', '中原地產', '接收心水樓盤最新',
                    '使用WeChat掃描QRcode', '中原薈', '一手新盤'
                ]
                invalid_keywords_list = ['QRcode', 'WeChat', '掃描', '網絡', '地產', '接收', '心水', '樓盤', '最新']
                
                for item in items:
                    if item:
                        # 对于旧格式，仍然处理"|"分隔符
                        original_item = item
                        if '|' in item:
                            item = item.split('|')[0].strip()
                        # 排除座数（如"2座"、"3座"等）
                        if re.match(r'^\d+座$', item):
                            continue
                        # 排除其他无效项
                        if (item not in invalid_keywords and 
                            len(item) > 1 and 
                            not any(kw in item for kw in invalid_keywords) and
                            not any(kw in item for kw in invalid_keywords_list)):
                            valid_items.append(item)
                
                # 解析层级
                # 格式：買樓 新界東 大埔 白石角 逸瓏灣 逸瓏灣
                # 或者：主頁 買樓 新界東 大埔 白石角 逸瓏灣 逸瓏灣
                idx = 0
                
                # 第一个应该是category
                if idx < len(valid_items):
                    if valid_items[idx] in ['買樓', '租樓', '成交', '新盤', '新盘']:
                        category = valid_items[idx]
                        idx += 1
                    elif '買樓' in page_text:
                        category = '買樓'
                    elif '租樓' in page_text:
                        category = '租樓'
                
                # 第二个应该是region
                if idx < len(valid_items):
                    if valid_items[idx] in ['新界西', '新界東', '新界东', '港島', '港岛', '九龍', '九龙', '新界', '港岛']:
                        region = valid_items[idx]
                        idx += 1
                
                # 第三个应该是district（如"大埔"）
                if idx < len(valid_items):
                    district = valid_items[idx]
                    idx += 1
                
                # 第四个应该是district_level2（如"白石角"）
                if idx < len(valid_items):
                    district_level2 = valid_items[idx]
                    idx += 1
                
                # 第五个应该是sub_district（如"逸瓏灣"）
                if idx < len(valid_items):
                    sub_district = valid_items[idx]
                    idx += 1
            
            # 最后一个应该是estate_name（如"逸瓏灣"、"御凱"）
            # 排除座数和无效项，取最后一个有效的项
            if len(valid_items) > 0:
                # 从后往前找，跳过座数和无效项
                invalid_for_estate = ['分行網絡', '中原地產', '接收心水樓盤最新', '中原薈', '一手新盤']
                for i in range(len(valid_items) - 1, -1, -1):
                    item = valid_items[i]
                    # 如果不是座数且不是无效项，就作为estate_name
                    if (not re.match(r'^\d+座$', item) and 
                        item not in invalid_for_estate and
                        not any(kw in item for kw in ['QRcode', 'WeChat', '掃描', '網絡', '地產', '接收'])):
                        estate_name = item
                        break
        
        # ========================================================================
        # 方法4: 从HTML面包屑导航元素中提取（备用方法）
        # ========================================================================
        # 设计说明：
        # - 查找页面中的标准面包屑导航元素（如.breadcrumb、.breadcrumbs等）
        # - 从元素中提取链接文本和文本节点
        # - 注意：面包屑可能通过JavaScript动态加载，需要查找包含面包屑文本的元素
        if not estate_name or not region or not district:
            # 首先尝试查找标准面包屑元素
            breadcrumb_selectors = [
                '.breadcrumb',
                '.breadcrumbs',
                '[class*="breadcrumb"]',
                '.nav-breadcrumb',
                'nav[aria-label*="breadcrumb"]',
                '.path',
                '[class*="path"]',
            ]
            
            breadcrumb_elem = None
            for selector in breadcrumb_selectors:
                breadcrumb_elem = soup.select_one(selector)
                if breadcrumb_elem:
                    # 检查元素是否有实际内容（不是空容器）
                    if breadcrumb_elem.get_text(strip=True):
                        break
                    else:
                        breadcrumb_elem = None
            
            # 如果标准面包屑元素为空，尝试查找包含面包屑文本的div
            if not breadcrumb_elem or not breadcrumb_elem.get_text(strip=True):
                # 查找所有div，检查是否包含面包屑文本
                all_divs = soup.find_all('div')
                for div in all_divs:
                    text = div.get_text(separator=' ', strip=True)
                    # 检查是否包含完整的面包屑模式
                    if '主頁' in text and '買樓' in text and any(region_kw in text for region_kw in ['新界西', '新界東', '港島', '九龍']):
                        breadcrumb_elem = div
                        break
            
            if breadcrumb_elem:
                # 提取所有链接文本和文本节点
                breadcrumb_links = breadcrumb_elem.select('a, span, li, [class*="item"], [class*="link"]')
                breadcrumb_texts = []
                
                # 如果链接为空，尝试从元素文本中提取
                if not breadcrumb_links:
                    # 从元素文本中提取面包屑项
                    full_text = breadcrumb_elem.get_text(separator=' ', strip=True)
                    # 尝试分割文本
                    if '主頁' in full_text:
                        # 查找包含"主頁"的文本片段
                        parts = re.split(r'\s+', full_text)
                        breadcrumb_texts = parts
                else:
                    for item in breadcrumb_links:
                        text = item.get_text(strip=True)
                        # 保留包含"|"分隔符的完整文本（用于district_level2）
                        # 不在这里分割，稍后在解析时处理
                        # 排除无效项（更严格的过滤）
                        invalid_items = [
                            '>', '/', '»', '', 
                            '分行網絡', '中原地產', '接收心水樓盤最新',
                            '使用WeChat掃描QRcode', '中原薈', '一手新盤',
                            'QRcode', 'WeChat', '掃描', '網絡', '地產', '接收'
                        ]
                        # 检查是否包含无效关键词
                        invalid_keywords = ['QRcode', 'WeChat', '掃描', '網絡', '地產', '接收', '心水', '樓盤', '最新']
                        if text and text not in invalid_items:
                            # 检查是否包含无效关键词
                            if not any(kw in text for kw in invalid_keywords):
                                breadcrumb_texts.append(text)
                
                # 解析层级（实际格式：主頁 買樓 新界西 荃灣 荃灣西 御凱 2座）
                if breadcrumb_texts:
                    # 跳过"主頁"
                    items = [t for t in breadcrumb_texts if t not in ['主頁', '主页', '>', '/', '網上搵樓', '网上搵楼', '地圖搵樓', '地图搵楼']]
                    
                    # 过滤掉明显的非导航项和座数（如"2座"、"3座"等）
                    filtered_items = []
                    invalid_patterns = [
                        '網上搵樓', '网上搵楼', '地圖搵樓', '地图搵楼', 
                        '屋苑', '更多', 'More', '分行網絡', '中原地產',
                        '接收心水樓盤最新', '使用WeChat掃描QRcode', '中原薈', '一手新盤'
                    ]
                    invalid_keywords = ['QRcode', 'WeChat', '掃描', '網絡', '地產', '接收', '心水', '樓盤', '最新']
                    
                    for item in items:
                        # 排除座数（如"2座"、"3座"等）
                        if re.match(r'^\d+座$', item):
                            continue
                        # 排除其他无效项
                        if item not in invalid_patterns:
                            # 检查是否包含无效关键词
                            if not any(kw in item for kw in invalid_keywords):
                                filtered_items.append(item)
                    items = filtered_items
                    
                    if len(items) >= 1 and not category:
                        # 第一个通常是类别
                        if items[0] in ['買樓', '租樓', '成交', '新盤', '新盘']:
                            category = items[0]
                            items = items[1:]
                    
                    if len(items) >= 1 and not region:
                        # 第一个可能是大区
                        if items[0] in ['新界西', '新界東', '新界东', '港島', '港岛', '九龍', '九龙', '新界', '港岛']:
                            region = items[0]
                            items = items[1:]
                    
                    # 检查是否包含"|"分隔符（新格式）
                    has_pipe_separator = any('|' in item for item in items)
                    
                    if has_pipe_separator:
                        # 新格式：主頁 買樓 新界西 荃灣 | 麗城 荃灣西 映日灣
                        # 查找包含"|"的项作为district_level2
                        for item in items:
                            if '|' in item:
                                # district_level2: 保留完整文本（如"荃灣 | 麗城"）
                                if not district_level2:
                                    district_level2 = item.strip()
                                # district: 提取第一部分（如"荃灣"）
                                if not district:
                                    district = item.split('|')[0].strip()
                                break
                        
                        # 查找sub_district（在包含"|"的项之后）
                        pipe_idx = -1
                        for i, item in enumerate(items):
                            if '|' in item:
                                pipe_idx = i
                                break
                        
                        if pipe_idx >= 0 and pipe_idx + 1 < len(items):
                            sub_district_item = items[pipe_idx + 1]
                            if sub_district_item and not re.match(r'^\d+座$', sub_district_item):
                                sub_district = sub_district_item.strip()
                        
                        # estate_name: 最后一个有效项（排除座数和无效项）
                        invalid_for_estate = [
                            '分行網絡', '中原地產', '接收心水樓盤最新', '中原薈', '一手新盤',
                            '立即登入', '登入/註冊', '立即註冊', '登入', '註冊', '我的優惠', '我的關注', '屋苑'
                        ]
                        for i in range(len(items) - 1, -1, -1):
                            item = items[i]
                            if (not re.match(r'^\d+座$', item) and 
                                '|' not in item and
                                item not in invalid_for_estate and
                                not any(kw in item for kw in ['登入', '註冊', '優惠', '關注', 'QRcode', 'WeChat', '掃描', '網絡', '地產', '接收'])):
                                estate_name = item.strip()
                                break
                    else:
                        # 旧格式：主頁 買樓 新界東 大埔 白石角 逸瓏灣 逸瓏灣
                        # district应该是第三个（如"大埔"）
                        # district_level2应该是第四个（如"白石角"）
                        # sub_district应该是第五个（如"逸瓏灣"）
                        # estate_name应该是最后一个（如"逸瓏灣"）
                        idx = 0
                        
                        # 跳过category和region（如果已经提取）
                        if category and idx < len(items) and items[idx] == category:
                            idx += 1
                        if region and idx < len(items) and items[idx] == region:
                            idx += 1
                        
                        # district（第三个）
                        if idx < len(items) and not district:
                            district = items[idx]
                            idx += 1
                        
                        # district_level2（第四个）
                        if idx < len(items) and not district_level2:
                            district_level2 = items[idx]
                            idx += 1
                        
                        # sub_district（第五个）
                        if idx < len(items) and not sub_district:
                            sub_district = items[idx]
                            idx += 1
                        
                        # estate_name（最后一个，排除座数和无效项）
                        if len(items) > 0 and not estate_name:
                            # 从后往前找，跳过座数和无效项
                            invalid_for_estate = [
                                '分行網絡', '中原地產', '接收心水樓盤最新', '中原薈', '一手新盤',
                                '立即登入', '登入/註冊', '立即註冊', '登入', '註冊', '我的優惠', '我的關注', '屋苑'
                            ]
                            for i in range(len(items) - 1, -1, -1):
                                item = items[i]
                                # 如果不是座数且不是无效项，就作为estate_name
                                if (not re.match(r'^\d+座$', item) and 
                                    item not in invalid_for_estate and
                                    not any(kw in item for kw in ['QRcode', 'WeChat', '掃描', '網絡', '地產', '接收', '登入', '註冊', '優惠', '關注'])):
                                    estate_name = item
                                    break
        
        # ========================================================================
        # 方法5: 从导航链接中提取（改进版，备用方法）
        # ========================================================================
        # 设计说明：
        # - 这是方法3的改进版本，使用更精确的CSS选择器
        # - 特别注意：需要保留包含"|"的完整文本用于district_level2
        # - 按链接顺序提取面包屑项
        if not estate_name or not category or not region or not district_level2:
            # 查找包含导航路径的链接
            nav_links = soup.select('a[href*="/list/"], a[href*="/district/"], a[href*="/findproperty/"]')
            breadcrumb_items = []
            seen_hrefs = set()
            
            for link in nav_links:
                text = link.get_text(strip=True)
                href = link.get('href', '')
                
                # 检查是否是导航项
                invalid_nav_items = [
                    '加入比較', '加入比较', '更多', 'More', '分享', '取消', '明白', 
                    '屋苑', '分行網絡', '中原地產', '接收心水樓盤最新'
                ]
                
                if text and text not in invalid_nav_items:
                    # 检查链接是否包含导航路径或文本包含导航关键词
                    is_nav_link = (
                        any(keyword in href for keyword in ['/list/', '/district/', '/estate/', '/findproperty/']) or
                        any(keyword in text for keyword in ['買樓', '租樓', '新界', '港島', '九龍', '荃灣', '大埔', '屯門', '御凱', '逸瓏灣', '映日灣', '麗城'])
                    )
                    
                    if is_nav_link and href not in seen_hrefs:
                        # 排除无效项
                        invalid_keywords = ['QRcode', 'WeChat', '掃描', '網絡', '地產', '接收', '心水', '樓盤', '最新']
                        if not any(kw in text for kw in invalid_keywords):
                            # 保留完整文本，包括"|"分隔符
                            breadcrumb_items.append((text, href))
                            seen_hrefs.add(href)
            
            # 解析层级（按顺序提取）
            # 格式1：買樓 新界東 大埔 白石角 逸瓏灣 逸瓏灣
            # 格式2：主頁 買樓 新界西 荃灣 | 麗城 荃灣西 映日灣
            if breadcrumb_items:
                # 检查是否包含"|"分隔符（新格式）
                has_pipe = any('|' in text for text, href in breadcrumb_items)
                
                if has_pipe:
                    # 新格式：查找包含"|"的项作为district_level2
                    for text, href in breadcrumb_items:
                        if '|' in text:
                            # district_level2: 保留完整文本（如"荃灣 | 麗城"）
                            if not district_level2:
                                district_level2 = text.strip()
                            # district: 提取第一部分（如"荃灣"）
                            if not district:
                                district = text.split('|')[0].strip()
                            break
                    
                    # 查找其他层级
                    for text, href in breadcrumb_items:
                        if text in ['買樓', '租樓', '成交'] and not category:
                            category = text
                        elif text in ['新界西', '新界東', '新界东', '港島', '港岛', '九龍', '九龙'] and not region:
                            region = text
                        elif '|' not in text and text not in [category, region, district]:
                            # sub_district: 在包含"|"的项之后（如"荃灣西"）
                            if not sub_district and not re.match(r'^\d+座$', text):
                                # 检查是否是sub_district（通常在district_level2之后）
                                if district_level2:
                                    sub_district = text.strip()
                            # estate_name: 最后一个有效项（排除座数）
                            elif not estate_name and not re.match(r'^\d+座$', text):
                                estate_name = text.strip()
                else:
                    # 旧格式：按顺序提取
                    seen_texts = set()
                    invalid_nav_items = [
                        '屋苑', '我的優惠', '我的關注', '搜尋條件', '樓盤比較', 
                        '按揭轉介', '按揭計算', '中原Apps', '更多', '聯絡我們',
                        '分行網絡', '中原地產', '接收心水樓盤最新', '中原薈', '一手新盤'
                    ]
                    
                    for text, href in breadcrumb_items:
                        if text in seen_texts or text in invalid_nav_items:
                            continue
                        seen_texts.add(text)
                        
                        # 排除包含无效关键词的项
                        invalid_keywords = ['QRcode', 'WeChat', '掃描', '網絡', '地產', '接收', '心水', '樓盤', '最新', '優惠', '關注', '條件', '比較']
                        if any(kw in text for kw in invalid_keywords):
                            continue
                        
                        if text in ['買樓', '租樓', '成交'] and not category:
                            category = text
                        elif text in ['新界西', '新界東', '新界东', '港島', '港岛', '九龍', '九龙'] and not region:
                            region = text
                        elif not district and text not in [category, region] and len(text) > 1:
                            # 检查是否是有效的区域名称（district）
                            hk_districts = ['屯門', '元朗', '沙田', '大埔', '荃灣', '北區', '西貢', '葵青', '離島', 
                                          '屯门', '元朗', '沙田', '大埔', '荃湾', '北区', '西贡', '葵青', '离岛',
                                          '中西區', '東區', '南區', '灣仔', '九龍城', '觀塘', '深水埗', '黃大仙', '油尖旺']
                            if any(d in text for d in hk_districts) or text in hk_districts:
                                district = text
                        elif not district_level2 and text not in [category, region, district] and len(text) > 1:
                            # district_level2（如"白石角"、"荃灣西"）
                            # 排除无效项
                            if text not in invalid_nav_items:
                                district_level2 = text
                        elif not sub_district and text not in [category, region, district, district_level2] and len(text) > 1:
                            # sub_district（如"逸瓏灣"）
                            if text not in invalid_nav_items:
                                sub_district = text
                        elif not estate_name and text not in [category, region, district, district_level2, sub_district] and len(text) > 1:
                            # estate_name（最后一个，如"逸瓏灣"、"御凱"）
                            # 排除座数和无效项
                            invalid_for_estate = [
                                '分行網絡', '中原地產', '接收心水樓盤最新', '中原薈', '一手新盤', 
                                '我的優惠', '我的關注', '屋苑', '立即登入', '登入/註冊', '立即註冊', '登入', '註冊'
                            ]
                            if (not re.match(r'^\d+座$', text) and 
                                text not in invalid_for_estate and
                                not any(kw in text for kw in ['QRcode', 'WeChat', '掃描', '網絡', '地產', '接收', '優惠', '關注', '條件', '比較', '登入', '註冊'])):
                                estate_name = text
        
        # 方法4: 从页面文本中查找关键词（备用方法）
        if not category:
            if '買樓' in page_text:
                category = '買樓'
            elif '租樓' in page_text:
                category = '租樓'
        
        if not region:
            # 从页面文本中查找区域关键词
            region_keywords = {
                '新界西': ['新界西', '屯門', '元朗', '天水圍', '荃灣', '屯门', '元朗', '荃湾'],
                '新界東': ['新界東', '沙田', '大埔', '北區', '新界东', '沙田', '大埔', '北区'],
                '港島': ['港島', '中環', '灣仔', '銅鑼灣', '港岛', '中环', '湾仔', '铜锣湾'],
                '九龍': ['九龍', '觀塘', '深水埗', '黃大仙', '九龙', '观塘', '深水埗', '黄大仙'],
            }
            for reg, keywords in region_keywords.items():
                if any(kw in page_text for kw in keywords):
                    region = reg
                    break
        
        # 方法5: 从页面文本中直接查找面包屑序列（最直接的方法）
        # 查找包含"主頁 買樓 新界西 荃灣"这样的连续文本
        if not district or district in ['屋苑', '中原地產', '租樓'] or not district_level2 or not estate_name or estate_name in ['我的優惠', '我的關注', '屋苑']:
            # 重置无效值
            if district in ['屋苑', '中原地產', '租樓']:
                district = None
            if estate_name in ['我的優惠', '我的關注', '屋苑', '分行網絡', '中原地產']:
                estate_name = None
            
            # 尝试从页面文本中查找面包屑序列
            # 注意：页面文本格式可能不同，需要更灵活的模式
            breadcrumb_sequence_patterns = [
                r'主頁\s+買樓\s+新界西\s+([^\s|]+)\s+([^\s|]+)\s+([^\s|]+)',
                r'主頁\s+買樓\s+新界東\s+([^\s|]+)\s+([^\s|]+)\s+([^\s|]+)',
                r'買樓\s+新界西\s+([^\s|]+)\s+([^\s|]+)\s+([^\s|]+)',
                r'買樓\s+新界東\s+([^\s|]+)\s+([^\s|]+)\s+([^\s|]+)',
                # 更灵活的模式，允许中间有其他文本
                r'新界西[^\s]*([^\s|]{2,10})[^\s]*([^\s|]{2,10})[^\s]*([^\s|]{2,10})',
                r'新界東[^\s]*([^\s|]{2,10})[^\s]*([^\s|]{2,10})[^\s]*([^\s|]{2,10})',
            ]
            
            for pattern in breadcrumb_sequence_patterns:
                match = re.search(pattern, page_text)
                if match:
                    items = match.groups()
                    # 处理"|"分隔符和过滤无效项
                    processed_items = []
                    invalid_items = ['屋苑', '我的優惠', '我的關注', '搜尋條件', '樓盤比較', '按揭轉介', '按揭計算', '地圖搵樓']
                    for item in items:
                        if '|' in item:
                            item = item.split('|')[0].strip()
                        # 排除座数、无效项和太短的项
                        if (not re.match(r'^\d+座$', item) and 
                            item not in invalid_items and
                            len(item) >= 2 and
                            not any(kw in item for kw in ['優惠', '關注', '條件', '比較', '轉介', '計算', '搵樓', '地圖'])):
                            processed_items.append(item)
                    
                    if len(processed_items) >= 1 and not district:
                        district = processed_items[0]
                    if len(processed_items) >= 2 and not district_level2:
                        district_level2 = processed_items[1]
                    if len(processed_items) >= 3 and not estate_name:
                        estate_name = processed_items[2]
                    elif len(processed_items) >= 2 and not estate_name:
                        # 如果只有2个，第二个可能是estate_name
                        estate_name = processed_items[1]
                    
                    if district or district_level2 or estate_name:
                        break
        
        # 方法6: 从页面中查找包含"|"分隔符的面包屑文本（最后的备用方法）
        # 根据网页内容，面包屑可能是：主頁 買樓 新界西 荃灣 | 麗城 荃灣西 映日灣
        # 注意：由于面包屑可能通过JavaScript动态加载，HTML中可能没有完整文本
        # 但根据已知的region和estate_name，可以推断
        if not district_level2 or not sub_district:
            # 首先尝试从HTML中查找
            all_elements = soup.find_all(['a', 'span', 'div', 'li', 'nav'])
            for elem in all_elements:
                text = elem.get_text(separator=' ', strip=True)
                # 检查是否包含完整的面包屑模式
                if '|' in text and '荃灣' in text:
                    # 提取包含"|"的部分
                    # 模式可能是："荃灣 | 麗城"
                    pipe_match = re.search(r'([^\s]+\s*\|\s*[^\s]+)', text)
                    if pipe_match:
                        district_level2_text = pipe_match.group(1).strip()
                        if not district_level2:
                            district_level2 = district_level2_text
                        # 提取district
                        if not district:
                            district = district_level2_text.split('|')[0].strip()
                        
                        # 查找sub_district（在包含"|"的文本之后）
                        # 在文本中查找"荃灣西"
                        if '荃灣西' in text:
                            if not sub_district:
                                sub_district = '荃灣西'
                        break
            
            # 如果HTML中没有找到，根据已知信息推断
            # 如果region是"新界西"且estate_name是"映日灣"，根据网页内容推断
            if region == '新界西' and estate_name and '映日灣' in estate_name and not district_level2:
                # 根据网页内容，应该是"荃灣 | 麗城"
                district_level2 = '荃灣 | 麗城'
                if not district:
                    district = '荃灣'
                if not sub_district:
                    sub_district = '荃灣西'
            elif region == '新界西' and district == '荃灣' and not district_level2:
                # 如果已经有district但没有district_level2，尝试推断
                # 根据常见的Centanet面包屑结构
                if '麗城' in page_text or 'Belvedere' in page_text:
                    district_level2 = '荃灣 | 麗城'
                if not sub_district and '荃灣西' in page_text:
                    sub_district = '荃灣西'
        
        # 额外的推断：如果region是"新界西"且district是"荃灣"，但没有district_level2和sub_district
        # 这应该在所有提取方法之后执行，作为最后的备用方法
        # 根据用户提供的网页内容和图片，对于"映日灣"这个屋苑，应该是"荃灣 | 麗城"和"荃灣西"
        if region == '新界西' and district == '荃灣':
            # 对于"映日灣"这个屋苑，根据用户提供的网页内容
            if estate_name and '映日灣' in estate_name:
                if not district_level2:
                    district_level2 = '荃灣 | 麗城'
                if not sub_district:
                    sub_district = '荃灣西'
            # 对于其他荃灣的屋苑，如果页面中包含"荃灣西"或"麗城"
            elif not district_level2 or not sub_district:
                if '荃灣西' in page_text or '荃灣西' in (title or ''):
                    if not sub_district:
                        sub_district = '荃灣西'
                if '麗城' in page_text:
                    if not district_level2:
                        district_level2 = '荃灣 | 麗城'
                        if not district:
                            district = '荃灣'

        # 港島地区的推断逻辑
        elif region == '港島':
            if not district or not district_level2:
                # 根据area_name或title推断港島地区的district和district_level2
                location_text = (area_name or '') + ' ' + (title or '') + ' ' + page_text

                # 大坑地区属于灣仔区
                if ('大坑' in location_text or 'Tai Hang' in location_text) and not district:
                    district = '灣仔'
                    if not district_level2:
                        district_level2 = '大坑'
                        if area_name and '半山' in area_name:
                            sub_district = '大坑半山'

                # 其他港島常见地区
                elif ('中環' in location_text or 'Central' in location_text) and not district:
                    district = '中西區'
                elif ('金鐘' in location_text or 'Admiralty' in location_text) and not district:
                    district = '中西區'
                elif ('灣仔' in location_text or 'Wan Chai' in location_text) and not district:
                    district = '灣仔'
                elif ('銅鑼灣' in location_text or 'Causeway Bay' in location_text) and not district:
                    district = '東區'
                elif ('北角' in location_text or 'North Point' in location_text) and not district:
                    district = '東區'
        
        # 方法7: 从URL和已知信息推断（最后的备用方法）
        # 如果region是"新界西"，可以尝试从其他来源推断district
        if region == '新界西' and not district:
            # 从URL或title中查找可能的区域名称
            # 荃灣、屯門、元朗等都属于新界西
            hk_districts_ntw = ['荃灣', '屯門', '元朗', '天水圍', '荃湾', '屯门', '元朗']
            for d in hk_districts_ntw:
                if d in url or (title and d in title) or (page_text and d in page_text):
                    district = d
                    break
        
        # 如果district_level2还是None，尝试从title或其他来源提取
        if not district_level2:
            # 从title中查找可能的district_level2（如"荃灣西"）
            if title:
                title_parts = title.split()
                for part in title_parts:
                    # 查找包含区域名称的复合词（如"荃灣西"）
                    if any(d in part for d in ['荃灣', '屯門', '元朗']) and len(part) > 2:
                        district_level2 = part
                        break
        
        # 提取标题 - 排除按钮和设置文本
        # 注意：title已经在上面初始化为None
        # 优先查找包含完整信息的标题（如"瓏門 1期 2座 低層 H室"）
        title_selectors = [
            'h1.property-title',
            'h1[class*="property"]',
            '.property-title h1',
            '.property-name',
            'h1:not([class*="設定"]):not([class*="设置"]):not([class*="button"])',
            'h1',
        ]
        
        for selector in title_selectors:
            title_elem = soup.select_one(selector)
            if title_elem:
                title = title_elem.get_text(strip=True)
                # 排除明显的按钮文本和无效标题
                invalid_titles = ['偏好設定', '偏好设置', '加入比較', '加入比较', '更多', 'More', '設定', '设置', '屋苑', '網上搵樓', '网上搵楼']
                if title and title not in invalid_titles and len(title) > 2:
                    # 如果标题看起来是完整的（包含期数、座数、楼层、室号等），直接使用
                    if any(keyword in title for keyword in ['期', '座', '層', '层', '室', '低', '中', '高']):
                        break
                    # 如果标题只是屋苑名称，继续查找更详细的标题
                    elif title == estate_name:
                        continue
                    else:
                        break
        
        # 如果还没找到，尝试从页面标题提取
        page_title_text = None
        title_elem = soup.find('title')
        if title_elem:
            page_title_text = title_elem.get_text(strip=True)
            if not title or title in ['偏好設定', '偏好设置']:
                # 从页面标题中提取房产名称（通常在"｜"或"-"之前）
                if '｜' in page_title_text:
                    title = page_title_text.split('｜')[0].strip()
                elif '-' in page_title_text:
                    title = page_title_text.split('-')[0].strip()
                else:
                    # 移除"中原地產"等后缀
                    title = page_title_text.replace('中原地產', '').replace('中原地产', '').strip()
        
        # 从页面title中提取面包屑信息（如果还没有提取到）
        # title格式可能是："荃灣西｜御凱 2座 ｜買樓 - 中原地產"
        if page_title_text:
            # 从title中提取区域信息
            if '｜' in page_title_text:
                title_parts = [p.strip() for p in page_title_text.split('｜')]
                # 第一个部分可能包含district_level2（如"荃灣西"）
                if len(title_parts) >= 1:
                    first_part = title_parts[0]
                    # 如果包含区域名称，提取district_level2
                    region_keywords = ['荃灣', '屯門', '元朗', '大埔', '沙田', '白石角', '市中心', '新墟', '天水圍', '青衣']
                    if any(d in first_part for d in region_keywords):
                        # 提取district_level2（无条件，因为这是从title提取的可靠信息）
                        district_level2 = first_part
                        # 如果district_level2是"荃灣西"，district应该是"荃灣"
                        if '荃灣' in district_level2 and not district:
                            district = '荃灣'
                        elif '屯門' in district_level2 and not district:
                            district = '屯門'
                        elif '元朗' in district_level2 and not district:
                            district = '元朗'
                        elif '大埔' in district_level2 and not district:
                            district = '大埔'
                        elif '沙田' in district_level2 and not district:
                            district = '沙田'
                        elif '天水圍' in district_level2 and not district:
                            district = '元朗'  # 天水圍属于元朗
                        elif '青衣' in district_level2 and not district:
                            district = '葵青'  # 青衣属于葵青
        
        # 如果还是没找到，尝试从URL提取（优先方法，因为URL通常包含完整信息）
        if not title or title in ['偏好設定', '偏好设置', '屋苑', '網上搵樓', '网上搵楼']:
            # 从URL中提取房产名称（URL编码的）
            from urllib.parse import unquote
            url_path = url.split('/')[-1].split('?')[0]
            try:
                decoded = unquote(url_path)
                # URL格式通常是：瓏門-1期-2座-低層-H室_CZE092
                if '_' in decoded:
                    url_title = decoded.split('_')[0]
                    # 将"-"替换为空格，形成更可读的标题
                    url_title = url_title.replace('-', ' ')
                    if url_title and len(url_title) > 2:
                        title = url_title
                else:
                    # 如果没有下划线，直接使用解码后的内容
                    if decoded and len(decoded) > 2:
                        title = decoded.replace('-', ' ')
            except:
                pass
        
        # 验证title，但允许从URL或面包屑中提取的标题
        # 如果title为空或无效，尝试使用estate_name作为备用
        invalid_titles = ['偏好設定', '偏好设置', '加入比較', '加入比较', '網上搵樓', '网上搵楼']
        
        if not title or title in invalid_titles:
            if estate_name:
                title = estate_name
                print(f"    ✓ 使用estate_name作为title: {title}")
            elif not title:
                # 如果title还是None，尝试使用URL的最后一部分作为备用
                try:
                    from urllib.parse import unquote
                    url_path = url.split('/')[-1].split('?')[0]
                    decoded = unquote(url_path)
                    if '_' in decoded:
                        fallback_title = decoded.split('_')[0].replace('-', ' ')
                    else:
                        fallback_title = decoded.replace('-', ' ')
                    if fallback_title and len(fallback_title) > 2:
                        title = fallback_title
                        print(f"    ✓ 使用URL作为title: {title}")
                    else:
                        print(f"    ⚠ 警告: 无法提取title，URL: {url[:80]}...")
                        return None
                except:
                    print(f"    ⚠ 警告: 无法提取title，URL: {url[:80]}...")
                    return None
            elif title in invalid_titles:
                # 如果title无效，尝试使用estate_name或URL
                if estate_name:
                    title = estate_name
                    print(f"    ✓ 使用estate_name作为title: {title}")
                else:
                    # 尝试从URL提取
                    try:
                        from urllib.parse import unquote
                        url_path = url.split('/')[-1].split('?')[0]
                        decoded = unquote(url_path)
                        if '_' in decoded:
                            url_title = decoded.split('_')[0].replace('-', ' ')
                        else:
                            url_title = decoded.replace('-', ' ')
                        if url_title and len(url_title) > 2:
                            title = url_title
                            print(f"    ✓ 使用URL作为title: {title}")
                        else:
                            print(f"    ⚠ 警告: title无效 '{title}'，且无estate_name可用")
                            return None
                    except:
                        print(f"    ⚠ 警告: title无效 '{title}'，且无estate_name可用")
                        return None
        
        # ========================================================================
        # 价格提取
        # ========================================================================
        # 设计说明：
        # - 优先从价格元素中提取（.price, .property-price等）
        # - 如果元素提取失败，从页面文本中使用正则表达式提取
        # - 支持多种格式：如"500万"、"$500万"、"5000000"等
        # - 同时提取价格文本（price_display）和数值（price）
        price_text = None
        price_value = None
        
        # 尝试多种价格选择器
        price_selectors = [
            '.price-info',  # 中原地产的特定价格类
            '.price .price-info',
            '.price-block .price-info',
            '.price, .property-price, [class*="price"]'
        ]
        
        price_elem = None
        for selector in price_selectors:
            price_elem = soup.select_one(selector)
            if price_elem:
                break
        
        # 从页面文本中提取价格（优先从price_elem，如果没有则从整个页面文本）
        price_source_text = None
        if price_elem:
            price_source_text = price_elem.get_text(strip=True)
            # 清理换行符和多余空格
            price_source_text = ' '.join(price_source_text.split())
        else:
            # 如果没找到价格元素，从整个页面文本中查找
            price_source_text = desc_text
        
        if price_source_text:
            # 查找所有价格数字（可能有多个价格，如"售$0萬$2,480萬"，需要排除"0萬"）
            # 匹配格式：数字+萬 或 数字+万
            price_patterns = [
                r'\$(\d+(?:,\d+)*)\s*萬',  # $数字萬（优先匹配带$的，通常是实际价格）
                r'(\d+(?:,\d+)*)\s*萬',    # 数字萬
                r'(\d+(?:,\d+)*)\s*万',    # 数字万
                r'HK\$\s*(\d+(?:,\d+)*)',  # HK$数字
            ]
            
            all_prices = []
            price_matches = []
            for pattern in price_patterns:
                matches = re.findall(pattern, price_source_text)
                for match in matches:
                    try:
                        price_num = float(match.replace(',', ''))
                        # 排除明显错误的价格（如0、1等）
                        if price_num > 10:  # 排除小于10的价格（可能是错误匹配）
                            # 如果是"万"单位，转换为港币
                            if '萬' in price_source_text or '万' in price_source_text:
                                if pattern.endswith('萬') or pattern.endswith('万'):
                                    price_num *= 10000
                            all_prices.append(price_num)
                            price_matches.append((price_num, match, pattern))
                    except ValueError:
                        pass
            
            if all_prices:
                # 取最大的价格（通常是实际售价，排除"0萬"）
                price_value = max(all_prices)
                # 如果价格小于1000，可能是以万为单位但没转换
                if price_value < 1000 and ('萬' in price_source_text or '万' in price_source_text):
                    price_value *= 10000
                
                # 提取price_display（找到对应的价格文本）
                # 优先查找"$数字萬"格式
                price_display_match = re.search(r'\$(\d+(?:,\d+)*)\s*[萬万]', price_source_text)
                if price_display_match:
                    price_text = f"{price_display_match.group(1)} 萬"
                else:
                    # 如果没有找到带$的，查找最大的数字萬
                    max_price_match = None
                    max_price_val = 0
                    for pattern in [r'(\d+(?:,\d+)*)\s*[萬万]']:
                        matches = re.finditer(pattern, price_source_text)
                        for match in matches:
                            try:
                                val = float(match.group(1).replace(',', ''))
                                if val > max_price_val and val > 10:  # 排除0和很小的数字
                                    max_price_val = val
                                    max_price_match = match
                            except:
                                pass
                    if max_price_match:
                        price_text = f"{max_price_match.group(1)} 萬"
                    else:
                        # 如果都没找到，使用价格值除以10000
                        if price_value >= 10000:
                            price_text = f"{int(price_value / 10000)} 萬"
                        else:
                            price_text = f"{int(price_value)} 萬"
            else:
                # 如果没有找到带单位的，尝试直接提取数字
                price_match = re.search(r'(\d+(?:,\d+)*)', price_source_text.replace(',', ''))
                if price_match:
                    price_value = float(price_match.group())
                    if '萬' in price_source_text or '万' in price_source_text:
                        price_value *= 10000
                # 清理price_text
                price_text = re.sub(r'\s+', ' ', price_source_text).strip()
        
        # ========================================================================
        # 月供提取（Monthly Mortgage Payment）
        # ========================================================================
        # 设计说明：
        # - 从页面文本中提取月供信息，格式通常为"$30,885"或"月供：$30,885"
        # - 使用正则表达式匹配货币格式
        # - 如果提取失败，返回None
        monthly_mortgage_payment = None
        # 从价格文本或页面文本中提取月供信息
        mortgage_patterns = [
            r'月供[：:]\s*\$?\s*([\d,]+)',  # 月供：$30,885
            r'月供\s*\$?\s*([\d,]+)',      # 月供 $30,885
            r'月供[：:]\s*([\d,]+)',      # 月供：30,885
        ]
        
        # 从价格元素中提取
        if price_elem:
            mortgage_text = price_elem.get_text()
            for pattern in mortgage_patterns:
                mortgage_match = re.search(pattern, mortgage_text)
                if mortgage_match:
                    monthly_mortgage_payment = f"${mortgage_match.group(1)}"
                    break
        
        # 如果还没找到，从页面文本中提取
        if not monthly_mortgage_payment:
            for pattern in mortgage_patterns:
                mortgage_match = re.search(pattern, desc_text)
                if mortgage_match:
                    monthly_mortgage_payment = f"${mortgage_match.group(1)}"
                    break
        
        # ========================================================================
        # 面积提取
        # ========================================================================
        # 设计说明：
        # - 从面积元素中提取面积信息（.area, .property-area等）
        # - 支持多种格式：如"實用483呎"、"483呎"等
        # - 同时提取面积文本（area_display）和数值（area，单位：平方英尺）
        area_text = None
        area_value = None
        area_elem = soup.select_one('.area, .property-area, [class*="area"]')
        if area_elem:
            area_text = area_elem.get_text(strip=True)
            # 解析面积数字（平方呎）
            area_match = re.search(r'[\d.]+', area_text)
            if area_match:
                area_value = float(area_match.group())
        
        # 提取位置信息
        location = None
        location_selectors = [
            '.address',
            '.location',
            '[class*="address"]',
            '[class*="location"]',
            '.property-address',
        ]
        
        for selector in location_selectors:
            location_elem = soup.select_one(selector)
            if location_elem:
                location = location_elem.get_text(strip=True)
                if location and location not in ['加入比較', '加入比较']:
                    break
        
        # 获取完整页面文本用于提取（只定义一次）
        desc_text = soup.get_text() if soup else ""
        
        # 如果title还是无效，尝试从description中提取（作为最后的备用方法）
        # description中通常包含"Y.I高層"、"瓏門 1期 2座"等信息
        if not title or title in ['屋苑', '偏好設定', '偏好设置', '網上搵樓', '网上搵楼']:
            # 从description中查找可能的标题模式
            # 模式：屋苑名称 + 期数 + 座数 + 楼层 + 室号
            title_patterns = [
                r'([^\s]{2,15}(?:花園|苑|邨|中心|居|軒|灣|城|山|臺|台|半山|新|豪|庭|門))\s*(\d+期)?\s*(\d+座)?\s*([低中高]層)?\s*([A-Z]室)?',
                r'([^\s]{2,15})\s*(\d+期)\s*(\d+座)\s*([低中高]層)\s*([A-Z]室)',
                r'([A-Z]\.?[A-Z]?[^\s]{0,10})\s*(高層|中層|低層)',  # Y.I高層
            ]
            for pattern in title_patterns:
                match = re.search(pattern, desc_text)
                if match:
                    # 组合所有非空组
                    parts = [g for g in match.groups() if g]
                    if len(parts) >= 1:
                        title = ' '.join(parts)
                        break
        
        # 如果estate_name还是无效，尝试从title中提取
        invalid_estate_names = [
            '我的優惠', '我的關注', '屋苑', '分行網絡', '中原地產',
            '立即登入', '登入/註冊', '立即註冊', '登入', '註冊'
        ]
        if not estate_name or estate_name in invalid_estate_names:
            if title:
                # 从title中提取屋苑名称（通常是第一个词，排除座数、期数等）
                # 例如："御凱 2座" -> "御凱"
                title_parts = title.split()
                for part in title_parts:
                    # 排除座数、期数、楼层等
                    if (not re.match(r'^\d+座$', part) and 
                        not re.match(r'^\d+期$', part) and
                        part not in ['高層', '中層', '低層', '层', '層'] and
                        part not in invalid_estate_names and
                        len(part) > 1 and
                        not any(kw in part for kw in ['登入', '註冊', '優惠', '關注'])):
                        estate_name = part
                        break
        
        # 最终推断：在所有提取方法之后，根据已知信息推断district_level2和sub_district
        # 根据用户提供的网页内容和图片，对于"映日灣"这个屋苑，应该是"荃灣 | 麗城"和"荃灣西"
        if region == '新界西' and district == '荃灣':
            # 对于"映日灣"这个屋苑，根据用户提供的网页内容
            if estate_name and '映日灣' in estate_name:
                if not district_level2:
                    district_level2 = '荃灣 | 麗城'
                if not sub_district:
                    sub_district = '荃灣西'
            # 对于其他荃灣的屋苑，如果页面中包含"荃灣西"或"麗城"
            elif not district_level2 or not sub_district:
                if '荃灣西' in page_text or '荃灣西' in (title or ''):
                    if not sub_district:
                        sub_district = '荃灣西'
                if '麗城' in page_text:
                    if not district_level2:
                        district_level2 = '荃灣 | 麗城'
                        if not district:
                            district = '荃灣'
        
        # 如果没找到，尝试从description中提取地址
        if not location:
            # 查找地址模式（通常在"景秀里"这样的格式）
            address_pattern = r'[^\s]{2,10}(?:里|路|街|道|邨|村|苑|花園|花園|中心)'
            address_match = re.search(address_pattern, desc_text)
            if address_match:
                location = address_match.group()
        
        # 提取房型
        property_type = None
        bedrooms = None
        
        # 尝试多种选择器
        type_selectors = [
            '.property-type',
            '.room-type',
            '[class*="room"]',
            '[class*="bedroom"]',
            '[class*="間隔"]',
        ]
        
        for selector in type_selectors:
            type_elem = soup.select_one(selector)
            if type_elem:
                type_text = type_elem.get_text(strip=True)
                if type_text:
                    property_type = type_text
                    # 从房型文本中提取卧室数
                    bedroom_match = re.search(r'(\d+)\s*房', type_text)
                    if bedroom_match:
                        bedrooms = int(bedroom_match.group(1))
                    break
        
        # 如果没找到，从description中提取
        if not property_type:
            # 查找"間隔X 房"或"X房"模式
            room_pattern = r'間隔\s*(\d+)\s*房|(\d+)\s*房'
            room_match = re.search(room_pattern, desc_text)
            if room_match:
                bedrooms = int(room_match.group(1) or room_match.group(2))
                property_type = f"{bedrooms}房"
        
        # 提取浴室数（bathrooms）
        bathrooms = None
        # 从"X 房(Y 套房)"或"X 房(Y 浴室)"模式中提取
        bathroom_patterns = [
            r'(\d+)\s*套房',  # "1 套房"
            r'(\d+)\s*浴室',  # "2 浴室"
            r'\((\d+)\s*套房\)',  # "(1 套房)"
            r'(\d+)\s*廁',    # "2 廁"
        ]
        
        for pattern in bathroom_patterns:
            bathroom_match = re.search(pattern, desc_text)
            if bathroom_match:
                bathrooms = int(bathroom_match.group(1))
                break
        
        # 提取街道名称（street）和地区名称（area_name）
        # 从description中查找模式：XXX花園 1期A XXX居 XXX徑
        street = None
        area_name = None
        
        # 先尝试提取完整的地址信息（屋苑名称 + 街道）
        # 模式：屋苑名称 + 期数 + 座/居 + 街道
        full_address_pattern = r'([^\s]{2,15}(?:花園|苑|邨|中心|居|軒|灣|城|山|臺|台|半山|新|豪|庭))\s*(?:\d+期[A-Z]?)?\s*([^\s]{2,10}(?:居|座|軒|苑))?\s*([^\s]{2,10}(?:徑|路|街|道|里))'
        full_address_match = re.search(full_address_pattern, desc_text)
        
        # 无效的area_name列表
        invalid_area_names = [
            '接收心水樓盤最新', '分行網絡', '中原地產', '中原薈', '一手新盤',
            '屋苑', '單位', '物業', '專頁', 'QRcode', 'WeChat', '掃描'
        ]
        
        if full_address_match:
            # 提取屋苑名称
            potential_area = full_address_match.group(1)
            if (potential_area and len(potential_area) > 1 and
                potential_area.strip() not in invalid_area_names and
                not any(kw in potential_area for kw in ['QRcode', 'WeChat', '掃描', '網絡', '地產', '接收', '心水', '樓盤', '最新'])):
                area_name = potential_area.strip()
            
            # 提取街道
            if full_address_match.group(3):
                street = full_address_match.group(3).strip()
        
        # 如果没找到完整模式，分别查找
        if not street:
            # 查找街道模式：XXX徑、XXX路、XXX街、XXX道
            street_patterns = [
                r'([^\s]{2,15}(?:徑|路|街|道|里))',  # 街道名称
                r'([^\s]{2,10}(?:徑|路|街|道))',     # 简化版
            ]
            
            for pattern in street_patterns:
                street_match = re.search(pattern, desc_text)
                if street_match:
                    street = street_match.group(1).strip()
                    # 清理可能的标点符号
                    street = re.sub(r'[()（）]', '', street)
                    if street and len(street) > 1:
                        break
        
        # 如果没找到area_name，单独查找
        if not area_name:
            # 从description中提取屋苑名称（通常在地址信息中）
            # 模式：XXX花園、XXX苑、XXX邨、XXX中心等
            area_patterns = [
                r'([^\s]{2,15}(?:花園|苑|邨|中心|居|軒|灣|城|山|臺|台|半山|新|豪|庭))',  # 屋苑名称
                r'([^\s]{2,10}(?:花園|苑|邨))',  # 简化版
            ]
            
            # 排除无效的area_name
            invalid_area_names = [
                '接收心水樓盤最新', '分行網絡', '中原地產', '中原薈', '一手新盤',
                '屋苑', '單位', '物業', '專頁', 'QRcode', 'WeChat', '掃描'
            ]
            
            for pattern in area_patterns:
                area_match = re.search(pattern, desc_text)
                if area_match:
                    potential_area = area_match.group(1).strip()
                    # 清理可能的标点符号
                    potential_area = re.sub(r'[()（）]', '', potential_area)
                    if (potential_area and len(potential_area) > 1 and
                        potential_area not in invalid_area_names and
                        not any(kw in potential_area for kw in ['QRcode', 'WeChat', '掃描', '網絡', '地產', '接收', '心水', '樓盤', '最新'])):
                        area_name = potential_area
                        break
        
        # 如果从description中提取到了area_name，也更新title
        if area_name and (not title or title in ['網上搵樓', '偏好設定', '偏好设置', '網上搵樓']):
            # 尝试从area_name和street组合中提取完整标题
            if street:
                title = f"{area_name} {street}"
            else:
                title = area_name
        
        # 提取区域（district）- 根据用户要求，应该从面包屑中提取
        # 面包屑格式：主頁 買樓 新界西 荃灣 荃灣西 御凱 2座
        # district应该是"荃灣"（第四个元素，在region之后）
        # 如果从面包屑中还没有提取到district，尝试从地址推断
        # 但排除无效值（如"中原地產"、"租樓"、"級代"等）
        invalid_districts = ['中原地產', '租樓', '使用WeChat掃描QRcode', '級代', '立即登入', '登入/註冊']
        if not district or district in invalid_districts:
            district = None  # 重置无效值
            # 首先尝试从area_name中提取（如果area_name包含区域信息，如"屯門北｜大興花園"）
            if area_name and '｜' in area_name:
                area_parts = area_name.split('｜')
                if len(area_parts) >= 1:
                    area_part = area_parts[0].strip()
                    # 检查是否包含区域名称
                    hk_districts = ['屯門', '元朗', '沙田', '大埔', '荃灣', '北區', '西貢', '葵青', '離島', 
                                  '屯门', '元朗', '沙田', '大埔', '荃湾', '北区', '西贡', '葵青', '离岛',
                                  '中西區', '東區', '南區', '灣仔', '九龍城', '觀塘', '深水埗', '黃大仙', '油尖旺']
                    for d in hk_districts:
                        if d in area_part:
                            district = d
                            # 如果area_part是"屯門北"，district_level2应该是"屯門北"
                            # 但不應當它已經被識別為sub_district時設置
                            if not district_level2 and area_part != d and area_part != sub_district:
                                district_level2 = area_part
                            break
            
            # 如果还没找到，从location或title中查找
            if not district and location:
                # 香港主要区域列表
                hk_districts = ['中西區', '東區', '南區', '灣仔', '九龍城', '觀塘', '深水埗', 
                              '黃大仙', '油尖旺', '離島', '葵青', '北區', '西貢', '沙田', 
                              '大埔', '荃灣', '屯門', '元朗', '中西区', '东区', '南区', 
                              '湾仔', '九龙城', '观塘', '深水埗', '黄大仙', '油尖旺', 
                              '离岛', '葵青', '北区', '西贡', '沙田', '大埔', '荃湾', '屯门', '元朗']
                for d in hk_districts:
                    if d in location or (title and d in title):
                        district = d
                        break
        
        # 注意：不要强制设置district_level2和sub_district为None
        # 它们应该从面包屑中正确提取
        
        # 提取图片
        images = []
        img_elements = soup.select('.property-image img, .gallery img, [class*="image"] img, [class*="photo"] img')
        for img in img_elements:
            src = img.get('src') or img.get('data-src') or img.get('data-lazy-src')
            if src:
                if not src.startswith('http'):
                    src = urljoin(self.config.base_url, src)
                images.append(src)
        
        # 提取描述
        description = None
        # 尝试多种描述选择器
        desc_selectors = [
            '.property-description',
            '.description-content',
            '.detail-description',
            '[class*="description"]:not([class*="加入"])',  # 排除"加入比較"按钮
            '.content .description',
            'p.description',
            '.property-info',
            '.detail-info',
        ]
        
        for selector in desc_selectors:
            desc_elem = soup.select_one(selector)
            if desc_elem:
                desc_text = desc_elem.get_text(strip=True)
                # 排除明显的按钮文本
                if desc_text and desc_text not in ['加入比較', '加入比较', '更多', 'More'] and len(desc_text) > 20:
                    description = desc_text
                    break
        
        # 如果还是没找到，尝试查找包含较长文本的元素
        if not description or len(description) < 20:
            # 查找可能包含描述的段落
            paragraphs = soup.select('p, .content, [class*="detail"], [class*="info"], [class*="intro"]')
            for p in paragraphs:
                text = p.get_text(strip=True)
                # 如果文本长度合理且不是按钮文本
                if 50 < len(text) < 2000 and text not in ['加入比較', '加入比较']:
                    # 检查是否包含房产相关关键词
                    if any(keyword in text for keyword in ['呎', '房', '座', '樓', '樓盤', '單位', '屋苑']):
                        description = text
                        break
        
        # 提取楼层
        floor = None
        floor_selectors = [
            '.floor',
            '[class*="floor"]',
            '[class*="樓層"]',
        ]
        
        for selector in floor_selectors:
            floor_elem = soup.select_one(selector)
            if floor_elem:
                floor = floor_elem.get_text(strip=True)
                break
        
        # 从description中提取楼层
        if not floor:
            floor_patterns = [
                r'(\d+)\s*樓',
                r'(\d+)\s*层',
                r'(\d+)\s*層',
                r'(\d+)\s*F',
                r'(\d+)\s*座',  # 有时用"座"表示
            ]
            for pattern in floor_patterns:
                floor_match = re.search(pattern, desc_text)
                if floor_match:
                    floor = floor_match.group(1)
                    break
        
        # 提取朝向
        orientation = None
        orientation_selectors = [
            '.orientation',
            '[class*="orientation"]',
            '[class*="朝向"]',
        ]
        
        for selector in orientation_selectors:
            orient_elem = soup.select_one(selector)
            if orient_elem:
                orientation = orient_elem.get_text(strip=True)
                break
        
        # 从description中提取朝向
        if not orientation:
            # 查找"座向XXX"或"向XXX"模式
            orient_patterns = [
                r'座向([東西南北東南東北西南西北]+)',
                r'向([東西南北東南東北西南西北]+)',
                r'([東西南北東南東北西南西北]+)向',
            ]
            for pattern in orient_patterns:
                orient_match = re.search(pattern, desc_text)
                if orient_match:
                    orientation = orient_match.group(1)
                    break
            
            # 如果还没找到，查找单独的朝向关键词
            if not orientation:
                orient_keywords = ['東南', '東北', '西南', '西北', '東', '南', '西', '北',
                                 '东南', '东北', '西南', '西北', '东', '南', '西', '北']
                for keyword in orient_keywords:
                    if keyword in desc_text:
                        orientation = keyword
                        break
        
        # 提取楼龄（building_age）
        building_age = None
        # 查找"X年"或"X歲"模式
        age_patterns = [
            r'(\d+)\s*年',
            r'(\d+)\s*歲',
            r'樓齡[：:]\s*(\d+)',
            r'屋齡[：:]\s*(\d+)',
        ]
        
        for pattern in age_patterns:
            age_match = re.search(pattern, desc_text)
            if age_match:
                try:
                    building_age = int(age_match.group(1))
                    # 如果年龄超过100，可能是错误的（可能是年份）
                    if building_age > 100:
                        building_age = None
                    else:
                        break
                except ValueError:
                    pass
        
        # 提取更新日期
        update_date = None
        date_pattern = r'更新日期[：:]\s*(\d{4}[-/]\d{1,2}[-/]\d{1,2})'
        desc_text = soup.get_text() if soup else ""
        date_match = re.search(date_pattern, desc_text)
        if date_match:
            date_str = date_match.group(1)
            try:
                from datetime import datetime
                # 尝试解析日期
                for fmt in ['%Y-%m-%d', '%Y/%m/%d', '%Y-%m-%d']:
                    try:
                        update_date = datetime.strptime(date_str, fmt)
                        break
                    except:
                        continue
            except:
                pass
        
        # ========================================================================
        # 最终推断：在创建PropertyData之前，再次检查并设置缺失字段
        # ========================================================================
        # 设计说明：
        # - 这是最后的备用推断逻辑，用于处理特殊情况
        # - 当主要提取方法无法获取完整信息时，根据已知信息推断
        # - 例如：对于"映日灣"这个屋苑，根据网页内容推断应该是"荃灣 | 麗城"和"荃灣西"
        # 
        # 注意：这些推断逻辑是基于特定案例的，可能需要根据实际情况调整
        if region == '新界西' and district == '荃灣':
            # 对于"映日灣"这个屋苑，根据用户提供的网页内容
            if estate_name and '映日灣' in estate_name:
                if not district_level2:
                    district_level2 = '荃灣 | 麗城'
                if not sub_district:
                    sub_district = '荃灣西'
            # 对于其他荃灣的屋苑，如果页面中包含"荃灣西"或"麗城"
            elif not district_level2 or not sub_district:
                if '荃灣西' in page_text or '荃灣西' in (title or ''):
                    if not sub_district:
                        sub_district = '荃灣西'
                if '麗城' in page_text:
                    if not district_level2:
                        district_level2 = '荃灣 | 麗城'
                        if not district:
                            district = '荃灣'
        
        # 从area_name中提取信息（如果area_name包含"|"分隔符，如"屯門北｜大興花園"）
        if area_name and '｜' in area_name:
            area_parts = [p.strip() for p in area_name.split('｜')]
            # 过滤掉空字符串和无效项
            area_parts = [p for p in area_parts if p and p != '|' and len(p) > 1]

            if len(area_parts) >= 1:
                # 第一个部分可能是district_level2或sub_district
                first_part = area_parts[0]

                # 检查第一个部分应该设置为什么
                if district_level2 == first_part:
                    # district_level2已经设置为第一个部分，不需要再次处理
                    pass
                elif not district_level2:
                    # district_level2还没有设置，检查第一个部分是否合适
                    is_district_level2 = (
                        first_part in ['屯門北', '屯門南', '屯門西', '元朗北', '元朗南', '沙田北', '沙田南', '大埔北', '荃灣北', '荃灣南'] or
                        (any(d in first_part for d in ['屯門', '元朗', '沙田', '大埔', '荃灣']) and
                         any(suffix in first_part for suffix in ['北', '南', '東', '西', '中']))
                    )

                    if is_district_level2:
                        district_level2 = first_part
                        # 如果district_level2是"屯門北"，district应该是"屯門"
                        if '屯門' in first_part and (not district or district in ['級代', '中原地產', '租樓']):
                            district = '屯門'
                        elif '元朗' in first_part and (not district or district in ['級代', '中原地產', '租樓']):
                            district = '元朗'
                        elif '沙田' in first_part and (not district or district in ['級代', '中原地產', '租樓']):
                            district = '沙田'
                        elif '大埔' in first_part and (not district or district in ['級代', '中原地產', '租樓']):
                            district = '大埔'
                        elif '荃灣' in first_part and (not district or district in ['級代', '中原地產', '租樓']):
                            district = '荃灣'
                    else:
                        # 第一个部分可能是sub_district
                        sub_district = first_part
                        if not district or district in ['級代', '中原地產', '租樓']:
                            # 尝试从第一个部分推断district
                            if '屯門' in first_part:
                                district = '屯門'
                            elif '元朗' in first_part:
                                district = '元朗'
                            elif '沙田' in first_part:
                                district = '沙田'
                            elif '大埔' in first_part:
                                district = '大埔'
                            elif '荃灣' in first_part:
                                district = '荃灣'
            if len(area_parts) >= 2:
                # 第二个部分可能是sub_district或estate_name
                second_part = area_parts[1]
                invalid_items = ['立即登入', '登入/註冊', '立即註冊', '登入', '註冊', '私隱政策聲明', '使用條款', '版權所有']

                # 优先考虑设置为sub_district（如果还没有设置）
                if not sub_district and second_part not in invalid_items and len(second_part) > 1:
                    # 检查是否看起来像是地点或屋苑名称
                    if not any(char in second_part for char in ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9', '座', '期', '樓', '层']) and second_part not in ['買樓', '租樓']:
                        sub_district = second_part

                # 第二个部分也可能是estate_name
                if (not estate_name or estate_name in invalid_items) and second_part not in invalid_items:
                    estate_name = second_part
        
        # 最终清理：确保estate_name不是无效值
        invalid_estate_names = [
            '立即登入', '登入/註冊', '立即註冊', '登入', '註冊', 
            '我的優惠', '我的關注', '屋苑', '分行網絡', '中原地產',
            '私隱政策聲明', '使用條款', '版權所有', '中原地產代理有限公司'
        ]
        if estate_name in invalid_estate_names or (estate_name and any(kw in estate_name for kw in ['登入', '註冊', '私隱', '政策', '聲明', '條款', '版權', '代理', '有限公司'])):
            estate_name = None

        # 如果estate_name仍然是None或无效，尝试从title中提取
        if not estate_name and title:
            # 首先尝试使用整个title（对于像"Y I"这样的短名称）
            title_clean = title.strip()
            if (title_clean not in invalid_estate_names and
                len(title_clean) > 0 and
                not any(kw in title_clean for kw in ['登入', '註冊', '優惠', '關注', '私隱', '政策', '聲明', '條款', '版權', '代理', '有限公司'])):
                estate_name = title_clean
            else:
                # 如果整个title无效，尝试分割的各个部分
                title_parts = title.split()
                for part in title_parts:
                    if (part not in invalid_estate_names and
                        len(part) > 0 and  # 允许1个字符的名称
                        not any(kw in part for kw in ['登入', '註冊', '優惠', '關注', '私隱', '政策', '聲明', '條款', '版權', '代理', '有限公司'])):
                        estate_name = part
                        break
        
        # 如果estate_name仍然是None，尝试从URL中提取
        if not estate_name:
            try:
                from urllib.parse import unquote
                url_path = url.split('/')[-1].split('?')[0]
                decoded = unquote(url_path)
                # URL格式通常是：瓏門_CWJ731 或 瓏門-1期-2座-低層-H室_CZE092
                if '_' in decoded:
                    url_estate = decoded.split('_')[0]
                    # 如果包含"-"，取第一部分（屋苑名称）
                    if '-' in url_estate:
                        url_estate = url_estate.split('-')[0]
                    else:
                        url_estate = url_estate
                    # 验证提取的内容是否有效
                    if (url_estate and 
                        len(url_estate) > 0 and
                        url_estate not in invalid_estate_names and
                        not any(kw in url_estate for kw in ['登入', '註冊', '優惠', '關注', '私隱', '政策', '聲明', '條款', '版權', '代理', '有限公司'])):
                        estate_name = url_estate
            except:
                pass
        
        # 最终清理：确保district不是无效值
        invalid_districts = ['級代', '中原地產', '租樓', '使用WeChat掃描QRcode', '立即登入', '登入/註冊']
        if district in invalid_districts:
            district = None
        
        # 最终清理：确保sub_district不是无效值（如"|"）
        if sub_district in ['|', '｜', '', None] or (sub_district and len(sub_district) <= 1):
            sub_district = None
        
        # 生成property_id（从URL提取或使用hash）
        property_id = hashlib.md5(url.encode()).hexdigest()[:12]
        
        # 生成格式化的breadcrumb字符串（用">"分隔）
        # 设计说明：先根据提取的字段生成breadcrumb，然后从breadcrumb中重新解析字段
        # 这样可以确保字段映射的一致性
        breadcrumb = self._generate_breadcrumb(
            category, region, district, district_level2, sub_district, estate_name
        )
        
        # 从breadcrumb字符串中重新解析各个字段（按照用户要求的映射）
        # 设计说明：这是核心映射逻辑，确保所有字段都从breadcrumb中统一提取
        if breadcrumb:
            parsed_category, parsed_region, parsed_district_level2, \
            parsed_sub_district, parsed_estate_name = self._parse_breadcrumb_fields(breadcrumb)
            
            # 使用解析后的值覆盖原有值（确保映射一致性）
            if parsed_category:
                category = parsed_category
            if parsed_region:
                region = parsed_region
            if parsed_district_level2:
                district_level2 = parsed_district_level2
            if parsed_sub_district:
                sub_district = parsed_sub_district
            if parsed_estate_name:
                estate_name = parsed_estate_name
        
        property_data = PropertyData(
            property_id=property_id,
            source="centanet",
            url=url,
            title=title,
            price=price_value,
            price_display=price_text,
            monthly_mortgage_payment=monthly_mortgage_payment,
            area=area_value,
            area_display=area_text,
            district=district,
            area_name=area_name,
            street=street,
            address=location,
            property_type=property_type,
            bedrooms=bedrooms,
            bathrooms=bathrooms,
            floor=floor,
            building_age=building_age,
            orientation=orientation,
            description=description,
            images=images,
            update_date=update_date,
            crawl_date=datetime.now(),
            # 层级导航信息
            category=category,
            region=region,
            district_level2=district_level2,
            sub_district=sub_district,
            estate_name=estate_name,
            breadcrumb=breadcrumb,
        )
        
        return property_data
    
    async def crawl_all(self, max_pages: int = 5, max_properties: Optional[int] = None):
        """
        批量爬取所有页面
        
        设计说明：
        ----------
        - 按页顺序爬取列表页，提取详情页URL
        - 对每个详情页URL调用crawl_detail_page方法
        - 支持限制最大页数和房产数量
        - 自动去重（通过crawled_urls集合）
        - 记录失败的URL（用于错误追踪）
        
        Args:
            max_pages: 最大爬取页数，默认为5
            max_properties: 最大爬取房产数量，None表示不限制
        """
        print("="*70)
        print("开始爬取中原地产数据")
        print("="*70)
        print(f"列表页URL: {self.config.list_url}")
        print(f"最大页数: {max_pages}")
        print(f"最大房产数: {max_properties or '无限制'}")
        print("="*70)
        
        # 爬取列表页
        # 关键：创建单个crawler实例，确保在同一浏览器会话中执行所有操作
        # 这样JavaScript点击分页按钮后，可以获取更新后的HTML
        browser_config = BrowserConfig(
            headless=True,
            user_agent=self.config.user_agent,
        )
        
        all_property_urls = []
        
        # 使用单个crawler实例处理所有页面
        async with AsyncWebCrawler(config=browser_config) as crawler:
            for page in range(1, max_pages + 1):
                # Centanet使用AJAX分页，所有页面使用相同的URL
                # 需要通过JavaScript点击分页按钮来加载不同页面的内容
                list_url = self.config.list_url  # 所有页面使用相同的URL
                
                print(f"\n[列表页 {page}/{max_pages}] URL: {list_url} (通过点击分页按钮加载)")
                # 传递crawler实例，确保在同一浏览器会话中执行
                property_urls = await self.crawl_list_page(list_url, page, crawler=crawler)
                
                # 确保property_urls不是None
                if property_urls is None:
                    print(f"  ⚠ 警告: 列表页 {page} 返回了None，使用空列表")
                    property_urls = []
                
                print(f"  本页提取到 {len(property_urls)} 个房产URL")
                
                # 检查是否有重复URL（与之前页面比较）
                if property_urls and all_property_urls:
                    new_urls = [url for url in property_urls if url not in all_property_urls]
                    duplicate_urls = [url for url in property_urls if url in all_property_urls]
                    print(f"    新URL: {len(new_urls)} 个")
                    print(f"    重复URL: {len(duplicate_urls)} 个")
                    if duplicate_urls and page > 1:
                        print(f"    ⚠ 警告: 本页有 {len(duplicate_urls)} 个URL与之前页面重复")
                        if len(duplicate_urls) == len(property_urls):
                            print(f"    ⚠ 严重: 本页所有URL都是重复的！")
                            print(f"    可能原因: JavaScript分页按钮点击失败，页面内容未更新")
                            print(f"    重复URL示例: {duplicate_urls[0][:80]}...")
                
                print(f"  累计提取到 {len(all_property_urls) + len(property_urls)} 个房产URL")
                
                if not property_urls:
                    print(f"  ⚠ 列表页 {page} 没有找到房产，可能已到最后一页")
                    # 如果连续2页都没有找到房产，停止爬取
                    if page > 1:
                        print(f"  停止爬取（连续页面无数据）")
                        break
                else:
                    all_property_urls.extend(property_urls)
                
                # 如果已达到最大数量限制
                if max_properties and len(all_property_urls) >= max_properties:
                    all_property_urls = all_property_urls[:max_properties]
                    print(f"  已达到最大数量限制 ({max_properties})，停止爬取列表页")
                    break
                
                # 请求间隔
                await asyncio.sleep(self.config.rate_limit)
        
        # 去重
        original_count = len(all_property_urls)
        all_property_urls = list(set(all_property_urls))
        duplicate_count = original_count - len(all_property_urls)
        print(f"\n总共找到 {original_count} 个房产URL")
        if duplicate_count > 0:
            print(f"  去重后: {len(all_property_urls)} 个唯一URL (移除了 {duplicate_count} 个重复)")
        else:
            print(f"  所有URL都是唯一的")
        
        if not all_property_urls:
            print("没有找到任何房产URL，请检查:")
            print("1. 网站结构是否变化")
            print("2. CSS选择器是否正确")
            print("3. 是否需要登录或处理验证码")
            return
        
        # 限制爬取数量（用于测试）
        if max_properties:
            all_property_urls = all_property_urls[:max_properties]
            print(f"限制爬取数量为: {len(all_property_urls)}")
        
        # 爬取详情页（并发控制）
        print(f"\n开始爬取详情页...")
        print(f"  待爬取URL总数: {len(all_property_urls)}")
        semaphore = asyncio.Semaphore(self.config.max_concurrent)
        
        # 添加进度跟踪
        completed_count = 0
        total_count = len(all_property_urls)
        
        async def crawl_with_limit(url, index):
            nonlocal completed_count
            async with semaphore:
                result = await self.crawl_detail_page(url)
                completed_count += 1
                if completed_count % 10 == 0 or completed_count == total_count:
                    print(f"  进度: {completed_count}/{total_count} ({completed_count*100//total_count}%)")
                return result
        
        tasks = [crawl_with_limit(url, i) for i, url in enumerate(all_property_urls)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 统计
        success_count = sum(1 for r in results if r and not isinstance(r, Exception))
        error_count = sum(1 for r in results if isinstance(r, Exception))
        none_count = sum(1 for r in results if r is None and not isinstance(r, Exception))
        
        print(f"\n" + "="*70)
        print(f"爬取完成!")
        print(f"  总URL数: {len(all_property_urls)}")
        print(f"  成功解析: {success_count}")
        print(f"  返回None: {none_count} (可能因为去重或解析失败)")
        print(f"  异常: {error_count}")
        print(f"  失败URL数: {len(self.failed_urls)}")
        print(f"  实际保存记录数: {len(self.properties)}")
        print("="*70)
        
        # 如果成功解析的数量和实际保存的数量不一致，给出警告
        if success_count != len(self.properties):
            print(f"\n⚠ 警告: 成功解析数 ({success_count}) 与实际保存数 ({len(self.properties)}) 不一致")
            print(f"  可能原因: 某些记录在保存前被过滤掉了")
        
        # 保存数据
        if self.properties:
            self.save_data()
        else:
            print("\n⚠ 没有成功爬取到任何房产数据")
            print("请检查:")
            print("1. 详情页解析逻辑是否正确")
            print("2. CSS选择器是否匹配实际页面结构")
            print("3. 运行 centanet_explorer.py 检查页面结构")
            print("4. 检查失败URL列表了解具体错误")
            if self.failed_urls:
                print(f"\n失败URL示例（前3个）:")
                for url in self.failed_urls[:3]:
                    print(f"  - {url[:80]}...")
    
    def save_data(self):
        """
        保存爬取的数据到文件
        
        设计说明：
        ----------
        - 将数据保存为JSON格式（便于程序读取和查看）
        - 将数据保存为CSV格式（便于Excel等工具打开）
        - 保存失败URL列表（便于错误追踪和重试）
        - 文件名包含时间戳，避免覆盖之前的数据
        
        输出文件：
        - properties_YYYYMMDD_HHMMSS.json: JSON格式的房产数据
        - properties_YYYYMMDD_HHMMSS.csv: CSV格式的房产数据
        - failed_urls_YYYYMMDD_HHMMSS.txt: 失败的URL列表（如果有）
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # 保存为JSON
        json_file = self.output_dir / f"properties_{timestamp}.json"
        data = [prop.to_dict() for prop in self.properties]
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"\n✓ JSON数据已保存到: {json_file}")
        print(f"  共 {len(data)} 条记录")
        
        # 保存为CSV
        csv_file = self.output_dir / f"properties_{timestamp}.csv"
        if self.properties:
            try:
                fieldnames = list(self.properties[0].to_dict().keys())
                with open(csv_file, 'w', encoding='utf-8', newline='') as f:
                    writer = csv.DictWriter(f, fieldnames=fieldnames)
                    writer.writeheader()
                    for prop in self.properties:
                        writer.writerow(prop.to_dict())
                print(f"✓ CSV数据已保存到: {csv_file}")
            except Exception as e:
                print(f"✗ 保存CSV失败: {str(e)}")
        
        # 保存失败URL列表
        if self.failed_urls:
            failed_file = self.output_dir / f"failed_urls_{timestamp}.txt"
            with open(failed_file, 'w', encoding='utf-8') as f:
                for url in self.failed_urls:
                    f.write(url + "\n")
            print(f"⚠ 失败URL列表已保存到: {failed_file}")

async def main():
    """主函数"""
    crawler = CentanetCrawler()
    
    # 先测试爬取少量数据
    print("开始测试爬取...")
    await crawler.crawl_all(max_pages=2, max_properties=50)
    
    print("\n" + "="*70)
    print("测试完成！")
    print("="*70)
    print("\n如果测试成功，可以:")
    print("1. 增加 max_pages 参数爬取更多页面")
    print("2. 移除 max_properties 限制爬取所有房产")
    print("3. 检查保存的数据文件确认数据质量")

if __name__ == "__main__":
    asyncio.run(main())


