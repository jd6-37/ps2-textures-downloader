import requests
import os
import sys
import zlib
import json
import gzip
import base64


# Import helper functions
from helpers import load_config_new, ConfigManager, remove_empty_folders, check_rate_limits, localize_reset_timestamp, get_and_print_local_time, format_time_difference, get_current_time


config_manager = ConfigManager()
# Access configuration variables
debug_mode = config_manager.debug_mode
initial_setup_done = config_manager.initial_setup_done
local_directory = config_manager.local_directory
# github_token = config_manager.github_token
last_run_date = config_manager.last_run_date
project_name = config_manager.project_name
owner = config_manager.owner
repo = config_manager.repo
branch_name = config_manager.branch_name
subdirectory = config_manager.subdirectory
slus_folder = config_manager.slus_folder
json_url = config_manager.json_url
# Other variables
github_repo_url = config_manager.github_repo_url
# Initialize user_choice_var as a global variable
user_choice_var = config_manager.user_choice_var

# Define paths to directory trees
local_tree_path = "utils/local_directory_tree.txt"
repo_tree_path = "utils/repo_directory_tree.txt"

# Set dry_run flag
dry_run = False



import requests

def get_repo_contents_recursive(owner, repo, path='', branch='main'):
    url = f'https://api.github.com/repos/{owner}/{repo}/contents/{path}?ref={branch}'
    headers = {'Accept': 'application/vnd.github.v3+json'}
    file_paths = []

    while url:
        response = requests.get(url, headers=headers)

        if response.status_code == 200:
            contents = response.json()

            for item in contents:
                if item['type'] == 'file':
                    file_paths.append(item['path'])
                elif item['type'] == 'dir':
                    # Recursively get contents for subdirectory
                    subdirectory_paths = get_repo_contents_recursive(owner, repo, item['path'], branch)
                    file_paths.extend(subdirectory_paths)

            # Check if there are more pages
            url = response.links.get('next', {}).get('url')
        else:
            # Handle error
            print(f"Error fetching repository contents. Status code: {response.status_code}")
            break

    return file_paths

# Example usage
owner = 'jd6-37'
repo = 'test-ncaanext'
branch = 'main'

file_paths = get_repo_contents_recursive(owner, repo, branch=branch)

# Save the file paths to repo_directory_tree.txt
with open('repo_directory_tree_GITHUB_API.txt', 'w') as file:
    for file_path in file_paths:
        file.write(file_path + '\n')

print("Directory tree generated for the GitHub repository using the GitHub API.")
