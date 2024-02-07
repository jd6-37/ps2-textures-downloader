import requests
import hashlib

def get_commit_information(owner, repo, commit_sha, access_token):
    url = f'https://api.github.com/repos/{owner}/{repo}/commits/{commit_sha}'
    headers = {'Authorization': f'token {access_token}'}
    response = requests.get(url, headers=headers)
    return response.json()

def get_tree_information(owner, repo, tree_sha, access_token):
    url = f'https://api.github.com/repos/{owner}/{repo}/git/trees/{tree_sha}?recursive=1'
    headers = {'Authorization': f'token {access_token}'}
    response = requests.get(url, headers=headers)
    return response.json()

def compute_local_file_hash(file_path):
    with open(file_path, 'rb') as f:
        data = f.read()
    s = hashlib.sha1()
    # Add blob, size of file and '\0' character
    s.update(("blob %u\0" % len(data)).encode('utf-8'))
    s.update(data)
    return s.hexdigest()


def compare_hashes(local_hash, github_hash):
    return local_hash == github_hash

# Replace these values with your own
owner = 'jd6-37'
repo = 'test-ncaanext'
commit_sha = '27c8c5c9c835c5ad514d3f67374815dffcc9652a'
local_file_path = '/Users/j/Documents/VideoGames/NCAA-Football/NCAA06/ncaanext-downloader/src/repo/a6c85db1568998c0-19eef849c8a801d6-00005553.png'
github_file_path = 'textures/SLUS-21214/replacements/uniforms/a6c85db1568998c0-19eef849c8a801d6-00005553.png'
access_token = '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'

# Step 1: Retrieve commit information
commit_info = get_commit_information(owner, repo, commit_sha, access_token)

# Step 2: Extract tree SHA from commit information
tree_sha = commit_info['commit']['tree']['sha']


# Step 3: Retrieve tree information
tree_info = get_tree_information(owner, repo, tree_sha, access_token)

# # Print all file paths in the "textures" directory for debugging
# print("All file paths in the directory:")
# for item in tree_info['tree']:
#     if item['path'].startswith('textures/SLUS-21214/replacements'):
#         print(item['path'])


# Step 4: Find the file in the tree and get its SHA
file_info = next((item for item in tree_info['tree'] if item['path'] == github_file_path), None)
print(f"file_info: {file_info}\n")

# Check if the file was found in the tree
if file_info is None:
    print("\nFile not found in the GitHub repository.")
else:
    github_file_sha = file_info['sha']
    print(f"\nRepo Tree SHA: {tree_sha}\n")
    print(f"\nRepo File SHA: {github_file_sha}\n")

# Step 5: Check if the file was found in the tree
if file_info is None:
    print("\nFile not found in the GitHub repository.")
    # Handle this case as needed (e.g., exit the script or provide a meaningful message)

# Step 5: Compute local file hash
local_hash = compute_local_file_hash(local_file_path)
print(f"Local File SHA: {local_hash}\n")

# Step 6: Compare hashes
if file_info is not None:
    result = compare_hashes(local_hash, github_file_sha)

    if result:
        print("File hashes match. The files are the same.\n")
    else:
        print("File hashes do not match. The files are different.\n")
else:
    print("File not found in the GitHub repository.\n")

