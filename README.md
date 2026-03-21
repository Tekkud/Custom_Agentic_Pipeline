# Custom_Agentic_Pipeline

[![Diagram](Diagram.png)](Diagram.png)
An Agentic Directory Generating Pipeline
## Features:

* MCP protocol
* Edge deployed pipeline developed around Qwen3-Coder-30B-A3B-Instruct
* Efficient KV cache management
* Shared context management
* File and directory creation

## Structure:

* Shared Context Between all Agents:
  For efficiency shared context is only unloaded/updated once per agentic cycle
  * System Prompt
    * Role descriptions contained within a single system prompt for faster transitions
    * Tools usage instructions
    * Supplemental Information
  * Directory Structure Updates
    * Clear-tree directory structure updates are added to shared memory
  * Changelog:
    * Team updates, cross team communication/team notes included within standardized formatting
  * Debugger Entries:
    * Debugger issues which are currently opened
  

* Orchestration Layer:
  * Roles:
    * Directory Planner:
      Inputs:
        * Objective and/or Restructure Request
      Outputs:
        * Updated Team Plan
    * System Assessor:
      * Reviews user feedback - translates user change requests into directory planner instructions (if applicable)
      * Review Manager:
      Inputs:
        * User Feedback
      Outputs:
        * List of teams to execute, high-level team guidance
      * Review Manager Assistant:
        Inputs:
          * Review Manager Document
        Outputs:
          * Targeted per-team high-level obligations
      * Debugger:
        * Inputs:
          * User Feedback
        * Outputs:
          * Reviews shared context. Provides structured updated debugger report
      * Synthesizer
        *Note: The synthesizer is rarely called. The only case where the synthesizer is implemented is when the user explicitly requests that more than two teams work on a single file*
        Inputs:
          * Team Outputs
        Outputs:
          * Final File Contents
  * Execution Layer:
    * Team Manager:
      Inputs:
        * Team obligations
      Outputs:
        * Pseudocode implementation/instructional document for the teams expected output
    * Worker:
      * Inputs:
        * Team obligations, pseudocode implementation
      * Outputs:
        * Teams core output
    * Commenter:
      Inputs:
        * Teams core output
      Outputs:
        * Communication/update section. Cross-team coordination/conversation and requests


* Context Management:
  * Only most recent changelog entries from each active team are included in shared cache
  * Only most recent structure updates included
  * Debugger removes closed bug reports and provides new report each iteration, old report is cleared
  * KV cache is unloaded only once per iteration
    * *Note: Inter-cycle cache clearing is done via ring buffer write pointer reset, which is not stable under certain contexts, such as flash attention. 
    It is used to increase the speed of context transition overhead in the target environment. 
    Ensure your environment supports this feature before utilizing* 












