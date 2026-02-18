import re


changelog = '''
<<STRUCTURE UPDATED>>
📁 src/
  📄 main.c [team_0001] - Initialize ncurses and game loop
  📄 game.c [team_0002] - Implement core game logic and state management
  📄 map.c [team_0003] - Implement procedural map generation and rendering
  📄 player.c [team_0004] - Implement player movement and actions
  📄 gold.c [team_0005] - Implement gold collection and scoring logic
  📄 ncurses_wrapper.c [team_0006] - Implement ncurses wrapper functions
📁 include/
  📄 game.h [team_0007] - Declare game logic functions and data structures
  📄 map.h [team_0008] - Declare map generation and rendering functions
  📄 player.h [team_0009] - Declare player movement and actions functions
  📄 gold.h [team_0010] - Declare gold collection and scoring functions
  📄 ncurses_wrapper.h [team_0011] - Declare ncurses wrapper functions
📁 utils/
  📄 map_generator.c [team_0013] - Implement procedural map generation algorithms
📄 Makefile [team_0014] - Build system configuration
<<STRUCTURE UPDATED>>
---
[ITER_0]| ID:team_0004 | src/main.c | Changes: Initialized ncurses library and set up terminal screen with basic input handling
Team 0001: Need map.h and map.c functions for rendering the dungeon map
Team 0001: Requesting gold.h and gold.c for score tracking functionality 
<<< TEAM OUTPUT START >>>
#include <ncurses.h>
#include "game.h"
#include "map.h"
#include "player.h"
#include "gold.h"
#include "ncurses_wrapper.h"

int main() {
    // Initialize ncurses
    initscr();
    cbreak();
    noecho();
    keypad(stdscr, TRUE);

    // Game loop
    int ch;
    bool game_running = true;

    while (game_running) {
        // Handle input
        ch = getch();

        // Exit on ESC key
        if (ch == 27) {
            game_running = false;
        }

        // Refresh screen
        refresh();
    }

    // End ncurses
    endwin();

    return 0;
}
<<< TEAM OUTPUT END >>>
---
[ITER_0]| ID:team_0003 | src/map.c | Changes: Implemented procedural map generation with rooms and corridors, random terrain features, and ncurses rendering functions.

Team 0003: Need player.h and player.c for player position integration in map rendering
Team 0003: Requesting gold.h and gold.c for gold position integration in map rendering
[TEAM_REVIEW_MANAGER]: Need to define Map struct and related functions for interface consistency 
<<< TEAM OUTPUT START >>>
#include <stdlib.h>
#include <time.h>
#include "map.h"
#include "ncurses_wrapper.h"

// Map structure definition
typedef struct {
    int width;
    int height;
    char** tiles;
} Map;

// Room structure
typedef struct {
    int x, y;
    int width, height;
} Room;

// Function to initialize map
void map_init(Map* map, int width, int height) {
    map->width = width;
    map->height = height;

    // Allocate memory for tiles
    map->tiles = (char**)malloc(height * sizeof(char*));
    for (int i = 0; i < height; i++) {
        map->tiles[i] = (char*)malloc(width * sizeof(char));
    }

    // Initialize all tiles to walls
    for (int y = 0; y < height; y++) {
        for (int x = 0; x < width; x++) {
            map->tiles[y][x] = '#';
        }
    }
}

// Function to generate a room
void generate_room(Map* map, Room* room) {
    room->x = rand() % (map->width - 10) + 1;
    room->y = rand() % (map->height - 10) + 1;
    room->width = rand() % 6 + 4;
    room->height = rand() % 6 + 4;
}

// Function to carve a room
void carve_room(Map* map, Room* room) {
    for (int y = room->y; y < room->y + room->height; y++) {
        for (int x = room->x; x < room->x + room->width; x++) {
            if (x >= 0 && x < map->width && y >= 0 && y < map->height) {
                map->tiles[y][x] = '.';
            }
        }
    }
}

// Function to create a corridor between two points
void create_corridor(Map* map, int x1, int y1, int x2, int y2) {
    int current_x = x1;
    int current_y = y1;

    while (current_x != x2 || current_y != y2) {
        if (current_x < x2) {
            current_x++;
        } else if (current_x > x2) {
            current_x--;
        }

        if (current_y < y2) {
            current_y++;
        } else if (current_y > y2) {
            current_y--;
        }

        if (current_x >= 0 && current_x < map->width && current_y >= 0 && current_y < map->height) {
            map->tiles[current_y][current_x] = '.';
        }
    }
}

// Function to generate procedural map
void map_generate(Map* map) {
    // Seed random number generator
    srand(time(NULL));

    // Create initial rooms
    Room rooms[5];
    for (int i = 0; i < 5; i++) {
        generate_room(map, &rooms[i]);
        carve_room(map, &rooms[i]);
    }

    // Connect rooms with corridors
    for (int i = 0; i < 4; i++) {
        int x1 = rooms[i].x + rooms[i].width / 2;
        int y1 = rooms[i].y + rooms[i].height / 2;
        int x2 = rooms[i+1].x + rooms[i+1].width / 2;
        int y2 = rooms[i+1].y + rooms[i+1].height / 2;
        create_corridor(map, x1, y1, x2, y2);
    }
}

// Function to render map
void map_render(Map* map) {
    for (int y = 0; y < map->height; y++) {
        for (int x = 0; x < map->width; x++) {
            mvaddch(y, x, map->tiles[y][x]);
        }
    }
}

// Function to check if position is valid
bool is_valid_position(Map* map, int x, int y) {
    return (x >= 0 && x < map->width && y >= 0 && y < map->height);
}

// Function to check if position is walkable
bool is_walkable(Map* map, int x, int y) {
    if (!is_valid_position(map, x, y)) {
        return false;
    }
    return (map->tiles[y][x] == '.' || map->tiles[y][x] == 'G');
}

// Function to cleanup map
void map_cleanup(Map* map) {
    for (int i = 0; i < map->height; i++) {
        free(map->tiles[i]);
    }
    free(map->tiles);
}

// Function to get tile at position
char get_tile_at(Map* map, int x, int y) {
    if (is_valid_position(map, x, y)) {
        return map->tiles[y][x];
    }
    return '#';
}

// Function to set tile at position
void set_tile_at(Map* map, int x, int y, char tile) {
    if (is_valid_position(map, x, y)) {
        map->tiles[y][x] = tile;
    }
}
<<< TEAM OUTPUT END >>>
<<STRUCTURE UPDATED>>
📁 src/
  📄 main.c [team_0001] - Initialize ncurses and game loop
  📄 game.c [team_0002] - Implement core game logic and state management
  📄 map.c [team_0003] - Implement procedural map generation and rendering
  📄 player.c [team_0004] - Implement player movement and actions
  📄 gold.c [team_0005] - Implement gold collection and scoring logic
  📄 ncurses_wrapper.c [team_0006] - Implement ncurses wrapper functions
📁 include/
  📄 game.h [team_0007] - Declare gamfdsfdsfsdfdsfsdfdsfdsfng functions
  📄 player.h [team_0009] - Declare playersdfsdfsdand actions functions
  📄 gold.h [team_0010] - Declare gold collection and scoring functions
  📄 ncurses_wrapper.h [team_0011] - Declare ncurses wrapper functions
📁 utils/
  📄 map_generator.c [team_0013] - Implement procedural map generation algorithms
📄 Makefile [team_0014] - Build system configuration
<<STRUCTURE UPDATED>>
---
[ITER_1]| ID:team_0004 | src/player.c | Changes: Implemented player movement logic, input handling, and collision detection
Team 0004: Need gold.h and gold.c functions for gold collection integration
Team 0004: Requesting map.h functions for player position validation against map boundaries 
<<< TEAM OUTPUT START >>>
#include <stdlib.h>
#include "player.h"
#include "map.h"
#include "ncurses_wrapper.h"

// Player structure definition
typedef struct {
    int x;
    int y;
    int health;
    int max_health;
    int inventory_size;
    int gold_count;
} Player;

// Function to initialize player
void player_init(Player* player) {
    player->x = 1;
    player->y = 1;
    player->health = 100;
    player->max_health = 100;
    player->inventory_size = 10;
    player->gold_count = 0;
}

// Function to update player position based on input
void player_update(Player* player) {
    // This function will be called in the game loop to handle movement
    // Implementation will be in the game loop
}

// Function to handle player movement input
void player_handle_input(Player* player, int ch) {
    int new_x = player->x;
    int new_y = player->y;

    switch (ch) {
        case KEY_UP:
        case 'w':
        case 'W':
            new_y--;
            break;
        case KEY_DOWN:
        case 's':
        case 'S':
            new_y++;
            break;
        case KEY_LEFT:
        case 'a':
        case 'A':
            new_x--;
            break;
        case KEY_RIGHT:
        case 'd':
        case 'D':
            new_x++;
            break;
        default:
            return;
    }

    // Check if new position is valid and walkable
    if (is_walkable(get_current_map(), new_x, new_y)) {
        player->x = new_x;
        player->y = new_y;
    }
}

// Function to render player on screen
void player_render(Player* player) {
    mvaddch(player->y, player->x, '@');
}

// Function to get player position
void player_get_position(Player* player, int* x, int* y) {
    *x = player->x;
    *y = player->y;
}

// Function to update player health
void player_update_health(Player* player, int amount) {
    player->health += amount;
    if (player->health > player->max_health) {
        player->health = player->max_health;
    }
    if (player->health < 0) {
        player->health = 0;
    }
}

// Function to add gold to player inventory
void player_add_gold(Player* player, int amount) {
    player->gold_count += amount;
}

// Function to get player gold count
int player_get_gold(Player* player) {
    return player->gold_count;
}

// Function to cleanup player resources
void player_cleanup(Player* player) {
    // No dynamic memory allocation in this simple implementation
}
<<< TEAM OUTPUT END >>>
---
[ITER_0]| ID:team_0005 | src/gold.c | Changes: Implemented gold collection mechanics and scoring system with functions to place gold on map, detect collection, and display score.

Team 0005: Need map.h functions to check for gold positions and player collision detection
Team 0005: Requesting player.h functions to update player gold count and health when collecting gold
[TEAM_REVIEW_MANAGER]: Need to define consistent interface for map tile checking and gold placement functions 
<<< TEAM OUTPUT START >>>
#include <stdlib.h>
#include <time.h>
#include "gold.h"
#include "map.h"
#include "player.h"
#include "ncurses_wrapper.h"

// Function to initialize gold system
void gold_init() {
    // Seed random number generator
    srand(time(NULL));
}

// Function to place gold on map during generation
void gold_place_on_map(Map* map) {
    // Place gold on some floor tiles
    for (int y = 0; y < map->height; y++) {
        for (int x = 0; x < map->width; x++) {
            if (map->tiles[y][x] == '.') {
                // 10% chance to place gold on floor tile
                if (rand() % 10 == 0) {
                    map->tiles[y][x] = 'G';
                }
            }
        }
    }
}

// Function to check if player collected gold
void gold_check_collection(Player* player, Map* map, int* score) {
    int player_x, player_y;
    player_get_position(player, &player_x, &player_y);

    if (map->tiles[player_y][player_x] == 'G') {
        // Collect gold
        player_add_gold(player, 1);
        (*score)++;

        // Remove gold from map
        map->tiles[player_y][player_x] = '.';
    }
}

// Function to render score at top left
void gold_render_score(int score) {
    mvprintw(0, 0, "Score: %d", score);
}

// Function to cleanup gold resources
void gold_cleanup() {
    // No dynamic memory allocation in this simple implementation
}
<<< TEAM OUTPUT END >>>


'''

