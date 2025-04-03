import logging
import time
import asyncio
import json
from typing import Dict, List, Any, Optional, Set

import requests
from bs4 import BeautifulSoup
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, StaleElementReferenceException, NoSuchElementException
from crawl4ai import AsyncWebCrawler, CrawlerRunConfig, CacheMode

from config import WAIT_TIME, MAX_RETRIES
from utils.scraper_utils import (
    get_browser_config,
    get_llm_strategy_for_categories,
    get_llm_strategy_for_products,
    fetch_categories,
    fetch_and_process_product_page,
)

class WebCrawler:
    def __init__(self):
        self.driver = None
        self.logger = logging.getLogger(__name__)
    
    def setup_driver(self):
        """Thiết lập driver với các options để tránh phát hiện"""
        options = uc.ChromeOptions()
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        
        self.driver = uc.Chrome(options=options)
        return self.driver
    
    def close_driver(self):
        """Đóng driver sau khi hoàn thành"""
        if self.driver:
            self.driver.quit()
            self.driver = None
            
    def scroll_page_slowly(self, max_scroll_time=20):
        """Scroll trang chậm để tải nội dung lazy load"""
        if not self.driver:
            self.logger.error("Driver chưa được khởi tạo")
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
        self.logger.info("Finished scrolling page.")
        
    def wait_for_page_load(self, timeout=WAIT_TIME, selector="body"):
        """Đợi trang tải xong với timeout và selector tùy chỉnh"""
        if not self.driver:
            self.logger.error("Driver chưa được khởi tạo")
            return False
            
        try:
            WebDriverWait(self.driver, timeout).until(
                lambda driver: driver.execute_script("return document.readyState") == "complete"
            )
            WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, selector))
            )
            # Thêm thời gian chờ để đảm bảo AJAX load xong
            time.sleep(3)
            self.logger.info(f"Page loaded successfully with elements matching '{selector}'.")
            return True
        except TimeoutException:
            self.logger.warning(f"Timeout waiting for page load or elements '{selector}' after {timeout} seconds.")
            return False

    def close_popups(self):
        """Đóng các popup và thông báo trên trang web
        
        Returns:
            bool: True nếu đã phát hiện và xử lý popup, False nếu không có popup
        """
        if not self.driver:
            self.logger.error("Driver chưa được khởi tạo")
            return False
            
        popup_detected = False
        self.logger.info("Đang kiểm tra có thông báo popup không...")
        
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
                            self.logger.info(f"Đang đóng popup ({popup_type}) với selector: {selector}")
                            element.click()
                            popup_detected = True
                            time.sleep(0.5)  # Chờ animation đóng popup
                except Exception as e:
                    self.logger.debug(f"Không tìm thấy popup với selector {selector}: {str(e)}")

        # Thử đóng popup bằng cách tìm nút có chứa text đóng
        close_texts = ["Đóng", "Close", "Skip", "Bỏ qua", "X", "×", "Không, cảm ơn", "No, thanks", "Để sau"]
        for text in close_texts:
            try:
                xpath = f"//button[contains(text(),'{text}')] | //a[contains(text(),'{text}')] | //*[contains(@class,'close') and contains(text(),'{text}')]"
                elements = self.driver.find_elements(By.XPATH, xpath)
                for element in elements:
                    if element.is_displayed():
                        self.logger.info(f"Đang đóng popup với text: {text}")
                        element.click()
                        popup_detected = True
                        time.sleep(0.5)
            except Exception as e:
                self.logger.debug(f"Không tìm thấy nút đóng với text {text}: {str(e)}")

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
                self.logger.info(f"Đã đóng {closed_popups} popup bằng JavaScript")
                popup_detected = True
        except Exception as e:
            self.logger.error(f"Lỗi khi đóng popup bằng JavaScript: {str(e)}")
            
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
                            self.logger.info("Đóng dropdown danh mục đang mở")
                            close_buttons[0].click()
                            popup_detected = True
                            time.sleep(0.3)
        except Exception as e:
            self.logger.error(f"Lỗi khi đóng popup danh mục: {str(e)}")
            
        if not popup_detected:
            self.logger.info("Không phát hiện popup nào trên trang")
            
        return popup_detected

    def get_page_content(self, url, selector=None, retry=3, delay=2):
        """Lấy nội dung trang web với cơ chế thử lại"""
        if not self.driver:
            self.setup_driver()
            
        for attempt in range(retry):
            try:
                self.driver.get(url)
                
                # Đợi trang load xong
                if selector:
                    loaded = self.wait_for_page_load(selector=selector)
                    if not loaded:
                        continue
                else:
                    loaded = self.wait_for_page_load()
                    if not loaded:
                        continue
                
                # Đóng các popup sau khi trang đã load
                popup_detected = self.close_popups()
                if popup_detected:
                    self.logger.info("Đã đóng popup, tiếp tục crawl")
                else:
                    self.logger.info("Không có popup, tiến hành crawl ngay")
                
                # Scroll để tải nội dung lazy load
                self.scroll_page_slowly()
                
                return BeautifulSoup(self.driver.page_source, 'html.parser')
            except Exception as e:
                self.logger.error(f"Lỗi khi lấy nội dung trang {url}, lần thử {attempt+1}: {str(e)}")
                if attempt < retry - 1:
                    time.sleep(delay)
        
        self.logger.error(f"Không thể lấy nội dung trang {url} sau {retry} lần thử")
        return None

    def extract_page_data(self, soup, selectors):
        """Trích xuất dữ liệu từ trang dựa trên các selector"""
        results = {}
        
        for key, selector_list in selectors.items():
            for selector in selector_list:
                elements = soup.select(selector)
                if elements:
                    if key == "description":
                        results[key] = "\n".join([elem.get_text(strip=True) for elem in elements])
                    else:
                        results[key] = elements[0].get_text(strip=True)
                    break
        
        return results
        
    def extract_links(self, soup, selector, base_url=""):
        """Trích xuất các liên kết từ trang"""
        links = []
        for link in soup.select(selector):
            href = link.get('href')
            if href:
                if href.startswith('/'):
                    href = base_url.rstrip('/') + href
                links.append(href)
        return links


class AsyncCrawler:
    """Lớp crawler bất đồng bộ sử dụng thư viện asyncio và crawl4ai"""
    
    def __init__(self):
        self.browser_config = get_browser_config()
        self.logger = logging.getLogger(__name__)
        
    async def setup_crawler(self):
        """Thiết lập crawler bất đồng bộ"""
        return AsyncWebCrawler(config=self.browser_config)
        
    async def fetch_product_details(
        self,
        crawler: AsyncWebCrawler,
        url: str,
        category: str,
        session_id: str,
        llm_strategy,
        max_retries: int = 3,
        retry_delay: float = 5.0,
    ) -> dict:
        """Lấy chi tiết sản phẩm từ URL"""
        for attempt in range(max_retries):
            result = await crawler.arun(
                url=url,
                config=CrawlerRunConfig(
                    cache_mode=CacheMode.BYPASS,
                    extraction_strategy=llm_strategy,
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
                self.logger.info(f"Extracted details for {product['name']}")
                return product
            await asyncio.sleep(retry_delay)
        self.logger.error(f"Failed to fetch details for {url} after {max_retries} attempts")
        return {} 