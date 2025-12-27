#!/usr/bin/env python3
"""
利嘉閣地產爬蟲 (Ricacorp Crawler)
https://www.ricacorp.com/zh-hk

設計目標：
- 參考 `centanet_crawler.py` 與 `28hse_crawler.py` 的整體架構/CLI/輸出格式
- 使用 Crawl4AI (Playwright) 進行非同步爬取（支援 JS 渲染）
- 列表頁：擷取詳情頁 URL、去重、支援 url_param 分頁（若站點為 ajax 也提供簡單 fallback）
- 詳情頁：多策略解析（JSON-LD / meta / breadcrumb / regex / CSS selectors）
- 支援 category / region 篩選（category 主要影響 list_url；region 為爬完後過濾）

注意：
Ricacorp 的實際列表/詳情 URL 可能因站點改版而變更。
若抓不到 URL，建議先用 explorer 腳本確認 URL 規則，再微調 `valid_patterns` / `link_selectors`。
"""

import asyncio
import csv
import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import urljoin, urlparse, urlencode, urlunparse, parse_qsl

from crawl4ai import AsyncWebCrawler
from crawl4ai.async_configs import BrowserConfig

from data_models import PropertyData
from sites_config import RICACORP_CONFIG


class RicacorpCrawler:
    """
    利嘉閣爬蟲類
    """

    def __init__(self, output_dir: str = "data/ricacorp"):
        self.config = RICACORP_CONFIG
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.crawled_urls: set[str] = set()
        self.properties: List[PropertyData] = []
        self.failed_urls: List[str] = []

    # -----------------------------
    # URL helpers
    # -----------------------------
    @staticmethod
    def _upsert_query(url: str, params: Dict[str, str]) -> str:
        """在 URL 上覆寫/新增 query 參數（保留其它參數）。"""
        try:
            parsed = urlparse(url)
            q = dict(parse_qsl(parsed.query, keep_blank_values=True))
            q.update({k: v for k, v in params.items() if v is not None})
            new_query = urlencode(q, doseq=True)
            return urlunparse(
                (parsed.scheme, parsed.netloc, parsed.path, parsed.params, new_query, parsed.fragment)
            )
        except Exception:
            # fallback：如果解析失敗，直接回傳原始 URL
            return url

    @staticmethod
    def _normalize_url(url: str) -> str:
        """
        將 URL 的 path 做 unquote（讓 JSON 輸出更一致/可讀），保留 query/fragment。
        Playwright 對含中文的 URL 一般可正常處理；若遇到特殊情況再回退原始 URL。
        """
        from urllib.parse import unquote

        try:
            p = urlparse(url)
            if not p.scheme or not p.netloc:
                return url
            new_path = unquote(p.path)
            return urlunparse((p.scheme, p.netloc, new_path, p.params, p.query, p.fragment))
        except Exception:
            return url

    def _build_list_url(self, category: Optional[str] = None) -> str:
        """
        根據 category 建立列表頁 URL。

        由於 Ricacorp 的實際路由可能變動，這裡採用：
        - 未指定：使用 `sites_config.RICACORP_CONFIG.list_url`
        - 指定：嘗試套用站內常見語意（buy/rent/transaction），若無法判斷則退回 list_url
        """
        base = self.config.list_url
        if not category:
            return base

        c = category.strip().lower()
        # 盡量容錯：同時接受中英輸入
        if c in {"buy", "買樓", "搵盤", "sale", "二手", "二手樓盤"}:
            # 常見的 Ricacorp 站內入口是「搵盤」；未知實際 path 時，先維持在 /zh-hk 並讓使用者在站內搜尋條件下分頁。
            return base
        if c in {"rent", "租樓", "搵租", "lease", "租盤"}:
            return base
        if c in {"transaction", "成交"}:
            return base

        return base

    # -----------------------------
    # List crawling
    # -----------------------------
    async def crawl_list_page(
        self, url: str, page_num: int = 1, crawler: Optional[AsyncWebCrawler] = None
    ) -> List[str]:
        """
        爬取列表頁並回傳詳情頁 URL 清單
        """
        browser_config = BrowserConfig(headless=True, user_agent=self.config.user_agent)
        if crawler is not None:
            return await self._crawl_list_page_with_crawler(crawler, url, page_num)
        async with AsyncWebCrawler(config=browser_config) as new_crawler:
            return await self._crawl_list_page_with_crawler(new_crawler, url, page_num)

    async def _crawl_list_page_with_crawler(
        self, crawler: AsyncWebCrawler, url: str, page_num: int
    ) -> List[str]:
        print(f"  正在爬取列表頁 {page_num}...")

        from crawl4ai.async_configs import CrawlerRunConfig

        session_id = f"ricacorp_list_{hashlib.md5(url.encode('utf-8')).hexdigest()[:10]}"

        # url_param 分頁（若站點支援）
        list_url = url
        if self.config.pagination_type == "url_param" and self.config.pagination_param:
            if page_num > 1:
                list_url = self._upsert_query(url, {self.config.pagination_param: str(page_num)})

        try:
            result = await crawler.arun(
                url=list_url,
                config=CrawlerRunConfig(
                    session_id=session_id,
                    delay_before_return_html=2,
                    simulate_user=True,
                    override_navigator=True,
                    magic=True,
                ),
                timeout=max(self.config.timeout, 90),
                wait_for="domcontentloaded",  # Ricacorp 首屏可能較慢，先用 DOMContentLoaded
            )
        except Exception as e:
            print(f"  ✗ 無法訪問列表頁 {page_num}: {str(e)[:120]}")
            # 退而求其次：以短超時 + js_only 再試一次，避免頁面腳本阻塞
            try:
                result = await crawler.arun(
                    url=list_url,
                    config=CrawlerRunConfig(
                        session_id=session_id,
                        delay_before_return_html=2,
                        js_only=True,
                        simulate_user=True,
                        magic=True,
                    ),
                    timeout=max(self.config.timeout, 60),
                    wait_for="domcontentloaded",
                )
            except Exception as e2:
                print(f"  ✗ 重試仍失敗: {str(e2)[:120]}")
                return []

        if not result or not result.success:
            print(f"  ✗ 無法訪問列表頁 {page_num}")
            return []

        property_urls: List[str] = []

        try:
            from bs4 import BeautifulSoup

            soup = BeautifulSoup(result.html, "html.parser")

            invalid_patterns = [
                "/login",
                "/register",
                "/member",
                "/account",
                "/privacy",
                "/terms",
                "/disclaimer",
                "/contact",
                "/about",
                "/news",
                "/agent",
                "/branch",
                "/mortgage",
                "/property/list/",  # 列表頁/功能頁，避免誤當詳情頁
                "/property/list",   # 容錯
                ";",                # 避免抓到 /buy;postTags=... 這類 query/條件組合
                "\"",               # 避免 href 字串殘留引號
                "/api/",
                "javascript:",
                "mailto:",
                "tel:",
                "#",
            ]

            # Ricacorp 詳情頁（依你提供的實例）：/zh-hk/property/detail/...
            # 只接受 detail，避免把 /property/list/* (estate/landregistry 等) 抓進來
            valid_patterns = [
                "/zh-hk/property/detail/",
                "/property/detail/",
            ]

            # 只擷取站內連結
            link_selectors = [
                'a[href*="/zh-hk/property/detail/"]',
                'a[href*="/property/detail/"]',
                "a.property-link",
                "a.listing-link",
                "a.card-link",
            ]

            seen = set()
            for selector in link_selectors:
                links = soup.select(selector)
                for a in links:
                    href = a.get("href", "")
                    if not href:
                        continue

                    # 清理 href（避免殘留引號/空白/不完整字串）
                    href = href.strip().strip('"').strip("'")
                    if '"' in href:
                        href = href.split('"', 1)[0]
                    if "'" in href:
                        href = href.split("'", 1)[0]
                    href = href.strip()
                    href_lower = href.lower()

                    if any(p in href_lower for p in invalid_patterns):
                        continue

                    # join relative
                    if not href_lower.startswith("http"):
                        href = urljoin(self.config.base_url, href)
                        href_lower = href.lower()

                    # domain check
                    if self.config.domain not in urlparse(href).netloc.lower():
                        continue

                    # 必須是 detail URL
                    if not any(p in href_lower for p in valid_patterns):
                        continue

                    href = self._normalize_url(href)
                    if href not in seen:
                        seen.add(href)
                        property_urls.append(href)

            # 去重（保序）
            property_urls = list(dict.fromkeys(property_urls))

        except Exception as e:
            print(f"  ⚠ 提取列表頁 URL 時出錯: {str(e)[:120]}")

        if property_urls:
            print(f"  ✓ 列表頁 {page_num}: 找到 {len(property_urls)} 個房產 URL")
        else:
            print(f"  ⚠ 列表頁 {page_num}: 未找到房產 URL（可能需要更新 valid_patterns / selectors）")

        return property_urls

    # -----------------------------
    # Detail crawling
    # -----------------------------
    async def crawl_detail_page(self, url: str) -> Optional[PropertyData]:
        if not url or not url.startswith("http"):
            return None
        url = self._normalize_url(url)
        if url in self.crawled_urls:
            return None
        self.crawled_urls.add(url)

        browser_config = BrowserConfig(headless=True, user_agent=self.config.user_agent)
        try:
            async with AsyncWebCrawler(config=browser_config) as crawler:
                result = await crawler.arun(
                    url=url,
                    timeout=max(self.config.timeout, 60),
                    wait_for="networkidle",
                )
                if not result or not result.success:
                    print(f"  ✗ 無法訪問: {url[:90]}...")
                    self.failed_urls.append(url)
                    return None

                prop = self._parse_detail_page(result.html, url)
                if prop:
                    self.properties.append(prop)
                    return prop
                self.failed_urls.append(url)
                return None
        except Exception as e:
            print(f"  ✗ 爬取失敗: {url[:90]}... 錯誤: {str(e)[:120]}")
            self.failed_urls.append(url)
            return None

    # -----------------------------
    # Parsing helpers
    # -----------------------------
    @staticmethod
    def _safe_json_loads(text: str):
        try:
            return json.loads(text)
        except Exception:
            return None

    @staticmethod
    def _extract_jsonld(soup) -> List[dict]:
        """抽取頁面上的 JSON-LD（可能是 dict / list / graph）。"""
        out: List[dict] = []
        if not soup:
            return out
        for script in soup.find_all("script", attrs={"type": re.compile(r"application/ld\+json", re.I)}):
            raw = script.get_text(strip=True)
            if not raw:
                continue
            data = RicacorpCrawler._safe_json_loads(raw)
            if data is None:
                continue
            if isinstance(data, dict):
                out.append(data)
            elif isinstance(data, list):
                out.extend([x for x in data if isinstance(x, dict)])
        return out

    @staticmethod
    def _pick_from_jsonld(jsonlds: List[dict]) -> Tuple[Optional[str], Optional[str], List[str], Optional[str]]:
        """
        從 JSON-LD 嘗試抽取：
        - title/name
        - address（字串）
        - images
        - price_display（字串）
        """
        title = None
        address = None
        images: List[str] = []
        price_display = None

        def consider(node: dict):
            nonlocal title, address, images, price_display

            if not title:
                t = node.get("name") or node.get("headline")
                if isinstance(t, str) and len(t.strip()) > 1:
                    title = t.strip()

            # image
            img = node.get("image")
            if isinstance(img, str):
                images.append(img)
            elif isinstance(img, list):
                images.extend([x for x in img if isinstance(x, str)])

            # address
            addr = node.get("address")
            if not address:
                if isinstance(addr, str) and len(addr.strip()) > 1:
                    address = addr.strip()
                elif isinstance(addr, dict):
                    parts = []
                    for k in ["addressCountry", "addressRegion", "addressLocality", "streetAddress", "postalCode"]:
                        v = addr.get(k)
                        if isinstance(v, str) and v.strip():
                            parts.append(v.strip())
                    if parts:
                        address = " ".join(parts)

            # offers / price
            offers = node.get("offers")
            if isinstance(offers, dict):
                p = offers.get("price")
                currency = offers.get("priceCurrency")
                if p is not None and not price_display:
                    try:
                        price_display = f"{currency+' ' if currency else ''}{p}".strip()
                    except Exception:
                        pass
            elif isinstance(offers, list):
                for off in offers:
                    if not isinstance(off, dict):
                        continue
                    p = off.get("price")
                    currency = off.get("priceCurrency")
                    if p is not None and not price_display:
                        price_display = f"{currency+' ' if currency else ''}{p}".strip()
                        break

        for d in jsonlds:
            # @graph
            g = d.get("@graph")
            if isinstance(g, list):
                for n in g:
                    if isinstance(n, dict):
                        consider(n)
            consider(d)

        # 去重 images
        images = list(dict.fromkeys([x for x in images if x]))
        return title, address, images, price_display

    @staticmethod
    def _generate_breadcrumb(parts: List[str]) -> Optional[str]:
        parts = [p.strip() for p in parts if p and p.strip()]
        if not parts:
            return None
        # Ricacorp 常見「首頁」等
        while parts and parts[0] in {"主頁", "首頁", "Home"}:
            parts = parts[1:]
        if not parts:
            return None
        return "主頁 > " + " > ".join(parts)

    @staticmethod
    def _map_breadcrumb_fields(items: List[str]) -> Tuple[Optional[str], Optional[str], Optional[str], Optional[str], Optional[str]]:
        """
        盡量通用的面包屑映射：
        - category：二手樓盤/租盤/成交/一手樓盤 等
        - region：香港島/九龍/新界/離島
        - district_level2/sub_district/estate_name：剩下的層級按出現順序填充
        """
        if not items:
            return None, None, None, None, None

        normalized = [x.strip() for x in items if x and x.strip()]
        # remove home
        while normalized and normalized[0] in {"主頁", "首頁", "Home"}:
            normalized = normalized[1:]

        category = None
        region = None
        district_level2 = None
        sub_district = None
        estate_name = None

        category_candidates = {"買樓", "搵盤", "二手樓盤", "一手樓盤", "租盤", "搵租", "成交", "二手成交"}
        region_candidates = {"香港島", "港島", "九龍", "九龙", "新界", "離島", "离岛"}

        rest: List[str] = []
        for x in normalized:
            if not category and x in category_candidates:
                category = x
                continue
            if not region and x in region_candidates:
                # normalize 港島 -> 香港島
                region = "香港島" if x == "港島" else ("離島" if x == "离岛" else x)
                continue
            rest.append(x)

        # 依序填入
        if rest:
            district_level2 = rest[0] if len(rest) > 0 else None
            sub_district = rest[1] if len(rest) > 1 else None
            estate_name = rest[-1] if len(rest) > 2 else (rest[1] if len(rest) == 2 else None)

        return category, region, district_level2, sub_district, estate_name

    @staticmethod
    def _map_breadcrumb_fields_ricacorp(items: List[str]) -> Tuple[
        Optional[str], Optional[str], Optional[str], Optional[str], Optional[str], Optional[str]
    ]:
        """
        Ricacorp 详情页面包屑（你提供的例子）：
        主頁 > 二手真盤源 > 新界西 > 屯門 > 屯門南 > 兆麟苑 > 旭麟閣 (J座)

        對應（基本規則）：
        - category: parts[0]
        - region: parts[1]
        - district: parts[2]
        - district_level2: parts[3]
        - sub_district:
          - 若最後一段是「X座」(例如 4座/36座/J座)，則把 sub_district 設為 district_level2（例如 兆康）
          - 否則保持 None（例如「屯門南 > 兆麟苑 > 旭麟閣 (J座)」）
        - estate_name:
          - 若最後一段是「X座」，則合成「屋苑 (X座)」
          - 否則取 parts[4]（屋苑）
        """
        if not items:
            return None, None, None, None, None, None

        parts = [x.strip() for x in items if x and x.strip()]
        while parts and parts[0] in {"主頁", "首頁", "Home"}:
            parts = parts[1:]
        # parts now like: [二手真盤源, 新界西, 屯門, 屯門南, 兆麟苑, 旭麟閣 (J座)]
        # or: [二手真盤源, 新界西, 屯門, 兆康, 疊茵庭, 4座]
        category = parts[0] if len(parts) >= 1 else None
        region = parts[1] if len(parts) >= 2 else None
        district = parts[2] if len(parts) >= 3 else None
        district_level2 = parts[3] if len(parts) >= 4 else None

        last = parts[-1] if parts else None
        # 檢查最後一段是否為純「X座」（例如：4座、36座、J座）
        is_seat = bool(last and re.match(r"^\d+座$", last)) or bool(last and re.match(r"^[A-Za-z]座$", last))

        sub_district: Optional[str] = None
        estate_name: Optional[str] = None

        if len(parts) >= 5:
            # base estate is parts[4]（例如：兆麟苑 或 疊茵庭）
            base_estate = parts[4]
            if is_seat and len(parts) >= 6:
                # 兆康例子：sub_district = 兆康（district_level2），estate_name = 疊茵庭 (4座)
                sub_district = district_level2
                estate_name = f"{base_estate} ({last})"
            else:
                # 屯門南例子：parts = [二手真盤源, 新界西, 屯門, 屯門南, 兆麟苑, 旭麟閣 (J座)]
                # estate_name = 兆麟苑（parts[4]），不取最後一段因為它包含「(J座)」
                estate_name = base_estate

        return category, region, district, district_level2, sub_district, estate_name

    @staticmethod
    def _derive_region_district(page_text: str) -> Tuple[Optional[str], Optional[str]]:
        """從頁面文本裡粗略推斷 region / district（僅關鍵詞匹配）。"""
        region_candidates = ["香港島", "港島", "九龍", "九龙", "新界東", "新界东", "新界西", "新界", "離島", "离岛"]
        region = None
        for rg in region_candidates:
            if rg in page_text:
                region = "香港島" if rg == "港島" else ("離島" if rg == "离岛" else rg)
                break

        # 區域關鍵詞（非完整列表，先匹配常見字串）
        district_candidates = [
            "中半山", "西半山", "上環", "中環", "金鐘", "灣仔", "銅鑼灣", "北角", "筲箕灣", "西灣河", "柴灣", "小西灣",
            "九龍站", "尖沙咀", "佐敦", "油麻地", "旺角", "太子", "深水埗", "長沙灣", "荔枝角", "美孚", "何文田", "九龍城",
            "土瓜灣", "黃大仙", "鑽石山", "新蒲崗", "九龍灣", "牛頭角", "觀塘", "藍田", "油塘",
            "沙田", "大圍", "火炭", "馬鞍山", "大埔", "粉嶺", "上水", "荃灣", "葵涌", "青衣", "屯門", "元朗", "天水圍",
            "將軍澳", "西貢", "清水灣", "東涌", "離島", "愉景灣",
        ]
        district = None
        for d in district_candidates:
            if d in page_text:
                district = d
                break
        return region, district

    @staticmethod
    def _breadcrumb_from_url(url: str, page_text: str) -> List[str]:
        """
        若頁面缺少 breadcrumb，嘗試從詳情 URL slug 推斷。
        例：https://www.ricacorp.com/zh-hk/property/detail/沙田第一城-hma-沙田第一城-7期-36座-ch63281948-3-hk
        期望：["二手真盤源", "新界東", "沙田", "沙田第一城", "沙田第一城", "沙田第一城 7期", "36座"]
        """
        from urllib.parse import unquote

        path = urlparse(url).path
        segs = [s for s in path.split("/") if s]
        slug = segs[-1] if segs else ""
        slug = unquote(slug)
        tokens = [t for t in slug.split("-") if t]

        # 移除 ID / 無關 token
        filtered = []
        for t in tokens:
            tl = t.lower()
            if tl in {"hma", "hk"}:
                continue
            if re.match(r"[a-z]{1,3}\d{5,}", tl):
                continue
            filtered.append(t)
        tokens = filtered

        region, district_guess = RicacorpCrawler._derive_region_district(page_text)

        # 嘗試從 slug token 推斷（不同房源 URL 結構不一致，這裡只做保守推導）：
        # 例1：屯門南-hma-兆麟苑-旭麟閣-j座-...
        #   district_level2=屯門南, estate_name=兆麟苑, building=旭麟閣 (J座)
        # 例2：沙田第一城-hma-沙田第一城-7期-36座-...
        #   estate_name=沙田第一城, phase=7期, block=36座
        district_level2 = tokens[0] if tokens else None
        estate_name = None
        building = None
        phase = None
        block = None

        # 找到 hma 後的 token 片段更接近樓盤結構
        tail = tokens
        for i, t in enumerate(tokens):
            if t.lower() == "hma":
                tail = tokens[i + 1 :]
                break

        if tail:
            estate_name = tail[0]
            # 其餘嘗試組合樓座/期數
            for t in tail[1:]:
                if "期" in t and not phase:
                    phase = t
                if ("座" in t or t.lower().endswith("座")) and not block:
                    block = t
            # building：如果有第二段（如 旭麟閣），以及 j座/k座 之類，組合成「旭麟閣 (J座)」
            if len(tail) >= 2:
                base_building = tail[1]
                # 找樓座 token（例如 j座 / k座 / 36座）
                seat = None
                for t in tail[2:]:
                    if re.match(r"^[a-zA-Z]\s*座$", t) or re.match(r"^[a-zA-Z]座$", t):
                        seat = t.upper()
                        break
                    if "座" in t:
                        seat = t
                        break
                if seat and "座" in seat and "(" not in base_building:
                    # 旭麟閣 + J座 -> 旭麟閣 (J座)
                    building = f"{base_building} ({seat})"
                else:
                    building = base_building

        breadcrumb_parts: List[str] = ["二手真盤源"]
        if region:
            breadcrumb_parts.append(region)
        # district：優先用從文本推導；沒有就用 district_level2 的上層（無法推就略）
        if district_guess:
            breadcrumb_parts.append(district_guess)
        if district_level2:
            breadcrumb_parts.append(district_level2)
        if estate_name:
            breadcrumb_parts.append(estate_name)
        if building:
            breadcrumb_parts.append(building)
        elif estate_name and phase:
            breadcrumb_parts.append(f"{estate_name} {phase}")
        if block:
            breadcrumb_parts.append(block)

        # 去除空白
        breadcrumb_parts = [p.strip() for p in breadcrumb_parts if p and p.strip()]
        return breadcrumb_parts

    def _parse_detail_page(self, html: str, url: str) -> Optional[PropertyData]:
        try:
            from bs4 import BeautifulSoup
        except Exception:
            print("  ⚠ BeautifulSoup 未安裝，無法解析詳情頁")
            return None

        # soup（嘗試多 parser）
        soup = None
        for parser in ["html.parser", "lxml", "html5lib"]:
            try:
                soup = BeautifulSoup(html, parser)
                break
            except Exception:
                continue
        if soup is None:
            return None

        page_text = soup.get_text(separator=" ", strip=True) if soup else ""

        # init fields
        title = None
        category = None
        region = None
        district = None
        district_level2 = None
        sub_district = None
        estate_name = None
        area_name = None
        street = None
        address = None
        price_value: Optional[float] = None
        price_display: Optional[str] = None
        monthly_mortgage_payment: Optional[str] = None
        area_value: Optional[float] = None
        area_display: Optional[str] = None
        property_type: Optional[str] = None
        bedrooms: Optional[int] = None
        bathrooms: Optional[int] = None
        floor: Optional[str] = None
        building_age: Optional[int] = None
        orientation: Optional[str] = None
        description: Optional[str] = None
        images: List[str] = []

        property_id = hashlib.md5(url.encode("utf-8")).hexdigest()[:16]

        # JSON-LD first (often most structured)
        jsonlds = self._extract_jsonld(soup)
        jl_title, jl_address, jl_images, jl_price = self._pick_from_jsonld(jsonlds)
        if jl_title:
            title = jl_title
        if jl_address:
            address = jl_address
        if jl_images:
            images.extend(jl_images)
        if jl_price:
            price_display = jl_price

        # title from DOM
        if not title:
            for sel in ["h1", ".property-title", ".title", "[class*='title']"]:
                el = soup.select_one(sel)
                if el:
                    t = el.get_text(strip=True)
                    if t and len(t) > 1:
                        title = t
                        break
        if not title:
            tt = soup.find("title")
            if tt:
                t = tt.get_text(strip=True)
                if t:
                    title = t

        # breadcrumb
        breadcrumb_items: List[str] = []
        for selector in [
            "nav[aria-label*='breadcrumb']",
            "nav[aria-label*='Breadcrumb']",
            ".breadcrumb",
            ".breadcrumbs",
            "[class*='breadcrumb']",
        ]:
            nav = soup.select_one(selector)
            if not nav:
                continue
            # Ricacorp 的 breadcrumb 可能包含純文字與 ">" 分隔（不一定都是 <a>）
            # 優先使用 <a> 標籤的文本，因為它們更準確
            links = nav.find_all("a")
            if links:
                for a in links:
                    t = a.get_text(strip=True)
                    if t and t not in {"主頁", "首頁", "Home"}:
                        breadcrumb_items.append(t)
            else:
                # fallback: 從文本中提取
                txt = nav.get_text(" ", strip=True)
                if ">" in txt:
                    breadcrumb_items = [x.strip() for x in txt.split(">") if x.strip()]
            if breadcrumb_items:
                break

        # 若頁面無 breadcrumb，嘗試從 URL slug 推導
        if not breadcrumb_items:
            breadcrumb_items = self._breadcrumb_from_url(url, page_text)

        # 去重：移除連續重複的項（例如：屯門南 > 屯門南）
        # 同時過濾掉純「X座」格式的項（例如：j座、J座），因為它們通常已經包含在上一項中（例如：旭麟閣 (J座)）
        if breadcrumb_items:
            deduplicated = []
            prev = None
            for item in breadcrumb_items:
                item_clean = item.strip()
                if not item_clean:
                    continue
                # 跳過純「X座」格式（例如：j座、J座、4座、36座），因為它們通常已經包含在上一項中
                if re.match(r"^[A-Za-z0-9]+座$", item_clean):
                    continue
                # 移除連續重複的項
                if item_clean != prev:
                    deduplicated.append(item_clean)
                    prev = item_clean
            breadcrumb_items = deduplicated

        breadcrumb = self._generate_breadcrumb(breadcrumb_items) if breadcrumb_items else None
        if breadcrumb_items:
            # 優先用 Ricacorp 固定映射（以詳情頁 breadcrumb 為準）
            rc_category, rc_region, rc_district, rc_district_level2, rc_sub_district, rc_estate_name = (
                self._map_breadcrumb_fields_ricacorp(breadcrumb_items)
            )
            category = rc_category or category
            region = rc_region or region
            district = rc_district or district
            district_level2 = rc_district_level2 or district_level2
            sub_district = rc_sub_district if rc_sub_district is not None else sub_district
            estate_name = rc_estate_name or estate_name

        # price parsing (fallback)
        if not price_display:
            # common patterns: HK$ 1,250萬 / $12,500,000 / 1250 萬
            m = re.search(r"(HK\$|\$)\s*([\d,]+(?:\.\d+)?)\s*(萬|万)?", page_text)
            if m:
                price_display = m.group(0).strip()
        if price_display and price_value is None:
            m = re.search(r"([\d,]+(?:\.\d+)?)", price_display.replace(",", ""))
            if m:
                try:
                    v = float(m.group(1))
                    if "萬" in price_display or "万" in price_display:
                        v *= 10000
                    price_value = v
                except Exception:
                    pass

        # area parsing
        # prefer "實用面積" then "建築面積"
        if area_display is None:
            m = re.search(r"(實用面積|建築面積)\s*[:：]?\s*([\d,]+)\s*(呎|ft²|sqft)", page_text)
            if m:
                area_display = f"{m.group(2)}{m.group(3)}"
        if area_display is None:
            m = re.search(r"([\d,]+)\s*(呎|ft²|sqft)", page_text, re.I)
            if m:
                area_display = f"{m.group(1)}{m.group(2)}"
        if area_display and area_value is None:
            m = re.search(r"([\d,]+(?:\.\d+)?)", area_display.replace(",", ""))
            if m:
                try:
                    area_value = float(m.group(1))
                except Exception:
                    pass

        # monthly mortgage (optional)
        m = re.search(r"(月供|按揭)\s*[:：]?\s*(HK\$|\$)?\s*([\d,]+)", page_text)
        if m:
            monthly_mortgage_payment = f"${m.group(3)}"

        # property_type / bedrooms / bathrooms
        m = re.search(r"(\d+)\s*房", page_text)
        if m:
            property_type = f"{m.group(1)}房"
            try:
                bedrooms = int(m.group(1))
            except Exception:
                pass
        m = re.search(r"(\d+)\s*廁", page_text)
        if m:
            try:
                bathrooms = int(m.group(1))
            except Exception:
                pass

        # floor (very heuristic)
        m = re.search(r"(高層|中層|低層|\d+\s*樓|\d+\s*層)", page_text)
        if m:
            floor = m.group(1).replace(" ", "")

        # description
        for sel in [".description", ".property-description", "[class*='description']"]:
            el = soup.select_one(sel)
            if el:
                d = el.get_text(" ", strip=True)
                if d and len(d) > 10:
                    description = d
                    break
        if not description:
            # fallback: meta description
            md = soup.find("meta", attrs={"name": "description"})
            if md and md.get("content"):
                description = md["content"].strip()

        # images (fallback)
        # og:image
        og = soup.find("meta", attrs={"property": "og:image"})
        if og and og.get("content"):
            images.append(og["content"].strip())
        # img tags
        for img in soup.find_all("img"):
            src = img.get("src") or img.get("data-src") or img.get("data-original")
            if not src:
                continue
            if not src.startswith("http"):
                src = urljoin(self.config.base_url, src)
            # skip tiny/base64
            if src.startswith("data:"):
                continue
            images.append(src)
        images = list(dict.fromkeys(images))

        # address fallback: try meta / visible "地址"
        if not address:
            # sometimes stored in meta property
            for key in ["og:description", "twitter:description"]:
                mtag = soup.find("meta", attrs={"property": key}) or soup.find("meta", attrs={"name": key})
                if mtag and mtag.get("content"):
                    c = mtag["content"].strip()
                    # avoid too-long marketing copy
                    if c and ("香港" in c or "九龍" in c or "新界" in c or "離島" in c):
                        address = c
                        break

        # district/area_name/street best-effort from breadcrumb/title
        if not estate_name and title:
            # title often contains estate name
            t = re.sub(r"\s*-\s*利嘉閣.*$", "", title).strip()
            t = re.sub(r"\s*\#?\d+.*$", "", t).strip()
            if t and len(t) > 1:
                estate_name = t
        if not area_name and estate_name:
            area_name = estate_name
        if not district and district_level2:
            district = district_level2

        # final breadcrumb string (if missing)
        if not breadcrumb and any([category, region, district_level2, sub_district, estate_name]):
            parts = []
            for p in [category, region, district_level2, sub_district, estate_name]:
                if p:
                    parts.append(p)
            breadcrumb = self._generate_breadcrumb(parts)

        # If still no title, fallback to URL last segment
        if not title:
            path = urlparse(url).path
            segs = [s for s in path.split("/") if s]
            title = segs[-1] if segs else "未知物業"

        # Build PropertyData
        return PropertyData(
            property_id=property_id,
            source="ricacorp",
            url=url,
            title=title,
            price=price_value,
            price_display=price_display,
            monthly_mortgage_payment=monthly_mortgage_payment,
            area=area_value,
            area_display=area_display,
            district=district,
            area_name=area_name,
            street=street,
            address=address,
            property_type=property_type,
            bedrooms=bedrooms,
            bathrooms=bathrooms,
            floor=floor,
            building_age=building_age,
            orientation=orientation,
            description=description,
            images=images,
            category=category,
            region=region,
            district_level2=district_level2,
            sub_district=sub_district,
            estate_name=estate_name,
            breadcrumb=breadcrumb,
            crawl_date=datetime.now(),
        )

    # -----------------------------
    # Orchestration
    # -----------------------------
    async def crawl_all(
        self,
        max_pages: int = 5,
        max_properties: Optional[int] = None,
        category: Optional[str] = None,
        region: Optional[str] = None,
    ):
        print("=" * 70)
        print("開始爬取 Ricacorp 資料")
        print("=" * 70)

        list_url = self._build_list_url(category)
        print(f"列表頁URL: {list_url}")
        if category:
            print(f"類別篩選(category): {category}")
        if region:
            print(f"地區篩選(region): {region}")
        print(f"最大頁數: {max_pages}")
        print(f"最大房產數: {max_properties or '不限制'}")
        print("=" * 70)

        browser_config = BrowserConfig(headless=True, user_agent=self.config.user_agent)

        all_property_urls: List[str] = []
        async with AsyncWebCrawler(config=browser_config) as crawler:
            for page in range(1, max_pages + 1):
                print(f"\n[列表頁 {page}/{max_pages}]")
                urls = await self.crawl_list_page(list_url, page, crawler=crawler)
                print(f"  本頁擷取到 {len(urls)} 個 URL")
                if not urls:
                    if page > 1:
                        break
                else:
                    all_property_urls.extend(urls)

                if max_properties and len(all_property_urls) >= max_properties:
                    all_property_urls = all_property_urls[:max_properties]
                    break

                await asyncio.sleep(self.config.rate_limit)

        # 去重
        all_property_urls = list(set(all_property_urls))
        print(f"\n總共找到 {len(all_property_urls)} 個唯一 URL")
        if not all_property_urls:
            print("沒有找到任何房產 URL（可能需要調整 Ricacorp 的 URL 規則）")
            return

        if max_properties:
            all_property_urls = all_property_urls[:max_properties]

        print("\n開始爬取詳情頁...")
        semaphore = asyncio.Semaphore(self.config.max_concurrent)
        completed = 0
        total = len(all_property_urls)

        async def crawl_with_limit(u: str):
            nonlocal completed
            async with semaphore:
                r = await self.crawl_detail_page(u)
                completed += 1
                if completed % 10 == 0 or completed == total:
                    print(f"  進度: {completed}/{total} ({completed * 100 // total}%)")
                return r

        results = await asyncio.gather(*[crawl_with_limit(u) for u in all_property_urls], return_exceptions=True)
        success_count = sum(1 for r in results if r and not isinstance(r, Exception))
        error_count = sum(1 for r in results if isinstance(r, Exception))

        # region filter (post-filter)
        if region:
            print(f"\n根據地區 '{region}' 過濾結果...")
            original = len(self.properties)
            region_variants = {
                "香港島": ["香港島", "港島", "香港岛"],
                "九龍": ["九龍", "九龙"],
                "新界": ["新界", "新界東", "新界东", "新界西"],
                "離島": ["離島", "离岛"],
            }
            region_matches = [region]
            for _, variants in region_variants.items():
                if region in variants or any(v in region for v in variants):
                    region_matches.extend(variants)
                    break
            region_matches = list(set(region_matches))

            filtered: List[PropertyData] = []
            for p in self.properties:
                if p.region and p.region in region_matches:
                    filtered.append(p)
                elif p.address and any(rm in p.address for rm in region_matches):
                    filtered.append(p)
            self.properties = filtered
            print(f"  原始記錄數: {original}")
            print(f"  過濾後保留: {len(self.properties)}")

        print("\n" + "=" * 70)
        print("爬取完成!")
        print(f"  總URL數: {len(all_property_urls)}")
        print(f"  成功解析: {success_count}")
        print(f"  異常: {error_count}")
        print(f"  實際保存記錄數: {len(self.properties)}")
        print("=" * 70)

        if self.properties:
            self.save_data()
        else:
            print("\n⚠ 沒有成功爬取到任何房產資料")

    def save_data(self):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # JSON
        json_file = self.output_dir / f"properties_{timestamp}.json"
        data = [p.to_dict() for p in self.properties]
        with open(json_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"\n✓ JSON 已保存到: {json_file}")
        print(f"  共 {len(data)} 條記錄")

        # CSV
        csv_file = self.output_dir / f"properties_{timestamp}.csv"
        if self.properties:
            try:
                fieldnames = list(self.properties[0].to_dict().keys())
                with open(csv_file, "w", encoding="utf-8", newline="") as f:
                    writer = csv.DictWriter(f, fieldnames=fieldnames)
                    writer.writeheader()
                    for p in self.properties:
                        writer.writerow(p.to_dict())
                print(f"✓ CSV 已保存到: {csv_file}")
            except Exception as e:
                print(f"✗ 保存CSV失敗: {str(e)[:120]}")

        # failed urls
        if self.failed_urls:
            failed_file = self.output_dir / f"failed_urls_{timestamp}.txt"
            with open(failed_file, "w", encoding="utf-8") as f:
                for u in self.failed_urls:
                    f.write(u + "\n")
            print(f"⚠ 失敗URL列表已保存到: {failed_file}")


async def main():
    import argparse

    parser = argparse.ArgumentParser(description="利嘉閣 Ricacorp 爬蟲")
    parser.add_argument("--max-pages", type=int, default=2, help="最大爬取頁數")
    parser.add_argument("--max-properties", type=int, default=50, help="最大爬取房產數量")
    parser.add_argument("--category", type=str, default=None, help="類別篩選：buy/買樓, rent/租樓, transaction/成交")
    parser.add_argument("--region", type=str, default=None, help="地區篩選：香港島/港島, 九龍, 新界, 離島 等")
    args = parser.parse_args()

    crawler = RicacorpCrawler()
    await crawler.crawl_all(
        max_pages=args.max_pages,
        max_properties=args.max_properties,
        category=args.category,
        region=args.region,
    )


if __name__ == "__main__":
    asyncio.run(main())


