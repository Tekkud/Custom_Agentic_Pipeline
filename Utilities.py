
from llama_cpp import Llama
from llama_cpp import llama_tokenize
import random
import pickle
from global_context import GLOBAL_CONTEXT
import global_kv as gkv
import os
import copy
import re
import importlib.util
import ctypes
import ast
import MCP_Client as mcp

base_ctx = None
basekv_token_count = 0
addtkv_token_count = 0
temp_ctx_overhead = 0
context_total = 40000
cache_on = False
# '''
# General Implementation
# ----------------------
# Functions in this category are general purpose and not specific to the agent flow
# '''

def load_model(model_path, n_gpu_layers = -1, n_ctx = None, use_mmap = False, verbose = False, temperature = .7, min_p = 0.0, top_p = .9, top_k = 0, repeat_penalty = 1.15):
    if n_ctx == None:
        n_ctx = context_total
    llm = Llama(
        model_path = model_path,
        n_gpu_layers = n_gpu_layers,
        n_ctx = n_ctx,
        use_mmap = use_mmap,
        verbose = verbose,
        temperature = temperature,
        top_p = top_p,
        min_p =  min_p,
        top_k = top_k,
        flash_attn=False,
        repeat_penalty = repeat_penalty
    )
    return llm

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
    prompt = build_chat(messages)
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




#We eliminate chat complete because of formatting issues
def build_chat(messages):
    output = ""
    for msg in messages:
        role = msg["role"]
        content = msg["content"]
        output += f"<|im_start|>{role}\n{content}<|im_end|>\n"
    return output

# # path = "/home/harry/Documents/textgen/textgen-portable-3.13-linux-cuda12.4/text-generation-webui-3.13/user_data/models/FluentlyLM-Prinum.IQ4_XS.gguf"
# # llm = load_model(model_path= path, n_ctx = 10000)
# # messages = []

# # initial = {"role":"user","content":"content1"}
# # example = {"role":"user","content":"content"}
# # last = {"role":"user","content":"contentlast"}
# # messages.append(initial)
# # messages.append(example)
# # messages.append(example)
# # messages.append(example)
# # messages.append(last)


# '''"
#     convert messages to prompt format (for tokenization)
# '''
def messages_token_counter(llm, messages):
    value = 0
    prompt = ""
    for message in messages:
        role = message["role"]
        content = message["content"]
        prompt += f"{role.upper()}: {content}\n"
    value = len(llm.tokenize(prompt.encode('utf-8'), special = True))
    return value, prompt

# # value,_ = messages_token_counter(llm, messages)

# # print(value)

def messages_trim(llm, messages):
    if messages == []:
        return
    while messages_token_counter(llm, messages)[0] > (llm.context_params.n_ctx - basekv_token_count - addtkv_token_count): #prevent OOM
        if len(messages) <= 1:
            messages.clear()
            return
        else:
            del messages[1]

# # messages_trim(llm, messages, 15)

# # _,prompt = messages_token_counter(llm, messages)

# # print(prompt)


# '''
#     add messages from string
# '''
def add_message(llm, messages, string, role):
    message = {"role": role, "content": string}
    messages.append(message)




def str2msg(role, string):
    message = {"role": role, "content": string}
# '''
#     run inference -->str
# '''
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


def remove_reasoning_tags(text: str) -> str:
    """
    Remove various reasoning/thinking tag formats.
    Handles: <think>, <reasoning>, <thought>, etc.
    """
    # Common thinking tag patterns
    patterns = [
        r'<think>.*?</think>',
        r'<thinking>.*?</thinking>',
        r'<reasoning>.*?</reasoning>',
        r'<thought>.*?</thought>',
        r'<reflection>.*?</reflection>',
    ]
    
    cleaned = text
    for pattern in patterns:
        cleaned = re.sub(pattern, '', cleaned, flags=re.DOTALL | re.IGNORECASE)
    
    # Clean up whitespace
    cleaned = re.sub(r'\n\s*\n+', '\n\n', cleaned)
    return cleaned.strip()





