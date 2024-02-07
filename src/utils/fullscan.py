import os
import sys
import requests
import tkinter as tk
from tkinter import filedialog, messagebox
from tkinter.scrolledtext import ScrolledText
from datetime import datetime, timezone, timedelta
from tzlocal import get_localzone
import time
import pytz
from urllib.parse import urljoin, quote

# Import helper functions
from helpers import load_config_new, ConfigManager, remove_empty_folders, check_rate_limits, localize_reset_timestamp, get_and_print_local_time, format_time_difference, get_current_time


config_manager = ConfigManager()
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

# Define paths to directory trees
local_tree_path = "utils/local_directory_tree.txt"
repo_tree_path = "utils/repo_directory_tree.txt"

# Set dry_run flag
dry_run = False


def get_tree_contents(owner, repo, subdirectory='', branch_name='main'):
    url = f'https://api.github.com/repos/{owner}/{repo}/git/trees/{branch_name}?recursive=1'
    headers = {'Authorization': f'token {github_token}'}
    response = requests.get(url, headers=headers)

    if response.status_code != 200:
        # Handle error as needed
        print(response.json())
        print(f"\nERROR: Unable to fetch repository tree. Status code: {response.status_code}. \nAPI rate limit probably exceeded. Try again later. The limit resets every hour. You can see the exact reset time above at the beginning of this output.\n")
        print("Terminating the process. Hasta la vista, baby.\n")
        sys.exit(1)

    tree_data = response.json().get('tree', [])

    return tree_data


def save_repo_directory_tree_to_file(tree_data, current_path='', file_paths=None, subdirectory=''):
    if file_paths is None:
        file_paths = []

    for item in tree_data:
        if item['type'] == 'tree':
            # If it's a directory, recursively call the function
            save_repo_directory_tree_to_file(item.get('contents', []), current_path + item['path'] + '/', file_paths, subdirectory)
        elif item['type'] == 'blob':
            # If it's a file, append the file path to the list only if it starts with the specified subdirectory
            if item['path'].startswith(subdirectory + '/'):
                file_paths.append(current_path + item['path'][len(subdirectory) + 1:])

    return file_paths


def save_local_directory_tree_to_file(directory, output_file=local_tree_path):
    file_paths = []
    for root, dirs, files in os.walk(directory):
        for file_name in files:
            # Ignore hidden files and folders like the .git folder and .gitignore file
            if not file_name.startswith(('.git', '.DS', '._')):
                full_path = os.path.relpath(os.path.join(root, file_name), directory)
                # Make sure that if there is SLUS folder specified, we're only adding paths for files in that folder
                if slus_folder is None or not slus_folder or full_path.startswith(slus_folder):
                    file_paths.append(os.path.relpath(os.path.join(root, file_name), directory))

    # Sort the file paths alphabetically
    file_paths.sort()

    # Save the sorted file paths to output_file
    with open(output_file, 'w') as file:
        for file_path in file_paths:
            file.write(file_path + '\n')

    print("Directory tree generated for the local directory.")
    sys.stdout.flush()  # Force flush the output


def build_full_path(base_path, entry):
    return os.path.join(base_path, entry.replace('/', os.path.sep))


def list_files_not_in_repo(local_tree_path, repo_tree_path, local_directory, dry_run=True):
    # Read local directory tree
    with open(local_tree_path, 'r') as local_file:
        local_files = [line.strip() for line in local_file.readlines()]

    # Read repo directory tree
    with open(repo_tree_path, 'r') as repo_file:
        repo_files = [line.strip() for line in repo_file.readlines()]

    # Build full paths using the provided base path
    local_full_paths = [os.path.join(local_directory, entry) for entry in local_files]
    repo_full_paths = [os.path.join(local_directory, entry) for entry in repo_files]

    # Filter out files with "user-customs" in their path and filenames starting with a dash ("-")
    local_full_paths = [path for path in local_full_paths if "user-customs" not in path and not os.path.basename(path).startswith("-")]
    repo_full_paths = [path for path in repo_full_paths if "user-customs" not in path]

    # Filter out files without "SLUS-XXXXX/replacements/" in their path
    replacements_path = os.path.join(slus_folder, "replacements")
    local_full_paths = [path for path in local_full_paths if replacements_path in path]
    repo_full_paths = [path for path in repo_full_paths if replacements_path in path]

    # Find files in local directory but not in the repo directory
    files_to_delete = set(local_full_paths) - set(repo_full_paths)

    return files_to_delete



