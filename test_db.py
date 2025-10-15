#!/usr/bin/env python3
"""
Test database operations
"""

import sqlite3
import json
import os

def create_test_database():
    """Create a test SQLite database"""
    db_path = "test.db"
    
    # Remove existing database
    if os.path.exists(db_path):
        os.remove(db_path)
    
    # Create new database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Create tables
    cursor.execute('''
        CREATE TABLE users (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT UNIQUE,
            age INTEGER
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE products (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            price REAL,
            category TEXT
        )
    ''')
    
    # Insert sample data
    users_data = [
        (1, 'Alice Johnson', 'alice@example.com', 28),
        (2, 'Bob Smith', 'bob@example.com', 34),
        (3, 'Charlie Brown', 'charlie@example.com', 25),
        (4, 'Diana Prince', 'diana@example.com', 30)
    ]
    
    products_data = [
        (1, 'Laptop', 999.99, 'Electronics'),
        (2, 'Mouse', 29.99, 'Electronics'),
        (3, 'Book', 19.99, 'Education'),
        (4, 'Chair', 149.99, 'Furniture')
    ]
    
    cursor.executemany('INSERT INTO users VALUES (?, ?, ?, ?)', users_data)
    cursor.executemany('INSERT INTO products VALUES (?, ?, ?, ?)', products_data)
    
    conn.commit()
    conn.close()
    
    print(f"✅ Test database created: {db_path}")
    print("📊 Tables created: users, products")
    print("📊 Sample data inserted")

def test_database_queries():
    """Test some database queries"""
    conn = sqlite3.connect("test.db")
    cursor = conn.cursor()
    
    print("\n🔍 Testing database queries:")
    
    # List all users
    cursor.execute("SELECT * FROM users")
    users = cursor.fetchall()
    print(f"\n👥 Users ({len(users)} rows):")
    for user in users:
        print(f"  ID: {user[0]}, Name: {user[1]}, Email: {user[2]}, Age: {user[3]}")
    
    # List all products
    cursor.execute("SELECT * FROM products")
    products = cursor.fetchall()
    print(f"\n🛍️ Products ({len(products)} rows):")
    for product in products:
        print(f"  ID: {product[0]}, Name: {product[1]}, Price: ${product[2]}, Category: {product[3]}")
    
    # Complex query
    cursor.execute("""
        SELECT u.name, p.name as product_name, p.price 
        FROM users u 
        CROSS JOIN products p 
        WHERE p.category = 'Electronics'
        ORDER BY u.name, p.price
    """)
    complex_result = cursor.fetchall()
    print(f"\n🔗 Complex query result ({len(complex_result)} rows):")
    for row in complex_result:
        print(f"  User: {row[0]}, Product: {row[1]}, Price: ${row[2]}")
    
    conn.close()

if __name__ == "__main__":
    create_test_database()
    test_database_queries()
