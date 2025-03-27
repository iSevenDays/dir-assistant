import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from dir_assistant.cli.start import setup_ignore_patterns


class TestMultipleIgnoreArgs(unittest.TestCase):
    """Test that multiple --ignore arguments from command line are properly handled."""
    
    def test_multiple_ignore_flags(self):
        """Test that multiple --ignore flags are all collected correctly."""
        # Mock args as if they came from argparse with multiple --ignore flags
        mock_args = MagicMock()
        # Simulate multiple --ignore flags from command line 
        mock_args.ignore = [
            "**/docker/**",
            "**/.git/**",
            "**/.vscode/**",
            "**/node_modules/**",
            "**/build/**",
            "**/.idea/**",
            "**/__pycache__/**",
            "**/dist/**",
            "**/resources/swagger/**",
            "**/.editorconfig",
            ".editorconfig"
        ]
        mock_args.use_gitignore = False
        
        # Mock config with some global ignores
        mock_config = {
            "DIR_ASSISTANT": {
                "GLOBAL_IGNORES": [
                    ".git/",
                    ".vscode/",
                    "node_modules/",
                    "build/",
                    ".idea/",
                    "__pycache__",
                    "dist/"
                ]
            }
        }
        
        # Process the ignore patterns
        processed_patterns, full_patterns = setup_ignore_patterns(mock_args, mock_config)
        
        # Verify .editorconfig patterns are included in the processed patterns
        self.assertTrue(any(pattern.endswith('.editorconfig') for pattern in processed_patterns), 
                       "'.editorconfig' pattern missing from processed patterns")
        self.assertTrue(any(pattern.endswith('.editorconfig') for pattern in full_patterns),
                      "'.editorconfig' pattern missing from full patterns")
        
        # Verify that both versions of the pattern exist (original and directory-independent)
        editorconfig_patterns = [p for p in processed_patterns if p.endswith('.editorconfig')]
        self.assertGreaterEqual(len(editorconfig_patterns), 2, 
                              "Should have both original and directory-independent .editorconfig patterns")
        
        # Verify that all command line patterns made it to the full list
        for cli_pattern in mock_args.ignore:
            self.assertIn(cli_pattern, full_patterns, f"CLI pattern '{cli_pattern}' missing from full patterns")


if __name__ == '__main__':
    unittest.main() 