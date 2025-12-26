#!/usr/bin/env python3
"""
Advanced Deep Crawling Example with Crawl4AI

This script demonstrates more advanced multi-level crawling techniques using
Crawl4AI's built-in deep crawling capabilities.
"""

import asyncio
from crawl4ai import AsyncWebCrawler
from crawl4ai.deep_crawling import (
    BFSDeepCrawlStrategy, 
    DeepCrawlDecorator,
    FilterChain,
    URLPatternFilter,
    DomainFilter
)
from crawl4ai.extraction_strategy import JsonCssExtractionStrategy
import json


async def basic_deep_crawl():
    """
    Example: Using built-in deep crawling to follow links automatically
    """
    print("="*70)
    print("ADVANCED DEEP CRAWLING WITH AUTOMATED LINK DISCOVERY")
    print("="*70)
    
    from crawl4ai.deep_crawling import DeepCrawlStrategy
    
    # Define filters to control crawling behavior
    filters = FilterChain([
        # Only crawl pages from the same domain
        DomainFilter(allowed_domains=["quotes.toscrape.com"]),
        # Avoid certain URL patterns
        URLPatternFilter(patterns=[".*login.*", ".*contact.*"], reverse=True),  # Exclude these
    ])
    
    # Create a crawl strategy
    strategy = BFSDeepCrawlStrategy(
        max_depth=2,  # Go 2 levels deep from the start URL
        max_pages=10,  # At most 10 pages total
        filter_chain=filters  # Use filter_chain instead of filters
    )
    
    # Example of a decorator approach (similar to how you might use it)
    print("Crawl4AI provides built-in deep crawling strategies like:")
    print("- BFSDeepCrawlStrategy: Breadth-first search")
    print("- DFSDeepCrawlStrategy: Depth-first search") 
    print("- BestFirstCrawlingStrategy: Priority-based crawling")
    print()
    print("These strategies automatically:")
    print("1. Discover links on each page")
    print("2. Follow links respecting depth/page limits")
    print("3. Apply filters to avoid unwanted pages")
    print("4. Collect content from all discovered pages")
    print()
    print("For our example with quotes.toscrape.com:")
    print("- Level 1: Main page")
    print("- Level 2: Individual quote pages, author pages, tag pages")
    print("- Level 3: Further navigation from level 2 pages (if max_depth=3)")


async def manual_crawl_chain():
    """
    Example: Manually chaining crawls to simulate deep crawling behavior
    """
    print("\n" + "="*70)
    print("MANUAL CRAWL CHAINING APPROACH")
    print("="*70)
    
    print("Sometimes it's better to manually control the crawling flow:")
    print()
    
    async with AsyncWebCrawler() as crawler:
        # Step 1: Get main page and extract all relevant links
        print("Step 1: Crawling main page to extract all links...")
        main_result = await crawler.arun(url="https://quotes.toscrape.com/")
        
        if main_result.success:
            # Extract different types of links
            import re
            
            # Extract author links
            author_links = re.findall(r'<a href="(/author/[^"]+)"', main_result.html)
            author_links = list(set(author_links))[:3]  # Get unique, limit to 3
            
            # Extract tag links
            tag_links = re.findall(r'<a class="tag" href="(/tag/[^"]+)"', main_result.html)
            tag_links = list(set(tag_links))[:3]  # Get unique, limit to 3
            
            print(f"  Found {len(author_links)} author links")
            print(f"  Found {len(tag_links)} tag links")
            
            # Step 2: Crawl each type of page
            print("\nStep 2: Crawling author pages...")
            author_data = []
            for i, link in enumerate(author_links, 1):
                full_url = f"https://quotes.toscrape.com{link}"
                print(f"  Crawling author {i}: {full_url}")
                
                author_result = await crawler.arun(url=full_url)
                if author_result.success:
                    # Extract author info
                    name_match = re.search(r'<h3 class="author-title">([^<]+)', author_result.html)
                    author_name = name_match.group(1).strip() if name_match else "Unknown"
                    author_data.append({"name": author_name, "url": full_url})
            
            print(f"\nStep 3: Crawling tag pages...")
            tag_data = []
            for i, link in enumerate(tag_links, 1):
                full_url = f"https://quotes.toscrape.com{link}"
                print(f"  Crawling tag {i}: {full_url}")
                
                tag_result = await crawler.arun(url=full_url)
                if tag_result.success:
                    # Count quotes on tag page
                    quote_count = len(re.findall(r'<span class="text"', tag_result.html))
                    tag_data.append({"tag": link.split('/')[-2], "quote_count": quote_count, "url": full_url})
    
    print(f"\nCollected data:")
    print(f"  Authors: {len(author_data)}")
    for author in author_data:
        print(f"    - {author['name']}")
    
    print(f"  Tags: {len(tag_data)}")
    for tag in tag_data:
        print(f"    - {tag['tag']} ({tag['quote_count']} quotes)")


