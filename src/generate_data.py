"""
RetailIQ - Synthetic Retail Data Generator
Generates realistic retail data with deliberate scenarios:
- Imminent stock-outs & low stock
- Overstocked products
- Slow-moving products
- Sales spikes & drops
- Store performance variations
- Zero stock edge case
"""

import os
import random
from datetime import datetime, timedelta
import pandas as pd
import numpy as np

# Set fixed seed for reproducibility
random.seed(42)
np.random.seed(42)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

# Reference date (current timeline)
END_DATE = datetime(2026, 9, 5)
START_DATE = END_DATE - timedelta(days=60)

def generate_stores():
    stores = [
        {
            "store_id": "S001",
            "store_name": "RetailIQ Flagship - Downtown",
            "city": "Seattle",
            "state": "WA",
            "store_type": "Flagship",
            "opened_date": "2022-01-15"
        },
        {
            "store_id": "S002",
            "store_name": "RetailIQ Metro - West End",
            "city": "Portland",
            "state": "OR",
            "store_type": "Urban",
            "opened_date": "2022-06-01"
        },
        {
            "store_id": "S003",
            "store_name": "RetailIQ Suburban - Oakridge",
            "city": "Bellevue",
            "state": "WA",
            "store_type": "Suburban",
            "opened_date": "2023-03-10"
        },
        {
            "store_id": "S004",
            "store_name": "RetailIQ Express - Airport",
            "city": "SeaTac",
            "state": "WA",
            "store_type": "Express Kiosk",
            "opened_date": "2023-08-20"
        }
    ]
    df = pd.DataFrame(stores)
    df.to_csv(os.path.join(DATA_DIR, "stores.csv"), index=False)
    print(f"Generated {len(df)} stores -> stores.csv")
    return df

def generate_products():
    # Note: Deliberately omitting unit_cost/margin per hackathon no-guessing requirement!
    products = [
        {"product_id": "P001", "product_name": "Wireless Mouse M20", "category": "Electronics", "unit_price": 29.99, "reorder_point": 20, "target_stock": 60},
        {"product_id": "P002", "product_name": "Mechanical Keyboard Pro", "category": "Electronics", "unit_price": 89.99, "reorder_point": 15, "target_stock": 45},
        {"product_id": "P003", "product_name": "USB-C Multiport Hub", "category": "Electronics", "unit_price": 39.99, "reorder_point": 25, "target_stock": 75},
        {"product_id": "P004", "product_name": "Noise-Cancelling Headphones H5", "category": "Electronics", "unit_price": 149.99, "reorder_point": 10, "target_stock": 30},
        {"product_id": "P005", "product_name": "Ergonomic Desk Chair Mat", "category": "Office Supplies", "unit_price": 49.99, "reorder_point": 10, "target_stock": 25},
        {"product_id": "P006", "product_name": "Adjustable Laptop Stand", "category": "Office Supplies", "unit_price": 34.99, "reorder_point": 15, "target_stock": 40},
        {"product_id": "P007", "product_name": "Gel Pen 10-Pack Black", "category": "Office Supplies", "unit_price": 9.99, "reorder_point": 30, "target_stock": 100},
        {"product_id": "P008", "product_name": "Hardcover Spiral Notebook", "category": "Office Supplies", "unit_price": 12.99, "reorder_point": 25, "target_stock": 80},
        {"product_id": "P009", "product_name": "Braided USB-C Cable 2m", "category": "Accessories", "unit_price": 14.99, "reorder_point": 35, "target_stock": 120},
        {"product_id": "P010", "product_name": "Magnetic Phone Car Mount", "category": "Accessories", "unit_price": 19.99, "reorder_point": 20, "target_stock": 50},
        {"product_id": "P011", "product_name": "Desk Pad Leatherette 90x40cm", "category": "Accessories", "unit_price": 24.99, "reorder_point": 15, "target_stock": 40},
        {"product_id": "P012", "product_name": "Smart LED Desk Lamp", "category": "Home & Lifestyle", "unit_price": 59.99, "reorder_point": 12, "target_stock": 35},
        {"product_id": "P013", "product_name": "Insulated Stainless Steel Tumbler", "category": "Home & Lifestyle", "unit_price": 22.99, "reorder_point": 20, "target_stock": 60},
        {"product_id": "P014", "product_name": "Ultrasonic Essential Oil Diffuser", "category": "Home & Lifestyle", "unit_price": 32.99, "reorder_point": 10, "target_stock": 30},
        {"product_id": "P015", "product_name": "Cable Management Sleeve Kit", "category": "Accessories", "unit_price": 11.99, "reorder_point": 20, "target_stock": 50},
    ]
    df = pd.DataFrame(products)
    df.to_csv(os.path.join(DATA_DIR, "products.csv"), index=False)
    print(f"Generated {len(df)} products -> products.csv")
    return df

