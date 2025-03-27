import argparse
import sys
import unittest

from dir_assistant.main import AppendMultipleAction


class TestArgparseMultipleIgnores(unittest.TestCase):
    """Test how argparse handles multiple --ignore arguments"""
    
    def test_multiple_ignore_flags(self):
        """Test that multiple --ignore flags are properly collected"""
        parser = argparse.ArgumentParser(description="Test parser")
        parser.add_argument(
            "-i",
            "--ignore",
            type=str,
            nargs="+",
            action=AppendMultipleAction,
            help="A list of space-separated filepaths to ignore."
        )
        
        # Simulate command line with multiple --ignore flags
        test_args = [
            "--ignore", "pattern1", "pattern2",
            "--ignore", "pattern3", "pattern4",
            "--ignore", ".editorconfig"
        ]
        args = parser.parse_args(test_args)
        
        # Check that all patterns are collected
        self.assertEqual(
            args.ignore,
            ["pattern1", "pattern2", "pattern3", "pattern4", ".editorconfig"]
        )
        
    def test_space_separated_single_ignore(self):
        """Test how argparse handles a single --ignore with multiple values"""
        parser = argparse.ArgumentParser(description="Test parser")
        parser.add_argument(
            "-i",
            "--ignore",
            type=str,
            nargs="+",
            action=AppendMultipleAction,
            help="A list of space-separated filepaths to ignore."
        )
        
        # Simulate command line with one --ignore flag and multiple values
        test_args = [
            "--ignore", "pattern1", "pattern2", "pattern3", "pattern4", ".editorconfig"
        ]
        args = parser.parse_args(test_args)
        
        # Check that all patterns are collected
        self.assertEqual(
            args.ignore,
            ["pattern1", "pattern2", "pattern3", "pattern4", ".editorconfig"]
        )
        
    def test_multiple_dirs_flags(self):
        """Test that multiple --dirs flags are properly collected"""
        parser = argparse.ArgumentParser(description="Test parser")
        parser.add_argument(
            "-d",
            "--dirs",
            type=str,
            nargs="+",
            action=AppendMultipleAction,
            help="A list of space-separated directories to work on."
        )
        
        # Simulate command line with multiple --dirs flags
        test_args = [
            "--dirs", "/path/to/dir1", "/path/to/dir2",
            "--dirs", "/path/to/dir3",
            "--dirs", "../relative/path"
        ]
        args = parser.parse_args(test_args)
        
        # Check that all directories are collected
        self.assertEqual(
            args.dirs,
            ["/path/to/dir1", "/path/to/dir2", "/path/to/dir3", "../relative/path"]
        )


if __name__ == "__main__":
    unittest.main() 