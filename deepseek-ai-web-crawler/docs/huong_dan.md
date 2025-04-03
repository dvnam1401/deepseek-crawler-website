# Web Scraping Guide for BachHoaXanh.com

To adapt your existing web scraping code to crawl product data from https://www.bachhoaxanh.com/, we need to make several adjustments. The new structure will involve:

- **Crawling Categories**: First, scrape the category pages to get a list of product URLs.
- **Crawling Product Details**: Then, scrape individual product pages for detailed information.
- **Updated Data Model**: Redefine the Venue model to a Product model suited for e-commerce data.
- **Adjusting Utilities**: Modify the scraper utilities to handle the new website structure and data requirements.

Below is a step-by-step refactoring of your code to scrape products from https://www.bachhoaxanh.com/.

## 1. Updated venue.py → product.py

Rename venue.py to product.py and update the data model for products.

```python
# product.py
from pydantic import BaseModel

class Product(BaseModel):
    """
    Represents the data structure of a Product.
    """
    name: str
    category: str
    price: str
    original_price: str | None = None  # Optional field for discounted price
    discount: str | None = None        # Optional discount info
    rating: float | None = None        # Optional if available
    reviews: int | None = None         # Optional if available
    description: str
    image_url: str | None = None       # Product image URL
    product_url: str                   # URL of the product page
```

## 2. Updated data_utils.py

Modify data_utils.py to work with the Product model.

```python
# data_utils.py
import csv

from models.product import Product

def is_duplicate_product(product_url: str, seen_urls: set) -> bool:
    return product_url in seen_urls

def is_complete_product(product: dict, required_keys: list) -> bool:
    return all(key in product for key in required_keys)

def save_products_to_csv(products: list, filename: str):
    if not products:
        print("No products to save.")
        return

    # Use field names from the Product model
    fieldnames = Product.model_fields.keys()

    with open(filename, mode="w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(products)
    print(f"Saved {len(products)} products to '{filename}'.")
```

## 3. Updated scraper_utils.py

Adjust scraper_utils.py to handle category crawling and product detail extraction.

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
    """
    LLM strategy to extract category links.
    """
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
    """
    LLM strategy to extract product details.
    """
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
) -> List[dict]:
    """
    Fetch category links from the main page.
    """
    result = await crawler.arun(
        url=base_url,
        config=CrawlerRunConfig(
            cache_mode=CacheMode.BYPASS,
            extraction_strategy=get_llm_strategy_for_categories(),
            css_selector=css_selector,
            session_id=session_id,
        ),
    )
    if result.success and result.extracted_content:
        return json.loads(result.extracted_content)
    print(f"Error fetching categories: {result.error_message}")
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
    """
    Fetch and process a product page or listing page.
    """
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
```

## 4. Updated config.py

Update the configuration for the new website.

```python
# config.py
BASE_URL = "https://www.bachhoaxanh.com/"
CATEGORY_CSS_SELECTOR = ".category-list"  # Adjust based on actual site structure
PRODUCT_CSS_SELECTOR = ".product-item"    # Adjust based on actual site structure
REQUIRED_KEYS = [
    "name",
    "category",
    "price",
    "description",
    "product_url",
]
```

## 5. Updated main.py

Rewrite main.py to crawl categories and then products.

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
    """
    Main function to crawl product data from the website.
    """
    browser_config = get_browser_config()
    llm_strategy = get_llm_strategy_for_products()
    session_id = "product_crawl_session"

    all_products = []
    seen_urls = set()

    async with AsyncWebCrawler(config=browser_config) as crawler:
        # Step 1: Fetch categories
        categories = await fetch_categories(crawler, BASE_URL, CATEGORY_CSS_SELECTOR, session_id)
        if not categories:
            print("No categories found. Exiting.")
            return

        # Step 2: Crawl each category page for products
        for category in categories:
            category_name = category["category_name"]
            category_url = category["category_url"]
            print(f"Processing category: {category_name}")

            # Fetch products from the category page
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

            # Polite delay
            await asyncio.sleep(2)

    # Save all products to CSV
    if all_products:
        save_products_to_csv(all_products, "bachhoaxanh_products.csv")
        print(f"Saved {len(all_products)} products to 'bachhoaxanh_products.csv'.")
    else:
        print("No products were found during the crawl.")

    # Show LLM usage
    llm_strategy.show_usage()

async def main():
    await crawl_products()

if __name__ == "__main__":
    asyncio.run(main())
```

## Notes on Adjustments

- **CSS Selectors**: The CATEGORY_CSS_SELECTOR and PRODUCT_CSS_SELECTOR in config.py are placeholders. Inspect the HTML structure of https://www.bachhoaxanh.com/ using browser developer tools to find the correct selectors for category lists and product items.
- **Pagination**: If category pages have pagination (e.g., ?page=2), you'll need to add logic similar to your original code to loop through pages. Modify fetch_and_process_product_page to handle this.
- **Dynamic Content**: If the site uses JavaScript to load products, ensure headless=False and test with headless=True later for efficiency. You may need to adjust BrowserConfig for waiting times.
- **Rate Limiting**: The asyncio.sleep(2) is a basic politeness measure. Adjust based on the site's terms of service or observed rate limits.

## How to Run

1. Install dependencies: Ensure you have crawl4ai, pydantic, and other required libraries installed (pip install crawl4ai pydantic python-dotenv).
2. Set up your .env file with GROQ_API_KEY=<your_key>.
3. Run the script: python main.py.

This refactored code will scrape categories and product details from https://www.bachhoaxanh.com/, saving the results to a CSV file. Let me know if you need help fine-tuning it further!