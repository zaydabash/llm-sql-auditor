import React from 'react';

interface Example {
    name: string;
    dialect: 'postgres' | 'sqlite';
    schema: string;
    queries: string;
}

const EXAMPLES: Example[] = [
    {
        name: 'Postgres: Missing Indexes',
        dialect: 'postgres',
        schema: `CREATE TABLE users (
  id SERIAL PRIMARY KEY,
  email VARCHAR(255) UNIQUE NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- @rows=100000
CREATE TABLE orders (
  id SERIAL PRIMARY KEY,
  user_id INTEGER REFERENCES users(id),
  status VARCHAR(50),
  amount DECIMAL(10, 2),
  order_date DATE
);`,
        queries: `SELECT * FROM orders WHERE user_id = 123 AND status = 'pending';

---

SELECT u.email, COUNT(o.id) 
FROM users u 
JOIN orders o ON u.id = o.user_id 
WHERE o.order_date > '2023-01-01'
GROUP BY u.email;`
    },
    {
        name: 'SQLite: N+1 and Full Table Scans',
        dialect: 'sqlite',
        schema: `CREATE TABLE products (
  id INTEGER PRIMARY KEY,
  name TEXT,
  category_id INTEGER
);

CREATE TABLE categories (
  id INTEGER PRIMARY KEY,
  name TEXT
);`,
        queries: `SELECT * FROM products WHERE category_id IN (SELECT id FROM categories WHERE name = 'Electronics');

---

SELECT p.*, c.name as category_name 
FROM products p 
LEFT JOIN categories c ON p.category_id = c.id;`
    }
];

interface ExampleQueriesProps {
    onSelect: (example: Example) => void;
}

export default function ExampleQueries({ onSelect }: ExampleQueriesProps) {
    return (
        <div className="mb-6">
            <label className="block text-sm font-medium text-gray-700 mb-2">
                Try an Example
            </label>
            <div className="flex flex-wrap gap-2">
                {EXAMPLES.map((example) => (
                    <button
                        key={example.name}
                        type="button"
                        onClick={() => onSelect(example)}
                        className="inline-flex items-center px-3 py-1.5 border border-gray-300 shadow-sm text-xs font-medium rounded-full text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
                    >
                        {example.name}
                    </button>
                ))}
            </div>
        </div>
    );
}
