import Utilities as u
import team as t
import copy
import os

import re

from typing import List





'''
*********
*
*************************
*
************************************
*
FOLDER SPLITTER --- THIS NEEDS TO BE UPDATED it is NOT compatible with current team structures*
*
************************************
*
*************************
*
*********
'''


import json


def validate_project_json(json_string):
    """
    Returns:
        (is_valid: bool, error_report: str)
    """
    
    # Check for common non-JSON preambles
    stripped = json_string.strip()
    if not stripped.startswith('['):
        preamble_hint = "\n\nREMINDER: Output ONLY valid JSON. No explanations, no 'Here is the JSON:', no commentary before or after the JSON array."
        return False, f"JSON must start with '[' but starts with: {stripped[:50]}...{preamble_hint}"
    
    try:
        data = json.loads(json_string)
    except json.JSONDecodeError as e:
        return False, (
            f"JSON parsing failed at line {e.lineno}, column {e.colno}: {e.msg}\n"
            f"Context: ...{e.doc[max(0, e.pos-30):e.pos+30]}...\n\n"
            "CRITICAL: Output ONLY pure JSON. No markdown fences, no text before/after, no explanations."
        )
    except Exception as e:
        return False, f"JSON error: {e}\n\nOUTPUT ONLY VALID JSON - no commentary, no preamble."
    
    if not isinstance(data, list):
        return False, (
            f"Root must be a list (array), but got {type(data).__name__}.\n"
            "Expected format: [{...}, {...}]\n\n"
            "OUTPUT ONLY VALID JSON."
        )
    
    seen_team_ids = set()
    
    def error(msg, path):
        return False, (
            f"ERROR at {path}:\n"
            f"  {msg}\n\n"
            "Fix the JSON and output ONLY the corrected JSON - no explanations, no 'here is the fix', just the JSON."
        )
    
    def validate_node(node, path):
        if not isinstance(node, dict):
            return error(
                f"Expected object/dict, got {type(node).__name__}. "
                f"Each node must be a JSON object with 'type', 'children', etc.",
                path
            )
        
        node_type = node.get("type")
        node_id = node.get("id")
        children = node.get("children")
        
        if node_type not in {"folder", "file"}:
            return error(
                f"Invalid 'type': {node_type!r}. Must be exactly 'folder' or 'file'.",
                path
            )
        
        if not isinstance(children, list):
            return error(
                f"'children' must be a list/array, got {type(children).__name__}. "
                f"Even empty children must be: \"children\": []",
                path
            )
        
        # ---------- FOLDER ----------
        if node_type == "folder":
            if node_id is not None:
                return error(
                    f"Folder nodes must have \"id\": null (not {node_id!r}). "
                    f"Only leaf files have string ids.",
                    path
                )
            
            name = node.get("name")
            if not isinstance(name, str) or not name:
                return error(
                    f"Folder must have non-empty 'name' string. Got: {name!r}",
                    path
                )
            
            for i, child in enumerate(children):
                ok, msg = validate_node(child, f"{path}/{name}[{i}]")
                if not ok:
                    return ok, msg
        
        # ---------- FILE ----------
        else:
            filename = node.get("filename")
            if not isinstance(filename, str) or not filename:
                return error(
                    f"File must have non-empty 'filename' string. Got: {filename!r}",
                    path
                )
            
            if "directive" not in node:
                return error(
                    f"File node missing required 'directive' field. "
                    f"Every file must have: \"directive\": \"...\", even if empty string.",
                    path
                )
            
            # Leaf file (no children)
            if len(children) == 0:
                if node_id is None or not isinstance(node_id, str):
                    return error(
                        f"Leaf file must have non-null string 'id'. Got: {node_id!r}. "
                        f"Example: \"id\": \"team_1\"",
                        path
                    )
                
                # Check for duplicates BEFORE adding
                if node_id in seen_team_ids:
                    return error(
                        f"Duplicate team id '{node_id}'. Each leaf file must have a GLOBALLY unique id across ALL folders/files. "
                        f"This id was already used elsewhere in the tree.",
                        path
                    )
                # Only add ONCE, here
                seen_team_ids.add(node_id)
            
            # File with team children
            else:
                if node_id is not None:
                    return error(
                        f"File with children must have \"id\": null, not {node_id!r}. "
                        f"Only leaf files (empty children) have string ids.",
                        path
                    )
                
                for i, child in enumerate(children):
                    if child.get("type") != "file":
                        return error(
                            f"File children must be file nodes (\"type\": \"file\"). "
                            f"Got: {child.get('type')!r}",
                            path
                        )
                    
                    ok, msg = validate_node(child, f"{path}/{filename}[{i}]")
                    if not ok:
                        return ok, msg
        
        return True, ""
        
    for i, root in enumerate(data):
        ok, msg = validate_node(root, f"root[{i}]")
        if not ok:
            return False, msg
    
    return True, "Valid"



