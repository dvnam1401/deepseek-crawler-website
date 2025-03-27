# main.py
import logging
import time
import json
import re
import os
import traceback
import requests
import sys
import io
from typing import Dict, List, Any, Optional
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, StaleElementReferenceException
import undetected_chromedriver as uc
from bs4 import BeautifulSoup
from slugify import slugify
import csv
from dotenv import load_dotenv
import pandas as pd
# Đảm bảo thư mục images tồn tại
os.makedirs("images", exist_ok=True)
# Cấu hình encoding cho tiếng Việt
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Cấu hình logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("crawler.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)

# Tải biến môi trường từ .env
load_dotenv()

# Định nghĩa hằng số
BASE_URL = "https://www.bachhoaxanh.com/"
CATEGORY_CSS_SELECTOR = ".mb-2.flex.flex-wrap .cate"
PRODUCT_CSS_SELECTOR = ".box_product"
OUTPUT_FILE = "bachhoaxanh_products.csv"
MAX_RETRIES = 3
WAIT_TIME = 45

# Các selector backup để trích xuất thông tin
SELECTORS = {
    "name": [
        "h1.title", 
        ".product_name", 
        "h1", 
        ".product-title", 
        "meta[property='og:title']"
    ],
    "price": [
        ".product_price", 
        ".price span", 
        ".current-price", 
        "span.price"
    ],
    "original_price": [
        "div.line-through", 
        ".text-[#9da7bc].line-through", 
        ".original-price"
    ],
    "discount": [
        "span.bg-red", 
        ".promotion-badge", 
        ".discount"
    ],
    "description": [
        ".detail-style p", 
        ".mb-4px.block.leading-3", 
        ".product-description", 
        ".detail-content"
    ]
}

def setup_driver():
    """Thiết lập driver với các options để tránh phát hiện"""
    options = uc.ChromeOptions()
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    # Không tắt hình ảnh để đảm bảo có thể thu thập đúng dữ liệu
    
    driver = uc.Chrome(options=options)
    return driver

def scroll_page_slowly(driver, max_scroll_time=20):
    """Scroll trang chậm để tải nội dung lazy load"""
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

def wait_for_page_load(driver, timeout=WAIT_TIME, selector="body"):
    """Đợi trang tải xong với timeout và selector tùy chỉnh"""
    try:
        WebDriverWait(driver, timeout).until(
            lambda driver: driver.execute_script("return document.readyState") == "complete"
        )
        WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, selector))
        )
        # Thêm thời gian chờ để đảm bảo AJAX load xong
        time.sleep(3)
        logging.info(f"Page loaded successfully with elements matching '{selector}'.")
        return True
    except TimeoutException:
        logging.warning(f"Timeout waiting for page load or elements '{selector}' after {timeout} seconds.")
        return False

