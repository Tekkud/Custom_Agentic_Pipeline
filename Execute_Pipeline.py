'''***IMPORTANT*** The material below is NOT part of your system prompt. It is for your reference only!'''

import Utilities as u
import argparse
import team as t
import teams as ts
import os
import pickle
import llama_cpp
import global_kv as gkv
import global_context
from pynput import keyboard
import MCP_Client as mcp
import asyncio
import Main_Helpers as mh


##improvements: modify to take advantage of FIM capabilities of qwen3 models

# ─────────────────────────────────────────────────────────────
# Instantiate Context
# ─────────────────────────────────────────────────────────────
async def instantiate_context(task):
    """Loads LLM, Supplemental Materials and Instantiates KV Cache"""
# 1. Parse Arguments:
    args = await mh.parseargs()

# 2. Start Server/Client:
    print(mh.bcolors.OKBLUE + "Initializing MCP Protocol..." + mh.bcolors.ENDC + mh.bcolors.DULLGREY)
    await mcp.init_client("MCP_Server.py")

# 3. Load Supplemental Info:
    supplemental_info_string = ""
    if args.load:
        print(mh.bcolors.ENDC + mh.bcolors.OKBLUE + "\nLoading Files/Directory..." + mh.bcolors.ENDC + mh.bcolors.DULLGREY)
        supplemental_info_string,_ = mh.load_supplemental(args.load)

# 4. Load Tools Info:
    tools_string = ""
    tools_string = await mh.load_tools()


# 5. Load Model:
    print(mh.bcolors.ENDC + mh.bcolors.OKBLUE + "\nLoading Model..." + mh.bcolors.ENDC + mh.bcolors.DULLGREY)
    llm = u.load_model("/home/harry/Downloads/Qwen3-Coder-30B-A3B-Instruct-IQ4_XS.gguf")
    print(mh.bcolors.ENDC)

# 6. Load Initial Request
    initial_request = f"\n[[INITIAL USER REQUEST: {task}]]\n"

# 7. Initialize Base Context
    print(mh.bcolors.ENDC + mh.bcolors.OKBLUE + "Generating KV Cache..." + mh.bcolors.ENDC + mh.bcolors.DULLGREY)
    context_string = global_context.GLOBAL_CONTEXT + tools_string + supplemental_info_string + initial_request + "</GLOBAL_CONTEXT>"
    context = [{"role": "system", "content": context_string}]
    await mh.init_kv_cache(context, llm)
    print(mh.bcolors.ENDC)

    print(mh.bcolors.HEADER + '-'*15 + "Begin Pipeline" + '-'*15 + mh.bcolors.ENDC)

    return llm


# ─────────────────────────────────────────────────────────────
# Create Teams
# ─────────────────────────────────────────────────────────────
async def create_teams(llm, task):
    """Initializes the teams and management"""
    print(mh.bcolors.ENDC + mh.bcolors.OKBLUE +"\nInitializing Directory Structure..." + mh.bcolors.ENDC)
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
    print(mh.bcolors.ENDC + mh.bcolors.OKBLUE + "Structure Initialized" + mh.bcolors.ENDC)


    
    management_info = ts.Teams_Info(prime_directive = task, master_plan = master_plan)
    management = ts.Teams(teams = teams, teams_info = management_info, directory_planner = create_files)
    return management, teams

# ─────────────────────────────────────────────────────────────
# Pipeline Loop
# ─────────────────────────────────────────────────────────────
async def pipeline_loop(management, list_of_teams, llm):
    """Main Pipeline Loop"""
    while True:
        commands = mh.input_mgr.get_input("Commands (type 'idle' to auto-run): \n   ")
        print("Response Recorded")
        if commands.lower() == "idle":
            mh.input_mgr.idle_mode = True
            print("[Idle mode - press any key to resume]")
            # Don't take other inputs this iteration, skip to processing
            kv_supplement = ""
            management.teams_info.overall_feedback = ""
        else:
            kv_supplement = mh.input_mgr.get_input("OPTIONAL KV SUPPLEMENT: ")
            management.teams_info.overall_feedback = mh.input_mgr.get_input("Feedback/Instruction: \n   ")
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
    """Main Entrypoint of Pipeline"""

# 1. Get Instructions:
    task = input(mh.bcolors.ENDC + mh.bcolors.OKBLUE + "\nInstructions:"+ mh.bcolors.ENDC + mh.bcolors.OKGREEN + "\n    ")
    print(mh.bcolors.ENDC)

# 2. Load All Utilities
    llm = await instantiate_context(task)

# 3. Create Teams and Management
    management, list_of_teams = await create_teams(llm, task)

# 4. Start Main Loop
    await pipeline_loop(management, list_of_teams, llm)


try:
    asyncio.run(main())
finally:
    mh.input_mgr.stop_listener()
   # asyncio.run(mcp.cleanup())

























#
#--------------I am putting this here for reference when pickling is added back in. this was originally in the main function
#
#

    #Pickling has been disabled until it can be reworked with kv caching in mind
    '''
    output_dir = "saved_states" #I need to modify the pickle in the while to dump the kv cache. When loading a cached kv I must remember to deserialize LlamaState.deserialize(data)
    filename = "states.pkl"
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    filepath = os.path.join(output_dir, filename)
    '''

    #Pickling has been disabled until it can be reworked with kv caching in mind
    '''
    y_n = input("Load State? Y/N\n")
    if y_n == "Y":
        print("Loading from save...\n")
        with open(filepath, "rb") as f:
            management = pickle.load(f)
            print("Loaded. Evaluating Teams.\n")
    else:
        task = input("New Session. Provide Initial Instructions:\n")
        initial_request = f"\n[[INITIAL REQUEST: {task}]]\n"
        u.add_string_to_kv(initial_request, llm)
        teams = []
    '''

#This went in the while loop v
'''
            with open(filepath, "wb") as f:
            pickle.dump(management, f)
            '''