#!/usr/bin/env python3
"""
数据模型定义
定义房产数据的结构
"""

from dataclasses import dataclass, field
from typing import List, Optional
from datetime import datetime


@dataclass
class PropertyData:
    """房产数据模型"""
    # 基本信息（无默认值的字段在前）
    property_id: str  # 房产唯一标识
    url: str  # 详情页URL
    title: str  # 标题
    
    # 有默认值的字段在后
    source: str = "centanet"  # 数据来源
    
    # 核心信息
    price: Optional[float] = None  # 价格（港币）
    price_display: Optional[str] = None  # 价格显示文本（如"500万"）
    monthly_mortgage_payment: Optional[str] = None  # 月供（如"$30,885"）
    area: Optional[float] = None  # 面积（平方英尺）
    area_display: Optional[str] = None  # 面积显示文本
    
    # 位置信息
    district: Optional[str] = None  # 区域
    area_name: Optional[str] = None  # 地区名称
    street: Optional[str] = None  # 街道
    address: Optional[str] = None  # 完整地址
    
    # 层级导航信息（面包屑）
    category: Optional[str] = None  # 类别（如"買樓"、"租樓"）
    region: Optional[str] = None  # 大区（如"新界西"、"港島"）
    district_level2: Optional[str] = None  # 二级区域（如"屯門"）
    sub_district: Optional[str] = None  # 子区域（如"屯門新墟"）
    estate_name: Optional[str] = None  # 屋苑名称（如"御半山"）
    breadcrumb: Optional[str] = None  # 完整面包屑路径（用">"分隔，如"主頁 > 買樓 > 新界西 > 屯門 > 屯門市中心 > 瓏門"）
    
    # 房产属性
    property_type: Optional[str] = None  # 房型（如"2房"）
    bedrooms: Optional[int] = None  # 卧室数
    bathrooms: Optional[int] = None  # 浴室数
    floor: Optional[str] = None  # 楼层
    building_age: Optional[int] = None  # 楼龄
    orientation: Optional[str] = None  # 朝向
    
    # 其他信息
    description: Optional[str] = None  # 描述
    images: List[str] = field(default_factory=list)  # 图片URL列表
    facilities: List[str] = field(default_factory=list)  # 设施列表
    
    # 元数据
    post_date: Optional[datetime] = None  # 发布日期
    update_date: Optional[datetime] = None  # 更新时间
    crawl_date: datetime = field(default_factory=datetime.now)  # 爬取时间
    
    def to_dict(self) -> dict:
        """转换为字典"""
        data = {
            'property_id': self.property_id,
            'source': self.source,
            'url': self.url,
            'title': self.title,
            'price': self.price,
            'price_display': self.price_display,
            'monthly_mortgage_payment': self.monthly_mortgage_payment,
            'area': self.area,
            'area_display': self.area_display,
            'district': self.district,
            'area_name': self.area_name,
            'street': self.street,
            'address': self.address,
            'category': self.category,
            'region': self.region,
            'district_level2': self.district_level2,
            'sub_district': self.sub_district,
            'estate_name': self.estate_name,
            'breadcrumb': self.breadcrumb,
            'property_type': self.property_type,
            'bedrooms': self.bedrooms,
            'bathrooms': self.bathrooms,
            'floor': self.floor,
            'building_age': self.building_age,
            'orientation': self.orientation,
            'description': self.description,
            'images': self.images,
            'facilities': self.facilities,
            'post_date': self.post_date.isoformat() if self.post_date else None,
            'update_date': self.update_date.isoformat() if self.update_date else None,
            'crawl_date': self.crawl_date.isoformat(),
        }
        return data