def list_files_to_download(local_tree_path, repo_tree_path, local_directory, dry_run=True):
    # Check if the local files already exist on the computer
    with open(local_tree_path, 'r') as local_file:
        local_files = [line.strip() for line in local_file.readlines()]

    # Build full paths using the provided base path
    local_full_paths = [os.path.join(local_directory, entry) for entry in local_files]


    # Read repo directory tree
    with open(repo_tree_path, 'r') as repo_file:
        repo_files = [line.strip() for line in repo_file.readlines()]

    # Build full paths using the provided base path
    repo_full_paths = [os.path.join(local_directory, entry) for entry in repo_files]

    # Filter out files with "user-customs" in their path and filenames starting with a dash ("-")
    local_full_paths = [path for path in local_full_paths if "user-customs" not in path and not path.split("/")[-1].startswith("-")]
    repo_full_paths = [path for path in repo_full_paths if "user-customs" not in path]

    # Find files in repo directory but not in the local directory
    files_to_download = set(repo_full_paths) - set(local_full_paths)

    # Remove local_directory from the paths
    files_to_download = [os.path.relpath(path, local_directory) for path in files_to_download]

    # Filter paths that do not begin with "SLUS-XXXXX/replacements/"
    files_to_download = [path for path in files_to_download if path.startswith(f"{slus_folder}\\replacements\\") or path.startswith(f"{slus_folder}/replacements/")]


    # Check if the local file already exists on the computer before further processing
    files_to_download = [path for path in files_to_download if not os.path.exists(os.path.join(local_directory, path))]

    return files_to_download



def delete_files_not_in_repo(files_to_delete, dry_run=True):

    # Check if there are files to be deleted
    if files_to_delete:
        print("\n\nWAITING FOR YOUR RESPONSE IN THE POP-UP DIALAOG WINDOW...\n")
        sys.stdout.flush()  # Force flush the output
        # Prompt the user to continue with deletion
        if not dry_run:
            confirmation_message = (
                "Files were found to exist locally that are not in Github. These could cause issues. It is advised to delete them."
                "\nIf they are your own custom files or DLC, move them to the 'user-customs' folder where they will be ignored."
                f"\n\nThe {len(files_to_delete)} files listed in the output window WILL BE DELETED. Do you want to proceed?"
            )
            confirmation = messagebox.askyesno("Confirmation", confirmation_message)

            if confirmation:
                # Delete files
                deleted_files = []
                for file_path in files_to_delete:
                    file_path = os.path.join(local_directory, file_path)
                    if os.path.exists(file_path):
                        try:
                            os.remove(file_path)
                            deleted_files.append(file_path)
                        except Exception as e:
                            messagebox.showerror("Error", f"Error deleting file {file_path}: {e}")
                    else:
                        messagebox.showwarning("File Not Found", f"File not found: {file_path}")


                # Print the list of deleted files
                print("\nDeleted Files:")
                for deleted_file in deleted_files:
                    print(deleted_file)
                    sys.stdout.flush()  # Force flush the output

                print("\nDeleted Files", "\nDeleted files:\n" + "\n".join(deleted_files))
                sys.stdout.flush()  # Force flush the output
            else:
                print("\nDeletion cancelled.")
                sys.stdout.flush()  # Force flush the output
        else:
            print("\nDry Run", "(Dry run) Deletion cancelled.")
            sys.stdout.flush()  # Force flush the output
    else:
        print("\nNo Files to Delete", "\nYou don't have any extra files that aren't in the Github repo (other than your custom textures and DLC in the 'user-customs'). Great!")
        sys.stdout.flush()  # Force flush the output


