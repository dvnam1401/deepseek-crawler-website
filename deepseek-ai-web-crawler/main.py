# main.py
import logging
import time
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
import undetected_chromedriver as uc
from bs4 import BeautifulSoup
from slugify import slugify
import os
import csv
import json

# Cấu hình logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Định nghĩa hằng số
BASE_URL = "https://www.bachhoaxanh.com/"
CATEGORY_CSS_SELECTOR = ".mb-2.flex.flex-wrap .cate"
PRODUCT_CSS_SELECTOR = ".box_product"
OUTPUT_FILE = "bachhoaxanh_products_detailed.csv"

def scroll_page_slowly(driver, max_scroll_time=20):
    last_height = driver.execute_script("return document.body.scrollHeight")
    step = 500
    current_position = 0
    start_time = time.time()

    while current_position < last_height and (time.time() - start_time) < max_scroll_time:
        driver.execute_script(f"window.scrollTo(0, {current_position});")
        time.sleep(1)
        current_position += step
        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height > last_height:
            last_height = new_height
    logging.info("Finished scrolling page.")

def wait_for_page_load(driver, timeout=30, selector=PRODUCT_CSS_SELECTOR):
    try:
        WebDriverWait(driver, timeout).until(
            lambda driver: driver.execute_script("return document.readyState") == "complete"
        )
        WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, selector))
        )
        logging.info(f"Page loaded successfully with elements matching '{selector}'.")
    except TimeoutException:
        logging.warning(f"Timeout waiting for page load or elements '{selector}' after {timeout} seconds.")

def extract_categories(driver):
    driver.get(BASE_URL)
    wait_for_page_load(driver)
    scroll_page_slowly(driver)
    
    html = driver.page_source
    soup = BeautifulSoup(html, 'html.parser')
    categories = [
        {"category_name": cate.get_text(strip=True), "category_url": f"/{slugify(cate.get_text(strip=True))}"}
        for cate in soup.select(CATEGORY_CSS_SELECTOR) if cate.get_text(strip=True)
    ]
    logging.info(f"Extracted {len(categories)} categories.")
    return categories

def extract_products(driver, category, retries=3):
    full_url = f"{BASE_URL}{category['category_url'].lstrip('/')}"
    products = []
    
    for attempt in range(retries):
        logging.info(f"Scraping category page (Attempt {attempt + 1}/{retries}): {full_url}")
        driver.get(full_url)
        wait_for_page_load(driver)
        scroll_page_slowly(driver)
        
        product_html = driver.page_source
        product_soup = BeautifulSoup(product_html, 'html.parser')
        product_elements = product_soup.select(PRODUCT_CSS_SELECTOR)
        
        if product_elements:
            products = [
                {
                    "name": product.select_one(".product_name").get_text(strip=True) if product.select_one(".product_name") else "",
                    "category": category["category_name"],
                    "price": product.select_one(".product_price").get_text(strip=True) if product.select_one(".product_price") else "",
                    "description": product.select_one(".mb-4px.block.leading-3").get_text(strip=True) if product.select_one(".mb-4px.block.leading-3") else "",
                    "product_url": BASE_URL + product.select_one("a")["href"].lstrip('/') if product.select_one("a") else full_url
                }
                for product in product_elements
            ]
            if products:
                logging.info(f"Extracted {len(products)} products from {category['category_name']}.")
                break
        else:
            logging.warning(f"No products found on attempt {attempt + 1}. HTML sample: {product_html[:1000]}")
            time.sleep(2)
        
        if attempt == retries - 1:
            logging.error(f"Failed to extract products from {category['category_name']} after {retries} attempts.")
    
    return products

