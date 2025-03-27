import os
import sys
import json

import litellm
from colorama import Fore, Style
from prompt_toolkit import prompt
from prompt_toolkit.history import FileHistory
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.keys import Keys

from dir_assistant.assistant.file_watcher import start_file_watcher
from dir_assistant.assistant.index import create_file_index, debug_ignore_patterns, preprocess_ignore_patterns
from dir_assistant.assistant.lite_llm_assistant import LiteLLMAssistant
from dir_assistant.assistant.lite_llm_embed import LiteLlmEmbed
from dir_assistant.assistant.llama_cpp_assistant import LlamaCppAssistant
from dir_assistant.assistant.llama_cpp_embed import LlamaCppEmbed
from dir_assistant.cli.config import (
    HISTORY_FILENAME,
    STORAGE_PATH,
    VERSION,
    get_file_path,
)

litellm.suppress_debug_info = True

MODELS_PATH = os.path.expanduser("~/.local/share/dir-assistant/models")


def display_startup_art(commit_to_git, no_color=False):
    sys.stdout.write(
        f"""{Style.RESET_ALL if no_color else Style.BRIGHT}{Style.RESET_ALL if no_color else Fore.GREEN}
  _____ _____ _____                                              
 |  __ \_   _|  __ \                                             
 | |  | || | | |__) |                                            
 | |  | || | |  _  /                                             
 | |__| || |_| | \ \                                             
 |_____/_____|_|_ \_\__ _____  _____ _______       _   _ _______ 
     /\    / ____/ ____|_   _|/ ____|__   __|/\   | \ | |__   __|
    /  \  | (___| (___   | | | (___    | |  /  \  |  \| |  | |   
   / /\ \  \___ \\\___ \  | |  \___ \   | | / /\ \ | . ` |  | |   
  / ____ \ ____) |___) |_| |_ ____) |  | |/ ____ \| |\  |  | |   
 /_/    \_\_____/_____/|_____|_____/   |_/_/    \_\_| \_|  |_|   
{Style.RESET_ALL}\n\n"""
    )
    color_prefix = Style.RESET_ALL if no_color else f"{Style.BRIGHT}{Fore.BLUE}"
    print(f"{color_prefix}Type 'exit' to quit the conversation.")
    if commit_to_git:
        print(f"{color_prefix}Type 'undo' to roll back the last commit.")
    print("")


def run_single_prompt(args, config_dict):
    # Get ignore paths the same way as in the start function
    ignore_paths = args.ignore if args.ignore else []
    config = config_dict["DIR_ASSISTANT"] if "DIR_ASSISTANT" in config_dict else config_dict
    ignore_paths.extend(config["GLOBAL_IGNORES"])
    
    # Process ignore patterns to ensure they work across directories - ALWAYS do this, not just in verbose mode
    processed_ignore_paths = preprocess_ignore_patterns(ignore_paths)
    
    # For diagnostic purposes in verbose mode
    if args.verbose and not args.verbose_show_ignored:  # Only show if not already shown
        print(f"{Fore.GREEN}Ignore patterns in single-prompt mode:{Style.RESET_ALL}")
        print(f"{Fore.LIGHTBLACK_EX}Original patterns: {ignore_paths}{Style.RESET_ALL}")
        print(f"{Fore.LIGHTBLACK_EX}Processed patterns: {processed_ignore_paths}{Style.RESET_ALL}")
    
    # Store processed patterns back in args for use in initialize_llm
    args.processed_ignore_paths = processed_ignore_paths
    
    llm = initialize_llm(args, config_dict, chat_mode=False)
    llm.initialize_history()
    response = llm.run_stream_processes(args.single_prompt, True)

    # Only print the final response
    sys.stdout.write(response)


