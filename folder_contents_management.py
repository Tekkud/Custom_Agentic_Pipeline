import Utilities as u
import file_contents_management as fi

'''
Folder-Level-Management Classes
 * Classes related to folder-level actions, such as evaluating ALL teams etc
'''


'''
    TEAMS - contains the teams, evaluation will evaluate all teams in the folder
'''
class Teams_Info:
    def __init__(self, prime_directive, team_directive):
        self.prime_directive = prime_directive
        self.master_plan
        self.documentation
        self.team_feedback

class Teams:
    def __init__(self, teams, teams_info, feedback = None, llm = None):
        self.teams = teams
        self.teams_processor = Teams_Feedback_Processor(feedback = self.feedback, teams = teams, llm = llm)
        self.teams_info = teams_info

    def evaluate_teams(self):
        for team in self.teams:
            self.recursive_loop(self, team)
            
    def recursive_loop(self, teams):
        outputs = []
            #recursively iterate through teams
        for team in teams:
            if isinstance(team, list): ##iterate through teams recursively
                output = self.recursive_loop(self, team)
            else:
                team_s, output, breakdown = self.feedback_processor(self) ## when you get to the teams themselves, process them
                if breakdown == True:
                    print("A breakdown occurred. It appears the LLM cant handle this task. You need to adjust the directory structure")
                    pause = input("...press enter to continue anyways")
                team = team_s
                 ##-------------------------------------------------------------------------------------------------------------------------------------------
            outputs.append(output)

        if len(teams) == 1:
            return output
        else:
            messages = []
            synth_sysprompt = f'''<ROLE> You are a Synthesizing Agent:
            <TASK> You will be provided two outputs. You will synthesize them into the final deliverable. The final deliverable is: {teams[-1].subdirective}'''
            u.add_message(self.llm, messages, synth_sysprompt, "system")
            final_synth_prompt = f'''<OUTPUT1> {output[0]} <OUTPUT2> {output[1]}'''
            u.add_message(self.llm, messages, final_synth_prompt, "user")
            output = u.infer(self.llm, messages)
            return output




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

'''
Folder Splitter - Responsible for creating the folder-level file structure
'''
class Folder_Planner:
    def __init__(self, directive, teams = None, llm = None):
        self.request = directive
        self.teams = teams
        self.llm = llm
        self.master_plan = None
        self.directives = []
        # sysprompt_arg
        # if prime_if_true == True:
        #     sysprompt_arg = "The outputs of the tasks must be text documents or programs which can be written to files"
        # else:
        #     sysprompt_arg = "You must be able to synthesize the final output of the tasks into a single text document or program which will be written to a file."
        sysprompt_arg = "The outputs of the tasks must be individual files"


        self.sysprompt = f'''<ROLE> You are the master planner for the following request: {self.request}.
        <TASK> Your job is to break the request into individual files.
        {sysprompt_arg}
        The output of tasks must be concrete text-based deliverables which create a solution for the request when completed.
        The output of tasks cannot be abstract things like "Ensure compliance with regulations".
        Instead, you should request deliverables such as: "Use search results or queries to write a one page document on regulations regarding Class I medical devices. Once completed, this document will be shared with the team responsible for financial planning."
        Make the tasks modular and use common sense.
        Make each step equivalent to one file in the finished design (e.g. utilities.c/Makefile/map.c/player.py etc.).
        Favor simple, verifiable steps.
        <STRUCTURE> Output should be a bulleted list using one asterisk.
        Each bulleted item should represent exactly one file
        <IMPORTANT NOTE> Files must be listed in the order they should be completed
        You must keep each output contained to a single line. if the output is not contained to a single line the whole system will break
        <EXAMPLE OUTPUT>
        * Create a file containing the word "foo"
        * Create a .c file named example.c that reads the text file foo.txt and prints the contents
        * Create a makefile to compile a c file named example.c
        <REQUEST> {self.request}
        '''
    def plan(self):
        #Plan here
        messages = []
        
        # Gather tasks
        u.add_message(self.llm, messages, self.sysprompt, "system")
        planner_output1 = u.infer(self.llm, messages)
        u.add_message(self.llm, messages, planner_output1, "assistant")
        self.master_plan = planner_output1
        list = planner_output1.split('*')
  
        print(f"\n\n{planner_output1}\n\n")

        for id, item in enumerate(list):
            if id != 0:
                self.directives.append(item)



