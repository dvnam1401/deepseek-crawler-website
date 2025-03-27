# product.py
from pydantic import BaseModel
from typing import List, Dict, Optional

class Product(BaseModel):
    """
    Đại diện cho cấu trúc dữ liệu của một Sản phẩm với thông tin chi tiết.
    """
    name: str                                    # Tên sản phẩm
    category: str                                # Danh mục
    price: str                                   # Giá hiện tại
    original_price: Optional[str] = None         # Giá gốc (nếu có giảm giá)
    discount: Optional[str] = None               # Thông tin giảm giá
    rating: Optional[float] = None               # Đánh giá (1-5 sao)
    reviews: Optional[int] = None                # Số lượng đánh giá
    description: str                             # Mô tả sản phẩm
    image_urls: Optional[List[str]] = None       # Danh sách URL ảnh
    product_url: str                             # URL của trang sản phẩm
    variants: Optional[List[Dict[str, str]]] = None  # Các biến thể sản phẩm (ví dụ: "Thùng 48 Hộp", "Lốc 4 Hộp")
    detailed_info: Optional[Dict[str, str]] = None   # Thông tin chi tiết từ bảng
    comments: Optional[List[Dict[str, str]]] = None  # Danh sách bình luận (nếu có)