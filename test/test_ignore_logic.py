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

if __name__ == '__main__':
    unittest.main() 