def generate_output(llm, context, current_role, seed = None, max_tokens = 30000, suppress_caching = False):
    import random
    if seed is None:
        seed = random.randint(0, 2**31 - 1)

    # Create stop condition
    stop_strings = [
    "<|im_end|>",
    "<|im_start|>",
    "<|im_start|>user",
    "<|im_start|>system",
    "<|end_of_text|>",
    "<|endoftext|>",
    "\nUser:",
    "\n<|im_start|>",
    "human",
    "Human",
    f"</{current_role.upper()}>"
]
    

    

    stop_condition = make_stop_condition(llm, stop_strings)

    # Load prefix and KV cache
    prefix_messages = load_prefix()
    gkv.base_state = load_kv_cache()
    llm.load_state(gkv.base_state)
    
    # Merge and build prompt
    context_ephemeral = merge_without_duplicates(prefix_messages, context)

    #print("="*20 + "PREFIX FINAL MESSAGE" + "="*20 + f"\n{prefix_messages[-1]['content']}")
          
    # Build only the NEW part of the prompt (not the prefix)
    new_messages = context_ephemeral[len(prefix_messages):]

    numnew = 0
    print("="*20 + "NEW MESSAGES MESSAGES" + "="*20)
    #for newmsg in new_messages:
    #    print(f"Message number {numnew}\n")
    #    print(newmsg['content'])
    #    numnew += 1

    tokens_before_gen = llm.n_tokens
    
    # Eval each new message into the KV cache individually
    for msg in new_messages:
        msg_text = build_chat([msg])
        msg_tokens = llm.tokenize(msg_text.encode("utf-8"), add_bos=False, special = True)
        llm.eval(msg_tokens)

    # Only need the assistant prompt now
    if context[-1]['content'].strip().endswith("/think"):
        new_part = f"<|im_start|>assistant\n<think>"
    else:
        new_part = f"<|im_start|>assistant\n"


#check tokenization
    withoutthink = llm.tokenize(new_part.encode("utf-8"), special = True)

    reset_tokens = llm.n_tokens + len(withoutthink)

    tokens = llm.tokenize(new_part.encode("utf-8"), special = True)
    output_tokens = []
    # Don't reset - keep the loaded KV cache
    num_to_remove = 0 #used for selective caching with thinking tokens
    og_prefix = None
    tokens_upto = None
    num_removed = -2
    start = True
    last_think_index = None
    think_tokens = llm.tokenize("</think>".encode("utf-8"), special=True)
    
    for token in llm.generate(
        tokens=tokens,
        top_k=20,
        top_p=0.8,
        min_p=0.0,
        temp=0.7,
        repeat_penalty=1.0,
        frequency_penalty=0.0,
        presence_penalty=0.0,
        reset=False,
    ):
        output_tokens.append(token)

        # edge case to handle /think cache management - ***IMPORTANT*** this assumes you are operating without flash attention and/or forks of the core llama cpp library
        # which may make n_tokens return value unreliable. If your context include flash attention, hidden token injections etc this approach can corrupe kv cache.
        # However if using the base repo with cuda acceleration, this is significantly faster than a full load/unload

            # The implementation below is greedy and assumes <think> injected at start- Qwen a3b has inconsisted nested pairings, so per-pair implementation was removed

        
        if output_tokens[-len(think_tokens):] == think_tokens:
            last_think_index = len(output_tokens) - len(think_tokens)

            
        if token == llm.token_eos():
            break     

        # Check stop condition
        should_stop, output_tokens = stop_condition(token, output_tokens)
        if should_stop:
            break

        
        
        # Check max tokens
        if len(output_tokens) >= max_tokens:
            break


    if last_think_index is not None:
        del output_tokens[0:last_think_index + len(think_tokens)]
        llm.n_tokens -= last_think_index + len(think_tokens)

    # Convert to string
    response_text = llm.detokenize(output_tokens).decode("utf-8", errors="ignore")
    
    # Roll back kv cache if not cached
    if cache_on and not suppress_caching:
        gkv.prefix = context_ephemeral
        gkv.base_state = llm.save_state()
    else:
        llm.n_tokens = tokens_before_gen
        gkv.base_state = llm.save_state()

    response_text = response_text
    return response_text

