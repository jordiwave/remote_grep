# remote_grep
A Python script to search for strings in files on remote servers via SSH. Supports password-based authentication, wildcard path expansion, and parallel execution. Uses grep for case-insensitive searches and lists matching files. Server configurations are managed via a JSON file.

# Remote Grep Utility

A Python-based utility for securely searching files on remote servers via SSH. This tool allows you to:

- Perform case-insensitive searches for specific strings in files on remote servers.
- Use wildcard patterns to search across multiple files or directories.
- Retrieve a list of files containing the search term, along with their line numbers.
- Manage multiple remote servers with a JSON-based configuration file.

### Features
- **Password-based SSH Authentication**: Connect to remote servers using username and password (ideal for environments without SSH keys).
- **Parallel Execution**: Search across multiple servers simultaneously using multithreading.
- **Customizable Configuration**: Define server details (hostname, IP, username, password, port) in a JSON file.
- **Error Handling**: Handles SSH connection issues and provides detailed error messages.

### Requirements
- Python 3.7+
- paramiko for SSH connections
- argparse for command-line argument parsing

