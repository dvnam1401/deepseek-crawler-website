#!/usr/bin/env python3
"""
Crawler chính cho website - Điểm khởi đầu của hệ thống
"""
import os
import time
import logging
import asyncio
import argparse
from typing import List, Dict, Any, Set
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

from dotenv import load_dotenv
from crawl4ai import AsyncWebCrawler
import undetected_chromedriver as uc

from crawler import WebCrawler, AsyncCrawler
from parser import DataParser
from storage import DataStorage
import config
from utils.scraper_utils import (
    get_browser_config,
    get_llm_strategy_for_categories,
    get_llm_strategy_for_products,
    fetch_categories,
    fetch_and_process_product_page,
)

# Thiết lập logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("crawler.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

# Tải biến môi trường từ file .env
load_dotenv()

def is_complete_product(product: Dict[str, Any], required_keys: List[str]) -> bool:
    """Kiểm tra xem sản phẩm có đầy đủ các trường bắt buộc không"""
    return all(key in product for key in required_keys)

def is_duplicate_product(product_url: str, seen_urls: Set[str]) -> bool:
    """Kiểm tra xem sản phẩm đã được crawl chưa"""
    return product_url in seen_urls

class CrawlerManager:
    """Quản lý và điều phối quá trình crawl dữ liệu"""
    
    def __init__(self, use_async: bool = True):
        """
        Khởi tạo CrawlerManager
        
        Args:
            use_async: Sử dụng AsyncCrawler (True) hoặc WebCrawler thông thường (False)
        """
        self.use_async = use_async
        self.crawler = AsyncCrawler() if use_async else WebCrawler()
        self.parser = DataParser()
        self.storage = DataStorage(output_dir=config.OUTPUT_DIR)
        self.seen_urls = set()
        self.categories = []
        self.products = []
        
    def load_checkpoint(self, checkpoint_file: str):
        """Tải checkpoint từ lần crawl trước"""
        if not checkpoint_file:
            return
            
        urls = self.storage.load_checkpoint(checkpoint_file)
        if urls:
            self.seen_urls.update(urls)
            logger.info(f"Đã tải {len(urls)} URL đã crawl từ checkpoint")
    
    async def run_async(self, max_products_per_category: int = None, checkpoint_file: str = None):
        """Chạy crawler bất đồng bộ"""
        
        # Tải checkpoint nếu có
        self.load_checkpoint(checkpoint_file)
        
        # Khởi tạo session
        session_id = f"crawl_session_{int(time.time())}"
        
        async with AsyncWebCrawler(config=get_browser_config()) as crawler:
            # Bước 1: Lấy danh sách các danh mục
            logger.info(f"Đang lấy danh sách danh mục từ {config.BASE_URL}")
            
            self.categories = await fetch_categories(
                crawler, 
                config.BASE_URL, 
                config.CATEGORY_CSS_SELECTOR, 
                session_id,
                max_retries=config.MAX_RETRIES, 
                retry_delay=config.CRAWL_DELAY
            )
            
            if not self.categories:
                logger.error("Không tìm thấy danh mục nào. Kết thúc.")
                return
                
            logger.info(f"Đã tìm thấy {len(self.categories)} danh mục")
            
            # Bước 2: Crawl từng danh mục để lấy danh sách sản phẩm
            for category in self.categories:
                category_name = category["category_name"]
                category_url = config.BASE_URL + category["category_url"].lstrip('/')
                
                logger.info(f"Đang crawl danh mục: {category_name} ({category_url})")
                
                # Lấy danh sách sản phẩm trong danh mục
                category_products = await fetch_and_process_product_page(
                    crawler, 
                    category_url, 
                    category_name, 
                    config.PRODUCT_CSS_SELECTOR,
                    get_llm_strategy_for_products(category_name), 
                    session_id,
                    config.REQUIRED_KEYS, 
                    self.seen_urls, 
                    max_retries=config.MAX_RETRIES, 
                    retry_delay=config.CRAWL_DELAY,
                    page_load_delay=3.0
                )
                
                # Giới hạn số lượng sản phẩm nếu cần
                if max_products_per_category and len(category_products) > max_products_per_category:
                    logger.info(f"Giới hạn {max_products_per_category} sản phẩm cho danh mục {category_name}")
                    category_products = category_products[:max_products_per_category]
                
                # Đánh dấu các URL đã crawl
                for product in category_products:
                    self.seen_urls.add(product["product_url"])
                
                # Thêm vào danh sách sản phẩm chung
                self.products.extend(category_products)
                
                # Lưu checkpoint sau mỗi danh mục
                self.storage.save_checkpoint(list(self.seen_urls))
                
                # Lưu sản phẩm đã crawl đến thời điểm hiện tại
                self.storage.save_to_csv(self.products, config.OUTPUT_FILE_CSV)
                
                # Nghỉ giữa các danh mục để tránh bị chặn
                await asyncio.sleep(config.CRAWL_DELAY)
            
            # Bước 3: Lưu tất cả sản phẩm vào file
            if self.products:
                logger.info(f"Đã crawl tổng cộng {len(self.products)} sản phẩm")
                self.storage.save_to_csv(self.products, config.OUTPUT_FILE_CSV)
                self.storage.save_to_json(self.products, config.OUTPUT_FILE_JSON)
            else:
                logger.warning("Không tìm thấy sản phẩm nào")
    
    def run_sync(self, max_products_per_category: int = None, checkpoint_file: str = None):
        """Chạy crawler đồng bộ"""
        
        # Tải checkpoint nếu có
        self.load_checkpoint(checkpoint_file)
        
        # Khởi tạo WebCrawler
        crawler = self.crawler
        if not isinstance(crawler, WebCrawler):
            crawler = WebCrawler()
        
        driver = crawler.setup_driver()
        
        try:
            # Bước 1: Lấy danh sách các danh mục
            logger.info(f"Đang lấy danh sách danh mục từ {config.BASE_URL}")
            
            soup = crawler.get_page_content(config.BASE_URL, config.CATEGORY_CSS_SELECTOR)
            if not soup:
                logger.error("Không thể tải trang chủ. Kết thúc.")
                return
                
            self.categories = self.parser.parse_category_data(soup, config.CATEGORY_CSS_SELECTOR)
            
            if not self.categories:
                logger.error("Không tìm thấy danh mục nào. Kết thúc.")
                return
                
            logger.info(f"Đã tìm thấy {len(self.categories)} danh mục")
            
            # Bước 2: Crawl từng danh mục để lấy danh sách sản phẩm
            for category in self.categories:
                category_name = category["category_name"]
                category_url = config.BASE_URL + category["category_url"].lstrip('/')
                
                logger.info(f"Đang crawl danh mục: {category_name} ({category_url})")
                
                # Lấy và phân tích trang danh mục
                category_soup = crawler.get_page_content(category_url, config.PRODUCT_CSS_SELECTOR)
                if not category_soup:
                    logger.warning(f"Không thể tải trang danh mục: {category_url}. Bỏ qua.")
                    continue
                
                # Phân tích danh sách sản phẩm
                category_products = self.parser.parse_product_list(
                    category_soup, 
                    config.PRODUCT_CSS_SELECTOR, 
                    category_name
                )
                
                # Giới hạn số lượng sản phẩm nếu cần
                if max_products_per_category and len(category_products) > max_products_per_category:
                    logger.info(f"Giới hạn {max_products_per_category} sản phẩm cho danh mục {category_name}")
                    category_products = category_products[:max_products_per_category]
                
                # Bước 3: Crawl chi tiết từng sản phẩm
                detailed_products = []
                
                for product in category_products:
                    product_url = product["product_url"]
                    
                    # Kiểm tra trùng lặp
                    if is_duplicate_product(product_url, self.seen_urls):
                        logger.info(f"Bỏ qua sản phẩm trùng lặp: {product['name']}")
                        continue
                    
                    # Crawl chi tiết sản phẩm
                    logger.info(f"Đang crawl chi tiết sản phẩm: {product['name']}")
                    
                    product_soup = crawler.get_page_content(product_url)
                    if not product_soup:
                        logger.warning(f"Không thể tải trang sản phẩm: {product_url}. Bỏ qua.")
                        continue
                    
                    # Phân tích chi tiết sản phẩm
                    product_details = self.parser.parse_product_details(product_soup, config.SELECTORS)
                    
                    # Hợp nhất thông tin cơ bản và chi tiết
                    detailed_product = {**product, **product_details}
                    
                    # Kiểm tra sản phẩm có đầy đủ thông tin không
                    if is_complete_product(detailed_product, config.REQUIRED_KEYS):
                        detailed_products.append(detailed_product)
                        self.seen_urls.add(product_url)
                        
                    # Nghỉ giữa các request để tránh bị chặn
                    time.sleep(config.CRAWL_DELAY)
                
                # Thêm vào danh sách sản phẩm chung
                self.products.extend(detailed_products)
                
                # Lưu checkpoint sau mỗi danh mục
                self.storage.save_checkpoint(list(self.seen_urls))
                
                # Lưu sản phẩm đã crawl đến thời điểm hiện tại
                self.storage.save_to_csv(self.products, config.OUTPUT_FILE_CSV)
                
                # Nghỉ giữa các danh mục để tránh bị chặn
                time.sleep(config.CRAWL_DELAY * 2)
            
            # Bước 4: Lưu tất cả sản phẩm vào file
            if self.products:
                logger.info(f"Đã crawl tổng cộng {len(self.products)} sản phẩm")
                self.storage.save_to_csv(self.products, config.OUTPUT_FILE_CSV)
                self.storage.save_to_json(self.products, config.OUTPUT_FILE_JSON)
            else:
                logger.warning("Không tìm thấy sản phẩm nào")
                
        finally:
            # Đóng driver khi hoàn thành
            crawler.close_driver()
    
    def run_multithread(self, max_products_per_category: int = None, 
                        max_workers: int = config.MAX_WORKERS, 
                        checkpoint_file: str = None):
        """Chạy crawler với đa luồng để tối ưu hiệu suất"""
        
        # Tải checkpoint nếu có
        self.load_checkpoint(checkpoint_file)
        
        # Khởi tạo WebCrawler chính để lấy danh mục
        main_crawler = WebCrawler()
        driver = main_crawler.setup_driver()
        
        try:
            # Bước 1: Lấy danh sách các danh mục
            logger.info(f"Đang lấy danh sách danh mục từ {config.BASE_URL}")
            
            soup = main_crawler.get_page_content(config.BASE_URL, config.CATEGORY_CSS_SELECTOR)
            if not soup:
                logger.error("Không thể tải trang chủ. Kết thúc.")
                return
                
            self.categories = self.parser.parse_category_data(soup, config.CATEGORY_CSS_SELECTOR)
            
            if not self.categories:
                logger.error("Không tìm thấy danh mục nào. Kết thúc.")
                return
                
            logger.info(f"Đã tìm thấy {len(self.categories)} danh mục")
            
            # Đóng crawler chính sau khi lấy danh mục
            main_crawler.close_driver()
            
            # Bước 2: Sử dụng ThreadPoolExecutor để crawl đa luồng các danh mục
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                # Tạo futures cho từng danh mục
                futures = {}
                
                for category in self.categories:
                    future = executor.submit(
                        self._crawl_category,
                        category,
                        max_products_per_category
                    )
                    futures[future] = category["category_name"]
                
                # Xử lý kết quả khi hoàn thành
                for future in as_completed(futures):
                    category_name = futures[future]
                    try:
                        category_products = future.result()
                        if category_products:
                            logger.info(f"Hoàn thành crawl danh mục {category_name}: {len(category_products)} sản phẩm")
                            self.products.extend(category_products)
                            
                            # Lưu checkpoint và sản phẩm sau mỗi danh mục hoàn thành
                            self.storage.save_checkpoint(list(self.seen_urls))
                            self.storage.save_to_csv(self.products, config.OUTPUT_FILE_CSV)
                        else:
                            logger.warning(f"Không tìm thấy sản phẩm nào trong danh mục {category_name}")
                    except Exception as e:
                        logger.error(f"Lỗi khi crawl danh mục {category_name}: {str(e)}")
            
            # Bước 3: Lưu tất cả sản phẩm vào file
            if self.products:
                logger.info(f"Đã crawl tổng cộng {len(self.products)} sản phẩm")
                self.storage.save_to_csv(self.products, config.OUTPUT_FILE_CSV)
                self.storage.save_to_json(self.products, config.OUTPUT_FILE_JSON)
            else:
                logger.warning("Không tìm thấy sản phẩm nào")
                
        except Exception as e:
            logger.error(f"Lỗi trong quá trình crawl: {str(e)}")
            
    def _crawl_category(self, category: Dict[str, str], max_products: int = None) -> List[Dict[str, Any]]:
        """
        Hàm helper để crawl một danh mục cụ thể, được sử dụng trong đa luồng
        
        Args:
            category: Thông tin danh mục
            max_products: Số lượng sản phẩm tối đa cần crawl
            
        Returns:
            List[Dict[str, Any]]: Danh sách sản phẩm đã crawl
        """
        category_products = []
        category_name = category["category_name"]
        category_url = config.BASE_URL + category["category_url"].lstrip('/')
        
        # Khởi tạo crawler riêng cho thread này
        thread_crawler = WebCrawler()
        driver = thread_crawler.setup_driver()
        
        try:
            logger.info(f"Thread crawl danh mục: {category_name}")
            
            # Lấy và phân tích trang danh mục
            category_soup = thread_crawler.get_page_content(category_url, config.PRODUCT_CSS_SELECTOR)
            if not category_soup:
                logger.warning(f"Không thể tải trang danh mục: {category_url}")
                return []
            
            # Phân tích danh sách sản phẩm
            products = self.parser.parse_product_list(
                category_soup, 
                config.PRODUCT_CSS_SELECTOR, 
                category_name
            )
            
            # Giới hạn số lượng sản phẩm nếu cần
            if max_products and len(products) > max_products:
                logger.info(f"Giới hạn {max_products} sản phẩm cho danh mục {category_name}")
                products = products[:max_products]
            
            # Crawl chi tiết từng sản phẩm
            for product in products:
                product_url = product["product_url"]
                
                # Kiểm tra URL đã crawl chưa
                if product_url in self.seen_urls:
                    logger.info(f"Bỏ qua sản phẩm trùng lặp: {product['name']}")
                    continue
                
                # Đánh dấu URL đã được xử lý
                self.seen_urls.add(product_url)
                
                # Crawl chi tiết sản phẩm
                logger.info(f"Đang crawl chi tiết sản phẩm: {product['name']}")
                
                product_soup = thread_crawler.get_page_content(product_url)
                if not product_soup:
                    logger.warning(f"Không thể tải trang sản phẩm: {product_url}")
                    continue
                
                # Phân tích chi tiết sản phẩm
                product_details = self.parser.parse_product_details(product_soup, config.SELECTORS)
                
                # Hợp nhất thông tin cơ bản và chi tiết
                detailed_product = {**product, **product_details}
                
                # Kiểm tra sản phẩm có đầy đủ thông tin không
                if is_complete_product(detailed_product, config.REQUIRED_KEYS):
                    category_products.append(detailed_product)
                    
                # Nghỉ giữa các request để tránh bị chặn
                time.sleep(config.CRAWL_DELAY)
                
            return category_products
            
        except Exception as e:
            logger.error(f"Lỗi khi crawl danh mục {category_name}: {str(e)}")
            return []
            
        finally:
            # Đóng driver khi hoàn thành
            thread_crawler.close_driver()

