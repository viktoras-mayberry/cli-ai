from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("mayai")
except PackageNotFoundError:  # pragma: no cover
    # Package metadata isn't available in editable/uninstalled contexts.
    __version__ = "0.0.0"
