import customtkinter as ctk
from tkinter import filedialog
from tkinter import messagebox
from threading import Thread
import datetime
import requests
import psutil
from datetime import datetime  # Import the datetime class
import subprocess  # Add this line to import subprocess module
import sys  # for the window scrolling

from utils.helpers import load_config_new, save_config_new, ConfigManager
from utils.sync import main_sync
from utils.download_repo import download_repo_main

# CustomTkinter appearance settings
ctk.set_appearance_mode("System")  # Options: "System", "Dark", "Light"
ctk.set_default_color_theme("blue")  # Options: "blue", "green", "dark-blue"

app_version = "0.25-beta"
app_version_num = 0.25

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

class DebugModeMixin:
    def toggle_debug_mode(self):
        debug_mode = self.debug_mode_var.get()
        save_config_new({'debug_mode': debug_mode})


class OnSaveButtonClickMixin:
    def on_save_button_click(self, config_dict, button, master):
        for variable_name, entry_widget in config_dict.items():
            # Get the value from the Entry widget
            value_to_save = entry_widget.get()

            # Special case for initial_setup_var: Convert to boolean
            if variable_name == "initial_setup_done":
                value_to_save = value_to_save.lower() == "true"

            # Call save_config_new with the value and variable name
            save_config_new({variable_name: value_to_save})

        # Reload the configuration
        config = load_config_new()

        # Destroy the LOCAL DIRECTORY PATH warning/instructions label if exists and local_directory has a value
        if hasattr(self, 'path_to_replacements_label') and self.path_to_replacements_label and config.get("local_directory"):
            self.path_to_replacements_label.destroy()

        # Destroy the GITHUB TOKEN warning/instructions label if exists and github_token has a value
        if hasattr(self, 'github_token_label') and self.github_token_label and config.get("github_token"):
            self.github_token_label.destroy()

        # Update the button text and color
        button.configure(text="Saved! (restart app)", text_color="green")

        # Schedule the reversion after 5000 milliseconds (5 seconds)
        master.after(5000, lambda: button.configure(text="Save Config", text_color=("black", "white")))





