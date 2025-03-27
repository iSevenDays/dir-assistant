import os
import sys

import numpy as np
from colorama import Fore, Style
from faiss import IndexFlatL2
from sqlitedict import SqliteDict
from concurrent.futures import ThreadPoolExecutor

from dir_assistant.cli.config import HISTORY_FILENAME, STORAGE_PATH, CACHE_PATH, get_file_path
from dir_assistant.assistant.ignore_handler import IgnoreHandler

INDEX_CACHE_FILENAME = "index_cache.sqlite"

TEXT_CHARS = bytearray({7, 8, 9, 10, 12, 13, 27} | set(range(0x20, 0x100)) - {0x7F})


def is_text_file(filepath):
    """Check if a file is a text file by looking at its content."""
    try:
        with open(filepath, "rb") as f:
            return not bool(f.read(1024).translate(None, TEXT_CHARS))
    except Exception:
        return False


def get_text_files(directory=".", ignore_paths=None, use_git_ignore=False):
    """Get all text files in a directory, respecting ignore patterns.
    
    Args:
        directory: Base directory to search in.
        ignore_paths: List of gitignore-style patterns or path to ignore file.
            If None, no additional ignore patterns will be used.
        use_git_ignore: Whether to also load and respect .gitignore files in the directory tree.
            
    Returns:
        List of relative paths to text files.
    """
    text_files = []
    # Convert target directory to absolute path
    base_dir = os.path.abspath(directory)
    
    # Always use an empty list for ignore_paths if None, since we only support .gitignore files
    if ignore_paths is None:
        ignore_paths = []
    
    # Pre-filter for any basename ignore patterns that might apply to any file
    # This includes patterns like dot files that should be ignored regardless of directory
    basename_ignores = set()
    dot_file_patterns = set()
    
    for pattern in ignore_paths:
        # Direct filename matches (most common for dot files)
        if pattern.startswith('.') and '/' not in pattern:
            basename_ignores.add(pattern)
            dot_file_patterns.add(pattern)
        # Directory-independent patterns with leading **/ (matches any level)  
        elif pattern.startswith('**/') and '/' not in pattern[3:]:
            basename_ignores.add(pattern[3:])
            # If it also starts with a dot, add to dot file patterns
            if pattern[3:].startswith('.'):
                dot_file_patterns.add(pattern[3:])
    
    # Initialize ignore handler with properly processed patterns
    ignore_handler = IgnoreHandler(
        patterns=ignore_paths,
        use_git_ignore=use_git_ignore,
        base_dir=base_dir
    )
    
    # Walk the directory tree
    for root, dirs, files in os.walk(base_dir, followlinks=True):
        # Get relative paths for checking ignore patterns
        rel_root = os.path.relpath(root, base_dir)
        
        # Filter directories first to optimize traversal
        filtered_dirs = []
        for d in dirs:
            # Skip directories that match basename patterns
            if d in basename_ignores:
                continue
                
            rel_path = os.path.join(rel_root, d) if rel_root != '.' else d
            if not ignore_handler.is_ignored(rel_path):
                filtered_dirs.append(d)
        dirs[:] = filtered_dirs
        
        # Filter files using multiple strategies for robustness without hardcoding
        for filename in files:
            # STRATEGY 1: Fast path - Skip files that match basename patterns directly
            if filename in basename_ignores:
                continue

            # STRATEGY 2: Extra robust check for dot files 
            if filename.startswith('.') and filename in dot_file_patterns:
                continue
                
            # STRATEGY 3: Skip .gitignore file itself
            if filename == '.gitignore':
                continue
                
            # Use relative path for ignore check
            rel_path = os.path.join(rel_root, filename) if rel_root != '.' else filename
            abs_path = os.path.join(root, filename)
            
            # FINAL STRATEGY: Full ignore handler check
            if (os.path.isfile(abs_path) and
                not ignore_handler.is_ignored(rel_path) and
                is_text_file(abs_path)):
                # Return the relative path
                text_files.append(rel_path)
    
    return sorted(text_files)  # Sort for consistent ordering