'''
Team-level feedback manager -- makes decisions based on feedback about what to do to teams
-passes relevant messages to teams
-warns of catastrophe (entire structure must be re-evaluated)
-collects the team outputs
'''
class Teams_Feedback_Processor:
    def __init__(self, feedback, teams, llm):
        self.feedback = feedback
        self.teams = teams
        self.notes
        self.sysprompt = f'''<CONTEXT> You perform an integral role within a recursive branching agent structure.
        The prime directive of this pipeline is the following: {self.teams.teams_info.prime_directive}
        this is the combined task of all of the teams.
        The prime directive has been broken down into the following deliverables: {self.teams.teams_info.master_plan}
        There are one or more teams working on every deliverable.'''
    
    
    def process_team(self, team):
        #check if team needs splitting. if so - split teams, provide their feedback, evaluate them
        #return: team(s) and (possibly synthesized) output
        if team.output == None:
            team.evaluate()
        elif self.feedback == None:
            print("ERROR: NON EMPTY TEAM OUTPUT WITH EMPTY MASTER-LEVEL FEEDBACK")
        else:
            team_s, output, breakdown = split_andor_eval(self, team)
        return team_s, output, breakdown
    

    def split_andor_eval(self, team):
        split_messages = []
        u.add_message(self.llm, split_messages, self.sysprompt, "system")
        boilerplate = f'''<USER> My feedback on the overall project is: {self.feedback}.
        The team currently under consideration currently has the following directive: {team.teaminfo.directive}
The output given from this team was: {team.team_info.output}'''
        split_question1 = "\nGiven the task of the team, the feedback from the user, and the directive of the team, please answer the following yes or no question:\n Is this feedback directly related to the output of this team? That is, can you say with certainty that the output of this team must be changed to address the users feedback?\n You must end your response with the phrase 'my answer is ' yes or no. e.g. this response is related to a different subtask from the one this team is working on. My answer is no"
        split_prompt = boilerplate + split_question1
        u.add_message(self.llm, split_messages, split_prompt, "user")
        feedback_manager_output1 = u.infer(self.llm, split_messages)
        response = feedback_manager_output1.split(' ')
        if response[-1].upper() == "YES":
            split_question2 = '''Thank you for your response. The next question is the following:
            In what way does the feedback from the user relate to the output of this team?
            1. The feedback suggests that the user desires specific changes to be made to this output, but it does not indicate that the team is struggling to solve the technical problem presented to them.
            2. The feedback suggests that the team is struggling to produce a working solution.
            End your responsed with the phrase "My answer is " followed by a numerical digit.
            e.g. The user wants to add a menu item, so it doesn't seem like there are fundamental errors in the code this team produced. My Answer is 2'''
            u.add_message(self.llm, split_messages, split_question2, "user")
            feedback_manager_output2 = u.infer(self.llm, split_messages)
            response2 = feedback_manager_output2.split(' ')
            if response2[-1].upper() == "1":

                messages_temp = split_messages
                split_question3a = '''Thank you for your response. You will now send a message to this team to help them
                adjust their output. Please respond with your message to the team with tailored instructions based on the feedback. Keep your answer brief, under 300 characters'''
                u.add_message(self.llm, messages_temp, split_question3a, "user")
                feedback_manager_output3a = u.infer(self.llm, messages_temp)
                team.feedback = feedback_manager_output3a
            elif response2[-1].upper() == "2":

                split_question3b = '''Thank you for your response.
                Based on your responses, we have decided to split the tasks of this team across two separate teams.
                These teams will work together to complete the directive of the original team.
                As you know, the current team directive is: ({team.teaminfo.directive})
                Please break this directive into two subdirectives.
                <OUTPUT STRUCTURE> Output should be a numbered list with two items. If the subdirectives must be completed in order, please make the first task to be completed number one.
                <Additional Notes> Team directives should contain all of the information the team needs to proceed with their task. Teams are provided some information, but you should not make any assumptions about what information they will have access to. Try to provide them with all of the information relevant to them.
                <Example Output>
                1. As part of a project to make a dungeon crawler terminal game, your team is working on a subtask of the player.c file. Your teams job is to write the player datatype. The player datatype should include: health, stamina, endurance 
                2. As part of a project to make a dungeon crawler terminal game, another team is working on the player data type. Your teams job is to implement that teams data structure into a combat() function. The function should take two arguments - one for the player, and one for the enemy.'''
                messages_temp = split_messages
                u.add_message(self.llm, messages_temp, split_question3b, "user")
                feedback_manager_output3b = u.infer(self.llm, messages_temp)
                response3 = feedback_manager_output3b.split('.')
                team1 = team.deepcopy()
                team1.feedback = None
                team1.directive = response3[1]
                team1.evalute()
                team2 = team.deepcopy()
                team2.feedback = None
                team2.directive = response3[3]
                team2.evaluate()
                self.synthesize_tuple(self, team1, team2)
                teams = [team1, team2]
            else:

                print("ERROR")
                pause = input("error with feedback agent")
                output = team.output
        elif response[-1].upper() == "NO":
            output = team.output
        else:
            print("ERROR")
            pause = input("error with feedback agent")
            
    def synthesize_tuple(self, team1, team2):
        messages = []
        synth_sysprompt = '''<ROLE> You are a Synthesizing Agent:
        <TASK> You will be provided two outputs. You will synthesize them into a single result'''
        u.add_message(self.llm, messages, synth_sysprompt, "system")
        synth_prompt = f'''<OUTPUT1> {team1.output} <OUTPUT2> {team2.output}'''
        u.add_message(self.llm, messages, synth_prompt, "user")
        output = u.infer(self.llm, messages)
        return output
