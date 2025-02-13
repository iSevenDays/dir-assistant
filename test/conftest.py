import warnings
import pytest

def pytest_configure(config):
    """Configure pytest to ignore specific deprecation warnings."""
    # Register custom markers
    config.addinivalue_line(
        "markers",
        "interactive: mark test as interactive (requires manual intervention and/or API keys)"
    )

    # Warning filters
    warnings.filterwarnings("ignore", category=DeprecationWarning, module="numpy.core")
    warnings.filterwarnings("ignore", category=DeprecationWarning, module="importlib._bootstrap")
    warnings.filterwarnings("ignore", category=DeprecationWarning, module="faiss.loader")
    warnings.filterwarnings("ignore", category=DeprecationWarning, module="faiss.swigfaiss")
    warnings.filterwarnings("ignore", category=DeprecationWarning, module="numpy.core.numeric")
    warnings.filterwarnings("ignore", category=DeprecationWarning, module="numpy.core.fromnumeric")

    # These warnings are from faiss using deprecated NumPy internals
    config.addinivalue_line(
        "filterwarnings",
        "ignore:numpy.core._multiarray_umath is deprecated:DeprecationWarning"
    )
    # These warnings are from SWIG-generated code in faiss
    config.addinivalue_line(
        "filterwarnings",
        "ignore:builtin type SwigPyPacked has no __module__ attribute:DeprecationWarning"
    )
    config.addinivalue_line(
        "filterwarnings",
        "ignore:builtin type SwigPyObject has no __module__ attribute:DeprecationWarning"
    )
    config.addinivalue_line(
        "filterwarnings",
        "ignore:builtin type swigvarlink has no __module__ attribute:DeprecationWarning"
    ) 