"""Module for handling file ignoring based on patterns and .gitignore files."""

import os
from typing import List, Optional
from pathspec import PathSpec
from pathspec.patterns import GitWildMatchPattern
from pathspec.gitignore import GitIgnoreSpec
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

        # If patterns is a string pointing to a file, load its contents
        if patterns and isinstance(patterns, str) and os.path.isfile(patterns):
            with open(patterns, 'r') as f:
                lines = f.readlines()
            # Filter out empty lines and comments
            patterns = [line.strip() for line in lines if line.strip() and not line.strip().startswith('#')]

        if patterns:
            self._specs[self.base_dir] = GitIgnoreSpec.from_lines(patterns)

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
        
        # Check if gitignore files have been modified
        if self._gitignore_manager and self._gitignore_manager.check_updates():
            self._cache.clear()  # Clear cache if gitignore files changed
        
        # Check cache first
        cache_key = f"{path}:{self.case_sensitive}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        # Check gitignore patterns first - these take precedence over explicit patterns
        if self._gitignore_manager:
            is_ignored_git, is_definitive = self._gitignore_manager.is_ignored(path)
            if is_definitive:
                self._cache[cache_key] = is_ignored_git
                return is_ignored_git

        # Match against explicit patterns
        is_ignored = False
        # Sort specs by directory depth (root first)
        sorted_specs = sorted(self._specs.items(), key=lambda x: len(x[0].split('/')))
        for dir_path, spec in sorted_specs:
            for pattern in spec.patterns:
                # Determine test string: use full path if pattern contains '/', else basename
                test_string = path if '/' in pattern.pattern else os.path.basename(path)
                # If pattern ends with '/' but test_string does not, append '/'
                if pattern.pattern.endswith('/') and not test_string.endswith('/'):
                    test_string = test_string + '/'
                if pattern.regex and pattern.regex.search(test_string):
                    is_ignored = pattern.include
        
        self._cache[cache_key] = is_ignored
        return is_ignored

    def add_patterns(self, patterns, dir_path=None):
        """Add new ignore patterns for a specific directory."""
        if not patterns:
            return

        dir_path = dir_path or self.base_dir
        self._specs[dir_path] = GitIgnoreSpec.from_lines(patterns)
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
