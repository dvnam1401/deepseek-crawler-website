#!/usr/bin/env python3
"""
Crawler cho danh mục và danh mục con
"""
import os
import json
import time
import logging
import argparse
from typing import List, Dict, Any
from bs4 import BeautifulSoup
import requests
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

from config import (
    BASE_URL, 
    CATEGORY_CSS_SELECTOR, 
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
        logging.FileHandler("category_crawler.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

class CategoryCrawler:
    """Crawler chuyên biệt cho việc crawl danh mục"""
    
    def __init__(self, output_file: str = "categories.json"):
        """
        Khởi tạo CategoryCrawler
        
        Args:
            output_file: Tên file đầu ra để lưu danh mục
        """
        self.output_file = os.path.join(OUTPUT_DIR, output_file)
        self.driver = None
        
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
            logger.info("Trang đã tải xong")
            return True
        except TimeoutException as e:
            logger.error(f"Timeout khi đợi trang tải: {e}")
            return False
        except Exception as e:
            logger.error(f"Lỗi khi đợi trang tải: {e}")
            return False
    
    # def close_popups(self):
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
    
    def crawl_categories(self) -> List[Dict[str, Any]]:
        """
        Crawl danh sách các danh mục từ trang chủ
        
        Returns:
            List[Dict[str, Any]]: Danh sách các danh mục
        """
        if not self.driver:
            self.setup_driver()
        
        logger.info(f"Bắt đầu crawl danh mục từ {BASE_URL}")
        
        try:
            # Truy cập trang chủ
            self.driver.get(BASE_URL)
            self.wait_for_page_load()
            
            # Đóng các popup sau khi trang đã tải xong
            # popup_detected = self.close_popups()
            # if popup_detected:
            #     logger.info("Đã đóng popup, tiếp tục crawl")
            # else:
            #     logger.info("Không có popup, tiến hành crawl ngay")
            
            # Lấy HTML và phân tích với BeautifulSoup
            html = self.driver.page_source
            soup = BeautifulSoup(html, 'html.parser')
            
            # Tìm tất cả các phần tử danh mục
            category_elements = soup.select(CATEGORY_CSS_SELECTOR)
            
            if not category_elements:
                logger.warning(f"Không tìm thấy danh mục nào với selector {CATEGORY_CSS_SELECTOR}")
                return []
            
            categories = []
            
            # Trích xuất thông tin từ mỗi danh mục
            for element in category_elements:
                try:
                    # Lấy tên danh mục
                    category_name = element.get_text(strip=True)
                    
                    # Lấy URL (href attribute)
                    category_url = element.get('href', '')
                    if category_url and not category_url.startswith('http'):
                        if category_url.startswith('/'):
                            category_url = BASE_URL + category_url.lstrip('/')
                        else:
                            category_url = BASE_URL + category_url
                    
                    # Chỉ thêm vào danh sách nếu có cả tên và URL
                    if category_name and category_url:
                        categories.append({
                            'category_name': category_name,
                            'category_url': category_url,
                            'subcategories': []  # Sẽ chứa danh mục con (nếu có)
                        })
                except Exception as e:
                    logger.error(f"Lỗi khi xử lý một danh mục: {e}")
            
            logger.info(f"Đã tìm thấy {len(categories)} danh mục")
            
            # Đối với mỗi danh mục, crawl danh mục con nếu có
            for category in categories:
                self.crawl_subcategories(category)
                # Chờ một chút giữa các request để tránh bị chặn
                time.sleep(CRAWL_DELAY)
            
            logger.info("Hoàn thành việc crawl danh mục và danh mục con")
            return categories
            
        except Exception as e:
            logger.error(f"Lỗi khi crawl danh mục: {e}")
            return []
        finally:
            self.close_driver()
    
    def crawl_subcategories(self, category: Dict[str, Any]):
        """
        Crawl danh mục con cho một danh mục cụ thể
        
        Args:
            category: Dictionary chứa thông tin danh mục
        """
        category_url = category['category_url']
        category_name = category['category_name']
        
        logger.info(f"Đang tìm danh mục con cho {category_name} tại {category_url}")
        
        try:
            # Truy cập trang danh mục
            self.driver.get(category_url)
            self.wait_for_page_load()
            
            # Đóng các popup sau khi trang đã tải xong
            # popup_detected = self.close_popups()
            # if popup_detected:
            #     logger.info("Đã đóng popup, tiếp tục crawl")
            # else:
            #     logger.info("Không có popup, tiến hành crawl ngay")
            
            # Lấy HTML và phân tích
            html = self.driver.page_source
            soup = BeautifulSoup(html, 'html.parser')
            
            # Tìm các danh mục con - thường nằm trong một menu hoặc sidebar
            # (Selector này cần điều chỉnh theo cấu trúc thực tế của trang web)
            subcategory_selectors = [
                ".subcategory", 
                ".subcategories .item",
                ".sidebar-categories .item",
                ".category-menu .subcategory"
            ]
            
            subcategories = []
            
            # Thử từng selector cho đến khi tìm thấy danh mục con
            for selector in subcategory_selectors:
                subcategory_elements = soup.select(selector)
                if subcategory_elements:
                    for element in subcategory_elements:
                        try:
                            # Lấy tên danh mục con
                            subcategory_name = element.get_text(strip=True)
                            
                            # Lấy URL
                            subcategory_url = element.get('href', '')
                            if subcategory_url and not subcategory_url.startswith('http'):
                                if subcategory_url.startswith('/'):
                                    subcategory_url = BASE_URL + subcategory_url.lstrip('/')
                                else:
                                    subcategory_url = BASE_URL + subcategory_url
                            
                            # Thêm vào danh sách nếu có cả tên và URL
                            if subcategory_name and subcategory_url:
                                subcategories.append({
                                    'subcategory_name': subcategory_name,
                                    'subcategory_url': subcategory_url
                                })
                        except Exception as e:
                            logger.error(f"Lỗi khi xử lý một danh mục con: {e}")
                    
                    # Nếu đã tìm thấy danh mục con với selector này, thoát khỏi vòng lặp
                    break
            
            # Cập nhật danh mục con cho danh mục hiện tại
            category['subcategories'] = subcategories
            logger.info(f"Đã tìm thấy {len(subcategories)} danh mục con cho {category_name}")
            
        except Exception as e:
            logger.error(f"Lỗi khi crawl danh mục con cho {category_name}: {e}")
    
    def save_categories(self, categories: List[Dict[str, Any]]):
        """
        Lưu danh sách danh mục vào file
        
        Args:
            categories: Danh sách các danh mục
        """
        if not categories:
            logger.warning("Không có danh mục để lưu")
            return
        
        try:
            with open(self.output_file, 'w', encoding='utf-8') as f:
                json.dump(categories, f, ensure_ascii=False, indent=4)
            logger.info(f"Đã lưu {len(categories)} danh mục vào {self.output_file}")
        except Exception as e:
            logger.error(f"Lỗi khi lưu danh mục vào file: {e}")
    
    def run(self):
        """Hàm chính để chạy crawler"""
        categories = self.crawl_categories()
        self.save_categories(categories)
        return categories

def main():
    """Hàm main để chạy từ dòng lệnh"""
    parser = argparse.ArgumentParser(description="Crawler danh mục và danh mục con")
    parser.add_argument("--output", type=str, default="categories.json",
                       help="Tên file đầu ra (mặc định: categories.json)")
    args = parser.parse_args()
    
    crawler = CategoryCrawler(output_file=args.output)
    crawler.run()

if __name__ == "__main__":
    main() 