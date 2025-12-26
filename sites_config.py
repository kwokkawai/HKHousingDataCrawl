#!/usr/bin/env python3
"""
网站配置文件
为每个目标网站定义爬取配置，包括URL模式、选择器、请求头等
"""

from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass
class SiteConfig:
    """网站配置数据类"""
    name: str  # 网站名称
    base_url: str  # 基础URL
    list_url: str  # 列表页URL
    domain: str  # 域名
    
    # 请求配置
    headers: Dict[str, str]  # 请求头
    user_agent: str  # User-Agent
    
    # 选择器配置（需要实际测试后更新）
    selectors: Dict[str, str]  # CSS选择器或XPath
    
    # 分页配置
    pagination_type: str  # 'url_param', 'ajax', 'infinite_scroll'
    pagination_param: Optional[str] = None  # 分页参数名（如 'page'）
    
    # 反爬虫配置
    requires_js: bool = True  # 是否需要JavaScript渲染
    rate_limit: float = 1.0  # 请求间隔（秒）
    max_concurrent: int = 3  # 最大并发数
    
    # 其他配置
    timeout: int = 30  # 超时时间（秒）
    retry_times: int = 3  # 重试次数


# 中原地产配置
CENTANET_CONFIG = SiteConfig(
    name="中原地产",
    base_url="https://hk.centanet.com",
    list_url="https://hk.centanet.com/findproperty/list/buy",
    domain="hk.centanet.com",
    headers={
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "zh-HK,zh;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    },
    user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    selectors={
        # 需要实际测试后更新这些选择器
        "property_list": ".property-item, .listing-item",  # 房产列表项
        "property_title": ".property-title, .title",
        "property_price": ".price, .property-price",
        "property_area": ".area, .property-area",
        "property_location": ".location, .address",
        "property_type": ".type, .property-type",
        "property_link": "a.property-link, a.listing-link",
        "next_page": ".next-page, .pagination-next",
    },
    pagination_type="url_param",  # 需要测试确认
    pagination_param="page",
    requires_js=True,
    rate_limit=1.5,
    max_concurrent=2,
    timeout=30,
    retry_times=3,
)


# 28Hse.com 配置
HSE28_CONFIG = SiteConfig(
    name="28Hse.com",
    base_url="https://www.28hse.com",
    list_url="https://www.28hse.com",
    domain="www.28hse.com",
    headers={
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "zh-HK,zh;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    },
    user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    selectors={
        # 需要实际测试后更新这些选择器
        "property_list": ".property-item, .listing-item, .house-item",
        "property_title": ".property-title, .title, .house-title",
        "property_price": ".price, .property-price, .house-price",
        "property_area": ".area, .property-area, .house-area",
        "property_location": ".location, .address, .house-location",
        "property_type": ".type, .property-type, .house-type",
        "property_link": "a.property-link, a.listing-link, a.house-link",
        "next_page": ".next-page, .pagination-next",
    },
    pagination_type="url_param",  # 需要测试确认
    pagination_param="page",
    requires_js=True,
    rate_limit=1.2,
    max_concurrent=3,
    timeout=30,
    retry_times=3,
)


# 利嘉阁配置
RICACORP_CONFIG = SiteConfig(
    name="利嘉阁",
    base_url="https://www.ricacorp.com",
    list_url="https://www.ricacorp.com/zh-hk",
    domain="www.ricacorp.com",
    headers={
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "zh-HK,zh;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    },
    user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    selectors={
        # 需要实际测试后更新这些选择器
        "property_list": ".property-item, .listing-item, .property-card",
        "property_title": ".property-title, .title, .card-title",
        "property_price": ".price, .property-price, .card-price",
        "property_area": ".area, .property-area, .card-area",
        "property_location": ".location, .address, .card-location",
        "property_type": ".type, .property-type, .card-type",
        "property_link": "a.property-link, a.listing-link, a.card-link",
        "next_page": ".next-page, .pagination-next",
    },
    pagination_type="url_param",  # 需要测试确认
    pagination_param="page",
    requires_js=True,
    rate_limit=1.3,
    max_concurrent=2,
    timeout=30,
    retry_times=3,
)


# 所有网站配置字典
ALL_SITES = {
    "centanet": CENTANET_CONFIG,
    "28hse": HSE28_CONFIG,
    "ricacorp": RICACORP_CONFIG,
}


def get_site_config(site_name: str) -> Optional[SiteConfig]:
    """根据网站名称获取配置"""
    return ALL_SITES.get(site_name.lower())


def get_all_configs() -> List[SiteConfig]:
    """获取所有网站配置"""
    return list(ALL_SITES.values())


if __name__ == "__main__":
    # 测试配置
    print("网站配置测试:")
    print("=" * 60)
    for name, config in ALL_SITES.items():
        print(f"\n{config.name} ({name}):")
        print(f"  基础URL: {config.base_url}")
        print(f"  列表URL: {config.list_url}")
        print(f"  需要JS: {config.requires_js}")
        print(f"  请求间隔: {config.rate_limit}秒")
        print(f"  最大并发: {config.max_concurrent}")