async def crawl_with_content_extraction():
    """
    Example: Multi-level crawling with content extraction at each level
    """
    print("\n" + "="*70)
    print("MULTI-LEVEL CRAWLING WITH CONTENT EXTRACTION")
    print("="*70)
    
    print("Example: Extract specific content from different levels")
    
    all_data = {
        "categories": [],
        "items": [],
        "details": []
    }
    
    async with AsyncWebCrawler() as crawler:
        # Level 1: Extract categories/tags
        print("\nLevel 1: Extracting categories...")
        main_result = await crawler.arun(url="https://quotes.toscrape.com/")
        
        if main_result.success:
            import re
            # Extract tags (simulating categories)
            tag_urls = re.findall(r'<a class="tag" href="(/tag/[^"]+)"', main_result.html)
            tag_urls = list(set(tag_urls))[:3]  # Get unique, limit to 3
            
            print(f"  Found {len(tag_urls)} categories")
            
            # Level 2: For each category, extract items
            print("\nLevel 2: Extracting items from each category...")
            for i, tag_url in enumerate(tag_urls, 1):
                full_url = f"https://quotes.toscrape.com{tag_url}"
                print(f"  Processing category {i}: {tag_url.split('/')[-2]}")
                
                category_result = await crawler.arun(url=full_url)
                if category_result.success:
                    # Extract quotes from this category page
                    quote_texts = re.findall(r'<span class="text" itemprop="text">([^<]+)', category_result.html)
                    
                    category_info = {
                        "name": tag_url.split('/')[-2],
                        "url": full_url,
                        "quote_count": len(quote_texts),
                        "sample_quotes": quote_texts[:2]  # First 2 quotes as sample
                    }
                    all_data["categories"].append(category_info)
                    
                    print(f"    Found {len(quote_texts)} quotes")
            
            # Level 3: Extract author details for a sample of quotes
            print("\nLevel 3: Extracting detailed information...")
            if all_data["categories"]:
                # Pick a quote from the first category to get author info
                first_category = all_data["categories"][0]
                author_match = re.search(r'<a href="(/author/[^"]+)"[^>]*>([^<]+)</a>', main_result.html)
                
                if author_match:
                    author_path, author_name = author_match.groups()
                    author_url = f"https://quotes.toscrape.com{author_path}"
                    
                    print(f"  Getting detailed info for author: {author_name}")
                    author_result = await crawler.arun(url=author_url)
                    
                    if author_result.success:
                        # Extract author details
                        birth_match = re.search(r'<span class="author-born-date">([^<]+)', author_result.html)
                        birth_date = birth_match.group(1) if birth_match else "Unknown"
                        
                        desc_match = re.search(r'<div class="author-description">([^<]+)', author_result.html)
                        description = desc_match.group(1)[:100] if desc_match else "No description available"
                        
                        author_detail = {
                            "name": author_name,
                            "birth_date": birth_date,
                            "description": description,
                            "url": author_url
                        }
                        all_data["details"].append(author_detail)
                        print(f"    Birth date: {birth_date}")
    
    print(f"\nFinal collected data:")
    print(f"  Categories: {len(all_data['categories'])}")
    print(f"  Detail records: {len(all_data['details'])}")
    
    for cat in all_data["categories"]:
        print(f"    - {cat['name']}: {cat['quote_count']} quotes")


