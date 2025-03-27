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
import traceback

# Cấu hình logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


# Thêm vào phần đầu file main.py, sau phần khai báo hằng số hiện tại
BASE_URL = "https://www.bachhoaxanh.com/"
CATEGORY_CSS_SELECTOR = ".mb-2.flex.flex-wrap .cate"
PRODUCT_CSS_SELECTOR = ".box_product"
# Thêm các selector chi tiết hơn
PRODUCT_NAME_SELECTOR = ".product_name"
PRODUCT_PRICE_SELECTOR = ".product_price"
PRODUCT_DESCRIPTION_SELECTOR = ".mb-4px.block.leading-3"
PRODUCT_RATING_SELECTOR = ".star-rating"  # Thêm nếu có phần tử rating
PRODUCT_REVIEWS_SELECTOR = ".review-count"  # Thêm nếu có phần tử review count
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

def wait_for_page_load(driver, timeout=45, selector=PRODUCT_CSS_SELECTOR):
    try:
        WebDriverWait(driver, timeout).until(
            lambda driver: driver.execute_script("return document.readyState") == "complete"
        )
        WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, selector))
        )
        # Thêm thời gian chờ để đảm bảo các cuộc gọi AJAX hoàn tất
        time.sleep(3)  
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
            products = []
            for product in product_elements:
                product_data = {
                    "name": product.select_one(PRODUCT_NAME_SELECTOR).get_text(strip=True) if product.select_one(PRODUCT_NAME_SELECTOR) else "",
                    "category": category["category_name"],
                    "price": product.select_one(PRODUCT_PRICE_SELECTOR).get_text(strip=True) if product.select_one(PRODUCT_PRICE_SELECTOR) else "",
                    "description": product.select_one(PRODUCT_DESCRIPTION_SELECTOR).get_text(strip=True) if product.select_one(PRODUCT_DESCRIPTION_SELECTOR) else "",
                }
                
                # Cải thiện xây dựng URL sản phẩm
                if product.select_one("a") and product.select_one("a").get("href"):
                    href = product.select_one("a")["href"]
                    if href.startswith("http"):
                        product_data["product_url"] = href
                    else:
                        product_data["product_url"] = BASE_URL + href.lstrip('/')
                else:
                    product_data["product_url"] = full_url
                
                products.append(product_data)
                
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
    
    fieldnames = ["name", "category", "price", "original_price", "discount", 
                  "rating", "reviews", "description", "image_urls", "product_url", 
                  "variants", "detailed_info", "comments"]
    
    processed_product = product.copy()
    # Chuyển đổi các trường phức tạp thành chuỗi JSON
    for field in ["image_urls", "variants", "detailed_info", "comments"]:
        if field in processed_product and processed_product[field]:
            processed_product[field] = json.dumps(processed_product[field], ensure_ascii=False)
    
    # Đảm bảo tất cả các trường đều tồn tại
    for field in fieldnames:
        if field not in processed_product:
            processed_product[field] = None
    
    file_exists = os.path.isfile(filename)
    with open(filename, mode="a" if file_exists else "w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        writer.writerow(processed_product)
    logging.info(f"Saved product '{processed_product.get('name', 'Unknown')}' to '{filename}'.")

def extract_product_details(driver, product, output_file):
    url = product["product_url"]
    logging.info(f"Scraping product detail page: {url}")
    try:
        driver.get(url)
        wait_for_page_load(driver, selector=".detail-style", timeout=45)  # Tăng thời gian chờ
        scroll_page_slowly(driver)
        
        html = driver.page_source
        soup = BeautifulSoup(html, 'html.parser')
        
        detailed_product = product.copy()
        
        # Trích xuất thông tin sản phẩm chính
        name_elem = soup.select_one("h1.title") or soup.select_one(".product_name")
        if name_elem:
            detailed_product["name"] = name_elem.get_text(strip=True)
        
        price_elem = soup.select_one(".product_price") or soup.select_one(".price span")
        if price_elem:
            detailed_product["price"] = price_elem.get_text(strip=True)
        
        # Lấy rating và reviews nếu có
        rating_elem = soup.select_one(".star-rating")
        if rating_elem:
            try:
                detailed_product["rating"] = float(rating_elem.get_text(strip=True).split("/")[0])
            except (ValueError, IndexError):
                detailed_product["rating"] = None
        else:
            detailed_product["rating"] = None
            
        reviews_elem = soup.select_one(".review-count")
        if reviews_elem:
            try:
                detailed_product["reviews"] = int("".join(filter(str.isdigit, reviews_elem.get_text(strip=True))))
            except ValueError:
                detailed_product["reviews"] = None
        else:
            detailed_product["reviews"] = None
        
        # Các thông tin sản phẩm bổ sung
        image_urls = [img["src"] for img in soup.select(".swiper-slide img") if img.get("src")]
        detailed_product["image_urls"] = image_urls if image_urls else None
        
        # Trích xuất mô tả tốt hơn
        description_elem = soup.select_one(".detail-style p") or soup.select_one(".mb-4px.block.leading-3")
        if description_elem:
            detailed_product["description"] = description_elem.get_text(strip=True)
        
        # Thông tin về biến thể sản phẩm
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
        
        # Thông tin chi tiết từ bảng
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
        
        # Thông tin về bình luận
        comments = []
        comment_elements = soup.select(".comment-list .comment-item")
        for comment in comment_elements:
            user_elem = comment.select_one(".user-name")
            content_elem = comment.select_one(".comment-content")
            if user_elem and content_elem:
                comments.append({
                    "user": user_elem.get_text(strip=True),
                    "content": content_elem.get_text(strip=True)
                })
        detailed_product["comments"] = comments if comments else None
        
        # Thông tin về giá gốc và giảm giá
        original_price_elem = soup.select_one("div.line-through") or soup.select_one(".text-[#9da7bc].line-through")
        detailed_product["original_price"] = original_price_elem.get_text(strip=True) if original_price_elem else None
        
        discount_elem = soup.select_one("span.bg-red") or soup.select_one(".promotion-badge")
        detailed_product["discount"] = discount_elem.get_text(strip=True) if discount_elem else None
        
        # Đảm bảo tất cả các trường đều có giá trị
        for field in ["name", "category", "price", "original_price", "discount", 
                     "rating", "reviews", "description", "image_urls", "product_url", 
                     "variants", "detailed_info", "comments"]:
            if field not in detailed_product:
                detailed_product[field] = None
        
        # Lưu ngay lập tức sau khi lấy xong thông tin
        save_product_to_csv(detailed_product, output_file)
        return detailed_product
    except Exception as e:
        logging.error(f"Error scraping {url}: {str(e)}")
        logging.error(traceback.format_exc())  # Thêm stack trace để debug tốt hơn
        return product  # Trả về thông tin sản phẩm ban đầu thay vì None
    
def crawl_bachhoaxanh():
    # Thêm import nếu chưa có
    import traceback
    
    options = uc.ChromeOptions()
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    # Thêm các options mới để tránh phát hiện
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
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
                    logging.info(f"Skipped product due to error: {product.get('name', 'Unknown')}")
                time.sleep(1)
        
        logging.info(f"Total products extracted and saved: {len(all_products)}")
        return len(all_products)
    except Exception as e:
        logging.error(f"Unexpected error in crawl_bachhoaxanh: {str(e)}")
        logging.error(traceback.format_exc())
        return 0
    finally:
        driver.quit()

if __name__ == "__main__":
    total_count = crawl_bachhoaxanh()
    logging.info(f"Crawling completed. Total products: {total_count}")