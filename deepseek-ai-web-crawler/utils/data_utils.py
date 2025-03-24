# data_utils.py
import csv
import json

from models.product import Product

def is_duplicate_product(product_url: str, seen_urls: set) -> bool:
    return product_url in seen_urls

def is_complete_product(product: dict, required_keys: list) -> bool:
    return all(key in product for key in required_keys)

# def save_products_to_csv(products: list, filename: str):
#     if not products:
#         print("No products to save.")
#         return

#     fieldnames = Product.model_fields.keys()
#     processed_products = []
#     for product in products:
#         processed_product = product.copy()
#         # Chuyển các trường phức tạp thành chuỗi JSON để lưu vào CSV
#         if "image_urls" in processed_product and processed_product["image_urls"]:
#             processed_product["image_urls"] = json.dumps(processed_product["image_urls"])
#         if "variants" in processed_product and processed_product["variants"]:
#             processed_product["variants"] = json.dumps(processed_product["variants"])
#         if "detailed_info" in processed_product and processed_product["detailed_info"]:
#             processed_product["detailed_info"] = json.dumps(processed_product["detailed_info"])
#         if "comments" in processed_product and processed_product["comments"]:
#             processed_product["comments"] = json.dumps(processed_product["comments"])
#         processed_products.append(processed_product)

#     with open(filename, mode="w", newline="", encoding="utf-8") as file:
#         writer = csv.DictWriter(file, fieldnames=fieldnames)
#         writer.writeheader()
#         writer.writerows(processed_products)
#     print(f"Saved {len(products)} products to '{filename}'.")