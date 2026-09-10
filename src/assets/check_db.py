import sqlite3
import pandas as pd

conn = sqlite3.connect("database/products.db")
q = "SELECT color, SUM(qty_delta * unit_price) as total_sales FROM transactions WHERE action='sale' GROUP BY color ORDER BY total_sales ASC LIMIT 5"
print(pd.read_sql_query(q, conn).to_string())
conn.close()
