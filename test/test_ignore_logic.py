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
        """Test basic ignore patterns without globs"""
        test_cases = [
            # Basic directory ignore
            ("src/node_modules/package.json", "node_modules", True),
            ("project/src/dist/bundle.js", "dist", True),
            ("src/some_folder/file.txt", "node_modules", False),
            
            # Nested paths
            ("frontend/src/node_modules/deep/package.json", "node_modules", True),
            ("backend/src/tests/dist/output.js", "dist", True),
        ]
        for path, pattern, expected in test_cases:
            with self.subTest(path=path, pattern=pattern):
                handler = IgnoreHandler([pattern], base_dir=self.test_dir)
                self.assertEqual(handler.is_ignored(path, self.test_dir), expected)

    def test_gitignore_hierarchy(self):
        """Test that .gitignore files in different directories work correctly."""
        # Create test directory structure
        root_gitignore = os.path.join(self.test_dir, ".gitignore")
        frontend_dir = os.path.join(self.test_dir, "frontend")
        frontend_gitignore = os.path.join(frontend_dir, ".gitignore")
        backend_dir = os.path.join(self.test_dir, "backend")
        backend_gitignore = os.path.join(backend_dir, ".gitignore")
        
        os.makedirs(frontend_dir)
        os.makedirs(backend_dir)
        
        # Create .gitignore files
        with open(root_gitignore, 'w') as f:
            f.write("*.log\n")
            f.write("node_modules/\n")
        
        with open(frontend_gitignore, 'w') as f:
            f.write("*.tsx\n")
            f.write("dist/\n")
        
        with open(backend_gitignore, 'w') as f:
            f.write("*.pyc\n")
            f.write("__pycache__/\n")
        
        # Create test files
        test_files = [
            "app.log",  # Should be ignored by root .gitignore
            "frontend/app.log",  # Should be ignored by root .gitignore
            "frontend/src/component.tsx",  # Should be ignored by frontend/.gitignore
            "frontend/dist/bundle.js",  # Should be ignored by frontend/.gitignore
            "backend/app.pyc",  # Should be ignored by backend/.gitignore
            "backend/__pycache__/module.pyc",  # Should be ignored by backend/.gitignore
            "src/app.js",  # Should NOT be ignored
            "frontend/src/app.js",  # Should NOT be ignored
            "backend/src/app.py",  # Should NOT be ignored
        ]
        
        for file_path in test_files:
            full_path = os.path.join(self.test_dir, file_path)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            with open(full_path, 'w') as f:
                f.write("test content")
        
        # Initialize handler with gitignore support
        handler = IgnoreHandler(use_git_ignore=True, base_dir=self.test_dir)
        
        # Verify ignored files
        should_ignore = [
            "app.log",
            "frontend/app.log",
            "frontend/src/component.tsx",
            "frontend/dist/bundle.js",
            "backend/app.pyc",
            "backend/__pycache__/module.pyc",
        ]
        
        should_keep = [
            "src/app.js",
            "frontend/src/app.js",
            "backend/src/app.py",
        ]
        
        for file_path in should_ignore:
            with self.subTest(file_path=file_path):
                self.assertTrue(
                    handler.is_ignored(file_path, self.test_dir),
                    f"Expected {file_path} to be ignored"
                )
        
        for file_path in should_keep:
            with self.subTest(file_path=file_path):
                self.assertFalse(
                    handler.is_ignored(file_path, self.test_dir),
                    f"Expected {file_path} to NOT be ignored"
                )

    def test_gitignore_precedence(self):
        """Test that more specific .gitignore files take precedence."""
        # Create test directory structure with nested .gitignore files
        os.makedirs(os.path.join(self.test_dir, "src/special"))
        
        # Root .gitignore ignores all .txt files
        with open(os.path.join(self.test_dir, ".gitignore"), 'w') as f:
            f.write("*.txt\n")
            f.write("!src/special/important.txt\n")  # Explicit allow
        
        # Create test files
        test_files = [
            "regular.txt",  # Should be ignored by root .gitignore
            "src/file.txt",  # Should be ignored by root .gitignore
            "src/special/important.txt",  # Should NOT be ignored due to negation
            "src/special/other.txt",  # Should be ignored
        ]
        
        # Create test files
        test_files = [
            "regular.txt",  # Should be ignored by root .gitignore
            "src/file.txt",  # Should be ignored by root .gitignore
            "src/special/important.txt",  # Should NOT be ignored due to negation
        ]
        
        for file_path in test_files:
            full_path = os.path.join(self.test_dir, file_path)
            with open(full_path, 'w') as f:
                f.write("test content")
        
        handler = IgnoreHandler(use_git_ignore=True, base_dir=self.test_dir)
        
        # Verify that the more specific .gitignore takes precedence
        self.assertTrue(handler.is_ignored("regular.txt", self.test_dir))
        self.assertTrue(handler.is_ignored("src/file.txt", self.test_dir))
        self.assertFalse(handler.is_ignored("src/special/important.txt", self.test_dir))
        self.assertTrue(handler.is_ignored("src/special/other.txt", self.test_dir))

    def test_glob_patterns(self):
        """Test different glob pattern combinations"""
        test_cases = [
            # Single star patterns
            ("src/test123/file.txt", "test*/file.txt", True),
            ("src/test/file123.txt", "test/*.txt", True),
            ("src/test/subdir/file.txt", "test/*.txt", False),
            
            # Double star patterns
            ("very/deep/node_modules/package.json", "**/node_modules/**", True),
            ("node_modules/package.json", "**/node_modules/**", True),
            ("src/lib/node_modules/deep/pkg/file.js", "**/node_modules/**", True),
            ("src/nodemodules/file.js", "**/node_modules/**", False),
        ]
        for path, pattern, expected in test_cases:
            with self.subTest(path=path, pattern=pattern):
                handler = IgnoreHandler([pattern], base_dir=self.test_dir)
                self.assertEqual(handler.is_ignored(path, self.test_dir), expected)

    def test_build_and_dependency_patterns(self):
        """Test common build and dependency patterns"""
        test_cases = [
            # Node.js
            ("frontend/node_modules/react/index.js", "**/node_modules/**", True),
            ("package-lock.json", "**/package-lock.json", True),
            ("app/yarn.lock", "**/yarn.lock", True),
            
            # Python
            ("src/__pycache__/module.pyc", "**/__pycache__/**", True),
            ("tests/.pytest_cache/CACHEDIR.TAG", "**/.pytest_cache/**", True),
            (".venv/lib/python3.8/site-packages/pkg.py", "**/.venv/**", True),
            
            # Java/Maven
            ("build/classes/main/App.class", "**/build/**/*.class", True),
            ("target/myapp-1.0.jar", "**/target/**/*.jar", True),
            (".gradle/7.0/checksums", "**/.gradle/**", True),
        ]
        for path, pattern, expected in test_cases:
            with self.subTest(path=path, pattern=pattern):
                handler = IgnoreHandler([pattern])
                self.assertEqual(handler.is_ignored(path), expected)

    def test_ide_and_editor_patterns(self):
        """Test IDE and editor specific patterns"""
        test_cases = [
            # VS Code
            (".vscode/settings.json", "**/.vscode/**", True),
            ("project/.vscode/launch.json", "**/.vscode/**", True),
            
            # JetBrains
            (".idea/workspace.xml", "**/.idea/**", True),
            ("project/.idea/misc.xml", "**/.idea/**", True),
            
            # Eclipse
            (".settings/org.eclipse.jdt.core.prefs", "**/.settings/**", True),
            (".project", "**/.project", True),
            
            # Vim
            ("src/file.txt.swp", "**/*.swp", True),
            (".config.swp", "**/*.swp", True),
        ]
        for path, pattern, expected in test_cases:
            with self.subTest(path=path, pattern=pattern):
                handler = IgnoreHandler([pattern])
                self.assertEqual(handler.is_ignored(path), expected)

    def test_case_sensitivity(self):
        """Test case insensitive matching"""
        test_cases = [
            # Mixed case in path
            ("src/Node_Modules/package.json", "**/node_modules/**", True),
            ("SRC/DIST/bundle.js", "**/dist/**", True),
            
            # Mixed case in pattern
            ("src/node_modules/file.js", "**/NODE_MODULES/**", True),
            ("src/dist/file.js", "**/DiSt/**", True),
        ]
        for path, pattern, expected in test_cases:
            with self.subTest(path=path, pattern=pattern):
                handler = IgnoreHandler([pattern], base_dir=self.test_dir)
                self.assertEqual(handler.is_ignored(path, self.test_dir), expected)

    def test_backward_compatibility(self):
        """Test that old pattern styles still work"""
        test_cases = [
            # Original test cases
            ("my_projects/tst/src/main/resources/swagger/swagger-ui-core.js.map", "**/swagger/**", True),
            ("my_projects/tst/src/resources/swagger/swagger-ui-core.js.map", "**/swagger/**", True),
            ("my_projects/tst/src/main/resources/some-other-folder/file.txt", "**/swagger/**", False),
            (r"C:\workspace\projects\company\src\main\resources\swagger\swagger-ui-es-bundle-core.js.map", "**/swagger/**", True),
        ]
        for path, pattern, expected in test_cases:
            with self.subTest(path=path, pattern=pattern):
                handler = IgnoreHandler([pattern])
                self.assertEqual(handler.is_ignored(path), expected)

    def test_relative_path_scenarios(self):
        """Test ignore patterns with relative paths and different working directories"""
        test_cases = [
            # When working dir is /workspace/projects/empty and target dir is ../company
            ("modules/shared/target/classes/com/example/Test.class", "**/target/**", True),
            ("modules/shared/src/main/java/com/example/Test.java", "**/target/**", False),
            
            # Deeply nested target directories
            ("some/very/deep/path/target/classes/file.class", "**/target/**", True),
            ("another/deep/path/not-target/classes/file.class", "**/target/**", False),
            
            # Complex relative paths
            ("../company/modules/shared/target/maven-status/maven-compiler-plugin/compile/default-compile/createdFiles.lst", "**/target/**", True),
            ("../company/modules/core/src/main/resources/config.xml", "**/target/**", False),
            
            # Parent directory references
            ("../../other-project/target/classes/file.class", "**/target/**", True),
            ("../sibling-project/build/libs/file.jar", "**/target/**", False),
            
            # Mixed path separators
            (r"..\company\modules\shared\target\classes\Test.class", "**/target/**", True),
            (r"..\company\modules\shared\src\main\java\Test.java", "**/target/**", False),
            
            # Absolute paths when working from relative directory
            ("/workspace/projects/company/modules/shared/target/classes/Test.class", "**/target/**", True),
            ("/workspace/projects/company/modules/shared/src/main/java/Test.java", "**/target/**", False),
            
            # Current directory references
            ("./target/classes/Test.class", "**/target/**", True),
            ("./src/main/java/Test.java", "**/target/**", False),
        ]
        for path, pattern, expected in test_cases:
            with self.subTest(path=path, pattern=pattern):
                handler = IgnoreHandler([pattern])
                self.assertEqual(handler.is_ignored(path), expected)


if __name__ == '__main__':
    unittest.main() 