def strip_role_tags(text):
    text = re.sub(r'^\s*(<.*?>)\s*', '', text)
    text = re.sub(r'\s*(<.*?>)\s*$', '', text)
    return text


# MCP integration groans - * async everything *:(
async def infer(
    llm,
    context, agent_role,
    suppress_caching = False,
    seed = None, max_tokens = 30000, tools = True
):
    init_msg = context[-1]['content']

    inference = generate_output(llm, context, agent_role, suppress_caching = suppress_caching, max_tokens = max_tokens)

    if tools:
        abort_pattern = r"\[ABORT\]"
        match = list(re.finditer(abort_pattern, inference, re.DOTALL))
        if match:
            abort_msg = f"Tool Use Attempt Aborted. {init_msg}"
            add_message(llm, context, abort_msg, "system")
            await infer(llm, context, agent_role, suppress_caching, seed, max_tokens, tools)
        combined_pattern = r"<tool_call>(.*?)</tool_call>"
        matches = list(re.finditer(combined_pattern, inference, re.DOTALL))
        if matches:
            prefix_og = None
            token_index = None
            if cache_on:
                prefix_og = copy.deepcopy(load_prefix())
                token_index = llm.n_tokens
            add_message(llm, context, inference, "assistant")
            tool_summary = await tool_loop(matches, context, llm, agent_role, init_msg)
            if token_index and prefix_og:
                remove_difference_from_kv(llm, token_index, prefix_og)
            tool_summary = tool_summary + f"\n Reminder: <ROLE: {agent_role}> {agent_role} can no longer call tools. Resuming: {init_msg}"
            add_message(llm, context, tool_summary, "assistant")
            end_msg = f"Important: {agent_role} may not call any more tools. They must now proceed to their assigned task."
            add_message(llm, context, end_msg, "system")
            inference = generate_output(llm, context, agent_role, suppress_caching = suppress_caching, max_tokens = max_tokens)
    return inference


import json
#cache is kept for duration of tool loop
async def tool_loop(matches, context, llm, agent_name, original_task, cache_on_copy=None, context_copy=None, num_calls=0, max_calls=5):
    context_copy = copy.deepcopy(context)
    inference = ""
    for match in matches:
        block_text = match.group(1)
        print("Matched block:", repr(block_text))

        try:
            result = json.loads(block_text.strip())
        except Exception as e:
            print("Error parsing tool call:", e)
            print(block_text)
            continue

        # Call the tool
        output = await mcp.call_tool(result['name'], result['arguments'])
        #Reference: https://github.com/modelcontextprotocol/modelcontextprotocol/tree/main/schema
        output = output.content[0].text
        print("Output:", output[:100])

        # Format output for model
        output_msg = (
            "\n<<TOOL OUTPUT>>\n" + output +
            "\n<<TOOL OUTPUT>>\n" +
            f"If you are done calling tools you will proceed to the summarization section. Stop calling tools if you have enough information to respond to: {original_task} /think"
        )

        # Update caching variables
        global cache_on
        cache_on_copy = cache_on
        cache_on = True

        add_message(llm, context_copy, output_msg, "user")
        inference = generate_output(llm, context_copy, agent_name)
        add_message(llm, context_copy, inference, "assistant")

        # Check for further tool calls
        combined_pattern = r"(<tool_call>(.*?)</tool_call>)"
        next_matches = list(re.finditer(combined_pattern, inference, re.DOTALL))

        if next_matches and num_calls < max_calls:
            await tool_loop(next_matches, context, llm, agent_name, original_task, cache_on_copy, context_copy, num_calls=num_calls+1, max_calls=max_calls)
            return

    # Summarization section
    summary_prompt = f'''SUMMARY SECTION -

Now that the tool calling section is over, you must do the following:
Condense the information provided by the tool calls into a well-formatted summary. Keep only important and necessary information.
Summary:'''
    add_message(llm, context_copy, summary_prompt, "system")

    summary_error = True
    timeout = 0
    summary = ""
    while summary_error and timeout < 4:
        summary = generate_output(llm, context_copy, agent_name)
        print(f"in summarization loop. Received {summary}")
        kv_dump(1000)
        # Check for tool calls in summary
        combined_pattern = r"{(.*?)}"
        matches = list(re.finditer(combined_pattern, summary, re.DOTALL))
        if matches or len(summary.strip()) < 5:
            error_msg = "ERROR: DO NOT call any tools in your response. Do not include any json in your response. Please provide a summary of the information from this tool use session now and nothing else /think"
            add_message(llm, context_copy, error_msg, "system")
            timeout += 1
        else:
            summary_error = False

    summary = "\n<<<TOOL OUTPUT SUMMARY>>>\n" + summary + f"\n<<</TOOL OUTPUT SUMMARY>>>\n"
    cache_on = cache_on_copy
    print(f"Final Tool Loop Summary is provided below\n\n==========\n{summary}")
    return summary



            


