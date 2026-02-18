import pickle
from . import global_kv as gkv
import os
import re
from MCP import MCP_Client as mcp
from . import Message_Utilities as msgu
from . import String_Utilities as stru
from . import constants as c

PREFIX_FILE = "prefix"         # stores prefix messages (list of dicts)
KV_CACHE_FILE = "kv_cache.bin" # stores binary LlamaState (KV cache)

def gen_kv_cache_from_string(llm, messages):
    """
    Generate base KV cache and prefix messages.
    Saves:
       KV cache to KV_CACHE_FILE
       Prefix messages to PREFIX_FILE
    Also updates gkv.base_state and gkv.prefix in memory
    """
    llm.reset()
    # Populate KV cache with system messages
    prompt = msgu.build_chat(messages)
    tokens = llm.tokenize(prompt.encode("utf-8"), special = True)

    llm.eval(tokens)



    # Save KV cache to disk
    kv_state = llm.save_state()
    with open(KV_CACHE_FILE, "wb") as f:
        pickle.dump(kv_state, f)
    gkv.base_state = kv_state

    # Save prefix messages to disk
    with open(PREFIX_FILE, "wb") as f:
        pickle.dump(messages, f)
    gkv.prefix = messages

    return gkv.base_state, gkv.prefix

def load_prefix():
    """Load prefix messages into memory if gkv.prefix is None"""
    if getattr(gkv, "prefix", None) is None:
        if not os.path.exists(PREFIX_FILE):
            raise RuntimeError("Prefix file does not exist. Run gen_kv_cache_from_string first.")
        with open(PREFIX_FILE, "rb") as f:
            gkv.prefix = pickle.load(f)
    return gkv.prefix

def load_kv_cache():
    """Load KV cache into memory if gkv.base_state is None"""
    if getattr(gkv, "base_state", None) is None:
        if not os.path.exists(KV_CACHE_FILE):
            raise RuntimeError("KV cache file does not exist. Run gen_kv_cache_from_string first.")
        with open(KV_CACHE_FILE, "rb") as f:
            gkv.base_state = pickle.load(f)
    return gkv.base_state



def add_string_to_kv(string, llm, teams = None):
    load_prefix()
    
    # Add to in-memory prefix
    addendum = [{"role": "user", "content": string}]

    addendum_length,_ = msgu.messages_token_counter(llm, addendum)

    c.addtkv_token_count += addendum_length

    if c.context_total - (c.addtkv_token_count + c.basekv_token_count) < c.temp_ctx_overhead:
        print("-----------------------TRIMMING KV to avoid overflow-----------------------")
        trim_kv(llm, teams)



    gkv.prefix = msgu.merge_without_duplicates(gkv.prefix, addendum)
    
    # Update KV cache with new content
    tokens = llm.tokenize(
    msgu.build_chat(addendum).encode("utf-8"), special = True
    )

    llm.eval(tokens)

    gkv.base_state = llm.save_state()


def trim_kv(llm, teams):
    """
    Trim KV cache to keep only content up to and including </GLOBAL_CONTEXT>
    """

    prefix = load_prefix()

    # Rebuild prompt exactly how it was fed to model
    full_prompt = msgu.build_chat(prefix)

    if not stru.has_duplicate_ids(full_prompt):
        #print("Warning: Duplicate ID's not found, no KV trimming performed")
        return False

    match = re.search(r'</GLOBAL_CONTEXT>', full_prompt)
    if not match:
        print("Warning: </GLOBAL_CONTEXT> not found, no trimming performed")
        return False

    keep_text = full_prompt[:match.end()]

    # Tokenize EXACTLY how model sees it
    keep_tokens = llm.tokenize(keep_text.encode("utf-8"), special = True)
    keep_len = len(keep_tokens)

    # Remove everything AFTER keep_len
    # seq_id = 0 in most single-sequence usage
    llm._ctx.kv_cache_seq_rm(0, keep_len, -1)

    # Re-evaluate prefix tokens to sync internal counters
    llm.reset()
    llm.eval(keep_tokens)

    gkv.base_state = llm.save_state()

    # Update stored prefix
    gkv.prefix = prefix  # or trim messages structurally if needed

    # Re-add compressed changelog safely
    changelog = stru.compress_changelog(keep_text, teams)
    changelog_msg = [{"role": "user", "content": changelog}]
    add_string_to_kv(changelog_msg, llm, teams)

    return True



def remove_difference_from_kv(llm, token_index, original_prefix):
    llm.n_tokens = token_index
    
    gkv.base_state = llm.save_state()
    gkv.prefix = original_prefix.copy()
    print(f"Restored KV cache to {token_index} tokens")




def kv_dump(length):
        # Test KV cache functionality
        print("\n" + "="*60)
        print("KV CACHE TEST")
        print("="*60)
        prefix = load_prefix()
        if prefix:
            print(f"Prefix has {len(prefix)} messages")
            all_content = "\n".join([msg.get("content", "") for msg in prefix])
            last_1000 = all_content[-length:]
            print(f"\nLast 1000 chars of prefix:")
            print("-" * 60)
            print(last_1000)
            print("-" * 60)
            print("="*60 + "\n")