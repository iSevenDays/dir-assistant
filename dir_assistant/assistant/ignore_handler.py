"""Module for handling file ignoring based on patterns and .gitignore files."""

import os
import logging
from typing import List, Optional
from pathspec import PathSpec
from pathspec.patterns import GitWildMatchPattern
from pathspec.gitignore import GitIgnoreSpec
from .gitignore_manager import GitIgnoreManager

logger = logging.getLogger(__name__)

class IgnoreHandler:
    """Handles file ignoring based on patterns and .gitignore files."""
    
    def __init__(self, patterns=None, base_dir=None, use_git_ignore=False, case_sensitive=False, debug=False):
        """Initialize the IgnoreHandler.
        
        Args:
            patterns: List of ignore patterns or path to ignore file
            base_dir: Base directory for relative paths
            use_git_ignore: Whether to also load and respect .gitignore files
            case_sensitive: Whether to use case-sensitive pattern matching (False by default, following git behavior)
            debug: Whether to enable debug logging
        """
        self.base_dir = base_dir or "."
        self.use_git_ignore = use_git_ignore
        self.case_sensitive = case_sensitive
        self._specs = {}
        self.debug = debug

        # Process the patterns to ensure they work across directories
        processed_patterns = self._preprocess_patterns(patterns)

        # If patterns is a string pointing to a file, load its contents
        if processed_patterns and isinstance(processed_patterns, str):
            # Make sure we use absolute path for the ignore file
            patterns_path = os.path.join(self.base_dir, processed_patterns) if not os.path.isabs(processed_patterns) else processed_patterns
            if os.path.isfile(patterns_path):
                with open(patterns_path, 'r') as f:
                    lines = f.readlines()
                # Filter out empty lines and comments
                processed_patterns = [line.strip() for line in lines if line.strip() and not line.strip().startswith('#')]

        # Create the pattern spec with appropriate case sensitivity
        if processed_patterns:
            if self.case_sensitive:
                # Use PathSpec directly with GitWildMatchPattern for case-sensitive matching
                from pathspec import PathSpec
                patterns_obj = PathSpec.from_lines(
                    GitWildMatchPattern, processed_patterns
                )
                self._specs[self.base_dir] = patterns_obj
            else:
                # Use GitIgnoreSpec for standard case-insensitive git behavior
                self._specs[self.base_dir] = GitIgnoreSpec.from_lines(processed_patterns)
                
            if self.debug:
                logger.debug(f"Initialized ignore patterns for {self.base_dir}: {processed_patterns}")

        # Initialize components
        self._cache = {}  # Changed from IgnoreCache() to a simple dict
        self._gitignore_manager = GitIgnoreManager(self.base_dir, self.case_sensitive) if self.use_git_ignore else None
        
        # Load gitignore patterns if enabled
        if self._gitignore_manager:
            self._gitignore_manager.load_patterns()
                
    def _preprocess_patterns(self, patterns):
        """Process patterns to make them work consistently across directories.
        
        This ensures patterns like ".editorconfig" are matched regardless of directory level.
        
        Args:
            patterns: List of patterns or path to patterns file
            
        Returns:
            Processed list of patterns
        """
        if not patterns:
            return []
            
        # If patterns is a string (file path), return it as is
        if isinstance(patterns, str):
            return patterns
            
        # Process list of patterns
        processed = []
        for pattern in patterns:
            # Skip patterns that are already directory-independent
            if pattern.startswith("**/"):
                processed.append(pattern)
                continue
                
            # If pattern is a root-level hidden file/directory (like .git, .editorconfig)
            if pattern.startswith(".") and "/" not in pattern:
                # Add both patterns - one for root level, one for any directory
                processed.append(pattern)
                processed.append(f"**/{pattern}")
                if self.debug:
                    logger.debug(f"Preprocessed pattern {pattern} to also include **/{pattern}")
            else:
                processed.append(pattern)
                
        return processed
                
    def is_ignored(self, path):
        """Check if a path should be ignored based on the patterns."""
        if not self._specs and not self._gitignore_manager:
            return False

        # Normalize path for consistent matching
        norm_path = os.path.normpath(path).replace("\\", "/")
        
        # For case-insensitive matching, convert to lowercase
        search_path = norm_path.lower() if not self.case_sensitive else norm_path
        
        # Always check basename for hidden files at any directory level
        basename = os.path.basename(norm_path)
        search_basename = basename.lower() if not self.case_sensitive else basename
        all_patterns = [p.pattern for p in self._get_all_patterns()]
        
        # Get case-normalized patterns for matching
        pattern_list = []
        for p in all_patterns:
            if not self.case_sensitive:
                pattern_list.append(p.lower())
            else:
                pattern_list.append(p)
        
        # Fast path for basename matches (especially for dot files)
        if search_basename.startswith(".") and search_basename in pattern_list:
            if self.debug:
                logger.debug(f"Fast path match: {basename} is in pattern list, ignoring {norm_path}")
            return True
        
        # Check if gitignore files have been modified
        if self._gitignore_manager and self._gitignore_manager.check_updates():
            self._cache.clear()  # Clear cache if gitignore files changed
        
        # Check cache first
        cache_key = f"{norm_path}:{self.case_sensitive}"
        if cache_key in self._cache:
            if self.debug:
                logger.debug(f"Cache hit for {norm_path}: {self._cache[cache_key]}")
            return self._cache[cache_key]

        # Check gitignore patterns first - these take precedence over explicit patterns
        if self._gitignore_manager:
            is_ignored_git, is_definitive = self._gitignore_manager.is_ignored(norm_path)
            if is_definitive:
                self._cache[cache_key] = is_ignored_git
                if self.debug:
                    logger.debug(f"GitIgnore match for {norm_path}: {is_ignored_git}")
                return is_ignored_git
                
        # Import re module for regex handling
        import re

        # Match against explicit patterns
        is_ignored = False
        matched_by = None
        # Sort specs by directory depth (root first)
        sorted_specs = sorted(self._specs.items(), key=lambda x: len(x[0].split('/')))
        for dir_path, spec in sorted_specs:
            for pattern in spec.patterns:
                # Determine test string: use full path if pattern contains '/', else basename
                test_string = search_path if '/' in pattern.pattern else search_basename
                
                # Extract pattern string and whether it's a negation
                pattern_string = pattern.pattern
                is_negation = pattern_string.startswith('!')
                
                # Remove ! for negation patterns during comparison
                if is_negation:
                    pattern_string = pattern_string[1:]
                    
                # Convert pattern string to lowercase for case-insensitive matching
                if not self.case_sensitive:
                    pattern_string = pattern_string.lower()
                
                # If pattern ends with '/' but test_string does not, append '/'
                if pattern_string.endswith('/') and not test_string.endswith('/'):
                    test_string = test_string + '/'
                
                # Create case-insensitive regex pattern if needed
                if pattern.regex:
                    matches = False
                    if not self.case_sensitive:
                        try:
                            case_insensitive_pattern = re.compile(pattern.regex.pattern, re.IGNORECASE)
                            matches = bool(case_insensitive_pattern.search(test_string))
                        except re.error:
                            # Fallback to normal regex if error occurs
                            matches = bool(pattern.regex.search(test_string))
                    else:
                        matches = bool(pattern.regex.search(test_string))
                        
                    if matches:
                        is_ignored = pattern.include
                        matched_by = pattern.pattern
                        if self.debug:
                            logger.debug(f"Pattern match: {pattern.pattern} on {test_string} -> {is_ignored}")
        
        self._cache[cache_key] = is_ignored
        return is_ignored
    
    def _get_all_patterns(self):
        """Get all patterns from all specs.
        
        Returns:
            List of all pattern objects
        """
        all_patterns = []
        for spec in self._specs.values():
            all_patterns.extend(spec.patterns)
        return all_patterns

    def add_patterns(self, patterns, dir_path=None):
        """Add new ignore patterns for a specific directory."""
        if not patterns:
            return

        dir_path = dir_path or self.base_dir
        self._specs[dir_path] = GitIgnoreSpec.from_lines(patterns)
        self._cache.clear()  # Clear cache when patterns change
        if self.debug:
            logger.debug(f"Added patterns for {dir_path}: {patterns}")

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
