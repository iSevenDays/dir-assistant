"""Module for handling ignore patterns using pathspec.

This module provides a wrapper around pathspec for handling gitignore-style pattern matching.
"""
import os
import logging
from pathlib import Path
from typing import List, Optional, Union

from pathspec import PathSpec
from pathspec.patterns.gitwildmatch import GitWildMatchPattern

logger = logging.getLogger(__name__)

class IgnoreHandler:
    """Handles file/directory ignore patterns using gitignore syntax.
    
    This class provides a wrapper around pathspec's PathSpec for pattern matching.
    It supports loading patterns from files or direct pattern lists.
    
    Attributes:
        DEFAULT_IGNORE_FILE: Name of the default ignore file to look for.
        GITIGNORE_FILE: Name of git's ignore file.
        base_dir: Base directory for resolving relative paths.
        patterns: List of ignore patterns.
    """
    
    DEFAULT_IGNORE_FILE = ".dirassistantignore"
    GITIGNORE_FILE = ".gitignore"
    
    def __init__(self, 
                 ignore_paths: Optional[Union[List[str], str]] = None,
                 use_git_ignore: bool = False,
                 base_dir: Optional[str] = None):
        """Initialize the IgnoreHandler.
        
        Args:
            ignore_paths: List of patterns or path to ignore file
            use_git_ignore: Whether to respect .gitignore files
            base_dir: Base directory for resolving relative paths
        """
        self.base_dir = os.path.abspath(base_dir) if base_dir else os.getcwd()
        self.patterns: List[str] = []
        self.use_git_ignore = use_git_ignore
        self._spec = None  # Cache for PathSpec object
        
        # Load patterns from ignore_paths
        if ignore_paths:
            if isinstance(ignore_paths, str) and os.path.isfile(ignore_paths):
                try:
                    with open(ignore_paths, 'r') as f:
                        self.patterns.extend(
                            self._normalize_pattern(line) for line in f
                            if line.strip() and not line.startswith('#')
                        )
                except IOError as e:
                    logger.error(f"Failed to read ignore file {ignore_paths}: {e}")
            else:
                self.patterns.extend(
                    self._normalize_pattern(p) for p in ignore_paths if p.strip()
                )
                
        # Load patterns from gitignore if enabled
        if use_git_ignore and os.path.isfile(os.path.join(self.base_dir, self.GITIGNORE_FILE)):
            try:
                with open(os.path.join(self.base_dir, self.GITIGNORE_FILE)) as f:
                    self.patterns.extend(line.strip() for line in f
                                      if line.strip() and not line.startswith('#'))
            except IOError as e:
                logger.error(f"Failed to read .gitignore: {e}")
        
        # Initialize PathSpec with all patterns
        self._spec = PathSpec.from_lines(GitWildMatchPattern, self.patterns)

    def _normalize_pattern(self, pattern: str) -> str:
        """Normalize a pattern for consistent matching."""
        # Convert to forward slashes
        pattern = pattern.replace("\\", "/")
        # Remove leading/trailing whitespace
        pattern = pattern.strip()
        # Handle special cases
        if pattern.startswith("./"):
            pattern = pattern[2:]
        if pattern.endswith("/"):
            pattern = pattern[:-1]
        return pattern

    def is_ignored(self, path: str, base_dir: Optional[str] = None) -> bool:
        """Check if a path should be ignored.
        
        Args:
            path: Path to check
            base_dir: Optional base directory for resolving relative paths
            
        Returns:
            True if path matches any ignore pattern, False otherwise
        """
        check_dir = os.path.abspath(base_dir) if base_dir else self.base_dir
        
        # Get relative path from base directory
        if not os.path.isabs(path):
            path = os.path.join(check_dir, path)
            
        try:
            rel_path = os.path.relpath(path, check_dir)
        except ValueError:
            return False
            
        # Normalize path for matching
        rel_path = rel_path.replace("\\", "/").strip("/")
        if not rel_path:
            return False
            
        # Use PathSpec for matching
        return self._spec.match_file(rel_path)
