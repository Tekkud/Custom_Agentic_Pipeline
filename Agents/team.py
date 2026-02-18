import Utilities as u
import numpy as np
from typing import Optional, List, Tuple
import json
import re
import random
import os
import textwrap
import copy

class Team_Info:
    def __init__(self, prime_directive, master_plan = None, directive = None, feedback = None, context = None, documentation = None, filename = None, id = None, output = None, comment = None):
        self.prime_directive = prime_directive
#removed sub directive
        self.directive = directive
        self.filename = filename
        self.master_plan = master_plan
        self.id = id
        self.feedback = feedback
        self.context = context
        self.documentation = documentation
        self.output = output if output is not None else ""
        self.comment = comment if comment is not None else "NONE" 

class Team:
    def __init__(self, team_info, manager = None, worker = None, documenter = None):
        self.info = team_info
        self.worker_instr = ""
        self.commenter_inst = ""
        if manager == None:
            self.manager = Manager(self)
        else:
            manager = manager
        if worker == None:
            self.worker = Worker(self)
        else:
            worker = worker
        if documenter == None:
            self.documenter = Documenter(self)
        else:
            documenter = documenter
    async def evaluate_team(self, llm):

        u.cache_on = True    
        prefix_og = copy.deepcopy(u.load_prefix())
        token_index = llm.n_tokens

        self.worker_instr = await self.manager.evaluate(llm)
        self.info.output = await self.worker.evaluate(llm, self.worker_instr)
        self.info.comment = await self.documenter.evaluate(llm)


        u.remove_difference_from_kv(llm, token_index, prefix_og)

class Manager(Team):
    def __init__(self, team, llm = None):
        self.team = team
        self.sysprompt = f'''YOUR ROLE: TEAM_MANAGER. Follow the instructions of the team manager.'''
        self.name = "TEAM_MANAGER"

    async def evaluate(self, llm):
        sysprompt = f'''YOUR ROLE: TEAM_MANAGER. Follow the instructions of the team manager.'''
        # Generate Context
        messages = []
        u.add_message(llm, messages, sysprompt, "system")
        # file_locations_str = find_file_locations(self.team.info.id, json) - removed
        team_manager_agent_prompt1 = f'''<TEAM ID: {self.team.info.id}>
        <TEAM DIRECTIVE (long term)> {self.team.info.directive}
        
        <Current Obligations> {self.team.info.feedback}
        '''
        u.add_message(llm, messages, team_manager_agent_prompt1, "system")


        # print(f"debug {file_locations_str}")
            
        team_manager_agent_prompt2 = "Provide worker instructions:"
        u.add_message(llm, messages, team_manager_agent_prompt2, "user")
        response1 = await u.infer(llm, messages, agent_role = self.name)
        return response1

class Worker(Team):
    def __init__(self, team, llm = None, instructions = None):
        self.team = team
        self.instructions = instructions
        self.sysprompt = f'''YOUR ROLE: WORKER. Follow the instructions of the worker.'''
        self.name = "WORKER"
    async def evaluate(self, llm, worker_instructions):
        messages = []
        u.add_message(llm, messages, worker_instructions, "assistant")
        name = "WORKER"
        worker_sysprompt = self.sysprompt
        worker_sysprompt = worker_sysprompt + f"<TEAM ID: {self.team.info.id}>"
        worker_sysprompt = worker_sysprompt + f'''
    ''' + "\nDELIVERABLE:"
            
        u.add_message(llm, messages, worker_sysprompt, "system")
        output = await u.infer(llm, messages, agent_role = self.name)
        return output

class Documenter(Team):
    def __init__(self, team, llm = None, instructions = None):
        self.team = team
        self.instructions = instructions
        self.sysprompt = f'''YOUR ROLE: COMMENTER. Follow the instructions of the commenter.'''
        self.name = "COMMENTER"
    async def evaluate(self, llm):
        messages = []
        u.add_message(llm, messages, self.team.commenter_inst, "assistant")
        commenter_sysprompt = self.sysprompt + f"\n <TEAM ID: {self.team.info.id}> Please Provide a Unique Status Report. The requests therein must not be present in the changelog. (max 3 lines, no summaries):"
        u.add_message(llm, messages, self.sysprompt, "user")
        comment = await u.infer(llm, messages, agent_role = self.name)
        return comment  





'''
import os
import json
from typing import Optional, List, Tuple

def find_file_locations(team_id: str, structure_json: str) -> str:
    """
    Find all file locations relative to a given team's file.
    
    Args:
        team_id: The team ID to find relative paths from (e.g., "team_0001")
        structure_json: JSON string representing the file tree
    
    Returns:
        String with all other files and their relative paths
    """
    
    # Parse JSON string
    try:
        structure = json.loads(structure_json)
    except json.JSONDecodeError as e:
        return f"Error: Invalid JSON - {e}"
    
    def find_all_files(node, current_path=""):
        """Recursively find all files with their paths and team IDs."""
        files = []
        
        if isinstance(node, list):
            for item in node:
                files.extend(find_all_files(item, current_path))
        elif isinstance(node, dict):
            node_type = node.get("type")
            
            if node_type == "folder":
                folder_name = node.get("name", "")
                new_path = os.path.join(current_path, folder_name) if current_path else folder_name
                
                for child in node.get("children", []):
                    files.extend(find_all_files(child, new_path))
            
            elif node_type == "file":
                filename = node.get("filename", "")
                file_id = node.get("id")
                filepath = os.path.join(current_path, filename)
                
                files.append({
                    "id": file_id,
                    "filename": filename,
                    "path": filepath,
                    "directive": node.get("directive", "")
                })
        
        return files
    
    # Find all files in the structure
    all_files = find_all_files(structure)
    
    # Find the target file(s) for the given team_id
    target_files = [f for f in all_files if f["id"] == team_id]
    
    if not target_files:
        return f"Error: Team ID '{team_id}' not found in structure"
    
    # Use the first occurrence as the reference point
    target_file = target_files[0]
    target_path = target_file["path"]
    target_dir = os.path.dirname(target_path)
    
    # Deduplicate by path
    seen_paths = set()
    output_lines = []
    
    for file in all_files:
        # Skip if it's the same file as our target
        if file["path"] == target_path:
            continue
        if file["path"] in seen_paths:
            continue
        
        seen_paths.add(file["path"])
        rel_path = os.path.relpath(file["path"], target_dir)
        output_lines.append(f"{file['filename']} - {rel_path}")
    
    return "\n".join(output_lines)
'''






 