# Cần thêm function mới để trích xuất URL hình ảnh
def extract_product_images(driver, soup):
    """
    Trích xuất tất cả URL hình ảnh của sản phẩm sử dụng cả BeautifulSoup và JavaScript
    
    Args:
        driver: WebDriver instance
        soup: BeautifulSoup object
    
    Returns:
        list: Danh sách các URL hình ảnh
    """
    image_urls = []
    
    # Phương pháp 1: Tìm hình ảnh trong swiper-slide
    try:
        # Tìm tất cả hình ảnh trong swiper-slide (thường chứa nhiều hình ảnh sản phẩm)
        swiper_images = soup.select(".swiper-slide img")
        for img in swiper_images:
            src = img.get("src") or img.get("data-src")
            if src and src.startswith("https://cdnv2.tgdd.vn/") and "placeholder" not in src:
                src = src.split("?")[0]  # Loại bỏ query params
                if src not in image_urls:
                    image_urls.append(src)
    except Exception as e:
        logging.error(f"Error extracting swiper images: {str(e)}")
    
    # Phương pháp 2: Tìm tất cả hình ảnh sản phẩm bằng selector phổ biến
    if len(image_urls) < 2:  # Nếu không tìm thấy đủ hình ảnh
        try:
            # Các selector phổ biến cho hình ảnh sản phẩm
            selectors = [
                "img[src*='cdnv2.tgdd.vn']",
                ".product-image img",
                ".product-gallery img",
                "[data-gallery-role='gallery'] img"
            ]
            
            for selector in selectors:
                try:
                    images = soup.select(selector)
                    for img in images:
                        src = img.get("src") or img.get("data-src")
                        if src and "placeholder" not in src:
                            src = src.split("?")[0]
                            if src not in image_urls:
                                image_urls.append(src)
                except Exception:
                    continue
        except Exception as e:
            logging.error(f"Error extracting images with selectors: {str(e)}")
    
    # Phương pháp 3: Sử dụng JavaScript để lấy tất cả hình ảnh
    if len(image_urls) < 2:  # Nếu vẫn chưa tìm thấy đủ hình ảnh
        try:
            js_script = """
            const getAllProductImages = () => {
                // Tìm tất cả các thẻ img trên trang
                const allImages = Array.from(document.querySelectorAll('img'));
                
                // Lọc những img có src bắt đầu bằng cdnv2.tgdd.vn (hình ảnh sản phẩm)
                return allImages
                    .filter(img => img.src && img.src.includes('cdnv2.tgdd.vn') && !img.src.includes('placeholder'))
                    .map(img => img.src);
            };
            
            return getAllProductImages();
            """
            
            js_images = driver.execute_script(js_script)
            
            for src in js_images:
                src = src.split("?")[0]  # Loại bỏ query params
                if src and src not in image_urls:
                    image_urls.append(src)
        except Exception as e:
            logging.error(f"Error extracting images with JavaScript: {str(e)}")
    
    # Phương pháp 4: Tìm trong data-src trong các element khác
    if len(image_urls) < 2:
        try:
            data_src_elements = soup.select("[data-src], [data-lazy], [data-original]")
            for elem in data_src_elements:
                src = elem.get("data-src") or elem.get("data-lazy") or elem.get("data-original")
                if src and "cdnv2.tgdd.vn" in src and "placeholder" not in src:
                    src = src.split("?")[0]
                    if src not in image_urls:
                        image_urls.append(src)
        except Exception as e:
            logging.error(f"Error extracting images from data attributes: {str(e)}")
    
    # Phương pháp 5: Sử dụng JavaScript để kích hoạt slider nếu có
    if len(image_urls) < 2:
        try:
            # Cố gắng kích hoạt slider nếu có
            js_activate_slider = """
            // Tìm và kích hoạt các nút next/prev của slider nếu có
            const nextButtons = Array.from(document.querySelectorAll('.swiper-button-next, .slick-next, [class*="next"]'));
            const prevButtons = Array.from(document.querySelectorAll('.swiper-button-prev, .slick-prev, [class*="prev"]'));
            
            // Click vào các nút để kích hoạt slider
            if (nextButtons.length > 0) {
                nextButtons.forEach(btn => {
                    if (btn.offsetParent !== null) { // Kiểm tra nút có hiển thị không
                        btn.click();
                    }
                });
                return true;
            }
            return false;
            """
            
            slider_activated = driver.execute_script(js_activate_slider)
            
            if slider_activated:
                # Đợi slider chuyển động
                time.sleep(1)
                
                # Lấy lại HTML sau khi kích hoạt slider
                updated_html = driver.page_source
                updated_soup = BeautifulSoup(updated_html, 'html.parser')
                
                # Tìm lại hình ảnh sau khi kích hoạt slider
                slider_images = updated_soup.select(".swiper-slide img")
                for img in slider_images:
                    src = img.get("src") or img.get("data-src")
                    if src and src.startswith("https://cdnv2.tgdd.vn/") and "placeholder" not in src:
                        src = src.split("?")[0]
                        if src not in image_urls:
                            image_urls.append(src)
        except Exception as e:
            logging.error(f"Error activating slider: {str(e)}")
    
    return image_urls