def compress_changelog(changelog_text):
    """
    Extract only the most recent structure update and most recent output for each active team.
    
    Args:
        changelog_text: Full changelog string
        teams: Nested list of team objects
        
    Returns:
        Compressed changelog string
    """
    # Flatten teams to get all active team IDs
    active_team_ids = set()
    for idx in range(1, 7):  # 1 through 6
        active_team_ids.add(f"team_{idx:04d}")  # team_0001, team_0002, etc.
    
    # Extract most recent structure update
    structure_pattern = r'<<STRUCTURE UPDATED>>\n(.*?)\n<<STRUCTURE UPDATED>>'
    structure_matches = list(re.finditer(structure_pattern, changelog_text, re.DOTALL))
    most_recent_structure = structure_matches[-1].group(0) if structure_matches else ""
    
    # Extract all team entries
    # Pattern matches from "---" to "<<< TEAM OUTPUT END >>>"
    team_entry_pattern = r'\[ITER_(\d+)\]\| ID:(team_\d+) \| ([^\|]+) \| Changes: ([^\n]+)\n(.*?)<<< TEAM OUTPUT END >>>'

    team_matches = re.finditer(team_entry_pattern, changelog_text, re.DOTALL)
 
    # Store most recent entry for each team ID
    most_recent_entries = {}
    
    for match in team_matches:
        iteration = int(match.group(1))
        team_id = match.group(2)
        filename = match.group(3).strip()
        changes = match.group(4).strip()
        full_content = match.group(5)  # Everything between Changes line and OUTPUT END
        
        # Parse out comments and output
        output_start_pattern = r'<<< TEAM OUTPUT START >>>\n(.*)'
        output_match = re.search(output_start_pattern, full_content, re.DOTALL)
        
        if output_match:
            output_content = output_match.group(1).strip()
            # Everything before OUTPUT START is comments
            comments_section = full_content[:output_match.start()].strip()
        else:
            output_content = ""
            comments_section = full_content.strip()
        
        # Keep only if this is a more recent iteration for this team
        if team_id not in most_recent_entries or iteration > most_recent_entries[team_id]['iteration']:
            most_recent_entries[team_id] = {
                'iteration': iteration,
                'team_id': team_id,
                'filename': filename,
                'changes': changes,
                'comments': comments_section,
                'output': output_content,
                'full_match': match.group(0)
            }
    
    # Build compressed changelog
    compressed = ""
    
    # Add structure if exists
    if most_recent_structure:
        compressed += most_recent_structure + "\n\n"
    
    compressed += "="*60 + "CHANGELOG BEGIN" + "="*60 + "\n\n"
    
    # Add most recent entries for active teams only
    # Sort by iteration for chronological order
    sorted_entries = sorted(
        [entry for team_id, entry in most_recent_entries.items() if team_id in active_team_ids],
        key=lambda x: x['iteration']
    )
    
    for entry in sorted_entries:
        compressed += "---\n" + entry['full_match'] + "\n\n"
    
    return compressed.strip()


