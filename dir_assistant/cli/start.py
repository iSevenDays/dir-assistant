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


def get_config_section(config_dict):
    """Extract the appropriate config section from the configuration dictionary.
    
    Args:
        config_dict: The full configuration dictionary
        
    Returns:
        The DIR_ASSISTANT section if it exists, otherwise the full config
    """
    return config_dict["DIR_ASSISTANT"] if "DIR_ASSISTANT" in config_dict else config_dict


def setup_ignore_patterns(args, config_dict):
    """Set up and process all ignore patterns consistently.
    
    This centralizes pattern handling to ensure consistent behavior across
    all parts of the application.
    
    Args:
        args: The command line arguments containing ignore patterns
        config_dict: The configuration dictionary with global ignores
        
    Returns:
        tuple: (processed_ignore_paths, full_ignore_paths)
    """
    # Get the proper config section
    config = get_config_section(config_dict)
    
    # Get all command line ignore patterns
    all_cli_ignore_patterns = args.ignore if args.ignore else []
    
    # Combine CLI ignores with global ignores
    full_ignore_paths = list(all_cli_ignore_patterns)  # Make a copy to avoid modification issues
    full_ignore_paths.extend(config["GLOBAL_IGNORES"])
    
    # Process for consistency across directories
    processed_ignore_paths = preprocess_ignore_patterns(full_ignore_paths)
    
    # Store for use in other functions
    args.full_ignore_paths = full_ignore_paths
    args.processed_ignore_paths = processed_ignore_paths
    
    return processed_ignore_paths, full_ignore_paths


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


def print_ignore_pattern_debug(original_patterns, processed_patterns, mode=""):
    """Print debug information about ignore patterns.
    
    Args:
        original_patterns: The original unprocessed patterns
        processed_patterns: The processed patterns after preprocessing
        mode: Optional context label for the output (e.g., "single-prompt mode")
    """
    title = f"Ignore patterns{' in ' + mode if mode else ''}:"
    print(f"{Fore.GREEN}{title}{Style.RESET_ALL}")
    print(f"{Fore.LIGHTBLACK_EX}Original patterns: {original_patterns}{Style.RESET_ALL}")
    print(f"{Fore.LIGHTBLACK_EX}Processed patterns: {processed_patterns}{Style.RESET_ALL}")


def print_embedding_debug_info(is_local, model_info, chunk_size, request_delay=None):
    """Print debug information about the embedding model configuration.
    
    Args:
        is_local: Whether the model is local or remote
        model_info: Name or path of the model
        chunk_size: Chunk size for the embedding model
        request_delay: Optional delay between requests (for remote models)
    """
    model_type = "local" if is_local else "remote"
    print(f"{Fore.LIGHTBLACK_EX}Using {model_type} embedding model with chunk size: {chunk_size}{Style.RESET_ALL}")
    
    if model_info:
        print(f"{Fore.LIGHTBLACK_EX}  Model: {model_info}{Style.RESET_ALL}")
    
    if request_delay is not None:
        print(f"{Fore.LIGHTBLACK_EX}  Request delay: {request_delay}{Style.RESET_ALL}")


def run_single_prompt(args, config_dict):
    # Set up ignore patterns if they haven't been processed yet
    if not hasattr(args, 'processed_ignore_paths'):
        setup_ignore_patterns(args, config_dict)
    
    # For diagnostic purposes in verbose mode
    if args.verbose and not args.verbose_show_ignored:  # Only show if not already shown
        print_ignore_pattern_debug(args.full_ignore_paths, args.processed_ignore_paths, "single-prompt mode")
    
    llm = initialize_llm(args, config_dict, chat_mode=False)
    llm.initialize_history()
    response = llm.run_stream_processes(args.single_prompt, True)

    # Only print the final response
    sys.stdout.write(response)


