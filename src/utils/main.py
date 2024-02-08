import os
import sys
import requests
import base64
import hashlib
from datetime import datetime, timezone, timedelta
import time
import pytz
from email.utils import parsedate_to_datetime
import tempfile
import shutil
import argparse

# Import functions
import fullscan
import helpers

# Parse command-line arguments
parser = argparse.ArgumentParser()
parser.add_argument('--user_choice', type=str, default='only_new_content',
                    help='Specify whether to do a full scan or only check for new or modified files.')
args = parser.parse_args()

config_manager = helpers.ConfigManager()
# Access configuration variables
debug_mode = config_manager.debug_mode
initial_setup_done = config_manager.initial_setup_done
local_directory = config_manager.local_directory
github_token = config_manager.github_token
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

# Initialize counter for commits newer than last sync date
counter_valid_commits = 0
# Initialize counter for number of files downloaded
counter_files_downloaded = 0
# Initialize counter for number of files deleted
counter_files_deleted = 0

# For write_last_run_date
config_path = "config.txt"

# Function to write the last run date to config.txt in UTC format
def write_last_run_date():
    try:
        with open(config_path, 'r') as config_file:
            lines = config_file.readlines()

        # Find the line containing last_run_date and update it
        for i, line in enumerate(lines):
            if line.startswith("last_run_date:"):
                # Get the current UTC time
                utc_now = datetime.utcnow().replace(microsecond=0, tzinfo=pytz.UTC)
                # Format and convert the UTC time to a string with milliseconds
                utc_time_str = utc_now.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
                lines[i] = f"last_run_date: {utc_time_str}\n"

        # Write the updated lines back to config.txt
        with open(config_path, 'w') as config_file:
            config_file.writelines(lines)
    except FileNotFoundError:
        # Handle the case when the file doesn't exist
        print("Config file not found.")
        sys.stdout.flush()


def download_file(url, destination, counter_files_downloaded, commit_date=None, debug_mode=False, hash_comparison=True):

    # Create the folder if it doesn't exist
    os.makedirs(os.path.dirname(destination), exist_ok=True)

    # Check if the file with a prepended dash exists locally
    dashed_file_path = os.path.join(os.path.dirname(destination), '-' + os.path.basename(destination))

    if os.path.exists(dashed_file_path):
        # Check if the dashed file is not newer, download the original file as the dashed file
        if commit_date is None or not hash_comparison:
            with open(dashed_file_path, 'wb') as f:
                f.write(requests.get(url).content)
                counter_files_downloaded += 1
                if debug_mode == 'True':
                    print(f"    Downloaded: {os.path.basename(url)} as {os.path.basename(dashed_file_path)}")
                    sys.stdout.flush()
                else:
                    print(f"    Downloaded: {os.path.basename(dashed_file_path)}")
                    sys.stdout.flush()
            return counter_files_downloaded  # Return the updated counter
        else:
            print(f"    Skipping download because exists and is current (with prepended dash).")
            sys.stdout.flush()
            return counter_files_downloaded  # Return the current counter

    # Download the file with the original name
    response = requests.get(url)
    if response.status_code == 200:
        with open(destination, 'wb') as f:
            f.write(response.content)
            counter_files_downloaded += 1
            if debug_mode == 'True':
                print(f"    Downloaded: {os.path.basename(url)} as {os.path.basename(destination)}")
                sys.stdout.flush()
            else:
                print(f"    Downloaded: {os.path.basename(destination)}")
                sys.stdout.flush()
    else:
        print(f"Failed to download file. Status Code: {response.status_code}")
        sys.stdout.flush()

    return counter_files_downloaded  # Return the updated counter