new_changelog = compress_changelog(changelog)

print(new_changelog)

# Add before the regex
print("Sample from changelog:")
print(repr(changelog[changelog.find("---"):changelog.find("---")+100]))



def compress_changelog(changelog_text, teams):
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
    
    # Extract all team entries
    # Pattern matches from "---" to "<<< TEAM OUTPUT END >>>"
    team_entry_pattern = r'\[ITER_(\d+)\]\| ID:(team_\d+) \| ([^\|]+) \| Changes: ([^\n]+)\n(.*?)<<< TEAM OUTPUT END >>>'

    team_matches = re.finditer(team_entry_pattern, changelog_text, re.DOTALL)
 
    # Store most recent entry for each team ID
    most_recent_entries = {}
    
    for match in team_matches:
        iteration = int(match.group(1))
        team_id = match.group(2)
        filename = match.group(3).strip()
        changes = match.group(4).strip()
        full_content = match.group(5)  # Everything between Changes line and OUTPUT END
        
        # Parse out comments and output
        output_start_pattern = r'<<< TEAM OUTPUT START >>>\n(.*)'
        output_match = re.search(output_start_pattern, full_content, re.DOTALL)
        
        if output_match:
            output_content = output_match.group(1).strip()
            # Everything before OUTPUT START is comments
            comments_section = full_content[:output_match.start()].strip()
        else:
            output_content = ""
            comments_section = full_content.strip()
        
        # Keep only if this is a more recent iteration for this team
        if team_id not in most_recent_entries or iteration > most_recent_entries[team_id]['iteration']:
            most_recent_entries[team_id] = {
                'iteration': iteration,
                'team_id': team_id,
                'filename': filename,
                'changes': changes,
                'comments': comments_section,
                'output': output_content,
                'full_match': match.group(0)
            }
    
    # Build compressed changelog
    compressed = ""
    
    # Add structure if exists
    if most_recent_structure:
        compressed += most_recent_structure + "\n\n"
    
    compressed += "="*60 + "CHANGELOG BEGIN" + "="*60 + "\n\n"
    
    # Add most recent entries for active teams only
    # Sort by iteration for chronological order
    sorted_entries = sorted(
        [entry for team_id, entry in most_recent_entries.items() if team_id in active_team_ids],
        key=lambda x: x['iteration']
    )
    
    for entry in sorted_entries:
        compressed += "---\n" + entry['full_match'] + "\n\n"
    
    return compressed.strip()