def save_product_to_csv(product, filename):
    if not product:
        logging.info("No product to save.")
        return
    
    from models.product import Product
    fieldnames = Product.model_fields.keys()
    processed_product = product.copy()
    if "image_urls" in processed_product and processed_product["image_urls"]:
        processed_product["image_urls"] = json.dumps(processed_product["image_urls"])
    if "variants" in processed_product and processed_product["variants"]:
        processed_product["variants"] = json.dumps(processed_product["variants"])
    if "detailed_info" in processed_product and processed_product["detailed_info"]:
        processed_product["detailed_info"] = json.dumps(processed_product["detailed_info"])
    if "comments" in processed_product and processed_product["comments"]:
        processed_product["comments"] = json.dumps(processed_product["comments"])
    
    file_exists = os.path.isfile(filename)
    with open(filename, mode="a" if file_exists else "w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        writer.writerow(processed_product)
    logging.info(f"Immediately saved product '{processed_product['name']}' to '{filename}'.")

def extract_product_details(driver, product, output_file):
    url = product["product_url"]
    logging.info(f"Scraping product detail page: {url}")
    try:
        driver.get(url)
        wait_for_page_load(driver, selector=".detail-style")
        scroll_page_slowly(driver)
        
        html = driver.page_source
        soup = BeautifulSoup(html, 'html.parser')
        
        detailed_product = product.copy()
        
        image_urls = [img["src"] for img in soup.select(".swiper-slide img") if img.get("src")]
        detailed_product["image_urls"] = image_urls if image_urls else None
        
        variants = []
        variant_elements = soup.select(".swiper-list-cate-search .swiper-slide")
        for variant in variant_elements:
            variant_data = {
                "name": variant.select_one(".bg-[#00AC5B]").get_text(strip=True) if variant.select_one(".bg-[#00AC5B]") else "",
                "price": variant.select_one(".text-12.font-bold").get_text(strip=True) if variant.select_one(".text-12.font-bold") else "",
                "original_price": variant.select_one(".line-through").get_text(strip=True) if variant.select_one(".line-through") else "",
                "discount": variant.select_one(".discount").get_text(strip=True) if variant.select_one(".discount") else "",
                "unit_price": variant.select_one(".text-10.leading-4").get_text(strip=True) if variant.select_one(".text-10.leading-4") else ""
            }
            variants.append(variant_data)
        detailed_product["variants"] = variants if variants else None
        
        detailed_info = {}
        table = soup.select_one(".detail-style table")
        if table:
            for row in table.find_all("tr"):
                cols = row.find_all("td")
                if len(cols) == 2:
                    key = cols[0].get_text(strip=True)
                    value = cols[1].get_text(strip=True)
                    detailed_info[key] = value
        detailed_product["detailed_info"] = detailed_info if detailed_info else None
        
        comments = []
        detailed_product["comments"] = comments if comments else None
        
        original_price_elem = soup.select_one("div.line-through")
        detailed_product["original_price"] = original_price_elem.get_text(strip=True) if original_price_elem else None
        
        discount_elem = soup.select_one("span.bg-red")
        detailed_product["discount"] = discount_elem.get_text(strip=True) if discount_elem else None
        
        # Lưu ngay lập tức sau khi lấy xong thông tin
        save_product_to_csv(detailed_product, output_file)
        return detailed_product
    except Exception as e:
        logging.error(f"Error scraping {url}: {str(e)}")
        return None  # Trả về None nếu lỗi, sẽ bỏ qua sản phẩm này

def crawl_bachhoaxanh():
    options = uc.ChromeOptions()
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    driver = uc.Chrome(options=options)
    
    output_file = OUTPUT_FILE
    all_products = []
    
    try:
        categories = extract_categories(driver)
        
        for category in categories:
            products = extract_products(driver, category)
            
            for product in products:
                detailed_product = extract_product_details(driver, product, output_file)
                if detailed_product:  # Chỉ thêm vào all_products nếu crawl thành công
                    all_products.append(detailed_product)
                else:
                    logging.info(f"Skipped product due to error: {product['name']}")
                time.sleep(1)
        
        logging.info(f"Total products extracted and saved: {len(all_products)}")
        return len(all_products)
    
    finally:
        driver.quit()

if __name__ == "__main__":
    total_count = crawl_bachhoaxanh()
    logging.info(f"Crawling completed. Total products: {total_count}")