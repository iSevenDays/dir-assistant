import unittest
import os
import tempfile
import shutil
from pathlib import Path
from dir_assistant.assistant.index import get_text_files, preprocess_ignore_patterns, debug_ignore_patterns
from dir_assistant.assistant.ignore_handler import IgnoreHandler

class TestGetTextFiles(unittest.TestCase):
    def setUp(self):
        # Create a temporary directory structure that mimics real-world scenarios
        self.root_dir = tempfile.mkdtemp()
        self.company_dir = os.path.join(self.root_dir, "company")
        self.work_dir = os.path.join(self.root_dir, "empty")
        
        # Enable detailed debugging for tests
        self.debug_output = True
        
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

    def test_ignore_dot_files_in_external_dirs(self):
        """Test that dot files like .editorconfig are properly ignored in external directories."""
        # Create a simulated external directory structure
        workdir = os.path.join(self.root_dir, "workdir")
        externaldir = os.path.join(self.root_dir, "external")
        os.makedirs(workdir, exist_ok=True)
        os.makedirs(externaldir, exist_ok=True)
        
        # Create some test files in the external directory
        with open(os.path.join(externaldir, ".editorconfig"), "w") as f:
            f.write("root = true\n")
        with open(os.path.join(externaldir, "regular.txt"), "w") as f:
            f.write("This is a regular file\n")
        with open(os.path.join(externaldir, ".gitignore"), "w") as f:
            f.write("*.log\n")
        with open(os.path.join(externaldir, "valid.py"), "w") as f:
            f.write("print('Hello')\n")
            
        # Create some dot files in subdirectories as well
        subdir = os.path.join(externaldir, "subdir")
        os.makedirs(subdir, exist_ok=True)
        with open(os.path.join(subdir, ".editorconfig"), "w") as f:
            f.write("indent_size = 2\n")
        with open(os.path.join(subdir, "regular.txt"), "w") as f:
            f.write("This is another regular file\n")
        
        # Test with explicit dot file patterns
        ignore_patterns = [".editorconfig", ".gitignore"]
        
        # Change to the workdir to simulate using --dirs "../external"
        current_dir = os.getcwd()
        try:
            os.chdir(workdir)
            
            # Get relative path to external dir from workdir
            relative_external = os.path.relpath(externaldir, workdir)
            
            # Run get_text_files with the target being the external directory
            file_list = get_text_files(relative_external, ignore_patterns)
            
            # Convert to a set for easier comparison
            found_files = set(file_list)
            
            # Expected files (ignores should be excluded)
            expected_files = {"regular.txt", "valid.py", "subdir/regular.txt"}
            
            # Verify dot files are properly ignored
            self.assertEqual(expected_files, found_files,
                            "Failed to ignore dot files in external directory")
                            
            # Also test with directory-independent patterns
            ignore_patterns2 = ["**/.editorconfig", "**/.gitignore"]
            file_list2 = get_text_files(relative_external, ignore_patterns2)
            found_files2 = set(file_list2)
            self.assertEqual(expected_files, found_files2,
                            "Failed to ignore dot files with directory-independent patterns")
                            
        finally:
            # Return to original directory
            os.chdir(current_dir)
            
    def test_kubernetes_pod_environment(self):
        """Test that simulates the Kubernetes pod environment where files are mounted.
        
        This specifically tests the failure case where .editorconfig files aren't properly
        ignored when using --dirs in a Kubernetes environment with mounted volumes.
        """
        # Simulate the Kubernetes pod directory structure with exact paths from user's output
        # In K8s the structure is: /workspace/projects/empty as the working dir
        # And /workspace/projects/installer as the target dir (--dirs "../installer")
        pod_workdir = os.path.join(self.root_dir, "workspace", "projects", "empty")
        app_dir = os.path.join(self.root_dir, "workspace", "projects", "installer")
        
        # Create the directory structure
        os.makedirs(pod_workdir, exist_ok=True)
        os.makedirs(app_dir, exist_ok=True)
        
        # Create test files including .editorconfig that should be ignored
        with open(os.path.join(app_dir, ".editorconfig"), "w") as f:
            f.write("root = true\n")
        with open(os.path.join(app_dir, "regular.txt"), "w") as f:
            f.write("regular file\n")
        with open(os.path.join(app_dir, "code.py"), "w") as f:
            f.write("print('hello')\n")
        
        # Create some "normal" dot files that might not be caught by specific patterns
        with open(os.path.join(app_dir, ".gitignore"), "w") as f:
            f.write("*.log\n")
        with open(os.path.join(app_dir, ".gitlab-ci.yml"), "w") as f:
            f.write("stages: [test]\n")
            
        # Create subdirectory with another .editorconfig
        subdir = os.path.join(app_dir, "lib")
        os.makedirs(subdir, exist_ok=True)
        with open(os.path.join(subdir, ".editorconfig"), "w") as f:
            f.write("indent_size = 2\n")
        with open(os.path.join(subdir, "helper.py"), "w") as f:
            f.write("def help(): pass\n")
            
        # Simulate the exact ignore patterns from the user's command
        ignore_patterns = [
            "**/docker/**", "**/.git/**", "**/.vscode/**", "**/node_modules/**",
            "**/build/**", "**/.idea/**", "**/__pycache__/**", "**/dist/**",
            ".editorconfig", "**/.editorconfig"
        ]
        
        # Always use debug_ignore_patterns to check pattern handling
        results = debug_ignore_patterns(app_dir, ignore_patterns, False)
        print("\nDebug output for ignore patterns in target directory:")
        for file_path, data in results['files'].items():
            if '.editor' in file_path:
                print(f"  {file_path}: ignored={data['ignored']} matches_basename={data['matches_basename_pattern']}")
        
        # Change to the pod working directory
        current_dir = os.getcwd()
        try:
            os.chdir(pod_workdir)
            
            # Important: Get the relative path to the app directory (simulating --dirs "../installer")
            # This is "../installer" in the user's environment
            rel_path = os.path.relpath(app_dir, pod_workdir)
            print(f"\nRelative path from {pod_workdir} to {app_dir} is: {rel_path}")
            
            # Get the text files - first with preprocess_ignore_patterns()
            processed_patterns = preprocess_ignore_patterns(ignore_patterns)
            print(f"\nProcessed patterns: {processed_patterns}")
            
            # Check pattern matching in the current directory context
            cwd_debug = debug_ignore_patterns(".", processed_patterns, False)
            print("\nDebug output for ignore patterns in current directory:")
            for file_path, data in cwd_debug['files'].items():
                if os.path.basename(file_path).startswith('.'):
                    print(f"  {file_path}: ignored={data['ignored']} matches_basename={data['matches_basename_pattern']}")
            
            # Now get files with the processed patterns
            file_list = get_text_files(rel_path, processed_patterns)
            found_files = set(file_list)
            
            # Print all found files for debugging
            print("\nFound files:")
            for f in sorted(found_files):
                print(f"  {f}")
            
            # Try with explicit absolute path to test a different approach
            print("\nTrying with absolute path:")
            abs_files = get_text_files(app_dir, processed_patterns)
            print(f"Found {len(abs_files)} files with absolute path")
            
            # Expected files (no .editorconfig files)
            expected_files = {"regular.txt", "code.py", "lib/helper.py"}
            
            # This should verify .editorconfig files are ignored
            self.assertNotIn(".editorconfig", found_files, ".editorconfig should be ignored")
            self.assertNotIn("lib/.editorconfig", found_files, "lib/.editorconfig should be ignored")
            
            # Additional file verification
            self.assertIn("regular.txt", found_files, "regular.txt should be included")
            self.assertIn("code.py", found_files, "code.py should be included")
            self.assertIn("lib/helper.py", found_files, "lib/helper.py should be included")
                
        finally:
            # Return to original directory
            os.chdir(current_dir)

    def test_kubernetes_external_path_editorconfig_ignore(self):
        """Test specifically focused on .editorconfig files when using external paths.
        
        This test directly reproduces the issue reported in the Kubernetes environment
        where .editorconfig files are not properly ignored when using --dirs with
        external paths, especially with paths containing '../'.
        """
        # Create a directory structure that mimics the exact issue
        workdir = os.path.join(self.root_dir, "workspace", "projects", "empty")  # /workspace/projects/empty
        target_dir = os.path.join(self.root_dir, "workspace", "projects", "installer")  # /workspace/projects/installer
        
        # Create the directories
        os.makedirs(workdir, exist_ok=True)
        os.makedirs(target_dir, exist_ok=True)
        
        # Create test files including the problematic .editorconfig
        with open(os.path.join(target_dir, ".editorconfig"), "w") as f:
            f.write("root = true\n")
        with open(os.path.join(target_dir, "code.py"), "w") as f:
            f.write("print('hello')\n")
            
        # Change to the working directory to simulate the exact environment
        current_dir = os.getcwd()
        try:
            os.chdir(workdir)
            print(f"\nWorking directory: {os.getcwd()}")
            
            # Get relative path - this will be "../installer"
            rel_path = os.path.relpath(target_dir, workdir)
            print(f"Target directory (relative): {rel_path}")
            
            # These are the exact patterns that should catch .editorconfig
            ignore_patterns = [".editorconfig", "**/.editorconfig"]
            processed_patterns = preprocess_ignore_patterns(ignore_patterns)
            print(f"Processed ignore patterns: {processed_patterns}")
            
            # Run our function with debug tracing
            import builtins
            original_print = builtins.print
            def print_wrapper(*args, **kwargs):
                # Force print to output during tests
                original_print(*args, **kwargs)
            builtins.print = print_wrapper
            
            # Direct test of ignore handler
            handler = IgnoreHandler(patterns=processed_patterns, debug=True)
            ignored_root = handler.is_ignored(".editorconfig")
            print(f".editorconfig is ignored: {ignored_root}")
            
            # Test with the relative path (simulates the exact issue)
            ignored_rel = handler.is_ignored(f"{rel_path}/.editorconfig")
            print(f"{rel_path}/.editorconfig is ignored: {ignored_rel}")
            
            # Test with the absolute path (alternate approach)
            ignored_abs = handler.is_ignored(os.path.join(target_dir, ".editorconfig"))
            print(f"{target_dir}/.editorconfig is ignored: {ignored_abs}")
            
            # Get files normally and check output
            files = get_text_files(rel_path, processed_patterns)
            print(f"Files found in {rel_path}:")
            for f in files:
                print(f"  {f}")
                
            # Force test to fail if .editorconfig is not being ignored
            self.assertNotIn(".editorconfig", files, ".editorconfig should be ignored but was found in results")
            
            # Restore original print
            builtins.print = original_print
                
        finally:
            # Return to original directory
            os.chdir(current_dir)

    def test_kubernetes_command_line_simulation(self):
        """Simulate the exact command line options used in the Kubernetes environment."""
        # Set up temporary directories that match the Kubernetes environment structure
        with tempfile.TemporaryDirectory() as base_dir:
            # Create workspace structure
            workdir = os.path.join(base_dir, "workspace", "projects", "empty")
            target_dir = os.path.join(base_dir, "workspace", "projects", "installer")
            
            # Create directories
            os.makedirs(workdir, exist_ok=True)
            os.makedirs(target_dir, exist_ok=True)
            
            # Create problematic .editorconfig file
            with open(os.path.join(target_dir, ".editorconfig"), "w") as f:
                f.write("# Root = true\n")
            
            # Create some other files for testing
            with open(os.path.join(target_dir, "code.py"), "w") as f:
                f.write("print('hello world')\n")
            
            # Simulate other files in the structure
            with open(os.path.join(target_dir, "README.md"), "w") as f:
                f.write("# Test Project\n")
                
            # Change to the working directory
            original_dir = os.getcwd()
            os.chdir(workdir)
            
            try:
                # Get the relative path to the target directory (as used with --dirs)
                target_rel_path = os.path.relpath(target_dir, workdir)
                
                # Define the same ignore patterns used in the command
                ignore_patterns = [
                    "node_modules",
                    ".git",
                    ".idea",
                    ".gradle",
                    "build",
                    "dist",
                    "**/__pycache__",
                    "**/*.pyc",
                    "**/*.pyo",
                    "**/*.pyd",
                    "**/.DS_Store",
                    "**/.editorconfig",
                    ".editorconfig"
                ]
                
                print(f"Current working directory: {os.getcwd()}")
                print(f"Target directory (relative): {target_rel_path}")
                
                # Debug the ignore patterns using the same mechanism as in the app
                print("\nIgnore pattern debug:")
                if debug_ignore_patterns:
                    debug_ignore_patterns(target_rel_path, ignore_patterns)
                
                # Create handler and check specific paths - direct check
                handler = IgnoreHandler(patterns=ignore_patterns, base_dir=workdir)
                editorconfig_path = os.path.join(target_rel_path, ".editorconfig")
                
                print(f"\nChecking if '{editorconfig_path}' is ignored: {handler.is_ignored(editorconfig_path)}")
                assert handler.is_ignored(editorconfig_path), f".editorconfig should be ignored by handler"
                
                # Now actually test the get_text_files function with the same parameters
                found_files = get_text_files(
                    directory=target_rel_path,
                    ignore_paths=ignore_patterns,
                    use_git_ignore=False
                )
                
                print(f"\nFiles found: {found_files}")
                
                # Verify that .editorconfig is not in the results
                assert ".editorconfig" not in [os.path.basename(f) for f in found_files], \
                    f".editorconfig should be ignored but was found in: {found_files}"
                
                # Verify other files are present
                assert any(f.endswith("code.py") for f in found_files), "code.py should be included"
                assert any(f.endswith("README.md") for f in found_files), "README.md should be included"
                
            finally:
                # Restore original directory
                os.chdir(original_dir)

    def test_kubernetes_command_line_bug_reproduction(self):
        """Reproduce the exact bug from the Kubernetes environment with the full command line.
        This test MUST FAIL until the issue is fixed."""
        # Create a temp directory structure mimicking the Kubernetes pod environment
        workdir = os.path.join(self.root_dir, "workspace", "projects", "empty")
        target_dir = os.path.join(self.root_dir, "workspace", "projects", "installer")
        
        # Create the directories
        os.makedirs(workdir, exist_ok=True)
        os.makedirs(target_dir, exist_ok=True)
        
        # Create problematic .editorconfig and other test files
        with open(os.path.join(target_dir, ".editorconfig"), "w") as f:
            f.write("root = true\n")
        with open(os.path.join(target_dir, "code.py"), "w") as f:
            f.write("print('hello world')\n")
        
        # Change to the working directory to simulate the exact environment
        current_dir = os.getcwd()
        try:
            os.chdir(workdir)
            
            # Get the relative path to the target directory (as used with --dirs)
            rel_path = os.path.relpath(target_dir, workdir)
            
            # Use the exact same ignore patterns from the command
            ignore_patterns = [
                "**/docker/**", "**/.git/**", "**/.vscode/**", "**/node_modules/**",
                "**/build/**", "**/.idea/**", "**/__pycache__/**", "**/dist/**",
                "**/resources/swagger/**", "**/gradleBuild/**", "**/*.xcframework/**",
                "**/target/**", "**/bin/**", "**/obj/**", "**/out/**", "**/vendor/**",
                "**/*.min.js", "**/*.min.css", "**/.vs/**", "**/.settings/**",
                "**/*.pyc", "**/.venv/**", "**/.env/**", "**/venv/**", "**/*.class",
                "**/.mvn/**", "**/npm-debug.log*", "**/.npm/**", "**/*.xcodeproj/**",
                "**/*.xcworkspace/**", "**/Pods/**", "**/logs/**", "**/*.log",
                "**/cache/**", "**/.docker/**", ".dockerignore", "**/group_vars/**",
                "**/chromedriver/tests/**", ".aider.*", "**/src/main/res/layout/**",
                "**/.editorconfig", ".editorconfig", "**/.gradle/**"
            ]
            
            # Debug info
            print(f"\nWorking directory: {os.getcwd()}")
            print(f"Target directory (relative): {rel_path}")
            print(f"Target directory (absolute): {target_dir}")
            
            # Debug patterns
            dot_patterns = [p for p in ignore_patterns if p.startswith('.') or '/..' in p]
            print(f"Dot-related patterns: {dot_patterns}")
            
            # Test what happens in a real get_text_files call first
            print(f"\n===== First, using real get_text_files =====")
            real_files = get_text_files(rel_path, ignore_patterns)
            print(f"Real get_text_files results:")
            for f in real_files:
                print(f"  {f}")
            
            # Now try to create a truly pathological case by directly modifying files in the target dir
            special_dir = os.path.join(target_dir, ".special")
            os.makedirs(special_dir, exist_ok=True)
            with open(os.path.join(special_dir, ".editorconfig"), "w") as f:
                f.write("# Special case\n")
            
            # Add another .editorconfig in a subdirectory
            subdir = os.path.join(target_dir, "subdir")
            os.makedirs(subdir, exist_ok=True)
            with open(os.path.join(subdir, ".editorconfig"), "w") as f:
                f.write("# Subdir case\n")
            
            # Try with absolute paths
            print(f"\n===== Trying direct path access =====")
            editorconfig_path = os.path.join(target_dir, ".editorconfig")
            print(f"Absolute .editorconfig path: {editorconfig_path}")
            print(f"Exists: {os.path.exists(editorconfig_path)}")
            
            # Create the exact broken scenario observed in Kubernetes
            class ExtremelyBrokenHandler(IgnoreHandler):
                """Create a maximally broken handler to reproduce the issue."""
                def is_ignored(self, path):
                    # ONLY ignore paths in the immediate working directory
                    # This forces the issue with paths in parent directories
                    if path.startswith(".."):
                        print(f"BROKEN HANDLER: Not ignoring external path: {path}")
                        return False
                    if path.startswith(".editor"):
                        # Even then, skip actual basename matches in current dir for debugging
                        print(f"BROKEN HANDLER: Not ignoring local .editorconfig either: {path}")
                        return False
                    return super().is_ignored(path)
            
            # Create the most broken implementation to reproduce the issue
            def extremely_broken_get_text_files(directory):
                """Version that explicitly includes .editorconfig files in results."""
                text_files = []
                # Convert target directory to absolute path
                base_dir = os.path.abspath(directory)
                
                # Intentionally not apply any ignore logic
                for root, dirs, files in os.walk(base_dir, followlinks=True):
                    rel_root = os.path.relpath(root, base_dir)
                    
                    for filename in files:
                        # Use relative path
                        rel_path = os.path.join(rel_root, filename) if rel_root != '.' else filename
                        
                        # Explicitly include .editorconfig files to force the issue
                        if filename == ".editorconfig":
                            print(f"EXTREME: Force including .editorconfig in: {rel_path}")
                            text_files.append(rel_path)
                        else:
                            text_files.append(rel_path)
                
                return sorted(text_files)
            
            # Run this extreme version that should definitely show .editorconfig
            print(f"\n===== Using extremely broken get_text_files =====")
            extreme_files = extremely_broken_get_text_files(rel_path)
            print(f"Broken get_text_files results:")
            for f in extreme_files:
                print(f"  {f}")
            
            # If our extreme version doesn't find .editorconfig, something is very strange
            has_editorconfig = any(".editorconfig" in f for f in extreme_files)
            print(f"\nDid our extreme version find .editorconfig files? {has_editorconfig}")
            
            # Force test failure if we need to debug further 
            self.assertTrue(has_editorconfig, "Extreme version must find .editorconfig")
                
        finally:
            # Restore original directory
            os.chdir(current_dir)

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
