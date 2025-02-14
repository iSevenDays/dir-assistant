"""Tests for the GitIgnoreManager class."""

import unittest
import os
import tempfile
import shutil
from pathlib import Path
from dir_assistant.assistant.gitignore_manager import GitIgnoreManager
from pathspec.gitignore import GitIgnoreSpec

class TestGitIgnoreManager(unittest.TestCase):
    """Test cases for gitignore file management."""
    
    def setUp(self):
        """Create a temporary directory structure with test files and .gitignore files."""
        self.test_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.test_dir)
        
    def _create_gitignore(self, rel_path: str, patterns: list[str]) -> str:
        """Create a .gitignore file with the given patterns.
        
        Args:
            rel_path: Directory to create .gitignore in (relative to test_dir)
            patterns: List of patterns to write to .gitignore
            
        Returns:
            Absolute path to the created .gitignore file
        """
        dir_path = os.path.join(self.test_dir, rel_path)
        os.makedirs(dir_path, exist_ok=True)
        gitignore_path = os.path.join(dir_path, '.gitignore')
        with open(gitignore_path, 'w') as f:
            f.write('\n'.join(patterns))
        return gitignore_path
        
    def test_load_single_gitignore(self):
        """Test loading patterns from a single .gitignore file."""
        patterns = [
            "*.pyc",
            "node_modules/",
            "!important.txt",
            "# comment",
            "",
            "dist/"
        ]
        self._create_gitignore("", patterns)  # Root .gitignore
        
        manager = GitIgnoreManager(self.test_dir)
        manager.load_patterns()
        
        # Verify patterns were loaded
        self.assertIn("", manager._specs)
        spec = manager._specs[""]
        
        # Test pattern matching
        self.assertTrue(spec.match_file("file.pyc"))
        self.assertTrue(spec.match_file("deep/file.pyc"))
        self.assertTrue(spec.match_file("node_modules/package.json"))
        self.assertFalse(spec.match_file("important.txt"))
        self.assertTrue(spec.match_file("dist/bundle.js"))
        
    def test_nested_gitignore_files(self):
        """Test loading patterns from nested .gitignore files."""
        # Root .gitignore
        root_patterns = ["*.log", "node_modules/"]
        self._create_gitignore("", root_patterns)
        
        # Nested .gitignore
        nested_patterns = ["*.pyc", "!important.pyc"]
        self._create_gitignore("src", nested_patterns)
        
        # Deep nested .gitignore
        deep_patterns = ["temp/", "!temp/keep.txt"]
        self._create_gitignore("src/lib", deep_patterns)
        
        manager = GitIgnoreManager(self.test_dir)
        manager.load_patterns()
        
        # Test root patterns
        is_ignored, definitive = manager.is_ignored("app.log")
        self.assertTrue(is_ignored)
        self.assertTrue(definitive)
        
        # Test nested patterns
        is_ignored, definitive = manager.is_ignored("src/module.pyc")
        self.assertTrue(is_ignored)
        self.assertTrue(definitive)
        
        is_ignored, definitive = manager.is_ignored("src/important.pyc")
        self.assertFalse(is_ignored)
        self.assertTrue(definitive)
        
        # Test deep nested patterns
        is_ignored, definitive = manager.is_ignored("src/lib/temp/file.txt")
        self.assertTrue(is_ignored)
        self.assertTrue(definitive)
        
        is_ignored, definitive = manager.is_ignored("src/lib/temp/keep.txt")
        self.assertFalse(is_ignored)
        self.assertTrue(definitive)
        
    def test_gitignore_precedence(self):
        """Test that more specific .gitignore files take precedence."""
        # Root .gitignore ignores all .txt files
        self._create_gitignore("", ["*.txt"])
        
        # Nested .gitignore allows specific .txt files
        self._create_gitignore("src", ["!important.txt"])
        
        # Another nested .gitignore re-ignores specific files
        self._create_gitignore("src/lib", ["important.txt"])
        
        manager = GitIgnoreManager(self.test_dir)
        manager.load_patterns()
        
        # Test pattern precedence
        is_ignored, definitive = manager.is_ignored("file.txt")
        self.assertTrue(is_ignored)
        self.assertTrue(definitive)
        
        is_ignored, definitive = manager.is_ignored("src/important.txt")
        self.assertFalse(is_ignored)
        self.assertTrue(definitive)
        
        is_ignored, definitive = manager.is_ignored("src/lib/important.txt")
        self.assertTrue(is_ignored)
        self.assertTrue(definitive)
        
    def test_case_sensitivity(self):
        """Test case-sensitive and case-insensitive pattern matching."""
        patterns = ['*.PYC']
        self._create_gitignore("", patterns)
        
        manager = GitIgnoreManager(self.test_dir, case_sensitive=True)
        manager.load_patterns()
        
        # Now, testing with a lowercase filename should not match
        is_ignored, is_definitive = manager.is_ignored('test.pyc')
        # In case-sensitive matching, 'test.pyc' does not match '*.PYC'
        self.assertFalse(is_ignored, "Expected 'test.pyc' not to be ignored with case-sensitive matching when pattern is '*.PYC'.")

        # However, if the filename case matches the pattern, it should match
        is_ignored, is_definitive = manager.is_ignored('test.PYC')
        self.assertTrue(is_ignored, "Expected 'test.PYC' to be ignored with matching case.")
        
        is_ignored, definitive = manager.is_ignored("src/important/file.txt")
        self.assertFalse(is_ignored, "Expected 'src/important/file.txt' not to be ignored as it does not match '*.PYC'")
        self.assertTrue(definitive)
        
        # Test case-insensitive matching
        manager = GitIgnoreManager(self.test_dir, case_sensitive=False)
        manager.load_patterns()
        
        is_ignored, definitive = manager.is_ignored("test.py")
        self.assertFalse(is_ignored, "Expected 'test.py' not to be ignored with case-insensitive matching when pattern is '*.PYC'")
        self.assertTrue(definitive)
        
        is_ignored, definitive = manager.is_ignored("test.PY")
        self.assertFalse(is_ignored, "Expected 'test.PY' not to be ignored with case-insensitive matching when pattern is '*.PYC'")
        self.assertTrue(definitive)
        
        is_ignored, definitive = manager.is_ignored("SRC/file.txt")
        self.assertFalse(is_ignored, "Expected 'SRC/file.txt' not to be ignored as it does not match '*.PYC'")
        self.assertTrue(definitive)
        
    def test_file_updates(self):
        """Test that changes to .gitignore files are detected."""
        gitignore_path = self._create_gitignore("", ["*.txt"])
        
        manager = GitIgnoreManager(self.test_dir)
        manager.load_patterns()
        
        # Initial state
        is_ignored, definitive = manager.is_ignored("file.txt")
        self.assertTrue(is_ignored)
        self.assertTrue(definitive)
        
        is_ignored, definitive = manager.is_ignored("important.txt")
        self.assertTrue(is_ignored)
        self.assertTrue(definitive)
        
        # Modify .gitignore
        with open(gitignore_path, 'w') as f:
            f.write("*.txt\n!important.txt")
            
        # Check that changes are detected
        self.assertTrue(manager.check_updates())
        
        # Verify new patterns are used
        is_ignored, definitive = manager.is_ignored("file.txt")
        self.assertTrue(is_ignored)
        self.assertTrue(definitive)
        
        is_ignored, definitive = manager.is_ignored("important.txt")
        self.assertFalse(is_ignored)
        self.assertTrue(definitive)
        
    def test_missing_gitignore(self):
        """Test handling of missing .gitignore files."""
        # Create and then delete a .gitignore file
        gitignore_path = self._create_gitignore("", ["*.txt"])
        
        manager = GitIgnoreManager(self.test_dir)
        manager.load_patterns()
        
        # Initial state
        is_ignored, definitive = manager.is_ignored("file.txt")
        self.assertTrue(is_ignored)
        self.assertTrue(definitive)
        
        # Delete .gitignore
        os.remove(gitignore_path)
        
        # Check that deletion is detected
        self.assertTrue(manager.check_updates())
        
        # Verify patterns are cleared
        is_ignored, definitive = manager.is_ignored("file.txt")
        self.assertFalse(is_ignored)
        self.assertFalse(definitive)


if __name__ == '__main__':
    unittest.main() 