def initialize_llm(args, config_dict, chat_mode=True):
    # Check if we're working with the full config dict or just DIR_ASSISTANT section
    config = (
        config_dict["DIR_ASSISTANT"] if "DIR_ASSISTANT" in config_dict else config_dict
    )

    # Main settings
    active_model_is_local = config["ACTIVE_MODEL_IS_LOCAL"]
    active_embed_is_local = config["ACTIVE_EMBED_IS_LOCAL"]
    context_file_ratio = config["CONTEXT_FILE_RATIO"]
    system_instructions = config["SYSTEM_INSTRUCTIONS"]

    # Llama.cpp settings
    llm_model_file = get_file_path(config["MODELS_PATH"], config["LLM_MODEL"])
    embed_model_file = get_file_path(config["MODELS_PATH"], config["EMBED_MODEL"])
    llama_cpp_options = config["LLAMA_CPP_OPTIONS"]
    llama_cpp_embed_options = config["LLAMA_CPP_EMBED_OPTIONS"]
    llama_cpp_completion_options = config["LLAMA_CPP_COMPLETION_OPTIONS"]

    # LiteLLM settings
    lite_llm_model = config["LITELLM_MODEL"]
    lite_llm_context_size = config["LITELLM_CONTEXT_SIZE"]
    lite_llm_model_uses_system_message = config["LITELLM_MODEL_USES_SYSTEM_MESSAGE"]
    lite_llm_pass_through_context_size = config["LITELLM_PASS_THROUGH_CONTEXT_SIZE"]
    lite_llm_embed_model = config["LITELLM_EMBED_MODEL"]
    lite_llm_embed_chunk_size = config["LITELLM_EMBED_CHUNK_SIZE"]
    lite_llm_embed_request_delay = float(config["LITELLM_EMBED_REQUEST_DELAY"])

    # Assistant settings
    use_cgrag = config["USE_CGRAG"]
    print_cgrag = config["PRINT_CGRAG"]
    output_acceptance_retries = config["OUTPUT_ACCEPTANCE_RETRIES"]
    commit_to_git = config["COMMIT_TO_GIT"]
    verbose = config["VERBOSE"] or args.verbose
    no_color = config["NO_COLOR"] or args.no_color

    # Check for basic missing model configs
    if active_model_is_local:
        if config["LLM_MODEL"] == "":
            print(
                """You must specify LLM_MODEL. Use 'dir-assistant config open' and \
    see readme for more information. Exiting..."""
            )
            exit(1)
    elif lite_llm_model == "":
        print(
            """You must specify LITELLM_MODEL. Use 'dir-assistant config open' and see readme \
for more information. Exiting..."""
        )
        exit(1)

    # Check for basic missing embedding model configs
    if active_embed_is_local:
        if config["EMBED_MODEL"] == "":
            print(
                """You must specify EMBED_MODEL. Use 'dir-assistant config open' and \
see readme for more information. Exiting..."""
            )
            exit(1)
    elif lite_llm_embed_model == "":
        print(
            """You must specify LITELLM_EMBED_MODEL. Use 'dir-assistant config open' and \
see readme for more information. Exiting..."""
        )
        exit(1)

    ignore_paths = args.ignore if args.ignore else []
    ignore_paths.extend(config["GLOBAL_IGNORES"])

    extra_dirs = args.dirs if args.dirs else []

    # Ensure ignore paths are preprocessed
    if hasattr(args, 'processed_ignore_paths'):
        processed_ignore_paths = args.processed_ignore_paths
    else:
        processed_ignore_paths = preprocess_ignore_patterns(ignore_paths)
        
    # Debug print for verbose mode
    if verbose:
        print(f"{Fore.LIGHTBLACK_EX}Using these processed ignore patterns for file index: {processed_ignore_paths}{Style.RESET_ALL}")

    # Initialize the embedding model
    if verbose:
        print(f"{Fore.LIGHTBLACK_EX}Loading embedding model...{Style.RESET_ALL}")
        # Add detailed logging for embedding configuration
        print(f"{Fore.LIGHTBLACK_EX}Embedding configuration:{Style.RESET_ALL}")
        print(f"{Fore.LIGHTBLACK_EX}  Model: {lite_llm_embed_model}{Style.RESET_ALL}")
        print(f"{Fore.LIGHTBLACK_EX}  Chunk size: {lite_llm_embed_chunk_size}{Style.RESET_ALL}")
        print(f"{Fore.LIGHTBLACK_EX}  Request delay: {lite_llm_embed_request_delay}{Style.RESET_ALL}")
        
    if active_embed_is_local:
        embed = LlamaCppEmbed(
            model_path=embed_model_file, embed_options=llama_cpp_embed_options
        )
        embed_chunk_size = embed.get_chunk_size()
        if verbose:
            print(f"{Fore.LIGHTBLACK_EX}Using local embedding model with chunk size: {embed_chunk_size}{Style.RESET_ALL}")
    else:
        embed = LiteLlmEmbed(
            lite_llm_embed_model=lite_llm_embed_model,
            chunk_size=lite_llm_embed_chunk_size,
            delay=lite_llm_embed_request_delay,
        )
        embed_chunk_size = lite_llm_embed_chunk_size
        if verbose:
            print(f"{Fore.LIGHTBLACK_EX}Using remote embedding model with chunk size: {embed_chunk_size}{Style.RESET_ALL}")

    # Create the file index
    if verbose or chat_mode:
        print(
            f"{Fore.LIGHTBLACK_EX}Creating file embeddings and index...{Style.RESET_ALL}"
        )
    index, chunks = create_file_index(
        embed, 
        processed_ignore_paths,  # Use processed ignore paths
        embed_chunk_size, 
        extra_dirs, 
        verbose,
        use_git_ignore=args.use_gitignore
    )

    # Set up the system instructions
    system_instructions_full = f"{system_instructions}\n\nThe user will ask questions relating \
    to files they will provide. Do your best to answer questions related to the these files. When \
    the user refers to files, always assume they want to know about the files they provided."

    # Initialize the LLM model
    if active_model_is_local:
        if verbose:
            print(f"{Fore.LIGHTBLACK_EX}Loading local LLM model...{Style.RESET_ALL}")
        llm = LlamaCppAssistant(
            llm_model_file,
            llama_cpp_options,
            system_instructions_full,
            embed,
            index,
            chunks,
            context_file_ratio,
            output_acceptance_retries,
            use_cgrag,
            print_cgrag,
            commit_to_git,
            llama_cpp_completion_options,
            verbose=verbose,
            no_color=no_color,
        )
    else:
        if verbose:
            print(f"{Fore.LIGHTBLACK_EX}Loading remote LLM model...{Style.RESET_ALL}")
        llm = LiteLLMAssistant(
            lite_llm_model,
            lite_llm_model_uses_system_message,
            lite_llm_context_size,
            lite_llm_pass_through_context_size,
            system_instructions,
            embed,
            index,
            chunks,
            context_file_ratio,
            output_acceptance_retries,
            use_cgrag,
            print_cgrag,
            commit_to_git,
            verbose=verbose,
            no_color=no_color,
        )

    return llm