# DOWNLOAD MISSING 
def download_missing_files(github_repo_url, local_directory, branch_name, files_to_download, github_token, debug_mode=False):
    api_base_url = f"https://api.github.com/repos/{github_repo_url}/contents/textures/"
    headers = {"Authorization": f"Bearer {github_token}"} if github_token else {}
    counter_files_downloaded = 0

    for relative_path in files_to_download:
        # Replace %5C with slashes, if any
        corrected_path = relative_path.replace("%5C", "/").replace("\\", "/")
        # Construct the API URL for the file
        api_url = urljoin(api_base_url, f"{corrected_path}?ref={branch_name}")
        print(f"MADE API URL:\n{api_url}\n")
        page = 1

        while api_url:
            # Debugging the url format
            print(f"\nFILE PATH for URL:\n{api_url}\n")

            try:
                response = requests.get(api_url, headers=headers)
                response.raise_for_status()

                file_info = response.json()
                download_url = file_info.get('download_url')

                
                if download_url:
                    file_path = os.path.join(local_directory, relative_path)
                    os.makedirs(os.path.dirname(file_path), exist_ok=True)


                    if not os.path.exists(file_path):
                        # Download the file using the provided download_url
                        download_response = requests.get(download_url, headers=headers)

                        if download_response.status_code == 200:
                            with open(file_path, 'wb') as file:
                                file.write(download_response.content)
                            counter_files_downloaded += 1
                            print(f"Downloaded: {relative_path}")
                            sys.stdout.flush()  
                        else:
                            print(f"Failed to download file: {relative_path}")
                            sys.stdout.flush() 
                    else:
                        print(f"Skipping existing file: {relative_path}")
                        sys.stdout.flush() 
                else:
                    print(f"Download URL not available for file: {relative_path}")
                    sys.stdout.flush() 

                # Check for pagination information in the response headers
                link_header = response.headers.get('Link')
                api_url = get_next_page_url(link_header)
                page += 1

            except requests.exceptions.RequestException as e:
                print(f"Failed to fetch file information. Error: {e}")
                sys.stdout.flush() 

    return counter_files_downloaded


def get_next_page_url(link_header):
    if link_header:
        links = link_header.split(', ')
        for link in links:
            url, rel = link.split('; ')
            if 'rel="next"' in rel:
                return url.strip('<>')
    return None


def download_files_not_in_local(files_to_download, dry_run=True):

    # Check if there are files to download
    if files_to_download:
        print("\n\nWAITING FOR YOUR RESPONSE IN THE POP-UP DIALAOG WINDOW...:\n")
        sys.stdout.flush()
        # Prompt the user to continue with downloading
        if not dry_run:
            confirmation_message = (
                "You're missing files that are in the Github repo. This will cause issues! It is highly recommended that you download them now. See the output window for the list of files."
                f"\n\nOkay to download the {len(files_to_download)} missing files?"
            )
            confirmation = messagebox.askyesno("Confirmation", confirmation_message)

            if confirmation:
                print("\nDownloading files:\n")
                sys.stdout.flush()
                # Download files
                download_missing_files(github_repo_url, local_directory, branch_name, files_to_download, github_token, debug_mode=True)
            else:
                print("\nDownload cancelled.")
                sys.stdout.flush()
        else:
            print("\nDry Run. Download cancelled.")
            sys.stdout.flush()
    else:
        print("\nNo Files to download", "\nYou have everything in the Github repo. Great!")
        sys.stdout.flush()


def create_message_window(title, message):
    root = tk.Tk()
    root.withdraw()  # Hide the main window

    # Define the callback function to be executed after the main loop has a chance to run
    def close_messagebox():
        root.destroy()

    confirmation = messagebox.askyesno(title, message)


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


print()  # Add a line break 
# Print the current time
get_and_print_local_time()
# Get the starting time to calculate the duration later
start_time = get_current_time()
print()  # Add a line break 
print("#######################################################################")
print("#                                                                     #")
print("#                    Textures Sync - DEEP SCAN                        #")
print("#                                                                     #")
print("#    Important for identifying and deleting extraneous textures.      #")
print("#                                                                     #")
print("#     Compares directory trees of local vs repo and prompts to        #")
print("#   download/delete files where it doesn't match the Github repo.     #")
print("#  It ignores the 'user-customs' folder and all disabled textures     #")
print("#  everywhere (aka files prepended with a dash, such as '-file.png')  #")
print("#                                                                     #")
print("#---------------------------------------------------------------------#")
print()  # Add a line break 
print()  # Add a line break 
sys.stdout.flush()  # Force flush the output

