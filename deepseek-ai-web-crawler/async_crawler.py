# async_crawler.py
import asyncio
import os
import json
import logging
from typing import List, Set

from dotenv import load_dotenv
from crawl4ai import AsyncWebCrawler, CrawlerRunConfig, CacheMode, LLMExtractionStrategy

from config import BASE_URL, CATEGORY_CSS_SELECTOR, PRODUCT_CSS_SELECTOR, REQUIRED_KEYS
from utils.data_utils import save_products_to_csv
from utils.scraper_utils import (
    fetch_categories,
    fetch_and_process_product_page,
    get_browser_config,
    get_llm_strategy_for_products,
)

# Cấu hình logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Tải biến môi trường từ .env
load_dotenv()

# Thêm chiến lược LLM để crawl chi tiết sản phẩm
def get_llm_strategy_for_product_details(category_name: str) -> LLMExtractionStrategy:
    return LLMExtractionStrategy(
        provider="groq/deepseek-r1-distill-llama-70b",
        api_token=os.getenv("GROQ_API_KEY"),
        schema={
            "name": "str",
            "category": "str",
            "price": "str",
            "original_price": "str",
            "discount": "str",
            "description": "str",
            "image_urls": "list[str]",
            "product_url": "str",
            "variants": "list[dict]",
            "detailed_info": "dict",
            "comments": "list[dict]"
        },
        extraction_type="schema",
        instruction=(
            "Extract detailed product information from the product detail page: "
            "- 'name': Text inside <h1> tag with class 'title' or similar in the product header. "
            f"- 'category': Set to '{category_name}'. "
            "- 'price': Text inside '.price span' or similar price element (e.g., '175.000₫'). "
            "- 'original_price': Text inside a strikethrough element (e.g., <div class='text-[#9da7bc] line-through'>) if present, otherwise empty. "
            "- 'discount': Text inside a discount badge (e.g., '-40%') if present, otherwise empty. "
            "- 'description': Text inside the first paragraph of '.detail-style' or similar description section. "
            "- 'image_urls': List of 'src' attributes from all <img> tags inside '.swiper-slide' elements within the main product image carousel. "
            "- 'product_url': The current page URL. "
            "- 'variants': List of dictionaries from '.swiper-list-cate-search .swiper-slide', each containing: "
            "  - 'name': Text inside the green badge (e.g., 'Thùng 48 Hộp'). "
            "  - 'price': Text of the main price (e.g., '175.000₫'). "
            "  - 'original_price': Text of the strikethrough price if present (e.g., '294.000₫'). "
            "  - 'discount': Text of the discount badge if present (e.g., '-40%'). "
            "  - 'unit_price': Text inside parentheses (e.g., '(6.125₫/Hộp)'). "
            "- 'detailed_info': Dictionary from the table in '.detail-style', where keys are the left column (e.g., 'Khối lượng') and values are the right column. "
            "- 'comments': List of dictionaries from comment section (e.g., '.comment-list' if present), each with 'user' (username) and 'content' (comment text). If no comments, return empty list."
            "Return a single object with these fields."
        ),
        input_format="markdown",
        verbose=True,
    )

async def fetch_product_details(
    crawler: AsyncWebCrawler,
    url: str,
    category: str,
    session_id: str,
    max_retries: int = 3,
    retry_delay: float = 5.0,
) -> dict:
    for attempt in range(max_retries):
        result = await crawler.arun(
            url=url,
            config=CrawlerRunConfig(
                cache_mode=CacheMode.BYPASS,
                extraction_strategy=get_llm_strategy_for_product_details(category),
                session_id=session_id,
                bypass_cache=True,
                timeout=60,
                wait_until="domcontentloaded",
                wait_for_selector=".detail-style",
            ),
        )
        if result.success and result.extracted_content:
            product = json.loads(result.extracted_content)
            product["product_url"] = url
            logging.info(f"Extracted details for {product['name']}")
            return product
        await asyncio.sleep(retry_delay)
    logging.error(f"Failed to fetch details for {url} after {max_retries} attempts")
    return {}

async def crawl_products():
    browser_config = get_browser_config()
    session_id = f"product_crawl_session_{os.getpid()}"
    all_products = []
    seen_urls = set()

    async with AsyncWebCrawler(config=browser_config) as crawler:
        # Bước 1: Lấy danh sách danh mục
        logging.info(f"Fetching categories from {BASE_URL}")
        categories = await fetch_categories(
            crawler, BASE_URL, CATEGORY_CSS_SELECTOR, session_id,
            max_retries=5, retry_delay=8.0,
        )
        if not categories:
            logging.error("No categories found. Exiting.")
            return

        logging.info(f"Found {len(categories)} categories")

        # Bước 2: Crawl từng danh mục để lấy URL sản phẩm
        for category in categories:
            category_name = category["category_name"]
            category_url = BASE_URL + category["category_url"].lstrip('/')

            # Lấy danh sách sản phẩm cơ bản (bao gồm product_url)
            products = await fetch_and_process_product_page(
                crawler, category_url, category_name, PRODUCT_CSS_SELECTOR,
                get_llm_strategy_for_products(category_name), session_id,
                REQUIRED_KEYS, seen_urls, max_retries=4, retry_delay=10.0, page_load_delay=5.0,
            )

            # Bước 3: Crawl chi tiết từng sản phẩm
            for product in products:
                if product["product_url"] in seen_urls:
                    logging.info(f"Skipping duplicate product: {product['name']}")
                    continue
                detailed_product = await fetch_product_details(
                    crawler, product["product_url"], category_name, session_id
                )
                if detailed_product and is_complete_product(detailed_product, REQUIRED_KEYS):
                    all_products.append(detailed_product)
                    seen_urls.add(detailed_product["product_url"])
                await asyncio.sleep(2)  # Nghỉ giữa các request để tránh bị chặn

        # Lưu tất cả sản phẩm
        if all_products:
            output_file = "bachhoaxanh_products_detailed.csv"
            save_products_to_csv(all_products, output_file)
            logging.info(f"Saved {len(all_products)} products to '{output_file}'.")
        else:
            logging.warning("No products were found during the crawl.")

async def main():
    try:
        await crawl_products()
    except Exception as e:
        logging.error(f"An error occurred: {e}")

if __name__ == "__main__":
    asyncio.run(main())