def download_files(repo_url, local_path, branch='main', subdirectory='', debug_mode=False):
    api_url = f"https://api.github.com/repos/{repo_url}/commits?path={subdirectory}&sha={branch_name}"
    headers = {"Authorization": f"Bearer {github_token}"}
    global counter_files_downloaded  # Declare the global variable
    global counter_files_deleted  # Declare the global variable
    global counter_valid_commits  # Declare the global variable

    # Keeping track of finished, deleted and renamed files so they don't get re-downloaded
    finished_files_set = set()

    def add_to_finished_files_set(file_path, debug_mode=False):
        if file_path not in finished_files_set:
            finished_files_set.add(file_path)
            if debug_mode == 'True':
              print(f"    Added to finished files set: {file_path}")
              sys.stdout.flush()
        else:
            if debug_mode == 'True':
                print(f"    File already exists in finished files set.")
                sys.stdout.flush()
    
    # Standard first line
    def starter_line(file_status, relative_path):
        if file_status == 'added':
            bullet = '[+]'
        elif file_status == 'modified':
            bullet = '[~]'
        elif file_status == 'renamed':
            bullet = '[=]'
        else:
            bullet = '[-]'
        print(f"{bullet} {file_status} in commit: {relative_path}")
        sys.stdout.flush()

    while api_url:
        response = requests.get(api_url, headers=headers)

        if response.status_code == 200:
            commits = response.json()
            

            for commit in commits:
                commit_date = datetime.strptime(commit['commit']['author']['date'], '%Y-%m-%dT%H:%M:%SZ')
                commit_hash = commit['sha'][:7]

                if args.user_choice == 'full_scan' or commit_date > last_run_date:
                    counter_valid_commits += 1
                    print()
                    print(f"****** GIT COMMIT ({commit_hash}) DATE: {commit_date} ******")
                    sys.stdout.flush()
                    commit_sha = commit['sha']
                    files_url = f"https://api.github.com/repos/{repo_url}/commits/{commit_sha}?path={subdirectory}&sha={branch_name}"
                    files_response = requests.get(files_url, headers=headers)

                    if files_response.status_code == 200:
                        files_info = files_response.json()['files']

                        while 'next' in files_response.links:
                            next_page_url = files_response.links['next']['url']
                            files_response = requests.get(next_page_url, headers=headers)
                            files_info += files_response.json()['files']

                        for file_info in files_info:
                            file_status = file_info.get('status')  # New, modified, or deleted
                            file_sha = file_info.get('sha')  # hash

                            if debug_mode == 'True':
                                print(f"======== NEXT FILE ==============")
                                sys.stdout.flush()
                            
                            # Get the URL to the item
                            file_url = file_info.get('raw_url')
                            # Get the name of the file or folder
                            file_or_folder_name = os.path.basename(file_info['filename'])
                            # Build the relative path
                            relative_path = os.path.relpath(file_info['filename'], start=subdirectory)

                            # Ignore git and certain (but not all) hidden files and folders
                            if file_or_folder_name.startswith(('.git', '.DS', '._')):
                                starter_line(file_status, relative_path)
                                print(f"    Skipping hidden file or directory.")
                                sys.stdout.flush()
                                continue

                            if 'user-customs' in relative_path:
                                starter_line(file_status, relative_path)
                                print(f"    Skipping file with 'user-customs' in its path.")
                                sys.stdout.flush()
                                continue

                            # Check if the file is outside the specified subdirectory but only if the status wasn't "modified" (handle that later)
                            if file_status != 'renamed':
                                if debug_mode == 'True':
                                    print("    Checking if outside of specified directory by seeing if relative_path starts with '..'.")
                                    print(f"    relative_path: {relative_path}")
                                    sys.stdout.flush()
                                if relative_path.startswith('..') or os.path.isabs(relative_path):
                                    if debug_mode == 'True':
                                        starter_line(file_status, relative_path)
                                        print(f"    Outside of specified subdirectory. Skipping file: {file_info['filename']}")
                                        sys.stdout.flush()
                                    else:
                                        starter_line(file_status, relative_path)
                                        print(f"    Skipping download because outside of specified subdirectory.")
                                        sys.stdout.flush()
                                    continue  # Skip the file and move to the next one
                            
                            # Build the local absolute path
                            file_path = os.path.join(local_path, relative_path)
                            if debug_mode == 'True':
                                print(f"    file_path: {file_path}")



                            # Common for ADDED or MODIFIED or RENAMED
                            if file_status == 'added' or file_status == 'modified' or file_status == 'renamed':

                                # Check if the file is has already been processed
                                if debug_mode == 'True':
                                    print(f"    Checking if in finished_files_set before running hash tests.")
                                if file_path not in finished_files_set:
                                    if debug_mode == 'True':
                                        print(f"    Not in finished_files_set.")
                                    if os.path.exists(file_path):
                                        # Compute the local hash
                                        local_file_hash = helpers.compute_local_file_hash(file_path, debug_mode)
                                        # Compare local hash to github file hash
                                        hash_comparison = helpers.compare_hashes(local_file_hash, file_sha, file_path, debug_mode)
                                    
                                    # Check for prepended version and use that unless there is also the normal/non-prepended version
                                    else:
                                        if debug_mode == 'True':
                                            print("    LOCAL PATH DOESN'T EXIST. Checking if there is a disabled/prepended version.")
                                            # Split the path into directory and filename
                                        directory, filename = os.path.split(file_path)
                                        # Add a dash before the final segment (filename or folder)
                                        modified_filename = '-' + filename
                                        # Join the directory and modified filename to get the new path
                                        file_path_prepended = os.path.join(directory, modified_filename)
                                        # Check if disabled/prepended version exists
                                        if os.path.exists(file_path_prepended):
                                            # Redefine file_path to prepended name
                                            if debug_mode == 'True':
                                                print(f"    It exists. Modifying path for hash comparison to: {file_path_prepended}")
                                            # Compute the local hash
                                            local_file_hash = helpers.compute_local_file_hash(file_path_prepended, debug_mode)
                                            if debug_mode == 'True':
                                                print(f"    Computed hash for file_path_prepended is {local_file_hash}")
                                            # Compare local hash to github file hash
                                            hash_comparison = helpers.compare_hashes(local_file_hash, file_sha, file_path, debug_mode)
                                            if debug_mode == 'True':
                                                print(f"    Is remote has same as file_path_prepended: {hash_comparison}")
                                        else:
                                            if debug_mode == 'True':
                                                print(f"    Disabled/prepended file doesn't exist: {file_path}")
                                            hash_comparison = False
                                    sys.stdout.flush()
                                else:
                                    if debug_mode == 'True':
                                        print(f"    In finished_files_set. Skipping hash tests.")
                                        sys.stdout.flush()


                                # Detailed output for debug mode
                                if debug_mode == 'True':
                                    # print(f"- {file_status} File: {file_info['filename']}, Relative Path: {relative_path}")
                                    starter_line(file_status, relative_path)
                                    print(f"    Remote hash: {file_sha}")
                                    # initialize variable
                                    local_file_hash = "" 
                                    if local_file_hash:
                                        print(f"    Local_file_hash exists as {local_file_hash}.")
                                        if hash_comparison == True:
                                            print(f"    Local hash: {local_file_hash}")
                                            print("    HASHES ARE SAME.")
                                        else:
                                            print(f"    Local hash: {local_file_hash}")
                                            print("    DIFFERENT HASHES.")

                                    sys.stdout.flush()
                                # Normal output
                                else:
                                    starter_line(file_status, relative_path)
                            
                            
                            # ADDED or MODIFIED
                            if file_status == 'added' or file_status == 'modified':

                                # Check if the file is has already been processed
                                if debug_mode == 'True':
                                    print(f"    Checking if in finished_files_set.")
                                if file_path in finished_files_set:
                                    print(f"    Skipping because already processed in a newer commit.")
                                    sys.stdout.flush()
                                    continue  # Skip the file and move to the next one
                                else:
                                    if debug_mode == 'True':
                                        print(f"    Not in finished_files_set.")

                                if file_status == 'added':
                                    if not os.path.exists(file_path) or not hash_comparison:
                                        counter_files_downloaded = download_file(file_url, file_path, counter_files_downloaded, commit_date, debug_mode, hash_comparison)
                                    else:
                                        print(f"    Skipping download because file exists and matches github file.")
                                    # Add to finished file set to skip processing in older commits
                                    if debug_mode == 'True':
                                        print(f"    Adding to the finished_files_set.")
                                    add_to_finished_files_set(file_path, debug_mode)   
                                    sys.stdout.flush()
                                    continue  
                                    
                                  
                                if file_status == 'modified':
                                    if debug_mode == 'True':
                                        print(f"    Check if hash is different before downloading: {file_path}")  # Debugging output
                                    if not os.path.exists(file_path) or not hash_comparison:
                                        # Download the file (or prepended file) and update the counter
                                        counter_files_downloaded = download_file(file_url, file_path, counter_files_downloaded, commit_date, debug_mode, hash_comparison)
                                    else:
                                        print(f"    Skipping download because files are identical.")
                                    # Add to finished file set to skip processing in older commits
                                    if debug_mode == 'True':
                                        print(f"    Adding to the finished_files_set.")
                                    add_to_finished_files_set(file_path, debug_mode)   
                                    sys.stdout.flush()
                                    continue  
                                    
                            elif file_status == 'renamed':
                                old_file_relative_path = os.path.relpath(file_info['previous_filename'], start=subdirectory)
                                old_file_path = os.path.join(local_path, old_file_relative_path)
                                new_file_path = file_path

                                # Info on what happened in the commit
                                if debug_mode == 'True':
                                    print(f"    In commit, {old_file_relative_path} renamed to {relative_path}.")
                               
                                # Check if the file is has already been processed
                                if file_path in finished_files_set:
                                    # Add the old name if it's not already in the set
                                    print(f"    Skipping because new or old path already processed in a newer commit.")
                                    if debug_mode == 'True':
                                            print(f"    Adding old path to the finished_files_set. New path was already there.")
                                    add_to_finished_files_set(old_file_path)  
                                    sys.stdout.flush()
                                    continue  # Done. Move on to the next file

                                # Check if activity was all outside of the subdirectory and skip to next file if so
                                if debug_mode == 'True':
                                    print("    Checking if all activity was outside of specified directory by seeing if relative_paths both start with '..'.")
                                    print(f"    New path: {relative_path}")
                                    print(f"    Old Path: {old_file_relative_path}")
                                    sys.stdout.flush()
                                # Checking both old and new file names 
                                if relative_path.startswith('..') or os.path.isabs(relative_path):
                                    if old_file_relative_path.startswith('..') or os.path.isabs(old_file_relative_path):
                                        print(f"    Old name and new name outside of specified subdirectory. Skipping file.")
                                        sys.stdout.flush()
                                        continue  # Skip the file and move to the next one
                                else:
                                    if debug_mode == 'True':
                                        print("    One or both of the old/new filenames are inside the specified subdirectory. Proceeding...")


                                # Check if new file name is outside of the subdirectory, and if so, just delete the local file instead of moving it
                                if debug_mode == 'True':
                                    print("    Checking if the new/desination file name is outside of the specified subdirectory by seeing if its relative path starts with '..'.")
                                    print(f"    New path: {relative_path}")
                                    sys.stdout.flush()
                                # Checking new file name
                                if relative_path.startswith('..') or os.path.isabs(relative_path):
                                    if debug_mode:
                                        print(f"    New name is outside of specified directory. Looking for the old file...")
                                    sys.stdout.flush()
                                    # Check if old file exists
                                    if os.path.exists(old_file_path):
                                        if debug_mode:
                                            print(f"    Found the old name file Deleting...")
                                        os.remove(old_file_path)
                                        counter_files_deleted += 1
                                        print(f"    Deleted {file_info['previous_filename']}")
                                    else:
                                        print(f"    File has already been deleted locally.")
                                    
                                    if debug_mode == 'True':
                                        print(f"    Adding old and new path to the finished_files_set..")
                                    add_to_finished_files_set(old_file_path)  
                                    add_to_finished_files_set(new_file_path)  

                                    continue  # Skip the file and move to the next one


                                # Check if new old name is outside of the subdirectory, and if so, download the new name file
                                if debug_mode == 'True':
                                    print("    Checking if the old file name is outside of the specified subdirectory by seeing if its relative path starts with '..'.")
                                    print(f"    Old path: {old_file_path}")
                                    sys.stdout.flush()
                                # Checking new file name
                                if old_file_relative_path.startswith('..') or os.path.isabs(old_file_relative_path):
                                    if debug_mode:
                                        print(f"    Old name is outside of specified directory. Downloading the new file.")
                                    if debug_mode == 'True':
                                        print(f"    Adding old and new path to the finished_files_set..")
                                    add_to_finished_files_set(old_file_path)  
                                    add_to_finished_files_set(new_file_path)  
                                    counter_files_downloaded = download_file(file_url, file_path, counter_files_downloaded, commit_date, debug_mode, hash_comparison)
                                    sys.stdout.flush()

                                    continue  # Skip the file and move to the next one

                                # Check for the old filename to see if file exists
                                if os.path.exists(old_file_path):
                                    # File with the old name exists, rename it to the new name
                                    os.rename(old_file_path, new_file_path)
                                    if debug_mode == 'True':
                                        print(f"    Adding old and new path to the finished_files_set..")
                                    add_to_finished_files_set(old_file_path)  
                                    add_to_finished_files_set(new_file_path)  
                                    print(f"    Renamed: {file_info['previous_filename']} to {relative_path}")
                                    sys.stdout.flush()
                                    continue  # Done. Move on to the next file
                                

                                # Check for a disabled/prepended version of the old filename
                                directory, filename = os.path.split(old_file_path)
                                # Add a dash before the final segment (filename or folder)
                                modified_old_filename = '-' + filename
                                # Join the directory and modified filename to get the new path
                                old_file_path_prepended = os.path.join(directory, modified_old_filename)
                                # Check if disabled/prepended version exists
                                if os.path.exists(old_file_path_prepended):
                                    # disabled/prepended File with the old name exists, rename it to the new name
                                    if debug_mode == 'True':
                                        print(f"    Old file name doesn't exist, but a disabled/prepended file with the old name exists. Renaming it to the new name...")
                                    os.rename(old_file_path_prepended, new_file_path)
                                    if debug_mode == 'True':
                                        print(f"    Adding old and new path to the finished_files_set..")
                                    add_to_finished_files_set(old_file_path)  
                                    add_to_finished_files_set(new_file_path)  
                                    print(f"    Renamed: {modified_old_filename} version of to {relative_path}")
                                    sys.stdout.flush()
                                    continue  # Done. Move on to the next file
                                    
                                # Check for the new filename to see if file exists and if it is current
                                elif os.path.exists(new_file_path):
                                    if not hash_comparison:
                                        # Download the file and update the counter
                                        print(f"    Downloading because the version of new file on github is newer.")
                                        counter_files_downloaded = download_file(file_url, file_path, counter_files_downloaded, commit_date, debug_mode, hash_comparison)
                                        if debug_mode == 'True':
                                            print(f"    Adding old and new path to the finished_files_set..")
                                        add_to_finished_files_set(old_file_path)  
                                        add_to_finished_files_set(new_file_path)  
                                    else:
                                        # File with the new name already exists
                                        if debug_mode == 'True':
                                            print(f"    Adding old and new path to the finished_files_set..")
                                        add_to_finished_files_set(old_file_path)  
                                        add_to_finished_files_set(new_file_path)  
                                        print(f"    Skipping download because already exists with the new name and is current.")
                                    sys.stdout.flush()
                                    continue  # Done. Move on to the next file
                                
                                else:
                                    # Download the file  and update the counter
                                    if debug_mode == 'True':
                                        print(f"    Adding old and new path to the finished_files_set..")
                                    add_to_finished_files_set(old_file_path)  
                                    add_to_finished_files_set(new_file_path)  
                                    if debug_mode == 'True':
                                        print(f"    Downloading because neither the new or old path exist.")
                                    # Proceed to download logic
                                    counter_files_downloaded = download_file(file_url, file_path, counter_files_downloaded, commit_date, debug_mode, hash_comparison)
                                    sys.stdout.flush()
                                
                                continue  

                            elif file_status == 'removed':
                                
                                starter_line(file_status, relative_path)

                                # # Check if the file is outside the specified subdirectory
                                # if debug_mode == 'True':
                                #     print("    Checking if outside of specified directory by seeing if relative_path starts with '..'.")
                                #     print(f"    relative_path: {relative_path}")
                                # if relative_path.startswith('..') or os.path.isabs(relative_path):
                                #     if debug_mode == 'True':
                                #         print(f"    Outside of specified subdirectory. Skipping file: {file_info['filename']}")
                                #     else:
                                #         print(f"    Skipping because outside of specified subdirectory.")
                                #     sys.stdout.flush()
                                #     continue  # Skip the file and move to the next one

                                # Check if the file is has already been processed
                                if file_path in finished_files_set:
                                    print(f"    Skipping because already processed in a newer commit.")
                                    sys.stdout.flush()
                                    continue  # Skip the file and move to the next one
                                
                                # Add to finished file set to skip processing in older commits
                                if debug_mode == 'True':
                                    print(f"    Adding deleted path to the finished_files_set.")
                                add_to_finished_files_set(file_path, debug_mode)

                                # If passed all of those checks, check if the file exists, and if so, delete it.
                                if os.path.exists(file_path):
                                    os.remove(file_path)
                                    counter_files_deleted += 1
                                    if debug_mode:
                                        print(f"    Deleted {file_info['filename']} from {relative_path}")
                                    else:
                                        print(f"    Deleted {relative_path}")
                                else:
                                    if debug_mode == 'True':
                                        print("    LOCAL PATH DOESN'T EXIST. Checking if there is a disabled/prepended version.")
                                        # Split the path into directory and filename
                                    directory, filename = os.path.split(file_path)
                                    # Add a dash before the final segment (filename or folder)
                                    modified_filename = '-' + filename
                                    # Join the directory and modified filename to get the new path
                                    file_path_prepended = os.path.join(directory, modified_filename)
                                    # Check if disabled/prepended version exists
                                    if os.path.exists(file_path_prepended):
                                        if debug_mode == 'True':
                                            print(f"    Prepended version exists at: {file_path_prepended}")
                                        # Delete the prepended version
                                        os.remove(file_path_prepended)
                                        counter_files_deleted += 1
                                        print(f"    Deleted disabled/prepended version because normal named version doesn't exist. ")
                                    else:
                                        print(f"    File has already been deleted locally.")



                                sys.stdout.flush()
                                continue

                            
                            else:
                                print(f"Unknown file status: {file_status}")
                                sys.stdout.flush()
                        
                        # Add to finished file set to skip processing in older commits
                        # add_to_finished_files_set(file_path, debug_mode)


                    else:
                        print(f"Failed to fetch files for commit. Status Code: {files_response.status_code}")
                        print(f"Commit ({commit_hash}) SHA: {commit_sha}, Commit Date: {commit_date}")
                        print(f"Files URL: {files_url}")
                        sys.stdout.flush()

                # else:
                #     print("Commit date is not greater than last run date. Skipping commit")

            if counter_valid_commits < 1:
                print("There is no new or modified content in Github since your last sync date.")
                sys.stdout.flush()
                break  # No need to continue checking older commits

        else:
            print(f"Failed to fetch commits. Status Code: {response.status_code}")
            print(f"API URL: {api_url}")
            sys.stdout.flush()

        # Check for pagination information in the response headers
        link_header = response.headers.get('Link')
        api_url = get_next_page_url(link_header)

    # print(finished_files_set)