# Cải thiện phương pháp để lấy mô tả đúng
def get_product_description(soup):
    """Lấy mô tả sản phẩm từ các nguồn khác nhau"""
    # Thử các selector có khả năng chứa mô tả sản phẩm
    desc_selectors = [
        ".product-content p",       # Nội dung sản phẩm
        "div.text-justify",         # Text justify thường là mô tả
        ".detail-content",          # Nội dung chi tiết
        ".product-description"      # Mô tả sản phẩm
    ]
    
    for selector in desc_selectors:
        elems = soup.select(selector)
        for elem in elems:
            text = elem.get_text(strip=True)
            if text and text != "Bài viết sản phẩm" and len(text) > 20:
                return text
    
    # Nếu không tìm thấy, thử trích xuất từ div có chứa văn bản dài
    for div in soup.find_all("div"):
        text = div.get_text(strip=True)
        if len(text) > 50 and "." in text and text != "Bài viết sản phẩm":
            # Loại bỏ các nút và UI text
            if not any(btn_text in text.lower() for btn_text in ["xem thêm", "đóng", "click", "button"]):
                return text
    
    # Cuối cùng, thử meta description
    meta_desc = soup.select_one("meta[name='description']")
    if meta_desc and meta_desc.get("content"):
        return meta_desc.get("content")
    
    return None

def click_info_tab(driver):
    """Click vào tab 'Thông tin sản phẩm' nếu có"""
    try:
        # Thử tìm bằng XPath - cách chính xác nhất
        info_tab_xpath = "//div[contains(text(), 'Thông tin sản phẩm')]"
        info_buttons = driver.find_elements(By.XPATH, info_tab_xpath)
        
        if info_buttons:
            for button in info_buttons:
                try:
                    if button.is_displayed():
                        # Scroll đến phần tử trước khi click
                        driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", button)
                        time.sleep(1)  # Đợi scroll xong
                        
                        # Click bằng JavaScript để đảm bảo
                        driver.execute_script("arguments[0].click();", button)
                        logging.info("Clicked on 'Thông tin sản phẩm' button")
                        time.sleep(2)  # Đợi nội dung hiển thị
                        return True
                except Exception as e:
                    logging.debug(f"Error clicking button: {str(e)}")
                    continue
                    
        # Nếu không tìm thấy, thử các cách khác
        try:
            # Thử tìm bằng JavaScript
            script = """
            const tabs = Array.from(document.querySelectorAll('div, button, span'));
            const infoTab = tabs.find(el => el.innerText && el.innerText.includes('Thông tin sản phẩm'));
            if (infoTab) {
                infoTab.click();
                return true;
            }
            return false;
            """
            clicked = driver.execute_script(script)
            if clicked:
                logging.info("Clicked on 'Thông tin sản phẩm' using JavaScript")
                time.sleep(2)
                return True
        except:
            pass
        
        logging.info("No 'Thông tin sản phẩm' tab found or already active")
        return False
    except Exception as e:
        logging.error(f"Error clicking info tab: {str(e)}")
        return False

def extract_table_data_from_tables(soup):
    """Trích xuất dữ liệu từ tất cả các bảng"""
    table_data = {}
    # Tìm tất cả bảng
    tables = soup.select("table")
    
    for table in tables:
        rows = table.select("tr")
        for row in rows:
            cells = row.select("td")
            if len(cells) >= 2:
                key = cells[0].get_text(strip=True)
                # Lấy text từ tất cả nội dung, kể cả nếu nằm trong div
                value_cell = cells[1]
                value = value_cell.get_text(strip=True)
                if key and value:
                    table_data[key] = value
    
    return table_data