def get_files_with_contents(directory, ignore_paths, cache_db, use_git_ignore=False):
    text_files = get_text_files(directory, ignore_paths, use_git_ignore)
    files_with_contents = []
    # Convert directory to absolute path to ensure consistent path resolution
    base_dir = os.path.abspath(directory)
    
    with SqliteDict(cache_db, autocommit=True) as cache:
        for filepath in text_files:
            # Resolve the file path relative to the specified directory
            abs_path = os.path.join(base_dir, filepath)
            
            try:
                file_stat = os.stat(abs_path)
                file_info = cache.get(filepath)
                if file_info and file_info["mtime"] == file_stat.st_mtime:
                    files_with_contents.append(file_info)
                else:
                    try:
                        with open(abs_path, "r") as file:
                            contents = file.read()
                    except UnicodeDecodeError:
                        print(
                            f"{Fore.LIGHTBLACK_EX}Skipping {filepath} because it is not a text file.{Style.RESET_ALL}"
                        )
                        continue
                    file_info = {
                        "filepath": os.path.abspath(abs_path),
                        "contents": contents,
                        "mtime": file_stat.st_mtime,
                    }
                    cache[filepath] = file_info
                    files_with_contents.append(file_info)
            except (FileNotFoundError, PermissionError) as e:
                print(f"{Fore.LIGHTBLACK_EX}Error accessing {abs_path}: {str(e)}{Style.RESET_ALL}")
                continue
    return files_with_contents


def create_file_index(
    embed, ignore_paths, embed_chunk_size, extra_dirs=[], verbose=False, use_git_ignore=False
):
    cache_db = get_file_path(CACHE_PATH, INDEX_CACHE_FILENAME)
    if verbose:
        print(f"cache_db path: {cache_db}")
        
    # The ignore_paths should already be processed by setup_ignore_patterns() from start.py
    # No need to process them again here
    if verbose:
        print(f"Using processed ignore patterns: {ignore_paths}")
        
    # Start with current directory
    files_with_contents = get_files_with_contents(".", ignore_paths, cache_db, use_git_ignore)

    # Add files from additional folders
    for folder in extra_dirs:
        # Convert relative paths to absolute to ensure they exist check works properly
        abs_folder_path = os.path.abspath(folder)
        if os.path.exists(abs_folder_path):
            if verbose:
                print(f"Processing additional directory: {abs_folder_path}")
                
            # Apply the same ignore patterns to the target directory
            folder_files = get_files_with_contents(abs_folder_path, ignore_paths, cache_db, use_git_ignore)
            
            if verbose:
                # Debug info - check for important dot files
                dot_patterns = [p for p in ignore_paths if p.startswith('.') or 
                             (p.startswith('**/') and p[3:].startswith('.'))]
                if dot_patterns:
                    print(f"Dot-related patterns: {dot_patterns}")
                    
            files_with_contents.extend(folder_files)
        else:
            if verbose:
                print(
                    f"{Fore.YELLOW}Warning: Additional folder {folder} does not exist{Style.RESET_ALL}"
                )

    if not files_with_contents:
        if verbose:
            print(
                f"{Fore.YELLOW}Warning: No text files found, creating first-file.txt...{Style.RESET_ALL}"
            )
        with open("first-file.txt", "w") as file:
            file.write(
                "Dir-assistant requires a file to be initialized, so this one was created because "
                "the directory was empty."
            )
        files_with_contents = get_files_with_contents(".", ignore_paths, cache_db, use_git_ignore)

    chunks = []
    embeddings_list = []
    with SqliteDict(cache_db, autocommit=True) as cache:
        # Separate cached and non-cached files
        files_to_process = {}
        for file_info in files_with_contents:
            filepath = file_info["filepath"]
            cached_chunks = cache.get(f"{filepath}_chunks")
            if cached_chunks and cached_chunks["mtime"] == file_info["mtime"]:
                if verbose:
                    print(f"Using cached embeddings for {filepath}")
                chunks.extend(cached_chunks["chunks"])
                embeddings_list.extend(cached_chunks["embeddings"])
            else:
                # Add to processing batch
                files_to_process[filepath] = file_info["contents"]

        # Process non-cached files concurrently
        if files_to_process:
            file_chunks, file_embeddings = process_files_concurrently(
                embed, files_to_process, embed_chunk_size, verbose
            )
            chunks.extend(file_chunks)
            embeddings_list.extend(file_embeddings)
            
            # Update cache for processed files
            for filepath, contents in files_to_process.items():
                file_info = next(fi for fi in files_with_contents if fi["filepath"] == filepath)
                cache[f"{filepath}_chunks"] = {
                    "chunks": [chunk for chunk in file_chunks if chunk["filepath"] == filepath],
                    "embeddings": [emb for emb, chunk in zip(file_embeddings, file_chunks) if chunk["filepath"] == filepath],
                    "mtime": file_info["mtime"],
                }

    if verbose:
        print(f"{Fore.LIGHTBLACK_EX}Creating index from embeddings...{Style.RESET_ALL}")
    embeddings = np.array(embeddings_list)
    index = IndexFlatL2(embeddings.shape[1])
    index.add(embeddings)
    return index, chunks