def get_next_page_url(link_header):
    # Extracts the URL for the next page from the 'Link' header
    if link_header:
        links = link_header.split(',')
        for link in links:
            if 'rel="next"' in link:
                return link.split(';')[0].strip('<>')
    return None








def download_directory_contents(repo_url, local_path, branch, directory_path, subdirectory=''):
    print("download_files function:")
    api_url = f"https://api.github.com/repos/{repo_url}/contents/{directory_path}?ref={branch_name}"
    headers = {"Authorization": f"Bearer {github_token}"}

    while api_url:
        print(f"Fetching: {api_url}")  # Print the API URL being fetched
        sys.stdout.flush()
        response = requests.get(api_url, headers=headers)

        if response.status_code == 200:
            files = response.json()
            print(f"Received {len(files)} files")  # Print the number of files received
            sys.stdout.flush()

            for file in files:
                file_url = file.get('download_url')

                if file.get('type') == 'dir':
                    download_directory_contents(repo_url, local_path, branch, file['path'], subdirectory)
                elif file_url:
                    # Preserve directory structure inside the specified subdirectory
                    relative_path = os.path.relpath(file['path'], subdirectory)
                    file_path = os.path.join(local_path, relative_path)
                    os.makedirs(os.path.dirname(file_path), exist_ok=True)

                    if not os.path.exists(file_path) or not hash_comparison:
                        # Download the file (or prepended file) and update the counter
                        counter_files_downloaded = download_file(file_url, file_path, counter_files_downloaded, commit_date, debug_mode, hash_comparison)
                    else:
                        print(f"Skipping existing file: {file['path']}")
                        sys.stdout.flush()
                else:
                    print(f"Skipping file {file['path']} - download URL not available")
                    sys.stdout.flush()
        elif response.status_code == 403:
            print(f"Failed to fetch directory contents. Permission issue. Directory: {directory_path}")
        else:
            print(f"Failed to fetch directory contents. Status Code: {response.status_code}")

        # Check for pagination information in the response headers
        link_header = response.headers.get('Link')
        api_url = get_next_page_url(link_header)
        print(f"Next page URL: {api_url}")  # Print the next page URL
        sys.stdout.flush()


