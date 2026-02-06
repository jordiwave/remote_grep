## Overview

Remote Grep allows you to search for strings in files on remote servers without manually logging into each one. It connects via SSH, runs searches in parallel, and returns results with file paths and line numbers.

## Key Features

- **SSH Authentication** - Connect using username/password authentication
- **Parallel Search** - Search multiple servers simultaneously with multithreading
- **Pattern Matching** - Support for wildcard patterns to search multiple files
- **Case-Insensitive** - Searches ignore case by default
- **JSON Configuration** - Manage all server credentials in one configuration file
- **Detailed Results** - Get file paths and line numbers for every match
- **Error Handling** - Clear error messages for connection and search issues

## Requirements

- Python 3.7 or higher
- Dependencies listed in `requirements.txt`

## Installation

### Linux

```bash
# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Windows

```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

## Usage

### Activate Virtual Environment

Before running the program, activate the virtual environment:

**Linux:**
```bash
source venv/bin/activate
```

**Windows:**
```bash
venv\Scripts\activate
```

### Run the Program

```bash
python remote_grep.py <search_term> <file_pattern> [options]
```

### Deactivate Virtual Environment

When finished, deactivate the virtual environment:

```bash
deactivate
```

This command works on both Linux and Windows.

## Configuration

Create a JSON file with your server details:

```json
[
  {
    "hostname": "server1",
    "ip": "192.168.1.1",
    "username": "user",
    "password": "pass",
    "port": 22
  },
  {
    "hostname": "server2",
    "ip": "192.168.1.2",
    "username": "user",
    "password": "Telefpassoni0126",
    "port": 22
  }
]
```

## Example

Search for "error" in log files across all configured servers:

```bash
python remote_grep.py \
  --config hosts.json \
  --search 'Return:' \
  --path '/var/log/*.log' \
  --download 1 \
  --dest downloads \
  --parallel 6 \
  --timeout 180
```

## Security Note

This tool stores passwords in plain text in the configuration file. Use appropriate file permissions to protect sensitive credentials.
