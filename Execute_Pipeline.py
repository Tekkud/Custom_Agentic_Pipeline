# ─────────────────────────────────────────────────────────────
# Import Statements
# ─────────────────────────────────────────────────────────────
import Utilities as u
import argparse
import team as t
import teams as ts
import os
import pickle
import llama_cpp
import global_context
from pynput import keyboard
from MCP import MCP_Client as mcp
import asyncio



# ─────────────────────────────────────────────────────────────
# Utility Functions
# ─────────────────────────────────────────────────────────────
async def instantiate_context(task):
    """Load LLM, Supplemental Materials, and Instantiate KV Cache
    
    Args:
        task (str): The user's initial task request
        
    Returns:
        llama_cpp.LLM: The loaded LLM instance
    """
    # 1. Parse Arguments:
    args = await u.parseargs()

    # 2. Start Server/Client:
    print(u.bcolors.OKBLUE + "Initializing MCP Protocol..." + u.bcolors.ENDC + u.bcolors.DULLGREY)
    await mcp.init_client("MCP/MCP_Server.py")

    # 3. Load Supplemental Info:
    supplemental_info_string = ""
    if args.load:
        print(u.bcolors.ENDC + u.bcolors.OKBLUE + "\nLoading Files/Directory..." + u.bcolors.ENDC + u.bcolors.DULLGREY)
        supplemental_info_string, _ = u.load_supplemental(args.load)

    # 4. Load Tools Info:
    tools_string = ""
    tools_string = await u.load_tools()

    # 5. Load Model:
    print(u.bcolors.ENDC + u.bcolors.OKBLUE + "\nLoading Model..." + u.bcolors.ENDC + u.bcolors.DULLGREY)
    llm = u.load_model("/home/harry/Downloads/Qwen3-Coder-30B-A3B-Instruct-IQ4_XS.gguf")
    print(u.bcolors.ENDC)

    # 6. Load Initial Request
    initial_request = f"\n[[INITIAL USER REQUEST: {task}]]\n"

    # 7. Initialize Base Context
    print(u.bcolors.ENDC + u.bcolors.OKBLUE + "Generating KV Cache..." + u.bcolors.ENDC + u.bcolors.DULLGREY)
    context_string = global_context.GLOBAL_CONTEXT + tools_string + supplemental_info_string + initial_request + "</GLOBAL_CONTEXT>"
    context = [{"role": "system", "content": context_string}]
    await u.init_kv_cache(context, llm)
    print(u.bcolors.ENDC)

    print(u.bcolors.HEADER + '-'*15 + "Begin Pipeline" + '-'*15 + u.bcolors.ENDC)

    return llm


# ─────────────────────────────────────────────────────────────
# Team Creation Functions
# ─────────────────────────────────────────────────────────────
async def create_teams(llm, task):
    """Initialize the teams and management system
    
    Args:
        llm: The loaded LLM instance
        task (str): The user's initial task request
        
    Returns:
        tuple: Management object and list of teams
    """
    print(u.bcolors.ENDC + u.bcolors.OKBLUE +"\nInitializing Directory Structure..." + u.bcolors.ENDC)
    teams = []
    add_inst = ""
    add_inst = input("Additional Directory Instructions *Optional*:\n   ")
    request = f"User Request: {task}\n"
    if add_inst != "":
        add_inst = "\nAdditional Instructions: \n" + add_inst + "\n"
    request = request + add_inst
    create_files = ts.Folder_Planner(teams = teams, request= request)
    teams = await create_files.plan(llm = llm)
    master_plan = create_files.master_plan
    print(u.bcolors.ENDC + u.bcolors.OKBLUE + "Structure Initialized" + u.bcolors.ENDC)

    management_info = ts.Teams_Info(prime_directive = task, master_plan = master_plan)
    management = ts.Teams(teams = teams, teams_info = management_info, directory_planner = create_files)
    return management, teams


# ─────────────────────────────────────────────────────────────
# Main Pipeline Loop
# ─────────────────────────────────────────────────────────────
async def pipeline_loop(management, list_of_teams, llm):
    """Main execution loop that manages team interactions and processing
    
    Args:
        management: The management system object
        list_of_teams: List of initialized teams
        llm: The loaded LLM instance
    """
    while True:
        commands = u.input_mgr.get_input("Commands (type 'idle' to auto-run): \n   ")
        print("Response Recorded")
        if commands.lower() == "idle":
            u.input_mgr.idle_mode = True
            print("[Idle mode - press any key to resume]")
            # Don't take other inputs this iteration, skip to processing
            kv_supplement = ""
            management.teams_info.overall_feedback = ""
        else:
            kv_supplement = u.input_mgr.get_input("OPTIONAL KV SUPPLEMENT: ")
            management.teams_info.overall_feedback = u.input_mgr.get_input("Feedback/Instruction: \n   ")
            print("Response Recorded")
        
        if kv_supplement:
            if kv_supplement != "":
                kv_supplement = f"\n<<USER INPUT>> {kv_supplement} <<USER INPUT>>\n"
                u.add_string_to_kv(kv_supplement, llm)

        teams, kv_update, review = await management.evaluate_teams(llm)
        if kv_update:
            print(f"*"*30 + "Management_KV_Update" + "*"*30 + f"\n{kv_update}\n")
            u.add_string_to_kv(kv_update, llm, management.teamslist)
        if review:
            print("Orchestration Document" + "="*60 + "\n" + review + "\n")
        else:
            print("Team manager Error. Retrying")
            continue

        management.teams_info.iteration += 1
        changelog_updates = ""
        if teams:
            for team in teams:
                print(f"\n=================\nID: {team.info.id}\n=================\n\nTeam Guidance\n--------------------\n{team.info.feedback}")
                await team.evaluate_team(llm = llm)
                print(f"\n\nWorker Instructions\n--------------------\n{team.worker_instr}")
                output_stripped_fences = ts.strip_code_fences(team.info.output)
                team.info.output = output_stripped_fences
                changelog_update = ts.create_changelog_entry(team.info.id, team.info.filename, output_stripped_fences, management.teams_info.iteration, team.info.comment)
                print(f"\n\nChangelog\n--------------------\n{changelog_update}")
                changelog_updates += "\n" + changelog_update
            u.add_string_to_kv(changelog_updates, llm, management.teamslist)

        await management.synthesizer.evaluate(llm) #Write team outputs to disk

        if u.trim_kv(llm, management.teamslist):
            continue

        prefix = u.load_prefix()
        if prefix:
            if u.trim_kv(llm, management.teamslist):
                continue


# ╔════════════════════════════════════════════════════════════╗
# ║                          Main                              ║
# ╚════════════════════════════════════════════════════════════╝
async def main():
    """Main entrypoint of the pipeline system
    
    This function orchestrates the entire system startup and execution flow
    """
    # 1. Get Instructions:
    task = input(u.bcolors.ENDC + u.bcolors.OKBLUE + "\nInstructions:"+ u.bcolors.ENDC + u.bcolors.OKGREEN + "\n    ")
    print(u.bcolors.ENDC)

    # 2. Load All Utilities
    llm = await instantiate_context(task)

    # 3. Create Teams and Management
    management, list_of_teams = await create_teams(llm, task)

    # 4. Start Main Loop
    await pipeline_loop(management, list_of_teams, llm)


# ─────────────────────────────────────────────────────────────
# Program Execution
# ─────────────────────────────────────────────────────────────
try:
    asyncio.run(main())
finally:
    u.input_mgr.stop_listener()
   # asyncio.run(mcp.cleanup())