async def practical_ecommerce_crawl():
    """
    Example: Practical e-commerce crawl pattern (simulated)
    """
    print("\n" + "="*70)
    print("PRACTICAL E-COMMERCE CRAWLING PATTERN (SIMULATED)")
    print("="*70)
    
    print("Real-world e-commerce crawl pattern:")
    print("Level 1: Category listing pages")
    print("Level 2: Product listing within categories") 
    print("Level 3: Individual product details")
    print()
    
    print("Implementation approach:")
    print("1. Start with main category page")
    print("2. Extract all category URLs")
    print("3. For each category, extract product URLs")
    print("4. For each product, extract detailed information")
    print()
    
    # Simulate this with our quotes site
    print("Simulated using quotes.toscrape.com:")
    print("- Categories = Tags")
    print("- Products = Individual quotes")
    print("- Details = Author information")
    print()
    
    async with AsyncWebCrawler() as crawler:
        # Category level (tags)
        main_result = await crawler.arun(url="https://quotes.toscrape.com/")
        
        if main_result.success:
            import re
            # Extract unique tags (categories) 
            tag_urls = list(set(re.findall(r'<a class="tag" href="(/tag/[^"]+)"', main_result.html)))[:2]
            
            for i, tag_url in enumerate(tag_urls, 1):
                tag_name = tag_url.split('/')[-2]
                full_url = f"https://quotes.toscrape.com{tag_url}"
                
                print(f"\nCategory {i}: {tag_name}")
                print(f"  URL: {full_url}")
                
                # Product listing level (quotes in this tag)
                tag_result = await crawler.arun(url=full_url)
                if tag_result.success:
                    quotes = re.findall(r'<span class="text" itemprop="text">([^<]+)', tag_result.html)
                    quote_links = re.findall(r'<a href="(\/author\/[^"]+)"', tag_result.html)[:2]  # Get first 2 author links
                    
                    print(f"  Found {len(quotes)} quotes in this category")
                    
                    # Product detail level (author details)
                    for j, author_path in enumerate(quote_links, 1):
                        author_url = f"https://quotes.toscrape.com{author_path}"
                        print(f"    Product {j} detail: {author_url}")
                        
                        author_result = await crawler.arun(url=author_url)
                        if author_result.success:
                            name_match = re.search(r'<h3 class="author-title">([^<]+)', author_result.html)
                            name = name_match.group(1) if name_match else "Unknown"
                            print(f"      Author: {name}")


async def main():
    """
    Main function to run all deep/multi-level crawling examples
    """
    print("🔍 ADVANCED MULTI-LEVEL CRAWLING WITH CRAWL4AI")
    print("Examples of how to handle websites with multiple levels/pages")
    
    await basic_deep_crawl()
    await manual_crawl_chain()
    await crawl_with_content_extraction()
    await practical_ecommerce_crawl()
    
    print("\n" + "="*70)
    print("ADVANCED MULTI-LEVEL CRAWLING EXAMPLES COMPLETED!")
    print("="*70)
    print("\nBest practices for multi-level crawling:")
    print("1. Plan your crawling strategy based on site structure")
    print("2. Use filters to avoid irrelevant pages/loops")
    print("3. Handle rate limiting and politeness")
    print("4. Implement proper error handling")
    print("5. Structure data extraction by level")
    print("6. Be mindful of legal/ethical considerations")


if __name__ == "__main__":
    asyncio.run(main())