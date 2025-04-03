import logging
import re
import json
from typing import Dict, List, Any, Optional
from bs4 import BeautifulSoup

class DataParser:
    """Lớp xử lý và phân tích dữ liệu trích xuất từ website"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def parse_category_data(self, soup: BeautifulSoup, category_selector: str) -> List[Dict[str, str]]:
        """
        Phân tích dữ liệu danh mục từ trang web
        
        Args:
            soup: Đối tượng BeautifulSoup
            category_selector: CSS selector cho các phần tử danh mục
            
        Returns:
            List[Dict[str, str]]: Danh sách các danh mục
        """
        categories = []
        
        try:
            category_elements = soup.select(category_selector)
            
            for element in category_elements:
                category_name = element.get_text(strip=True)
                category_url = element.get('href', '')
                
                if category_name and category_url:
                    categories.append({
                        'category_name': category_name,
                        'category_url': category_url
                    })
        except Exception as e:
            self.logger.error(f"Lỗi khi phân tích dữ liệu danh mục: {str(e)}")
        
        return categories
    
    def parse_product_list(self, soup: BeautifulSoup, product_selector: str, 
                          category_name: str) -> List[Dict[str, Any]]:
        """
        Phân tích dữ liệu danh sách sản phẩm từ trang danh mục
        
        Args:
            soup: Đối tượng BeautifulSoup
            product_selector: CSS selector cho các phần tử sản phẩm
            category_name: Tên danh mục
            
        Returns:
            List[Dict[str, Any]]: Danh sách các sản phẩm
        """
        products = []
        
        try:
            product_elements = soup.select(product_selector)
            
            for element in product_elements:
                try:
                    name_element = element.select_one(".product_name, h3")
                    price_element = element.select_one(".product_price, .price")
                    description_element = element.select_one(".mb-4px.block.leading-3")
                    link_element = element.select_one("a")
                    
                    if name_element and price_element and link_element:
                        product = {
                            'name': name_element.get_text(strip=True),
                            'price': price_element.get_text(strip=True),
                            'category': category_name,
                            'description': description_element.get_text(strip=True) if description_element else "",
                            'product_url': link_element.get('href', '')
                        }
                        
                        products.append(product)
                except Exception as e:
                    self.logger.warning(f"Lỗi khi phân tích một sản phẩm: {str(e)}")
        except Exception as e:
            self.logger.error(f"Lỗi khi phân tích danh sách sản phẩm: {str(e)}")
        
        return products
    
    def parse_product_details(self, soup: BeautifulSoup, selectors: Dict[str, List[str]]) -> Dict[str, Any]:
        """
        Phân tích chi tiết sản phẩm từ trang sản phẩm
        
        Args:
            soup: Đối tượng BeautifulSoup
            selectors: Dictionary các CSS selector cho từng loại thông tin
            
        Returns:
            Dict[str, Any]: Chi tiết sản phẩm
        """
        product_details = {}
        
        # Trích xuất các thông tin cơ bản từ selectors
        for key, selector_list in selectors.items():
            for selector in selector_list:
                elements = soup.select(selector)
                if elements:
                    if key == "description":
                        product_details[key] = "\n".join([elem.get_text(strip=True) for elem in elements])
                    else:
                        product_details[key] = elements[0].get_text(strip=True)
                    break
        
        # Trích xuất URL hình ảnh
        product_details["image_urls"] = self.extract_image_urls(soup)
        
        # Trích xuất thông tin chi tiết từ bảng
        product_details["detailed_info"] = self.extract_table_data(soup)
        
        return product_details
    
    def extract_image_urls(self, soup: BeautifulSoup) -> List[str]:
        """
        Trích xuất URL hình ảnh từ trang sản phẩm
        
        Args:
            soup: Đối tượng BeautifulSoup
            
        Returns:
            List[str]: Danh sách URL hình ảnh
        """
        image_urls = []
        
        # Tìm hình ảnh trong swiper-slide (carousel sản phẩm)
        try:
            swiper_images = soup.select(".swiper-slide img")
            for img in swiper_images:
                src = img.get("src") or img.get("data-src")
                if src and "placeholder" not in src:
                    src = src.split("?")[0]  # Loại bỏ query params
                    if src not in image_urls:
                        image_urls.append(src)
        except Exception as e:
            self.logger.error(f"Lỗi khi trích xuất hình ảnh: {str(e)}")
        
        # Tìm hình ảnh sản phẩm bằng các selector phổ biến
        if len(image_urls) < 2:
            selectors = [
                "img[src*='cdn']",
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
        
        return image_urls
    
    def extract_table_data(self, soup: BeautifulSoup) -> Dict[str, str]:
        """
        Trích xuất dữ liệu từ bảng thông tin
        
        Args:
            soup: Đối tượng BeautifulSoup
            
        Returns:
            Dict[str, str]: Dictionary chứa thông tin từ bảng
        """
        table_data = {}
        
        # Tìm các bảng thông tin chi tiết sản phẩm
        try:
            tables = soup.select("table")
            for table in tables:
                rows = table.select("tr")
                for row in rows:
                    cells = row.select("td, th")
                    if len(cells) >= 2:
                        key = cells[0].get_text(strip=True)
                        value = cells[1].get_text(strip=True)
                        if key and key not in table_data:
                            table_data[key] = value
        except Exception as e:
            self.logger.error(f"Lỗi khi trích xuất dữ liệu bảng: {str(e)}")
        
        # Thử phương pháp khác nếu không tìm thấy bảng
        if not table_data:
            try:
                detail_divs = soup.select(".detail-style .row, .product-info .row")
                for div in detail_divs:
                    key_elem = div.select_one(".col-5, .col-4, .label")
                    value_elem = div.select_one(".col-7, .col-8, .data")
                    if key_elem and value_elem:
                        key = key_elem.get_text(strip=True)
                        value = value_elem.get_text(strip=True)
                        if key and key not in table_data:
                            table_data[key] = value
            except Exception as e:
                self.logger.error(f"Lỗi khi trích xuất dữ liệu từ div: {str(e)}")
        
        return table_data 