# Check if all required variables exist and have values
required_variables = ["local_directory", "github_token", "owner", "repo", "branch_name", "subdirectory"]

if not config_manager.github_token:
    print(f"\nERROR: Cannot run sync. A Github Personal Access Token is missing or empty.")
    print(f"\nA Github Personal Token is required. Without it, your IP address is limited to 60 request per hour,")
    print(f"and that will be easily exceeded by how this installer chunks and downloads the repo.")
    print(f"Get your free API token in your Github account: Settings > Developer Settings > Personal Access Token.")
    print(f"Click profile pic at top right > Settings > Developer Settings (at bottom) > Personal Access Token.")
    sys.exit(1)

for var_name in required_variables:
    if not getattr(config_manager, var_name):
        print(f"\nERROR: Cannot run sync. Configuration variable '{var_name}' is missing or empty.")
        sys.exit(1)


# Check the rate limits (limit resets every hour at top of hour)
limits = helpers.check_rate_limits(github_token)

if limits:
    limit_cap = limits['limit']
    used_calls = limits['used']
    remaining_calls_start = limits['remaining']
    limit_reset_timestamp = limits['reset']
    reset_timestamp_local = helpers.localize_reset_timestamp(limit_reset_timestamp)

    print()
    print(f"Github API RATE LIMITS status: {used_calls} of {limit_cap} calls used. {remaining_calls_start} remaining until the hourly limit reset at {reset_timestamp_local}.")
    # print(f"Raw: {limits}")
    print()
    sys.stdout.flush()
