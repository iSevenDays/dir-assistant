from logging import info
import os
import logging
from traceback import print_exc
from typing import Optional, Callable, Any

from colorama import Fore, Style
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from dir_assistant.assistant.index import get_text_files, process_file
from dir_assistant.assistant.ignore_handler import IgnoreHandler

logger = logging.getLogger(__name__)

class FileChangeHandler(FileSystemEventHandler):
    """Handles file system events and updates the index accordingly."""
    
    def __init__(
        self,
        embed: Any,
        ignore_paths: Optional[list] = None,
        embed_chunk_size: int = 1024,
        llm_updated_index_callback: Optional[Callable] = None,
        base_dir: str = ".",
        use_git_ignore: bool = False
    ):
        """Initialize the file change handler.
        
        Args:
            embed: Embedding model instance
            ignore_paths: List of paths to ignore (should be preprocessed with preprocess_ignore_patterns)
            embed_chunk_size: Size of chunks for embedding
            llm_updated_index_callback: Callback when index is updated
            base_dir: Base directory to watch
            use_git_ignore: Whether to respect .gitignore files
        """
        self.embed = embed
        self.base_dir = os.path.abspath(base_dir)
        self.ignore_handler = IgnoreHandler(
            ignore_paths=ignore_paths,  # These should be preprocessed patterns
            use_git_ignore=use_git_ignore,
            base_dir=self.base_dir
        )
        self.embed_chunk_size = embed_chunk_size
        self.llm_updated_index_callback = llm_updated_index_callback

    def reindex_file(self, file_path: str) -> None:
        """Reindex a file if it's not ignored and is a text file.
        
        Args:
            file_path: Path to the file to reindex
        """
        if not file_path:
            return
            
        try:
            # Convert to absolute path and then get relative path for consistency
            abs_path = os.path.abspath(file_path)
            rel_path = os.path.relpath(abs_path, self.base_dir)
            
            # Check if file should be processed
            text_files = get_text_files(
                self.base_dir,
                self.ignore_handler.patterns,
                use_git_ignore=self.ignore_handler.use_git_ignore
            )
            
            if rel_path in text_files:
                try:
                    with open(abs_path, "r") as file:
                        contents = file.read()
                    chunks, embeddings = process_file(
                        self.embed,
                        rel_path,  # Use relative path for consistency
                        contents,
                        self.embed_chunk_size
                    )
                    if self.llm_updated_index_callback:
                        self.llm_updated_index_callback(rel_path, chunks, embeddings)
                except FileNotFoundError:
                    logger.warning(
                        f"{Fore.LIGHTBLACK_EX}Error updating file {rel_path}: "
                        f"File not found{Style.RESET_ALL}"
                    )
                except Exception as e:
                    logger.error(f"Error processing file {rel_path}: {e}")
                    print_exc()
        except Exception as e:
            logger.error(f"Error in reindex_file: {e}")
            print_exc()

    def on_any_event(self, event):
        """Handle any file system event.
        
        Args:
            event: The file system event
        """
        if (
            event.is_directory
            or event.event_type == "opened"
            or event.event_type == "closed"
            or event.event_type == "closed_no_write"
        ):
            return
        self.reindex_file(event.src_path)
        if hasattr(event, 'dest_path'):
            self.reindex_file(event.dest_path)


def start_file_watcher(
    directory: str,
    embed: Any,
    ignore_paths: Optional[list] = None,
    embed_chunk_size: int = 1024,
    llm_updated_index_callback: Optional[Callable] = None,
    use_git_ignore: bool = False
) -> Observer:
    """Start watching a directory for file changes.
    
    Args:
        directory: Directory to watch
        embed: Embedding model instance
        ignore_paths: List of paths to ignore (already preprocessed by setup_ignore_patterns)
        embed_chunk_size: Size of chunks for embedding
        llm_updated_index_callback: Callback when index is updated
        use_git_ignore: Whether to respect .gitignore files
        
    Returns:
        The file system observer
    """
    # Note: We're using the already processed ignore patterns from setup_ignore_patterns
    # No need to call preprocess_ignore_patterns again
    
    event_handler = FileChangeHandler(
        embed=embed,
        ignore_paths=ignore_paths,
        embed_chunk_size=embed_chunk_size,
        llm_updated_index_callback=llm_updated_index_callback,
        base_dir=directory,
        use_git_ignore=use_git_ignore
    )
    
    observer = Observer()
    observer.schedule(event_handler, directory, recursive=True)
    observer.start()
    
    return observer