def extract_with_backup_method(driver, soup, url, category_name):
    """Phương pháp backup để trích xuất thông tin từ trang sản phẩm"""
    product_data = {"product_url": url, "category": category_name}
    
    # Trích xuất thông tin cơ bản
    for field, selectors in SELECTORS.items():
        for selector in selectors:
            try:
                if selector.startswith("meta"):
                    meta_elem = soup.select_one(selector)
                    if meta_elem and meta_elem.get("content"):
                        product_data[field] = meta_elem.get("content").strip()
                        break
                else:
                    elems = soup.select(selector)
                    if elems:
                        for elem in elems:
                            text = elem.get_text(strip=True)
                            if text:
                                product_data[field] = text
                                break
                        if field in product_data:
                            break
            except Exception as e:
                logging.debug(f"Error extracting {field} with selector {selector}: {str(e)}")
    
    # Click vào tab "Thông tin sản phẩm" nếu có
    tab_clicked = click_info_tab(driver)
    
    # Lấy lại HTML sau khi click (hoặc không click nếu không có tab)
    updated_html = driver.page_source
    updated_soup = BeautifulSoup(updated_html, 'html.parser')
    
    # Trích xuất dữ liệu từ bảng thông tin chi tiết
    table_data = extract_table_data_from_tables(updated_soup)
    
    # Ánh xạ các trường thông dụng
    field_mapping = {
        "Khối lượng": "khoi_luong",
        "Số lượng trái": "so_luong_trai",
        "Xuất xứ": "xuat_xu",
        "Vùng trồng": "xuat_xu",
        "Hướng dẫn bảo quản": "bao_quan",
        "Hướng dẫn sử dụng": "huong_dan_su_dung",
        "Thành phần": "thanh_phan"
    }
    
    # Cập nhật dữ liệu từ bảng
    for table_key, value in table_data.items():
        for field_key, field_name in field_mapping.items():
            if field_key.lower() in table_key.lower():
                product_data[field_name] = value
                break
    
    # Lấy mô tả sản phẩm đúng (không phải "Bài viết sản phẩm")
    if "description" not in product_data or product_data["description"] == "Bài viết sản phẩm":
        try:
            # Tìm mô tả trong văn bản có ý nghĩa
            paragraphs = []
            for p in updated_soup.select("p"):
                text = p.get_text(strip=True)
                if text and text != "Bài viết sản phẩm" and len(text) > 20:
                    paragraphs.append(text)
            
            if paragraphs:
                product_data["description"] = max(paragraphs, key=len)
            else:
                # Thử tìm trong các div có content
                for div in updated_soup.select("div"):
                    text = div.get_text(strip=True)
                    if text and text != "Bài viết sản phẩm" and len(text) > 50:
                        paragraphs.append(text)
                
                if paragraphs:
                    product_data["description"] = max(paragraphs, key=len)
                else:
                    # Tìm trong meta description
                    meta_desc = updated_soup.select_one("meta[name='description']")
                    if meta_desc and meta_desc.get("content"):
                        product_data["description"] = meta_desc.get("content")
        except Exception as e:
            logging.error(f"Error extracting description: {str(e)}")
    
    # Trích xuất và tải xuống tất cả hình ảnh sản phẩm
    image_urls = extract_product_images(driver, updated_soup)
    
    if image_urls:
        # Lưu URL hình ảnh đầu tiên vào product_data
        product_data["image_url"] = image_urls[0]
        
        # Lưu danh sách URL của tất cả hình ảnh
        product_data["all_image_urls"] = ",".join(image_urls)
        
        # Tải xuống tất cả hình ảnh nếu có tên sản phẩm
        if "name" in product_data and product_data["name"]:
            try:
                product_name = product_data["name"]
                downloaded_images = download_images(image_urls, product_name)
                if downloaded_images:
                    # Lưu đường dẫn đến thư mục hình ảnh
                    product_data["images_folder"] = os.path.dirname(downloaded_images[0])
                    logging.info(f"Downloaded {len(downloaded_images)} images for product: {product_name}")
            except Exception as e:
                logging.error(f"Error downloading images for product {product_data.get('name', 'Unknown')}: {str(e)}")
    
    return product_data

import os
import requests
import shutil
from urllib.parse import urlparse
from slugify import slugify