def start(args, config_dict):
    single_prompt = args.single_prompt
    
    if config_dict["VERBOSE"]:
        print(f"dir-assistant {VERSION}")

    # Handle --verbose-show-ignored flag
    if args.verbose_show_ignored:
        ignore_paths = args.ignore if args.ignore else []
        ignore_paths.extend(config_dict["GLOBAL_IGNORES"])
        
        # Ensure we're using the same processed patterns that will be used later
        processed_ignore_paths = preprocess_ignore_patterns(ignore_paths)
        
        # Store processed patterns for use elsewhere in the code
        args.processed_ignore_paths = processed_ignore_paths
        
        print(f"{Fore.GREEN}Analyzing ignore patterns...{Style.RESET_ALL}")
        print(f"{Fore.LIGHTBLACK_EX}Input patterns: {ignore_paths}{Style.RESET_ALL}")
        print(f"{Fore.LIGHTBLACK_EX}Processed patterns that will be used: {processed_ignore_paths}{Style.RESET_ALL}")
        
        # Debug current directory first
        results = debug_ignore_patterns(".", processed_ignore_paths, args.use_gitignore)
        print(f"\n{Fore.GREEN}Results for current directory:{Style.RESET_ALL}")
        print_ignore_results(results)
        
        # Debug each extra directory
        extra_dirs = args.dirs if args.dirs else []
        for directory in extra_dirs:
            dir_results = debug_ignore_patterns(directory, processed_ignore_paths, args.use_gitignore)
            print(f"\n{Fore.GREEN}Results for directory '{directory}':{Style.RESET_ALL}")
            print_ignore_results(dir_results)
            
        # If this was a diagnostic command, exit after showing results
        if not single_prompt:
            sys.exit(0)

    if single_prompt:
        # For single prompt mode, many options are ignored
        config_dict["NO_COLOR"] = True
        config_dict["VERBOSE"] = False
        config_dict["COMMIT_TO_GIT"] = False

    llm = initialize_llm(args, config_dict, chat_mode=not single_prompt)
    llm.initialize_history()

    # If in single prompt mode, run the prompt and exit
    if single_prompt:
        llm.stream_chat(single_prompt)
        exit(0)

    # Get variables needed for file watcher and startup art
    is_full_config = "DIR_ASSISTANT" in config_dict
    config = config_dict["DIR_ASSISTANT"] if is_full_config else config_dict

    ignore_paths = args.ignore if args.ignore else []
    ignore_paths.extend(config["GLOBAL_IGNORES"])
    commit_to_git = config["COMMIT_TO_GIT"]
    embed = llm.embed
    active_embed_is_local = config["ACTIVE_EMBED_IS_LOCAL"]
    embed_chunk_size = (
        config["LITELLM_EMBED_CHUNK_SIZE"]
        if not active_embed_is_local
        else embed.get_chunk_size()
    )

    # Process ignore paths to ensure they work correctly in all directories
    processed_ignore_paths = preprocess_ignore_patterns(ignore_paths)
    
    # Start file watcher. It is running in another thread after this.
    watcher = start_file_watcher(
        ".", 
        embed, 
        processed_ignore_paths,  # Use processed ignore paths here
        embed_chunk_size, 
        llm.update_index_and_chunks,
        use_git_ignore=args.use_gitignore
    )

    # Display the startup art
    no_color = llm.no_color
    display_startup_art(commit_to_git, no_color=no_color)

    # Initialize history for prompt input
    history = FileHistory(get_file_path(STORAGE_PATH, HISTORY_FILENAME))

    # Begin the conversation
    while True:
        # Get user input
        color_prefix = "" if no_color else f"{Style.BRIGHT}{Fore.RED}"
        color_suffix = "" if no_color else Style.RESET_ALL
        sys.stdout.write(
            f"{color_prefix}You (Press ALT-Enter, OPT-Enter, or CTRL-O to submit): \n\n{color_suffix}"
        )
        # Configure key bindings for Option-Enter on macOS
        bindings = KeyBindings()

        @bindings.add(Keys.Escape, Keys.Enter)
        @bindings.add("escape", "enter")  # For Option-Enter on macOS
        def _(event):
            event.current_buffer.validate_and_handle()

        user_input = prompt("", multiline=True, history=history, key_bindings=bindings)

        if user_input.strip().lower() == "exit":
            break
        elif user_input.strip().lower() == "undo":
            os.system("git reset --hard HEAD~1")
            color_prefix = "" if args.no_color else Style.BRIGHT
            print(
                f"\n{color_prefix}Rolled back to the previous commit.{color_suffix}\n\n"
            )
            continue
        else:
            llm.stream_chat(user_input)


