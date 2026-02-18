from . import constants as c

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

def messages_trim(llm, messages):
    if messages == []:
        return
    while messages_token_counter(llm, messages)[0] > (llm.context_params.n_ctx - c.basekv_token_count - c.addtkv_token_count): #prevent OOM
        if len(messages) <= 1:
            messages.clear()
            return
        else:
            del messages[1]


# '''
#     add messages from string
# '''
def add_message(llm, messages, string, role):
    message = {"role": role, "content": string}
    messages.append(message)


#We eliminate chat complete because of formatting issues
def build_chat(messages):
    output = ""
    for msg in messages:
        role = msg["role"]
        content = msg["content"]
        output += f"<|im_start|>{role}\n{content}<|im_end|>\n"
    return output



def merge_without_duplicates(prefix_messages, new_messages):
    prefix_contents = [m['content'] for m in prefix_messages]
    
    # Find the longest suffix of prefix that matches a prefix of new_messages
    best_overlap = 0
    for overlap in range(min(len(prefix_messages), len(new_messages)), 0, -1):
        if [m['content'] for m in new_messages[:overlap]] == prefix_contents[-overlap:]:
            best_overlap = overlap
            break
    
    return prefix_messages + new_messages[best_overlap:]