def has_duplicate_ids(text):
    """
    Checks if any ID appears more than once in the given text.
    
    Args:
        text: String containing one or more entries in the specified format
        
    Returns:
        True if any ID appears more than once, False otherwise
    """
    # Pattern to match the entry format and capture the ID
    pattern = r'\[ITER_\d+\]\s*\|\s*ID:(\S+)\s*\|'
    
    # Find all IDs in the text
    ids = re.findall(pattern, text)
    
    # Check if any ID appears more than once
    return len(ids) != len(set(ids))




def add_string_to_kv(string, llm, teams = None):
    load_prefix()
    
    # Add to in-memory prefix
    addendum = [{"role": "user", "content": string}]

    addendum_length,_ = messages_token_counter(llm, addendum)
    global addtkv_token_count 
    addtkv_token_count += addendum_length

    if context_total - (addtkv_token_count + basekv_token_count) < temp_ctx_overhead:
        print("-----------------------TRIMMING KV to avoid overflow-----------------------")
        trim_kv(llm, teams)



    gkv.prefix = merge_without_duplicates(gkv.prefix, addendum)
    
    # Update KV cache with new content
    tokens = llm.tokenize(
    build_chat(addendum).encode("utf-8"), special = True
    )

    llm.eval(tokens)

    gkv.base_state = llm.save_state()



def flatten(list_):
    flat = []
    for item in list_:
        if isinstance(item, (list)):
            flat.extend(flatten(item))  # recurse
        else:
            flat.append(item)
    return flat



