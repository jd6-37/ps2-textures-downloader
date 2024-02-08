import os
import sys
import shutil
import aiohttp
import asyncio
from tenacity import retry, wait_fixed, stop_after_attempt 
import zipfile
import requests
from datetime import datetime, timezone, timedelta
import time
import pytz

# Import functions
from helpers import ConfigManager, check_rate_limits, localize_reset_timestamp, get_and_print_local_time

# Number of concurrent downloads
semaphore = asyncio.Semaphore(2) 

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

# Other variables
github_repo_url = f"{owner}/{repo}"
api_url = f"https://api.github.com/repos/{github_repo_url}/commits?sha={branch_name}"
headers = {"Authorization": f"Bearer {github_token}"}


if debug_mode == 'True':
    print()
    print(github_repo_url)
    print()
    print(api_url)
    print()
    print(headers)
    print()
    print()
# Function to grab a list of directories inside a particular directory
def get_subdirectory_names(api_url, headers, local_directory, subdirectory):
    selected_directories = []
    content_url = f"https://api.github.com/repos/{github_repo_url}/contents/{subdirectory}?ref={branch_name}"
    if debug_mode == 'True':
        print()
        print(content_url)
        print()
    content_response = requests.get(content_url, headers=headers)
    if debug_mode == 'True':
        print()
        print(content_response)
        print()

    if content_response.status_code == 200:
        content_data = content_response.json()
        for item in content_data:
            if item['type'] == 'dir':
                directory_name = item['name']
                selected_directories.append(f"{subdirectory}/{directory_name}")
    else:
        print(f"get_subdirectory_names failed for {subdirectory}")
        sys.stdout.flush() 

    return selected_directories

# Define a queue to store zip file names
zip_queue = asyncio.Queue()

async def process_zip_queue(local_directory):
    while True:
        # Get the next zip file from the queue
        zip_file_path = await zip_queue.get()

        # Break the loop if the sentinel is encountered
        if zip_file_path is None:
            break

        # Unzip the file after writing all contents
        unzip_file(local_directory, zip_file_path)

        # Mark the task as done
        zip_queue.task_done()


async def download_repo_split_async(api_url, headers, local_directory, selected_directories, progress_printer):
    async with aiohttp.ClientSession() as session:
        tasks = [download_subdirectory_async(session, api_url, headers, local_directory, directory, progress_printer) for directory in selected_directories]
        await asyncio.gather(*tasks)

async def download_subdirectory_async(session, api_url, headers, local_directory, subdirectory, progress_printer):
    content_url = f"https://api.github.com/repos/{github_repo_url}/contents/{subdirectory}?ref={branch_name}"

    async with semaphore:
        async with session.get(content_url, headers=headers, timeout=300) as content_response:
            subdirectory_trimmed = subdirectory.removeprefix(f"textures/{slus_folder}/replacements/")
            try:
                if content_response.status == 200:
                    zip_file_path = os.path.join(local_directory, f"{subdirectory.replace('/', '_')}.zip")
                    content_data = await content_response.json()

                    total_files = len(content_data)
                    files_downloaded = 0

                    print(f"Downloading next zip ({subdirectory_trimmed})...")
                    sys.stdout.flush() 

                    with zipfile.ZipFile(zip_file_path, 'w') as zip_file:
                        for item in content_data:
                            await download_item_async(api_url, headers, local_directory, subdirectory, item, zip_file)
                            files_downloaded += 1

                            # Print progress message every 5 seconds
                            if files_downloaded % 5 == 0:
                                progress_printer(subdirectory_trimmed, files_downloaded, total_files)
                                await asyncio.sleep(5)  # Sleep for 5 seconds

                    print(f"Finished zip ({subdirectory_trimmed}) - {files_downloaded}/{total_files} items. Extracting...")
                    sys.stdout.flush() 

                    # Unzip the file after writing all contents
                    unzip_file(local_directory, zip_file_path)
                else:
                    print(f"Failed to get content information: {content_response.status}")
                    sys.stdout.flush() 

            except Exception as e:
                print(f"Error downloading subdirectory: {e}")
                sys.stdout.flush() 
                raise e

