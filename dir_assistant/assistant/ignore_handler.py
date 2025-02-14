"""Module for handling file ignoring based on patterns and .gitignore files."""

import os
from typing import List, Optional
from pathspec import PathSpec
from pathspec.patterns import GitWildMatchPattern
from .gitignore_manager import GitIgnoreManager

class IgnoreHandler:
    """Handles file ignoring based on patterns and .gitignore files."""
    
    DEFAULT_IGNORE_FILE = ".dirassistantignore"
    
    def __init__(self, patterns=None, base_dir=None, use_git_ignore=False, case_sensitive=False):
        """Initialize the IgnoreHandler.
        
        Args:
            patterns: List of ignore patterns or path to ignore file
            base_dir: Base directory for relative paths
            use_git_ignore: Whether to also load and respect .gitignore files
            case_sensitive: Whether to use case-sensitive pattern matching (False by default, following git behavior)
        """
        self.base_dir = base_dir or "."
        self.use_git_ignore = use_git_ignore
        self.case_sensitive = case_sensitive
        self._specs = {}
        
        if patterns:
            if not case_sensitive:
                patterns = [p.lower() if isinstance(p, str) else p for p in patterns]
            self._specs[self.base_dir] = PathSpec.from_lines(GitWildMatchPattern, patterns)
        
        # Initialize components
        self._cache = {}  # Changed from IgnoreCache() to a simple dict
        self._gitignore_manager = GitIgnoreManager(self.base_dir, self.case_sensitive) if self.use_git_ignore else None
        
        # Load gitignore patterns if enabled
        if self._gitignore_manager:
            self._gitignore_manager.load_patterns()
                
    def is_ignored(self, path):
        """Check if a path should be ignored based on the patterns."""
        if not self._specs and not self._gitignore_manager:
            return False

        # Normalize path for consistent matching
        path = os.path.normpath(path).replace("\\", "/")
        if not self.case_sensitive:
            path = path.lower()
        
        # Check if gitignore files have been modified
        if self._gitignore_manager and self._gitignore_manager.check_updates():
            self._cache.clear()  # Clear cache if gitignore files changed
        
        # Check cache first
        cache_key = f"{path}:{self.case_sensitive}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        # Check gitignore patterns first - these take precedence over explicit patterns
        if self._gitignore_manager:
            is_ignored, is_definitive = self._gitignore_manager.is_ignored(path)
            if is_definitive:
                self._cache[cache_key] = is_ignored
                return is_ignored

        # Match against explicit patterns
        is_ignored = False
        # Sort specs by directory depth (root first)
        sorted_specs = sorted(self._specs.items(), key=lambda x: len(x[0].split('/')))
        for dir_path, spec in sorted_specs:
            # Check if any pattern matches
            for pattern in spec.patterns:
                if pattern.regex.search(path):
                    is_ignored = pattern.include
                    # If this is a negation pattern, it's definitive
                    if not pattern.include:
                        self._cache[cache_key] = is_ignored
                        return is_ignored

        self._cache[cache_key] = is_ignored
        return is_ignored

    def add_patterns(self, patterns, dir_path=None):
        """Add new ignore patterns for a specific directory."""
        if not patterns:
            return

        dir_path = dir_path or self.base_dir
        if not self.case_sensitive:
            patterns = [p.lower() if isinstance(p, str) else p for p in patterns]
        self._specs[dir_path] = PathSpec.from_lines(GitWildMatchPattern, patterns)
        self._cache.clear()  # Clear cache when patterns change

    @property
    def patterns(self) -> List[str]:
        """Get all active ignore patterns.
        
        Returns:
            List of ignore patterns from both explicit patterns and .gitignore files
        """
        patterns = []
        
        # Add explicit patterns
        if self._specs:
            for spec in self._specs.values():
                patterns.extend(str(pattern) for pattern in spec.patterns)
            
        # Add gitignore patterns
        if self._gitignore_manager:
            for spec in self._gitignore_manager._specs.values():
                patterns.extend(str(pattern) for pattern in spec.patterns)
                
        return patterns
