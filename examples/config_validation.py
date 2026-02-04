#!/usr/bin/env python3
"""
Example: Using config validation at startup.

This shows how to use validate_config() to ensure your configuration
is valid before running pipelines or analysis.
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import get_config, validate_config

def main():
    """Example startup validation."""
    print("Loading configuration...")

    # Option 1: Validate the default config
    is_valid, messages = validate_config()

    # Option 2: Validate a specific config instance
    # config = get_config()
    # is_valid, messages = validate_config(config)

    if not is_valid:
        print("\n❌ Configuration validation FAILED:", file=sys.stderr)
        for msg in messages:
            if msg.startswith("ERROR"):
                print(f"  {msg}", file=sys.stderr)
        return 1

    print("✅ Configuration is valid")

    # Show warnings if any
    warnings = [m for m in messages if not m.startswith("ERROR")]
    if warnings:
        print("\n⚠️  Configuration warnings:")
        for msg in warnings:
            print(f"  {msg}")

    # Now safe to proceed with your application
    config = get_config()
    print(f"\nReady to run with {len(config.watchlist)} tickers")

    return 0

if __name__ == "__main__":
    sys.exit(main())