def validate_model_config(is_local, model_name, model_config_key, model_type="LLM"):
    """Validate that the required model configuration is present.
    
    Args:
        is_local: Whether a local model is being used
        model_name: The model name from config
        model_config_key: The configuration key for the model
        model_type: Type of model (LLM or embedding) for error messages
        
    Raises:
        SystemExit: If required configuration is missing
    """
    if not model_name:
        print(
            f"""You must specify {model_config_key}. Use 'dir-assistant config open' and \
see readme for more information. Exiting..."""
        )
        exit(1)


def initialize_llm(args, config_dict, chat_mode=True):
    # Get the proper config section
    config = get_config_section(config_dict)

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

    # Check for basic missing model configs using the helper function
    validate_model_config(
        active_model_is_local, 
        config["LLM_MODEL"], 
        "LLM_MODEL", 
        "LLM"
    )
    
    if not active_model_is_local:
        validate_model_config(
            False, 
            lite_llm_model, 
            "LITELLM_MODEL", 
            "LLM"
        )
    
    # Check for basic missing embedding model configs
    validate_model_config(
        active_embed_is_local, 
        config["EMBED_MODEL"], 
        "EMBED_MODEL", 
        "embedding"
    )
    
    if not active_embed_is_local:
        validate_model_config(
            False, 
            lite_llm_embed_model, 
            "LITELLM_EMBED_MODEL", 
            "embedding"
        )

    extra_dirs = args.dirs if args.dirs else []

    # Initialize the embedding model
    if verbose:
        print(f"{Fore.LIGHTBLACK_EX}Loading embedding model...{Style.RESET_ALL}")
    
    if active_embed_is_local:
        embed = LlamaCppEmbed(
            model_path=embed_model_file, embed_options=llama_cpp_embed_options
        )
        embed_chunk_size = embed.get_chunk_size()
        if verbose:
            print_embedding_debug_info(
                is_local=True,
                model_info=embed_model_file,
                chunk_size=embed_chunk_size
            )
    else:
        embed = LiteLlmEmbed(
            lite_llm_embed_model=lite_llm_embed_model,
            chunk_size=lite_llm_embed_chunk_size,
            delay=lite_llm_embed_request_delay,
        )
        embed_chunk_size = lite_llm_embed_chunk_size
        if verbose:
            print_embedding_debug_info(
                is_local=False,
                model_info=lite_llm_embed_model,
                chunk_size=embed_chunk_size,
                request_delay=lite_llm_embed_request_delay
            )

    # Make sure ignore patterns have been processed
    if not hasattr(args, 'processed_ignore_paths'):
        processed_ignore_paths, _ = setup_ignore_patterns(args, config_dict)
    else:
        # Get processed ignore paths - args.processed_ignore_paths is guaranteed to be set by now
        processed_ignore_paths = args.processed_ignore_paths
    
    # Debug print for verbose mode
    if verbose:
        print_ignore_pattern_debug(args.full_ignore_paths, processed_ignore_paths, "file indexing")
        
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

    # Set up all ignore patterns - do this first thing
    processed_ignore_paths, full_ignore_paths = setup_ignore_patterns(args, config_dict)

    # Handle --verbose-show-ignored flag
    if args.verbose_show_ignored:
        print(f"{Fore.GREEN}Analyzing ignore patterns...{Style.RESET_ALL}")
        print_ignore_pattern_debug(full_ignore_paths, processed_ignore_paths)
        
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
    commit_to_git = config["COMMIT_TO_GIT"]
    embed = llm.embed
    active_embed_is_local = config["ACTIVE_EMBED_IS_LOCAL"]
    embed_chunk_size = (
        config["LITELLM_EMBED_CHUNK_SIZE"]
        if not active_embed_is_local
        else embed.get_chunk_size()
    )

    # Start file watcher with processed ignore paths - use the patterns we already processed earlier
    watcher = start_file_watcher(
        ".", 
        embed, 
        args.processed_ignore_paths,
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
