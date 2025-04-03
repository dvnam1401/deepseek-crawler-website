#!/usr/bin/env python3
import os
import json
import time
import logging
import argparse
from typing import List, Dict, Any
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright, Page, Browser

from config_playwright import (
    BASE_URL,
    CATEGORY_CSS_SELECTOR,
    SUBCATEGORY_SELECTORS,
    OUTPUT_DIR,
    WAIT_TIME,
    MAX_RETRIES,
    CRAWL_DELAY,
    BROWSER_CONFIG
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("category_crawler_playwright.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

class PlaywrightCategoryCrawler:
    def __init__(self, output_file: str = "categories_playwright.json"):
        self.output_file = os.path.join(OUTPUT_DIR, output_file)
        self.browser = None
        self.page = None
        self.playwright = None
        
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        os.makedirs(os.path.join(OUTPUT_DIR, "screenshots"), exist_ok=True)
    
    def setup_browser(self):
        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch(
            headless=BROWSER_CONFIG["headless"]
        )
        self.page = self.browser.new_page(
            viewport=BROWSER_CONFIG["viewport"],
            user_agent=BROWSER_CONFIG["user_agent"]
        )
        return self.page
    
    def close_browser(self):
        if self.browser:
            self.browser.close()
            self.browser = None
        if self.playwright:
            self.playwright.stop()
            self.playwright = None
    
    def wait_for_page_load(self, timeout: int = WAIT_TIME):
        try:
            self.page.wait_for_load_state("networkidle", timeout=timeout * 1000)
            self.page.wait_for_load_state("domcontentloaded", timeout=timeout * 1000)
            self.page.wait_for_selector("body", timeout=timeout * 1000)
            logger.info("Trang đã tải xong")
            return True
        except Exception as e:
            logger.error(f"Lỗi khi đợi trang tải: {e}")
            return False
    
    def take_snapshot(self, name: str = "homepage"):
        """Chụp ảnh và lưu HTML của trang hiện tại"""
        try:
            # Chụp ảnh màn hình
            screenshot_path = os.path.join(OUTPUT_DIR, "screenshots", f"{name}.png")
            self.page.screenshot(path=screenshot_path, full_page=True)
            logger.info(f"Đã chụp ảnh màn hình: {screenshot_path}")
            
            # Lưu HTML
            html_path = os.path.join(OUTPUT_DIR, "screenshots", f"{name}.html")
            with open(html_path, "w", encoding="utf-8") as f:
                f.write(self.page.content())
            logger.info(f"Đã lưu HTML: {html_path}")
            
            # Lưu thông tin về các selector
            selectors_info = {}
            
            # Kiểm tra selector danh mục chính
            category_elements = self.page.query_selector_all(CATEGORY_CSS_SELECTOR)
            selectors_info["main_category"] = {
                "selector": CATEGORY_CSS_SELECTOR,
                "count": len(category_elements),
                "text": [elem.text_content().strip() for elem in category_elements[:5]]
            }
            
            # Kiểm tra các selector danh mục con
            for selector in SUBCATEGORY_SELECTORS:
                subcategory_elements = self.page.query_selector_all(selector)
                selectors_info[selector] = {
                    "count": len(subcategory_elements),
                    "text": [elem.text_content().strip() for elem in subcategory_elements[:3]]
                }
            
            # Lưu thông tin selector
            selector_path = os.path.join(OUTPUT_DIR, "screenshots", f"{name}_selectors.json")
            with open(selector_path, "w", encoding="utf-8") as f:
                json.dump(selectors_info, f, ensure_ascii=False, indent=4)
            logger.info(f"Đã lưu thông tin selector: {selector_path}")
            
            return True
        except Exception as e:
            logger.error(f"Lỗi khi chụp ảnh và lưu HTML: {e}")
            return False
    
    def detect_categories(self):
        """Phát hiện danh mục bằng cách thử các selector khác nhau"""
        possible_selectors = [
            ".cate_parent .text-14.font-semibold.uppercase",
            ".flex.cursor-pointer .text-14.font-semibold.uppercase",
            "span.text-14.font-semibold.uppercase"
        ]
        
        for selector in possible_selectors:
            elements = self.page.query_selector_all(selector)
            if elements:
                logger.info(f"Đã tìm thấy {len(elements)} phần tử với selector: {selector}")
                logger.info(f"Một số phần tử đầu tiên: {[e.text_content().strip() for e in elements[:3]]}")
        
        # Tìm tất cả danh mục chính
        category_elements = self.page.query_selector_all(CATEGORY_CSS_SELECTOR)
        logger.info(f"Tổng số danh mục chính: {len(category_elements)}")
        
        category_links = []
        
        for element in category_elements:
            try:
                category_name = element.text_content().strip()
                if not category_name:
                    continue
                    
                # Tạo URL cho danh mục (trong trường hợp này, chỉ lưu tên danh mục vì không có URL trực tiếp)
                # Trong thực tế, chúng ta sẽ cần trích xuất URL hoặc tạo URL dựa trên tên danh mục
                category_url = BASE_URL  # URL giả, sẽ được điều chỉnh sau
                
                category_links.append({
                    "text": category_name,
                    "href": category_url,
                    "element": element  # Lưu lại element để sau này có thể tương tác
                })
            except Exception as e:
                logger.error(f"Lỗi khi xử lý phần tử danh mục: {e}")
        
        logger.info(f"Tìm thấy {len(category_links)} danh mục")
        
        # Lưu danh sách các danh mục vào file
        category_data = [{
            "text": cat["text"], 
            "href": cat["href"]
        } for cat in category_links]
        
        category_links_path = os.path.join(OUTPUT_DIR, "screenshots", "category_links.json")
        with open(category_links_path, "w", encoding="utf-8") as f:
            json.dump(category_data, f, ensure_ascii=False, indent=4)
        logger.info(f"Đã lưu danh sách danh mục: {category_links_path}")
        
        return category_links
    
    def crawl_categories(self) -> List[Dict[str, Any]]:
        if not self.page:
            self.setup_browser()
        
        logger.info(f"Bắt đầu crawl danh mục từ {BASE_URL}")
        
        try:
            self.page.goto(BASE_URL)
            self.wait_for_page_load()
            
            # Chụp ảnh và lưu HTML để kiểm tra
            self.take_snapshot("homepage")
            
            # Phát hiện danh mục
            category_links = self.detect_categories()
            
            if not category_links:
                logger.warning("Không tìm thấy danh mục nào")
                return []
            
            categories = []
            
            for idx, link in enumerate(category_links):
                try:
                    category_name = link["text"]
                    category_element = link["element"]
                    
                    logger.info(f"Đang xử lý danh mục {idx+1}/{len(category_links)}: {category_name}")
                    
                    category = {
                        'category_name': category_name,
                        'category_url': BASE_URL,  # Sử dụng URL trang chủ
                        'subcategories': []
                    }
                    
                    # Mở rộng danh mục để hiển thị danh mục con
                    success = self.expand_category(category_element)
                    
                    if success:
                        # Tìm các danh mục con cho danh mục này
                        try:
                            # Lưu HTML của container danh mục con để debug
                            subcategories_html = self.page.evaluate("""
                                (categoryName) => {
                                    // Tìm phần tử danh mục chính
                                    const mainCategories = Array.from(document.querySelectorAll('.cate_parent .text-14.font-semibold.uppercase'));
                                    const mainCategory = mainCategories.find(el => el.textContent.trim().includes(categoryName));
                                    
                                    if (!mainCategory) return "";
                                    
                                    // Tìm phần tử cha có class cate_parent
                                    const parentElement = mainCategory.closest('.cate_parent');
                                    if (!parentElement) return "";
                                    
                                    // Tìm container của danh mục con
                                    const subcategoryContainer = parentElement.querySelector('.overflow-hidden');
                                    if (!subcategoryContainer) return "";
                                    
                                    return subcategoryContainer.outerHTML;
                                }
                            """, category_name)
                            
                            # Lưu HTML subcategories container để debug
                            debug_html_path = os.path.join(OUTPUT_DIR, "screenshots", f"subcategories_{category_name.replace(' ', '_').lower()}.html")
                            with open(debug_html_path, "w", encoding="utf-8") as f:
                                f.write(subcategories_html)
                            logger.info(f"Đã lưu HTML danh mục con để debug: {debug_html_path}")
                            
                            # Thử nhiều selector khác nhau để tìm subcategory và xây dựng URL phù hợp
                            subcategories_js = self.page.evaluate("""
                                (categoryName) => {
                                    // Tìm phần tử danh mục chính
                                    const mainCategories = Array.from(document.querySelectorAll('.cate_parent .text-14.font-semibold.uppercase'));
                                    const mainCategory = mainCategories.find(el => el.textContent.trim().includes(categoryName));
                                    
                                    if (!mainCategory) return [];
                                    
                                    // Tìm phần tử cha có class cate_parent
                                    const parentElement = mainCategory.closest('.cate_parent');
                                    if (!parentElement) return [];
                                    
                                    // Tìm container của danh mục con
                                    const subcategoryContainer = parentElement.querySelector('.overflow-hidden');
                                    if (!subcategoryContainer) return [];
                                    
                                    // Tìm tất cả danh mục con div.cate
                                    const subcategoryElements = Array.from(subcategoryContainer.querySelectorAll('div.cate'));
                                    
                                    // Trích xuất tên danh mục con
                                    return subcategoryElements.map(el => {
                                        return {
                                            name: el.textContent.trim(),
                                            html: el.outerHTML
                                        };
                                    });
                                }
                            """, category_name)
                            
                            logger.info(f"Tìm thấy {len(subcategories_js)} danh mục con cho {category_name}")
                            
                            # Chuyển đổi danh sách thành danh sách đối tượng danh mục con
                            subcategories = []
                            for sub in subcategories_js:
                                sub_name = sub.get('name', '')
                                
                                if not sub_name:
                                    continue
                                    
                                # Chuẩn hóa tên danh mục để tạo URL slug
                                # Thay thế dấu cách bằng dấu gạch ngang và chuyển thành chữ thường
                                slug = self.convert_to_slug(sub_name)
                                
                                # Khởi tạo URL theo cấu trúc chính xác của bachhoaxanh.com
                                sub_url = f"{BASE_URL}/{slug}"
                                
                                subcategories.append({
                                    'subcategory_name': sub_name,
                                    'subcategory_url': sub_url
                                })
                            
                            category['subcategories'] = subcategories
                            
                            # Đóng lại danh mục sau khi đã lấy xong thông tin
                            try:
                                self.page.evaluate("""
                                    (categoryName) => {
                                        const mainCategories = Array.from(document.querySelectorAll('.cate_parent .text-14.font-semibold.uppercase'));
                                        const mainCategory = mainCategories.find(el => el.textContent.trim().includes(categoryName));
                                        if (mainCategory) {
                                            const parentElement = mainCategory.closest('.cate_parent');
                                            if (parentElement) {
                                                const clickableElement = parentElement.querySelector('.flex.cursor-pointer');
                                                if (clickableElement) clickableElement.click();
                                            }
                                        }
                                    }
                                """, category_name)
                                time.sleep(0.3)
                            except Exception as e:
                                logger.error(f"Lỗi khi đóng danh mục: {e}")
                            
                        except Exception as e:
                            logger.error(f"Lỗi khi lấy danh mục con cho {category_name}: {e}")
                    
                    categories.append(category)
                    time.sleep(CRAWL_DELAY)
                    
                except Exception as e:
                    logger.error(f"Lỗi khi xử lý danh mục: {e}")
            
            logger.info(f"Đã tìm thấy {len(categories)} danh mục")
            
            # Lọc danh mục dư thừa và không liên quan
            filtered_categories = []
            excluded_keywords = ['đăng nhập', 'tài khoản', 'giỏ hàng', 'giỏ', 'tìm kiếm', 'về chúng tôi', 'liên hệ', 'hỗ trợ', 'chính sách', 'xem', 'cửa hàng', 'ưu đãi từ hãng']
            
            for category in categories:
                name_lower = category['category_name'].lower()
                should_exclude = any(keyword in name_lower for keyword in excluded_keywords)
                
                if not should_exclude:
                    filtered_categories.append(category)
            
            logger.info(f"Còn lại {len(filtered_categories)} danh mục sau khi lọc")
            
            logger.info("Hoàn thành việc crawl danh mục và danh mục con")
            return filtered_categories
            
        except Exception as e:
            logger.error(f"Lỗi khi crawl danh mục: {e}")
            return []
        finally:
            self.close_browser()
    
    def crawl_subcategories(self, category: Dict[str, Any]):
        category_url = category['category_url']
        category_name = category['category_name']
        
        logger.info(f"Đang tìm danh mục con cho {category_name} tại {category_url}")
        
        try:
            self.page.goto(category_url)
            self.wait_for_page_load()
            
            # Chụp ảnh trang danh mục con để kiểm tra
            snapshot_name = f"category_{category_name.replace(' ', '_').lower()}"
            self.take_snapshot(snapshot_name)
            
            html = self.page.content()
            soup = BeautifulSoup(html, 'html.parser')
            
            subcategories = []
            
            for selector in SUBCATEGORY_SELECTORS:
                subcategory_elements = soup.select(selector)
                if subcategory_elements:
                    for element in subcategory_elements:
                        try:
                            subcategory_name = element.get_text(strip=True)
                            
                            subcategory_url = element.get('href', '')
                            if not subcategory_url:
                                continue
                                
                            # Đảm bảo URL đầy đủ
                            if subcategory_url.startswith('/'):
                                subcategory_url = BASE_URL + subcategory_url
                            elif not subcategory_url.startswith('http'):
                                subcategory_url = BASE_URL + '/' + subcategory_url
                            
                            # Kiểm tra nếu URL và name hợp lệ
                            if subcategory_name and subcategory_url and subcategory_url != category_url:
                                # Kiểm tra xem đã có trong danh sách chưa
                                if not any(sub['subcategory_url'] == subcategory_url for sub in subcategories):
                                    subcategories.append({
                                        'subcategory_name': subcategory_name,
                                        'subcategory_url': subcategory_url
                                    })
                        except Exception as e:
                            logger.error(f"Lỗi khi xử lý một danh mục con: {e}")
                    
                    # Nếu đã tìm được các danh mục con với selector này, thoát khỏi vòng lặp
                    if subcategories:
                        break
            
            # Lọc trùng lặp và danh mục con giống với danh mục cha
            filtered_subcategories = []
            for sub in subcategories:
                # Loại bỏ các danh mục con có URL giống với danh mục cha
                if sub['subcategory_url'] != category_url:
                    filtered_subcategories.append(sub)
            
            category['subcategories'] = filtered_subcategories
            logger.info(f"Đã tìm thấy {len(filtered_subcategories)} danh mục con cho {category_name}")
            
        except Exception as e:
            logger.error(f"Lỗi khi crawl danh mục con cho {category_name}: {e}")
            category['subcategories'] = []
    
    def save_categories(self, categories: List[Dict[str, Any]]):
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
        categories = self.crawl_categories()
        self.save_categories(categories)
        return categories

    def expand_category(self, category_element):
        """Mở rộng danh mục để hiển thị danh mục con bằng cách nhấp vào nó"""
        try:
            # Tìm phần tử cha có class cate_parent
            parent_element = category_element.evaluate_handle("el => el.closest('.cate_parent')")
            
            # Kiểm tra xem danh mục đã mở chưa
            is_collapsed = parent_element.evaluate("""
                (el) => {
                    const overflowDiv = el.querySelector('.overflow-hidden');
                    return overflowDiv && overflowDiv.style.height === '0px';
                }
            """)
            
            if is_collapsed:
                # Tìm phần tử có thể nhấp được (div.flex.cursor-pointer)
                clickable_element = parent_element.evaluate_handle("el => el.querySelector('.flex.cursor-pointer')")
                
                # Nhấp vào phần tử để mở rộng danh mục
                clickable_element.click()
                
                # Đợi một chút để hiệu ứng mở hoàn tất
                time.sleep(0.5)
                
                # Kiểm tra lại xem đã mở chưa
                is_expanded = parent_element.evaluate("""
                    (el) => {
                        const overflowDiv = el.querySelector('.overflow-hidden');
                        return overflowDiv && overflowDiv.style.height !== '0px';
                    }
                """)
                
                if not is_expanded:
                    logger.warning("Không thể mở rộng danh mục sau khi nhấp vào nó")
                    return False
                
                logger.info("Đã mở rộng danh mục thành công")
            else:
                logger.info("Danh mục đã được mở rộng sẵn")
            
            return True
        except Exception as e:
            logger.error(f"Lỗi khi mở rộng danh mục: {e}")
            return False

    def convert_to_slug(self, text):
        """Chuyển text thành slug URL"""
        # Dictionary mapping cho tiếng Việt
        vietnamese_map = {
            'à': 'a', 'á': 'a', 'ả': 'a', 'ã': 'a', 'ạ': 'a',
            'ă': 'a', 'ắ': 'a', 'ằ': 'a', 'ẳ': 'a', 'ẵ': 'a', 'ặ': 'a',
            'â': 'a', 'ấ': 'a', 'ầ': 'a', 'ẩ': 'a', 'ẫ': 'a', 'ậ': 'a',
            'đ': 'd',
            'è': 'e', 'é': 'e', 'ẻ': 'e', 'ẽ': 'e', 'ẹ': 'e',
            'ê': 'e', 'ế': 'e', 'ề': 'e', 'ể': 'e', 'ễ': 'e', 'ệ': 'e',
            'ì': 'i', 'í': 'i', 'ỉ': 'i', 'ĩ': 'i', 'ị': 'i',
            'ò': 'o', 'ó': 'o', 'ỏ': 'o', 'õ': 'o', 'ọ': 'o',
            'ô': 'o', 'ố': 'o', 'ồ': 'o', 'ổ': 'o', 'ỗ': 'o', 'ộ': 'o',
            'ơ': 'o', 'ớ': 'o', 'ờ': 'o', 'ở': 'o', 'ỡ': 'o', 'ợ': 'o',
            'ù': 'u', 'ú': 'u', 'ủ': 'u', 'ũ': 'u', 'ụ': 'u',
            'ư': 'u', 'ứ': 'u', 'ừ': 'u', 'ử': 'u', 'ữ': 'u', 'ự': 'u',
            'ỳ': 'y', 'ý': 'y', 'ỷ': 'y', 'ỹ': 'y', 'ỵ': 'y'
        }
        
        # Chuyển đổi tiếng Việt và các ký tự đặc biệt
        result = ""
        for char in text.lower():
            if char in vietnamese_map:
                result += vietnamese_map[char]
            elif char.isalnum():
                result += char
            else:
                result += " "
        
        # Thay thế nhiều dấu cách liên tiếp thành một dấu cách
        result = " ".join(result.split())
        
        # Thay thế dấu cách bằng dấu gạch ngang
        result = result.replace(" ", "-")
        
        # Xử lý các trường hợp đặc biệt dựa trên mẫu từ URL đúng
        special_cases = {
            'thit-heo': 'thit-heo',
            'thit-bo': 'thit-bo',
            'thit-ga-vit-chim': 'thit-ga-vit-chim',
            'ca-hai-san-kho': 'ca-hai-san-kho',
            'trung-ga-vit-cut': 'trung'
        }
        
        # Kiểm tra xem có phải trường hợp đặc biệt không
        for key, value in special_cases.items():
            if result == key or result.startswith(key):
                return value
        
        return result

def main():
    parser = argparse.ArgumentParser(description="Crawler danh mục sử dụng Playwright")
    parser.add_argument("--output", type=str, default="categories_playwright.json",
                       help="Tên file đầu ra (mặc định: categories_playwright.json)")
    args = parser.parse_args()
    
    try:
        crawler = PlaywrightCategoryCrawler(output_file=args.output)
        crawler.run()
    except Exception as e:
        logger.error(f"Lỗi khi chạy crawler: {e}")

if __name__ == "__main__":
    main() 