class PostInstallScreen(ctk.CTkFrame, DebugModeMixin, OnSaveButtonClickMixin):
    def __init__(self, master, switch_func):
        super().__init__(master, fg_color="transparent")
        self.config_manager = ConfigManager()

        # Get the root window to set the title
        root = self.winfo_toplevel()
        root.title(f"{project_name} Textures Updater {app_version}")

        # Initialize UI components
        self.debug_mode_var = ctk.BooleanVar(value=self.config_manager.debug_mode)

        heading_label = ctk.CTkLabel(self, text=f"{project_name} Textures Updater", font=ctk.CTkFont(size=20, weight="bold"))
        heading_label.grid(row=0, column=0, columnspan=3, pady=(10, 10))

        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=1)
        self.columnconfigure(2, weight=1)

        ctk.CTkLabel(self, text="Path to PCSX2\\textures:", justify="left").grid(row=1, column=0, sticky="e", padx=(20, 0), pady=2)
        self.local_directory_entry = ctk.CTkEntry(self, width=400, placeholder_text="Enter path to textures folder...")
        self.local_directory_entry.grid(row=1, column=1, columnspan=2, sticky="ew", padx=(10, 20), pady=2)
        self.local_directory_entry.insert(0, self.config_manager.local_directory)

        self.path_to_replacements_label = ctk.CTkLabel(self, text=f"Enter the full path to your emulator's TEXTURES FOLDER and click Save Config. Find this in PCSX2 > Settings > Graphics > Texture Replacements. Copy that path exactly as-is. Example: C:\\Whatever\\PCSX2\\textures", font=ctk.CTkFont(size=12), text_color="red", justify="left", wraplength=530)
        if not self.config_manager.local_directory:
            self.path_to_replacements_label.grid(row=2, column=1, columnspan=2, pady=(0, 5), padx=(20, 0), sticky="w")

        ctk.CTkLabel(self, text="GitHub API Token:", justify="left").grid(row=3, column=0, sticky="e", pady=2)
        self.github_token_entry = ctk.CTkEntry(self, width=250, placeholder_text="Enter GitHub token...")
        self.github_token_entry.grid(row=3, column=1, sticky="w", padx=(10, 20), pady=2)
        self.github_token_entry.insert(0, self.config_manager.github_token)

        self.github_token_label = ctk.CTkLabel(self, text=f"Log in to Github.com and go to Settings > Developer Settings > Personal Access Tokens", font=ctk.CTkFont(size=11), text_color="red", justify="left", wraplength=250)
        if not self.config_manager.github_token:
            self.github_token_label.grid(row=4, column=1, columnspan=2, pady=(0, 5), padx=(20, 0), sticky="w")

        last_run_date_label = ctk.CTkLabel(self, text="Last Sync Date:", justify="right")
        last_run_date_label.grid(row=5, column=0, sticky="e", pady=2)
        self.last_run_date_entry = ctk.CTkEntry(self, width=250, placeholder_text="Last sync date...")
        self.last_run_date_entry.grid(row=5, column=1, sticky="w", padx=(10, 20), pady=2)

        last_run_date = self.config_manager.last_run_date
        if last_run_date:
            try:
                self.last_run_date_entry.insert(0, last_run_date.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3])
            except ValueError:
                default_last_run_date = datetime(2005, 7, 11, 0, 0, 0)
                self.last_run_date_entry.insert(0, default_last_run_date.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3])
                save_config_new({'last_run_date': default_last_run_date.strftime('%Y-%m-%d %H:%M:%S.%f')})
        else:
            default_last_run_date = datetime(2005, 7, 11, 0, 0, 0)
            self.last_run_date_entry.insert(0, default_last_run_date.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3])
            save_config_new({'last_run_date': default_last_run_date.strftime('%Y-%m-%d %H:%M:%S.%f')})

        initial_setup_var = ctk.StringVar(value="False")  # Set the initial value as needed

        config_dict_main = {
            "local_directory": self.local_directory_entry,
            "github_token": self.github_token_entry,
            "last_run_date": self.last_run_date_entry,
        }
        save_button_on_main = ctk.CTkButton(self, text="Save Configuration", command=lambda: self.on_save_button_click(config_dict_main, save_button_on_main, self), width=150, cursor="hand2")
        save_button_on_main.grid(row=3, column=2, rowspan=4, pady=20, padx=(0, 60))

        # Separator (CTk doesn't have separator, use thin frame)
        separator = ctk.CTkFrame(self, height=2, fg_color="gray50")
        separator.grid(row=7, column=0, columnspan=3, pady=5, sticky="ew")

        ctk.CTkLabel(self, text="Would you like to only check for files in Github that are new or have changed\nsince your last sync date or would you like to do a full sync of the entire repo?", font=ctk.CTkFont(size=13, weight="bold")).grid(row=8, column=0, columnspan=3, pady=(5, 5))

        radio_buttons = ctk.CTkFrame(self, fg_color="transparent")
        radio_buttons.grid(row=9, column=0, columnspan=3, pady=(3, 5), padx=(0, 0), sticky="n")

        self.user_choice_var = ctk.IntVar(value=1)
        ctk.CTkRadioButton(radio_buttons, text="Download New Content (recommended)", variable=self.user_choice_var, value=1).grid(row=0, column=0, sticky="e", padx=(0, 10))
        ctk.CTkRadioButton(radio_buttons, text="Full Sync (slower, but can fix issues)", variable=self.user_choice_var, value=2).grid(row=0, column=1, sticky="w", padx=(50, 0))

        # Terminal output (using CTkTextbox with built-in scrollbar)
        self.terminal_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.terminal_text = ctk.CTkTextbox(self.terminal_frame, height=300, width=800, wrap="word", font=ctk.CTkFont(family="Courier", size=12))
        self.terminal_text.pack(fill="both", expand=True, padx=10, pady=10)
        self.terminal_frame.grid(row=11, column=0, columnspan=3, padx=10, pady=10, sticky="nsew")

       
        

        ctk.CTkLabel(self, text="PUT ALL OF YOUR CUSTOM TEXTURES AND DLC FILES\nIN 'user-customs' OR THEY WILL BE DELETED!", font=ctk.CTkFont(size=13, weight="bold"), text_color="red", justify="left").grid(row=12, column=0, columnspan=2, pady=(0, 0))
        ctk.CTkLabel(self, text="When using custom files, leave the default textures in place and\ndisable them by prepending the name with a dash (eg. '-file.png').", font=ctk.CTkFont(size=12), justify="left").grid(row=13, column=0, columnspan=2, padx=(20, 0), pady=(0, 5))

        def main_sync_wrapper():
            # Initialize sync running flag if it doesn't exist
            if not hasattr(self, '_sync_running'):
                self._sync_running = False

            # Check if sync is already running
            if self._sync_running:
                print("Sync already running, ignoring click")
                return

            print("Button clicked - starting sync")  # Debug print

            # Update UI state immediately
            self._sync_running = True
            self.update_idletasks()  # Force UI update
            self.sync_button.configure(state="disabled")
            self.update_idletasks()  # Force UI update

            # Get parameters before starting thread
            user_choice = "full_scan" if self.user_choice_var.get() == 2 else "only_new_content"
            github_token = self.github_token_entry.get()
            last_run_date = self.last_run_date_entry.get()

            # Clear terminal
            self.terminal_text.delete("1.0", "end")
            self.update_idletasks()  # Force UI update

            def run_sync():
                try:
                    # Use after() to update UI from the thread
                    self.after(0, lambda: self.terminal_text.insert("end", "Starting sync...\n"))
                    main_sync(user_choice, self.terminal_text, github_token, last_run_date)
                except Exception as e:
                    self.after(0, lambda: self.terminal_text.insert("end", f"Error: {str(e)}\n"))
                finally:
                    # Reset UI state using after()
                    self.after(0, lambda: self.sync_button.configure(state="normal"))
                    self._sync_running = False

            # Start thread as daemon
            thread = Thread(target=run_sync, daemon=True)
            thread.start()

        # Sync button (replaces canvas-based button)
        self.sync_button = ctk.CTkButton(
            self,
            text="Run Sync",
            font=ctk.CTkFont(size=16, weight="bold"),
            width=150,
            height=40,
            corner_radius=10,
            command=main_sync_wrapper
        )
        self.sync_button.grid(row=12, column=2, rowspan=2, sticky="w", pady=(0, 0))
        # macOS fix: bind ButtonRelease as backup for clicks that don't register
        self.sync_button.bind("<ButtonRelease-1>", lambda e: main_sync_wrapper() if self.sync_button.cget("state") == "normal" else None)




        # Divider
        separator2 = ctk.CTkFrame(self, height=2, fg_color="gray50")
        separator2.grid(row=18, column=0, columnspan=3, pady=10, sticky="ew")

        # Debug mode checkbox
        debug_mode_checkbox = ctk.CTkCheckBox(
            self,
            text='Debug Mode',
            command=self.toggle_debug_mode,
            variable=self.debug_mode_var,
            onvalue=True,
            offvalue=False
        )
        debug_mode_checkbox.grid(row=19, column=0, padx=(20, 5), pady=(0, 10), sticky="w")

        # Go to new install screen
        link_label = ctk.CTkLabel(self, text="Fresh Install →", cursor="hand2", font=ctk.CTkFont(underline=True), text_color=("blue", "#5B9BD5"))
        link_label.grid(row=19, column=2, padx=(5, 20), pady=(0, 10), sticky="e")
        # Bind the label to the function that should be executed on click
        link_label.bind("<Button-1>", lambda event: switch_func())

        try:
            # Fetch the JSON data from the URL
            json_url = self.config_manager.json_url
            response = requests.get(json_url)
            response.raise_for_status()

            # Parse the JSON data
            json_data = response.json()

            # About this release
            version = json_data.get("version", "?")
            release_date = json_data.get("release_date", "Date Unknown")
            release_url = json_data.get("release_url", "")
            total_size_gb = json_data.get("total_size", "? GB")
            largest_size_gb = json_data.get("temp_size", "? GB")
            min_version = json_data.get("min_downloader_app_version", "")
            downloader_app_url = json_data.get("downloader_app_url", "")

            # For the warning text if downloader_app_url is not null or empty
            if downloader_app_url:
                downloader_url_string = f" at {downloader_app_url}"
            else:
                downloader_url_string = "."  


            # Compare app_version_num with min_version
            if app_version_num >= min_version:
                self.terminal_text.insert("end", f"\n\n")
                self.terminal_text.insert("end", "!!! ATTENTION !!! This Run Sync tool is only intended to be used for updates AFTER you have completed the initial installation. If you are attempting to do a first-time download/install of the textures pack, click the 'Fresh Install' button at the bottom right of this screen.\n")
                self.terminal_text.insert("end", f"\n\n")
                self.terminal_text.insert("end", f"Internet connection test passed. Remote JSON data retrieved. Ready to proceed.")
                self.terminal_text.insert("end", f"\n\n")
                self.terminal_text.see("end")  # Scroll to the end
                self.update()
            else:
                self.terminal_text.insert("end", f"!!! App version {app_version_num} is out of date (< {min_version}). Please update to latest version release{downloader_url_string}")
                self.terminal_text.insert("end", f"\n\n")
                # Disable the sync button for outdated app version
                self.sync_button.configure(state="disabled")

        except Exception as e:
            self.terminal_text.insert("end", f"Error fetching remote JSON data (debug info: {str(e)})")
            self.terminal_text.insert("end", f"\n\n")
            self.terminal_text.see("end")  # Scroll to the end
            self.update()
            # About this release
            version = "?"
            release_date = "Date Unknown"
            release_url = "#"
            total_size_gb = "? GB"
            largest_size_gb = "? GB"

    def on_save_button_click(self, config_dict, button, master):
        # Call the mixin's on_save_button_click method
        super().on_save_button_click(config_dict, button, master)
        config_manager = ConfigManager()
        # Access configuration variables
        debug_mode = config_manager.debug_mode
        initial_setup_done = config_manager.initial_setup_done
        local_directory = config_manager.local_directory
        github_token = config_manager.github_token
        last_run_date = config_manager.last_run_date
        self.terminal_text.delete("1.0", "end")
        self.terminal_text.insert("end", "\n\nVariables updated. RESTART THE APP TO APPLY.\n\n")
        self.terminal_text.see("end")





