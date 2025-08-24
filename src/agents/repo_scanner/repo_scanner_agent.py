from agents import Agent, function_tool
import re
import requests
import base64
from collections import deque


# Add your GitHub personal access token here
GITHUB_TOKEN = ""

def extract_endpoints(file_content: str):
    """Scan Java file content for REST endpoints."""
    endpoints = []
    for match in re.finditer(
        r'@(GetMapping|PostMapping|PutMapping|DeleteMapping)\("([^"]+)"\)',
        file_content
    ):
        endpoints.append({"method": match.group(1), "path": match.group(2)})
    return endpoints

def list_repo_files(repo: str, path: str = "", branch: str = "main"):
    """List files in a GitHub repo using GitHub API."""
    print(f"[LOG] Listing files in repo: {repo}, path: {path}, branch: {branch}")
    url = f"https://api.github.com/repos/{repo}/contents/{path}?ref={branch}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    resp = requests.get(url, headers=headers)
    resp.raise_for_status()
    return resp.json()  # list of files/folders

def read_repo_file(repo: str, filepath: str, branch: str = "main"):
    """Read file content from GitHub using GitHub API."""
    print(f"[LOG] Reading file: {filepath} from repo: {repo}, branch: {branch}")
    url = f"https://api.github.com/repos/{repo}/contents/{filepath}?ref={branch}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    resp = requests.get(url, headers=headers)
    resp.raise_for_status()
    file_info = resp.json()
    content = base64.b64decode(file_info["content"]).decode("utf-8")
    return content

def repo_scan_logic_github(repo: str, path: str = "", branch: str = "main") -> str:
    """Iteratively scan GitHub repo for Java REST controllers and endpoints."""

    endpoints_summary = []
    dirs_to_scan = deque([""])  # start with root directory
    print(f"[LOG] Starting scan of repo: {repo}, branch: {branch}")
    while dirs_to_scan:
        current_path = dirs_to_scan.popleft()
        try:
            items = list_repo_files(repo, current_path, branch)
        except Exception as e:
            print(f"[ERROR] Failed to list files at path '{current_path}': {e}")
            continue

        for item in items:
            if item["type"] == "dir":
                # Skip hidden folders
                if item["name"].startswith("."):
                    print(f"[LOG] Skipping hidden folder: {item['path']}")
                    continue
                # Add directory to queue for later scanning
                dirs_to_scan.append(item["path"])
            elif item["type"] == "file" and item["name"].endswith(".java"):
                try:
                    content = read_repo_file(repo, item["path"], branch)
                    # Check if the file contains a REST controller
                    if "@RestController" in content or "@Controller" in content:
                        endpoints = extract_endpoints(content)
                        if endpoints:
                            endpoints_summary.append({"file": item["path"], "endpoints": endpoints})
                except Exception as e:
                    print(f"[ERROR] Failed to read file {item['path']}: {e}")

    result = {"repo": repo, "endpoints_found": endpoints_summary}
    print(result)
    print("******************************************************")
    return result


@function_tool
def scan_repo_github(repo: str, branch: str = "main") -> str:

    """High-level tool: scan GitHub repo for Java REST endpoints."""
    print(f"[LOG] Scanning GitHub repo: {repo}, branch: {branch}")
    return repo_scan_logic_github(repo, path="", branch=branch)

REPO_SCANNER_AGENT = Agent(
    name="GitHubRepoScannerAgent",
    instructions="Scan a GitHub repository for Java REST endpoints and return them grouped by file. Return the function tool response in JSON format",
    tools=[scan_repo_github],
    output_type=str
)
