# product.py
from pydantic import BaseModel
from typing import List, Dict, Optional

class Product(BaseModel):
    """
    Represents the data structure of a Product with detailed information.
    """
    name: str
    category: str
    price: str
    original_price: Optional[str] = None
    discount: Optional[str] = None
    rating: Optional[float] = None
    reviews: Optional[int] = None
    description: str
    image_urls: Optional[List[str]] = None  # Danh sách URL ảnh
    product_url: str
    variants: Optional[List[Dict[str, str]]] = None  # Các biến thể sản phẩm (ví dụ: "Thùng 48 Hộp", "Lốc 4 Hộp")
    detailed_info: Optional[Dict[str, str]] = None  # Thông tin chi tiết từ bảng
    comments: Optional[List[Dict[str, str]]] = None  # Danh sách bình luận (nếu có)