#!/bin/bash
# Seed demo SQLite database with sample data

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
DB_PATH="$PROJECT_ROOT/backend/db/demo.sqlite"
SEED_SQL="$PROJECT_ROOT/backend/db/seed.sql"

echo "Seeding demo database at $DB_PATH..."

# Remove existing database if it exists
if [ -f "$DB_PATH" ]; then
    echo "Removing existing database..."
    rm "$DB_PATH"
fi

# Create database and schema
echo "Creating schema..."
sqlite3 "$DB_PATH" < "$SEED_SQL"

# Generate sample data using Python
echo "Generating sample data..."
python3 << PYTHON_SCRIPT
import sqlite3
import random
from datetime import datetime, timedelta
import os

db_path = "$DB_PATH"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Categories for products
categories = ['Electronics', 'Clothing', 'Books', 'Home', 'Sports', 'Toys', 'Food', 'Health']

# Generate users (50k)
print("Generating users...")
users_data = []
for i in range(50000):
    email = f"user{i}@example.com"
    name = f"User {i}"
    status = random.choice(['active', 'inactive', 'suspended'])
    created_at = datetime.now() - timedelta(days=random.randint(0, 365))
    users_data.append((email, name, status, created_at))

cursor.executemany(
    "INSERT INTO users (email, name, status, created_at) VALUES (?, ?, ?, ?)",
    users_data
)

# Generate products (10k)
print("Generating products...")
products_data = []
for i in range(10000):
    sku = f"SKU-{i:06d}"
    name = f"Product {i}"
    category = random.choice(categories)
    price_cents = random.randint(1000, 50000)  # $10 to $500
    created_at = datetime.now() - timedelta(days=random.randint(0, 180))
    products_data.append((sku, name, category, price_cents, created_at))

cursor.executemany(
    "INSERT INTO products (sku, name, category, price_cents, created_at) VALUES (?, ?, ?, ?, ?)",
    products_data
)

# Generate orders (100k)
print("Generating orders...")
orders_data = []
for i in range(100000):
    user_id = random.randint(1, 50000)
    created_at = datetime.now() - timedelta(days=random.randint(0, 365))
    total_cents = random.randint(1000, 100000)  # $10 to $1000
    status = random.choice(['pending', 'completed', 'cancelled', 'shipped'])
    orders_data.append((user_id, created_at, total_cents, status))

cursor.executemany(
    "INSERT INTO orders (user_id, created_at, total_cents, status) VALUES (?, ?, ?, ?)",
    orders_data
)

# Generate order items (300k)
print("Generating order items...")
order_items_data = []
for i in range(300000):
    order_id = random.randint(1, 100000)
    product_id = random.randint(1, 10000)
    quantity = random.randint(1, 5)
    # Get product price
    cursor.execute("SELECT price_cents FROM products WHERE id = ?", (product_id,))
    result = cursor.fetchone()
    price_cents = result[0] if result else random.randint(1000, 50000)
    order_items_data.append((order_id, product_id, quantity, price_cents))

cursor.executemany(
    "INSERT INTO order_items (order_id, product_id, quantity, price_cents) VALUES (?, ?, ?, ?)",
    order_items_data
)

conn.commit()
conn.close()

print("Database seeded successfully!")
print("Total rows:")
print("  Users: 50,000")
print("  Products: 10,000")
print("  Orders: 100,000")
print("  Order Items: 300,000")
PYTHON_SCRIPT

echo "Demo database seeded successfully at $DB_PATH"

