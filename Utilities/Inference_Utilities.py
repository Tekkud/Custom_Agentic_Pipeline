from . import KV_Utilities as kvu
from . import global_kv as gkv #gotta change this
from . import Message_Utilities as msgu
from . import constants as c
import re
import copy
from MCP import MCP_Client as mcp

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
    prefix_messages = kvu.load_prefix()
    gkv.base_state = kvu.load_kv_cache()
    llm.load_state(gkv.base_state)
    
    # Merge and build prompt
    context_ephemeral = msgu.merge_without_duplicates(prefix_messages, context)

    #print("="*20 + "PREFIX FINAL MESSAGE" + "="*20 + f"\n{prefix_messages[-1]['content']}")
          
    # Build only the NEW part of the prompt (not the prefix)
    new_messages = context_ephemeral[len(prefix_messages):]

    #numnew = 0
    #print("="*20 + "NEW MESSAGES MESSAGES" + "="*20)
    #for newmsg in new_messages:
    #    print(f"Message number {numnew}\n")
    #    print(newmsg['content'])
    #    numnew += 1

    tokens_before_gen = llm.n_tokens
    
    # Eval each new message into the KV cache individually
    for msg in new_messages:
        msg_text = msgu.build_chat([msg])
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
    if c.cache_on and not suppress_caching:
        gkv.prefix = context_ephemeral
        gkv.base_state = llm.save_state()
    else:
        llm.n_tokens = tokens_before_gen
        gkv.base_state = llm.save_state()

    response_text = response_text
    return response_text



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
            msgu.add_message(llm, context, abort_msg, "system")
            await infer(llm, context, agent_role, suppress_caching, seed, max_tokens, tools)
        combined_pattern = r"<tool_call>(.*?)</tool_call>"
        matches = list(re.finditer(combined_pattern, inference, re.DOTALL))
        if matches:
            prefix_og = None
            token_index = None
            if c.cache_on:
                prefix_og = copy.deepcopy(kvu.load_prefix())
                token_index = llm.n_tokens
            msgu.add_message(llm, context, inference, "assistant")
            tool_summary = await tool_loop(matches, context, llm, agent_role, init_msg, suppress_caching, max_tokens)
            if token_index and prefix_og:
                kvu.remove_difference_from_kv(llm, token_index, prefix_og)
            tool_summary = tool_summary + f"\n Reminder: <ROLE: {agent_role}> {agent_role} can no longer call tools. Resuming: {init_msg}"
            msgu.add_message(llm, context, tool_summary, "assistant")
            end_msg = f"Important: {agent_role} may not call any more tools. They must now proceed to their assigned task."
            msgu.add_message(llm, context, end_msg, "system")
            inference = generate_output(llm, context, agent_role, suppress_caching = suppress_caching, max_tokens = max_tokens)
    return inference


import json
#cache is kept for duration of tool loop
async def tool_loop(matches, context, llm, agent_name, original_task, suppress_caching, max_tokens, cache_copy=None, context_copy=None, num_calls=0, max_calls=5):
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

        availtools = await mcp.get_tools()
        avail = False
        for tool in availtools:
            if result['name'] == tool['name']:
                avail = True
        
        if avail == False:
            from .Main_Helpers import format_tools
            tools_str = format_tools(availtools)
            rejection_msg = f"The tool named {result['name']} does not exist. You cannot call this tool. Don't try to call this tool name again. The only available tools are as follows: {tools_str}"
            msgu.add_message(llm, context, rejection_msg, "user")
            return await infer(llm, context, agent_role = agent_name, suppress_caching = suppress_caching, max_tokens = max_tokens)

        # Call the tool
        output = await mcp.call_tool(result['name'], result['arguments'])
        #Reference: https://github.com/modelcontextprotocol/modelcontextprotocol/tree/main/schema
        output = output.content[0].text
        print("Output:", output[:100])

        # Format output for model
        output_msg = (
            "\n<<TOOL OUTPUT>>\n" + output +
            "\n<<TOOL OUTPUT>>\n" +
            f"If you are done calling tools please response with [DONE]. Stop calling tools if you have enough information to respond to: {original_task} /think"
        )

        # Update caching variables
        cache_copy = c.cache_on
        c.cache_on = True

        msgu.add_message(llm, context_copy, output_msg, "user")
        inference = generate_output(llm, context_copy, agent_name)
        msgu.add_message(llm, context_copy, inference, "assistant")

        # Check for further tool calls
        combined_pattern = r"(<tool_call>(.*?)</tool_call>)"
        next_matches = list(re.finditer(combined_pattern, inference, re.DOTALL))

        if next_matches and num_calls < max_calls:
            await tool_loop(next_matches, context, llm, agent_name, original_task, cache_copy, context_copy, num_calls=num_calls+1, max_calls=max_calls)
            return

    # Summarization section
    summary_prompt = f'''SUMMARY SECTION -

Now that the tool calling section is over, you must do the following:
Condense the information provided by the tool calls into a well-formatted summary. Keep only important and necessary information.
If you did not receive useful information from the tool call. Just say "Tool did not provide useful information".
Summary:'''
    msgu.add_message(llm, context_copy, summary_prompt, "system")

    summary = generate_output(llm, context_copy, agent_name)

    summary = "\n<<<TOOL OUTPUT SUMMARY>>>\n" + summary + f"\n<<</TOOL OUTPUT SUMMARY>>>\n"
    c.cache_on = cache_copy
    print(f"Final Tool Loop Summary is provided below\n\n==========\n{summary}")
    return summary


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