from app import run_search

from flight_search.reporting.report_builder import (
    build_console_report,
)

report = run_search(False)

console_report = build_console_report(
    report
)

print()

print("=" * 70)
print("REPORT BUILDER TEST")
print("=" * 70)

print()

print(console_report.keys())

print()

print(
    len(
        console_report["results"]
    )
)

print()

print(
    console_report["results"][0]["recommendation"]
)