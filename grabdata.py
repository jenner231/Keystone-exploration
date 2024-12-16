import requests
import csv
import json
import os

def get_mythic_plus_runs(all_data, region='world', dungeon='all', affix='tyrannical-challengers-peril-fortified-xalataths-guile',pages=1):
    for i in range(0, pages):
        url = f'https://raider.io/api/v1/mythic-plus/runs?season=season-tww-1&region={region}&dungeon={dungeon}&affixes={affix}&page={i}'
        response = requests.get(url)
    
        if response.status_code == 200:
            data = response.json()
            all_data.extend(data.get('rankings', []))  # Extract rankings
        else:
            print(f"Failed to retrieve data from page {i}: {response.status_code}")


def save_to_csv(data, filename):
    # Define the columns to extract
    headers = [
        'rank', 'score', 'keystone_team_id', 'mythic_level', 'dungeon_name', 'completed_at',
        'clear_time_ms', 'keystone_time_ms', 'num_chests', 'affixes', 'player_name', 
        'player_class', 'player_spec', 'player_role', 'player_realm', 'player_faction'
    ]
    
    # Extract dungeon name (assume the first entry determines the dungeon for the file)
    if data:
        dungeon_name = data[0].get('run', {}).get('dungeon', {}).get('name', 'unknown_dungeon')
    else:
        dungeon_name = 'unknown_dungeon'
    
    # Create a directory for the dungeon if it doesn't exist
    os.makedirs(dungeon_name, exist_ok=True)
    
    # Save the file in the dungeon-specific folder
    filepath = os.path.join(dungeon_name, filename)
    
    # Open a CSV file for writing
    with open(filepath, mode='w', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        writer.writerow(headers)  # Write header row
        
        # Iterate through rankings
        for entry in data:
            rank = entry.get('rank', '')
            score = entry.get('score', '')
            run = entry.get('run', {})
            
            # Extract run-level data
            keystone_team_id = run.get('keystone_team_id', '')
            mythic_level = run.get('mythic_level', '')
            dungeon_name = run.get('dungeon', {}).get('name', '')
            completed_at = run.get('completed_at', '')
            clear_time_ms = run.get('clear_time_ms', '')
            keystone_time_ms = run.get('keystone_time_ms', '')
            num_chests = run.get('num_chests', '')
            affixes = ", ".join([affix['name'] for affix in run.get('weekly_modifiers', [])])
            
            # Extract roster data (players)
            roster = run.get('roster', [])
            for player in roster:
                character = player.get('character', {})
                player_name = character.get('name', '')
                player_class = character.get('class', {}).get('name', '')
                player_spec = character.get('spec', {}).get('name', '')
                player_role = player.get('role', '')
                player_realm = character.get('realm', {}).get('name', '')
                
                # Write a row for each player in the roster
                writer.writerow([
                    rank, score, keystone_team_id, mythic_level, dungeon_name, completed_at,
                    clear_time_ms, keystone_time_ms, num_chests, affixes, player_name, 
                    player_class, player_spec, player_role, player_realm
                ])
    
    print(f'Data saved to {filepath}')


if __name__ == "__main__":
    region = 'world'
    regions = ['world', 'eu','us','kr','tw','cn']
    dungeon = 'all'
    dungeons = ['Ara-Kara, City of Echoes', 'The Necrotic Wake', 'Mists of Tirna Scithe', 'The Dawnbreaker',
                'The Stonevault', 'City of Threads', 'Siege of Boralus', 'Grim Batol'
                ]
    #xalataths-bargain-ascendant-tyrannical-challengers-peril-fortified
    affixes = ['xalataths-bargain-ascendant', #lowest (<=3)
               #'xalataths-bargain-ascendant-tyrannical', 'xalataths-bargain-ascendant-fortified', # 4-6
               'xalataths-bargain-ascendant-tyrannical-challengers-peril', 'xalataths-bargain-ascendant-fortified-challengers-peril', # 7-9
               'xalataths-bargain-ascendant-tyrannical-challengers-peril-fortified', #10-11
               #Voidbound
               'xalataths-bargain-voidbound', #lowest (<=3)
               #'xalataths-bargain-voidbound-tyrannical', 'xalataths-bargain-voidbound-fortified', # 4-6
               'xalataths-bargain-voidbound-tyrannical-challengers-peril', 'xalataths-bargain-voidbound-fortified-challengers-peril', # 7-9
               'xalataths-bargain-voidbound-tyrannical-challengers-peril-fortified', #10-11
               #Oblivion
               'xalataths-bargain-oblivion', #lowest (<=3)
               #'xalataths-bargain-oblivion-tyrannical', 'xalataths-bargain-oblivion-fortified', # 4-6
               'xalataths-bargain-oblivion-tyrannical-challengers-peril', 'xalataths-bargain-oblivion-fortified-challengers-peril', # 7-9
               'xalataths-bargain-oblivion-tyrannical-challengers-peril-fortified', #10-11
               #Devour
               'xalataths-bargain-devour', #lowest (<=3)
               #'xalataths-bargain-devour-tyrannical', 'xalataths-bargain-devour-fortified', # 4-6
               'xalataths-bargain-devour-tyrannical-challengers-peril', 'xalataths-bargain-devour-fortified-challengers-peril', # 7-9
               'xalataths-bargain-devour-tyrannical-challengers-peril-fortified', #10-11
               #Above 12
               'tyrannical-challengers-peril-fortified-xalataths-guile' #>12 (17-19)
               ]
    
    affix_short_names = {
    'xalataths-bargain-ascendant': 'Asc-3',
    'xalataths-bargain-ascendant-tyrannical-challengers-peril': 'Asc-9-T',
    'xalataths-bargain-ascendant-fortified-challengers-peril': 'Asc-9-F',
    'xalataths-bargain-ascendant-tyrannical-challengers-peril-fortified': 'Asc-11',
    'xalataths-bargain-voidbound': 'Void-3',
    'xalataths-bargain-voidbound-tyrannical-challengers-peril': 'Void-9-T',
    'xalataths-bargain-voidbound-fortified-challengers-peril': 'Void-9-F',
    'xalataths-bargain-voidbound-tyrannical-challengers-peril-fortified': 'Void-11',
    'xalataths-bargain-oblivion': 'Obliv-3',
    'xalataths-bargain-oblivion-tyrannical-challengers-peril': 'Obliv-9-T',
    'xalataths-bargain-oblivion-fortified-challengers-peril': 'Obliv-9-F',
    'xalataths-bargain-oblivion-tyrannical-challengers-peril-fortified': 'Obliv-11',
    'xalataths-bargain-devour': 'Dev-3',
    'xalataths-bargain-devour-tyrannical-challengers-peril': 'Dev-9-T',
    'xalataths-bargain-devour-fortified-challengers-peril': 'Dev-9-F',
    'xalataths-bargain-devour-tyrannical-challengers-peril-fortified': 'Dev-11',
    'tyrannical-challengers-peril-fortified-xalataths-guile': '12+'
}
    pages = 100
    

    # Fetch the data
    for region in regions:
        for dungeon in dungeons:
            for affix in affixes:
                all_data = []
                get_mythic_plus_runs(all_data, region, dungeon, affix, pages)
                
                short_affix = affix_short_names.get(affix, affix)
                # Save the data to CSV
                filename = f'{region}_{dungeon}_{short_affix}.csv'
                save_to_csv(all_data, filename)
                print(f'Data saved to {filename}')
