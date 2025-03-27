# data_utils.py
import csv
import json

from models.product import Product

def is_duplicate_product(product_url: str, seen_urls: set) -> bool:
    return product_url in seen_urls

def is_complete_product(product: dict, required_keys: list) -> bool:
    return all(key in product for key in required_keys)

def save_products_to_csv(products: list, filename: str):
    if not products:
        print("No products to save.")
        return

    fieldnames = ["name", "category", "price", "original_price", "discount", 
                  "rating", "reviews", "description", "image_urls", "product_url", 
                  "variants", "detailed_info", "comments"]
    
    processed_products = []
    for product in products:
        processed_product = product.copy()
        # Chuyển các trường phức tạp thành chuỗi JSON để lưu vào CSV
        for field in ["image_urls", "variants", "detailed_info", "comments"]:
            if field in processed_product and processed_product[field]:
                processed_product[field] = json.dumps(processed_product[field], ensure_ascii=False)
            elif field not in processed_product:
                processed_product[field] = None
        processed_products.append(processed_product)

    with open(filename, mode="w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(processed_products)
    print(f"Saved {len(products)} products to '{filename}'.")