@retry(wait=wait_fixed(2), stop=stop_after_attempt(3))  # Retry every 2 seconds, stop after 3 attempts
async def download_item_async(api_url, headers, local_directory, subdirectory, item, zip_file):
    try:
        if item['type'] == 'file':
            file_path = item['path']
            content_url = f"https://raw.githubusercontent.com/{github_repo_url}/{branch_name}/{file_path}"

            async with aiohttp.ClientSession() as session:
                async with session.get(content_url, headers=headers, timeout=300) as content_response:
                    if content_response.status == 200:
                        relative_path = os.path.relpath(file_path, subdirectory)
                        zip_file.writestr(os.path.join(subdirectory, relative_path), await content_response.content.read())
                    else:
                        print(f"Failed to get file content: {content_response.status}")
                        sys.stdout.flush() 

        elif item['type'] == 'dir':
            subdir_path = item['path']
            content_url = f"https://api.github.com/repos/{github_repo_url}/contents/{subdir_path}?ref={branch_name}"

            async with aiohttp.ClientSession() as session:
                async with session.get(content_url, headers=headers, timeout=300) as content_response:
                    if content_response.status == 200:
                        content_data = await content_response.json()
                        for sub_item in content_data:
                            await download_item_async(api_url, headers, local_directory, subdir_path, sub_item, zip_file)

    except Exception as e:
        print(f"Error downloading item: {e}")
        sys.stdout.flush() 
        raise e


def unzip_file(directory, zip_file_path):
    max_retries = 5
    retry_delay = 2  # seconds

    for _ in range(max_retries):
        try:
            with zipfile.ZipFile(zip_file_path, 'r') as zip_ref:
                zip_ref.extractall(directory)
            
            # Attempt to remove the file
            os.remove(zip_file_path)
            print("Extracted. Deleting zip.")
            sys.stdout.flush()
            break  # If successful, exit the loop
        except PermissionError as e:
            print(f"PermissionError: {e}. Retrying after {retry_delay} seconds...")
            time.sleep(retry_delay)
    else:
        # If the loop completes without a successful extraction and removal, raise an exception
        raise RuntimeError(f"Unable to extract and remove file: {zip_file_path}")


# Function to print progress messages
def progress_printer(subdirectory, files_downloaded, total_files):
    print(f"Status update for the zip file ({subdirectory}): {files_downloaded} of {total_files} items.")
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



try:
    # Fetch the JSON data from the URL
    json_url = json_url
    response = requests.get(json_url)
    response.raise_for_status()

    # Parse the JSON data
    json_data = response.json()

    release_url = json_data.get("release_url")
    
    # Initialize the list of directories to grab as zip files
    selected_directories = []
    
    # Grab the list of directories to download as a single zip
    download_complete = json_data.get("download_complete")
    # Grab the list of directories for which the subdirectories should be downloaded as individual zips
    download_subdirectories = json_data.get("download_subdirectories")

    # Add the complete directories list to the array
    selected_directories.extend(download_complete)

    # Add the subdirectories list to the array
    for item in download_subdirectories:
        selected_directories.extend(get_subdirectory_names(api_url, headers, local_directory, item))


except Exception as e:
    # print(f"Error fetching JSON data: {str(e)}")
    print("Error fetching remote JSON data (debug info: {str(e)})")
    sys.stdout.flush()


# Create output directory if not exists
os.makedirs(local_directory, exist_ok=True)


