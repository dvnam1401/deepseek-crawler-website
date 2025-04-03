import csv
import json
import os
import logging
import pandas as pd
from typing import List, Dict, Any, Optional, Union
from datetime import datetime

class DataStorage:
    """Lớp xử lý việc lưu trữ dữ liệu thu thập được"""
    
    def __init__(self, output_dir: str = "data"):
        """
        Khởi tạo đối tượng DataStorage
        
        Args:
            output_dir: Thư mục đầu ra cho dữ liệu
        """
        self.output_dir = output_dir
        self.logger = logging.getLogger(__name__)
        
        # Tạo thư mục đầu ra nếu không tồn tại
        os.makedirs(output_dir, exist_ok=True)
    
    def save_to_csv(self, data: List[Dict[str, Any]], filename: str, append: bool = False) -> bool:
        """
        Lưu dữ liệu vào file CSV
        
        Args:
            data: Danh sách các dictionary chứa dữ liệu
            filename: Tên file CSV (sẽ được lưu trong thư mục output_dir)
            append: Nếu True, dữ liệu sẽ được thêm vào file hiện có
            
        Returns:
            bool: True nếu lưu thành công, False nếu lỗi
        """
        if not data:
            self.logger.warning("Không có dữ liệu để lưu vào CSV.")
            return False
            
        filepath = os.path.join(self.output_dir, filename)
        mode = "a" if append and os.path.exists(filepath) else "w"
        write_header = mode == "w" or (mode == "a" and not os.path.exists(filepath))
        
        try:
            # Xác định các trường dữ liệu từ dữ liệu đầu vào
            all_fields = set()
            for item in data:
                all_fields.update(item.keys())
            fieldnames = sorted(list(all_fields))
            
            # Xử lý các trường phức tạp thành chuỗi JSON
            processed_data = []
            for item in data:
                processed_item = {}
                for key, value in item.items():
                    if isinstance(value, (dict, list)):
                        processed_item[key] = json.dumps(value, ensure_ascii=False)
                    else:
                        processed_item[key] = value
                processed_data.append(processed_item)
            
            # Ghi dữ liệu vào file CSV
            with open(filepath, mode=mode, newline="", encoding="utf-8") as file:
                writer = csv.DictWriter(file, fieldnames=fieldnames)
                if write_header:
                    writer.writeheader()
                writer.writerows(processed_data)
                
            self.logger.info(f"Đã lưu {len(data)} mục vào file '{filepath}'.")
            return True
        except Exception as e:
            self.logger.error(f"Lỗi khi lưu dữ liệu vào CSV: {str(e)}")
            return False
    
    def save_to_json(self, data: Union[List[Dict[str, Any]], Dict[str, Any]], 
                     filename: str, indent: int = 4) -> bool:
        """
        Lưu dữ liệu vào file JSON
        
        Args:
            data: Dictionary hoặc danh sách các dictionary chứa dữ liệu
            filename: Tên file JSON (sẽ được lưu trong thư mục output_dir)
            indent: Số khoảng trắng để thụt lề (định dạng JSON)
            
        Returns:
            bool: True nếu lưu thành công, False nếu lỗi
        """
        if not data:
            self.logger.warning("Không có dữ liệu để lưu vào JSON.")
            return False
            
        filepath = os.path.join(self.output_dir, filename)
        
        try:
            with open(filepath, mode="w", encoding="utf-8") as file:
                json.dump(data, file, ensure_ascii=False, indent=indent)
                
            self.logger.info(f"Đã lưu dữ liệu vào file '{filepath}'.")
            return True
        except Exception as e:
            self.logger.error(f"Lỗi khi lưu dữ liệu vào JSON: {str(e)}")
            return False
    
    def load_from_csv(self, filename: str) -> List[Dict[str, Any]]:
        """
        Đọc dữ liệu từ file CSV
        
        Args:
            filename: Tên file CSV (trong thư mục output_dir)
            
        Returns:
            List[Dict[str, Any]]: Danh sách các dictionary chứa dữ liệu
        """
        filepath = os.path.join(self.output_dir, filename)
        
        if not os.path.exists(filepath):
            self.logger.warning(f"File CSV '{filepath}' không tồn tại.")
            return []
            
        try:
            data = []
            with open(filepath, mode="r", encoding="utf-8") as file:
                reader = csv.DictReader(file)
                for row in reader:
                    # Chuyển đổi chuỗi JSON thành đối tượng Python
                    processed_row = {}
                    for key, value in row.items():
                        try:
                            if value and (value.startswith('[') or value.startswith('{')):
                                processed_row[key] = json.loads(value)
                            else:
                                processed_row[key] = value
                        except:
                            processed_row[key] = value
                    data.append(processed_row)
                    
            self.logger.info(f"Đã đọc {len(data)} mục từ file '{filepath}'.")
            return data
        except Exception as e:
            self.logger.error(f"Lỗi khi đọc dữ liệu từ CSV: {str(e)}")
            return []
    
    def load_from_json(self, filename: str) -> Union[List[Dict[str, Any]], Dict[str, Any], None]:
        """
        Đọc dữ liệu từ file JSON
        
        Args:
            filename: Tên file JSON (trong thư mục output_dir)
            
        Returns:
            Union[List[Dict[str, Any]], Dict[str, Any], None]: Dữ liệu từ file JSON
        """
        filepath = os.path.join(self.output_dir, filename)
        
        if not os.path.exists(filepath):
            self.logger.warning(f"File JSON '{filepath}' không tồn tại.")
            return None
            
        try:
            with open(filepath, mode="r", encoding="utf-8") as file:
                data = json.load(file)
                
            self.logger.info(f"Đã đọc dữ liệu từ file '{filepath}'.")
            return data
        except Exception as e:
            self.logger.error(f"Lỗi khi đọc dữ liệu từ JSON: {str(e)}")
            return None
    
    def save_checkpoint(self, crawled_urls: List[str], filename: Optional[str] = None) -> bool:
        """
        Lưu danh sách các URL đã crawl để có thể tiếp tục sau này
        
        Args:
            crawled_urls: Danh sách các URL đã crawl
            filename: Tên file checkpoint (mặc định: checkpoint_<timestamp>.json)
            
        Returns:
            bool: True nếu lưu thành công, False nếu lỗi
        """
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"checkpoint_{timestamp}.json"
            
        checkpoint_data = {
            "timestamp": datetime.now().isoformat(),
            "crawled_urls": crawled_urls
        }
        
        return self.save_to_json(checkpoint_data, filename)
    
    def load_checkpoint(self, filename: str) -> List[str]:
        """
        Đọc danh sách các URL đã crawl từ checkpoint
        
        Args:
            filename: Tên file checkpoint
            
        Returns:
            List[str]: Danh sách các URL đã crawl
        """
        checkpoint_data = self.load_from_json(filename)
        
        if checkpoint_data and "crawled_urls" in checkpoint_data:
            return checkpoint_data["crawled_urls"]
        return []
    
    def download_images(self, image_urls: List[str], product_name: str, 
                       output_subdir: str = "images") -> List[str]:
        """
        Tải xuống hình ảnh từ danh sách URL
        
        Args:
            image_urls: Danh sách các URL hình ảnh
            product_name: Tên sản phẩm (để đặt tên file)
            output_subdir: Thư mục con trong output_dir để lưu hình ảnh
            
        Returns:
            List[str]: Danh sách đường dẫn đến các file hình ảnh đã tải
        """
        import requests
        from slugify import slugify
        
        if not image_urls:
            return []
            
        # Tạo thư mục cho hình ảnh
        image_dir = os.path.join(self.output_dir, output_subdir)
        os.makedirs(image_dir, exist_ok=True)
        
        # Tạo tên sản phẩm hợp lệ cho tên file
        safe_product_name = slugify(product_name)[:50]  # Giới hạn độ dài tên file
        
        downloaded_images = []
        
        for i, img_url in enumerate(image_urls):
            try:
                # Xác định phần mở rộng của file
                extension = "jpg"  # Mặc định
                if "." in img_url.split("/")[-1]:
                    ext = img_url.split(".")[-1].split("?")[0].lower()
                    if ext in ["jpg", "jpeg", "png", "gif", "webp"]:
                        extension = ext
                
                img_filename = f"{safe_product_name}_{i+1}.{extension}"
                img_path = os.path.join(image_dir, img_filename)
                
                # Tải và lưu hình ảnh
                response = requests.get(img_url, stream=True, timeout=10)
                if response.status_code == 200:
                    with open(img_path, 'wb') as f:
                        for chunk in response.iter_content(1024):
                            f.write(chunk)
                    downloaded_images.append(img_path)
                    self.logger.info(f"Đã tải xuống hình ảnh: {img_path}")
                else:
                    self.logger.warning(f"Không thể tải hình ảnh từ {img_url} (status: {response.status_code})")
            except Exception as e:
                self.logger.error(f"Lỗi khi tải hình ảnh từ {img_url}: {str(e)}")
        
        return downloaded_images 