# file scraper_utils.py
import json
import os
import asyncio
from typing import List, Set, Tuple

from crawl4ai import (
    AsyncWebCrawler,
    BrowserConfig,
    CacheMode,
    CrawlerRunConfig,
    LLMExtractionStrategy,
)

from models.product import Product
import logging

logging.basicConfig(level=logging.INFO)

def get_browser_config() -> BrowserConfig:
    """
    Returns the browser configuration for the crawler.

    Returns:
        BrowserConfig: The configuration settings for the browser.
    """
    return BrowserConfig(
        browser_type="chromium",
        headless=False,
        verbose=True,
    )

from crawl4ai.extraction_strategy import LLMExtractionStrategy
import logging
from slugify import slugify  

logging.basicConfig(level=logging.INFO)
def get_llm_strategy_for_categories() -> LLMExtractionStrategy:
    return LLMExtractionStrategy(
        provider="groq/deepseek-r1-distill-llama-70b",
        api_token=os.getenv("GROQ_API_KEY"),
        schema={"category_name": "str", "category_url": "str"},
        extraction_type="schema",
        instruction=(
            "Extract all category names from elements with class 'cate' "
            "inside a parent element with classes 'mb-2 flex flex-wrap'. "
            "For each 'cate' element: "
            "- 'category_name': Get the text inside the element (e.g., 'Thịt heo', 'Trái cây'). "
            "- 'category_url': Generate a URL slug from the category name by converting it to lowercase, "
            "removing special characters, and replacing spaces with hyphens (e.g., 'Thịt heo' -> '/thit-heo'). "
            "Only include categories where the category_name is not empty and a valid URL slug can be generated."
        ),
        input_format="markdown",
        verbose=True,
    )

def get_llm_strategy_for_products(category_name: str) -> LLMExtractionStrategy:
    return LLMExtractionStrategy(
        provider="groq/deepseek-r1-distill-llama-70b",
        api_token=os.getenv("GROQ_API_KEY"),
        schema={
            "name": "str",
            "category": "str",
            "price": "str",
            "description": "str",
            "product_url": "str"
        },
        extraction_type="schema",
        instruction=(
            "Extract product information from elements with class 'box_product'. "
            "For each 'box_product' element: "
            "- 'name': Text inside the <h3 class='product_name'> tag. "
            f"- 'category': Set to '{category_name}'. "
            "- 'price': Text inside the <div class='product_price'> tag (include unit like '/300g' if present). "
            "- 'description': Text inside <div class='mb-4px block leading-3'> containing price per kg (e.g., '(171.900đ/kg)') or set to empty string if not present. "
            "- 'product_url': The 'href' attribute of the first <a> tag inside the element. "
            "Return a list of objects with these fields."
        ),
        input_format="markdown",
        verbose=True,
    )
    
async def fetch_categories(
    crawler: AsyncWebCrawler,
    base_url: str,
    css_selector: str,
    session_id: str,
    max_retries: int = 3,
    retry_delay: float = 5.0,
) -> List[dict]:
    """
    Fetch category links from the main page with retry logic.
    """
    for attempt in range(max_retries):
        await asyncio.sleep(2)  # Chờ 2 giây trước mỗi lần thử
        result = await crawler.arun(
            url=base_url,
            config=CrawlerRunConfig(
                cache_mode=CacheMode.BYPASS,
                extraction_strategy=get_llm_strategy_for_categories(),
                css_selector=css_selector,
                session_id=session_id,
                bypass_cache=True,  # Đảm bảo tải mới mỗi lần
            ),
        )
        if result.success and result.extracted_content:
            categories = json.loads(result.extracted_content)
            if categories:
                print(f"Attempt {attempt + 1}/{max_retries}: Successfully extracted {len(categories)} categories.")
                return categories
            print(f"Attempt {attempt + 1}/{max_retries}: No categories extracted.")
        else:
            print(f"Attempt {attempt + 1}/{max_retries} failed: {result.error_message}")
        if attempt < max_retries - 1:  # Không chờ sau lần cuối
            print(f"Retrying in {retry_delay} seconds...")
            await asyncio.sleep(retry_delay)

    print(f"Failed to fetch categories after {max_retries} attempts.")
    return []


async def fetch_and_process_product_page(
    crawler: AsyncWebCrawler,
    url: str,
    category: str,
    css_selector: str,
    llm_strategy: LLMExtractionStrategy,
    session_id: str,
    required_keys: List[str],
    seen_urls: Set[str],
    max_retries: int = 3,
    retry_delay: float = 5.0,
    page_load_delay: float = 3.0,
) -> List[dict]:
    """
    Fetch and process a product page or listing page with retry logic and page load delay.
    """
    print(f"Scraping product page: {url}")
    
    result = None
    for attempt in range(max_retries):
        # Chờ đợi trước khi tải trang để đảm bảo kết nối ổn định
        await asyncio.sleep(page_load_delay)
        
        print(f"Attempt {attempt + 1}/{max_retries} for {url}")
        result = await crawler.arun(
            url=url,
            config=CrawlerRunConfig(
                cache_mode=CacheMode.BYPASS,
                extraction_strategy=llm_strategy,
                css_selector=css_selector,
                session_id=session_id,
                timeout=60,  # Tăng timeout lên 60 giây
            ),
        )
        
        # Kiểm tra kết quả và thoát vòng lặp nếu thành công
        if result.success and result.extracted_content:
            extracted_data = json.loads(result.extracted_content)
            if extracted_data and len(extracted_data) > 0:
                print(f"Successfully extracted {len(extracted_data)} products on attempt {attempt + 1}")
                break
        
        # Nếu không thành công và còn lần thử, đợi trước khi thử lại
        if attempt < max_retries - 1:
            print(f"No data extracted or error occurred. Retrying in {retry_delay} seconds...")
            await asyncio.sleep(retry_delay)
    
    # Kiểm tra kết quả cuối cùng sau tất cả các lần thử
    if not result or not (result.success and result.extracted_content):
        print(f"Error fetching page {url} after {max_retries} attempts: {result.error_message if result else 'No result'}")
        return []

    extracted_data = json.loads(result.extracted_content)
    if not extracted_data:
        print(f"No products found on {url} after {max_retries} attempts.")
        return []

    complete_products = []
    for product in extracted_data:
        product["category"] = category  # Add category to each product
        product["product_url"] = url if "product_url" not in product else product["product_url"]

        if not is_complete_product(product, required_keys):
            continue

        if is_duplicate_product(product["product_url"], seen_urls):
            print(f"Duplicate product '{product['name']}' found. Skipping.")
            continue

        seen_urls.add(product["product_url"])
        complete_products.append(product)

    print(f"Extracted {len(complete_products)} products from {url}.")
    return complete_products