def gen_teams_from_json(json_string, prime_directive, teams):
    """
    json_string: JSON string (validated project structure)
    prime_directive: string shared by all teams
    teams: list[list[t.Team]]
    """

    master_plan = json.loads(json_string)

    # Existing teams indexed by id
    team_by_id = {}
    for group in teams:
        for team in group:
            team_by_id[team.info.id] = team

    def find_group(filename):
        for group in teams:
            if group and group[0].info.filename == filename:
                return group
        return None

    def walk(node, path):
        node_type = node["type"]

        if node_type == "folder":
            name = node["name"]
            new_path = f"{path}/{name}" if path else name
            for child in node["children"]:
                walk(child, new_path)

        else:  # file
            filename = node["filename"]
            full_path = f"{path}/{filename}" if path else filename

            # Leaf team node
            if not node["children"]:
                team_id = node["id"]
                directive = node.get("directive", "")

                if team_id in team_by_id:
                    info = team_by_id[team_id].info
                    if (
                        info.prime_directive != prime_directive or
                        info.directive != directive or
                        info.filename != full_path or
                        info.master_plan != master_plan
                    ):
                        info.prime_directive = prime_directive
                        info.directive = directive
                        info.filename = full_path
                        info.master_plan = master_plan
                else:
                    team_info = t.Team_Info(
                        id=team_id,
                        prime_directive=prime_directive,
                        directive=directive,
                        filename=full_path,
                        master_plan=master_plan,
                        feedback=None,
                        context=None,
                        documentation=None,
                        output = "",
                        comment = "NONE"
                    )
                    team = t.Team(team_info=team_info)

                    group = find_group(full_path)
                    if group is None:
                        teams.append([team])
                    else:
                        group.append(team)

            # File with multiple team children
            else:
                for child in node["children"]:
                    walk(child, path)

    for root in master_plan:
        walk(root, "")

    return teams


def strip_code_fences(text):
    text = text.strip()
    # Remove opening fence (with optional language specifier)
    text = re.sub(r'^```[a-zA-Z]*\n?', '', text)
    # Remove closing fence
    text = re.sub(r'\n?```$', '', text)
    return text.strip()


def format_for_user(json_string):
    """
    Converts project JSON into a condensed, LLM-readable format.
    Handles multiple teams per file.
    """
    try:
        data = json.loads(json_string)
    except:
        return "Invalid JSON"
    
    lines = []
    
    def walk(node, indent=0):
        # Add type check to handle non-dict nodes
        if not isinstance(node, dict):
            return
            
        prefix = "  " * indent
        node_type = node.get("type")
        
        if node_type == "folder":
            name = node.get("name")
            lines.append(f"{prefix}📁 {name}/")
            for child in node.get("children", []):
                walk(child, indent + 1)
                
        elif node_type == "file":
            filename = node.get("filename")
            directive = node.get("directive", "")
            children = node.get("children", [])
            
            # Single team (leaf file)
            if len(children) == 0:
                team_id = node.get("id")
                lines.append(f"{prefix}📄 {filename} [{team_id}] - {directive}")
            # Multiple teams
            else:
                team_ids = [c.get("id") for c in children if isinstance(c, dict)]
                team_directives = [c.get("directive", "") for c in children if isinstance(c, dict)]
                
                # Truncate each directive -- hackily removed. will fix
                truncated_directives = []
                for d in team_directives:
                    truncated_directives.append(d)
                        
                teams_str = ", ".join(team_ids)
                directives_str = ", ".join(truncated_directives)
                lines.append(f"{prefix}📄 {filename} [{teams_str}] - [{directives_str}]")
    
    # Handle different data structures
    if isinstance(data, list):
        for root in data:
            walk(root)
    elif isinstance(data, dict):
        walk(data)
    else:
        return "Unexpected JSON structure"
    
    return "\n".join(lines)