def download_images(image_urls, product_name):
    """
    Tải xuống nhiều hình ảnh và lưu vào thư mục có tên theo sản phẩm
    
    Args:
        image_urls (list): Danh sách URL hình ảnh
        product_name (str): Tên sản phẩm (sẽ được sử dụng làm tên thư mục)
    
    Returns:
        list: Danh sách đường dẫn đến các hình ảnh đã tải xuống
    """
    if not image_urls:
        logging.info(f"No images to download for product: {product_name}")
        return []
    
    # Tạo tên thư mục an toàn từ tên sản phẩm
    folder_name = slugify(product_name)
    folder_path = os.path.join("images", folder_name)
    
    # Tạo thư mục nếu chưa tồn tại
    os.makedirs(folder_path, exist_ok=True)
    
    downloaded_images = []
    
    for i, url in enumerate(image_urls):
        try:
            # Tạo tên file từ URL hoặc index
            parsed_url = urlparse(url)
            file_name = os.path.basename(parsed_url.path)
            
            # Nếu tên file không hợp lệ, sử dụng index
            if not file_name or len(file_name) < 5:
                file_name = f"image_{i+1}.jpg"
            
            file_path = os.path.join(folder_path, file_name)
            
            # Tải hình ảnh
            response = requests.get(url, stream=True, timeout=10)
            if response.status_code == 200:
                with open(file_path, 'wb') as file:
                    shutil.copyfileobj(response.raw, file)
                logging.info(f"Downloaded image: {file_path}")
                downloaded_images.append(file_path)
            else:
                logging.warning(f"Failed to download image: {url} - Status code: {response.status_code}")
        
        except Exception as e:
            logging.error(f"Error downloading image {url}: {str(e)}")
    
    return downloaded_images

def extract_product_details(driver, product, output_file):
    """Chiến lược trích xuất thông tin chi tiết sản phẩm chỉ dùng phương pháp backup"""
    url = product["product_url"]
    category_name = product.get("category", "")
    logging.info(f"Scraping product detail page: {url}")
    
    for attempt in range(MAX_RETRIES):
        try:
            driver.get(url)
            page_loaded = wait_for_page_load(driver, timeout=WAIT_TIME, selector=".detail-style, .product-detail")
            
            if not page_loaded and attempt < MAX_RETRIES - 1:
                logging.warning(f"Page not loaded properly on attempt {attempt+1}/{MAX_RETRIES}. Retrying...")
                time.sleep(2)
                continue
                
            scroll_page_slowly(driver)
            
            # Lấy HTML ban đầu
            html = driver.page_source
            soup = BeautifulSoup(html, 'html.parser')
            
            # Sử dụng phương pháp backup nâng cao
            detailed_product = extract_with_backup_method(driver, soup, url, category_name)
            
            # Gộp dữ liệu ban đầu với kết quả từ phương pháp backup
            for key, value in product.items():
                if key not in detailed_product or not detailed_product[key]:
                    detailed_product[key] = value
            
            # Đảm bảo các trường cơ bản đều có
            required_fields = ["name", "price", "description", "product_url", "category"]
            if all(field in detailed_product for field in required_fields):
                # Lưu ngay sau khi trích xuất thành công
                save_product_to_csv(detailed_product, output_file)
                return detailed_product
            else:
                missing_fields = [field for field in required_fields if field not in detailed_product]
                logging.warning(f"Missing required fields: {missing_fields} for {url}. Retrying...")
        
        except Exception as e:
            logging.error(f"Error on attempt {attempt+1}/{MAX_RETRIES} scraping {url}: {str(e)}")
            logging.error(traceback.format_exc())
        
        # Chờ trước khi thử lại
        if attempt < MAX_RETRIES - 1:
            time.sleep(3)
    
    # Nếu tất cả các lần thử đều thất bại, trả về thông tin ban đầu
    logging.error(f"All attempts failed for {url}. Returning basic product info.")
    return product

