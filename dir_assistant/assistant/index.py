import os
import sys

import numpy as np
from colorama import Fore, Style
from faiss import IndexFlatL2
from sqlitedict import SqliteDict
from concurrent.futures import ThreadPoolExecutor

from dir_assistant.cli.config import HISTORY_FILENAME, STORAGE_PATH, CACHE_PATH, get_file_path

INDEX_CACHE_FILENAME = "index_cache.sqlite"

TEXT_CHARS = bytearray({7, 8, 9, 10, 12, 13, 27} | set(range(0x20, 0x100)) - {0x7F})


def is_text_file(filepath):
    """Check if a file is a text file by looking at its content."""
    try:
        with open(filepath, "rb") as f:
            return not bool(f.read(1024).translate(None, TEXT_CHARS))
    except Exception:
        return False


def get_text_files(directory=".", ignore_paths=[]):
    text_files = []
    base_dir = os.path.abspath(directory)
    for root, dirs, files in os.walk(directory):
        # Convert root to absolute path for relative path calculation
        abs_root = os.path.abspath(root)
        
        # Filter directories first
        filtered_dirs = []
        for d in dirs:
            abs_dir_path = os.path.join(abs_root, d)
            rel_dir_path = os.path.relpath(abs_dir_path, base_dir)
            if not any(_is_path_ignored(rel_dir_path, ignore_path) for ignore_path in ignore_paths):
                filtered_dirs.append(d)
        dirs[:] = filtered_dirs

        for filename in files:
            abs_filepath = os.path.join(abs_root, filename)
            rel_filepath = os.path.relpath(abs_filepath, base_dir)
            
            if (
                os.path.isfile(abs_filepath)
                and not any(_is_path_ignored(rel_filepath, ignore_path) for ignore_path in ignore_paths)
                and is_text_file(abs_filepath)
            ):
                text_files.append(abs_filepath)
    return text_files


def _is_path_ignored(filepath, ignore_pattern):
    """
    Check if a filepath matches an ignore pattern.
    Handles both file and directory patterns correctly.
    """
    # Normalize both paths and convert to lowercase for case-insensitive matching
    norm_filepath = os.path.normpath(filepath).lower()
    # Handle both forward and backward slashes in ignore pattern
    norm_ignore = os.path.normpath(ignore_pattern.rstrip('/')).lower().replace('\\', '/')
    
    # Split paths into components, handling both slash types
    filepath_parts = norm_filepath.replace('\\', '/').split('/')
    ignore_parts = norm_ignore.split('/')
    
    # For each component in the filepath, check if it matches the ignore pattern
    for i in range(len(filepath_parts)):
        remaining_parts = filepath_parts[i:]
        # Check if we have enough remaining parts to match the ignore pattern
        if len(remaining_parts) >= len(ignore_parts):
            # Check if the next N components match the ignore pattern
            matches = True
            for j in range(len(ignore_parts)):
                if remaining_parts[j] != ignore_parts[j]:
                    matches = False
                    break
            if matches:
                return True
    
    return False


def get_files_with_contents(directory, ignore_paths, cache_db):
    text_files = get_text_files(directory, ignore_paths)
    files_with_contents = []
    with SqliteDict(cache_db, autocommit=True) as cache:
        for filepath in text_files:
            file_stat = os.stat(filepath)
            file_info = cache.get(filepath)
            if file_info and file_info["mtime"] == file_stat.st_mtime:
                files_with_contents.append(file_info)
            else:
                try:
                    with open(filepath, "r") as file:
                        contents = file.read()
                except UnicodeDecodeError:
                    print(
                        f"{Fore.LIGHTBLACK_EX}Skipping {filepath} because it is not a text file.{Style.RESET_ALL}"
                    )
                file_info = {
                    "filepath": os.path.abspath(filepath),
                    "contents": contents,
                    "mtime": file_stat.st_mtime,
                }
                cache[filepath] = file_info
                files_with_contents.append(file_info)
    return files_with_contents


def create_file_index(
    embed, ignore_paths, embed_chunk_size, extra_dirs=[], verbose=False
):
    cache_db = get_file_path(CACHE_PATH, INDEX_CACHE_FILENAME)
    if verbose:
        print(f"cache_db path: {cache_db}")
    # Start with current directory
    files_with_contents = get_files_with_contents(".", ignore_paths, cache_db)

    # Add files from additional folders
    for folder in extra_dirs:
        if os.path.exists(folder):
            folder_files = get_files_with_contents(folder, ignore_paths, cache_db)
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
        files_with_contents = get_files_with_contents(".", ignore_paths, cache_db)

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
