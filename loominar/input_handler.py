import os
import sys

VALID_FORMATS = ("word", "excel", "csv")

# Prompt text -> CLI flag, used to explain what is missing in headless mode.
_REQUIRED = (
    ("url", "Enter SonarQube server URL (e.g., http://localhost:9000): ", "-u/--url or SONAR_URL"),
    ("token", "Enter SonarQube API token: ", "-t/--token or SONAR_TOKEN"),
    ("project", "Enter SonarQube project key: ", "-p/--project or SONAR_PROJECT"),
)


class MissingInputError(Exception):
    """Raised when a required value is absent and no one can be asked for it."""


def _interactive() -> bool:
    """input() only works when a human is attached to stdin."""
    try:
        return sys.stdin is not None and sys.stdin.isatty()
    except (AttributeError, ValueError):
        return False


def get_user_inputs(cli_defaults=None):
    cli_defaults = cli_defaults or {}
    # --no-confirm means "never block". Without a TTY, prompting would hang the
    # pipeline forever instead of failing with a usable message.
    headless = bool(cli_defaults.get("no_confirm")) or not _interactive()

    def get_value(prompt_text, key, default=None, flag=None):
        value = cli_defaults.get(key)
        if value:
            return value
        if headless:
            if default is not None:
                return default
            raise MissingInputError(
                f"Missing required value '{key}'. Pass {flag or key} "
                "(running non-interactively, so it cannot be prompted for)."
            )
        return input(prompt_text).strip() or default

    sonar_url = get_value(_REQUIRED[0][1], "url", flag=_REQUIRED[0][2])
    sonar_token = get_value(_REQUIRED[1][1], "token", flag=_REQUIRED[1][2])
    project_key = get_value(_REQUIRED[2][1], "project", flag=_REQUIRED[2][2])

    output_format = str(
        get_value("Enter output format (word / excel / csv) [excel]: ", "format", "excel")
    ).lower().strip()
    if output_format not in VALID_FORMATS:
        raise MissingInputError(
            f"Unsupported format '{output_format}'. Choose one of: {', '.join(VALID_FORMATS)}."
        )

    verbosity = int(cli_defaults.get("verbosity", 2))

    # Default output dir: Documents/Loominar
    default_dir = os.path.join(os.path.expanduser("~"), "Documents", "Loominar")
    output_dir = get_value(
        f"Enter output directory (leave blank for {default_dir}): ", "output", default_dir
    )
    os.makedirs(output_dir, exist_ok=True)

    return {
        "sonar_url": str(sonar_url).strip().rstrip("/"),
        "sonar_token": str(sonar_token).strip(),
        "project_key": str(project_key).strip(),
        "format": output_format,
        "verbosity": verbosity,
        "output_dir": output_dir,
        "no_confirm": bool(cli_defaults.get("no_confirm", False)),
        "large_warn": bool(cli_defaults.get("large_warn", False)),
        "split_by": cli_defaults.get("split_by") or None,
        "inline_limit": int(cli_defaults.get("inline_limit", 10000)),
        "keep_temp": bool(cli_defaults.get("keep_temp", False)),
        "headless": headless,
    }
