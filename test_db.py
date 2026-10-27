"""Print configured database tables for a local diagnostic."""

from flight_search.database.db import list_database_tables

print("Tables:")
for table in list_database_tables():
    print(f"- {table}")