def compress_changelog(changelog_text, teams): # should rename to trim
    """
    Extract only the most recent structure update and most recent output for each active team.
    
    Args:
        changelog_text: Full changelog string
        teams: Nested list of team objects
        
    Returns:
        Compressed changelog string
    """
    active_team_ids = set()
    def flatten_teams(team_list):
        for item in team_list:
            if isinstance(item, list):
                flatten_teams(item)
            else:
                active_team_ids.add(item.info.id)
    
    flatten_teams(teams)
    

    # Extract most recent structure update
    structure_pattern = r'<<STRUCTURE UPDATED>>\n(.*?)\n<<STRUCTURE UPDATED>>'
    structure_matches = list(re.finditer(structure_pattern, changelog_text, re.DOTALL))
    most_recent_structure = structure_matches[-1].group(0) if structure_matches else ""

    # Extract most recent debug update
    debugger_structure_pattern = r'<<< DEBUGGER REVIEW START >>>\n(.*?)\n<<< DEBUGGER REVIEW END >>>'
    debugger_structure_matches = list(re.finditer(debugger_structure_pattern, changelog_text, re.DOTALL))
    debugger_most_recent_structure = debugger_structure_matches[-1].group(0) if structure_matches else ""
    
    # Extract all team entries
    # Pattern matches from "---" to "<<< TEAM OUTPUT END >>>"
    team_entry_pattern = r'\[ITER_(\d+)\]\| ID:(team_\d+) \| ([^\|]+) \| (.*?)<<< TEAM OUTPUT START >>>\n(.*?)<<< TEAM OUTPUT END >>>'

    team_matches = re.finditer(team_entry_pattern, changelog_text, re.DOTALL)
    print("CHANGELOG COMPRESIEDFODSFJDSIOFSDNFDSF SDFSD TREXTE TDSFDSFDSERERSETSFDSFDFDSF", list(re.finditer(team_entry_pattern, changelog_text, re.DOTALL)))
    # Store most recent entry for each team ID
    most_recent_entries = {}
    
    for match in team_matches:
        iteration = int(match.group(1))
        team_id = match.group(2)
        filename = match.group(3).strip()
        comments_and_changes = match.group(4).strip()  # Everything before OUTPUT START
        output_content = match.group(5).strip()  # Everything between Changes line and OUTPUT END
        
        # Keep only if this is a more recent iteration for this team
        if team_id not in most_recent_entries or iteration > most_recent_entries[team_id]['iteration']:
            most_recent_entries[team_id] = {
                'iteration': iteration,
                'team_id': team_id,
                'filename': filename,
                'comments': comments_and_changes,
                'output': output_content,
                'full_match': match.group(0)
            }
    
    # Build compressed changelog
    compressed = ""
    
    compressed += "="*60 + "CHANGELOG BEGIN" + "="*60 + "\n\n"

    # Add structure if exists
    if most_recent_structure:
        compressed += most_recent_structure + "\n\n"

    if debugger_most_recent_structure:
        compressed += debugger_most_recent_structure + "\n\n"
    
    # Add most recent entries for active teams only
    # Sort by iteration for chronological order
    sorted_entries = sorted(
        [entry for team_id, entry in most_recent_entries.items() if team_id in active_team_ids],
        key=lambda x: x['iteration']
    )
    
    for entry in sorted_entries:
        compressed += "---\n" + entry['full_match'] + "\n\n"
    
    return compressed.strip()



def directory_to_string(directory_path):
    """Convert all files in a directory to a formatted string recursively."""
    output = []
    
    for root, dirs, files in os.walk(directory_path):
        for filename in files:
            filepath = os.path.join(root, filename)
            
            # Get relative path from the base directory
            relative_path = os.path.relpath(filepath, directory_path)
            folder = os.path.dirname(relative_path) or "."
            
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    contents = f.read()
                
                output.append(f"Folder | {folder} | Filename | {filename} |")
                output.append("<<Begin File Contents>>")
                output.append(contents)
                output.append("<<End File Contents>>")
                output.append("")  # Empty line between files
                
            except (UnicodeDecodeError, PermissionError) as e:
                # Skip binary files or files we can't read
                output.append(f"Folder | {folder} | Filename | {filename} |")
                output.append(f"<<Skipped: {type(e).__name__}>>")
                output.append("")
    
    return "\n".join(output)


