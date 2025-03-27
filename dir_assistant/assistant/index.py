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
    
    # Initialize ignore handler
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
            rel_path = os.path.join(rel_root, d) if rel_root != '.' else d
            if not ignore_handler.is_ignored(rel_path):
                filtered_dirs.append(d)
        dirs[:] = filtered_dirs
        
        # Filter files using the same ignore handler
        for filename in files:
            # Skip .gitignore file itself
            if filename == '.gitignore':
                continue
                
            # Use relative path for ignore check
            rel_path = os.path.join(rel_root, filename) if rel_root != '.' else filename
            abs_path = os.path.join(root, filename)
            
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
    # Start with current directory
    files_with_contents = get_files_with_contents(".", ignore_paths, cache_db, use_git_ignore)

    # Add files from additional folders
    for folder in extra_dirs:
        # Convert relative paths to absolute to ensure they exist check works properly
        abs_folder_path = os.path.abspath(folder)
        if os.path.exists(abs_folder_path):
            folder_files = get_files_with_contents(abs_folder_path, ignore_paths, cache_db, use_git_ignore)
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
    lines = contents.split("\n")
    current_chunk = ""
    start_line_number = 1
    chunks = []
    embeddings_list = []

    if verbose:
        print(
            f"{Fore.LIGHTBLACK_EX}Creating embeddings for {filepath}{Style.RESET_ALL}"
        )
    for line_number, line in enumerate(lines, start=1):
        # Process each line individually if needed
        line_content = line
        while line_content:
            proposed_chunk = current_chunk + line_content + "\n"
            chunk_header = f"---------------\n\nUser file '{filepath}' lines {start_line_number}-{line_number}:\n\n"
            proposed_text = chunk_header + proposed_chunk
            chunk_tokens = embed.count_tokens(proposed_text)

            if chunk_tokens <= embed_chunk_size:
                current_chunk = proposed_chunk
                break  # The line fits in the current chunk, break out of the inner loop
            else:
                # Split line if too large for a new chunk
                if current_chunk == "":
                    split_point = find_split_point(
                        embed, line_content, embed_chunk_size, chunk_header
                    )
                    current_chunk = line_content[:split_point] + "\n"
                    line_content = line_content[split_point:]
                else:
                    # Save the current chunk as it is, and start a new one
                    chunks.append(
                        {
                            "tokens": embed.count_tokens(chunk_header + current_chunk),
                            "text": chunk_header + current_chunk,
                            "filepath": filepath,
                        }
                    )
                    embedding = embed.create_embedding(chunk_header + current_chunk)
                    embeddings_list.append(embedding)
                    current_chunk = ""
                    start_line_number = line_number  # Next chunk starts from this line
                    # Do not break; continue processing the line

    # Add the remaining content as the last chunk
    if current_chunk:
        chunk_header = f"---------------\n\nUser file '{filepath}' lines {start_line_number}-{len(lines)}:\n\n"
        chunks.append(
            {
                "tokens": embed.count_tokens(chunk_header + current_chunk),
                "text": chunk_header + current_chunk,
                "filepath": filepath,
            }
        )
        embedding = embed.create_embedding(chunk_header + current_chunk)
        embeddings_list.append(embedding)

    return chunks, embeddings_list


def find_split_point(embed, line_content, max_size, header):
    for split_point in range(1, len(line_content)):
        if embed.count_tokens(header + line_content[:split_point] + "\n") >= max_size:
            return split_point - 1
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
    
    with ThreadPoolExecutor(max_workers=10) as executor:
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