async def main():
    """Hàm chính của chương trình"""
    
    # Phân tích tham số dòng lệnh
    parser = argparse.ArgumentParser(description="Crawler cho website Bach Hoa Xanh")
    parser.add_argument("--mode", choices=["async", "sync", "multithread"], default="async",
                      help="Chế độ chạy: async (bất đồng bộ), sync (đồng bộ), multithread (đa luồng)")
    parser.add_argument("--limit", type=int, default=None,
                      help="Giới hạn số lượng sản phẩm cho mỗi danh mục")
    parser.add_argument("--checkpoint", type=str, default=None,
                      help="File checkpoint để tiếp tục crawl")
    parser.add_argument("--workers", type=int, default=config.MAX_WORKERS,
                      help="Số lượng worker cho chế độ đa luồng")
    args = parser.parse_args()
    
    # Khởi tạo crawler manager
    manager = CrawlerManager(use_async=(args.mode == "async"))
    
    # Chạy crawler theo chế độ đã chọn
    start_time = time.time()
    
    try:
        if args.mode == "async":
            await manager.run_async(args.limit, args.checkpoint)
        elif args.mode == "multithread":
            manager.run_multithread(args.limit, args.workers, args.checkpoint)
        else:  # sync
            manager.run_sync(args.limit, args.checkpoint)
    except Exception as e:
        logger.error(f"Lỗi trong quá trình crawl: {str(e)}")
    
    elapsed_time = time.time() - start_time
    logger.info(f"Hoàn thành crawler trong {elapsed_time:.2f} giây")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Crawler bị dừng bởi người dùng")
    except Exception as e:
        logger.error(f"Lỗi không xử lý được: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())