def directory_tree(directory_path, prefix="", is_last=True, show_hidden=False):
    """
    Generate a visual tree representation of a directory structure.
    
    Args:
        directory_path: Path to the directory
        prefix: Prefix for the current line (used for recursion)
        is_last: Whether this is the last item in its parent directory
        show_hidden: Whether to show hidden files/folders
    
    Returns:
        String representation of the directory tree
    """
    output = []
    
    # Get the directory name
    dir_name = os.path.basename(directory_path) or directory_path
    
    # Add the current directory
    if prefix == "":
        output.append(f"{dir_name}/")
    else:
        connector = "└── " if is_last else "├── "
        output.append(f"{prefix}{connector}{dir_name}/")
    
    # Get all items in the directory
    try:
        items = sorted(os.listdir(directory_path))
        
        # Filter hidden files if needed
        if not show_hidden:
            items = [item for item in items if not item.startswith('.')]
        
        # Separate directories and files
        dirs = [item for item in items if os.path.isdir(os.path.join(directory_path, item))]
        files = [item for item in items if os.path.isfile(os.path.join(directory_path, item))]
        
        # Combine: directories first, then files
        all_items = dirs + files
        
        for i, item in enumerate(all_items):
            item_path = os.path.join(directory_path, item)
            is_last_item = (i == len(all_items) - 1)
            
            # Update prefix for children
            if prefix == "":
                new_prefix = ""
            else:
                new_prefix = prefix + ("    " if is_last else "│   ")
            
            if os.path.isdir(item_path):
                # Recursively process subdirectories
                subtree = directory_tree(item_path, new_prefix, is_last_item, show_hidden)
                output.append(subtree)
            else:
                # Add file
                connector = "└── " if is_last_item else "├── "
                output.append(f"{new_prefix}{connector}{item}")
    
    except PermissionError:
        output.append(f"{prefix}[Permission Denied]")
    
    return "\n".join(output)


# Simple wrapper function
def print_directory_tree(directory_path, show_hidden=False):
    """Print a directory tree."""
    tree = directory_tree(directory_path, show_hidden=show_hidden)
    return tree


def trim_kv(llm, teams):
    """
    Trim KV cache to keep only content up to and including </GLOBAL_CONTEXT>
    """

    prefix = load_prefix()

    # Rebuild prompt exactly how it was fed to model
    full_prompt = build_chat(prefix)

    if not has_duplicate_ids(full_prompt):
        print("Warning: Duplicate ID's not found, no KV trimming performed")
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
    changelog = compress_changelog(keep_text, teams)
    changelog_msg = [{"role": "user", "content": changelog}]
    add_string_to_kv(changelog_msg, llm, teams)

    return True



def remove_difference_from_kv(llm, token_index, original_prefix):
    llm.n_tokens = token_index
    
    gkv.base_state = llm.save_state()
    gkv.prefix = original_prefix.copy()
    print(f"Restored KV cache to {token_index} tokens")



def make_stop_condition(llm, stop_strings):
    """
    Creates a token-level stop condition function.

    Args:
        llm: The Llama/Qwen model instance
        stop_strings: List of strings that indicate stop (e.g., ["<|im_start|>", "User:"])

    Returns:
        stop_condition(token, output_tokens) -> (bool, output_tokens)
    """
    # Pre-tokenize all stop strings
    stop_seqs = [llm.tokenize(s.encode("utf-8"), special = True) for s in stop_strings]

    def stop_condition(token, output_tokens):
        """
        Checks if the current output ends with any stop sequence.
        Returns a tuple: (should_stop, possibly_trimmed_output_tokens)
        """
        for seq in stop_seqs:
            if len(output_tokens) >= len(seq):
                if output_tokens[-len(seq):] == seq:
                    # Trim stop sequence tokens from output
                    return True, output_tokens[:-len(seq)]
        return False, output_tokens

    return stop_condition



def merge_without_duplicates(prefix_messages, new_messages):
    prefix_contents = [m['content'] for m in prefix_messages]
    
    # Find the longest suffix of prefix that matches a prefix of new_messages
    best_overlap = 0
    for overlap in range(min(len(prefix_messages), len(new_messages)), 0, -1):
        if [m['content'] for m in new_messages[:overlap]] == prefix_contents[-overlap:]:
            best_overlap = overlap
            break
    
    return prefix_messages + new_messages[best_overlap:]




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