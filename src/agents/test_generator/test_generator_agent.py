from agents import Agent, function_tool
import re
import os
import json
import requests
from typing import List
from pathlib import Path


# ---------------------
# Helper Functions
# ---------------------

def extract_model_fields(file_content: str):
    """Extracts field names and types from a Java model file"""
    fields = {}
    for match in re.finditer(r'(private|public|protected)\s+(\w+)\s+(\w+);', file_content):
        field_type, field_name = match.group(2), match.group(3)
        fields[field_name] = field_type
    return fields

def dummy_value(java_type: str):
    """Maps Java types to dummy Python values for payloads"""
    mapping = {
        "int": 1,
        "long": 1,
        "double": 1.0,
        "float": 1.0,
        "String": "test",
        "boolean": True
    }
    return mapping.get(java_type, "dummy")

def build_payload(java_file_path):
    """Generates a dummy payload from a Java model file"""
    with open(java_file_path, "r") as f:
        content = f.read()
    fields = extract_model_fields(content)
    return {f: dummy_value(t) for f, t in fields.items()}

def detect_model_from_controller(controller_content: str, http_method: str, path: str):
    """Detects the Java model class from controller method signature"""
    pattern = re.compile(
        rf'@{http_method}Mapping\("{re.escape(path)}"\)\s+public\s+\w+\s+\w+\s*\(\s*@RequestBody\s+(\w+)'
    )
    match = pattern.search(controller_content)
    if match:
        return match.group(1)
    return None

def find_model_file(models_dir, model_name):
    """Searches for the model file under models_dir"""
    for root, _, files in os.walk(models_dir):
        for f in files:
            if f == f"{model_name}.java":
                return os.path.join(root, f)
    return None



def find_models_dir(repo_path: str) -> str | None:
    """
    Recursively search inside src/main/java for a 'model' or 'models' directory.
    Returns the first match or None if not found.
    """
    java_src = Path(repo_path) / "src" / "main" / "java"
    print(f"[Agent2] Looking for 'model' directory in {java_src}")

    if not java_src.exists():
        print(f"[Agent2] No src/main/java found in {repo_path}")
        return None

    # Walk recursively through all subdirectories
    for root, dirs, _ in os.walk(java_src):
        print(f"[Agent2] Scanning: {root}")  # 👈 debug: shows traversal
        for d in dirs:
            if d.lower() in ["model", "models"]:
                model_dir = os.path.join(root, d)
                print(f"[Agent2] Found model directory: {model_dir}")
                return model_dir

    print("[Agent2] No 'model' directory found under src/main/java")
    return None


    # Look through all subdirectories under src/main/java
    for root, dirs, _ in os.walk(java_src):
        for d in dirs:
            if d.lower() in ["model", "models"]:
                model_dir = os.path.join(root, d)
                print(f"[Agent2] Found model directory: {model_dir}")
                return model_dir

    print("[Agent2] No 'model' directory found under src/main/java")
    return None

# ---------------------
# Tool Function
# ---------------------

def read_repo_file(repo: str, path: str, branch: str = "main") -> str:
    """
    Read a file from GitHub repo using raw.githubusercontent.com
    """
    url = f"https://raw.githubusercontent.com/{repo}/{branch}/{path}"
    print(f"[Agent2] Reading: {url}")
    response = requests.get(url)
    print(f"[Agent2] Response status: {response.status_code}")
    if response.status_code == 200:
        return response.text
    else:
        raise Exception(f"Failed to read {path} from {repo} (status {response.status_code})")

def find_models_dir_github(repo: str, branch: str = "main") -> str | None:
    """
    Search GitHub repo under src/main/java for a 'model' or 'models' directory.
    Returns the first match path (relative to repo root) or None if not found.
    """
    base_path = "src/main/java"
    queue = [base_path]
    print(f"[Agent2] Looking for 'model' directory in {base_path} of repo {repo}")
    while queue:
        current_path = queue.pop(0)
        url = f"https://api.github.com/repos/{repo}/contents/{current_path}?ref={branch}"
        resp = requests.get(url)
        print(f"[Agent2] Checking: {url} (status {resp.status_code})")
        if resp.status_code != 200:
            continue

        items = resp.json()
        for item in items:
            if item["type"] == "dir":
                if item["name"].lower() in ["model", "models"]:
                    return item["path"]
                queue.append(item["path"])  # add subdirectory to queue

    return None

