# scripts/catalog_stats.py
"""Print a human summary of the loaded catalog (no PyRIT needed)."""
from collections import Counter

from agentic_redteam.catalog.loader import load_catalog


def main():
    cat = load_catalog()
    print(f"plugins:    {len(cat.plugins)}")
    print(f"strategies: {len(cat.strategies)}")
    print(f"presets:    {len(cat.presets)}  -> {sorted(cat.presets)}")
    print("\nby group:")
    for group, items in sorted(cat.plugins_by_group().items()):
        print(f"  {group:28} {len(items)}")
    print("\nby plugin_type:", dict(Counter(p.plugin_type.value for p in cat.plugins.values())))
    print("by rubric_kind:", dict(Counter(p.rubric_kind.value for p in cat.plugins.values())))
    print("runnable now:", sum(p.runnable for p in cat.plugins.values()), "/ 157")


if __name__ == "__main__":
    main()