else:
    print()
    print("Unable to retrieve rate limits.")
    print()
    sys.stdout.flush()


# Print the current time
helpers.get_and_print_local_time()
# Get the starting time to calculate the duration later
start_time = helpers.get_current_time()
print()  # Add a line break 
print("#######################################################################")
print("#                                                                     #")
print("#                         Textures Sync                               #")
print("#                                                                     #")
print("#        Reads the history of changes (commits) in Github             #")
print("#      and compares those file changes with your local files.         #")
print("#      For existing files, it compares hashes for accurately          #")
print("#   determining if you have the most recent version of the file.      #")
print("#                                                                     #")
print("#              It ignores your 'user-customs' folder.                 #")
print("#  It recognizes textures you have disabled anywhere in replacements  #")
print("#    (aka files prepended with a dash, such as '-file.png')           #")
print("#   and will keep the disabled file updated to its latest version.    #")
print("#                                                                     #")
print("#---------------------------------------------------------------------#")
print()  # Add a line break 
print()  # Add a line break 
sys.stdout.flush()  # Force flush the output


# Check for new files and download
try:
    print(f"Checking for new or modified files since last run date ({last_run_date})...")
    print()
    sys.stdout.flush()
    # debug_mode_variable_type = type(debug_mode)
    # print(f"debug_mode = {debug_mode} ({debug_mode_variable_type})")
    if debug_mode == True or debug_mode == "True":
      print("Debug mode is on. Output will be verbose.\n")
      sys.stdout.flush()
    download_files(github_repo_url, local_directory, branch_name, subdirectory, debug_mode)
    print()
    sys.stdout.flush()
    # Check the rate limits again to see usage (limit resets every hour at top of hour)
    limits = helpers.check_rate_limits(github_token)
    remaining_calls_end = limits['remaining']
    limit_reset_timestamp = limits['reset']
    reset_timestamp_local = helpers.localize_reset_timestamp(limit_reset_timestamp)
    print(f"Github API RATE LIMITS status: Used {remaining_calls_start - remaining_calls_end} API calls this sync round. {remaining_calls_end} remaining until the hourly limit reset at {reset_timestamp_local}.")
    print()
    print("Finished with textures sync.")
    print(f"{counter_files_downloaded} files downloaded.")
    print(f"{counter_files_deleted} files deleted.")
    print()
    sys.stdout.flush()
    # Call the function to delete empty folders after syncing files
    helpers.remove_empty_folders(local_directory, debug_mode=False)
    print()  # Add a line break 
    print("#                                                                   #")
    print("#     Finished reviewing all changes in specified time period.      #")
    print("#           Comparing directory structure to Github...              #")
    print("#-------------------------------------------------------------------#")
    print()
    sys.stdout.flush()

    # Save the current run date to the config file
    write_last_run_date()
