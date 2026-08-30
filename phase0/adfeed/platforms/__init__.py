"""Ad platform modules: google / meta / tiktok (isolated packages)."""

# Importing subpackages registers them on the registry.
from adfeed.platforms import google as _google  # noqa: F401
from adfeed.platforms import meta as _meta  # noqa: F401
from adfeed.platforms import tiktok as _tiktok  # noqa: F401