def extract_categories(driver):
    """Trích xuất danh sách danh mục sản phẩm"""
    driver.get(BASE_URL)
    wait_for_page_load(driver)
    scroll_page_slowly(driver)
    
    html = driver.page_source
    soup = BeautifulSoup(html, 'html.parser')
    categories = []
    
    try:
        category_elements = soup.select(CATEGORY_CSS_SELECTOR)
        if not category_elements:
            logging.warning(f"No category elements found with selector: {CATEGORY_CSS_SELECTOR}")
            logging.info("Trying alternative selectors...")
            
            # Thử các selector thay thế
            alternative_selectors = [".category-item", ".cate-item", "a.cate", ".menu-categories a"]
            for selector in alternative_selectors:
                category_elements = soup.select(selector)
                if category_elements:
                    logging.info(f"Found categories with alternative selector: {selector}")
                    break
        
        for cate in category_elements:
            cate_name = cate.get_text(strip=True)
            if not cate_name:
                continue
                
            # Lấy URL từ thẻ a
            if cate.name == "a" and cate.get("href"):
                cate_url = cate["href"]
            else:
                cate_url = f"/{slugify(cate_name)}"
                
            categories.append({
                "category_name": cate_name,
                "category_url": cate_url
            })
    
    except Exception as e:
        logging.error(f"Error extracting categories: {str(e)}")
        logging.error(traceback.format_exc())
    
    logging.info(f"Extracted {len(categories)} categories.")
    return categories

def extract_products(driver, category, retries=MAX_RETRIES):
    """Trích xuất danh sách sản phẩm từ một danh mục"""
    full_url = category["category_url"]
    if not full_url.startswith("http"):
        full_url = f"{BASE_URL}{category['category_url'].lstrip('/')}"
        
    products = []
    
    for attempt in range(retries):
        logging.info(f"Scraping category page (Attempt {attempt + 1}/{retries}): {full_url}")
        try:
            driver.get(full_url)
            wait_for_page_load(driver)
            scroll_page_slowly(driver)
            
            product_html = driver.page_source
            product_soup = BeautifulSoup(product_html, 'html.parser')
            product_elements = product_soup.select(PRODUCT_CSS_SELECTOR)
            
            if not product_elements:
                # Thử selector thay thế
                alternative_selectors = [".product-item", ".product-list-item", ".product"]
                for selector in alternative_selectors:
                    alt_products = product_soup.select(selector)
                    if alt_products:
                        logging.info(f"Found products with alternative selector: {selector}")
                        product_elements = alt_products
                        break
            
            if product_elements:
                for product in product_elements:
                    try:
                        # Tìm tên sản phẩm
                        name_elem = product.select_one(".product_name")
                        name = name_elem.get_text(strip=True) if name_elem else ""
                        
                        # Tìm giá sản phẩm
                        price_elem = product.select_one(".product_price")
                        price = price_elem.get_text(strip=True) if price_elem else ""
                        
                        # Tìm mô tả sản phẩm
                        desc_elem = product.select_one(".mb-4px.block.leading-3")
                        description = desc_elem.get_text(strip=True) if desc_elem else ""
                        
                        # Tìm URL sản phẩm
                        url = None
                        link_elem = product.select_one("a")
                        if link_elem and link_elem.get("href"):
                            url = link_elem["href"]
                            if not url.startswith("http"):
                                url = f"{BASE_URL}{url.lstrip('/')}"
                        else:
                            url = full_url
                            
                        if name and url:
                            products.append({
                                "name": name,
                                "category": category["category_name"],
                                "price": price,
                                "description": description,
                                "product_url": url
                            })
                    except Exception as e:
                        logging.error(f"Error processing product element: {str(e)}")
                        continue
                
                logging.info(f"Extracted {len(products)} products from {category['category_name']}.")
                break
            else:
                logging.warning(f"No products found on attempt {attempt + 1}. HTML sample: {product_html[:500]}...")
                if attempt < retries - 1:
                    time.sleep(2)
        
        except Exception as e:
            logging.error(f"Error on attempt {attempt + 1} for category {category['category_name']}: {str(e)}")
            if attempt < retries - 1:
                time.sleep(2)
    
    if not products:
        logging.error(f"Failed to extract products from {category['category_name']} after {retries} attempts.")
    
    return products