except Exception as e:
    print()
    print(f"Error downloading files: {e}")
    print()
    sys.stdout.flush()

print()  # Add a line break 
print("#-------------------------------------------------------------------#")
print("#                                                                   #")
print("#                      Starting Health Check                        #")
print("#                                                                   #")
print("#    Looking for extraneous textures and duplicate filenames...     #")
print()

# Run fullscan.py to compare directory trees and offer to delete and/or download files
fullscan.run_scan_and_print_output()

if debug_mode == 'True':
    # Check for duplicate texture names across the entire replacements folder
    replacements_path = os.path.join(local_directory, slus_folder, "replacements")
    helpers.check_for_dupes(replacements_path)

print()

print()  # Add a line break 
print("#                                                                   #")
print("#                      Finished Health Check                        #")
print("#-------------------------------------------------------------------#")
print()

# Check the rate limits (limit resets every hour at top of hour)
limits = helpers.check_rate_limits(github_token)

if limits:
    limit_cap = limits['limit']
    used_calls = limits['used']
    remaining_calls_start = limits['remaining']
    limit_reset_timestamp = limits['reset']
    reset_timestamp_local = helpers.localize_reset_timestamp(limit_reset_timestamp)

    print()
    print(f"Github API RATE LIMITS status: {used_calls} of {limit_cap} calls used. {remaining_calls_start} remaining until the hourly limit reset at {reset_timestamp_local}.")
    # print(f"Raw: {limits}")
    print()
    sys.stdout.flush()  # Force flush the output
else:
    print()
    print("Unable to retrieve rate limits.")
    print()
    sys.stdout.flush()  # Force flush the output


# Print the current time
helpers.get_and_print_local_time()
# Get the end time and calculate the duration
end_time = helpers.get_current_time()
formatted_time = helpers.format_time_difference(start_time, end_time)
print(f"The operation took {formatted_time}")
print()
sys.stdout.flush()  # Force flush the output

print()  # Add a line break 
print()  # Add a line break 
print("#-------------------------------------------------------------------#")
print("#                                                                   #")
print("#                              DONE!                                #")
print("#                                                                   #")
print("#   If you answered yes to the prompts to download and/or delete    #")
print("#   files (or you didn't get prompted) your local directory and     #")
print("#   file structure is identical to the Github repository. Great!    #")
print("#                                                                   #")
print("#   TIP: The 'Full Sync' option goes beyond the normal directory    #")
print("#  tree comparison and compares the hashes of every file to ensure  #")
print("# they are identical, rather than just checking if the file exists. #")
print("#  It's recommended you run it occassionally (or if having issues). #")
print("#                                                                   #")
print("#####################################################################")

sys.stdout.flush()  # Force flush the output