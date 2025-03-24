# Cải thiện Crawler cho Bách Hóa Xanh

## 1. Cập nhật scraper_utils.py

Loại bỏ các tham số không được hỗ trợ trong BrowserConfig và thêm logic chờ thủ công nếu cần.

```python
# scraper_utils.py
import json
import os
from typing import List, Set, Tuple

from crawl4ai import (
    AsyncWebCrawler,
    BrowserConfig,
    CacheMode,
    CrawlerRunConfig,
    LLMExtractionStrategy,
)

from models.product import Product
from utils.data_utils import is_complete_product, is_duplicate_product

def get_browser_config() -> BrowserConfig:
    return BrowserConfig(
        browser_type="chromium",
        headless=False,
        verbose=True,
    )

def get_llm_strategy_for_categories() -> LLMExtractionStrategy:
    return LLMExtractionStrategy(
        provider="groq/deepseek-r1-distill-llama-70b",
        api_token=os.getenv("GROQ_API_KEY"),
        schema={"category_name": "str", "category_url": "str"},
        extraction_type="schema",
        instruction=(
            "Extract all category names and their URLs from the page content. "
            "Return a list of objects with 'category_name' and 'category_url'."
        ),
        input_format="markdown",
        verbose=True,
    )

def get_llm_strategy_for_products() -> LLMExtractionStrategy:
    return LLMExtractionStrategy(
        provider="groq/deepseek-r1-distill-llama-70b",
        api_token=os.getenv("GROQ_API_KEY"),
        schema=Product.model_json_schema(),
        extraction_type="schema",
        instruction=(
            "Extract all product objects with 'name', 'category', 'price', 'original_price', "
            "'discount', 'rating', 'reviews', 'description', 'image_url', and 'product_url' "
            "from the following content. If a field is not available, set it to null."
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
    for attempt in range(max_retries):
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

        if attempt < max_retries - 1:
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
) -> List[dict]:
    print(f"Scraping product page: {url}")
    result = await crawler.arun(
        url=url,
        config=CrawlerRunConfig(
            cache_mode=CacheMode.BYPASS,
            extraction_strategy=llm_strategy,
            css_selector=css_selector,
            session_id=session_id,
        ),
    )

    if not (result.success and result.extracted_content):
        print(f"Error fetching page {url}: {result.error_message}")
        return []

    extracted_data = json.loads(result.extracted_content)
    if not extracted_data:
        print(f"No products found on {url}.")
        return []

    complete_products = []
    for product in extracted_data:
        product["category"] = category
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
```

## 2. Cập nhật main.py

Giữ nguyên logic retry và đảm bảo crawler có thời gian chờ hợp lý thông qua asyncio.sleep.

```python
# main.py
import asyncio

from crawl4ai import AsyncWebCrawler
from dotenv import load_dotenv

from config import BASE_URL, CATEGORY_CSS_SELECTOR, PRODUCT_CSS_SELECTOR, REQUIRED_KEYS
from utils.data_utils import save_products_to_csv
from utils.scraper_utils import (
    fetch_categories,
    fetch_and_process_product_page,
    get_browser_config,
    get_llm_strategy_for_products,
)

load_dotenv()

async def crawl_products():
    browser_config = get_browser_config()
    llm_strategy = get_llm_strategy_for_products()
    session_id = "product_crawl_session"

    all_products = []
    seen_urls = set()

    async with AsyncWebCrawler(config=browser_config) as crawler:
        categories = await fetch_categories(
            crawler, BASE_URL, CATEGORY_CSS_SELECTOR, session_id, max_retries=3, retry_delay=5.0
        )
        if not categories:
            print("No categories found. Exiting.")
            return

        for category in categories:
            category_name = category["category_name"]
            category_url = category["category_url"]
            print(f"Processing category: {category_name}")

            products = await fetch_and_process_product_page(
                crawler,
                category_url,
                category_name,
                PRODUCT_CSS_SELECTOR,
                llm_strategy,
                session_id,
                REQUIRED_KEYS,
                seen_urls,
            )
            all_products.extend(products)
            await asyncio.sleep(2)  # Đợi giữa các yêu cầu

    if all_products:
        save_products_to_csv(all_products, "bachhoaxanh_products.csv")
        print(f"Saved {len(all_products)} products to 'bachhoaxanh_products.csv'.")
    else:
        print("No products were found during the crawl.")

    llm_strategy.show_usage()

async def main():
    await crawl_products()

if __name__ == "__main__":
    asyncio.run(main())
```

## 3. Kiểm tra CSS Selector

Lỗi "No categories found" có thể do CATEGORY_CSS_SELECTOR trong config.py không đúng. Hãy kiểm tra HTML của https://www.bachhoaxanh.com/:

1. Mở trang web trong trình duyệt.
2. Nhấn F12 hoặc Ctrl+Shift+I để mở Developer Tools.
3. Tìm phần tử chứa danh sách danh mục (thường là `<ul>` hoặc `<div>` với class như `.category-list`, `.menu`, hoặc `.nav`).

Cập nhật CATEGORY_CSS_SELECTOR trong config.py cho phù hợp, ví dụ:

```python
CATEGORY_CSS_SELECTOR = ".menu-category"  # Thay bằng class thực tế
```

## 4. Thêm thời gian chờ thủ công (nếu cần)

Nếu trang vẫn không tải kịp, bạn có thể thêm await asyncio.sleep() trước khi gửi yêu cầu trong fetch_categories:

```python
async def fetch_categories(
    crawler: AsyncWebCrawler,
    base_url: str,
    css_selector: str,
    session_id: str,
    max_retries: int = 3,
    retry_delay: float = 5.0,
) -> List[dict]:
    for attempt in range(max_retries):
        await asyncio.sleep(2)  # Chờ 2 giây trước mỗi lần thử
        result = await crawler.arun(
            url=base_url,
            config=CrawlerRunConfig(
                cache_mode=CacheMode.BYPASS,
                extraction_strategy=get_llm_strategy_for_categories(),
                css_selector=css_selector,
                session_id=session_id,
                bypass_cache=True,
            ),
        )
        # Tiếp tục logic như trên...

