from pathlib import Path
import os
try:
    from dotenv import load_dotenv
except Exception:
    # If python-dotenv isn't installed, provide a no-op loader so imports don't fail.
    def load_dotenv(*args, **kwargs):
        return None

# Load .env from repository root if present, otherwise fall back to environment
HERE = Path(__file__).resolve()
REPO_ROOT = HERE.parents[1]
DOTENV_PATH = REPO_ROOT / ".env"
if DOTENV_PATH.exists():
    try:
        load_dotenv(dotenv_path=DOTENV_PATH)
    except Exception:
        # ignore dotenv problems at import time; environment variables may be set externally
        pass
else:
    try:
        load_dotenv()
    except Exception:
        pass

def get_env(key, default=None, required=False, cast=None):
    """Get an environment variable with optional casting and required check.

    Args:
        key (str): Environment variable name.
        default: Default value if env var not set.
        required (bool): If True, raise EnvironmentError when missing or empty.
        cast (callable): Optional callable to cast the value (e.g., int).
    Returns:
        The value or default, optionally casted.
    """
    val = os.getenv(key, default)
    if required and (val is None or val == ""):
        raise EnvironmentError(f"Required environment variable '{key}' is not set.")
    if val is not None and cast is not None:
        try:
            return cast(val)
        except Exception as e:
            raise ValueError(f"Failed to cast env var '{key}' to {cast}: {e}")
    return val

# Application settings
MONGO_URI = get_env("MONGO_URI", required=True)
