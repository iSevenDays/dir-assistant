"""Module for managing .gitignore files and their patterns."""

import os
from typing import Dict, List, Tuple, Optional
from pathspec import PathSpec
from pathspec.patterns import GitWildMatchPattern
from pathspec.gitignore import GitIgnoreSpec
import re

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
                patterns = [line.rstrip() for line in f if line.rstrip() and not line.startswith('#')]

            if patterns:
                rel_dir = os.path.dirname(os.path.relpath(gitignore_path, self.base_dir))
                if rel_dir == '.':
                    rel_dir = ''
                # Create a new PathSpec with patterns in the order they appear
                spec = GitIgnoreSpec.from_lines(patterns)
                # Adjust each pattern's regex based on desired case sensitivity
                for pattern in spec.patterns:
                    if pattern.regex:
                        regex_str = pattern.regex.pattern
                        if self.case_sensitive:
                            # Remove 'i' from any inline flags so that matching becomes case sensitive
                            def repl(m):
                                flags = m.group(1)
                                new_flags = flags.replace('i', '')
                                return f"(?{new_flags}:"

                            regex_str = re.sub(r'\(\?([^:]+):', repl, regex_str)
                            pattern.regex = re.compile(regex_str)
                        else:
                            pattern.regex = re.compile(regex_str, re.IGNORECASE)
                self._specs[rel_dir] = spec
                self._mtimes[gitignore_path] = os.path.getmtime(gitignore_path)
        except (IOError, OSError):
            pass
        
    def check_updates(self) -> bool:
        """Check if any .gitignore files have been modified.
        
        Returns:
            True if any files were modified and reloaded
        """
        updated = False
        # Remove deleted .gitignore files (and clear their entries)
        for gitignore_path in list(self._mtimes.keys()):
            if not os.path.exists(gitignore_path):
                rel_dir = os.path.dirname(os.path.relpath(gitignore_path, self.base_dir))
                if rel_dir == '.':
                    rel_dir = ''
                self._mtimes.pop(gitignore_path)
                if rel_dir in self._specs:
                    del self._specs[rel_dir]
                updated = True
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
        norm_path = os.path.normpath(path).replace("\\", "/")

        # Build list of directories from root to file's parent
        path_parts = norm_path.split("/")
        check_dirs = [""]
        current = ""
        if len(path_parts) > 1:
            for part in path_parts[:-1]:
                current = os.path.join(current, part) if current else part
                check_dirs.append(current)

        result = None
        # Check each directory's patterns in order, from root to most specific
        for dir_path in check_dirs:
            if dir_path in self._specs:
                # Get the path relative to this gitignore's directory
                rel_path = norm_path
                if dir_path:
                    if not norm_path.startswith(dir_path + "/"):
                        continue
                    rel_path = norm_path[len(dir_path)+1:]
                
                # Check each pattern in this .gitignore
                for pattern in self._specs[dir_path].patterns:
                    test_string = rel_path if "/" in pattern.pattern else os.path.basename(rel_path)
                    if pattern.pattern.endswith('/') and not test_string.endswith('/'):
                        test_string += '/'
                    if pattern.regex and pattern.regex.search(test_string):
                        result = pattern.include
        
        if result is None:
            if self._specs:
                return (False, True)
            else:
                return (False, False)
        return (result, True) 