class InstallerScreen(ctk.CTkFrame, DebugModeMixin, OnSaveButtonClickMixin):
    def __init__(self, master, switch_func):
        super().__init__(master, fg_color="transparent")
        self.config_manager = ConfigManager()

        # Get the root window to set the title
        root = self.winfo_toplevel()
        root.title(f"{project_name} Textures Installer {app_version}")

        # Configure frame columns properly
        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=1)
        self.columnconfigure(2, weight=1)

        # Create a boolean variable to store the checkbox state of debug_mode
        self.debug_mode_var = ctk.BooleanVar(value=self.config_manager.debug_mode)

        def open_hyperlink(event):
            import webbrowser
            webbrowser.open(release_url)

        def get_free_disk_space(directory="/"):
            try:
                disk_info = psutil.disk_usage(directory)
                free_space_gb = disk_info.free / (1024 ** 3)  # Convert bytes to gigabytes
                return free_space_gb
            except PermissionError:
                # Handle permission error gracefully
                print(f"Permission error: Unable to access disk space information for {directory}")
                return None

        def run_installer():
            user_choice = "whatever"
            run_subprocess('utils/download_repo.py', user_choice, self.terminal_text, self.master)  

            



        # Terminal output (using CTkTextbox with built-in scrollbar)
        self.terminal_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.terminal_text = ctk.CTkTextbox(self.terminal_frame, height=260, width=800, wrap="word", font=ctk.CTkFont(family="Courier", size=12))
        self.terminal_text.pack(fill="both", expand=True, padx=10, pady=10)
        self.terminal_frame.grid(row=8, column=0, columnspan=3, padx=10, pady=10, sticky="nsew")

        
        try:
            # Fetch the JSON data from the URL
            json_url = self.config_manager.json_url
            response = requests.get(json_url)
            response.raise_for_status()

            # Parse the JSON data
            json_data = response.json()

            # About this release
            version = json_data.get("version", "?")
            release_date = json_data.get("release_date", "Date Unknown")
            release_url = json_data.get("release_url", "")
            total_size_gb = json_data.get("total_size", "? GB")
            largest_size_gb = json_data.get("temp_size", "? GB")
            min_version = json_data.get("min_downloader_app_version", "")
            downloader_app_url = json_data.get("downloader_app_url", "")

            # For the warning text if downloader_app_url is not null or empty
            if downloader_app_url:
                downloader_url_string = f" at {downloader_app_url}"
            else:
                downloader_url_string = "."  

            # Compare app_version_num with min_version
            if app_version_num >= min_version:
                self.terminal_text.insert("end", f"\n\n")
                self.terminal_text.insert("end", f"!!! FOR 1st INSTALL ONLY. ATTENTION !!! This screen is only for installing the textures for the first time. If you already have the textures installed, to update them, click the 'Post-Install Updater' button at the bottom right of this page.")
                self.terminal_text.insert("end", f"\n\n")
                self.terminal_text.insert("end", f"Internet connection test passed. Remote JSON data retrieved. Ready to proceed.")
                self.terminal_text.see("end")  # Scroll to the end
                self.update()
            else:
                self.terminal_text.insert("end", f"!!! App version {app_version_num} is out of date (< {min_version}). Please update to latest version release{downloader_url_string}")
                self.terminal_text.insert("end", f"\n\n")

        except Exception as e:
            self.terminal_text.insert("end", f"Error fetching remote JSON data (debug info: {str(e)})")
            self.terminal_text.see("end")  # Scroll to the end
            self.update()
            # About this release
            version = "?"
            release_date = "Date Unknown"
            release_url = "#"
            total_size_gb = "? GB"
            largest_size_gb = "? GB"

        # Heading
        heading_label = ctk.CTkLabel(self, text="First Time Setup – Textures Installation", font=ctk.CTkFont(size=20, weight="bold"), justify="center")
        heading_label.grid(row=0, column=0, columnspan=3, pady=(10, 0))
        # Subheading
        subheading_label = ctk.CTkLabel(self, text=f"{project_name} Version {version} • {release_date}", font=ctk.CTkFont(size=12))
        subheading_label.grid(row=1, column=0, columnspan=3, pady=(0, 5))

        # Create a hyperlink label
        hyperlink_label = ctk.CTkLabel(self, text="View Release Notes and Instructions", font=ctk.CTkFont(size=11, underline=True), cursor="hand2", text_color=("blue", "#5B9BD5"))
        hyperlink_label.grid(row=2, column=0, columnspan=3, pady=(0, 10))

        # Bind the label to the callback function
        hyperlink_label.bind("<Button-1>", open_hyperlink)

        # Body copy
        description_text = "This will download and install all of the required textures for this mod. This could take up to a few hours."
        description = ctk.CTkLabel(self, text=description_text, justify="left", wraplength=750)
        description.grid(row=3, column=0, columnspan=3, pady=(0, 10))

        # Path to Replacements
        ctk.CTkLabel(self, text="Enter the full path to your emulator's TEXTURES FOLDER and Github Token, click Save Config, and restart this app.", font=ctk.CTkFont(size=13, weight="bold"), justify="center").grid(row=4, column=0, columnspan=3, sticky="n", padx=(0, 0))
        ctk.CTkLabel(self, text="Find this in PCSX2 > Settings > Graphics > Texture Replacements.", font=ctk.CTkFont(size=13), justify="center").grid(row=5, column=0, columnspan=3, sticky="n", padx=(0, 0))
        

        # Create a frame for input and button
        input_frame = ctk.CTkFrame(self, fg_color="transparent")
        input_frame.grid(row=7, columnspan=3, column=0, pady=(3, 10), padx=(0, 0), sticky="nsew")

        input_frame.grid_columnconfigure(0, weight=1)
        input_frame.grid_columnconfigure(1, weight=1)
        input_frame.grid_columnconfigure(2, weight=1)
        input_frame.grid_columnconfigure(3, weight=1)

        # Local Directory / Path to Textures
        ctk.CTkLabel(input_frame, text="Full Path to Textures Folder:", font=ctk.CTkFont(size=13, weight="bold"), justify="left").grid(row=0, column=0, columnspan=1, sticky="w", padx=(20, 0), pady=3)
        local_directory_entry_first = ctk.CTkEntry(input_frame, width=400, placeholder_text="Enter path to textures folder...")
        local_directory_entry_first.grid(row=0, column=1, columnspan=3, sticky="nsew", padx=(5, 0))
        local_directory_entry_first.insert(0, local_directory)

        # Check if Path to Textures is provided in the config file
        self.path_to_replacements_label = ctk.CTkLabel(input_frame, text=f"Enter the full path to TEXTURES FOLDER. Example: C:\\PCSX2\\textures", font=ctk.CTkFont(size=12), text_color="red", justify="left", wraplength=450)
        if not local_directory:
            self.path_to_replacements_label.grid(row=1, column=1, columnspan=2, pady=(0, 10), padx=(5, 0), sticky="w")

        # Github Token
        ctk.CTkLabel(input_frame, text="Github Personal Access Token:", font=ctk.CTkFont(size=13, weight="bold"), justify="left").grid(row=2, column=0, columnspan=1, sticky="w", padx=(20, 0), pady=3)
        github_token_entry = ctk.CTkEntry(input_frame, width=400, placeholder_text="Enter GitHub token...")
        github_token_entry.grid(row=2, column=1, columnspan=3, sticky="nsew", padx=(5, 0))
        github_token_entry.insert(0, github_token)

        # Check if Github Token is provided in the config file
        self.github_token_label = ctk.CTkLabel(input_frame, text=f"An API token is required. Log in (or create a free account) to Github.com and go to (profile pic at top right) > Settings > Developer Settings > Personal Access Tokens.", font=ctk.CTkFont(size=11), text_color="red", justify="left", wraplength=450)
        if not github_token:
            self.github_token_label.grid(row=3, column=1, columnspan=2, pady=(0, 0), padx=(5, 0), sticky="w")

        # Create a StringVar for initial_setup_done because it doesn't have an entry field
        initial_setup_var = ctk.StringVar(value="False")  # Set the initial value as needed

        # Save Button Next to Input Field
        config_dict = {"local_directory": local_directory_entry_first, "github_token": github_token_entry}
        save_button_next_to_input = ctk.CTkButton(input_frame, text="Save Config", command=lambda: self.on_save_button_click(config_dict, save_button_next_to_input, self), width=100, cursor="hand2")
        save_button_next_to_input.grid(row=0, column=4, rowspan=4, pady=(0, 3), padx=(5, 25), sticky="w")


        # Create a frame for the buttons
        button_frame = ctk.CTkFrame(self, fg_color="transparent")
        button_frame.grid(row=9, columnspan=3, column=0, pady=(0, 10))

        try:
            # Function to get the color based on free disk space
            def get_text_color():
                free_space = get_free_disk_space()
                if free_space is not None:
                    return "green" if free_space > total_size_gb else "red"
                return ("black", "white")  # Default color (light, dark)

            # Display the "Requires <total_dl_size> GB free disk space" message
            if get_free_disk_space() is not None:
                requirement_label = ctk.CTkLabel(button_frame, text=f"Requires {total_size_gb:.2f} GB free disk space (including {largest_size_gb:.2f} GB of temporary space)\nYou have {get_free_disk_space():.2f} GB free.")
            else:
                requirement_label = ctk.CTkLabel(button_frame, text=f"Requires {total_size_gb:.2f} GB free disk space (including {largest_size_gb:.2f} GB of temporary space).")

            # Get the text color based on free disk space
            text_color = get_text_color()

            # Apply the text color to the label
            requirement_label.grid(row=0, column=0)
            requirement_label.configure(text_color=text_color)

            def download_repo_main_wrapper():
                self.terminal_text.delete("1.0", "end")
                thread = Thread(target=download_repo_main, args=(json_url, local_directory, slus_folder, self.terminal_text))
                thread.start()

            download_button = ctk.CTkButton(
                button_frame,
                text="Begin Installation",
                command=download_repo_main_wrapper,
                cursor="hand2",
                width=200,
                height=50,
                font=ctk.CTkFont(size=15, weight="bold")
            )
            download_button.grid(row=1, column=0)

            # Display a message and disable the button based on the text_color
            if text_color == "red":
                message = "Not enough free disk space to proceed."
                if debug_mode == False:
                    download_button.configure(state="disabled")
            elif text_color == "green":
                message = "You have enough disk space. Do you have the time to let this run?"
                download_button.configure(state="normal")  # Ensure the button is enabled
            else:
                message = "Error determining free disk space."

            # Display the message below the button
            message_label = ctk.CTkLabel(button_frame, text=message)
            message_label.grid(row=2, column=0, pady=(5, 5))

            # Divider
            separator = ctk.CTkFrame(self, height=2, fg_color="gray50")
            separator.grid(row=10, column=0, columnspan=3, pady=5, sticky="ew")

            # Debug mode checkbox
            debug_mode_checkbox = ctk.CTkCheckBox(
                self,
                text='Debug Mode',
                command=self.toggle_debug_mode,
                variable=self.debug_mode_var,
                onvalue=True,
                offvalue=False
            )
            debug_mode_checkbox.grid(row=11, column=0, padx=(20, 5), pady=(5, 20), sticky="w")

            # Go to post-install updater screen
            link_label = ctk.CTkLabel(self, text="Post-Install Updater →", cursor="hand2", font=ctk.CTkFont(underline=True), text_color=("blue", "#5B9BD5"))
            link_label.grid(row=11, column=2, padx=(5, 20), pady=(5, 20), sticky="e")
            # Bind the label to the function that should be executed on click
            link_label.bind("<Button-1>", lambda event: switch_func())

        except Exception as e:
            self.terminal_text.insert("end", f"Error (debug info: {str(e)})")
            self.terminal_text.see("end")  # Scroll to the end
            self.update()



        # Disable the button if the app version is lower than minimum required version per the json
        if app_version_num < min_version:
            if debug_mode == False:
                download_button.configure(state="disabled")

    def on_save_button_click(self, config_dict, button, master):
        # Call the mixin's on_save_button_click method
        super().on_save_button_click(config_dict, button, master)
        self.terminal_text.delete("1.0", "end")
        self.terminal_text.insert("end", "\n\nVariables updated. RESTART THE APP TO APPLY.\n\n")
        self.terminal_text.see("end")
  




class MainApplication(ctk.CTk):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Set initial size
        self.geometry("1080x870")
        self.minsize(400, 300)  # Allow smaller window sizes

        # Configure main window grid
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # Create scrollable main container with both horizontal and vertical scrolling
        self.scrollable_frame = ctk.CTkScrollableFrame(self, orientation="vertical")
        self.scrollable_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

        # Configure scrollable frame grid
        self.scrollable_frame.grid_columnconfigure(0, weight=1)

        # Initialize current_frame
        self.current_frame = None

        # Load initial frame
        if not initial_setup_done:
            self.switch_frame(InstallerScreen)
        else:
            self.switch_frame(PostInstallScreen)

    def switch_frame(self, frame_class):
        """Switch displayed frame."""
        new_frame = frame_class(self.scrollable_frame,
                              lambda: self.switch_frame(PostInstallScreen if frame_class == InstallerScreen else InstallerScreen))

        if self.current_frame:
            self.current_frame.destroy()  # Destroy the current frame

        self.current_frame = new_frame
        self.current_frame.grid(row=0, column=0, sticky="nsew")


if __name__ == "__main__":
    app = MainApplication()
    app.mainloop()