'''
Folder-Level-Management Classes
 * Classes related to folder-level actions, such as evaluating ALL teams etc
'''






'''
Folder-Level-Management Classes
 * Classes related to folder-level actions, such as evaluating ALL teams etc
'''

def extract_and_validate_teams(text: str, id_list: List[str], teams):
    """
    Extract team IDs from a string of the form:
    <<<TEAMS>>>[teamid1,teamid2,...]<<<TEAMS>>>
    Validates that every extracted team ID exists in id_list.
    The extracted list does NOT need to contain all IDs in id_list.
    Preserves the order of team IDs as they appear in the input string.
    Raises:
        ValueError: if the TEAMS block is missing or if any team ID is invalid.
    """
    error = ""
    pattern = r"<<<TEAMS>>>\s*\[(.*?)\]\s*<<<TEAMS>>>"
    match = re.search(pattern, text, re.DOTALL)
    if not match:
        error = "Error in the machine parser. Could not find a list of the form <<<TEAMS>>>[teamid1,teamid2,teamid3]<<<TEAMS>>>. Remember to replace the team IDs with the ones under consideration."
        return [], error
    
    # Preserve order by using a list instead of a set
    requested_ids = [
        t.strip().upper()
        for t in match.group(1).split(",")
        if t.strip()
    ]
    
    # Remove duplicates while preserving order
    seen = set()
    requested_ids_unique = []
    for tid in requested_ids:
        if tid not in seen:
            seen.add(tid)
            requested_ids_unique.append(tid)
    
    # Validate against valid IDs
    valid_ids = {i.strip().upper() for i in id_list}
    invalid = set(requested_ids_unique) - valid_ids
    if invalid:
        error = f"Invalid team IDs found: {invalid}. Please provide a list with only valid team IDs"
        return [], error
    
    # Build team lookup by ID for efficient matching
    team_lookup = {}
    for teamlist in teams:
        for t in teamlist:
            tid = t.info.id.strip().upper()
            team_lookup[tid] = t
    
    # Build result in the order specified in requested_ids_unique
    result = []
    for tid in requested_ids_unique:
        if tid in team_lookup:
            result.append(team_lookup[tid])
    
    return result, error








def flatten(list_):
    flat = []
    for item in list_:
        if isinstance(item, (list)):
            flat.extend(flatten(item))  # recurse
        else:
            flat.append(item)
    return flat
       

'''
    TEAMS - contains the teams, evaluation will evaluate all teams in the folder
'''
class Teams_Info:
    def __init__(self, prime_directive, master_plan, overall_feedback = None):
        self.prime_directive = prime_directive
        self.master_plan = master_plan
        self.overall_feedback = overall_feedback
        self.iteration = 0


class Teams:
    def __init__(self, teams, teams_info, directory_planner = None, structure_guider = None, teams_reviewer = None, debugger = None, synthesizer = None, teams_guider = None):
        self.teamslist = teams
        self.teams_info = teams_info

        self.directory_planner = directory_planner if directory_planner is not None else Folder_Planner(teams, request = self.teams_info.prime_directive)
        self.structure_guider = structure_guider if structure_guider is not None else Structure_Guider(self)
        self.teams_guider = teams_guider if teams_guider is not None else Team_Guider(self)
        self.debugger = debugger if debugger is not None else Debugger(self)
        self.synthesizer = synthesizer if synthesizer is not None else Synthesizer(self)
        self.teams_reviewer = teams_reviewer if teams_reviewer is not None else Review_Manager(self)

        self.outputs = None
        self.synthesizer = Synthesizer(self) 
    async def evaluate_teams(self, llm):
        kv_update = ""
        if self.teams_info.iteration != 0:
            kv_update = await self.debugger.evaluate(llm)

        u.cache_on = True    
        prefix_og = copy.deepcopy(u.load_prefix())
        token_index = llm.n_tokens

        restructure_inst = await self.structure_guider.evaluate(llm, self.teams_info.overall_feedback, self.teams_info.iteration)
    
        if restructure_inst != None:
            self.teams_info.master_plan, kv_addition = await self.directory_planner.rehash(restructure_inst, llm)
            kv_update += "\n" + kv_addition


        review, teams = await self.teams_reviewer.evaluate(llm)

        if review:
            await self.teams_guider.evaluate(llm, review, teams)

        u.remove_difference_from_kv(llm, token_index, prefix_og)
        return teams, kv_update, review
        
        





