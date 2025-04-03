#!/usr/bin/env python3
"""
Crawler cho chi tiết sản phẩm từ danh sách sản phẩm đã có
"""
import os
import json
import time
import csv
import logging
import argparse
from typing import List, Dict, Any, Set
from bs4 import BeautifulSoup
import requests
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

from config import (
    BASE_URL, 
    SELECTORS,
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
        logging.FileHandler("product_details_crawler.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

class ProductDetailsCrawler:
    """Crawler chuyên biệt cho việc crawl chi tiết sản phẩm"""
    
    def __init__(self, 
                product_list_file: str = "product_list.csv",
                output_file: str = "product_details.json",
                download_images: bool = True):
        """
        Khởi tạo ProductDetailsCrawler
        
        Args:
            product_list_file: Tên file chứa danh sách sản phẩm
            output_file: Tên file đầu ra để lưu chi tiết sản phẩm
            download_images: Tải xuống hình ảnh sản phẩm hay không
        """
        self.product_list_file = os.path.join(OUTPUT_DIR, product_list_file)
        self.output_file = os.path.join(OUTPUT_DIR, output_file)
        self.download_images = download_images
        self.image_dir = os.path.join(OUTPUT_DIR, "images")
        self.driver = None
        self.processed_urls = set()  # Các URL đã xử lý
        
        # Đảm bảo thư mục đầu ra tồn tại
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        if download_images:
            os.makedirs(self.image_dir, exist_ok=True)
    
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
    
    def load_product_list(self) -> List[Dict[str, Any]]:
        """
        Tải danh sách sản phẩm từ file CSV
        
        Returns:
            List[Dict[str, Any]]: Danh sách sản phẩm
        """
        products = []
        
        try:
            if not os.path.exists(self.product_list_file):
                logger.error(f"File danh sách sản phẩm {self.product_list_file} không tồn tại")
                return []
                
            with open(self.product_list_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    products.append(dict(row))
                    
            logger.info(f"Đã tải {len(products)} sản phẩm từ {self.product_list_file}")
            return products
        except Exception as e:
            logger.error(f"Lỗi khi tải danh sách sản phẩm: {e}")
            return []
    
    def load_processed_urls(self) -> Set[str]:
        """
        Tải danh sách URL sản phẩm đã xử lý từ file đầu ra (nếu có)
        
        Returns:
            Set[str]: Tập hợp các URL đã xử lý
        """
        processed_urls = set()
        
        try:
            if os.path.exists(self.output_file):
                with open(self.output_file, 'r', encoding='utf-8') as f:
                    existing_data = json.load(f)
                    for product in existing_data:
                        if 'product_url' in product:
                            processed_urls.add(product['product_url'])
                            
                logger.info(f"Đã tải {len(processed_urls)} URL sản phẩm đã xử lý từ {self.output_file}")
        except Exception as e:
            logger.error(f"Lỗi khi tải URL đã xử lý: {e}")
        
        return processed_urls
    
    def crawl_product_details(self, product: Dict[str, Any]) -> Dict[str, Any]:
        """
        Crawl chi tiết sản phẩm từ URL
        
        Args:
            product: Thông tin cơ bản về sản phẩm
            
        Returns:
            Dict[str, Any]: Chi tiết sản phẩm
        """
        product_url = product['product_url']
        product_name = product['name']
        
        logger.info(f"Đang crawl chi tiết sản phẩm: {product_name} ({product_url})")
        
        # Tạo một bản sao của sản phẩm để thêm thông tin chi tiết
        product_details = dict(product)
        
        try:
            # Truy cập trang sản phẩm
            self.driver.get(product_url)
            self.wait_for_page_load()
            
            # Đóng các popup sau khi trang đã tải xong
            popup_detected = self.close_popups()
            if popup_detected:
                logger.info("Đã đóng popup, tiếp tục crawl")
            else:
                logger.info("Không có popup, tiến hành crawl ngay")
            
            # Lấy HTML và phân tích
            html = self.driver.page_source
            soup = BeautifulSoup(html, 'html.parser')
            
            # Trích xuất thông tin chi tiết sử dụng các selectors trong config
            for key, selector_list in SELECTORS.items():
                # Bỏ qua các trường đã có trong thông tin cơ bản
                if key in product_details and product_details[key]:
                    continue
                
                # Thử lần lượt các selector cho đến khi tìm thấy thông tin
                for selector in selector_list:
                    elements = soup.select(selector)
                    if elements:
                        if key == "description":
                            # Đối với mô tả, kết hợp văn bản từ nhiều phần tử
                            product_details[key] = "\n".join([elem.get_text(strip=True) for elem in elements])
                        else:
                            # Đối với các trường khác, lấy văn bản từ phần tử đầu tiên
                            product_details[key] = elements[0].get_text(strip=True)
                        break
            
            # Trích xuất các thông số kỹ thuật từ bảng (nếu có)
            specs_table = {}
            table_selectors = ["table.specifications", "table.product-specs", ".product-attributes table"]
            
            for table_selector in table_selectors:
                tables = soup.select(table_selector)
                if tables:
                    for table in tables:
                        rows = table.select("tr")
                        for row in rows:
                            cells = row.select("td, th")
                            if len(cells) >= 2:
                                key = cells[0].get_text(strip=True)
                                value = cells[1].get_text(strip=True)
                                if key:
                                    specs_table[key] = value
                    
                    # Nếu đã tìm thấy bảng thông số, thoát khỏi vòng lặp
                    if specs_table:
                        break
            
            # Nếu không tìm thấy bảng, thử các phương pháp khác
            if not specs_table:
                # Thử tìm trong các cặp div
                spec_rows = soup.select(".product-specs .row, .specifications .item")
                for row in spec_rows:
                    key_elem = row.select_one(".spec-name, .label")
                    value_elem = row.select_one(".spec-value, .value")
                    if key_elem and value_elem:
                        key = key_elem.get_text(strip=True)
                        value = value_elem.get_text(strip=True)
                        if key:
                            specs_table[key] = value
            
            # Thêm thông số kỹ thuật vào chi tiết sản phẩm
            if specs_table:
                product_details['specifications'] = specs_table
            
            # Trích xuất các URL hình ảnh
            image_urls = self.extract_image_urls(soup)
            if image_urls:
                product_details['image_urls'] = image_urls
                
                # Tải xuống hình ảnh nếu được yêu cầu
                if self.download_images:
                    downloaded_images = self.download_product_images(image_urls, product_name)
                    if downloaded_images:
                        product_details['local_images'] = downloaded_images
            
            # Trích xuất đánh giá và bình luận (nếu có)
            reviews = self.extract_reviews(soup)
            if reviews:
                product_details['reviews'] = reviews
                
            return product_details
            
        except Exception as e:
            logger.error(f"Lỗi khi crawl chi tiết sản phẩm {product_name}: {e}")
            return product_details  # Trả về thông tin cơ bản nếu có lỗi
    
    def extract_image_urls(self, soup: BeautifulSoup) -> List[str]:
        """
        Trích xuất các URL hình ảnh từ trang sản phẩm
        
        Args:
            soup: Đối tượng BeautifulSoup của trang
            
        Returns:
            List[str]: Danh sách các URL hình ảnh
        """
        image_urls = []
        
        # Thử các selector khác nhau để tìm hình ảnh
        image_selectors = [
            ".product-image-gallery img",
            ".product-images img",
            ".gallery img",
            ".product-gallery img",
            ".swiper-slide img"
        ]
        
        for selector in image_selectors:
            try:
                images = soup.select(selector)
                for img in images:
                    # Lấy URL hình ảnh từ các thuộc tính khác nhau
                    src = img.get('src') or img.get('data-src') or img.get('data-lazy-src')
                    if src and src not in image_urls and "placeholder" not in src:
                        # Loại bỏ query params trong URL hình ảnh
                        src = src.split('?')[0]
                        image_urls.append(src)
            except Exception as e:
                logger.error(f"Lỗi khi trích xuất URL hình ảnh với selector {selector}: {e}")
        
        # Nếu không tìm thấy hình ảnh, thử tìm tất cả thẻ img
        if not image_urls:
            try:
                all_images = soup.select("img")
                for img in all_images:
                    src = img.get('src') or img.get('data-src') or img.get('data-lazy-src')
                    if src and src not in image_urls and "placeholder" not in src and "logo" not in src:
                        src = src.split('?')[0]
                        image_urls.append(src)
            except Exception as e:
                logger.error(f"Lỗi khi trích xuất tất cả URL hình ảnh: {e}")
        
        return image_urls
    
    def download_product_images(self, image_urls: List[str], product_name: str) -> List[str]:
        """
        Tải xuống hình ảnh sản phẩm
        
        Args:
            image_urls: Danh sách URL hình ảnh
            product_name: Tên sản phẩm
            
        Returns:
            List[str]: Danh sách đường dẫn đến các file hình ảnh đã tải
        """
        downloaded_images = []
        
        # Tạo tên file an toàn từ tên sản phẩm
        safe_name = ''.join(c if c.isalnum() or c in ' _-' else '_' for c in product_name)
        safe_name = safe_name.replace(' ', '_')[:50]  # Giới hạn độ dài
        
        for i, img_url in enumerate(image_urls):
            try:
                # Xác định phần mở rộng của file
                if '.' in img_url.split('/')[-1]:
                    ext = img_url.split('.')[-1].split('?')[0].lower()
                    if ext not in ['jpg', 'jpeg', 'png', 'gif', 'webp']:
                        ext = 'jpg'  # Mặc định nếu không xác định được
                else:
                    ext = 'jpg'
                
                # Tạo tên file cho hình ảnh
                img_filename = f"{safe_name}_{i+1}.{ext}"
                img_path = os.path.join(self.image_dir, img_filename)
                
                # Tải và lưu hình ảnh
                headers = {'User-Agent': USER_AGENT}
                response = requests.get(img_url, headers=headers, stream=True, timeout=10)
                
                if response.status_code == 200:
                    with open(img_path, 'wb') as f:
                        for chunk in response.iter_content(1024):
                            f.write(chunk)
                    
                    downloaded_images.append(img_path)
                    logger.info(f"Đã tải hình ảnh: {img_path}")
                else:
                    logger.warning(f"Không thể tải hình ảnh từ {img_url}: HTTP {response.status_code}")
            except Exception as e:
                logger.error(f"Lỗi khi tải hình ảnh từ {img_url}: {e}")
        
        return downloaded_images
    
    def extract_reviews(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """
        Trích xuất đánh giá và bình luận từ trang sản phẩm
        
        Args:
            soup: Đối tượng BeautifulSoup của trang
            
        Returns:
            List[Dict[str, Any]]: Danh sách các đánh giá
        """
        reviews = []
        
        # Thử các selector khác nhau để tìm đánh giá
        review_selectors = [
            ".product-reviews .review",
            ".reviews-list .review",
            "#reviews .review",
            ".comment-list .comment"
        ]
        
        for selector in review_selectors:
            try:
                review_elements = soup.select(selector)
                if review_elements:
                    for element in review_elements:
                        # Trích xuất thông tin người đánh giá
                        author_element = element.select_one(".author, .name, .user")
                        
                        # Trích xuất điểm đánh giá
                        rating_element = element.select_one(".rating, .stars")
                        
                        # Trích xuất nội dung đánh giá
                        content_element = element.select_one(".content, .text, .description")
                        
                        # Tạo đối tượng đánh giá
                        review = {}
                        
                        if author_element:
                            review['author'] = author_element.get_text(strip=True)
                        
                        if rating_element:
                            # Thử trích xuất số sao từ văn bản hoặc thuộc tính
                            rating_text = rating_element.get_text(strip=True)
                            rating_value = None
                            
                            # Thử tìm số (1-5) trong văn bản
                            import re
                            rating_match = re.search(r'(\d+(\.\d+)?)', rating_text)
                            if rating_match:
                                rating_value = float(rating_match.group(1))
                            
                            # Hoặc thử tìm từ thuộc tính
                            if not rating_value and rating_element.has_attr('data-rating'):
                                rating_value = float(rating_element['data-rating'])
                            
                            if rating_value:
                                review['rating'] = rating_value
                        
                        if content_element:
                            review['content'] = content_element.get_text(strip=True)
                        
                        # Thêm vào danh sách nếu có nội dung
                        if 'content' in review or 'rating' in review:
                            reviews.append(review)
                    
                    # Nếu đã tìm thấy đánh giá, thoát khỏi vòng lặp
                    if reviews:
                        break
            except Exception as e:
                logger.error(f"Lỗi khi trích xuất đánh giá với selector {selector}: {e}")
        
        return reviews
    
    def save_products_json(self, products: List[Dict[str, Any]], append: bool = True):
        """
        Lưu chi tiết sản phẩm vào file JSON
        
        Args:
            products: Danh sách chi tiết sản phẩm
            append: Nếu True, sẽ thêm vào file hiện có
        """
        if not products:
            logger.warning("Không có chi tiết sản phẩm để lưu")
            return
        
        existing_data = []
        
        # Nếu cần thêm vào file hiện có và file đã tồn tại
        if append and os.path.exists(self.output_file):
            try:
                with open(self.output_file, 'r', encoding='utf-8') as f:
                    existing_data = json.load(f)
                    logger.info(f"Đã tải {len(existing_data)} sản phẩm từ file hiện có")
            except Exception as e:
                logger.error(f"Lỗi khi tải dữ liệu hiện có: {e}")
        
        # Gộp dữ liệu hiện có và dữ liệu mới
        all_data = existing_data + products
        
        try:
            with open(self.output_file, 'w', encoding='utf-8') as f:
                json.dump(all_data, f, ensure_ascii=False, indent=4)
            logger.info(f"Đã lưu {len(all_data)} sản phẩm vào {self.output_file}")
        except Exception as e:
            logger.error(f"Lỗi khi lưu chi tiết sản phẩm: {e}")
    
    def run(self, batch_size: int = 10):
        """
        Hàm chính để chạy crawler
        
        Args:
            batch_size: Số lượng sản phẩm xử lý trước khi lưu
        """
        # Tải danh sách sản phẩm và URL đã xử lý
        product_list = self.load_product_list()
        self.processed_urls = self.load_processed_urls()
        
        if not product_list:
            logger.error("Không có sản phẩm để crawl chi tiết")
            return
        
        # Khởi tạo driver
        if not self.driver:
            self.setup_driver()
        
        try:
            # Lọc ra các sản phẩm chưa xử lý
            unprocessed_products = [p for p in product_list if p['product_url'] not in self.processed_urls]
            logger.info(f"Cần crawl chi tiết cho {len(unprocessed_products)}/{len(product_list)} sản phẩm")
            
            if not unprocessed_products:
                logger.info("Tất cả sản phẩm đã được xử lý")
                return
            
            # Crawl chi tiết sản phẩm theo batch
            detailed_products = []
            total_processed = 0
            
            for product in unprocessed_products:
                # Crawl chi tiết sản phẩm
                product_details = self.crawl_product_details(product)
                
                # Thêm vào danh sách và đánh dấu là đã xử lý
                detailed_products.append(product_details)
                self.processed_urls.add(product['product_url'])
                total_processed += 1
                
                # Lưu theo batch để tránh mất dữ liệu
                if len(detailed_products) >= batch_size:
                    self.save_products_json(detailed_products)
                    logger.info(f"Đã lưu batch {total_processed}/{len(unprocessed_products)} sản phẩm")
                    detailed_products = []
                
                # Chờ giữa các request để tránh bị chặn
                time.sleep(CRAWL_DELAY)
            
            # Lưu các sản phẩm còn lại
            if detailed_products:
                self.save_products_json(detailed_products)
                logger.info(f"Đã lưu batch cuối cùng, tổng cộng {total_processed}/{len(unprocessed_products)} sản phẩm")
            
            logger.info(f"Hoàn thành crawl chi tiết {total_processed} sản phẩm")
            
        except Exception as e:
            logger.error(f"Lỗi khi chạy crawler chi tiết sản phẩm: {e}")
        finally:
            self.close_driver()

def main():
    """Hàm main để chạy từ dòng lệnh"""
    parser = argparse.ArgumentParser(description="Crawler chi tiết sản phẩm")
    parser.add_argument("--product-list", type=str, default="product_list.csv",
                      help="File chứa danh sách sản phẩm (mặc định: product_list.csv)")
    parser.add_argument("--output", type=str, default="product_details.json",
                      help="File đầu ra cho chi tiết sản phẩm (mặc định: product_details.json)")
    parser.add_argument("--download-images", action="store_true",
                      help="Tải xuống hình ảnh sản phẩm")
    parser.add_argument("--batch-size", type=int, default=10,
                      help="Số lượng sản phẩm xử lý trước khi lưu (mặc định: 10)")
    args = parser.parse_args()
    
    crawler = ProductDetailsCrawler(
        product_list_file=args.product_list,
        output_file=args.output,
        download_images=args.download_images
    )
    crawler.run(batch_size=args.batch_size)

if __name__ == "__main__":
    main() 