def print_ignore_results(results):
    """Print the results of ignore pattern analysis in a user-friendly format."""
    print(f"{Fore.LIGHTBLACK_EX}Directory: {results['directory']}{Style.RESET_ALL}")
    print(f"{Fore.LIGHTBLACK_EX}Patterns: {results['patterns']}{Style.RESET_ALL}")
    print(f"{Fore.LIGHTBLACK_EX}Basename patterns: {results['basename_patterns']}{Style.RESET_ALL}")
    
    # Count files ignored vs not ignored
    ignored_files = [f for f, data in results['files'].items() if data['ignored']]
    not_ignored_files = [f for f, data in results['files'].items() if not data['ignored']]
    
    print(f"\n{Fore.YELLOW}Summary:{Style.RESET_ALL}")
    print(f"  Total files: {len(results['files'])}")
    print(f"  Ignored: {len(ignored_files)}")
    print(f"  Not ignored: {len(not_ignored_files)}")
    
    # Show ignored files with details
    if ignored_files:
        print(f"\n{Fore.RED}Ignored files:{Style.RESET_ALL}")
        for filepath in sorted(ignored_files):
            data = results['files'][filepath]
            reason = "basename pattern match" if data['matches_basename_pattern'] else "pattern match"
            print(f"  {filepath} ({reason})")
    
    # Optionally show first few non-ignored files
    if not_ignored_files:
        print(f"\n{Fore.GREEN}Sample of non-ignored files (first 5):{Style.RESET_ALL}")
        for filepath in sorted(not_ignored_files)[:5]:
            print(f"  {filepath}")
    
    # Check for any hidden files that SHOULD have been ignored but weren't
    suspicious_files = [f for f, data in results['files'].items() 
                        if data['is_hidden'] and not data['ignored']]
    if suspicious_files:
        print(f"\n{Fore.RED}Warning: Found hidden files that are NOT being ignored:{Style.RESET_ALL}")
        for filepath in sorted(suspicious_files):
            print(f"  {filepath}")