def save_product_to_csv(product, filename):
    """Lưu một sản phẩm vào file CSV"""
    if not product:
        logging.info("No product to save.")
        return
    
    # Danh sách các trường muốn lưu
    fieldnames = [
        "name", "category", "price", "original_price", "discount", 
        "description", "product_url", "image_url", "all_image_urls", 
        "images_folder", "khoi_luong", "xuat_xu",
        "bao_quan", "huong_dan_su_dung", "thanh_phan"
    ]
    
    processed_product = {}
    
    # Chỉ lấy các trường trong fieldnames
    for field in fieldnames:
        processed_product[field] = product.get(field, None)
    
    file_exists = os.path.isfile(filename)
    with open(filename, mode="a" if file_exists else "w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        writer.writerow(processed_product)
    logging.info(f"Saved product '{processed_product.get('name', 'Unknown')}' to '{filename}'.")
def save_products_to_csv(products, filename):
    """Lưu danh sách sản phẩm vào file CSV"""
    if not products:
        logging.info("No products to save.")
        return
    
    # Danh sách các trường muốn lưu
    fieldnames = [
        "name", "category", "price", "original_price", "discount", 
        "description", "product_url", "khoi_luong", "xuat_xu",
        "bao_quan", "huong_dan_su_dung", "thanh_phan"
    ]
    
    # Xử lý từng sản phẩm
    processed_products = []
    for product in products:
        processed_product = {}
        for field in fieldnames:
            processed_product[field] = product.get(field, None)
        processed_products.append(processed_product)
    
    # Sử dụng pandas để lưu file CSV
    df = pd.DataFrame(processed_products)
    df.to_csv(filename, index=False, encoding='utf-8-sig')
    logging.info(f"Saved {len(products)} products to '{filename}'.")

def crawl_bachhoaxanh():
    """Hàm chính để crawl dữ liệu từ BachHoaXanh"""
    driver = setup_driver()
    output_file = OUTPUT_FILE
    all_products = []
    seen_urls = set()
    
    try:
        # Bước 1: Lấy danh sách danh mục
        categories = extract_categories(driver)
        if not categories:
            logging.error("No categories found. Exiting.")
            return 0
            
        # Lấy sample nhỏ để test (uncomment dòng dưới để test)
        # categories = categories[:2]  # Chỉ lấy 2 danh mục đầu tiên để test
        
        # Bước 2: Lặp qua từng danh mục và lấy sản phẩm
        for category in categories:
            try:
                logging.info(f"Processing category: {category['category_name']}")
                products = extract_products(driver, category)
                
                # Bước 3: Lấy thông tin chi tiết của từng sản phẩm
                for i, product in enumerate(products):
                    if product["product_url"] in seen_urls:
                        logging.info(f"Skipping duplicate product: {product['name']}")
                        continue
                        
                    detailed_product = extract_product_details(driver, product, output_file)
                    if detailed_product:
                        all_products.append(detailed_product)
                        seen_urls.add(detailed_product["product_url"])
                    
                    # Giới hạn số lượng sản phẩm trích xuất cho mỗi danh mục để tránh crawl quá nhiều
                    if i >= 14:  # Only get first 15 products from each category
                        logging.info(f"Reached limit of 15 products for category {category['category_name']}")
                        break
                    
                    # Tạm nghỉ giữa các request để tránh bị chặn
                    time.sleep(1)
            
            except Exception as e:
                logging.error(f"Error processing category {category['category_name']}: {str(e)}")
                logging.error(traceback.format_exc())
                continue
        
        # Lưu tất cả sản phẩm vào một file CSV riêng
        if all_products:
            save_products_to_csv(all_products, "all_" + output_file)
            logging.info(f"Total products extracted and saved: {len(all_products)}")
        
        return len(all_products)
    
    except Exception as e:
        logging.error(f"Unexpected error in crawl_bachhoaxanh: {str(e)}")
        logging.error(traceback.format_exc())
        return 0
    
    finally:
        driver.quit()

if __name__ == "__main__":
    start_time = time.time()
    logging.info("Starting BachHoaXanh crawler...")
    
    total_count = crawl_bachhoaxanh()
    
    elapsed_time = time.time() - start_time
    logging.info(f"Crawling completed. Total products: {total_count}")
    logging.info(f"Total time: {elapsed_time:.2f} seconds")