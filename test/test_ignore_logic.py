import unittest
import os
import tempfile
import shutil
from pathlib import Path
from dir_assistant.assistant.ignore_handler import IgnoreHandler
from dir_assistant.assistant.index import preprocess_ignore_patterns


class TestIgnoreLogic(unittest.TestCase):
    def setUp(self):
        """Create a temporary directory structure for testing."""
        self.test_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.test_dir)

    def test_basic_ignore_patterns(self):
        """Test basic ignore patterns using standard gitignore rules"""
        test_cases = [
            # Python specific ignores
            ("src/__pycache__/module.pyc", "__pycache__/", True),
            ("project/test.pyc", "*.py[cod]", True),
            ("src/normal.py", "*.py[cod]", False),
            
            # Distribution/packaging
            ("build/output.txt", "build/", True),
            ("dist/bundle.js", "dist/", True),
            ("src/lib/module.py", "lib/", True),
            ("src/regular/file.txt", "dist/", False),
            
            # Coverage reports
            ("htmlcov/index.html", "htmlcov/", True),
            (".coverage", ".coverage", True),
            ("tests/coverage.xml", "coverage.xml", True),
            
            # Absolute paths
            (os.path.join(os.path.abspath(self.test_dir), "dist/file.txt"), "dist/", True),
            (os.path.join(os.path.abspath(self.test_dir), "src/file.txt"), "dist/", False),
        ]
        for path, pattern, expected in test_cases:
            with self.subTest(path=path, pattern=pattern):
                handler = IgnoreHandler([pattern], base_dir=self.test_dir)
                self.assertEqual(handler.is_ignored(path), expected)

    def test_gitignore_hierarchy(self):
        """Test that .gitignore files in different directories work correctly."""
        # Create test directory structure
        root_gitignore = os.path.join(self.test_dir, ".gitignore")
        frontend_dir = os.path.join(self.test_dir, "frontend")
        frontend_gitignore = os.path.join(frontend_dir, ".gitignore")
        backend_dir = os.path.join(self.test_dir, "backend")
        backend_gitignore = os.path.join(backend_dir, ".gitignore")
        nested_dir = os.path.join(frontend_dir, "src", "components")
        nested_gitignore = os.path.join(nested_dir, ".gitignore")

        os.makedirs(frontend_dir, exist_ok=True)
        os.makedirs(backend_dir, exist_ok=True)
        os.makedirs(nested_dir, exist_ok=True)

        # Create .gitignore files with standard patterns
        with open(root_gitignore, 'w') as f:
            f.write("*.py[cod]\ndist/\nbuild/\n")
        
        with open(frontend_gitignore, 'w') as f:
            f.write("coverage.xml\n.coverage\n*.egg-info/\n")
            
        with open(backend_gitignore, 'w') as f:
            f.write("__pycache__/\n.tox/\n.nox/\n")
            
        with open(nested_gitignore, 'w') as f:
            f.write("*.manifest\n*.spec\n.hypothesis/\n")

        handler = IgnoreHandler(base_dir=self.test_dir, use_git_ignore=True)
        
        # Test root patterns
        self.assertTrue(handler.is_ignored("test.pyc"))
        self.assertTrue(handler.is_ignored("dist/bundle.js"))
        self.assertFalse(handler.is_ignored("src/valid.py"))
        
        # Test frontend patterns
        self.assertTrue(handler.is_ignored("frontend/coverage.xml"))
        self.assertTrue(handler.is_ignored("frontend/package.egg-info/"))
        self.assertFalse(handler.is_ignored("frontend/src/valid.js"))
        
        # Test backend patterns
        self.assertTrue(handler.is_ignored("backend/__pycache__/cache.pyc"))
        self.assertTrue(handler.is_ignored("backend/.tox/env"))
        self.assertFalse(handler.is_ignored("backend/src/valid.py"))
        
        # Test nested patterns
        self.assertTrue(handler.is_ignored("frontend/src/components/app.manifest"))
        self.assertTrue(handler.is_ignored("frontend/src/components/.hypothesis/"))
        self.assertFalse(handler.is_ignored("frontend/src/components/valid.js"))

    def test_gitignore_precedence(self):
        """Test that .gitignore precedence rules are followed correctly."""
        # Create test directory structure
        root_gitignore = os.path.join(self.test_dir, ".gitignore")
        subdir = os.path.join(self.test_dir, "python_pkg")
        sub_gitignore = os.path.join(subdir, ".gitignore")
        
        os.makedirs(subdir, exist_ok=True)
        
        # Root .gitignore ignores all .pyc files
        with open(root_gitignore, 'w') as f:
            f.write("*.py[cod]\n")
            
        # Subdirectory .gitignore negates specific .pyc file
        with open(sub_gitignore, 'w') as f:
            f.write("!important.pyc\n")
            
        handler = IgnoreHandler(base_dir=self.test_dir, use_git_ignore=True)
        
        # Test precedence
        self.assertTrue(handler.is_ignored("test.pyc"))
        self.assertTrue(handler.is_ignored("python_pkg/test.pyc"))
        self.assertFalse(handler.is_ignored("python_pkg/important.pyc"))
        
        # Test with coverage files
        with open(root_gitignore, 'a') as f:
            f.write("\n.coverage\n")
            
        with open(sub_gitignore, 'a') as f:
            f.write("\n!.coverage\n")
            
        # Reload patterns
        handler = IgnoreHandler(base_dir=self.test_dir, use_git_ignore=True)
        
        self.assertTrue(handler.is_ignored(".coverage"))
        self.assertFalse(handler.is_ignored("python_pkg/.coverage"))

    def test_glob_patterns(self):
        """Test that glob patterns in .gitignore files work correctly."""
        test_cases = [
            # Python bytecode patterns
            ("*.py[cod]", [
                ("test.pyc", True),
                ("module.pyo", True),
                ("cache.pyd", True),
                ("test.py", False),
            ]),
            
            # Distribution patterns
            ("*.egg-info/", [
                ("package.egg-info/", True),
                ("pkg.egg-info/setup.py", True),
                ("my.egg-info.txt", False),
            ]),
            
            # Coverage patterns
            (".coverage.*", [
                (".coverage.xml", True),
                (".coverage.html", True),
                ("coverage.txt", False),
            ]),
            
            # Test reports
            ("*.py,cover", [
                ("test.py,cover", True),
                ("module.py,cover", True),
                ("test.pycover", False),
            ]),
        ]
        
        for pattern, cases in test_cases:
            with self.subTest(pattern=pattern):
                handler = IgnoreHandler([pattern], base_dir=self.test_dir)
                for path, expected in cases:
                    with self.subTest(path=path):
                        self.assertEqual(
                            handler.is_ignored(path),
                            expected,
                            f"Pattern '{pattern}' failed for path '{path}'"
                        )

    def test_case_sensitivity(self):
        """Test case-sensitive and case-insensitive pattern matching."""
        # Using a pattern with uppercase, expecting case sensitive behavior
        handler = IgnoreHandler(patterns=['*.PYC'], case_sensitive=True)
        # 'test.pyc' does not match '*.PYC' in a case-sensitive match
        self.assertFalse(handler.is_ignored('test.pyc'), "Expected 'test.pyc' not to be ignored with case-sensitive matching when pattern is '*.PYC'.")
        # 'test.PYC' should match
        self.assertTrue(handler.is_ignored('test.PYC'), "Expected 'test.PYC' to be ignored with matching case.")

    def test_ignore_file_loading(self):
        """Test loading patterns from an ignore file"""
        # Use a generic ignore file for testing pattern loading
        ignore_file = os.path.join(self.test_dir, "test.ignore")
        with open(ignore_file, 'w') as f:
            f.write("# Comment line\n")
            f.write("*.pyc\n")
            f.write("node_modules/\n")
            f.write("!important.pyc\n")
            f.write("\n")  # Empty line
            f.write("dist/\n")
        
        handler = IgnoreHandler(ignore_file, base_dir=self.test_dir)
        
        # Test the loaded patterns
        self.assertTrue(handler.is_ignored("file.pyc"))
        self.assertTrue(handler.is_ignored("src/node_modules/file.txt"))
        self.assertFalse(handler.is_ignored("important.pyc"))
        self.assertTrue(handler.is_ignored("dist/bundle.js"))
        self.assertFalse(handler.is_ignored("src/file.txt"))

    def test_gitignore_hidden_directories(self):
        """Test .gitignore patterns with hidden directories."""
        # Create test directory structure with hidden directories
        root_gitignore = os.path.join(self.test_dir, ".gitignore")
        hidden_dir = os.path.join(self.test_dir, ".hidden")
        hidden_sub = os.path.join(hidden_dir, ".sub")
        os.makedirs(hidden_sub, exist_ok=True)
        
        # Create test files
        with open(os.path.join(hidden_dir, "file1.txt"), "w") as f:
            f.write("test")
        with open(os.path.join(hidden_sub, "file2.txt"), "w") as f:
            f.write("test")
            
        # Test different patterns for hidden directories
        patterns = [
            (".*", False),  # A pattern without slash matches only basename; 'file1.txt' does not match '.*'
            (".hidden/", True),  # Ignore specific hidden dir
            ("!.hidden/file1.txt", False),  # Un-ignore specific file
            (".*/", True),  # Ignore all hidden dirs
        ]
        
        for pattern, expected in patterns:
            with self.subTest(pattern=pattern):
                with open(root_gitignore, "w") as f:
                    f.write(pattern + "\n")
                handler = IgnoreHandler(base_dir=self.test_dir, use_git_ignore=True)
                self.assertEqual(
                    handler.is_ignored(".hidden/file1.txt"),
                    expected,
                    f"Pattern '{pattern}' failed for '.hidden/file1.txt'"
                )
                
    def test_gitignore_multiple_negations(self):
        """Test complex scenarios with multiple negation patterns at different levels."""
        # Create nested directory structure
        dirs = [
            os.path.join(self.test_dir, d) for d in [
                "src",
                "src/lib",
                "src/lib/internal"
            ]
        ]
        for d in dirs:
            os.makedirs(d, exist_ok=True)
            
        # Create .gitignore files at different levels
        with open(os.path.join(self.test_dir, ".gitignore"), "w") as f:
            f.write("*.log\n")  # Ignore all logs
            
        with open(os.path.join(self.test_dir, "src", ".gitignore"), "w") as f:
            f.write("!*.log\n")  # Un-ignore logs in src
            f.write("lib/*.log\n")  # Re-ignore logs in lib
            
        with open(os.path.join(self.test_dir, "src/lib", ".gitignore"), "w") as f:
            f.write("!debug.log\n")  # Un-ignore specific log in lib
            f.write("internal/*.log\n")  # Re-ignore logs in internal
            
        handler = IgnoreHandler(base_dir=self.test_dir, use_git_ignore=True)
        
        # Test the complex negation hierarchy
        test_cases = [
            ("test.log", True),  # Ignored by root
            ("src/test.log", False),  # Un-ignored by src
            ("src/lib/test.log", True),  # Re-ignored by src/lib
            ("src/lib/debug.log", False),  # Un-ignored by lib
            ("src/lib/internal/debug.log", True),  # Re-ignored by internal
        ]
        
        for path, expected in test_cases:
            with self.subTest(path=path):
                self.assertEqual(
                    handler.is_ignored(path),
                    expected,
                    f"Multiple negation test failed for '{path}'"
                )
                
    def test_gitignore_pattern_order(self):
        """Test that pattern order within the same .gitignore file is respected."""
        gitignore_path = os.path.join(self.test_dir, ".gitignore")
        
        # Test pattern order: last matching pattern takes precedence
        with open(gitignore_path, "w") as f:
            f.write("*.txt\n")  # Ignore all txt
            f.write("!important.txt\n")  # Un-ignore important.txt
            f.write("important.txt\n")  # Re-ignore important.txt
            
        handler = IgnoreHandler(base_dir=self.test_dir, use_git_ignore=True)
        self.assertTrue(
            handler.is_ignored("important.txt"),
            "Last matching pattern (ignore) should take precedence"
        )
        
        # Test opposite order
        with open(gitignore_path, "w") as f:
            f.write("important.txt\n")  # Ignore important.txt
            f.write("!important.txt\n")  # Un-ignore important.txt
            f.write("*.txt\n")  # Ignore all txt
            
        handler = IgnoreHandler(base_dir=self.test_dir, use_git_ignore=True)
        self.assertTrue(
            handler.is_ignored("important.txt"),
            "Last matching pattern (ignore all) should take precedence"
        )

    def test_preprocess_ignore_patterns(self):
        """Test that preprocess_ignore_patterns correctly handles different types of patterns."""
        # Test basic patterns
        patterns = [".editorconfig", "node_modules/", "*.pyc"]
        processed = preprocess_ignore_patterns(patterns)
        
        # Verify .editorconfig has two versions
        self.assertIn(".editorconfig", processed)
        self.assertIn("**/.editorconfig", processed)
        
        # Verify other patterns are unchanged
        self.assertIn("node_modules/", processed)
        self.assertIn("*.pyc", processed)
        
        # Test patterns that are already directory-independent
        patterns = ["**/node_modules/**", "**/.git/**"]
        processed = preprocess_ignore_patterns(patterns)
        self.assertEqual(patterns, processed)
        
        # Test mixed patterns
        patterns = [".git", "**/node_modules/**", ".vscode", "build/"]
        processed = preprocess_ignore_patterns(patterns)
        self.assertIn(".git", processed)
        self.assertIn("**/.git", processed)
        self.assertIn(".vscode", processed)
        self.assertIn("**/.vscode", processed)
        self.assertIn("**/node_modules/**", processed)
        self.assertIn("build/", processed)
        
        # Test empty list
        self.assertEqual([], preprocess_ignore_patterns([]))
        self.assertEqual([], preprocess_ignore_patterns(None))

    def test_external_directory_ignore(self):
        """Test that files in external directories can be properly ignored."""
        # Create a subdirectory to simulate an external directory
        external_dir = os.path.join(self.test_dir, "external")
        os.makedirs(external_dir, exist_ok=True)
        
        # Create a .editorconfig file in the external directory
        with open(os.path.join(external_dir, ".editorconfig"), "w") as f:
            f.write("root = true\n")
            
        # Create a handler with .editorconfig in the ignore patterns
        handler = IgnoreHandler([".editorconfig"], base_dir=self.test_dir)
        
        # Verify .editorconfig is ignored in the main directory
        self.assertTrue(handler.is_ignored(".editorconfig"))
        
        # The critical test: verify .editorconfig is ignored in the external directory
        # Use both absolute and relative paths to test both scenarios
        rel_path = os.path.join("external", ".editorconfig")
        abs_path = os.path.join(external_dir, ".editorconfig")
        
        self.assertTrue(handler.is_ignored(rel_path), 
                        f"Failed to ignore {rel_path} with patterns: {handler.patterns}")
        self.assertTrue(handler.is_ignored(abs_path),
                        f"Failed to ignore {abs_path} with patterns: {handler.patterns}")
                        
        # Also test with the pattern explicitly specifying directory-independence
        handler2 = IgnoreHandler(["**/.editorconfig"], base_dir=self.test_dir)
        self.assertTrue(handler2.is_ignored(rel_path))
        self.assertTrue(handler2.is_ignored(abs_path))

    def test_complex_patterns_with_case_sensitivity(self):
        """Test complex patterns with case sensitivity.
        
        This test validates the actual behavior of the implementation
        with regard to case sensitivity.
        """
        # Test basic case-insensitive matching (default behavior)
        handler = IgnoreHandler(patterns=["*.log"])
        self.assertTrue(handler.is_ignored("file.log"), "Lowercase should match")
        self.assertTrue(handler.is_ignored("file.LOG"), "Uppercase should match with case-insensitive (default)")
        
        # Test basic case-sensitive matching
        handler = IgnoreHandler(patterns=["*.log"], case_sensitive=True)
        self.assertTrue(handler.is_ignored("file.log"), "Exact case should match")
        self.assertFalse(handler.is_ignored("file.LOG"), "Different case should not match in case-sensitive mode")
        
        # Test with negation and case sensitivity
        # NOTE: The PathSpec library handles negation in an unexpected way with case sensitivity
        # It appears that negation patterns affect all case variants, even in case-sensitive mode
        handler = IgnoreHandler(patterns=["*.log", "!important.log"], case_sensitive=True)
        self.assertTrue(handler.is_ignored("debug.log"), "Basic pattern should match")
        self.assertFalse(handler.is_ignored("important.log"), "Negated pattern should not match")
        self.assertFalse(handler.is_ignored("IMPORTANT.LOG"), "Negation applies to all case variants")
        
        # Verify with a different pattern format
        handler = IgnoreHandler(patterns=["*.LOG", "!IMPORTANT.LOG"], case_sensitive=True)
        self.assertFalse(handler.is_ignored("file.log"), "Case differs from pattern")
        self.assertTrue(handler.is_ignored("file.LOG"), "Exact case matches pattern")
        self.assertFalse(handler.is_ignored("IMPORTANT.LOG"), "Negated pattern should not match")
        
        # Test with negation and case insensitivity (default)
        handler = IgnoreHandler(patterns=["*.log", "!important.log"])
        self.assertTrue(handler.is_ignored("debug.log"), "Basic pattern should match")
        self.assertFalse(handler.is_ignored("important.log"), "Negated pattern should not match")
        self.assertFalse(handler.is_ignored("IMPORTANT.LOG"), "With case-insensitive, negation applies regardless of case")

    def test_kubernetes_external_directory_ignore(self):
        """Test that dot files (like .editorconfig) are properly ignored in external directories.
        
        This simulates the Kubernetes environment where the working directory is different
        from the directory being processed with the --dirs flag.
        """
        # Create an ignore handler with .editorconfig as pattern (simulates --ignore .editorconfig)
        patterns = ['.editorconfig']
        handler = IgnoreHandler(patterns=patterns)
        
        # Test root level file
        self.assertTrue(handler.is_ignored('.editorconfig'))
        
        # Test files in subdirectories 
        self.assertTrue(handler.is_ignored('some/path/.editorconfig'))
        
        # Test with path that includes a parent directory reference
        # Simulates when using --dirs "../installer" from within a Kubernetes pod
        self.assertTrue(handler.is_ignored('../installer/.editorconfig'))
        
        # Test with absolute paths (as might occur in mounted volumes)
        self.assertTrue(handler.is_ignored('/workspace/projects/installer/.editorconfig'))
        
        # Also verify the preprocessed patterns work as expected
        processed_patterns = handler._preprocess_patterns(patterns)
        self.assertIn('.editorconfig', processed_patterns)
        self.assertIn('**/.editorconfig', processed_patterns)


if __name__ == '__main__':
    unittest.main() 
