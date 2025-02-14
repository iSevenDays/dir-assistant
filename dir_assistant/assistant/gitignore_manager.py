"""Module for managing .gitignore files and their patterns."""

import os
from typing import Dict, List, Tuple, Optional
from pathspec import PathSpec
from pathspec.patterns import GitWildMatchPattern

class GitIgnoreManager:
    """Manages .gitignore files and their patterns."""
    
    def __init__(self, base_dir=".", case_sensitive=False):
        """Initialize the GitIgnore manager.
        
        Args:
            base_dir: Base directory to search for .gitignore files
            case_sensitive: Whether to use case-sensitive pattern matching (False by default, following git behavior)
        """
        self.base_dir = os.path.abspath(base_dir)
        self.case_sensitive = case_sensitive
        self._specs = {}
        self._mtimes = {}
        
    def load_patterns(self) -> None:
        """Load patterns from all .gitignore files in the directory tree."""
        self._specs.clear()
        self._mtimes.clear()
        for root, _, files in os.walk(self.base_dir):
            if ".gitignore" in files:
                gitignore_path = os.path.join(root, ".gitignore")
                self._load_gitignore(gitignore_path)
                    
    def _load_gitignore(self, gitignore_path: str) -> None:
        """Load patterns from a specific .gitignore file.
        
        Args:
            gitignore_path: Path to the .gitignore file
        """
        try:
            with open(gitignore_path, 'r') as f:
                patterns = []
                for line in f:
                    line = line.rstrip()
                    if line and not line.startswith('#'):
                        if not self.case_sensitive:
                            line = line.lower()
                        patterns.append(line)

            if patterns:
                rel_dir = os.path.dirname(os.path.relpath(gitignore_path, self.base_dir))
                if rel_dir == '.':
                    rel_dir = ''
                # Create a new PathSpec with patterns in the order they appear
                self._specs[rel_dir] = PathSpec.from_lines(GitWildMatchPattern, patterns)
                self._mtimes[gitignore_path] = os.path.getmtime(gitignore_path)
        except (IOError, OSError):
            pass
        
    def check_updates(self) -> bool:
        """Check if any .gitignore files have been modified.
        
        Returns:
            True if any files were modified and reloaded
        """
        updated = False
        for root, _, files in os.walk(self.base_dir):
            if ".gitignore" in files:
                gitignore_path = os.path.join(root, ".gitignore")
                try:
                    mtime = os.path.getmtime(gitignore_path)
                    if gitignore_path not in self._mtimes or mtime > self._mtimes[gitignore_path]:
                        self._load_gitignore(gitignore_path)
                        updated = True
                except (IOError, OSError):
                    pass
        return updated
        
    def is_ignored(self, path: str) -> Tuple[bool, bool]:
        """Check if a path should be ignored based on .gitignore rules.
        
        Args:
            path: Path to check (relative to base_dir)
            
        Returns:
            Tuple[bool, bool]: (is_ignored, is_definitive)
            - is_ignored: True if path should be ignored
            - is_definitive: True if this is a definitive answer
        """
        # Normalize path for consistent matching
        norm_path = os.path.normpath(path).replace("\\", "/")
        if not self.case_sensitive:
            norm_path = norm_path.lower()

        result = None
        definitive = False

        # Build list of directories from root to file's parent
        path_parts = norm_path.split("/")
        check_dirs = [""]
        current = ""
        if len(path_parts) > 1:
            for part in path_parts[:-1]:
                current = os.path.join(current, part) if current else part
                check_dirs.append(current)

        # Evaluate patterns in each relevant .gitignore, applying patterns relative to their directory
        for dir_path in check_dirs:
            if dir_path in self._specs:
                spec = self._specs[dir_path]
                # Determine the relative path for patterns in this directory
                rel_path = norm_path if dir_path == "" else (norm_path[len(dir_path)+1:] if norm_path.startswith(dir_path + "/") else None)
                if rel_path is None:
                    continue
                for pattern in spec.patterns:
                    if pattern.regex.search(rel_path):
                        result = pattern.include
                        definitive = True
        if result is None:
            return (False, False)
        return (result, definitive) 