import unittest
import os
import tempfile
import shutil
import numpy as np
from pathlib import Path
from unittest.mock import patch, MagicMock

from dir_assistant.main import main
from dir_assistant.assistant.index import get_text_files
from dir_assistant.assistant.file_watcher import FileChangeHandler, start_file_watcher
from dir_assistant.assistant.ignore_handler import IgnoreHandler


class TestGitignoreCLI(unittest.TestCase):
    """Test cases for gitignore CLI functionality."""

    def setUp(self):
        """Create a temporary directory structure with test files."""
        self.test_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.test_dir)
        
        # Create test directory structure
        dirs = [
            "src",
            "src/__pycache__",
            "src/test files/with spaces",
            "src/special-chars/dash-name",
            "src/case/MIXED/Case",
            "backend",
            "backend/__pycache__",
            "backend/tests",
            "frontend/node_modules/react",
            "frontend/dist",
            "frontend/src/components",
            "docs",
        ]
        for dir_path in dirs:
            os.makedirs(os.path.join(self.test_dir, dir_path))
            
        # Create test files
        files = {
            "src/main.py": "print('main')",
            "src/utils.py": "print('utils')",
            "src/__pycache__/main.cpython-39.pyc": "cache",
            "src/test files/with spaces/test.txt": "test",
            "src/special-chars/dash-name/test-file.js": "test",
            "src/case/MIXED/Case/TEST.txt": "test",
            "backend/app.py": "print('app')",
            "backend/__pycache__/app.cpython-39.pyc": "cache",
            "backend/tests/test_app.py": "print('test')",
            "frontend/node_modules/react/index.js": "react",
            "frontend/dist/bundle.js": "bundle",
            "frontend/src/App.tsx": "app",
            "frontend/src/components/Button.tsx": "button",
            "docs/README.md": "readme",
            "config.json": "{}",
            ".env": "SECRET=123",
        }
        for rel_path, content in files.items():
            full_path = os.path.join(self.test_dir, rel_path)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            with open(full_path, "w") as f:
                f.write(content)
                
        # Create .gitignore file
        with open(os.path.join(self.test_dir, ".gitignore"), "w") as f:
            f.write("""
# Python
*.pyc
__pycache__/

# Node
node_modules/
dist/
*.tsx

# Environment
.env
""")

    @patch('dir_assistant.assistant.lite_llm_embed.LiteLlmEmbed.create_embedding')
    @patch('dir_assistant.assistant.index.IndexFlatL2')
    @patch('dir_assistant.assistant.index.process_files_concurrently')
    @patch('dir_assistant.assistant.index.get_files_with_contents')
    @patch('dir_assistant.assistant.index.SqliteDict')
    @patch('dir_assistant.assistant.file_watcher.FileChangeHandler')
    @patch('dir_assistant.assistant.file_watcher.Observer')
    @patch('prompt_toolkit.shortcuts.prompt')
    @patch('argparse.ArgumentParser')
    @patch('dir_assistant.main.start')
    @patch('dir_assistant.assistant.lite_llm_assistant.completion')
    def test_cli_argument_parsing(self, mock_litellm_completion, mock_start, mock_parser_class, mock_prompt, mock_observer, mock_handler_class, mock_sqlite_dict, mock_get_files, mock_process_files, mock_index_class, mock_embed):
        """Test that the --use-gitignore CLI argument is properly parsed."""
        # Mock LiteLLM completion
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message = MagicMock()
        mock_response.choices[0].message.content = "Test response"
        mock_response.model = "local/model"
        mock_response.id = "test-id"
        mock_response.created = 1234567890
        mock_response.object = "chat.completion"
        mock_response.usage = MagicMock()
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 5
        mock_response.usage.total_tokens = 15
        mock_litellm_completion.return_value = mock_response
        
        # Mock config with local model settings
        config = {
            'ACTIVE_MODEL_IS_LOCAL': True,
            'ACTIVE_EMBED_IS_LOCAL': True,
            'CONTEXT_FILE_RATIO': 0.8,
            'SYSTEM_INSTRUCTIONS': '',
            'LLM_MODEL': 'local/model',
            'EMBED_MODEL': 'local/model',
            'LLAMA_CPP_OPTIONS': {},
            'LLAMA_CPP_EMBED_OPTIONS': {},
            'LLAMA_CPP_COMPLETION_OPTIONS': {},
            'GLOBAL_IGNORES': [],
            'VERBOSE': False,
            'NO_COLOR': False,
            'USE_CGRAG': False,
            'PRINT_CGRAG': False,
            'OUTPUT_ACCEPTANCE_RETRIES': 3,
            'COMMIT_TO_GIT': False,
            'MODELS_PATH': os.path.expanduser('~/.local/share/dir-assistant/models'),
            'LITELLM_MODEL': 'local/model',
            'LITELLM_API_KEY': 'dummy',
            'LITELLM_API_BASE': None,
            'LITELLM_CONTEXT_SIZE': 4096,
            'LITELLM_MODEL_USES_SYSTEM_MESSAGE': True,
            'LITELLM_PASS_THROUGH_CONTEXT_SIZE': True,
            'LITELLM_EMBED_MODEL': 'local/model',
            'LITELLM_EMBED_CHUNK_SIZE': 512,
            'LITELLM_EMBED_REQUEST_DELAY': '0.0',
            'LITELLM_PROVIDER': 'local',
            'LITELLM_MODEL_TYPE': 'local',
            'LITELLM_COMPLETION_MODEL': 'local/model',
            'LITELLM_COMPLETION_API_KEY': 'dummy',
            'LITELLM_COMPLETION_API_BASE': None,
            'LITELLM_COMPLETION_PROVIDER': 'local',
            'LITELLM_COMPLETION_MODEL_TYPE': 'local',
        }
        
        # Mock prompt to simulate non-interactive mode
        mock_prompt.side_effect = EOFError()
        
        # Mock file processing
        mock_get_files.return_value = [{"filepath": "test.txt", "contents": "test content", "mtime": 123456789}]
        mock_process_files.return_value = (
            [{"filepath": "test.txt", "text": "test content", "tokens": 2}],
            [[0.1] * 384]
        )
        
        # Mock SQLite cache
        mock_cache = MagicMock()
        mock_cache.__enter__ = MagicMock(return_value=mock_cache)
        mock_cache.__exit__ = MagicMock(return_value=None)
        mock_cache.get.return_value = None
        mock_sqlite_dict.return_value = mock_cache
        
        # Mock file watcher
        mock_handler = MagicMock()
        mock_handler_class.return_value = mock_handler
        mock_observer_instance = MagicMock()
        mock_observer.return_value = mock_observer_instance
        
        # Mock index creation and search
        mock_index = MagicMock()
        mock_index.search.return_value = (np.array([[0.5]]), np.array([[0]]))
        mock_index_class.return_value = mock_index
        
        # Mock embedding
        mock_embed.return_value = {"embeddings": [[0.1] * 384]}
        
        # Mock args object
        mock_args = MagicMock()
        mock_args.use_gitignore = True
        mock_args.mode = None
        mock_args.ignore = None
        mock_args.dirs = None
        mock_args.single_prompt = "test prompt"
        mock_args.verbose = False
        mock_args.no_color = False
        mock_args.config = None
        mock_args.interactive = False
        mock_args.config_mode = None
        mock_args.models_mode = None
        mock_args.start_mode = None
        
        # Mock the ArgumentParser
        mock_parser = MagicMock()
        mock_parser.parse_args.return_value = mock_args
        mock_parser.add_argument = MagicMock()
        mock_parser.add_subparsers = MagicMock()
        mock_parser_class.return_value = mock_parser
        
        # Mock the config loading
        with patch('dir_assistant.cli.config.load_config') as mock_load_config:
            mock_load_config.return_value = {'DIR_ASSISTANT': config}
            
            # Run the main function
            main()
            
            # Verify start was called with correct arguments
            mock_start.assert_called_once()
            args = mock_start.call_args[0][0]
            self.assertTrue(args.use_gitignore)

    def test_get_text_files_with_gitignore(self):
        """Test that get_text_files respects .gitignore files when enabled."""
        # Get files with gitignore enabled
        files_with_gitignore = set(get_text_files(
            self.test_dir,
            ignore_paths=None,
            use_git_ignore=True
        ))
        
        # Files that should be included
        expected_files = {
            "src/main.py",
            "src/utils.py",
            "backend/app.py",
            "backend/tests/test_app.py",
            "docs/README.md",
            "config.json",
            "src/test files/with spaces/test.txt",
            "src/special-chars/dash-name/test-file.js",
            "src/case/MIXED/Case/TEST.txt",
        }
        
        # Convert paths to normalized form for comparison
        files_with_gitignore = {os.path.normpath(p) for p in files_with_gitignore}
        expected_files = {os.path.normpath(p) for p in expected_files}
        
        # Verify included files
        self.assertEqual(files_with_gitignore, expected_files)
            
    def test_gitignore_cache_invalidation(self):
        """Test that the gitignore cache is invalidated when files change."""
        # Create initial .gitignore
        gitignore_path = os.path.join(self.test_dir, ".gitignore")
        with open(gitignore_path, "w") as f:
            f.write("*.txt\n")
            
        handler = IgnoreHandler(use_git_ignore=True, base_dir=self.test_dir)
        
        # Initial check
        test_file = "test.txt"
        self.assertTrue(handler.is_ignored(test_file))
        
        # Modify .gitignore
        with open(gitignore_path, "w") as f:
            f.write("*.txt\n!important.txt\n")
            
        # Cache should be invalidated
        self.assertTrue(handler.is_ignored(test_file))
        self.assertFalse(handler.is_ignored("important.txt"))
        
    def test_gitignore_edge_cases(self):
        """Test edge cases in gitignore pattern matching."""
        # Create test files
        files = {
            ".hidden": "hidden file",
            "file.with.dots": "dotted file",
            "path/with spaces/file": "spaced file",
            "path/with-dash/file": "dashed file",
            "path/with_underscore/file": "underscored file",
            "path/with.special+chars/file": "special chars file",
            "very/deep/nested/path/file": "deeply nested file",
            "sibling1/file": "sibling 1",
            "sibling2/file": "sibling 2",
        }
        for rel_path, content in files.items():
            full_path = os.path.join(self.test_dir, rel_path)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            with open(full_path, "w") as f:
                f.write(content)
                
        # Create .gitignore with edge case patterns
        with open(os.path.join(self.test_dir, ".gitignore"), "w") as f:
            f.write("""
# Hidden files
.*
!.gitignore

# Files with special characters
file.with.*
path/with?spaces/
path/with[!a-z]dash/
path/with_*/
path/with.special+chars/

# Deep nesting
very/deep/

# Multiple patterns for same directory
sibling*/
""")
                
        handler = IgnoreHandler(use_git_ignore=True, base_dir=self.test_dir)
        
        # Test pattern matching
        self.assertTrue(handler.is_ignored(".hidden"))
        self.assertFalse(handler.is_ignored(".gitignore"))
        self.assertTrue(handler.is_ignored("file.with.dots"))
        self.assertTrue(handler.is_ignored("path/with spaces/file"))
        self.assertTrue(handler.is_ignored("path/with-dash/file"))
        self.assertTrue(handler.is_ignored("path/with_underscore/file"))
        self.assertTrue(handler.is_ignored("path/with.special+chars/file"))
        self.assertTrue(handler.is_ignored("very/deep/nested/path/file"))
        self.assertTrue(handler.is_ignored("sibling1/file"))
        self.assertTrue(handler.is_ignored("sibling2/file"))
        
    def test_gitignore_precedence(self):
        """Test gitignore pattern precedence rules following git's actual behavior:
        1. More specific (deeper) patterns take precedence over more general ones
        2. Negative patterns can override positive patterns from parent .gitignore
        3. Only explicitly ignored patterns in child .gitignore remain ignored
        """
        # Create nested .gitignore files
        with open(os.path.join(self.test_dir, ".gitignore"), "w") as f:
            f.write("*.log\n")
            
        os.makedirs(os.path.join(self.test_dir, "subdir"))
        with open(os.path.join(self.test_dir, "subdir", ".gitignore"), "w") as f:
            f.write("!*.log\n*.debug.log\n")
            
        handler = IgnoreHandler(use_git_ignore=True, base_dir=self.test_dir)
        
        # Test pattern precedence
        self.assertTrue(handler.is_ignored("test.log"))
        self.assertFalse(handler.is_ignored("subdir/test.log"))  # Child rule (!*.log) takes precedence
        self.assertTrue(handler.is_ignored("subdir/test.debug.log"))
        
    def test_ignore_handler_path_normalization(self):
        """Test path normalization in ignore handler."""
        with open(os.path.join(self.test_dir, ".gitignore"), "w") as f:
            f.write("*.txt\n!src/*.txt\n")
            
        handler = IgnoreHandler(use_git_ignore=True, base_dir=self.test_dir)
        
        # Test with different path formats
        self.assertTrue(handler.is_ignored("test.txt"))
        self.assertFalse(handler.is_ignored("src/test.txt"))
        self.assertTrue(handler.is_ignored("./test.txt"))
        self.assertFalse(handler.is_ignored("./src/test.txt"))
        self.assertTrue(handler.is_ignored("subdir/../test.txt"))
        self.assertFalse(handler.is_ignored("subdir/../src/test.txt"))


if __name__ == '__main__':
    unittest.main() 