class Structure_Guider:
    def __init__(self, teams):
        self.teams = teams
        self.sysprompt_assessor = f'''YOUR ROLE: SYSTEM_ASSESSOR. Follow instructions of the SYSTEM ASSESSOR'''
        self.name = "SYSTEM_ASSESSOR"
    async def evaluate(self, llm, feedback, iter):
        messages = []
        u.add_message(llm, messages, self.sysprompt_assessor, "sysprompt")
        if feedback == None or feedback == "":
            feedback = "No Feedback Provided"
        pre_string = f"USER FEEDBACK: {feedback}\n" + f"ITERATION: {iter}\n"
        teamlist = flatten(self.teams.teamslist)
        part_1 = pre_string + "Output:"
        u.add_message(llm, messages, part_1, "user")
        self.review_summary = await u.infer(llm, messages, agent_role = self.name)

class Review_Manager:
    def __init__(self, teams):
        self.teams = teams
        self.sysprompt_review_manager = f'''YOUR ROLE: TEAM_REVIEW_MANAGER. Follow the instructions of the team review manager.'''
        self.name = "TEAM_REVIEW_MANAGER"
    async def evaluate(self, llm):
        messages = []
        failures = 0
        id_list = [team.info.id for teamlist in self.teams.teamslist for team in teamlist]
        feedback = self.teams.teams_info.overall_feedback
        u.add_message(llm, messages, self.sysprompt_review_manager, "system")
        if feedback == None or feedback == "":
            feedback = "No Feedback Provided"
        # Ask the reviewer to pick a team ready to produce output
        ids_str = ", ".join(id_list)
        prompt1 = (
                
                f"START OF ITERATION {self.teams.teams_info.iteration}"
            f"Project-Level User Feedback: {feedback}"
            "Consider User Feedback in your Plan/Obligations/Team Instructions"
            f"Available TEAM IDs: {ids_str}.\n"
            "You must now perform your role. Good luck."
        )
        while True:
            u.add_message(llm, messages, prompt1, "user")
            review = await u.infer(llm, messages, agent_role = self.name)
            teams, error = extract_and_validate_teams(review, id_list, self.teams.teamslist)
            if error == "":
                return review, teams
            else:
                u.add_message(llm, messages, error, "system")
                failures +=1
                if failures > 5:
                    return False, None
                
class Team_Guider:
    def __init__(self, teams):
        self.teams = teams
        self.sysprompt_guider = '''YOUR ROLE: REVIEW_MANAGER_ASSISTANT. Follow instructions of the REVIEW_MANAGER_ASSISTANT'''
        self.name = "REVIEW_MANAGER_ASSISTANT"
    async def evaluate(self, llm, reasoning, teams):
        messages = []
        u.add_message(llm, messages, self.sysprompt_guider, "system")
        reasoning = "\nHello review manager assistant. Here is the review managers reasoning report\n" + reasoning + "\n[END]\n"
        messages = []
        changelog_updates = []
        for team in teams:
            u.add_message(llm, messages, reasoning, "system")
            assistant_prompt = f"Please provide guidance for TEAM ID {team.info.id}:"
            u.add_message(llm, messages, assistant_prompt, "user")
            obligations = await u.infer(llm, messages, agent_role = self.name)
            team.info.feedback = obligations

