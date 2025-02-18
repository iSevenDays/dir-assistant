import os
import tempfile
import shutil
import unittest

from dir_assistant.assistant.index import get_text_files


class TestGitIgnoreFlag(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.test_dir)
        
        # Set up a directory structure
        src_dir = os.path.join(self.test_dir, "src")
        os.makedirs(src_dir, exist_ok=True)
        
        # Create two test files in src
        with open(os.path.join(src_dir, "ignore.txt"), "w") as f:
            f.write("ignored")
        with open(os.path.join(src_dir, "keep.txt"), "w") as f:
            f.write("kept")
        
        # Create a .gitignore file that should ignore src/ignore.txt
        with open(os.path.join(self.test_dir, ".gitignore"), "w") as f:
            f.write("src/ignore.txt\n")
        
        # Create a .dirassistantignore file that would ignore src/keep.txt if used
        # But when --use-gitignore flag is enabled, only .gitignore patterns should be used
        with open(os.path.join(self.test_dir, ".dirassistantignore"), "w") as f:
            f.write("src/keep.txt\n")

    def test_files_with_gitignore_enabled(self):
        """Test that with use_git_ignore enabled, only .gitignore is respected."""
        # When gitignore is enabled, src/ignore.txt should be ignored,
        # while src/keep.txt should be present (since .dirassistantignore is not used).
        files = list(get_text_files(self.test_dir, ignore_paths=None, use_git_ignore=True))
        normalized = {os.path.normpath(f) for f in files}
        self.assertNotIn(os.path.normpath("src/ignore.txt"), normalized, msg="src/ignore.txt should be ignored due to .gitignore")
        self.assertIn(os.path.normpath("src/keep.txt"), normalized, msg="src/keep.txt should not be ignored as .dirassistantignore is not applied")

    def test_files_without_gitignore_enabled(self):
        """Test that with use_git_ignore disabled, no gitignore filtering is applied."""
        # When gitignore is disabled, both files should be included
        files = list(get_text_files(self.test_dir, ignore_paths=None, use_git_ignore=False))
        normalized = {os.path.normpath(f) for f in files}
        self.assertIn(os.path.normpath("src/ignore.txt"), normalized, msg="src/ignore.txt should be present when gitignore is disabled")
        self.assertIn(os.path.normpath("src/keep.txt"), normalized, msg="src/keep.txt should be present when gitignore is disabled")


if __name__ == "__main__":
    unittest.main() 