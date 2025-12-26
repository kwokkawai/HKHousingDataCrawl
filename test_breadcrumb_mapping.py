#!/usr/bin/env python3
"""
测试从示例 URL 提取并验证 breadcrumb 映射
"""

import asyncio
import sys
sys.path.insert(0, '.')

from centanet_crawler import CentanetCrawler

async def test_single_url():
    """测试单个 URL 的 breadcrumb 解析"""
    test_url = "https://hk.centanet.com/findproperty/detail/%E7%93%8F%E9%96%80_CWJ731?theme=buy"
    
    print(f"测试 URL: {test_url}")
    print("=" * 80)
    
    crawler = CentanetCrawler()
    
    # 获取页面内容
    from crawl4ai import AsyncWebCrawler
    async with AsyncWebCrawler(verbose=False) as crawler_instance:
        result = await crawler_instance.arun(url=test_url)
        
        if result.success and result.html:
            # 解析页面
            property_data = crawler._parse_detail_page(result.html, test_url)
            
            if property_data:
                print("\n提取的属性:")
                print(f"  category: {property_data.category}")
                print(f"  region: {property_data.region}")
                print(f"  district_level2: {property_data.district_level2}")
                print(f"  sub_district: {property_data.sub_district}")
                print(f"  estate_name: {property_data.estate_name}")
                print(f"  breadcrumb: {property_data.breadcrumb}")
                
                print("\n验证映射（从 breadcrumb 解析）:")
                if property_data.breadcrumb:
                    # 解析 breadcrumb
                    if ' > ' in property_data.breadcrumb:
                        parts = [p.strip() for p in property_data.breadcrumb.split(' > ')]
                    else:
                        parts = property_data.breadcrumb.split()
                    
                    # 移除 "主頁"
                    if parts and parts[0] == '主頁':
                        parts = parts[1:]
                    
                    print(f"  breadcrumb 部分: {parts}")
                    print(f"  第2个字符串 (category): {parts[0] if len(parts) > 0 else 'N/A'}")
                    print(f"  第3个字符串 (region): {parts[1] if len(parts) > 1 else 'N/A'}")
                    print(f"  第4个字符串 (district_level2): {parts[2] if len(parts) > 2 else 'N/A'}")
                    print(f"  第5个字符串 (sub_district): {parts[3] if len(parts) > 3 else 'N/A'}")
                    print(f"  第6个字符串 (estate_name): {parts[4] if len(parts) > 4 else 'N/A'}")
                    
                    # 验证映射是否正确
                    print("\n映射验证:")
                    print(f"  category 匹配: {property_data.category == parts[0] if len(parts) > 0 else False}")
                    print(f"  region 匹配: {property_data.region == parts[1] if len(parts) > 1 else False}")
                    print(f"  district_level2 匹配: {property_data.district_level2 == parts[2] if len(parts) > 2 else False}")
                    print(f"  sub_district 匹配: {property_data.sub_district == parts[3] if len(parts) > 3 else False}")
                    print(f"  estate_name 匹配: {property_data.estate_name == parts[4] if len(parts) > 4 else False}")
            else:
                print("无法解析房产数据")
        else:
            print(f"无法获取页面内容: {result.error_message if hasattr(result, 'error_message') else 'Unknown error'}")

if __name__ == "__main__":
    asyncio.run(test_single_url())

