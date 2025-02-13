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
                 base_dir: Optional[str] = None,
                 case_sensitive: bool = False):
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
        if use_git_ignore:
            # Walk directory tree and find all .gitignore files
            for root, dirs, files in os.walk(self.base_dir):
                if self.GITIGNORE_FILE in files:
                    gitignore_path = os.path.join(root, self.GITIGNORE_FILE)
                    try:
                        with open(gitignore_path, 'r') as f:
                            # Add patterns with path relative to base_dir
                            rel_path = os.path.relpath(root, self.base_dir)
                            for line in f:
                                line = line.strip()
                                if line and not line.startswith('#'):
                                    # Make pattern relative to base_dir
                                    if rel_path != '.':
                                        pattern = os.path.join(rel_path, line)
                                        pattern = pattern.replace('\\', '/')
                                        self.patterns.append(pattern)
                                    else:
                                        self.patterns.append(line)
                    except IOError as e:
                        logger.error(f"Failed to read {gitignore_path}: {e}")
        
        # Initialize PathSpec with all patterns
        self._spec = PathSpec.from_lines(GitWildMatchPattern, self.patterns)
        self.case_sensitive = case_sensitive

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
            
        # Handle case sensitivity
        if not self.case_sensitive:
            rel_path = rel_path.lower()
            # Create case-insensitive patterns if needed
            patterns = [p.lower() for p in self.patterns]
            spec = PathSpec.from_lines(GitWildMatchPattern, patterns)
            return spec.match_file(rel_path)
            
        # Use original PathSpec for case-sensitive matching
        return self._spec.match_file(rel_path)
