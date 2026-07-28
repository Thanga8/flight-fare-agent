from search_history import (
    compare_with_previous_search,
)


result = compare_with_previous_search(
    origin="HYD",
    destination="MOW",
    current_price=63610,
)


print()
print("=" * 70)
print("PREVIOUS SEARCH PRICE COMPARISON")
print("=" * 70)

for key, value in result.items():

    print(
        f"{key}: {value}"
    )

print()
print("=" * 70)