@function_tool
def generate_api_tests(
    endpoints_summary: str,
    repo_path: str,
    base_url: str = "http://localhost:8080"
) -> dict:
    """
    Generates pytest API tests from Agent 1 endpoints summary.
    Reads controller files directly from GitHub using read_repo_file.
    Returns a plain dict with test names and code.
    """
    print("[Agent2] Generating pytest tests...")
    tests_generated = []

    models_dir = find_models_dir_github(repo_path)
    if not models_dir:
        print("[Agent2] Warning: 'model' directory not found. POST/PUT payloads will use dummy data.")
    print(f"[Agent2] INPUT: {endpoints_summary}")    
    json_data =  json.loads(endpoints_summary)
    print(f"[Agent2] Parsed JSON data: {json_data}")
    print(f"[Agent2] Parsed JSON data: {json_data.get('repo')}")
    print(f"[Agent2] Parsed JSON data: {json_data.get('endpoints_found')}")
    for file_entry in json_data.get("endpoints_found", []):
        print(f"[Agent2] Processing controller: {file_entry['file']}")
        print(f"[Agent2] Processing controller: {json_data['repo']}")
        try:
            # Read controller content directly from GitHub
            controller_content = read_repo_file(
                repo=json_data['repo'],
                path=file_entry['file'],
                branch="main"
            )
        except Exception as e:
            print(f"[Agent2] Warning: Could not read {file_entry['file']} from GitHub: {e}")
            continue

        for ep in file_entry["endpoints"]:
            method = ep["method"].replace("Mapping", "").lower()
            path = ep["path"]
            func_name = f"test_{method}_{path.strip('/').replace('/', '_').replace('{','').replace('}','')}"
            url_expr = f'f"{{BASE_URL}}{path}"'

            code_lines = [
                "import requests",
                f'BASE_URL = "{base_url}"',
                "def substitute_path(path: str):",
                "    import re",
                "    def repl(match):",
                '        return "1"',  # dummy ID replacement
                "    return re.sub(r'{(.*?)}', repl, path)",
                ""
            ]

            # POST/PUT requests
            if method in ["post", "put"] and models_dir:
                model_name = detect_model_from_controller(controller_content, ep["method"].replace("Mapping",""), path)
                payload = {"dummy": "data"}
                if model_name:
                    model_file = find_model_file(models_dir, model_name)
                    if model_file:
                        payload = build_payload(model_file)

                code_lines.append(f"def {func_name}():")
                code_lines.append(f"    url = substitute_path({url_expr})")
                code_lines.append(f"    payload = {json.dumps(payload, indent=4)}")
                code_lines.append(f"    response = requests.{method}(url, json=payload)")
                code_lines.append("    assert response.status_code in [200,201,204]")
                code_lines.append("")
            else:
                # GET/DELETE requests
                code_lines.append(f"def {func_name}():")
                code_lines.append(f"    url = substitute_path({url_expr})")
                code_lines.append(f"    response = requests.{method}(url)")
                code_lines.append("    assert response.status_code in [200,201,204]")
                code_lines.append("")

            tests_generated.append({
                "test_name": func_name,
                "code": "\n".join(code_lines)
            })

    test_file_path = os.path.join(os.getcwd(), "test_api.py")
    with open(test_file_path, "w") as f:
        f.write("\n".join(tests_generated))
        
    print(f"[Agent2] Generated {len(tests_generated)} tests.")
    return {"repo": repo_path, "tests_generated": tests_generated}

# ---------------------
# Agent Definition
# ---------------------

TEST_GENERATOR_AGENT = Agent(
    name="TestGeneratorAgent",
    instructions="Generate dynamic pytest API automation tests from scanned REST endpoints. Make sure \"endpoint_summary\" variable of GitHubRepoScannerAgent agent's output should have the dict structure as returned by it's function tool.",
    tools=[generate_api_tests],
    output_type=str
)
