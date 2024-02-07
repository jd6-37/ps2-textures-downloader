# Installer/Updater Tool for PS2 Mods' Replacement Textures 

## Table of Contents
- [Overview](#introduction)
  - [Mod Installer](#introduction--installer)
  - [Mod Updater](#introduction--updater)
- [Handling User-Custom Textures](#custom-textures)
- [Installation](#installation)
  - [Option 1: EXE](#installation--exe)
  - [Option 2: Python Source](#installation--python)
- [Forking and Using for Your Project](#forking)
- [License](#license)

<br>

## Introduction <a name="introduction"></a>

This is a companion app for PS2 mod projects like the [NCAA NEXT mod](https://www.ncaanext.com). Mods like NCAA NEXT require downloading and keeping up-to-date what is often a very large (multi-GB) pack of replacement texture files. These files are how the mod team is able to upscale PS2 games to 4K and, for example, change in the game a football team's uniforms from the game's original visuals to the current real life uniforms.

For users of the mod, downloading multi-GB zip files and keeping things updated to the most recent version can be a chore. That's where this application comes in. It is, essentially, two utilities in one:

1. An INSTALLER for the first-time download and setup
2. An UPDATER - a download/sync tool for post-installation updates

#### MOD INSTALLER <a name="introduction--installer"></a>

The **installer** ("First Time Setup") breaks up the multi-GBs of files into multiple smaller zip files and downloads them individually (and automatically extracts them). If you download the source.zip directly from Github, it will come as a single massive zip file, which can cause issues of failed downloads and corrupted archives. Additionally, the installer will also put the textures in the proper location (after you point it to your emualator's textures folder - Eg. C:\PCSX2\textures).

#### MOD UPDATER <a name="introduction--updater"></a>

The **updater's "Download New Content"** sync allows for quickly grabbing the latest changes or additions to the project that have been published to Github. It is better than downloading a zip file of updates because A) it only downloads what you don't have (or don't have the latest version of), B) it's able to move/rename files instead of downloading them, and C) it's able to delete files that have been deleted from the project – something a zip download can never do. It does all of this by means of the Github API and is able to, essentially, follow along with the changes the team makes to the project. Also, it uses the same file hashing comparison that Git/Github uses to know if your local file is the same as the one in Github. This is much more accurate than other methods such as comparing modified dates. 

The **updater's "Full Sync"** sync does the same as above, but instead of looking at changes (Git commits) since your last sync date, it looks at the entire history of changes.

The **updater's "Deep Scan"** will identify stray files in your textures directory that may be causing issues. With PS2 texture replacement, no two files can have the same name anywhere across the the entire `replacements` folder or any of its subfolders. The file **names** are all that matter to the emulator. The emulator will use the first "file.png" it finds, and will ignore the rest of the files with that name. The Deep Scan compares the directory tree of the local installation versus that of the Github repository. If it finds any files/paths that exist locally but not in Github, it will offer to delete them. Using the Deep Scan combined with the Full Sync will ensure your local textures are perfectly in sync with the project's latest version and that there are no extraneous files that could cause issues.

<br>

## How it Handles User-Custom Textures <a name="custom-textures"></a>

One great thing about PS2 modding is that it's very easy for users to customize the textures for their own installation. For example, in the NCAA NEXT mod, a user can use the ESPN logo in the scorebug instead of the mod's default NCAA NEXT logo, or they can use a different helmet texture for their favorite team's home uniform. These changes are easy to make and only require the user puts the desired new texture into the `replacements` folder and rename or remove the mod's default replacement texture (because remember, no two textures can have the same name).

This app was built with this in mind! It has two special features that make it great for modders:

1. It completely ignores anything in the `user-customs` folder. Put all of your custom textures and/or DLC in this folder. The updater tool will never try to update or delete them.

2. It recognizes disabled textures (filenames prepended with a dash "-", Eg. `-file.png`) and won't try to download them again. It will even update the disabled/prepended file to the latest version!

**IMPORTANT**: To utilize these features you must A) **put all of your custom and DLC textures in the `user-customs` folder** (putting it anywhere else will result in it being deleted or changed to the mod default) and B) for every default mod texture for which you have a custom texture, **leave the default texture in place** (don't remove or move it) **AND prepend the filename name with a dash** to disable it. Eg. if it was named `3a30272f374c5d47.png`, change the name to `-3a30272f374c5d47.png`. Now, because it is not the specific filename that the emulator is looking for, it's disabled; it doesn't exist as far as the emulator can tell. However, the updater tools still knows exactly what it is!

<br>

## Installing and Using this App <a name="installation"></a>

To install and run the app, you have two options:

### Option 1: Windows Installer <a name="installation--exe"></a>

*This option is for forked repos that have been customized to work for a specific mod, and the team has created and published an EXE version of the app. There is no EXE for this base version of the app.*

Download the setup exe from the latest release and run it. Follow the installation prompts. You can save a shortcut to your desktop or run it from your Start menu like any other Windows application. 

NOTE: You will most likely be warned by Windows Defender about malware for two reasons: 1) the program used to convert the Python app to an EXE is commonly used by hackers, so Windows (as it should) flags these as potential risks, especially because 2) I created the app without a proper developers license (because it costs hundreds of dollars per year). So, if you're not comfortable installing and running the EXE, that's understandable. You can always run the Python source file directly as described in Option 2 below. And feel free to inspect the source code (or ask a programmer you trust to inspect it) beforehand. 

### Option 2: Python Source (required for Mac and Linux) <a name="installation--python"></a>

Alternatively, if you have Python installed on your machine, you can run the source py file instead of installing an EXE. If you're on a Mac or Linux machine, this is the only way to run the program.

**STEP 1 – INSTALL PYTHON AND REQUIRED MODULES**

First, check to see if Python is already installed with `python --version`. Also try `python3 --version` if the first one doesn't return a version number. If neither command shows you have Python, you'll need to install it. The easiest way is to go to [python.org](https://www.python.org) and download and install it from there. This project was created in Python Version 3.11.7, so it's best to use that version, if possible. If you have no plans to do anything else in or with Python, this is fine. However, the recommended way to use Python is through "virtual environemnts". Think of them as seperate sandboxes in which you can install specific versions of Python and the specific modules (and versions of the modules) required for a particular application. The easiest way to get started with virtual environments is to use a free program called Anaconda ([anaconda.com/download](https://www.anaconda.com/download)).

Next, you need to install the project's required modules. This is done with the "pip" installer command. All of the project's required modules are listed in the included requirements.txt file. So, to install them all at once, simply open your Terminal or Command Prompt window, navigate to the project directory where the requirements.txt file resides, and run the command:

    pip install -r requirements.txt

**STEP 2 – RUN THE PY FILE**

With python and all of the required modules installed, you can now start the app with:

    python Textures-Downloader.py

or if that doesn't work, try...

    python3 Textures-Downloader.py

The app should open in a new window and from here it will work just the same as running the EXE.

Closing the window or pressing Ctrl + c will terminate the app.

<br>

## For Mod Teams - Using this Tool for Your Project <a name="forking"></a>

This app was created by an NCAA NEXT mod team member for the NEXT project, but it is open-source and can be used for other PS2 texture-replacement mod projects. Feel free to fork the repo, customize it for your own project, and share the customized app with your community.

#### REPO CONFIG SETTINGS

Open config.txt and change the following settings to that of your project.

    owner: org-or-user
    repo: repository-name
    branch_name: main
    subdirectory: textures
    slus_folder: SLUS-XXXXX
    json_url: https://link-to-your/installer-data.json

The JSON file must be formatted as such:

    {
      "version": "v1.1",
      "release_date": "2024-02-05",
      "release_url": "https://github.com/owner/repo/releases/tag/v1.1",
      "total_size": 0.15,
      "temp_size": 0.05,
      "download_complete": [
        "textures/SLUS-21214/replacements/Controller",
        "textures/SLUS-21214/replacements/general",
        "textures/SLUS-21214/replacements/user-customs"
      ],
      "download_subdirectories": [
        "textures/SLUS-21214/replacements/uniforms/FBS",
        "textures/SLUS-21214/replacements/uniforms/FCS"
      ]
    }

- version: the version the installer tool will install (format this how you like)
- release_date: the date of the version
- release_url: link to the release version or wherever you like
- total_size: the total approximate size of the repo in GBs
- temp_size: approximate size of the largest zip it will download
- download_complete: a list of the paths to a folder in your repo that the installer will zip whole and download
- download_subdirectories: a list of the paths to a folder for which the installer will zip and download its subdirectories individually

Optionally, you can convert the app to a Windows executable using pyinstaller or other similar methods. This will alleviate the need for your users to install Python, but heads up - without a Windows developer license to properly sign the app, your EXE will almost certainly get flagged as malware by Windows Defender. If you know of a way to avoid this, please let me know!

#### USER-CUSTOMS FOLDER

To make use of the features [discussed above](#custom-textures) about user-custom textures, there must be a `user-customs` folder in the root of your mod's `replacements` folder. It can't reside anywhere else. Currently the functionality regardign the dash-prepended filenames is hard-coded and can't be disabled, but if this proposes a problem for your mod, feel free to reach out to me by creating a feature request, and I'd be happy to look into adding a toggle in the config.txt.

<br>

## LICENSE & PERMISSIONS <a name="license"></a>

PS2 Emulator Replacement Textures Installer and Updater © 2024 by JD6-37 is licensed under [CC BY-NC 4.0](http://creativecommons.org/licenses/by-nc/4.0/?ref=chooser-v1) 

This license requires that reusers give credit to the creator. It allows reusers to distribute, remix, adapt, and build upon the material in any medium or format, for noncommercial purposes only.