import os
import tempfile
import shutil
from pathlib import Path
import pytest

from dir_assistant.assistant.index import get_text_files, preprocess_ignore_patterns
from dir_assistant.cli.config import load_config


class MockArgs:
    """Mock command line arguments for testing."""
    def __init__(self):
        self.ignore = ["**/.editorconfig", ".editorconfig"]
        self.dirs = []
        self.verbose = True
        self.no_color = True
        self.use_gitignore = False
        self.verbose_show_ignored = False
        self.single_prompt = None


class TestEditorConfigCLI:
    """Test that .editorconfig files are properly ignored via CLI arguments."""
    
    def test_editorconfig_cli_arguments(self):
        """Test that .editorconfig files are properly ignored via CLI arguments."""
        # Create a temporary directory with an .editorconfig file and a code file
        with tempfile.TemporaryDirectory() as tempdir:
            # Create target directory structure
            target_dir = os.path.join(tempdir, "test_project")
            os.makedirs(target_dir)
            
            # Create files
            editorconfig_path = os.path.join(target_dir, ".editorconfig")
            code_path = os.path.join(target_dir, "code.py")
            
            with open(editorconfig_path, "w") as f:
                f.write("# EditorConfig file\nroot = true\n")
            
            with open(code_path, "w") as f:
                f.write("print('Hello world')\n")
            
            # Prepare arguments and config
            args = MockArgs()
            args.dirs = [target_dir]
            
            # Load the actual config
            config_dict = load_config()
            
            # Get the proper config section - it might be nested
            config = config_dict["DIR_ASSISTANT"] if "DIR_ASSISTANT" in config_dict else config_dict
            
            # Process ignore paths the same way the CLI does
            ignore_paths = args.ignore if args.ignore else []
            ignore_paths.extend(config["GLOBAL_IGNORES"])
            
            # Make a copy to avoid modification (matching the new implementation)
            full_ignore_paths = list(ignore_paths)
            processed_ignore_paths = preprocess_ignore_patterns(full_ignore_paths)
            
            # Test 1: Verify that processed patterns include .editorconfig
            assert ".editorconfig" in processed_ignore_paths or "**/.editorconfig" in processed_ignore_paths
            
            # Test 2: Try getting text files with the processed patterns
            text_files = get_text_files(target_dir, processed_ignore_paths, use_git_ignore=False)
            assert "code.py" in text_files
            assert ".editorconfig" not in text_files
            
            # Store the processed ignore paths in args for completeness (matching the new implementation)
            args.full_ignore_paths = full_ignore_paths
            args.processed_ignore_paths = processed_ignore_paths
            
            print("All tests passed - CLI arguments correctly ignore .editorconfig files") 