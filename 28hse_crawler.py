#!/usr/bin/env python3
"""
28Hse.com 爬虫 (28Hse Crawler)

设计说明：
----------
本爬虫采用多策略提取方法，按优先级顺序尝试不同的数据提取策略：

1. 面包屑导航提取（主要方法）：
   - 方法1: 从页面文本中通过正则表达式提取面包屑模式
   - 方法2: 从JavaScript数据对象中提取（最可靠）
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
- Hse28Crawler: 主爬虫类
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

from sites_config import HSE28_CONFIG
from data_models import PropertyData


class Hse28Crawler:
    """
    28Hse.com 爬虫类
    
    功能：
    - 爬取28Hse.com网站的房产列表页和详情页
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
    
    def __init__(self, output_dir: str = "data/28hse"):
        """
        初始化爬虫
        
        Args:
            output_dir: 数据输出目录，默认为 "data/28hse"
        """
        self.config = HSE28_CONFIG
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.crawled_urls = set()
        self.properties: List[PropertyData] = []
        self.failed_urls = []
        self._first_page_urls = set()
        self._list_page_addresses: Dict[str, str] = {}  # 存储从列表页提取的地址信息
    
    @staticmethod
    def _parse_breadcrumb_fields(breadcrumb: str) -> tuple:
        """
        从breadcrumb字符串中解析各个字段（28hse专用）
        
        设计说明：
        ----------
        根据28hse的实际breadcrumb格式提取字段：
        breadcrumb格式: "主頁 > 地產主頁 > 住宅售盤 > 新界 > 大埔,太和,白石角 > 逸瓏灣8 > property 3688274"
        
        字段映射：
        - category: "住宅售盤" (移除"主頁"和"地產主頁"后的第一个，即parts[0])
        - region: "新界" (parts[1])
        - district_level2: "大埔,太和,白石角" (parts[2])
        - sub_district: None (28hse不使用此字段)
        - estate_name: "逸瓏灣8" (parts[3]，倒数第二个，排除最后一个property ID)
        
        Args:
            breadcrumb: 格式化的breadcrumb字符串，如 "主頁 > 地產主頁 > 住宅售盤 > 新界 > 大埔,太和,白石角 > 逸瓏灣8 > property 3688274"
            
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
        
        # 移除 "地產主頁" 如果存在（28hse特有）
        if parts and parts[0] == '地產主頁':
            parts = parts[1:]
        
        # 根据28hse的格式映射字段
        # parts结构: ["住宅售盤", "新界", "大埔,太和,白石角", "逸瓏灣8", "property 3688274"]
        category = parts[0] if len(parts) > 0 and parts[0] else None
        region = parts[1] if len(parts) > 1 and parts[1] else None
        district_level2 = parts[2] if len(parts) > 2 and parts[2] else None
        sub_district = None  # 28hse不使用sub_district字段
        
        # estate_name: 取倒数第二个部分（排除最后一个property ID）
        # 如果最后一个部分看起来像property ID（包含"property"或全是数字），则取倒数第二个
        if len(parts) >= 4:
            last_part = parts[-1].lower()
            # 检查最后一个部分是否是property ID
            if 'property' in last_part or last_part.replace('-', '').replace('_', '').isdigit():
                estate_name = parts[-2] if len(parts) > 2 else None
            else:
                estate_name = parts[-1] if parts[-1] else None
        elif len(parts) == 3:
            # 如果只有3个部分，最后一个就是estate_name
            estate_name = parts[2] if parts[2] else None
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
        28Hse.com可能使用URL参数分页或AJAX分页。
        本方法会先尝试URL参数分页，如果失败则尝试AJAX分页。
        
        Args:
            url: 列表页URL
            page_num: 页码（1, 2, 3...）
            crawler: 可选的AsyncWebCrawler实例（用于AJAX分页）
            
        Returns:
            房产详情页URL列表
        """
        browser_config = BrowserConfig(
            headless=True,
            user_agent=self.config.user_agent,
        )
        
        # 如果传入了crawler，直接使用；否则创建新的
        if crawler is not None:
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
        print(f"  正在爬取列表页 {page_num}...")
        
        from crawl4ai.async_configs import CrawlerRunConfig
        session_id = f"28hse_list_{hashlib.md5(url.encode('utf-8')).hexdigest()[:10]}"
        
        # 尝试URL参数分页
        if self.config.pagination_type == "url_param" and self.config.pagination_param:
            if page_num > 1:
                # 构建带页码的URL
                separator = "&" if "?" in url else "?"
                list_url = f"{url}{separator}{self.config.pagination_param}={page_num}"
            else:
                list_url = url
        else:
            list_url = url
        
        # 对于第1页，直接访问URL
        if page_num == 1:
            # 改进的warmup JS，添加更好的错误处理和等待机制
            warmup_js = """
            (async () => {
              try {
                // 等待页面稳定
                if (document.readyState !== 'complete') {
                  await new Promise(r => {
                    if (document.readyState === 'complete') {
                      r();
                    } else {
                      window.addEventListener('load', r, { once: true });
                      setTimeout(r, 5000); // 超时保护
                    }
                  });
                }
                
                // 等待一小段时间确保页面完全加载
                await new Promise(r => setTimeout(r, 500));
                
                // 安全地滚动页面
                try { 
                  window.scrollTo(0, 0); 
                } catch(e) {
                  console.log('[WARMUP] Scroll error (ignored):', e.message);
                }
                
                await new Promise(r => setTimeout(r, 300));
                
                try { 
                  const scrollHeight = document.body ? Math.min(1200, document.body.scrollHeight * 0.2) : 0;
                  if (scrollHeight > 0) {
                    window.scrollTo(0, scrollHeight); 
                  }
                } catch(e) {
                  console.log('[WARMUP] Scroll error (ignored):', e.message);
                }
                
                await new Promise(r => setTimeout(r, 600));
                
                try { 
                  window.scrollTo(0, 0); 
                } catch(e) {
                  console.log('[WARMUP] Scroll error (ignored):', e.message);
                }
                
                return true;
              } catch(e) {
                console.log('[WARMUP] Error (ignored):', e.message);
                return true; // 即使出错也返回true，不阻止页面加载
              }
            })();
            """
            
            config = CrawlerRunConfig(
                session_id=session_id,
                js_code=warmup_js,
                delay_before_return_html=3,
                simulate_user=True,
                override_navigator=True,
                magic=True,
            )
            
            try:
                result = await crawler.arun(
                    url=list_url,
                    config=config,
                    timeout=max(self.config.timeout, 60),
                    wait_for="networkidle",
                )
            except Exception as e:
                # 如果因为导航错误，尝试不使用js_code直接访问
                print(f"  ⚠ 首次访问时出现错误（可能不影响功能）: {str(e)[:100]}")
                # 重试不使用JavaScript
                result = await crawler.arun(
                    url=list_url,
                    config=CrawlerRunConfig(
                        session_id=session_id,
                        delay_before_return_html=3,
                    ),
                    timeout=max(self.config.timeout, 60),
                    wait_for="networkidle",
                )
        else:
            # 对于后续页面，根据分页类型处理
            if self.config.pagination_type == "url_param":
                # URL参数分页：直接访问新URL
                result = await crawler.arun(
                    url=list_url,
                    config=CrawlerRunConfig(
                        session_id=session_id,
                        delay_before_return_html=3,
                        simulate_user=True,
                    ),
                    timeout=max(self.config.timeout, 60),
                    wait_for="networkidle",
                )
            else:
                # AJAX分页：执行JavaScript点击分页按钮
                print(f"    执行JavaScript点击第{page_num}页按钮...")
                js_code = f"""
                (async () => {{
                    try {{
                        // 等待页面稳定
                        if (document.readyState !== 'complete') {{
                            await new Promise(r => {{
                                if (document.readyState === 'complete') {{
                                    r();
                                }} else {{
                                    window.addEventListener('load', r, {{ once: true }});
                                    setTimeout(r, 5000);
                                }}
                            }});
                        }}
                        
                        console.log('[PAGINATION] Starting pagination for page {page_num}...');
                        await new Promise(resolve => setTimeout(resolve, 2000));
                        
                        const targetPage = String({page_num});
                        let clicked = false;
                        
                        // 查找分页按钮
                        const allClickable = Array.from(document.querySelectorAll('a, button, li, span, div'));
                        
                        for (let el of allClickable) {{
                            try {{
                                const text = (el.textContent || el.innerText || '').trim();
                                
                                if (text === targetPage) {{
                                    const isActive = el.classList.contains('active') || 
                                                   el.classList.contains('current') ||
                                                   el.getAttribute('aria-current') === 'page';
                                    
                                    if (!isActive) {{
                                        try {{
                                            el.scrollIntoView({{ behavior: 'smooth', block: 'center' }});
                                        }} catch(e) {{
                                            console.log('[PAGINATION] ScrollIntoView error (ignored)');
                                        }}
                                        await new Promise(resolve => setTimeout(resolve, 1000));
                                        
                                        try {{
                                            if (el.tagName === 'A' || el.tagName === 'BUTTON') {{
                                                el.click();
                                            }} else if (el.tagName === 'LI') {{
                                                const link = el.querySelector('a');
                                                if (link) {{
                                                    link.click();
                                                }} else {{
                                                    el.click();
                                                }}
                                            }} else {{
                                                const clickEvent = new MouseEvent('click', {{
                                                    bubbles: true,
                                                    cancelable: true,
                                                    view: window
                                                }});
                                                el.dispatchEvent(clickEvent);
                                            }}
                                            
                                            clicked = true;
                                            await new Promise(resolve => setTimeout(resolve, 5000));
                                            break;
                                        }} catch(e) {{
                                            console.log('[PAGINATION] Click error (ignored):', e.message);
                                        }}
                                    }}
                                }}
                            }} catch(e) {{
                                // 忽略单个元素的错误，继续处理下一个
                                continue;
                            }}
                        }}
                        
                        if (!clicked) {{
                            console.log('[PAGINATION] Page button not found, trying next button...');
                            try {{
                                // 尝试点击"下一页"按钮多次
                                const nextButtons = Array.from(document.querySelectorAll('a, button')).filter(el => {{
                                    try {{
                                        const text = (el.textContent || '').toLowerCase();
                                        return text.includes('next') || text.includes('下一頁') || text.includes('下頁');
                                    }} catch(e) {{
                                        return false;
                                    }}
                                }});
                                
                                if (nextButtons.length > 0) {{
                                    for (let i = 0; i < {page_num - 1}; i++) {{
                                        try {{
                                            nextButtons[0].click();
                                            await new Promise(resolve => setTimeout(resolve, 3000));
                                        }} catch(e) {{
                                            console.log('[PAGINATION] Next button click error (ignored)');
                                        }}
                                    }}
                                }}
                            }} catch(e) {{
                                console.log('[PAGINATION] Next button search error (ignored)');
                            }}
                        }}
                        
                        return clicked;
                    }} catch (e) {{
                        console.error('[PAGINATION] Error:', e.message);
                        return false;
                    }}
                }})();
                """
                
                try:
                    result = await crawler.arun(
                        url=url,
                        config=CrawlerRunConfig(
                            session_id=session_id,
                            js_code=js_code,
                            js_only=True,
                            delay_before_return_html=8,
                            simulate_user=True,
                        ),
                        timeout=max(self.config.timeout, 90),
                    )
                except Exception as e:
                    print(f"  ⚠ JavaScript分页执行时出现错误（可能不影响功能）: {str(e)[:100]}")
                    # 如果JavaScript执行失败，尝试直接访问URL参数分页
                    if self.config.pagination_param:
                        separator = "&" if "?" in url else "?"
                        fallback_url = f"{url}{separator}{self.config.pagination_param}={page_num}"
                        result = await crawler.arun(
                            url=fallback_url,
                            config=CrawlerRunConfig(
                                session_id=session_id,
                                delay_before_return_html=3,
                            ),
                            timeout=max(self.config.timeout, 60),
                            wait_for="networkidle",
                        )
                
                # 重新获取HTML
                if result and result.success:
                    try:
                        result = await crawler.arun(
                            url=url,
                            config=CrawlerRunConfig(
                                session_id=session_id,
                                js_only=True,
                                delay_before_return_html=2,
                            ),
                            timeout=max(self.config.timeout, 60),
                        )
                    except Exception as e:
                        # 如果重新获取失败，使用之前的结果
                        print(f"  ⚠ 重新获取HTML时出现错误（使用之前的结果）: {str(e)[:100]}")
        
        if not result or not result.success:
            print(f"  ✗ 无法访问列表页 {page_num}")
            return []
        
        # 提取房产详情页URL
        property_urls = []
        
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(result.html, 'html.parser')
            
            # 无效URL模式（需要过滤的路径）
            invalid_patterns = [
                '/member/',
                '/login',
                '/register',
                '/search',
                '/about',
                '/contact',
                '/help',
                '/terms',
                '/privacy',
                '/admin/',
                '/api/',
                'javascript:',
                '#',
                'mailto:',
                'tel:',
                # 排除非apartment类型
                '/office/',
                '/shop/',
                '/parking/',
                '/car-park/',
                '/车位/',
                '/商铺/',
                '/写字楼/',
                '/commercial/',
                '/industrial/',
            ]
            
            # 有效的房产详情页URL模式（只包含apartment相关）
            valid_patterns = [
                '/buy/apartment/',
                '/rent/apartment/',
                '/buy/apartment/property-',
                '/rent/apartment/property-',
                # 也接受简化的格式（如果URL是 /buy/apartment/property-xxx）
                '/apartment/property-',
            ]
            
            # 方法1: 使用CSS选择器查找链接（只查找apartment类型）
            link_selectors = [
                'a[href*="/buy/apartment/property-"]',
                'a[href*="/rent/apartment/property-"]',
                'a[href*="/apartment/property-"]',
                'a[href*="/buy/apartment/"]',
                'a[href*="/rent/apartment/"]',
                'a.property-link',
                'a.listing-link',
            ]
            
            for selector in link_selectors:
                links = soup.select(selector)
                for link in links:
                    href = link.get('href', '')
                    if href:
                        # 跳过无效URL
                        if any(pattern in href.lower() for pattern in invalid_patterns):
                            continue
                        
                        # 确保URL包含apartment且是property详情页
                        href_lower = href.lower()
                        if '/apartment/' not in href_lower:
                            continue
                        
                        # 确保是property详情页（包含property-）
                        if 'property-' not in href_lower:
                            continue
                        
                        # 确保是有效的房产详情页URL
                        if not any(pattern in href_lower for pattern in valid_patterns):
                            # 如果不在有效模式中，检查是否是相对路径且看起来像房产URL
                            if href.startswith('/') and '/apartment/property-' in href_lower:
                                # 这是apartment property URL，接受
                                pass
                            else:
                                continue
                        
                        if not href.startswith('http'):
                            href = urljoin(self.config.base_url, href)
                        
                        # 最终验证：确保URL包含apartment和property-，且不包含无效模式
                        href_lower = href.lower()
                        if ('/apartment/' in href_lower and 
                            'property-' in href_lower and
                            not any(pattern in href_lower for pattern in invalid_patterns) and
                            href not in property_urls):
                            property_urls.append(href)
                
                if property_urls:
                    break
            
            # 从列表页提取地址信息（用于补充详情页的address字段）
            # 列表页格式通常为: "地区 屋苑名称 | 座数 楼层 室号"
            # 例如: "荔枝角 宇晴軒 | 7座 中層 E室"
            list_page_addresses = {}
            if soup:
                # 查找包含房产信息的文本块
                # 尝试多种选择器来定位房产列表项
                property_item_selectors = [
                    '.property-item',
                    '.listing-item',
                    '.house-item',
                    '[class*="property"]',
                    '[class*="listing"]',
                    '[class*="house"]',
                ]
                
                for item_selector in property_item_selectors:
                    items = soup.select(item_selector)
                    for item in items:
                        # 查找链接
                        link_elem = item.find('a', href=True)
                        if link_elem:
                            href = link_elem.get('href', '')
                            if href and '/apartment/property-' in href.lower():
                                if not href.startswith('http'):
                                    href = urljoin(self.config.base_url, href)
                                
                                # 提取文本内容，可能包含地址信息
                                item_text = item.get_text(separator=' ', strip=True)
                                
                                # 尝试从文本中提取地址模式
                                # 格式: "地区 屋苑名称 | ..." 或 "地区 屋苑名称"
                                address_patterns = [
                                    r'([^\s|]+)\s+([^\s|]+(?:\s+[^\s|]+)?)\s*\|',  # "地区 屋苑名称 |"
                                    r'([^\s|]+)\s+([^\s|]+(?:\s+[^\s|]+)?)(?:\s*\|)?',  # "地区 屋苑名称"
                                ]
                                
                                for pattern in address_patterns:
                                    try:
                                        match = re.search(pattern, item_text)
                                        if match:
                                            district_part = match.group(1).strip()
                                            estate_part = match.group(2).strip()
                                            
                                            # 构建地址字符串
                                            if district_part and estate_part:
                                                address_text = f"{district_part} {estate_part}"
                                                list_page_addresses[href] = address_text
                                                break
                                    except re.error:
                                        continue
                        
                        if list_page_addresses:
                            break
                    
                    if list_page_addresses:
                        break
                
                # 如果上面的方法没找到，尝试从所有链接的父元素中提取
                if not list_page_addresses:
                    for link in soup.find_all('a', href=True):
                        href = link.get('href', '')
                        if href and '/apartment/property-' in href.lower():
                            if not href.startswith('http'):
                                href = urljoin(self.config.base_url, href)
                            
                            # 查找链接附近的文本（向上查找父元素）
                            current = link
                            for _ in range(3):  # 最多向上查找3层
                                if current and current.parent:
                                    current = current.parent
                                    parent_text = current.get_text(separator=' ', strip=True)
                                    
                                    # 提取地址模式：格式通常是 "地区 屋苑名称 | ..."
                                    # 例如: "荔枝角 宇晴軒 | 7座 中層 E室"
                                    address_patterns = [
                                        r'([^\s|]{2,15})\s+([^\s|]{2,20})\s*\|',  # "地区 屋苑名称 |"
                                        r'([^\s|]{2,15})\s+([^\s|]{2,20})(?:\s*\|)?',  # "地区 屋苑名称"
                                    ]
                                    
                                    for pattern in address_patterns:
                                        try:
                                            match = re.search(pattern, parent_text)
                                            if match:
                                                district_part = match.group(1).strip()
                                                estate_part = match.group(2).strip()
                                                
                                                # 验证提取的内容是否合理
                                                invalid_keywords = ['售', '租', '萬元', '呎', '房', '浴室', '座', '層', '室', 
                                                                  '建築', '實用', '面積', '元', '售盤', '租盤', '樓盤']
                                                if (district_part and estate_part and 
                                                    len(district_part) > 1 and len(estate_part) > 1 and
                                                    not any(kw in district_part for kw in invalid_keywords) and
                                                    not any(kw in estate_part for kw in invalid_keywords)):
                                                    address_text = f"{district_part} {estate_part}"
                                                    if href not in list_page_addresses:
                                                        list_page_addresses[href] = address_text
                                                    break
                                        except re.error:
                                            continue
                                    
                                    if href in list_page_addresses:
                                        break
            
            # 方法2: 从所有链接中查找（如果方法1没找到，只查找apartment类型）
            if not property_urls:
                all_links = soup.find_all('a', href=True)
                for link in all_links:
                    href = link.get('href', '')
                    if href:
                        if not href.startswith('http'):
                            href = urljoin(self.config.base_url, href)
                        
                        href_lower = href.lower()
                        # 检查是否是28hse.com的URL
                        if self.config.domain in href_lower:
                            # 确保是apartment类型的property详情页
                            if ('/apartment/' in href_lower and 
                                'property-' in href_lower and
                                not any(pattern in href_lower for pattern in invalid_patterns)):
                                if href not in property_urls:
                                    property_urls.append(href)
            
            # 方法2: 从JavaScript数据中提取（如果网站使用SPA）
            if not property_urls:
                # 尝试从window对象中提取URL
                js_extract_code = """
                (() => {
                    const urls = [];
                    const seen = new Set();
                    
                    function extractUrls(obj, depth) {
                        if (depth > 10 || !obj) return;
                        if (typeof obj === 'string') {
                            const patterns = ['/property/', '/listing/', '/house/', '/unit/'];
                            for (const pattern of patterns) {
                                if (obj.includes(pattern)) {
                                    if (!seen.has(obj)) {
                                        seen.add(obj);
                                        urls.push(obj);
                                    }
                                }
                            }
                        } else if (typeof obj === 'object') {
                            for (const key in obj) {
                                extractUrls(obj[key], depth + 1);
                            }
                        }
                    }
                    
                    try {
                        extractUrls(window, 0);
                    } catch(e) {}
                    
                    return JSON.stringify(urls.slice(0, 500));
                })();
                """
                
                # 这里可以添加JavaScript提取逻辑
                # 由于需要执行JavaScript，暂时跳过
                
        except Exception as e:
            print(f"  ⚠ 提取URL时出错: {str(e)}")
        
        # 去重
        property_urls = list(set(property_urls))
        
        # 将列表页提取的地址信息存储到实例变量中
        for url, address in list_page_addresses.items():
            if url in property_urls:
                self._list_page_addresses[url] = address
        
        if property_urls:
            print(f"  ✓ 列表页 {page_num}: 找到 {len(property_urls)} 个唯一房产URL")
            if list_page_addresses:
                print(f"  ✓ 列表页 {page_num}: 提取了 {len(list_page_addresses)} 个地址信息")
        else:
            print(f"  ⚠ 列表页 {page_num}: 没有找到房产URL")
        
        return property_urls
    
    async def crawl_detail_page(self, url: str) -> Optional[PropertyData]:
        """
        爬取房产详情页
        
        Args:
            url: 详情页URL
            
        Returns:
            PropertyData 对象或 None
        """
        # 检查URL是否有效
        if not url or not url.startswith('http'):
            return None
        
        # 检查是否已爬取
        if url in self.crawled_urls:
            return None
        
        self.crawled_urls.add(url)
        
        browser_config = BrowserConfig(
            headless=True,
            user_agent=self.config.user_agent,
        )
        
        try:
            async with AsyncWebCrawler(config=browser_config) as crawler:
                result = await crawler.arun(
                    url=url,
                    timeout=self.config.timeout,
                    wait_for="networkidle",
                )
                
                if not result or not result.success:
                    print(f"  ✗ 无法访问: {url[:80]}...")
                    self.failed_urls.append(url)
                    return None
                
                # 解析详情页
                property_data = self._parse_detail_page(result.html, url)
                
                if property_data:
                    self.properties.append(property_data)
                    return property_data
                else:
                    self.failed_urls.append(url)
                    return None
                    
        except Exception as e:
            print(f"  ✗ 爬取失败: {url[:80]}... 错误: {str(e)}")
            self.failed_urls.append(url)
            return None
    
    def _parse_detail_page(self, html: str, url: str) -> Optional[PropertyData]:
        """
        解析详情页HTML，提取房产数据
        
        设计说明：
        ----------
        本方法采用多策略提取方法，按以下顺序执行：
        
        1. 面包屑导航提取（优先级最高）
        2. 其他字段提取（标题、价格、面积、位置等）
        3. 字段映射和验证
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
        
        # 使用更宽松的解析器，避免HTML格式错误导致解析失败
        try:
            soup = BeautifulSoup(html, 'html.parser')
        except Exception as e:
            # 如果html.parser失败，尝试lxml（如果可用）
            try:
                soup = BeautifulSoup(html, 'lxml')
            except:
                # 如果都失败，尝试html5lib（如果可用）
                try:
                    soup = BeautifulSoup(html, 'html5lib')
                except Exception as e2:
                    print(f"  ✗ 无法解析HTML: {str(e2)}")
                    return None
        
        # 初始化所有变量
        title = None
        category = None
        region = None
        district = None
        district_level2 = None
        sub_district = None
        area_name = None
        estate_name = None
        price_value = None
        price_text = None
        monthly_mortgage_payment = None
        area_value = None
        area_text = None
        property_type = None
        bedrooms = None
        bathrooms = None
        floor = None
        building_age = None
        orientation = None
        description = None
        images = []
        location = None
        street = None
        
        # 从URL提取property_id
        property_id = hashlib.md5(url.encode('utf-8')).hexdigest()[:16]
        
        # 从URL提取category和estate_name（备用方法）
        url_path = urlparse(url).path
        url_parts = [p for p in url_path.split('/') if p]
        if url_parts:
            # 从URL中提取category（28hse格式：/buy/ 或 /rent/）
            if not category:
                if 'buy' in url_path.lower() or '/buy/' in url_path:
                    category = '住宅售盤'
                elif 'rent' in url_path.lower() or '/rent/' in url_path:
                    category = '住宅租盤'
                elif 'sale' in url_path.lower() or '/sale/' in url_path:
                    category = '住宅售盤'
            
            # 尝试从URL中提取房产名称（但通常URL最后是property ID，不是estate_name）
            # 所以这里不设置estate_name，让它从breadcrumb中提取
        
        # ========================================================================
        # 方法1: 从页面文本中提取面包屑模式（通过正则表达式）
        # ========================================================================
        page_text = soup.get_text(separator=' ') if soup else ""
        breadcrumb_patterns = [
            r'主頁\s+買樓\s+([^\s]+)\s+([^\s]+)\s+([^\s]+)',
            r'主頁\s+租樓\s+([^\s]+)\s+([^\s]+)\s+([^\s]+)',
            r'主頁\s+([^\s|]+)\s+([^\s|]+)\s+([^\s|]+)\s+([^\s|]+)\s+([^\s|]+)',
        ]
        
        breadcrumb_match = None
        for pattern in breadcrumb_patterns:
            try:
                match = re.search(pattern, page_text)
                if match:
                    breadcrumb_match = match
                    break
            except re.error as e:
                print(f"  ⚠ 面包屑正则表达式错误: {pattern} - {str(e)}")
                continue
        
        # ========================================================================
        # 方法2: 从HTML面包屑导航元素中提取
        # ========================================================================
        breadcrumb_items = []
        breadcrumb_selectors = [
            '.breadcrumb',
            '.breadcrumbs',
            '.nav-breadcrumb',
            '[class*="breadcrumb"]',
            'nav[aria-label*="breadcrumb"]',
        ]
        
        for selector in breadcrumb_selectors:
            breadcrumb_elem = soup.select_one(selector)
            if breadcrumb_elem:
                links = breadcrumb_elem.find_all('a', href=True)
                for link in links:
                    text = link.get_text(strip=True)
                    if text and text not in ['主頁', 'Home', '首页']:
                        breadcrumb_items.append(text)
                if breadcrumb_items:
                    break
        
        # 从breadcrumb_items中提取字段（28hse格式）
        # breadcrumb_items格式: ["地產主頁", "住宅售盤", "新界", "大埔,太和,白石角", "逸瓏灣8"]
        if breadcrumb_items:
            # 跳过"地產主頁"如果存在
            start_idx = 0
            if breadcrumb_items[0] == '地產主頁':
                start_idx = 1
            
            # 根据28hse的格式映射字段
            if len(breadcrumb_items) > start_idx:
                category = breadcrumb_items[start_idx] if not category else category
            if len(breadcrumb_items) > start_idx + 1:
                region = breadcrumb_items[start_idx + 1] if not region else region
            if len(breadcrumb_items) > start_idx + 2:
                district_level2 = breadcrumb_items[start_idx + 2] if not district_level2 else district_level2
            # sub_district在28hse中不使用，保持为None
            if len(breadcrumb_items) > start_idx + 3:
                # estate_name是倒数第二个（排除最后一个property ID）
                # 如果最后一个看起来像property ID，则取倒数第二个
                last_item = breadcrumb_items[-1].lower()
                if 'property' in last_item or last_item.replace('-', '').replace('_', '').isdigit():
                    if len(breadcrumb_items) > start_idx + 3:
                        estate_name = breadcrumb_items[-2] if not estate_name else estate_name
                else:
                    estate_name = breadcrumb_items[-1] if not estate_name else estate_name
        
        # ========================================================================
        # 提取标题
        # ========================================================================
        title_selectors = [
            'h1.property-title',
            'h1.title',
            'h1',
            '.property-title',
            '.title',
            'title',
        ]
        
        for selector in title_selectors:
            elem = soup.select_one(selector)
            if elem:
                title = elem.get_text(strip=True)
                if title and len(title) > 3:
                    break
        
        # 如果还没有标题，从页面title标签提取
        if not title or len(title) < 3:
            title_tag = soup.find('title')
            if title_tag:
                title = title_tag.get_text(strip=True)
        
        # 从标题中提取 estate_name（如果还没有）
        # 标题格式通常是: "青華苑 #3688300 售盤樓盤詳細資料"
        if title and not estate_name:
            # 移除 # 后面的内容
            title_clean = re.sub(r'\s*#\d+.*', '', title)
            # 移除 "售盤樓盤詳細資料"、"租盤樓盤詳細資料" 等后缀
            title_clean = re.sub(r'\s*(售盤|租盤|樓盤|詳細資料).*', '', title_clean)
            title_clean = title_clean.strip()
            if title_clean and len(title_clean) > 1:
                estate_name = title_clean
                # 如果 area_name 也为空，使用 estate_name
                if not area_name:
                    area_name = estate_name
        
        # ========================================================================
        # 提取价格
        # ========================================================================
        price_selectors = [
            '.price',
            '.property-price',
            '.house-price',
            '[class*="price"]',
        ]
        
        for selector in price_selectors:
            elem = soup.select_one(selector)
            if elem:
                price_text = elem.get_text(strip=True)
                if price_text:
                    # 提取数字
                    price_match = re.search(r'[\d,]+', price_text.replace(',', ''))
                    if price_match:
                        try:
                            price_value = float(price_match.group().replace(',', ''))
                            # 如果包含"萬"或"万"，转换为港币
                            if '萬' in price_text or '万' in price_text:
                                price_value = price_value * 10000
                        except ValueError:
                            pass
                    break
        
        # 从页面文本中提取价格（备用方法）
        if not price_text:
            price_patterns = [
                r'[\$HK\$]?\s*[\d,]+萬?',
                r'[\d,]+万',
                r'[\d,]+萬',
                r'HK\$\s*[\d,]+',
            ]
            for pattern in price_patterns:
                try:
                    matches = re.findall(pattern, page_text)
                    if matches:
                        price_text = matches[0]
                        price_match = re.search(r'[\d,]+', price_text.replace(',', ''))
                        if price_match:
                            try:
                                price_value = float(price_match.group().replace(',', ''))
                                if '萬' in price_text or '万' in price_text:
                                    price_value = price_value * 10000
                            except ValueError:
                                pass
                        break
                except re.error as e:
                    # 如果正则表达式有错误，跳过这个模式
                    print(f"  ⚠ 价格正则表达式错误: {pattern} - {str(e)}")
                    continue
        
        # ========================================================================
        # 提取月供
        # ========================================================================
        monthly_patterns = [
            r'月供[：:]\s*[\$HK\$]?([\d,]+)',
            r'每月[：:]\s*[\$HK\$]?([\d,]+)',
            r'\$([\d,]+)\s*月供',
        ]
        for pattern in monthly_patterns:
            try:
                match = re.search(pattern, page_text)
                if match:
                    monthly_mortgage_payment = f"${match.group(1)}"
                    break
            except re.error as e:
                print(f"  ⚠ 月供正则表达式错误: {pattern} - {str(e)}")
                continue
        
        # ========================================================================
        # 提取面积
        # ========================================================================
        area_selectors = [
            '.area',
            '.property-area',
            '.house-area',
            '[class*="area"]',
        ]
        
        for selector in area_selectors:
            elem = soup.select_one(selector)
            if elem:
                area_text = elem.get_text(strip=True)
                if area_text:
                    # 提取数字
                    area_match = re.search(r'[\d.]+', area_text)
                    if area_match:
                        try:
                            area_value = float(area_match.group())
                        except ValueError:
                            pass
                    break
        
        # 从页面文本中提取面积（备用方法）
        if not area_text:
            area_patterns = [
                r'[\d.]+?\s*呎',
                r'[\d.]+?\s*平方呎',
                r'[\d.]+?\s*sqft',
            ]
            for pattern in area_patterns:
                try:
                    matches = re.findall(pattern, page_text, re.IGNORECASE)
                    if matches:
                        area_text = matches[0]
                        area_match = re.search(r'[\d.]+', area_text)
                        if area_match:
                            try:
                                area_value = float(area_match.group())
                            except ValueError:
                                pass
                        break
                except re.error as e:
                    # 如果正则表达式有错误，跳过这个模式
                    print(f"  ⚠ 面积正则表达式错误: {pattern} - {str(e)}")
                    continue
        
        # ========================================================================
        # 提取位置信息
        # ========================================================================
        location_selectors = [
            '.location',
            '.address',
            '.property-location',
            '[class*="location"]',
            '[class*="address"]',
        ]
        
        for selector in location_selectors:
            elem = soup.select_one(selector)
            if elem:
                location = elem.get_text(strip=True)
                if location:
                    break
        
        # ========================================================================
        # 提取房产属性
        # ========================================================================
        # 房型
        property_type_patterns = [
            r'(\d+)\s*房',
            r'(\d+)\s*bedroom',
        ]
        for pattern in property_type_patterns:
            try:
                match = re.search(pattern, page_text, re.IGNORECASE)
                if match:
                    property_type = f"{match.group(1)}房"
                    try:
                        bedrooms = int(match.group(1))
                    except ValueError:
                        pass
                    break
            except re.error as e:
                print(f"  ⚠ 房型正则表达式错误: {pattern} - {str(e)}")
                continue
        
        # 楼层
        floor_patterns = [
            r'(\d+)\s*樓',
            r'(\d+)\s*層',
            r'floor\s*(\d+)',
        ]
        for pattern in floor_patterns:
            try:
                match = re.search(pattern, page_text, re.IGNORECASE)
                if match:
                    floor = match.group(1)
                    break
            except re.error as e:
                print(f"  ⚠ 楼层正则表达式错误: {pattern} - {str(e)}")
                continue
        
        # ========================================================================
        # 提取描述
        # ========================================================================
        desc_selectors = [
            '.description',
            '.property-description',
            '[class*="description"]',
        ]
        
        for selector in desc_selectors:
            elem = soup.select_one(selector)
            if elem:
                description = elem.get_text(strip=True)
                if description and len(description) > 10:
                    break
        
        # ========================================================================
        # 提取图片
        # ========================================================================
        img_selectors = [
            '.property-images img',
            '.gallery img',
            '[class*="image"] img',
        ]
        
        for selector in img_selectors:
            imgs = soup.select(selector)
            for img in imgs:
                src = img.get('src') or img.get('data-src')
                if src:
                    if not src.startswith('http'):
                        src = urljoin(self.config.base_url, src)
                    if src not in images:
                        images.append(src)
            if images:
                break
        
        # ========================================================================
        # 生成breadcrumb并重新映射字段
        # ========================================================================
        breadcrumb = self._generate_breadcrumb(
            category, region, district, district_level2, sub_district, estate_name
        )
        
        # 从breadcrumb字符串中重新解析各个字段
        if breadcrumb:
            parsed_category, parsed_region, parsed_district_level2, \
            parsed_sub_district, parsed_estate_name = self._parse_breadcrumb_fields(breadcrumb)
            
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
        
        # ========================================================================
        # 从已提取的字段填充缺失的位置信息
        # ========================================================================
        # district: 使用 district_level2 的值（如果 district 为空）
        if not district and district_level2:
            district = district_level2
        
        # area_name: 使用 estate_name 的值（如果 area_name 为空）
        if not area_name and estate_name:
            area_name = estate_name
        
        # ========================================================================
        # 优先使用从列表页提取的地址信息
        # ========================================================================
        if url in self._list_page_addresses:
            list_page_address = self._list_page_addresses[url]
            if list_page_address and not location:
                location = list_page_address
            elif list_page_address and location and len(list_page_address) > len(location):
                # 如果列表页的地址更详细，使用列表页的地址
                location = list_page_address
        
        # 尝试从页面文本中提取 street（街道名称）
        # 模式：XXX徑、XXX路、XXX街、XXX道、XXX里
        if not street:
            street_patterns = [
                r'([^\s]{2,15}(?:徑|路|街|道|里))',
                r'([^\s]{2,15}(?:Road|Street|Avenue|Lane))',
            ]
            for pattern in street_patterns:
                try:
                    match = re.search(pattern, page_text)
                    if match:
                        potential_street = match.group(1).strip()
                        # 过滤掉无效的街道名称
                        invalid_street_keywords = ['地址', '位置', '地點', 'Location', 'Address', 
                                                  '致電', 'Whatsapp', '聯絡', '電話', 'Tel']
                        if not any(kw in potential_street for kw in invalid_street_keywords):
                            street = potential_street
                            break
                except re.error as e:
                    print(f"  ⚠ 街道正则表达式错误: {pattern} - {str(e)}")
                    continue
        
        # 尝试从页面文本中提取完整的 address
        # 组合已有信息构建地址（如果还没有从列表页获取到地址）
        if not location or location == "":
            address_parts = []
            if region:
                address_parts.append(region)
            if district_level2:
                address_parts.append(district_level2)
            if estate_name:
                address_parts.append(estate_name)
            if street:
                address_parts.append(street)
            
            if address_parts:
                location = " ".join(address_parts)
        
        # 从描述文本中尝试提取更详细的地址信息
        if description and len(description) > 10:
            # 尝试从描述中提取地址模式
            address_patterns = [
                r'([^\s]{2,20}(?:徑|路|街|道|里|花園|苑|邨|中心|居|軒|灣|城|山|臺|台))',
                r'([^\s]{2,20}(?:Road|Street|Avenue|Lane|Garden|Estate))',
            ]
            for pattern in address_patterns:
                try:
                    matches = re.findall(pattern, description)
                    if matches:
                        # 取第一个匹配的作为地址补充
                        potential_address = matches[0]
                        if potential_address and potential_address not in ['致電Whatsapp', '聯絡我們']:
                            if not location or len(location) < len(potential_address):
                                location = potential_address
                            break
                except re.error as e:
                    print(f"  ⚠ 地址正则表达式错误: {pattern} - {str(e)}")
                    continue
        
        # 验证必需字段
        if not title:
            title = url_parts[-1] if url_parts else "未知房产"
        
        # 创建PropertyData对象
        property_data = PropertyData(
            property_id=property_id,
            source="28hse",
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
            crawl_date=datetime.now(),
            category=category,
            region=region,
            district_level2=district_level2,
            sub_district=sub_district,
            estate_name=estate_name,
            breadcrumb=breadcrumb,
        )
        
        return property_data
    
    def _build_list_url(self, category: Optional[str] = None) -> str:
        """
        根据category构建列表页URL（只提取apartment类型）
        
        Args:
            category: 类别，可选值：
                - "buy" 或 "買樓": 買樓列表
                - "rent" 或 "租樓": 租樓列表
                - None: 使用默认配置的list_url
        
        Returns:
            列表页URL（包含/apartment路径）
        """
        if category is None:
            # 默认返回buy/apartment
            return f"{self.config.base_url}/buy/apartment"
        
        # Category映射（需要根据28hse.com的实际URL结构调整）
        category_map = {
            "buy": "buy",
            "買樓": "buy",
            "rent": "rent",
            "租樓": "rent",
        }
        
        category_key = category_map.get(category.lower() if category else None, "buy")
        # 28hse.com的apartment列表页URL格式: /buy/apartment 或 /rent/apartment
        return f"{self.config.base_url}/{category_key}/apartment"
    
    async def crawl_all(
        self, 
        max_pages: int = 5, 
        max_properties: Optional[int] = None,
        category: Optional[str] = None,
        region: Optional[str] = None
    ):
        """
        批量爬取所有页面
        
        Args:
            max_pages: 最大爬取页数，默认为5
            max_properties: 最大爬取房产数量，None表示不限制
            category: 类别筛选
            region: 地区筛选
        """
        print("="*70)
        print("开始爬取28Hse.com数据")
        print("="*70)
        
        # 构建列表页URL
        list_url = self._build_list_url(category)
        print(f"列表页URL: {list_url}")
        if category:
            print(f"类别筛选: {category}")
        if region:
            print(f"地区筛选: {region}")
        print(f"最大页数: {max_pages}")
        print(f"最大房产数: {max_properties or '无限制'}")
        print("="*70)
        
        # 爬取列表页
        browser_config = BrowserConfig(
            headless=True,
            user_agent=self.config.user_agent,
        )
        
        all_property_urls = []
        
        async with AsyncWebCrawler(config=browser_config) as crawler:
            for page in range(1, max_pages + 1):
                print(f"\n[列表页 {page}/{max_pages}]")
                property_urls = await self.crawl_list_page(list_url, page, crawler=crawler)
                
                if property_urls is None:
                    property_urls = []
                
                print(f"  本页提取到 {len(property_urls)} 个房产URL")
                
                if not property_urls:
                    print(f"  ⚠ 列表页 {page} 没有找到房产，可能已到最后一页")
                    if page > 1:
                        break
                else:
                    all_property_urls.extend(property_urls)
                
                if max_properties and len(all_property_urls) >= max_properties:
                    all_property_urls = all_property_urls[:max_properties]
                    break
                
                await asyncio.sleep(self.config.rate_limit)
        
        # 去重
        all_property_urls = list(set(all_property_urls))
        print(f"\n总共找到 {len(all_property_urls)} 个唯一房产URL")
        
        if not all_property_urls:
            print("没有找到任何房产URL")
            return
        
        if max_properties:
            all_property_urls = all_property_urls[:max_properties]
            print(f"限制爬取数量为: {len(all_property_urls)}")
        
        # 爬取详情页
        print(f"\n开始爬取详情页...")
        semaphore = asyncio.Semaphore(self.config.max_concurrent)
        
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
        
        # 如果指定了region，过滤结果
        if region:
            print(f"\n根据地区 '{region}' 过滤结果...")
            original_count = len(self.properties)
            # 支持多种region名称格式
            region_variants = {
                '港島': ['港島', '香港島', '香港岛'],
                '九龍': ['九龍', '九龙'],
                '新界': ['新界', '新界東', '新界东', '新界西'],
                '離島': ['離島', '离岛'],
            }
            
            # 获取region的所有变体
            region_matches = [region]
            for key, variants in region_variants.items():
                if region in variants or any(v in region for v in variants):
                    region_matches.extend(variants)
                    break
            
            # 去重
            region_matches = list(set(region_matches))
            
            # 过滤：匹配region或district_level2包含region
            filtered_properties = []
            for p in self.properties:
                if p.region and p.region in region_matches:
                    filtered_properties.append(p)
                elif p.district_level2 and any(rm in p.district_level2 for rm in region_matches):
                    filtered_properties.append(p)
                elif not p.region and region.lower() in ['all', '全部', '不限']:
                    # 如果没有region信息且用户选择"全部"，则保留
                    filtered_properties.append(p)
            
            self.properties = filtered_properties
            print(f"  原始记录数: {original_count}")
            print(f"  过滤后保留: {len(self.properties)} 条记录")
            if len(self.properties) < original_count:
                print(f"  已过滤掉 {original_count - len(self.properties)} 条不匹配的记录")
        
        print(f"\n" + "="*70)
        print(f"爬取完成!")
        print(f"  总URL数: {len(all_property_urls)}")
        print(f"  成功解析: {success_count}")
        print(f"  异常: {error_count}")
        print(f"  实际保存记录数: {len(self.properties)}")
        print("="*70)
        
        # 保存数据
        if self.properties:
            self.save_data()
        else:
            print("\n⚠ 没有成功爬取到任何房产数据")
    
    def save_data(self):
        """
        保存爬取的数据到文件
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
    import argparse
    
    parser = argparse.ArgumentParser(description='28Hse.com 爬虫')
    parser.add_argument('--max-pages', type=int, default=2, help='最大爬取页数')
    parser.add_argument('--max-properties', type=int, default=50, help='最大爬取房产数量')
    parser.add_argument('--category', type=str, default=None, 
                       help='类别筛选: buy/買樓, rent/租樓')
    parser.add_argument('--region', type=str, default=None,
                       help='地区筛选: 港島, 九龍, 新界東, 新界西 等')
    
    args = parser.parse_args()
    
    crawler = Hse28Crawler()
    
    print("开始测试爬取...")
    await crawler.crawl_all(
        max_pages=args.max_pages,
        max_properties=args.max_properties,
        category=args.category,
        region=args.region
    )
    
    print("\n" + "="*70)
    print("测试完成！")
    print("="*70)
    print("\n如果测试成功，可以:")
    print("1. 增加 max_pages 参数爬取更多页面")
    print("2. 移除 max_properties 限制爬取所有房产")
    print("3. 使用 --category 和 --region 参数筛选特定类别和地区")
    print("4. 检查保存的数据文件确认数据质量")
    print("\n注意: 如果数据提取不准确，请:")
    print("1. 运行探索脚本检查页面结构")
    print("2. 根据实际HTML结构更新CSS选择器")
    print("3. 调整数据提取逻辑")


if __name__ == "__main__":
    asyncio.run(main())