# Check if the SLUS folder exists
slus_folder_path = os.path.join(local_directory, slus_folder)
if os.path.exists(slus_folder_path) and os.path.isdir(slus_folder_path):
    print()
    print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
    print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
    print("!                                                                   !")
    print("!                 !!! ------- WARNING ----- !!!                     !")
    print("!                                                                   !")
    print(f"!   A '{slus_folder}' FOLDER ALREADY EXISTS IN YOUR TEXTURES FOLDER!   !")
    print("!         Are you sure this is your first installation?             !")
    print("!                                                                   !")
    print("!               To proceed with this installation,                  !")
    print(f"!      rename or remove the {slus_folder} folder and try again.        !")
    print("!      Alternatively, you may use the post-install updater.         !")
    print("!                                                                   !")
    print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
    print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
    print()
    print("Terminating installation. Hasta la vista, baby.")
    sys.stdout.flush() 
    sys.exit(1) 



# Get the current time in UTC timezone
utc_now = datetime.utcnow()
utc_now = utc_now.replace(tzinfo=pytz.utc)

# Format the time as a string
formatted_time = utc_now.strftime("%Y-%m-%d %H:%M:%S %Z")

# Print the current time in UTC
print("Current time in UTC:", formatted_time)




print()   
print()   
print("#####################################################################")
print("#                                                                   #")
print(f"#                 {project_name} Textures Installer                 ")
print("#                                                                   #")
print("#####################################################################")
print()   
print(f"Beginning initial installation of the {project_name} mod textures...")
print()   
print("HEADS UP: This is a huge download, broken down into chunks. Be patient")
print("and leave this window open. You can leave it running in the background,")
print("but if you close this window, it will terminate the installation.")
print()
print("NOTE: The folders in replacements will be reorganized at the very end. ")   
print()
sys.stdout.flush() 

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
    sys.stdout.flush() 
else:
    print()
    print("Unable to retrieve rate limits.")
    print()
    sys.stdout.flush() 

# Run the background task for progress messages
loop = asyncio.get_event_loop()
download_task = loop.create_task(download_repo_split_async(api_url, headers, local_directory, selected_directories, progress_printer))

# Start the task for processing the zip file queue
zip_processing_task = loop.create_task(process_zip_queue(local_directory))

# Run the event loop until the task is complete
loop.run_until_complete(download_task)

# Add sentinel to the queue
loop.run_until_complete(zip_queue.put(None))

# Wait for the zip processing task to complete before closing the event loop
loop.run_until_complete(zip_processing_task)

# Close the event loop
loop.close()

# Get rid of the nested "textures" folder
def move_and_delete_folders(local_directory):
    # Define the paths
    textures_path = os.path.join(local_directory, "textures")
    slus_path = os.path.join(textures_path, slus_folder)

    # Check if the "textures" folder exists
    if os.path.exists(textures_path) and os.path.isdir(textures_path):
        # Move SLUS folder up one level
        shutil.move(slus_path, local_directory)

        # Remove the "textures" folder
        shutil.rmtree(textures_path)

        print("Folders organized in the textures directory.")
    else:
        print(f"Error: Tried to reorganize the folder but something went wrong. Be sure the mod textures are in (your_emulator_folder)/textures/{slus_folder}replacements.")

# Get rid of the nested "textures" folder
move_and_delete_folders(local_directory)

print()   
print()   
print("#-------------------------------------------------------------------#")
print("#                                                                   #")
print("#                  TEXTURES INSTALLATION DONE!                      #")
print("#                                                                   #")
print("#      Don't forget to make your modded ISO with ImgBurn. ;)        #")
print("#                                                                   #")
print("#      It's recommended you run the Full Sync option in the         #")
print("#   Textures Updater utility now for a deep inspection that will    #")
print("#   ensure every file was downloaded and extracted without issue.   #")
print("#   This shouldn't be necessary, but it can solve issues caused by  #")
print("#        spotty internet connection or corrupted Zip files.         #")
print("#                                                                   #")
print("#####################################################################")

# Get the current time in UTC timezone
utc_now = datetime.utcnow()
utc_now = utc_now.replace(tzinfo=pytz.utc)

# Format the time as a string
formatted_time = utc_now.strftime("%Y-%m-%d %H:%M:%S %Z")

# Print the current time in UTC
print("\nCurrent time in UTC:", formatted_time)

sys.stdout.flush() 