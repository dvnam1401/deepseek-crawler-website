#!/usr/bin/env python3
"""
Crawler cho danh sách sản phẩm từ danh mục
"""
import os
import json
import time
import csv
import logging
import argparse
from typing import List, Dict, Any, Set
from bs4 import BeautifulSoup
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

from config import (
    BASE_URL, 
    PRODUCT_CSS_SELECTOR, 
    OUTPUT_DIR, 
    WAIT_TIME, 
    MAX_RETRIES,
    CRAWL_DELAY,
    USER_AGENT
)

# Thiết lập logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("product_list_crawler.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

class ProductListCrawler:
    """Crawler chuyên biệt cho việc crawl danh sách sản phẩm từ danh mục"""
    
    def __init__(self, 
                category_file: str = "categories.json",
                output_file: str = "product_list.csv"):
        """
        Khởi tạo ProductListCrawler
        
        Args:
            category_file: Tên file chứa danh sách danh mục
            output_file: Tên file đầu ra để lưu danh sách sản phẩm
        """
        self.category_file = os.path.join(OUTPUT_DIR, category_file)
        self.output_file = os.path.join(OUTPUT_DIR, output_file)
        self.driver = None
        self.seen_urls = set()  # Tập hợp URL đã thấy để tránh trùng lặp
        
        # Đảm bảo thư mục đầu ra tồn tại
        os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    def setup_driver(self):
        """Thiết lập driver với các options để tránh phát hiện"""
        options = uc.ChromeOptions()
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--window-size=1920,1080")
        options.add_argument(f"--user-agent={USER_AGENT}")
        
        self.driver = uc.Chrome(options=options)
        return self.driver
    
    def close_driver(self):
        """Đóng driver sau khi hoàn thành"""
        if self.driver:
            self.driver.quit()
            self.driver = None
    
    def wait_for_page_load(self, timeout: int = WAIT_TIME):
        """Đợi trang tải xong"""
        try:
            self.driver.implicitly_wait(timeout)
            # Đợi JavaScript hoàn thành
            WebDriverWait(self.driver, timeout).until(
                lambda driver: driver.execute_script("return document.readyState") == "complete"
            )
            # Đợi cho phần tử body xuất hiện để đảm bảo DOM được tải
            WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            # Thêm thời gian chờ để đảm bảo AJAX load xong
            time.sleep(3)
            return True
        except TimeoutException as e:
            logger.error(f"Timeout khi đợi trang tải: {e}")
            return False
        except Exception as e:
            logger.error(f"Lỗi khi đợi trang tải: {e}")
            return False
    
    def scroll_page_slowly(self, max_scroll_time: int = 20):
        """Scroll trang chậm để tải nội dung lazy load"""
        if not self.driver:
            logger.error("Driver chưa được khởi tạo")
            return
            
        last_height = self.driver.execute_script("return document.body.scrollHeight")
        step = 500
        current_position = 0
        start_time = time.time()

        while current_position < last_height and (time.time() - start_time) < max_scroll_time:
            self.driver.execute_script(f"window.scrollTo(0, {current_position});")
            time.sleep(1)
            current_position += step
            new_height = self.driver.execute_script("return document.body.scrollHeight")
            if new_height > last_height:
                last_height = new_height
    
    def load_categories(self) -> List[Dict[str, Any]]:
        """
        Tải danh sách danh mục từ file
        
        Returns:
            List[Dict[str, Any]]: Danh sách các danh mục
        """
        try:
            if not os.path.exists(self.category_file):
                logger.error(f"File danh mục {self.category_file} không tồn tại")
                return []
                
            with open(self.category_file, 'r', encoding='utf-8') as f:
                categories = json.load(f)
                logger.info(f"Đã tải {len(categories)} danh mục từ {self.category_file}")
                return categories
        except Exception as e:
            logger.error(f"Lỗi khi tải danh mục từ file: {e}")
            return []
    
    def load_seen_urls(self) -> Set[str]:
        """
        Tải danh sách URL sản phẩm đã thấy từ file đầu ra (nếu có)
        để tránh crawl lại sản phẩm đã có
        
        Returns:
            Set[str]: Tập hợp các URL đã thấy
        """
        seen_urls = set()
        
        try:
            if os.path.exists(self.output_file):
                with open(self.output_file, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        if 'product_url' in row and row['product_url']:
                            seen_urls.add(row['product_url'])
                    logger.info(f"Đã tải {len(seen_urls)} URL sản phẩm đã thấy từ {self.output_file}")
        except Exception as e:
            logger.error(f"Lỗi khi tải URL đã thấy: {e}")
        
        return seen_urls
    
    def close_popups(self):
        """Đóng các popup và thông báo trên trang web
        
        Returns:
            bool: True nếu đã phát hiện và xử lý popup, False nếu không có popup
        """
        if not self.driver:
            logger.error("Driver chưa được khởi tạo")
            return False
            
        popup_detected = False
        logger.info("Đang kiểm tra có thông báo popup không...")
        
        # Danh sách các CSS selector phổ biến cho các loại popup và nút đóng
        popup_selectors = {
            # Popup cookie consent
            "cookie_accept": [
                "button[aria-label='Accept cookies']", 
                ".cookie-accept", 
                ".accept-cookies", 
                ".accept-all", 
                "button:contains('Accept')", 
                "button:contains('Đồng ý')",
                "#cookieConsent button",
                ".cookie-banner .accept"
            ],
            # Popup newsletter
            "newsletter_close": [
                ".newsletter-popup .close", 
                ".popup-close", 
                ".modal .close", 
                ".modal-close"
            ],
            # Popup quảng cáo
            "ad_close": [
                ".ad-popup .close", 
                ".ads-close", 
                ".advertisement .close", 
                "#ad-overlay .close"
            ],
            # Popup thông báo chung
            "generic_close": [
                ".popup .close", 
                ".modal .close-button", 
                ".notification .close", 
                ".alert .close",
                "button.dismiss",
                ".btn-close"
            ]
        }

        # Thử đóng popup bằng các selector khác nhau
        for popup_type, selectors in popup_selectors.items():
            for selector in selectors:
                try:
                    # Thử tìm phần tử theo CSS selector
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    for element in elements:
                        if element.is_displayed():
                            logger.info(f"Đang đóng popup ({popup_type}) với selector: {selector}")
                            element.click()
                            popup_detected = True
                            time.sleep(0.5)  # Chờ animation đóng popup
                except Exception as e:
                    logger.debug(f"Không tìm thấy popup với selector {selector}: {str(e)}")

        # Thử đóng popup bằng cách tìm nút có chứa text đóng
        close_texts = ["Đóng", "Close", "Skip", "Bỏ qua", "X", "×", "Không, cảm ơn", "No, thanks", "Để sau"]
        for text in close_texts:
            try:
                xpath = f"//button[contains(text(),'{text}')] | //a[contains(text(),'{text}')] | //*[contains(@class,'close') and contains(text(),'{text}')]"
                elements = self.driver.find_elements(By.XPATH, xpath)
                for element in elements:
                    if element.is_displayed():
                        logger.info(f"Đang đóng popup với text: {text}")
                        element.click()
                        popup_detected = True
                        time.sleep(0.5)
            except Exception as e:
                logger.debug(f"Không tìm thấy nút đóng với text {text}: {str(e)}")

        # Đóng popup sử dụng JavaScript (phương pháp cuối cùng)
        try:
            js_script = """
            // Tìm và đóng các phần tử modal/popup
            const closePopups = () => {
                // Tìm tất cả các phần tử có thể là popup
                const popupElements = document.querySelectorAll('.modal, .popup, .overlay, [class*="popup"], [class*="modal"], [id*="popup"], [id*="modal"]');
                let closed = 0;
                
                popupElements.forEach(popup => {
                    if (popup.style.display !== 'none' && window.getComputedStyle(popup).display !== 'none') {
                        // Tìm nút đóng trong popup
                        const closeButtons = popup.querySelectorAll('button.close, .close-button, .btn-close, [class*="close"]');
                        
                        // Thử nhấp vào nút đóng nếu tìm thấy
                        if (closeButtons.length > 0) {
                            for (let btn of closeButtons) {
                                if (btn.offsetParent !== null) { // Kiểm tra nút có hiển thị không
                                    btn.click();
                                    closed++;
                                    break;
                                }
                            }
                        } else {
                            // Nếu không tìm thấy nút đóng, ẩn popup
                            popup.style.display = 'none';
                            closed++;
                        }
                    }
                });
                
                // Xóa các lớp overlay cố định trên body
                document.body.classList.remove('modal-open', 'popup-open', 'no-scroll');
                document.body.style.overflow = 'auto';
                
                // Xóa các overlay đè trên trang
                const overlays = document.querySelectorAll('.modal-backdrop, .popup-backdrop, .overlay-backdrop');
                overlays.forEach(overlay => overlay.remove());
                
                return closed;
            };
            
            return closePopups();
            """
            closed_popups = self.driver.execute_script(js_script)
            if closed_popups > 0:
                logger.info(f"Đã đóng {closed_popups} popup bằng JavaScript")
                popup_detected = True
        except Exception as e:
            logger.error(f"Lỗi khi đóng popup bằng JavaScript: {str(e)}")
            
        # Cố gắng tìm thêm các popup dựa vào cấu trúc HTML từ bachhoaxanh.com
        try:
            # Tìm các thẻ div có class chứa "cate_parent" mà đang hiện popup
            category_popup_elements = self.driver.find_elements(By.CSS_SELECTOR, ".cate_parent")
            for element in category_popup_elements:
                # Kiểm tra các thẻ div con có thuộc tính style "height" khác 0px không (đang mở)
                popup_divs = element.find_elements(By.CSS_SELECTOR, "div.overflow-hidden")
                for popup_div in popup_divs:
                    style = popup_div.get_attribute("style")
                    if style and "height: 0px" not in style:
                        # Tìm nút đóng (thẻ div có after:rotate)
                        close_buttons = element.find_elements(By.CSS_SELECTOR, "div.after\\:rotate-\\[225deg\\]")
                        if close_buttons:
                            logger.info("Đóng dropdown danh mục đang mở")
                            close_buttons[0].click()
                            popup_detected = True
                            time.sleep(0.3)
        except Exception as e:
            logger.error(f"Lỗi khi đóng popup danh mục: {str(e)}")
            
        if not popup_detected:
            logger.info("Không phát hiện popup nào trên trang")
            
        return popup_detected
    
    def crawl_product_list(self, category: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Crawl danh sách sản phẩm từ một danh mục
        
        Args:
            category: Dictionary chứa thông tin danh mục
            
        Returns:
            List[Dict[str, Any]]: Danh sách sản phẩm
        """
        category_name = category['category_name']
        category_url = category['category_url']
        
        logger.info(f"Crawl danh sách sản phẩm từ danh mục: {category_name} ({category_url})")
        
        products = []
        
        try:
            # Truy cập trang danh mục
            self.driver.get(category_url)
            self.wait_for_page_load()
            
            # Đóng các popup sau khi trang đã tải xong
            popup_detected = self.close_popups()
            if popup_detected:
                logger.info("Đã đóng popup, tiếp tục crawl")
            else:
                logger.info("Không có popup, tiến hành crawl ngay")
            
            # Scroll trang để tải tất cả sản phẩm (nếu có lazy load)
            self.scroll_page_slowly()
            
            # Lấy HTML và phân tích
            html = self.driver.page_source
            soup = BeautifulSoup(html, 'html.parser')
            
            # Tìm tất cả sản phẩm
            product_elements = soup.select(PRODUCT_CSS_SELECTOR)
            
            if not product_elements:
                logger.warning(f"Không tìm thấy sản phẩm nào trong danh mục {category_name} với selector {PRODUCT_CSS_SELECTOR}")
                return []
            
            logger.info(f"Đã tìm thấy {len(product_elements)} sản phẩm trong danh mục {category_name}")
            
            # Trích xuất thông tin từ mỗi sản phẩm
            for element in product_elements:
                try:
                    # Lấy tên sản phẩm
                    name_element = element.select_one(".product_name, h3, .name, .title")
                    
                    # Lấy giá sản phẩm
                    price_element = element.select_one(".product_price, .price, .current-price")
                    
                    # Lấy URL sản phẩm
                    product_url = ""
                    link_element = element.select_one("a")
                    if link_element:
                        product_url = link_element.get('href', '')
                        if product_url and not product_url.startswith('http'):
                            if product_url.startswith('/'):
                                product_url = BASE_URL + product_url.lstrip('/')
                            else:
                                product_url = BASE_URL + product_url
                    
                    # Lấy URL hình ảnh
                    img_element = element.select_one("img")
                    img_url = ""
                    if img_element:
                        img_url = img_element.get('src', '') or img_element.get('data-src', '')
                    
                    # Chỉ thêm vào danh sách nếu có đủ thông tin cần thiết và chưa thấy trước đó
                    if name_element and price_element and product_url and product_url not in self.seen_urls:
                        product = {
                            'name': name_element.get_text(strip=True),
                            'price': price_element.get_text(strip=True) if price_element else "",
                            'category': category_name,
                            'product_url': product_url,
                            'img_url': img_url
                        }
                        products.append(product)
                        self.seen_urls.add(product_url)  # Đánh dấu URL này đã thấy
                except Exception as e:
                    logger.error(f"Lỗi khi xử lý một sản phẩm: {e}")
            
            return products
            
        except Exception as e:
            logger.error(f"Lỗi khi crawl danh sách sản phẩm từ {category_name}: {e}")
            return []
    
    def save_products_to_csv(self, products: List[Dict[str, Any]], append: bool = True):
        """
        Lưu danh sách sản phẩm vào file CSV
        
        Args:
            products: Danh sách sản phẩm
            append: Nếu True, sẽ thêm vào file hiện có
        """
        if not products:
            logger.warning("Không có sản phẩm để lưu")
            return
        
        mode = 'a' if append and os.path.exists(self.output_file) else 'w'
        
        try:
            # Xác định các trường dữ liệu
            fieldnames = ['name', 'price', 'category', 'product_url', 'img_url']
            
            # Ghi dữ liệu vào file CSV
            with open(self.output_file, mode, encoding='utf-8', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                
                # Nếu là file mới hoặc file không tồn tại, viết header
                if mode == 'w':
                    writer.writeheader()
                
                writer.writerows(products)
                
            logger.info(f"Đã lưu {len(products)} sản phẩm vào {self.output_file}")
        except Exception as e:
            logger.error(f"Lỗi khi lưu sản phẩm vào file CSV: {e}")
    
    def run_from_categories(self, categories: List[Dict[str, Any]]):
        """
        Chạy crawler cho một danh sách danh mục
        
        Args:
            categories: Danh sách các danh mục
        """
        if not self.driver:
            self.setup_driver()
        
        self.seen_urls = self.load_seen_urls()
        
        try:
            # Các danh mục đã được tải từ file
            if not categories:
                logger.error("Không có danh mục để crawl")
                return
                
            all_products = []
            
            # Crawl từng danh mục
            for category in categories:
                category_products = self.crawl_product_list(category)
                
                # Thêm sản phẩm vào danh sách tổng và lưu ngay để tránh mất dữ liệu
                if category_products:
                    all_products.extend(category_products)
                    self.save_products_to_csv(category_products)
                
                # Crawl danh mục con nếu có
                if 'subcategories' in category and category['subcategories']:
                    for subcategory in category['subcategories']:
                        # Chuyển đổi cấu trúc danh mục con để phù hợp với hàm crawl_product_list
                        sub_cat = {
                            'category_name': subcategory['subcategory_name'],
                            'category_url': subcategory['subcategory_url']
                        }
                        subcategory_products = self.crawl_product_list(sub_cat)
                        
                        # Thêm sản phẩm vào danh sách tổng và lưu ngay
                        if subcategory_products:
                            all_products.extend(subcategory_products)
                            self.save_products_to_csv(subcategory_products)
                        
                        # Chờ giữa các request
                        time.sleep(CRAWL_DELAY)
                
                # Chờ giữa các request
                time.sleep(CRAWL_DELAY)
            
            logger.info(f"Đã crawl tổng cộng {len(all_products)} sản phẩm từ {len(categories)} danh mục")
            
        except Exception as e:
            logger.error(f"Lỗi khi chạy crawler: {e}")
        finally:
            self.close_driver()
    
    def run(self):
        """Hàm chính để chạy crawler"""
        categories = self.load_categories()
        self.run_from_categories(categories)

def main():
    """Hàm main để chạy từ dòng lệnh"""
    parser = argparse.ArgumentParser(description="Crawler danh sách sản phẩm từ danh mục")
    parser.add_argument("--category-file", type=str, default="categories.json",
                      help="File chứa danh sách danh mục (mặc định: categories.json)")
    parser.add_argument("--output", type=str, default="product_list.csv",
                      help="File đầu ra cho danh sách sản phẩm (mặc định: product_list.csv)")
    args = parser.parse_args()
    
    crawler = ProductListCrawler(
        category_file=args.category_file,
        output_file=args.output
    )
    crawler.run()

if __name__ == "__main__":
    main() 