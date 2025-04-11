#!/usr/bin/env python3
import os
import re
import subprocess
from datetime import datetime
import sys

def get_repo_root():
    """Get the root directory of the git repository."""
    try:
        root = subprocess.check_output(['git', 'rev-parse', '--show-toplevel'], 
                                      stderr=subprocess.STDOUT).decode('utf-8').strip()
        return root
    except subprocess.CalledProcessError:
        print("Error: Not a git repository or git command not found.")
        sys.exit(1)

def check_git_status():
    """Check if there are changes to commit."""
    status = subprocess.check_output(['git', 'status', '--porcelain']).decode('utf-8').strip()
    return bool(status)

def get_commit_number():
    """Extract the latest commit number from commit_log.md."""
    repo_root = get_repo_root()
    commit_log_path = os.path.join(repo_root, 'commit_log.md')
    
    if not os.path.exists(commit_log_path):
        return 0
    
    with open(commit_log_path, 'r') as f:
        content = f.read()
    
    # Find the latest commit number using regex
    commit_pattern = r'## commit (\d+)'
    matches = re.findall(commit_pattern, content)
    
    if not matches:
        return 0
    
    return int(matches[0]) + 1

def get_commit_message():
    """Get commit message from user input with proper formatting."""
    print("Enter your commit message (press Enter twice to finish):")
    lines = []
    
    while True:
        line = input()
        if not line and lines and not lines[-1]:  # Two consecutive empty lines
            lines.pop()  # Remove the last empty line
            break
        lines.append(line)
    
    # Process lines to handle different levels of dashes
    processed_lines = []
    for line in lines:
        # Match dashes at the beginning of the line
        match = re.match(r'^(-+)(\s+)?(.*)$', line)
        if match:
            dash_count = len(match.group(1))
            content = match.group(3)
            processed_lines.append(f"{'  ' * (dash_count - 1)}- {content}")
        else:
            processed_lines.append(line)
    
    return processed_lines

def update_commit_log(commit_number, commit_message):
    """Update the commit_log.md file with the new commit."""
    repo_root = get_repo_root()
    commit_log_path = os.path.join(repo_root, 'commit_log.md')
    
    # Get current date and time
    now = datetime.now()
    date_time = now.strftime("%-m/%-d/%Y - %H:%M")
    
    # Create new commit entry
    new_commit = f"## commit {commit_number} ({date_time})\n\n"
    for line in commit_message:
        new_commit += f"{line}\n"
    
    # Add an extra newline for spacing
    new_commit += "\n"
    
    # Read existing content
    if os.path.exists(commit_log_path):
        with open(commit_log_path, 'r') as f:
            content = f.read()
            
        # Split content to insert new commit after the header
        if '# Commit History' in content:
            header, rest = content.split('# Commit History', 1)
            new_content = header + '# Commit History' + '\n\n' + new_commit + rest.lstrip()
        else:
            new_content = '# Commit History\n\n' + new_commit + content
    else:
        new_content = '# Commit History\n\n' + new_commit
    
    # Write updated content back
    with open(commit_log_path, 'w') as f:
        f.write(new_content)

def perform_git_operations(commit_number):
    """Perform git add, commit, and push operations."""
    try:
        # Git add
        subprocess.run(['git', 'add', '.'], check=True)
        
        # Git commit
        commit_message = f"commit {commit_number}"
        subprocess.run(['git', 'commit', '-m', commit_message], check=True)
        
        # Git push
        subprocess.run(['git', 'push'], check=True)
        
        print(f"Successfully committed and pushed: commit {commit_number}")
    except subprocess.CalledProcessError as e:
        print(f"Error during git operations: {e}")
        sys.exit(1)

def main():
    # Check if there are changes to commit
    if not check_git_status():
        print("No changes to commit.")
        return
    
    # Get the next commit number
    commit_number = get_commit_number()
    
    # Get commit message from user
    commit_message = get_commit_message()
    
    # Update commit_log.md
    update_commit_log(commit_number, commit_message)
    
    # Perform git operations
    perform_git_operations(commit_number)

if __name__ == "__main__":
    main()