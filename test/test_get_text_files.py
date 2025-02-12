import unittest
import os
import tempfile
import shutil
from pathlib import Path
from dir_assistant.assistant.index import get_text_files

class TestGetTextFiles(unittest.TestCase):
    def setUp(self):
        # Create a temporary directory
        self.test_dir = tempfile.mkdtemp()
        
        # Create test directory structure
        paths = [
            "src/main/resources/swagger/swagger-ui.js",
            "src/main/resources/swagger/index.html",
            "src/main/resources/config.properties",
            "src/main/java/com/example/Test.java",
            "src/resources/swagger/swagger-ui-core.js",
            "src/test/resources/test.properties",
        ]
        
        # Create all directories and files
        for path in paths:
            full_path = os.path.join(self.test_dir, path)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            # Create the file with some content
            with open(full_path, 'w') as f:
                f.write("test content")

    def tearDown(self):
        # Remove the temporary directory and its contents
        shutil.rmtree(self.test_dir)

    def test_ignore_swagger_directory(self):
        # Get all files with swagger directory ignored
        ignore_paths = ["resources/swagger/"]
        files = get_text_files(self.test_dir, ignore_paths)
        
        # Convert to set of relative paths for easier comparison
        relative_paths = {os.path.relpath(f, self.test_dir) for f in files}
        
        # Files that should be included
        expected_files = {
            os.path.normpath("src/main/resources/config.properties"),
            os.path.normpath("src/main/java/com/example/Test.java"),
            os.path.normpath("src/test/resources/test.properties"),
        }
        
        # Files that should not be included
        excluded_files = {
            os.path.normpath("src/main/resources/swagger/swagger-ui.js"),
            os.path.normpath("src/main/resources/swagger/index.html"),
            os.path.normpath("src/resources/swagger/swagger-ui-core.js"),
        }
        
        # Verify expected files are included
        for expected_file in expected_files:
            self.assertIn(
                expected_file, 
                relative_paths, 
                f"File {expected_file} should be included"
            )
        
        # Verify swagger files are excluded
        for excluded_file in excluded_files:
            self.assertNotIn(
                excluded_file, 
                relative_paths, 
                f"File {excluded_file} should be excluded"
            )

    def test_multiple_ignore_patterns(self):
        # Test with multiple ignore patterns
        ignore_paths = ["resources/swagger/", "test/resources/"]
        files = get_text_files(self.test_dir, ignore_paths)
        relative_paths = {os.path.relpath(f, self.test_dir) for f in files}
        
        # Only these files should remain
        expected_files = {
            os.path.normpath("src/main/resources/config.properties"),
            os.path.normpath("src/main/java/com/example/Test.java"),
        }
        
        # These should all be excluded
        excluded_files = {
            os.path.normpath("src/main/resources/swagger/swagger-ui.js"),
            os.path.normpath("src/main/resources/swagger/index.html"),
            os.path.normpath("src/resources/swagger/swagger-ui-core.js"),
            os.path.normpath("src/test/resources/test.properties"),
        }
        
        for expected_file in expected_files:
            self.assertIn(
                expected_file, 
                relative_paths, 
                f"File {expected_file} should be included"
            )
        
        for excluded_file in excluded_files:
            self.assertNotIn(
                excluded_file, 
                relative_paths, 
                f"File {excluded_file} should be excluded"
            )

if __name__ == '__main__':
    unittest.main() 