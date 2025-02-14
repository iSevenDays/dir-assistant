import unittest
import os
import tempfile
import shutil
from pathlib import Path
from dir_assistant.assistant.ignore_handler import IgnoreHandler


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
        ignore_file = os.path.join(self.test_dir, ".dirassistantignore")
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


if __name__ == '__main__':
    unittest.main() 