'''
Folder Splitter - Responsible for creating the folder-level file structure
'''
class Folder_Planner:
    def __init__(self, teams, request):
        self.request = request
        self.teamslist = teams #list of teams
        self.name = "DIRECTORY_STRUCTURE_CREATOR"
        self.master_plan = None
        self.directives = []
        # sysprompt_arg
        # if prime_if_true == True:
        #     sysprompt_arg = "The outputs of the tasks must be text documents or programs which can be written to files"
        # else:
        #     sysprompt_arg = "You must be able to synthesize the final output of the tasks into a single text document or program which will be written to a file."
        self.sysprompt = f'''YOUR ROLE: DIRECTORY_STRUCTURE_CREATOR.
{self.request}\nPlan:'''
    
    async def plan(self, llm):
        
        u.cache_on = True    
        prefix_og = copy.deepcopy(u.load_prefix())
        token_index = llm.n_tokens

        #Plan here
        messages = []
        # Gather tasks
        u.add_message(llm, messages, self.sysprompt, "system")
        prompt1 = "Step 1: Reasoning. Please Provide Reasoning Now:"
        u.add_message(llm, messages, prompt1, "user")
        while True:
            reasoning = await u.infer(llm, messages, agent_role = self.name)
            #print(f"REASONING {reasoning}")
            u.add_message(llm, messages, reasoning, "assistant")
            self.name = "JSON_PRODUCER"
            prompt2 = "<NEW ROLE. YOU ARE NOW THE JSON PRODUCER> Output JSON NOW:"
            u.add_message(llm, messages, prompt2, "system")
            planner_output1 = await u.infer(llm, messages, agent_role = self.name)
            planner_output1 = strip_code_fences(planner_output1)
            planner_output1 = u.strip_role_tags(planner_output1)
            is_valid, errors = validate_project_json(planner_output1)
            if not is_valid:
                u.add_message(llm, messages, errors, "user")
                self.name = "DIRECTORY_STRUCTURE_CREATOR"
                prompte = "<NEW ROLE. YOU ARE NOW THE DIRECTORY_STRUCTURE_CREATOR> **imperative** Reason about the error before the role switch. you must not repeat yourself.\n"
                u.add_message(llm, messages, prompte, "system")
                continue
            planner_output1 = strip_code_fences(planner_output1)
            planner_output1_refined = format_for_user(planner_output1)
            print("File Structure Proposal\n---------------------------\n" + planner_output1_refined + "\n")
            fb = input("y/n\n")
            if fb == 'y':
                break
            else:
                feedback = input("Provide Feedback:")
                self.name = "DIRECTORY_STRUCTURE_CREATOR"
                new_role = "<NEW ROLE. YOU ARE NOW THE DIRECTORY_STRUCTURE_CREATOR>\n"
                u.add_message(llm, messages, new_role, "system")
                feedback = f'''PLAN REJECTED. USER FEEDBACK: {feedback}.\n'''
                u.add_message(llm, messages, feedback, "user")
        
        u.remove_difference_from_kv(llm, token_index, prefix_og)
        
        planner_output1 = strip_code_fences(planner_output1)
        self.master_plan = planner_output1
        self.teams = gen_teams_from_json(json_string = planner_output1, prime_directive = self.master_plan, teams = self.teamslist)
        curr_json_structure = planner_output1
        planner_output1_refined = format_for_user(planner_output1)
        kv_update = "<<STRUCTURE UPDATED>>\n" + planner_output1_refined + "\n<<STRUCTURE UPDATED>>\n"
        changelog_start = kv_update + "\n" + "="*60 + "CHANGELOG BEGIN" + "="*60 + "\n"
        print("Adding initial structure to kv cache")
        u.add_string_to_kv(changelog_start, llm, self.teams)
        return self.teams

    async def rehash(self, instructions, llm):


        u.cache_on = True    
        prefix_og = copy.deepcopy(u.load_prefix())
        token_index = llm.n_tokens

        #Plan here
        is_valid = False
        messages = []
        planner_output1 = ""
        prompt = self.sysprompt + f"RESTRUCTURE REQUESTED. INPUT FROM GENERAL MANAGER: {instructions}."
        # Gather tasks
        u.add_message(llm, messages, prompt, "user")
        while is_valid == False:
            prompt1 = "Step 1: Reasoning. Please Provide Reasoning Now:"
            u.add_message(llm, messages, prompt1, "user")
            reasoning = await u.infer(llm, messages, agent_role = self.name)
            u.add_message(llm, messages, reasoning, "assistant")
            prompt2 = "Step 2: JSON Output. Output JSON NOW:"
            u.add_message(llm, messages, prompt2, "user")
            planner_output1 = "abcd{}{}" #invalid default
            planner_output1 = await u.infer(llm, messages, agent_role = self.name)
            planner_output1 = strip_code_fences(planner_output1)
            is_valid, errors = validate_project_json(planner_output1)
            errors = errors + "\nReturning to step 1. Reasoning. Do not move on to JSON structure creation. Do not output any JSON.\n"
            if not is_valid:
                u.add_message(llm, messages, errors, "user")
                continue

        u.remove_difference_from_kv(llm, token_index, prefix_og)

        self.teams = gen_teams_from_json(json_string = planner_output1, prime_directive = self.master_plan, teams = self.teamslist)
        self.master_plan = planner_output1
        planner_output1_refined = format_for_user(planner_output1)
        print("NEW STRUCTURE:\n" + planner_output1_refined)
        kv_update = "TEAM STRUCTURE CHANGE/UPDATE:\n<<STRUCTURE UPDATED>>\n" + planner_output1_refined + "\n<<STRUCTURE UPDATED>>\n"
        return self.teams, kv_update
        # print(f"\n\n{planner_output1}\n\n")




