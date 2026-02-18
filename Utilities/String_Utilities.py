import re
import os

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

def strip_role_tags(text):
    text = re.sub(r'^\s*(<.*?>)\s*', '', text)
    text = re.sub(r'\s*(<.*?>)\s*$', '', text)
    return text




def has_duplicate_ids(text):
    """
    Checks if any ID appears more than once in the given text. Expects changelog format
    
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