# Configuration System

> **The Discogs Intelligence Platform uses a central, typed configuration system for application-wide settings.**

The configuration system provides one source of truth for values that would otherwise be hard-coded throughout the application.

---

# Purpose

Central configuration improves:

- Maintainability
- Consistency
- Validation
- Portability between environments
- Future extensibility

Application code should read shared settings from the configuration package rather than defining duplicate constants.

---

# Structure

Configuration is stored in:

```text
config/
├── __init__.py
└── settings.py
```

`settings.py` defines an immutable `Settings` dataclass and a `load_settings()` function.

The loaded settings object is exposed as:

```python
from config import SETTINGS
```

---

# Current Settings

Version 0.1 currently includes:

- Application name
- Application version
- Database path
- Discogs request delay
- Default window width
- Default window height

Example usage:

```python
from config import SETTINGS

print(SETTINGS.application_name)
print(SETTINGS.application_version)
print(SETTINGS.database_path)
```

---

# Default Values

The configuration system provides defaults suitable for local desktop use.

Current defaults include:

```text
Application name: Discogs Intelligence Platform
Application version: 0.1-dev
Database filename: discogs_intelligence.db
Discogs request delay: 1.08 seconds
Window width: 1380
Window height: 820
```

Defaults are defined in `config/settings.py`.

---

# Environment Variable Overrides

Selected settings may be overridden with environment variables.

Supported variables include:

```text
DIP_APPLICATION_NAME
DIP_APPLICATION_VERSION
DIP_DATABASE_FILENAME
DIP_DISCOGS_REQUEST_DELAY_SECONDS
DIP_WINDOW_WIDTH
DIP_WINDOW_HEIGHT
```

Example:

```bash
DIP_WINDOW_WIDTH=1600 python3 app.py
```

Environment overrides are useful for:

- Development
- Testing
- Different machines
- Temporary configuration changes

---

# Validation

Configuration values are validated when settings are loaded.

Examples include:

- Discogs request delay must not be negative.
- Window width must be at least 800.
- Window height must be at least 500.

Invalid configuration raises a clear error during application startup rather than causing unpredictable behaviour later.

---

# Secrets

Sensitive values must not be stored in committed configuration.

This includes:

- Discogs access tokens
- API secrets
- Passwords
- Private credentials

The Discogs token remains session-specific and is requested at runtime.

Future secrets handling should continue to keep sensitive values outside source control.

---

# Adding a New Setting

To introduce a new application setting:

1. Add a typed field to the `Settings` dataclass.
2. Load the value in `load_settings()`.
3. Provide a safe default.
4. Add validation where appropriate.
5. Add an environment-variable override when useful.
6. Update this document.
7. Replace any existing hard-coded usages.

Example:

```python
@dataclass(frozen=True)
class Settings:
    report_directory: Path
```

---

# Design Principles

The configuration system should remain:

- Typed
- Immutable
- Explicit
- Lightweight
- Easy to understand
- Free from unnecessary dependencies

Configuration logic should remain outside the user interface.

---

# Future Enhancements

Potential future settings include:

- Default currency
- Report output directory
- Logging level
- API timeout
- Refresh limits
- Scheduled analysis options
- Export preferences

Persistent user preferences and a graphical settings screen are outside the scope of Version 0.1.

---

# Guiding Principle

Application-wide settings should have one clear source of truth.

Hard-coded values should only remain where they are genuinely fixed implementation details.

---

## Document Information

Version: 1.0

Status: Active

Owner: Russell Friend