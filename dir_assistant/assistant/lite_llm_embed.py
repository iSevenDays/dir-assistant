from time import sleep

from litellm import embedding, token_counter

from dir_assistant.assistant.base_embed import BaseEmbed


class LiteLlmEmbed(BaseEmbed):
    def __init__(self, lite_llm_embed_model, chunk_size=8192, delay=0):
        self.lite_llm_model = lite_llm_embed_model
        self.chunk_size = chunk_size
        self.delay = delay

    def create_embedding(self, text):
        """Create embedding for the given text, with safety checks for token limits.
        
        Args:
            text: The text to embed
            
        Returns:
            The embedding vector
        """
        if self.delay:
            sleep(self.delay)
        if not text:
            text = "--empty--"
        
        # Safety check: ensure text doesn't exceed model's context window
        token_count = self.count_tokens(text)
        if token_count > self.chunk_size:
            print(f"WARNING: Text exceeds embedding model context window ({token_count} > {self.chunk_size})")
            print(f"Emergency truncating text to approximately {self.chunk_size} tokens")
            # Recursive binary search to find largest prefix under token limit
            truncated_text = self._truncate_text(text, self.chunk_size)
            return embedding(model=self.lite_llm_model, input=truncated_text, timeout=600)["data"][0]["embedding"]
        
        return embedding(model=self.lite_llm_model, input=text, timeout=600)["data"][0]["embedding"]

    def _truncate_text(self, text, max_tokens, min_tokens=0):
        """Truncate text to fit within max_tokens using binary search.
        
        Args:
            text: Text to truncate
            max_tokens: Maximum number of tokens allowed
            min_tokens: Minimum number of tokens to keep
            
        Returns:
            Truncated text that fits within max_tokens
        """
        if self.count_tokens(text) <= max_tokens:
            return text
        
        left, right = min_tokens, len(text)
        best_text = text[:min_tokens] + "..." if min_tokens > 0 else "..."
        
        while left < right:
            mid = left + (right - left) // 2
            current_text = text[:mid] + "..." # Add ellipsis to indicate truncation
            token_count = self.count_tokens(current_text)
            
            if token_count <= max_tokens:
                best_text = current_text
                left = mid + 1
            else:
                right = mid
        
        return best_text

    def get_chunk_size(self):
        return self.chunk_size

    def count_tokens(self, text):
        return token_counter(
            model=self.lite_llm_model, messages=[{"role": "user", "content": text}]
        )
