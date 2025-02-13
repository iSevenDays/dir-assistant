import unittest
import os
from dir_assistant.assistant.index import _is_path_ignored


class TestIgnoreLogic(unittest.TestCase):
    def test_ignore_swagger(self):
        # Test a swagger file in a nested path
        path = "my_projects/tst/src/main/resources/swagger/swagger-ui-core.js.map"
        pattern = "resources/swagger/"
        self.assertTrue(_is_path_ignored(path, pattern))

    def test_ignore_swagger_different_structure(self):
        # Test another structure
        path = "my_projects/tst/src/resources/swagger/swagger-ui-core.js.map"
        pattern = "resources/swagger/"
        self.assertTrue(_is_path_ignored(path, pattern))

    def test_non_ignore_file(self):
        # Test a file that should not be ignored
        path = "my_projects/tst/src/main/resources/some-other-folder/file.txt"
        pattern = "resources/swagger/"
        self.assertFalse(_is_path_ignored(path, pattern))

    def test_case_insensitive(self):
        # Test case insensitivity
        path = "/WORKSPACE/Projects/XYZ/src/main/Resources/Swagger/ui-es-bundle-core.js.map"
        pattern = "resources/swagger/"
        self.assertTrue(_is_path_ignored(path, pattern))

    def test_ignore_with_backslashes(self):
        # Test Windows style backslashes in path
        path = r"C:\workspace\projects\pool\src\main\resources\swagger\swagger-ui-es-bundle-core.js.map"
        pattern = "resources/swagger/"
        self.assertTrue(_is_path_ignored(path, pattern))

    # New tests for glob pattern matching
    def test_double_star_pattern(self):
        # Test ** pattern matching any number of directories
        path = "modules/java/org/company/core/swift/file.swift"
        pattern = "**/core/swift/**"
        self.assertTrue(_is_path_ignored(path, pattern))

    def test_double_star_no_match(self):
        # Test ** pattern not matching when pattern doesn't exist in path
        path = "modules/company/org/project/storage/other/ios/file.swift"
        pattern = "**/core/ios/**"
        self.assertFalse(_is_path_ignored(path, pattern))

    def test_single_star_pattern(self):
        # Test * pattern matching within a directory name
        path = "src/test/java/com/example/test123/MyTest.java"
        pattern = "test*/java"
        self.assertTrue(_is_path_ignored(path, pattern))

    def test_complex_pattern(self):
        # Test combination of * and ** patterns
        path = "src/components/java/company/storage/main/android/utils/Helper.java"
        pattern = "**/main/android/**/*.java"
        self.assertTrue(_is_path_ignored(path, pattern))

    def test_double_star_empty_match(self):
        # Test ** matching zero directories
        path = "core/ios/file.swift"
        pattern = "**/core/ios/**"
        self.assertTrue(_is_path_ignored(path, pattern))

    def test_double_star_at_end(self):
        # Test ** at the end of pattern
        path = "src/main/java/core/ios/deep/nested/file.swift"
        pattern = "core/ios/**"
        self.assertTrue(_is_path_ignored(path, pattern))

    def test_double_star_at_start(self):
        # Test ** at the start of pattern
        path = "very/deep/path/core/ios/file.swift"
        pattern = "**/core/ios"
        self.assertTrue(_is_path_ignored(path, pattern))

    def test_multiple_double_stars(self):
        # Test multiple ** patterns
        path = "src/test/java/core/something/ios/utils/file.swift"
        pattern = "**/core/**/ios/**"
        self.assertTrue(_is_path_ignored(path, pattern))


if __name__ == '__main__':
    unittest.main() 