def generate_sales(stores_df, products_df):
    sales_records = []
    tx_counter = 10001
    
    total_days = (END_DATE - START_DATE).days + 1
    
    # Store multiplier for realistic disparity
    store_weights = {
        "S001": 1.8,  # Flagship: very high traffic
        "S002": 1.1,  # Urban: medium-high
        "S003": 0.8,  # Suburban: steady
        "S004": 0.5   # Express: selective commuter items
    }
    
    # Base daily velocity per product
    product_base_sales = {
        "P001": 3.8,  # Wireless Mouse: high volume
        "P002": 1.5,  # Mechanical Keyboard: moderate
        "P003": 2.5,  # USB-C Hub: moderate, will spike
        "P004": 0.9,  # Headphones: premium, lower unit velocity
        "P005": 0.3,  # Chair Mat: slow moving
        "P006": 1.6,  # Laptop stand: steady
        "P007": 4.5,  # Gel Pens: high volume
        "P008": 3.0,  # Notebook: steady
        "P009": 5.0,  # Braided Cable: high volume
        "P010": 2.2,  # Phone Mount: steady
        "P011": 1.2,  # Desk Pad: steady
        "P012": 1.0,  # LED Lamp: moderate
        "P013": 2.8,  # Tumbler: high/steady
        "P014": 0.25, # Essential Oil Diffuser: very slow moving
        "P015": 1.8,  # Cable kit: steady
    }
    
    prices = dict(zip(products_df["product_id"], products_df["unit_price"]))
    
    for day_offset in range(total_days):
        current_date = START_DATE + timedelta(days=day_offset)
        date_str = current_date.strftime("%Y-%m-%d")
        
        # Scenario: Days remaining in window
        days_from_end = (END_DATE - current_date).days
        
        for store_id in stores_df["store_id"]:
            s_mult = store_weights[store_id]
            
            for prod_id in products_df["product_id"]:
                base_lambda = product_base_sales[prod_id] * s_mult
                
                # Airport express carries fewer office supplies / lamps
                if store_id == "S004" and prod_id in ["P005", "P012", "P014"]:
                    base_lambda *= 0.1
                
                # SCENARIO 1: Sales Spike for P003 (USB-C Hub) in last 10 days
                if prod_id == "P003" and days_from_end <= 10:
                    base_lambda *= 3.2
                
                # SCENARIO 2: Sales Drop for P002 (Mechanical Keyboard) in last 14 days
                if prod_id == "P002" and days_from_end <= 14:
                    base_lambda *= 0.25
                
                # Poisson distributed sales count for this day
                qty_sold = np.random.poisson(base_lambda)
                
                if qty_sold > 0:
                    # Break into 1-3 transactions
                    chunks = []
                    remaining = qty_sold
                    while remaining > 0:
                        take = min(remaining, random.choice([1, 2, 3]))
                        chunks.append(take)
                        remaining -= take
                        
                    for chunk_qty in chunks:
                        unit_p = prices[prod_id]
                        total_amt = round(chunk_qty * unit_p, 2)
                        sales_records.append({
                            "transaction_id": f"TX{tx_counter}",
                            "date": date_str,
                            "store_id": store_id,
                            "product_id": prod_id,
                            "quantity": chunk_qty,
                            "unit_price": unit_p,
                            "total_amount": total_amt
                        })
                        tx_counter += 1
                        
    df = pd.DataFrame(sales_records)
    df.to_csv(os.path.join(DATA_DIR, "sales.csv"), index=False)
    print(f"Generated {len(df)} sales transactions -> sales.csv (Revenue: ${df['total_amount'].sum():,.2f})")
    return df

def generate_inventory(stores_df, products_df):
    """
    Generate current stock levels with deliberate scenarios:
    - P001 (Wireless Mouse) at S001: Stock 18 (daily sales ~4.2 -> ~4.3 days left, Imminent stock-out)
    - P009 (Braided Cable) at S001: Stock 14 (daily sales ~5.5 -> ~2.5 days left, Critical stock-out)
    - P004 (Headphones) at S002: Stock 4 (daily sales ~1.0 -> ~4 days left)
    - P005 (Desk Chair Mat) at S003: Stock 95 (target 25, daily sales ~0.24 -> ~395 days left, Overstocked!)
    - P014 (Oil Diffuser) at S004: Stock 80 (target 30, airport kiosk with near-zero sales, Overstocked & Slow-moving!)
    - P011 (Desk Pad) at S004: Stock 0 (Zero stock edge case)
    - Others: healthy balanced stock between 25 and 110 units
    """
    inventory_records = []
    
    # Deliberate specific stock settings
    deliberate_stock = {
        ("S001", "P001"): (18, "2026-08-15"),  # Wireless Mouse: Low stock / Imminent stock-out (~4.3 days)
        ("S001", "P009"): (14, "2026-08-10"),  # Braided Cable: Critical stock-out (~2.5 days)
        ("S002", "P004"): (4,  "2026-08-18"),  # Noise Cancelling Headphones: Low stock
        ("S003", "P005"): (95, "2026-07-01"),  # Desk Chair Mat: Severe Overstock & Slow moving
        ("S004", "P014"): (80, "2026-06-15"),  # Oil Diffuser: Severe Overstock at Airport kiosk
        ("S004", "P011"): (0,  "2026-07-20"),  # Desk Pad: Out of stock (0 stock)
    }
    
    for store_id in stores_df["store_id"]:
        for prod_id in products_df["product_id"]:
            if (store_id, prod_id) in deliberate_stock:
                stock_qty, restock_dt = deliberate_stock[(store_id, prod_id)]
            else:
                # Normal healthy stock levels around target
                target = int(products_df.loc[products_df["product_id"] == prod_id, "target_stock"].values[0])
                stock_qty = max(15, int(np.random.normal(target, target * 0.2)))
                restock_dt = (END_DATE - timedelta(days=random.randint(5, 25))).strftime("%Y-%m-%d")
                
            inventory_records.append({
                "store_id": store_id,
                "product_id": prod_id,
                "current_stock": stock_qty,
                "last_restocked_date": restock_dt
            })
            
    df = pd.DataFrame(inventory_records)
    df.to_csv(os.path.join(DATA_DIR, "inventory.csv"), index=False)
    print(f"Generated {len(df)} inventory records -> inventory.csv")
    return df

if __name__ == "__main__":
    print("=== Generating RetailIQ Synthetic Retail Dataset ===")
    stores = generate_stores()
    products = generate_products()
    sales = generate_sales(stores, products)
    inventory = generate_inventory(stores, products)
    print("=== Dataset Generation Complete ===")
