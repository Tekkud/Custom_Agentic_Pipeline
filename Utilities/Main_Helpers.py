import Utilities as u
import argparse
import os
from pynput import keyboard
from MCP import MCP_Client as mcp

class InputManager:
    def __init__(self):
        self.idle_mode = False
        self.any_key_pressed = False
        self.listener = None
    
    def on_press(self, key):
        if self.idle_mode:
            self.any_key_pressed = True
            print("\n[Key detected - resuming inputs after next iteration]")
    
    def start_listener(self):
        if not self.listener:
            self.listener = keyboard.Listener(on_press=self.on_press)
            self.listener.start()
    
    def stop_listener(self):
        if self.listener:
            self.listener.stop()
    
    def get_input(self, prompt):
        # Check if we should exit idle mode at START of iteration
        if self.idle_mode and self.any_key_pressed:
            self.idle_mode = False
            self.any_key_pressed = False
            print("[Inputs resumed]\n")
            # Fall through to normal input
        
        # If still in idle mode, return empty string
        if self.idle_mode:
            return ""
        
        # Normal input
        return input(prompt)

# Initialize once at start
input_mgr = InputManager()
input_mgr.start_listener()



#used for trimming kv cache
temp_ctx_overhead = 5500
context_total = 32000
u.temp_ctx_overhead = temp_ctx_overhead
u.context_total = context_total


#Format tools as returned by MCP server
def format_tools(tools):
    formatted = []
    for tool in tools:
        lines = [f"Tool: {tool['name']}", f"Description: {tool['description']}", "Parameters:"]
        schema = tool['input_schema']
        required = schema.get('required', [])
        for param, info in schema['properties'].items():
            req = "(required)" if param in required else "(optional)"
            default = f", default={info['default']}" if 'default' in info else ""
            lines.append(f"  - {param} {req}{default}")
        formatted.append("\n".join(lines))
    return "\n\n".join(formatted)



#def generate_base_context(*args):




async def parseargs():
    """Parse system arguments"""
    parser = argparse.ArgumentParser(description='Program')
    parser.add_argument('-load', '--load', type=str, help='Load directory and convert to string')
    try:
        args = parser.parse_args()
    except SystemExit:
        await mcp.cleanup()
        exit()
    return args    


def load_supplemental(args):
    obj = ()
    context_string = ""
    if os.path.isdir(args):
        contents = u.directory_to_string(args)
        tree = u.print_directory_tree(args)
        obj = (contents, tree)
        print(f"Loaded Files.")
    elif open(args, 'r', encoding='utf-8'):
        try:
            with open(args, 'r', encoding='utf-8') as f:
                contents = f.read()
                tree = f"./{args}"
                obj = (contents, tree)
                print(f"Loaded File.")
        except:
            AssertionError()
    else:
        print(f"Error: '{args}' is not a valid directory")
        return "", None
    if len(obj) == 2:
        context_string = "\n<<<BEGIN SUPPLEMENTAL MATERIAL>>>\n" + obj[0] + "\n<<<END SUPPLEMENTAL MATERIAL>>>\n SUPPLEMENTAL MATERIAL DIRECTORY TREE:\n" + obj[1] + "\nSupplemental Material is here for the reference.\n"
    return context_string, obj


async def load_tools():
    #Add available tools to context
    availtools = await mcp.get_tools()
    tools_toprint = format_tools(availtools)
    tools_string = "\n<tools>\n" + tools_toprint + "\n</tools>\n" + "The only tools that you can use are the ones listed here.\n"
    return tools_string

async def init_kv_cache(context, llm):
    #---------
    # Load global prompt into kv cache
    #---------
    u.base_ctx = context

    u.gen_kv_cache_from_string(llm, context)
    
    prefix = u.load_prefix()

    initial_token_count,_  = u.messages_token_counter(llm, context)


    
    u.basekv_token_count = initial_token_count

    print("Generated/Saved KV Cache.")
    print(f"Initial Token Count: {initial_token_count} Tokens")

# To-Do
# incorporate kv dumping/context management. This also includes counting/tracking kv growth. add kv saving to pickling process.
class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    DULLGREY = '\033[90m'
    UNDERLINE = '\033[4m'
#print(llama_cpp.__version__)
#print(llama_cpp.llama_cpp.__file__)