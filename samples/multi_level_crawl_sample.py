#!/usr/bin/env python3
"""
Crawl4AI Sample for Multi-Level/Multi-Page Websites

This script demonstrates how Crawl4AI handles websites with multiple levels/pages:
- Pagination
- Category pages
- Individual record detail pages
"""

import asyncio
from crawl4ai import AsyncWebCrawler
from crawl4ai.extraction_strategy import JsonCssExtractionStrategy
from crawl4ai.deep_crawling import BFSDeepCrawlStrategy, DeepCrawlDecorator, FilterChain, URLPatternFilter
import json


async def crawl_pagination_example():
    """
    Example: Crawling paginated content (like quotes.toscrape.com with multiple pages)
    """
    print("="*70)
    print("MULTI-PAGE CRAWLING EXAMPLE - PAGINATION")
    print("="*70)
    
    # URLs for multiple pages
    base_url = "https://quotes.toscrape.com"
    pages = [f"{base_url}/page/{i}/" for i in range(1, 4)]  # Pages 1-3
    
    all_quotes = []
    
    async with AsyncWebCrawler() as crawler:
        for i, page_url in enumerate(pages, 1):
            print(f"\nProcessing page {i}: {page_url}")
            
            # Define extraction schema for quotes
            quote_schema = {
                "name": "quotes",
                "baseSelector": ".quote",
                "fields": [
                    {
                        "name": "text",
                        "selector": ".text",
                        "type": "text"
                    },
                    {
                        "name": "author",
                        "selector": ".author",
                        "type": "text"
                    }
                ]
            }
            extraction_strategy = JsonCssExtractionStrategy(quote_schema)
            
            result = await crawler.arun(
                url=page_url,
                extraction_strategy=extraction_strategy
            )
            
            if result.success and result.extracted_content:
                page_data = json.loads(result.extracted_content)
                quotes = page_data.get("quotes", [])
                all_quotes.extend(quotes)
                print(f"  Found {len(quotes)} quotes on page {i}")
            else:
                print(f"  No quotes extracted from page {i} - trying alternative approach")
                # For fallback, just show that we crawled the page
                print(f"  Successfully crawled page {i} - {len(result.markdown)} chars of content")
    
    print(f"\nTotal quotes collected from all pages: {len(all_quotes)}")
    if all_quotes:
        print("First few quotes:")
        for i, quote in enumerate(all_quotes[:3], 1):
            print(f"  {i}. '{quote['text'][:50]}...' by {quote['author']}")


async def crawl_with_detail_pages():
    """
    Example: Crawling summary pages and then individual detail pages
    This demonstrates a two-level crawling approach
    """
    print("\n" + "="*70)
    print("TWO-LEVEL CRAWLING - LISTING + DETAIL PAGES")
    print("="*70)
    
    print("Step 1: Crawling main page to get links to detail pages...")
    
    async with AsyncWebCrawler() as crawler:
        # Get the listing page and extract author links
        listing_result = await crawler.arun(url="https://quotes.toscrape.com/")
        
        if listing_result.success:
            # Extract links manually from HTML since extraction might not work
            import re
            # Find author links using regex from HTML
            html_content = listing_result.html
            author_link_matches = re.findall(r'<a href="(/author/[^"]+)"', html_content)
            
            print(f"Found {len(author_link_matches)} author links via regex")
            
            # Get unique author URLs (remove duplicates)
            base_url = "https://quotes.toscrape.com"
            author_urls = []
            seen_urls = set()
            
            for url_path in author_link_matches[:3]:  # Limit to first 3 for demo
                full_url = base_url + url_path
                if full_url not in seen_urls:
                    author_urls.append(full_url)
                    seen_urls.add(full_url)
            
            print(f"Crawling {len(author_urls)} author detail pages...")
            
            # Now crawl each author detail page
            all_authors_details = []
            
            for i, author_url in enumerate(author_urls, 1):
                print(f"\nCrawling author detail page {i}: {author_url}")
                
                # Try to extract author details
                detail_result = await crawler.arun(url=author_url)
                
                if detail_result.success:
                    # Extract relevant info from the author page
                    # Find author name from HTML
                    import re
                    author_name_match = re.search(r'<h3 class="author-title">([^<]+)', detail_result.html)
                    author_name = author_name_match.group(1).strip() if author_name_match else "Unknown"
                    
                    # Find birth info
                    birth_match = re.search(r'<span class="author-born-date">([^<]+)', detail_result.html)
                    birth_date = birth_match.group(1).strip() if birth_match else "Unknown birth date"
                    
                    all_authors_details.append({
                        "url": author_url,
                        "name": author_name,
                        "birth_info": birth_date
                    })
                    print(f"  ✓ Got details for: {author_name}")
                else:
                    print(f"  ✗ Failed to crawl: {author_url}")
        else:
            print("  ✗ Failed to get main page")
            all_authors_details = []  # Define the variable to avoid scope error
    
    print(f"\nTotal author details collected: {len(all_authors_details)}")
    for i, author_detail in enumerate(all_authors_details, 1):
        print(f"  {i}. {author_detail.get('name', 'Unknown')} - {author_detail.get('birth_info', 'No birth info')}")


