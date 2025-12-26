#!/usr/bin/env python3
"""
Comprehensive Sample Crawl4AI Program

This script demonstrates various features of Crawl4AI including:
- Basic crawling
- Advanced configurations
- CSS selectors and content filtering
- Error handling
- Different types of websites
"""

import asyncio
from crawl4ai import AsyncWebCrawler, CacheMode
from crawl4ai.extraction_strategy import JsonCssExtractionStrategy
from crawl4ai.content_filter_strategy import PruningContentFilter
from crawl4ai.models import CrawlResult


async def basic_crawling_example():
    """
    Basic crawling example - demonstrates the simplest usage of Crawl4AI
    """
    print("="*60)
    print("BASIC CRAWLING EXAMPLE")
    print("="*60)
    
    async with AsyncWebCrawler() as crawler:
        result = await crawler.arun(
            url="https://quotes.toscrape.com/",
        )
        
        if result.success:
            print(f"✓ Successfully crawled: {result.url}")
            print(f"Status Code: {result.status_code}")
            print(f"Content Length: {len(result.markdown)} characters")
            print("\nFirst 300 characters of content:")
            print(result.markdown[:300] + "...")
        else:
            print(f"✗ Failed to crawl: {result.url}")
            print(f"Error: {result.error_message}")


async def advanced_crawling_with_css_selectors():
    """
    Advanced crawling example using CSS selectors to extract specific content
    """
    print("\n" + "="*60)
    print("ADVANCED CRAWLING WITH CSS SELECTORS")
    print("="*60)
    
    # For this example, let's use a simple regex extraction to find email addresses and URLs
    from crawl4ai.extraction_strategy import RegexExtractionStrategy
    
    # Create extraction strategy to find URLs and other common patterns
    extraction_strategy = RegexExtractionStrategy(
        pattern=RegexExtractionStrategy.Url  # Extract URLs from the page
    )
    
    async with AsyncWebCrawler(verbose=True) as crawler:
        result = await crawler.arun(
            url="https://quotes.toscrape.com/",
            extraction_strategy=extraction_strategy
        )
        
        if result.success:
            if result.extracted_content:
                print(f"✓ Successfully extracted content from: {result.url}")
                import json
                try:
                    extracted_data = json.loads(result.extracted_content)
                    
                    print(f"Found {len(extracted_data['quotes'])} quotes")
                    for i, quote in enumerate(extracted_data['quotes'][:3]):  # Show first 3 quotes
                        print(f"\nQuote {i+1}:")
                        print(f"  Text: {quote['text'][:100]}...")
                        print(f"  Author: {quote['author']}")
                        # Handle tags which might be a single value or list
                        tags = quote.get('tags', [])
                        if isinstance(tags, list):
                            print(f"  Tags: {', '.join(tags)}")
                        else:
                            print(f"  Tags: {tags}")
                except json.JSONDecodeError:
                    print(f"  Extracted content (not JSON): {result.extracted_content[:500]}...")
            else:
                print(f"⚠ No extracted content returned from: {result.url}")
                print(f"  Raw markdown length: {len(result.markdown)}")
        else:
            print(f"✗ Failed to extract content from: {result.url}")


async def crawling_with_content_filtering():
    """
    Crawling example with content filtering to get only relevant content
    """
    print("\n" + "="*60)
    print("CRAWLING WITH CONTENT FILTERING")
    print("="*60)
    
    # Create a content filter for relevant content
    content_filter = PruningContentFilter(
        user_query="quotes to scrape"
    )
    
    async with AsyncWebCrawler() as crawler:
        result = await crawler.arun(
            url="https://quotes.toscrape.com/",
            content_filter=content_filter
        )
        
        if result.success:
            print(f"✓ Successfully crawled with filtering: {result.url}")
            print(f"Original content length: {len(result.html)} characters")
            print(f"Filtered content length: {len(result.markdown)} characters")
            print("\nFiltered content preview:")
            print(result.markdown[:400] + "...")
        else:
            print(f"✗ Failed to crawl: {result.url}")
            print(f"Error: {result.error_message}")


async def crawling_multiple_urls():
    """
    Example of crawling multiple URLs concurrently
    """
    print("\n" + "="*60)
    print("CRAWLING MULTIPLE URLS CONCURRENTLY")
    print("="*60)
    
    urls = [
        "https://httpbin.org/delay/1",  # Simple test endpoint
        "https://quotes.toscrape.com/page/1/",
        "https://quotes.toscrape.com/page/2/"
    ]
    
    async with AsyncWebCrawler() as crawler:
        # Crawl multiple URLs concurrently
        tasks = [crawler.arun(url=url) for url in urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                print(f"✗ Exception crawling {urls[i]}: {result}")
            elif result.success:
                print(f"✓ Successfully crawled {urls[i]} - Status: {result.status_code}")
            else:
                print(f"✗ Failed to crawl {urls[i]} - Error: {result.error_message}")


async def crawling_with_browser_config():
    """
    Crawling with custom browser configurations
    """
    print("\n" + "="*60)
    print("CRAWLING WITH CUSTOM BROWSER CONFIG")
    print("="*60)
    
    from crawl4ai.async_configs import BrowserConfig
    
    # Configure browser settings
    browser_config = BrowserConfig(
        headless=True,
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        extra_args=["--disable-blink-features=AutomationControlled"],  # Example of a valid browser argument
    )
    
    async with AsyncWebCrawler() as crawler:
        result = await crawler.arun(
            url="https://httpbin.org/headers",
            browser_config=browser_config
        )
        
        if result.success:
            print(f"✓ Crawled with custom config: {result.url}")
            print(f"User-Agent in response: {result.status_code}")
            print("Response preview:", result.markdown[:200] + "...")
        else:
            print(f"✗ Failed to crawl: {result.url}")


async def error_handling_example():
    """
    Example demonstrating proper error handling with Crawl4AI
    """
    print("\n" + "="*60)
    print("ERROR HANDLING EXAMPLE")
    print("="*60)
    
    test_urls = [
        "https://httpbin.org/status/404",  # 404 error
        "https://httpbin.org/status/500",  # 500 error
        "https://quotes.toscrape.com/",    # Valid URL
        "https://invalid-domain-12345.com/" # Invalid domain
    ]
    
    async with AsyncWebCrawler() as crawler:
        for url in test_urls:
            try:
                result = await crawler.arun(url=url, timeout=10)
                if result.success:
                    print(f"✓ Success: {url} - Status: {result.status_code}")
                else:
                    print(f"✗ Crawl failed: {url} - Error: {result.error_message}")
            except Exception as e:
                print(f"✗ Exception: {url} - {str(e)}")


async def main():
    """
    Main function to run all examples
    """
    print("🧪 CRAWL4AI COMPREHENSIVE SAMPLE PROGRAM")
    print("This program demonstrates various features of Crawl4AI")
    
    # Run examples sequentially
    await basic_crawling_example()
    await advanced_crawling_with_css_selectors()
    await crawling_with_content_filtering()
    await crawling_multiple_urls()
    await crawling_with_browser_config()
    await error_handling_example()
    
    print("\n" + "="*60)
    print("ALL EXAMPLES COMPLETED!")
    print("="*60)


if __name__ == "__main__":
    asyncio.run(main())