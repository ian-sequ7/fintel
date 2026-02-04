"""
Configuration loader.

Loads configuration from:
1. Default values (built-in)
2. TOML config file (fintel.toml or ~/.config/fintel/config.toml)
3. Environment variables (for secrets)

Priority: env vars > config file > defaults
"""

import logging
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from .schema import FintelConfig, ApiKeysConfig

logger = logging.getLogger(__name__)

# Config file search paths (in priority order)
CONFIG_PATHS = [
    Path("fintel.toml"),                          # Current directory
    Path(".fintel.toml"),                         # Hidden in current directory
    Path.home() / ".config" / "fintel" / "config.toml",  # User config
    Path("/etc/fintel/config.toml"),              # System config
]

# Environment variable prefix
ENV_PREFIX = "FINTEL_"


class ConfigError(Exception):
    """Configuration error with helpful message."""

    def __init__(self, message: str, source: str | None = None, field: str | None = None):
        self.source = source
        self.field = field
        super().__init__(message)

    def __str__(self) -> str:
        parts = [super().__str__()]
        if self.source:
            parts.append(f"Source: {self.source}")
        if self.field:
            parts.append(f"Field: {self.field}")
        return " | ".join(parts)


def _load_toml_file(path: Path) -> dict[str, Any]:
    """Load TOML file if it exists."""
    if not path.exists():
        return {}

    try:
        import tomllib
    except ImportError:
        # Python < 3.11 fallback
        try:
            import tomli as tomllib
        except ImportError:
            logger.warning(f"TOML library not available, skipping config file: {path}")
            return {}

    try:
        with open(path, "rb") as f:
            data = tomllib.load(f)
        logger.info(f"Loaded config from: {path}")
        return data
    except Exception as e:
        raise ConfigError(f"Failed to parse TOML: {e}", source=str(path))


def _find_config_file() -> Path | None:
    """Find the first existing config file."""
    for path in CONFIG_PATHS:
        if path.exists():
            return path
    return None


def _load_env_api_keys() -> dict[str, str | None]:
    """Load API keys from environment variables."""
    return {
        "alpha_vantage": os.environ.get(f"{ENV_PREFIX}ALPHA_VANTAGE_KEY"),
        "finnhub": os.environ.get(f"{ENV_PREFIX}FINNHUB_KEY"),
        "fred": os.environ.get(f"{ENV_PREFIX}FRED_KEY"),
        "polygon": os.environ.get(f"{ENV_PREFIX}POLYGON_KEY"),
        "quandl": os.environ.get(f"{ENV_PREFIX}QUANDL_KEY"),
    }


def _deep_merge(base: dict, override: dict) -> dict:
    """Deep merge two dictionaries."""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def load_config(config_path: Path | str | None = None) -> FintelConfig:
    """
    Load and validate configuration.

    Args:
        config_path: Explicit path to config file (optional)

    Returns:
        Validated FintelConfig

    Raises:
        ConfigError: If configuration is invalid
    """
    config_data: dict[str, Any] = {}

    # Load from config file
    if config_path:
        path = Path(config_path)
        if not path.exists():
            raise ConfigError(f"Config file not found: {path}", source=str(path))
        config_data = _load_toml_file(path)
    else:
        found_path = _find_config_file()
        if found_path:
            config_data = _load_toml_file(found_path)

    # Override API keys from environment
    env_keys = _load_env_api_keys()
    env_keys_filtered = {k: v for k, v in env_keys.items() if v is not None}
    if env_keys_filtered:
        if "api_keys" not in config_data:
            config_data["api_keys"] = {}
        config_data["api_keys"].update(env_keys_filtered)
        logger.debug(f"Loaded {len(env_keys_filtered)} API key(s) from environment")

    # Load additional env overrides
    if watchlist_env := os.environ.get(f"{ENV_PREFIX}WATCHLIST"):
        config_data["watchlist"] = [t.strip() for t in watchlist_env.split(",")]

    # Validate and create config
    try:
        config = FintelConfig(**config_data)
    except ValidationError as e:
        errors = e.errors()
        if errors:
            first_error = errors[0]
            field = ".".join(str(loc) for loc in first_error.get("loc", []))
            msg = first_error.get("msg", "Validation error")
            raise ConfigError(f"Invalid configuration: {msg}", field=field)
        raise ConfigError(f"Invalid configuration: {e}")

    return config


def validate_config(config: FintelConfig | None = None) -> tuple[bool, list[str]]:
    """
    Validate configuration at startup.

    Checks:
    - Required data directories exist or can be created
    - API keys are present if required features are enabled
    - Watchlist is not empty when using watchlist mode

    Args:
        config: Configuration to validate (defaults to current config)

    Returns:
        (is_valid, warnings) - True if critical checks pass, list of warnings/errors
    """
    if config is None:
        config = get_config()

    warnings = []
    errors = []

    # Check data directories
    project_root = Path(__file__).parent.parent
    data_dir = project_root / "data"
    cache_dir = data_dir / "cache"

    # Try to create directories if they don't exist
    for dir_path, name in [(data_dir, "data"), (cache_dir, "cache")]:
        if not dir_path.exists():
            try:
                dir_path.mkdir(parents=True, exist_ok=True)
                warnings.append(f"Created missing {name} directory: {dir_path}")
            except Exception as e:
                errors.append(f"ERROR: Cannot create {name} directory: {dir_path} - {e}")

    # Check watchlist when using watchlist mode
    if config.universe.source == "watchlist" and not config.watchlist:
        errors.append("ERROR: universe.source is 'watchlist' but watchlist is empty")

    # Check API keys for data sources that need them
    # WHY: FRED is used for macro data which is important for analysis
    if not config.api_keys.fred:
        warnings.append(
            "FRED API key not set (FINTEL_FRED_KEY). "
            "Macro indicators will not be available. "
            "Get key at: https://fred.stlouisfed.org/docs/api/api_key.html"
        )

    # WHY: Finnhub provides price/fundamental data, optional but useful
    if not config.api_keys.finnhub:
        warnings.append(
            "Finnhub API key not set (FINTEL_FINNHUB_KEY). "
            "Some price/fundamental data may be limited. "
            "Get key at: https://finnhub.io/register"
        )

    # Validate universe configuration
    if config.universe.source == "sector" and not config.universe.sectors:
        errors.append("ERROR: universe.source is 'sector' but no sectors specified")

    # Check max_tickers is reasonable
    if config.universe.max_tickers > 500:
        warnings.append(
            f"universe.max_tickers is high ({config.universe.max_tickers}). "
            "This may cause slow pipeline execution."
        )

    # Validate scoring weights sum to 1.0 (redundant with Pydantic but explicit check)
    weights = config.thresholds.scoring_weights
    total = (
        weights.valuation + weights.growth + weights.quality +
        weights.momentum + weights.analyst
    )
    if abs(total - 1.0) > 0.01:
        errors.append(f"ERROR: Scoring weights sum to {total}, must equal 1.0")

    # All errors are critical
    is_valid = len(errors) == 0

    return is_valid, errors + warnings


@lru_cache
def get_config() -> FintelConfig:
    """
    Get singleton configuration instance.

    Uses LRU cache to ensure config is loaded only once.
    """
    return load_config()


def reload_config(config_path: Path | str | None = None) -> FintelConfig:
    """
    Force reload configuration.

    Clears the cache and reloads from file/environment.
    """
    get_config.cache_clear()
    if config_path:
        # Load specific path and cache it
        config = load_config(config_path)
        # Replace the cached value
        get_config.cache_clear()
        return load_config(config_path)
    return get_config()