def process_file(embed, filepath, contents, embed_chunk_size, verbose=False):
    """Process a file into chunks that fit within the embedding model's context window.
    
    Args:
        embed: The embedding model to use
        filepath: Path to the file being processed
        contents: Content of the file
        embed_chunk_size: Maximum number of tokens per chunk
        verbose: Whether to print verbose output
        
    Returns:
        Tuple of (chunks, embeddings)
    """
    lines = contents.split("\n")
    current_chunk = ""
    start_line_number = 1
    chunks = []
    embeddings_list = []
    max_tokens = embed_chunk_size - 50  # Leave margin for safety

    if verbose:
        print(f"{Fore.LIGHTBLACK_EX}Creating embeddings for {filepath}{Style.RESET_ALL}")
        
    for line_number, line in enumerate(lines, start=1):
        # Process each line individually if needed
        line_content = line
        while line_content:
            # Create proposed chunk by adding this line to current chunk
            proposed_chunk = current_chunk + line_content + "\n"
            chunk_header = f"---------------\n\nUser file '{filepath}' lines {start_line_number}-{line_number}:\n\n"
            proposed_text = chunk_header + proposed_chunk
            chunk_tokens = embed.count_tokens(proposed_text)
            
            if verbose and chunk_tokens > max_tokens:
                print(f"{Fore.LIGHTBLACK_EX}Chunk exceeds token limit: {chunk_tokens}/{max_tokens} - splitting{Style.RESET_ALL}")

            if chunk_tokens <= max_tokens:
                # Line fits, add it to current chunk and move to next line
                current_chunk = proposed_chunk
                break
            else:
                # Line doesn't fit, need to handle differently depending on current state
                if current_chunk == "":
                    # Current chunk is empty but line is still too big, need to split the line
                    split_point = find_split_point(embed, line_content, max_tokens, chunk_header)
                    
                    if split_point == 0:  # Cannot split further
                        if verbose:
                            print(f"{Fore.YELLOW}WARNING: Cannot chunk line effectively in {filepath}, line {line_number}{Style.RESET_ALL}")
                        # Force a minimum split to avoid infinite loop
                        split_point = min(100, len(line_content) // 2) if len(line_content) > 100 else 1
                    
                    # Take first part of line and continue processing the rest
                    current_chunk = line_content[:split_point] + "\n"
                    line_content = line_content[split_point:]
                    
                    # Verify the chunk is actually under the limit
                    test_text = chunk_header + current_chunk
                    test_tokens = embed.count_tokens(test_text)
                    
                    if test_tokens > max_tokens:
                        if verbose:
                            print(f"{Fore.YELLOW}WARNING: Split chunk still exceeds token limit ({test_tokens}/{max_tokens}){Style.RESET_ALL}")
                        # Emergency split - reduce size further
                        current_chunk = current_chunk[:len(current_chunk)//2] + "...\n"
                else:
                    # Current chunk has content, save it and start a new chunk with this line
                    chunk_text = chunk_header + current_chunk
                    token_count = embed.count_tokens(chunk_text)
                    
                    if token_count > max_tokens and verbose:
                        print(f"{Fore.YELLOW}WARNING: Chunk exceeds token limit ({token_count}/{max_tokens}){Style.RESET_ALL}")
                    
                    chunks.append({
                        "tokens": token_count,
                        "text": chunk_text,
                        "filepath": filepath,
                    })
                    embedding = embed.create_embedding(chunk_text)
                    embeddings_list.append(embedding)
                    
                    # Reset for next chunk
                    current_chunk = ""
                    start_line_number = line_number  # Next chunk starts from this line
                    # Don't break - continue processing current line

    # Add the remaining content as the last chunk
    if current_chunk:
        chunk_header = f"---------------\n\nUser file '{filepath}' lines {start_line_number}-{len(lines)}:\n\n"
        chunk_text = chunk_header + current_chunk
        token_count = embed.count_tokens(chunk_text)
        
        if token_count > max_tokens and verbose:
            print(f"{Fore.YELLOW}WARNING: Final chunk exceeds token limit ({token_count}/{max_tokens}){Style.RESET_ALL}")
            
        chunks.append({
            "tokens": token_count,
            "text": chunk_text,
            "filepath": filepath,
        })
        embedding = embed.create_embedding(chunk_text)
        embeddings_list.append(embedding)

    if verbose:
        print(f"{Fore.LIGHTBLACK_EX}Created {len(chunks)} chunks for {filepath}{Style.RESET_ALL}")
        
    return chunks, embeddings_list


def find_split_point(embed, line_content, max_size, header):
    """Find a point to split the line content to fit within max_size tokens.
    
    Args:
        embed: The embedding model to use for token counting
        line_content: The line content to split
        max_size: The maximum number of tokens allowed
        header: The header text that will be prepended to the content
        
    Returns:
        The index at which to split the line content
    """
    # Start with a binary search to quickly narrow down the range
    left, right = 0, len(line_content)
    
    # Handle the case where even a single character exceeds max_size with header
    if embed.count_tokens(header + line_content[:1] + "\n") > max_size:
        return 0
        
    while left < right:
        mid = (left + right) // 2
        if mid == left:  # Avoid infinite loop
            break
            
        token_count = embed.count_tokens(header + line_content[:mid] + "\n")
        
        if token_count < max_size:
            left = mid
        else:
            right = mid
    
    # Fine-tune: find the largest point that stays under max_size
    for split_point in range(left, min(right + 1, len(line_content))):
        if embed.count_tokens(header + line_content[:split_point] + "\n") > max_size:
            return split_point - 1 if split_point > 0 else 0
    
    # If we got here, the entire content fits
    return len(line_content)


def search_index(embed, index, query, all_chunks):
    query_embedding = embed.create_embedding(query)
    distances, indices = index.search(
        np.array([query_embedding]), 100
    )  # 819,200 tokens max with default embedding
    relevant_chunks = [all_chunks[i] for i in indices[0] if i != -1]
    return relevant_chunks


def clear(args, config_dict):
    files = [
        get_file_path(CACHE_PATH, INDEX_CACHE_FILENAME),
        get_file_path(STORAGE_PATH, HISTORY_FILENAME),
    ]
    for file in files:
        if os.path.exists(file):
            os.remove(file)
            sys.stdout.write(f"Deleted {file}\n")
        else:
            sys.stdout.write(f"{file} does not exist.\n")


def process_files_concurrently(embed, files, embed_chunk_size, verbose):
    """Process multiple files in parallel using thread workers"""
    all_chunks = []
    all_embeddings = []
    
    with ThreadPoolExecutor(max_workers=1) as executor:
        # Create list of tasks
        tasks = [
            (embed, filepath, contents, embed_chunk_size, verbose)
            for filepath, contents in files.items()
        ]
        
        # Process files in parallel
        results = executor.map(lambda p: process_file(*p), tasks)
        
        # Collect results
        for file_chunks, file_embeddings in results:
            all_chunks.extend(file_chunks)
            all_embeddings.extend(file_embeddings)
            
    return all_chunks, all_embeddings


def preprocess_ignore_patterns(ignore_paths):
    """Process ignore patterns to ensure they work across different directories.
    
    This ensures patterns like dot files (e.g., ".editorconfig", ".git") will match 
    in any directory context, making the patterns directory-independent.
    
    Args:
        ignore_paths: List of gitignore-style patterns
        
    Returns:
        Processed list of patterns that will work in any directory context
    """
    if not ignore_paths:
        return []
        
    processed_patterns = []
    for pattern in ignore_paths:
        # Skip patterns that are already directory-independent (start with **)
        if pattern.startswith("**/"):
            processed_patterns.append(pattern)
            continue
            
        # Special handling for dot files and simple filenames
        # If pattern is a simple filename (no path separator) or starts with a dot
        if "/" not in pattern:
            # Add the original pattern (for the current directory)
            processed_patterns.append(pattern)
            
            # Also add a directory-independent version (for --dirs folders)
            # This ensures it works in any directory context
            processed_patterns.append(f"**/{pattern}")
        else:
            # Regular pattern - pass through as is
            processed_patterns.append(pattern)
            
    return processed_patterns


def debug_ignore_patterns(directory, ignore_paths, use_git_ignore=False):
    """Debug function to see which files would be ignored with the given patterns.
    
    Args:
        directory: Base directory to check in
        ignore_paths: List of ignore patterns to apply (already processed by setup_ignore_patterns)
        use_git_ignore: Whether to also respect .gitignore files
        
    Returns:
        Dictionary with info about which files are ignored and why
    """
    abs_dir = os.path.abspath(directory)
    
    # The patterns should already be processed when this function is called
    # We don't need to preprocess them again
    processed_patterns = ignore_paths
    
    # Set up the ignore handler with debug mode enabled
    ignore_handler = IgnoreHandler(
        patterns=processed_patterns,
        use_git_ignore=use_git_ignore,
        base_dir=abs_dir,
        debug=True  # Enable detailed logging
    )
    
    # Identify basename patterns (including dot files) for quick filtering
    basename_patterns = [
        p for p in processed_patterns 
        if "/" not in p  # Direct filename patterns without path separators
        or (p.startswith("**/") and "/" not in p[3:])  # Directory-independent single file patterns
    ]
    
    results = {
        "directory": abs_dir,
        "patterns": processed_patterns,
        "files": {},
        "basename_patterns": basename_patterns
    }
    
    # Walk the directory and check each file
    for root, dirs, files in os.walk(abs_dir, followlinks=True):
        rel_root = os.path.relpath(root, abs_dir)
        
        # Check files in this directory
        for filename in files:
            rel_path = os.path.join(rel_root, filename) if rel_root != '.' else filename
            abs_path = os.path.join(root, filename)
            
            if os.path.isfile(abs_path):
                # Check if this file would be ignored
                is_ignored = ignore_handler.is_ignored(rel_path)
                
                # Check if it matches any basename pattern
                matches_basename = filename in basename_patterns or any(
                    p[3:] == filename for p in basename_patterns if p.startswith("**/")
                )
                
                # Store result
                results["files"][rel_path] = {
                    "ignored": is_ignored,
                    "basename": os.path.basename(rel_path),
                    "is_hidden": filename.startswith("."),
                    "matches_basename_pattern": matches_basename
                }
    
    return results
