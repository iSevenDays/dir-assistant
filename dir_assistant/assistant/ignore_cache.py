"""Module for caching ignore pattern results."""

from typing import Dict, Optional

class IgnoreCache:
    """Handles caching of ignore pattern matching results."""
    
    def __init__(self):
        """Initialize the cache."""
        self._cache: Dict[str, bool] = {}
        
    def get(self, key: str) -> Optional[bool]:
        """Get a cached result.
        
        Args:
            key: Cache key to look up
            
        Returns:
            Cached boolean result or None if not found
        """
        return self._cache.get(key)
        
    def set(self, key: str, value: bool) -> None:
        """Set a cache entry.
        
        Args:
            key: Cache key to set
            value: Boolean result to cache
        """
        self._cache[key] = value
        
    def clear(self) -> None:
        """Clear all cached results."""
        self._cache.clear()
        
    @staticmethod
    def create_key(path: str, dir_context: str, case_sensitive: bool) -> str:
        """Create a cache key for the given parameters.
        
        Args:
            path: The path being checked
            dir_context: The directory context for gitignore evaluation
            case_sensitive: Whether case-sensitive matching is being used
            
        Returns:
            A string key combining all parameters
        """
        # Normalize path for consistent cache keys
        path = path.replace('\\', '/')
        dir_context = dir_context.replace('\\', '/')
        
        # Include case sensitivity in key
        if not case_sensitive:
            path = path.lower()
            dir_context = dir_context.lower()
            
        return f"{path}:{dir_context}:{case_sensitive}" 