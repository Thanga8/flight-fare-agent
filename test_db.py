import sqlite3

connection = sqlite3.connect("data/flights.db")

cursor = connection.cursor()

cursor.execute(
    """
    SELECT name
    FROM sqlite_master
    WHERE type = 'table'
    """
)

tables = cursor.fetchall()

print("Tables:")

for table in tables:
    print(f"- {table[0]}")

connection.close()