class Synthesizer:
    def __init__(self, teams):
        self.teams = teams
        self.name = "SYNTHESIZER"
        self.sysprompt = '''YOUR ROLE: SYNTHESIZER. Follow the instructions of the synthesizer.
        you are NOT team_feedback_manager. you are NOT team_review_manager. you are NOT team_manager. you are NOT DIRECTORY_STRUCTURE_CREATOR. you are NOT worker. you are NOT commenter'''
    async def evaluate(self, llm):
        for team_ in self.teams.teamslist:  # Each team_ is a list of teams working on same file
            messages = []
            u.add_message(llm, messages, self.sysprompt, "system")
            
            team_outputs = []  # Use list instead of string concatenation
            comments = []
            filename = None
            
            # Collect outputs from all teams in this group
            for team in team_:
                if team.info.output:
                    team_outputs.append(u.strip_role_tags(team.info.output))
                if team.info.comment and team.info.comment != "NONE":
                    comments.append(u.strip_role_tags(team.info.comment))
                if not filename:
                    filename = team.info.filename
            
            if not team_outputs:
                continue
            
            # Autogen if single team (no synthesis needed)
            autogen = len(team_) == 1
            
            if not autogen:
                # Join with clear separators for LLM to parse
                combined_outputs = "\n\n---\n\n".join(team_outputs)
                
                prompt = f"""[Begin Outputs]
    {combined_outputs}
    [End Outputs]
    TASK: Synthesize the above team outputs into the final complete file contents for {filename}.
    Remember: Output ONLY the raw file contents with no explanations, no markdown fences, no preamble:"""
                u.add_message(llm, messages, prompt, "user")
                output = await u.infer(llm, messages, agent_role = self.name)
                output = strip_code_fences(output)
            else:
                output = team_outputs[0]
            
            # Write to file
            output_dir = f"./outputs/{filename}"
            os.makedirs(os.path.dirname(output_dir) or ".", exist_ok=True)
            with open(output_dir, 'w') as f:
                f.write(output)
                    

'''
Team-level feedback manager -- makes decisions based on feedback about what to do to teams
-passes relevant messages to teams
-warns of catastrophe (entire structure must be re-evaluated)
-collects the team outputs
'''
class Teams_Feedback_Processor:
    def __init__(self, teams_info, teams):
        self.name = "TEAMS_FEEDBACK_PROCESSOR"
        self.teams = teams
        self.teams_info = teams_info
        self.notes = None
        self.team_feedback = ""
        self.sysprompt = self.sysprompt = f'''YOUR ROLE: TEAMS_FEEDBACK_PROCESSOR. Follow the instructions of the teams feedback processor.
        you are NOT team_review_manager. you are NOT team_manager. you are NOT DIRECTORY_STRUCTURE_CREATOR. you are NOT worker. you are NOT commenter'''

  
    async def evaluate(self, overall_feedback, review_summary, llm):
        #check if team needs splitting. if so - split teams, provide their feedback, evaluate them
        #return: team(s) and (possibly synthesized) output
        messages = []
        u.add_message(llm, messages, self.sysprompt, "system")
        info = f"INFORMATION PROVIDED:\nOverall Feedback: {overall_feedback}\n Team Review Summary: {review_summary}"
        teams_feedback_processor_prompt1 = info + "\nShould the teams be restructured? YES or NO"
        u.add_message(llm, messages, self.sysprompt, "system")
        u.add_message(llm, messages, teams_feedback_processor_prompt1, "user")
        teams_feedback_processor_output1 = await u.infer(llm, messages, agent_role = self.name)
        if "YES" in teams_feedback_processor_output1:
            teams_feedback_processor_prompt2 = "Provide the restructuring instructions now."
            u.add_message(llm, messages, teams_feedback_processor_prompt2, "user")
            restructuring_instructions = await u.infer(llm, messages, agent_role = self.name)
            return restructuring_instructions
        else: return None
            