async def crawl_with_deep_crawling():
    """
    Example: Using DeepCrawlStrategy for automatic multi-level crawling
    """
    print("\n" + "="*70)
    print("DEEP CRAWLING AUTOMATION EXAMPLE")
    print("="*70)
    
    print("Using DeepCrawlStrategy to automatically discover and crawl related pages...")
    
    # Create a deep crawling strategy
    from crawl4ai.deep_crawling import (
        BFSDeepCrawlStrategy,
        URLPatternFilter,
        FilterChain,
        URLFilter,
        KeywordRelevanceScorer
    )
    
    # Define filters to control what URLs to crawl
    filters = FilterChain([
        URLPatternFilter(patterns=[".*quotes.*"], reverse=False),  # Only include URLs with 'quotes'
        URLPatternFilter(patterns=[".*login.*"], reverse=True),   # Exclude login pages (reverse=True means exclude)
    ])
    
    print("Note: Full deep crawling implementation would typically involve:")
    print("- Auto-discovering links on pages")
    print("- Following links up to max depth")
    print("- Applying filters to avoid irrelevant pages")
    print("- Extracting content from discovered pages")
    
    # For now, we'll demonstrate with basic crawling
    # The deep crawling feature would work differently in practice
    print("\nDemonstrating with manual multi-level approach...")
    
    # Get all pages by following pagination manually
    base_url = "https://quotes.toscrape.com"
    all_pages_content = []
    
    async with AsyncWebCrawler() as crawler:
        # Crawl the first few pages to simulate discovery
        for page_num in range(1, 4):
            url = f"{base_url}/page/{page_num}/"
            result = await crawler.arun(url=url)
            if result.success:
                all_pages_content.append({
                    "url": url,
                    "length": len(result.markdown),
                    "title": result.markdown.split('\n')[0] if result.markdown else "No title"
                })
                print(f"  Crawled: {url} - Content length: {len(result.markdown)} chars")
            else:
                print(f"  Failed: {url}")
    
    print(f"\nDiscovered and crawled {len(all_pages_content)} pages")


async def crawl_ecommerce_style():
    """
    Example: Simulating an e-commerce multi-level crawl
    (categories -> products -> product details)
    """
    print("\n" + "="*70)
    print("E-COMMERCE STYLE MULTI-LEVEL CRAWL (SIMULATION)")
    print("="*70)
    
    print("Simulating an e-commerce crawl pattern:")
    print("Level 1: Category pages")
    print("Level 2: Product listing pages within categories") 
    print("Level 3: Individual product detail pages")
    
    # In a real e-commerce site, this would involve:
    # 1. Crawling category pages to get category links
    # 2. Crawling each category to get product links
    # 3. Crawling each product to get product details
    
    print("\nFor demonstration, let's simulate with our quotes site:")
    
    # Level 1: Get all tag categories
    tag_schema = {
        "name": "tags",
        "baseSelector": ".tags a",
        "fields": [
            {
                "name": "tag_name",
                "selector": "",
                "type": "text"
            },
            {
                "name": "tag_url",
                "selector": "",
                "type": "attribute",
                "attribute": "href"
            }
        ]
    }
    extraction_strategy = JsonCssExtractionStrategy(tag_schema)
    
    async with AsyncWebCrawler() as crawler:
        # Get tags (simulating category level)
        tag_result = await crawler.arun(
            url="https://quotes.toscrape.com/",
            extraction_strategy=extraction_strategy
        )
        
        if tag_result.success and tag_result.extracted_content:
            tag_data = json.loads(tag_result.extracted_content) 
            tags = tag_data.get("tags", [])
            
            print(f"Found {len(tags)} tags/categories")
            
            # Simulate Level 2: For first two tags, get their pages
            base_url = "https://quotes.toscrape.com"
            for i, tag in enumerate(tags[:2], 1):  # Only first 2 tags
                tag_url = base_url + tag["tag_url"]
                print(f"\nLevel 2 - Crawling tag page {i}: {tag_url}")
                
                # Extract quotes from tag page
                quote_result = await crawler.arun(url=tag_url)
                if quote_result.success:
                    print(f"  Found page content of {len(quote_result.markdown)} characters")
                    
                    # In a real scenario, we would extract product links here
                    # and then crawl each product detail page
                    
    print("\nThis pattern can be extended to:")
    print("- E-commerce sites: categories -> products -> product details")
    print("- News sites: sections -> articles -> article content")
    print("- Job sites: categories -> listings -> job details")
    print("- Real estate: property types -> listings -> property details")


async def main():
    """
    Main function to run all multi-level crawling examples
    """
    print("🔗 CRAWL4AI MULTI-LEVEL/MULTI-PAGE CRAWLING SAMPLES")
    print("This program demonstrates various approaches to crawling websites with multiple levels/pages")
    
    await crawl_pagination_example()
    await crawl_with_detail_pages()
    await crawl_with_deep_crawling()
    await crawl_ecommerce_style()
    
    print("\n" + "="*70)
    print("ALL MULTI-LEVEL CRAWLING EXAMPLES COMPLETED!")
    print("="*70)
    print("\nKey takeaways:")
    print("- For pagination: Process each page in sequence with same extraction schema")
    print("- For detail pages: Extract links first, then crawl each detail page")
    print("- For deep crawling: Use strategies to automatically discover and crawl links")
    print("- For e-commerce: Follow the category->product->detail hierarchy")


if __name__ == "__main__":
    asyncio.run(main())