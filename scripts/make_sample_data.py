"""Create (or reset) the two small sample tables in data/.

The data is made up. A fixed random seed means everyone gets identical files.

Run:  python scripts/make_sample_data.py
"""

import csv
import os
import random
from datetime import date, timedelta

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")

PRODUCTS = [
    ("P-001", "Steel Bolt M8", "Hardware", 0.45),
    ("P-002", "Steel Bolt M10", "Hardware", 0.60),
    ("P-003", "Hex Nut M8", "Hardware", 0.12),
    ("P-004", "Copper Wire 2.5mm (100m)", "Electrical", 38.00),
    ("P-005", "Circuit Breaker 16A", "Electrical", 9.50),
    ("P-006", "LED Panel 40W", "Electrical", 24.00),
    ("P-007", "PVC Pipe 1in (3m)", "Plumbing", 4.20),
    ("P-008", "Ball Valve 1in", "Plumbing", 7.80),
    ("P-009", "Safety Helmet", "Safety", 12.50),
    ("P-010", "Safety Gloves (pair)", "Safety", 3.40),
    ("P-011", "Hi-Vis Vest", "Safety", 5.90),
    ("P-012", "Cordless Drill 18V", "Tools", 89.00),
    ("P-013", "Angle Grinder 115mm", "Tools", 54.00),
    ("P-014", "Measuring Tape 5m", "Tools", 6.75),
    ("P-015", "Cement Bag 50kg", "Building", 7.10),
]
REGIONS = ["North", "South", "East", "West", "Central"]
REPS = ["A. Sharma", "B. Iyer", "C. Reddy", "D. Mehta", "E. Khan", "F. Das"]
STATUSES = ["Delivered", "Delivered", "Delivered", "Shipped", "Pending", "Cancelled"]


def write(path, header, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(rows)
    print(f"wrote {os.path.relpath(path)} ({len(rows)} rows)")


def main():
    rng = random.Random(42)
    os.makedirs(DATA_DIR, exist_ok=True)

    products = []
    for pid, name, category, price in PRODUCTS:
        products.append([pid, name, category, f"{price:.2f}", rng.randint(0, 2000), rng.choice(["Yes", "Yes", "No"])])
    write(
        os.path.join(DATA_DIR, "sample_products.csv"),
        ["product_id", "product_name", "category", "unit_price", "stock_qty", "active"],
        products,
    )

    orders = []
    start = date(2026, 1, 1)
    for i in range(1, 501):
        pid, name, category, price = rng.choice(PRODUCTS)
        qty = rng.randint(1, 250)
        status = rng.choice(STATUSES)
        notes = "" if rng.random() < 0.8 else rng.choice(["Urgent", "Call before delivery", "Partial shipment"])
        orders.append(
            [
                f"SO-{i:05d}",
                (start + timedelta(days=rng.randint(0, 300))).isoformat(),
                rng.choice(REGIONS),
                pid,
                name,
                qty,
                f"{price:.2f}",
                f"{qty * price:.2f}",
                rng.choice(REPS),
                status,
                notes,
            ]
        )
    write(
        os.path.join(DATA_DIR, "sample_sales_orders.csv"),
        ["order_id", "order_date", "region", "product_id", "product_name", "quantity",
         "unit_price", "total", "sales_rep", "status", "notes"],
        orders,
    )


if __name__ == "__main__":
    main()
