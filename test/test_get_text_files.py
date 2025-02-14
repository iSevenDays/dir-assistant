import unittest
import os
import tempfile
import shutil
from pathlib import Path
from dir_assistant.assistant.index import get_text_files

class TestGetTextFiles(unittest.TestCase):
    def setUp(self):
        # Create a temporary directory structure that mimics real-world scenarios
        self.root_dir = tempfile.mkdtemp()
        self.company_dir = os.path.join(self.root_dir, "company")
        self.work_dir = os.path.join(self.root_dir, "empty")
        
        # Create the working directory
        os.makedirs(self.work_dir)
        
        # Create test directory structure with various file types and patterns
        paths = [
            # Original test paths
            "src/main/resources/swagger/swagger-ui.js",
            "src/main/resources/swagger/index.html",
            "src/main/resources/config.properties",
            "src/main/java/com/example/Test.java",
            "src/resources/swagger/swagger-ui-core.js",
            "src/test/resources/test.properties",
            
            # Target directory test paths
            "modules/company/target/classes/swagger/index.html",
            "modules/company/target/classes/swagger/swagger-ui.js",
            "modules/company/target/classes/swagger/swagger-ui-core.js",
            "modules/company/src/main/java/com/example/Test.java",
            
            # Additional test paths for common scenarios
            # Hidden files and directories
            ".git/config",
            ".idea/workspace.xml",
            ".vscode/settings.json",
            ".env",
            
            # Build outputs and dependencies
            "build/outputs/app.jar",
            "dist/bundle.js",
            "node_modules/package/index.js",
            "__pycache__/module.pyc",
            
            # Different file extensions
            "docs/README.md",
            "src/main/resources/application.yaml",
            "config/settings.json",
            "scripts/deploy.sh",
            
            # Nested structures
            "frontend/src/components/Button.tsx",
            "frontend/node_modules/react/index.js",
            "backend/src/models/User.py",
            "backend/tests/__pycache__/test_user.pyc",
            
            # Special characters in paths
            "src/test files/space in name.txt",
            "src/special-chars/test-file.js",
            "src/unicode/τεστ.txt",
            
            # Symlinks (created separately)
            "src/links/real_file.txt",
            
            # Large and empty files
            "src/large/big_file.txt",
            "src/empty/empty_file.txt",
        ]
        
        # Create all directories and files
        for path in paths:
            full_path = os.path.join(self.company_dir, path)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            with open(full_path, 'w') as f:
                if "large" in path:
                    f.write("x" * 1024 * 1024)  # 1MB file
                elif "empty" not in path:
                    f.write("test content")
        
        # Create symlinks
        real_file = os.path.join(self.company_dir, "src/links/real_file.txt")
        link_path = os.path.join(self.company_dir, "src/links/link_to_file.txt")
        os.symlink(real_file, link_path)
        
        # Create .gitignore files at different levels
        self._create_gitignore_files()

    def _create_gitignore_files(self):
        """Create .gitignore files at different directory levels for testing."""
        # Root level .gitignore
        root_gitignore = os.path.join(self.company_dir, ".gitignore")
        with open(root_gitignore, 'w') as f:
            f.write("""# Root level ignores
*.log
.env
node_modules/
**/target/
""")

        # Frontend specific .gitignore
        frontend_dir = os.path.join(self.company_dir, "frontend")
        frontend_gitignore = os.path.join(frontend_dir, ".gitignore")
        with open(frontend_gitignore, 'w') as f:
            f.write("""# Frontend specific ignores
 dist/
 *.tsx
""")

        # Backend specific .gitignore
        backend_dir = os.path.join(self.company_dir, "backend")
        backend_gitignore = os.path.join(backend_dir, ".gitignore")
        with open(backend_gitignore, 'w') as f:
            f.write("""# Backend specific ignores
 __pycache__/
 *.pyc
""")

    def tearDown(self):
        # Remove the temporary directory and its contents
        shutil.rmtree(self.root_dir)

    def test_gitignore_support(self):
        """Test that .gitignore files are respected when use_git_ignore is True."""
        # This test will initially fail because use_git_ignore is not implemented
        ignore_paths = []  # No explicit ignore patterns
        relative_paths = set(get_text_files(self.company_dir, ignore_paths, use_git_ignore=True))
        
        # Debug output
        print("\nActual files found:")
        for path in sorted(relative_paths):
            print(f"  {path}")
        
        # Files that should be included (updated based on proper gitignore rules)
        expected_files = {
            ".git/config",
            ".idea/workspace.xml",
            ".vscode/settings.json",
            "__pycache__/module.pyc",
            "backend/src/models/User.py",
            "build/outputs/app.jar",
            "config/settings.json",
            "dist/bundle.js",
            "docs/README.md",
            "modules/company/src/main/java/com/example/Test.java",
            "scripts/deploy.sh",
            "src/empty/empty_file.txt",
            "src/large/big_file.txt",
            "src/links/real_file.txt",
            "src/links/link_to_file.txt",
            "src/main/java/com/example/Test.java",
            "src/main/resources/application.yaml",
            "src/main/resources/config.properties",
            "src/main/resources/swagger/index.html",
            "src/main/resources/swagger/swagger-ui.js",
            "src/resources/swagger/swagger-ui-core.js",
            "src/special-chars/test-file.js",
            "src/test files/space in name.txt",
            "src/test/resources/test.properties",
            "src/unicode/τεστ.txt",
        }
        
        # Files that should be excluded based only on explicit .gitignore rules
        excluded_files = {
            # From root .gitignore
            ".env",
            "node_modules/package/index.js",
            
            # From frontend/.gitignore
            "frontend/node_modules/react/index.js",
            "frontend/src/components/Button.tsx",
            
            # From target directories via **/target/
            "modules/company/target/classes/swagger/index.html",
            "modules/company/target/classes/swagger/swagger-ui.js",
            "modules/company/target/classes/swagger/swagger-ui-core.js",
            
            # From backend/.gitignore
            "backend/tests/__pycache__/test_user.pyc",
        }
        
        self._verify_file_sets(relative_paths, expected_files, excluded_files)

    def test_ignore_swagger_directory(self):
        """Test ignoring swagger directory using gitignore syntax."""
        ignore_paths = ["**/swagger/**"]
        relative_paths = set(get_text_files(self.company_dir, ignore_paths))
        
        # Debug output
        print("\nActual files found:")
        for path in sorted(relative_paths):
            print(f"  {path}")
        
        # Files that should be included
        expected_files = {
            "src/main/resources/config.properties",
            "src/main/java/com/example/Test.java",
            "src/test/resources/test.properties",
            "modules/company/src/main/java/com/example/Test.java",
            "docs/README.md",
            "src/main/resources/application.yaml",
            "config/settings.json",
            "scripts/deploy.sh",
            "frontend/src/components/Button.tsx",
            "backend/src/models/User.py",
            "src/test files/space in name.txt",
            "src/special-chars/test-file.js",
            "src/unicode/τεστ.txt",
            "src/links/real_file.txt",
            "src/links/link_to_file.txt",
            "src/large/big_file.txt",
            "src/empty/empty_file.txt",
        }
        
        # Files that should be excluded
        excluded_files = {
            "src/main/resources/swagger/swagger-ui.js",
            "src/main/resources/swagger/index.html",
            "src/resources/swagger/swagger-ui-core.js",
            "modules/company/target/classes/swagger/index.html",
            "modules/company/target/classes/swagger/swagger-ui.js",
            "modules/company/target/classes/swagger/swagger-ui-core.js",
        }
        
        self._verify_file_sets(relative_paths, expected_files, excluded_files)

    def test_multiple_ignore_patterns(self):
        """Test with multiple ignore patterns using gitignore syntax."""
        ignore_paths = ["**/swagger/**", "**/test/resources/**"]
        relative_paths = set(get_text_files(self.company_dir, ignore_paths))
        
        # Debug output
        print("\nActual files found:")
        for path in sorted(relative_paths):
            print(f"  {path}")
        
        # Only these files should remain
        expected_files = {
            "src/main/resources/config.properties",
            "src/main/java/com/example/Test.java",
            "modules/company/src/main/java/com/example/Test.java",
            "docs/README.md",
            "src/main/resources/application.yaml",
            "config/settings.json",
            "scripts/deploy.sh",
            "frontend/src/components/Button.tsx",
            "backend/src/models/User.py",
            "src/test files/space in name.txt",
            "src/special-chars/test-file.js",
            "src/unicode/τεστ.txt",
            "src/links/real_file.txt",
            "src/links/link_to_file.txt",
            "src/large/big_file.txt",
            "src/empty/empty_file.txt",
        }
        
        # These should all be excluded
        excluded_files = {
            "src/main/resources/swagger/swagger-ui.js",
            "src/main/resources/swagger/index.html",
            "src/resources/swagger/swagger-ui-core.js",
            "src/test/resources/test.properties",
            "modules/company/target/classes/swagger/index.html",
            "modules/company/target/classes/swagger/swagger-ui.js",
            "modules/company/target/classes/swagger/swagger-ui-core.js",
        }
        
        self._verify_file_sets(relative_paths, expected_files, excluded_files)

    def test_target_directory_ignore(self):
        """Test that files in target directory are properly ignored."""
        ignore_paths = ["**/target/**", "**/swagger/**"]
        relative_paths = set(get_text_files(self.company_dir, ignore_paths))
        
        # Debug output
        print("\nActual files found:")
        for path in sorted(relative_paths):
            print(f"  {path}")
        
        # Files that should be included
        expected_files = {
            "modules/company/src/main/java/com/example/Test.java",
            "src/main/resources/config.properties",
            "src/main/java/com/example/Test.java",
            "docs/README.md",
            "src/main/resources/application.yaml",
            "config/settings.json",
            "scripts/deploy.sh",
            "frontend/src/components/Button.tsx",
            "backend/src/models/User.py",
            "src/test files/space in name.txt",
            "src/special-chars/test-file.js",
            "src/unicode/τεστ.txt",
            "src/links/real_file.txt",
            "src/links/link_to_file.txt",
            "src/large/big_file.txt",
            "src/empty/empty_file.txt",
        }
        
        # Files that should be excluded
        excluded_files = {
            "modules/company/target/classes/swagger/index.html",
            "modules/company/target/classes/swagger/swagger-ui.js",
            "modules/company/target/classes/swagger/swagger-ui-core.js",
            "src/main/resources/swagger/swagger-ui.js",
            "src/main/resources/swagger/index.html",
            "src/resources/swagger/swagger-ui-core.js",
        }
        
        self._verify_file_sets(relative_paths, expected_files, excluded_files)

    def test_hidden_and_special_files(self):
        """Test handling of hidden files, special characters, and symlinks."""
        ignore_paths = [".*", "!.gitkeep"]  # Ignore all hidden files except .gitkeep
        relative_paths = set(get_text_files(self.company_dir, ignore_paths))
        
        # Files that should be excluded
        excluded_files = {
            ".git/config",
            ".idea/workspace.xml",
            ".vscode/settings.json",
            ".env",
        }
        
        # Verify special files are handled correctly
        self.assertTrue("src/test files/space in name.txt" in relative_paths)
        self.assertTrue("src/special-chars/test-file.js" in relative_paths)
        self.assertTrue("src/unicode/τεστ.txt" in relative_paths)
        self.assertTrue("src/links/link_to_file.txt" in relative_paths)
        
        # Verify hidden files are excluded
        for excluded in excluded_files:
            self.assertNotIn(excluded, relative_paths)

    def test_build_and_cache_files(self):
        """Test ignoring build outputs and cache directories."""
        ignore_paths = [
            "**/build/**",
            "**/dist/**",
            "**/node_modules/**",
            "**/__pycache__/**",
        ]
        relative_paths = set(get_text_files(self.company_dir, ignore_paths))
        
        # Files that should be excluded
        excluded_files = {
            "build/outputs/app.jar",
            "dist/bundle.js",
            "node_modules/package/index.js",
            "__pycache__/module.pyc",
            "frontend/node_modules/react/index.js",
            "backend/tests/__pycache__/test_user.pyc",
        }
        
        # Verify build and cache files are excluded
        for excluded in excluded_files:
            self.assertNotIn(excluded, relative_paths)

    def _verify_file_sets(self, actual_paths, expected_files, excluded_files):
        """Helper method to verify file sets match expectations."""
        # Verify expected files are included
        missing_files = expected_files - actual_paths
        if missing_files:
            print("\nMissing expected files:")
            for path in sorted(missing_files):
                print(f"  {path}")
            print("\nFound files:")
            for path in sorted(actual_paths):
                print(f"  {path}")
            self.assertEqual(missing_files, set(), "Some expected files were not found")
        
        # Verify excluded files are not included
        included_excluded = actual_paths & excluded_files
        if included_excluded:
            print("\nExcluded files that were incorrectly included:")
            for path in sorted(included_excluded):
                print(f"  {path}")
            self.assertEqual(included_excluded, set(), "Some excluded files were incorrectly included")

if __name__ == '__main__':
    unittest.main() 