# Check the rate limits (limit resets every hour at top of hour)
limits = check_rate_limits(github_token)

if limits:
    limit_cap = limits['limit']
    used_calls = limits['used']
    remaining_calls_start = limits['remaining']
    limit_reset_timestamp = limits['reset']
    reset_timestamp_local = localize_reset_timestamp(limit_reset_timestamp)

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


# Save the local directory tree to a file
print(f"Analyzing local directory structure...")
print()
sys.stdout.flush()  # Force flush the output
save_local_directory_tree_to_file(local_directory)
print()
sys.stdout.flush()  # Force flush the output

# Get the contents of the github repo root directory 
print(f"Analyzing Github repo directory structure...")
print()
sys.stdout.flush()  # Force flush the output

# Step 1: Fetch the repository tree
tree_data = get_tree_contents(owner, repo, subdirectory, branch_name)

# Step 2: Process the tree data and get file paths
file_paths = save_repo_directory_tree_to_file(tree_data, subdirectory=subdirectory)

# Sort the file paths alphabetically
file_paths.sort()

# Save the sorted file paths to repo_directory_tree.txt
with open(repo_tree_path, 'w') as file:
    for file_path in file_paths:
        file.write(file_path + '\n')

print("Directory tree generated for the Github repository.")
sys.stdout.flush()  # Force flush the output


# PROCEED TO PRUNING OR DOWNLOADING -------------------------
print("\nComparing the Github repo directory structure to your local textures folder...")
sys.stdout.flush()  # Force flush the output


# Perform the deletion of local files not in the repo (or dry run) with user prompt
files_to_delete = list_files_not_in_repo(local_tree_path, repo_tree_path, local_directory, dry_run)
if files_to_delete:
    print("\nEXTRA Files to be Deleted:")
    sys.stdout.flush()  # Flush the buffer to ensure immediate display

    for file_path in files_to_delete:
        print(f"- {file_path}")
        sys.stdout.flush()  # Flush the buffer after each line

# Delete the files or print a message saying no files to delete
delete_files_not_in_repo(files_to_delete, dry_run)
sys.stdout.flush()  # Force flush the output


# Perform the download of missing files with user prompt
files_to_download = list_files_to_download(local_tree_path, repo_tree_path, local_directory, dry_run)
if files_to_download:
    print("\nMISSING Files to Download:")
    sys.stdout.flush()  # Flush the buffer to ensure immediate display
    for file_path in files_to_download:
        if file_path.startswith(f"{slus_folder}/replacements/"):
            # Remove the prefix before printing
            print(f"- {file_path[len(f'{slus_folder}/replacements/'):]}")
        else:
            # Print as-is
            print(f"- {file_path}")
        sys.stdout.flush()  # Flush the buffer after each line

# Download the files or print a message saying no files to download
download_files_not_in_local(files_to_download, dry_run)
sys.stdout.flush()  # Force flush the output




# Call the function to delete empty folders after syncing files
remove_empty_folders(local_directory, debug_mode=False)

print()  # Add a line break 
print()  # Add a line break 
print("#-------------------------------------------------------------------#")
print("#                                                                   #")
print("#                              DONE!                                #")
print("#                                                                   #")
print("#  You should also do a FULL SYNC as that will compare the files    #")
print("#    (that already existed and got ignored with this scan) to       #")
print("#       ensure their hashes match and they are identical.           #")
print("#                                                                   #")
print("#####################################################################")
print()

# Check the rate limits (limit resets every hour at top of hour)
limits = check_rate_limits(github_token)

if limits:
    limit_cap = limits['limit']
    used_calls = limits['used']
    remaining_calls_start = limits['remaining']
    limit_reset_timestamp = limits['reset']
    reset_timestamp_local = localize_reset_timestamp(limit_reset_timestamp)

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
get_and_print_local_time()
# Get the end time and calculate the duration
end_time = get_current_time()
print()
formatted_time = format_time_difference(start_time, end_time)
print(f"The operation took {formatted_time}")
print()
sys.stdout.flush()  # Force flush the output