class Debugger:
    def __init__(self, teams):
        self.teams = teams
        self.name = "DEBUGGER"
        # sysprompt_arg
        # if prime_if_true == True:
        #     sysprompt_arg = "The outputs of the tasks must be text documents or programs which can be written to files"
        # else:
        #     sysprompt_arg = "You must be able to synthesize the final output of the tasks into a single text document or program which will be written to a file."
        self.sysprompt = f'''YOUR ROLE: DEBUGGER. Follow the instructions of the debugger.
        you are NOT team_feedback_manager. you are NOT team_review_manager. you are NOT team manager. you are NOT worker. you are NOT commenter
        '''
    async def evaluate(self, llm):
        current_feedback = self.teams.teams_info.overall_feedback
        if current_feedback == None or current_feedback == "":
            feedback = "None"
        feedback = current_feedback
        messages = []
        self.sysprompt = self.sysprompt + f"\nCurrent User Feedback: {feedback}\n"
        # Add the cached/global system prompt
        u.add_message(llm, messages, self.sysprompt, "system")

        # --- Step 1: Reasoning ---
        reasoning_prompt = (
            "Provide your internal reasoning for this iteration. "
            "Do NOT output the report yet. End with 'Ready to provide report.' and then stop talking"
        )
        u.add_message(llm, messages, reasoning_prompt, "user")

        reasoning_output = await u.infer(llm, messages, agent_role = self.name)

        print(f"DEBUG: \n{reasoning_output}")

        # Optional: log or print reasoning
        print("DEBUGGER REASONING:\n", reasoning_output, "\n")

        # --- Step 2: Report ---
        report_prompt = "Provide the debugger report for this iteration. Include resolved and unresolved errors."
        # Reset messages for report inference, keeping system context
        messages_report = []
        u.add_message(llm, messages_report, self.sysprompt, "system")
        u.add_message(llm, messages_report, report_prompt, "user")

        report_output = await u.infer(llm, messages_report, agent_role = self.name)

        # Add report to changelog
        debug_changelog_report = create_changelog_entry(
            "DEBUGGER",
            "REVIEW",
            report_output,
            self.teams.teams_info.iteration,
            "Output:",
            debug=True
        )

        return debug_changelog_report


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


def create_changelog_entry(id, filename, team_output, iteration, comment, debug = False):
    """
    Create a changelog entry with proper formatting.
    
    Args:
        filename: e.g., "main.c"
        file_contents: Raw file contents
        iteration: Iteration number
        reason: Brief reason (e.g., "Fixed includes") or None if no changes
        
    Returns:
        str: Formatted changelog entry
    """
    team_output = u.strip_role_tags(team_output)
    comment = u.strip_role_tags(comment)
    if debug:
        return f"""---
[ITER_{iteration}]| DEBUGGER REVIEW:
<<< DEBUGGER REVIEW START >>>
{team_output}
<<< DEBUGGER REVIEW END >>>
"""
    else:
        return f"""---
[ITER_{iteration}]| ID:{id} | {filename} | {comment} 
<<< TEAM OUTPUT START >>>
{team_output}
<<< TEAM OUTPUT END >>>
"""
        

        



'''        
    def recursive_loop(self, teams, llm, review_summary):
        team_s = []
        outputs = []
            #recursively iterate through teams
        if isinstance(teams, list):
            for team in teams:
                directive, output, team_out = self.recursive_loop(team, llm, review_summary)
                team_s.append(team_out)
                outputs.append(output)
        else:
            team_s, output = self.teams_processor.process_team(teams, llm, review_summary) ## when you get to the teams themselves, process them
            directive = teams.info.directive
            return directive, output, team_s

        messages = []
        synth_sysprompt = f'<ROLE> You are a Synthesizing Agent:
        <TASK> You will be provided some outputs. If there are more than one, you will synthesize them together. The goal is to meet the directive: {directive}
        Aside from integrating what has been provided by the teams, you should not contribute any content of your own to the output. Do not include duplicate instances of functionality. Do not give any commentary along with your answer'
        u.add_message(llm, messages, synth_sysprompt, "system")
        final_synth_prompt = "OUTPUTS:"
        for idx, output in enumerate(outputs):
            final_synth_prompt = final_synth_prompt + f"\n<OUTPUT {idx + 1}> {output[idx]}"
        u.add_message(llm, messages, final_synth_prompt, "user")
        output = u.infer(llm, messages, agent_role = self.name)
        return directive, output, team_s
'''


