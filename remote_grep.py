
#!/usr/bin/env python3
"""
Run a grep search over SSH on multiple Solaris hosts and optionally download matching files.

usage: remote_grep.py [-h] --config CONFIG --search SEARCH --path PATH [--download {0,1}] [--dest DEST] [--parallel PARALLEL] [--timeout TIMEOUT]

Run grep on Solaris hosts over SSH and optionally download matching files.

options:
  -h, --help           show this help message and exit
  --config CONFIG      Path to JSON config with host entries (hostname, username, password[, port]).
  --search SEARCH      Literal search string (e.g., 'Retorno:99').
  --path PATH          Remote path or glob pattern (e.g., /var/.../ssnnMAB0076*)
  --download {0,1}     If 1, download matching files.
  --dest DEST          Local destination root for downloads (default: downloads).
  --parallel PARALLEL  Number of parallel SSH sessions (default: 4).
  --timeout TIMEOUT    Per-host SSH/command timeout seconds (default: 120).

Usage:
  python3 remote_grep.py \
    --config hosts.json \
    --search 'Retorno:99' \
    --path '/var/opt/aat/trazas/ma/sunone/web_visord/ssnnMAB0076*' \
    --download 1 \
    --dest downloads

Notes:
- Uses password-based SSH auth (per requirement). Consider SSH keys for production.
- Uses grep -F -l to list matching files; this is more reliable for parsing results.
- Wildcard expansion (the '*' in your path) is performed on the remote host shell.
"""

import argparse
import json
import os
import sys
import socket
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import List, Tuple
import shlex
import paramiko

# ----------------------------- Data classes -----------------------------

@dataclass
class HostConfig:
    hostname: str
    ip: str
    username: str
    password: str
    port: int = 22

# ----------------------------- SSH logic -----------------------------

def build_list_command(search: str, path_glob: str) -> str:
    """
    Build a remote command that lists files containing the search string.
    - grep -i  : case-insensitive 
    - grep -l  : print only names of files with matches
    - '--'     : end of options, protects paths starting with '-'
    - LC_ALL=C : predictable locale
    We intentionally DO NOT shell-quote path_glob so the wildcard expands on remote side.
    """
    inner = f"LC_ALL=C grep -iln -- {shlex.quote(search)} {path_glob}"
    return "bash -c " + shlex.quote(inner)

def connect_ssh(host: HostConfig, timeout: int) -> paramiko.SSHClient:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(
        hostname=host.ip,
        port=host.port,
        username=host.username,
        password=host.password,
        allow_agent=False,
        look_for_keys=False,
        timeout=timeout,
        banner_timeout=timeout,
        auth_timeout=timeout,
    )
    return client

def run_list_on_host(host: HostConfig, search: str, path_glob: str, timeout: int = 120) -> Tuple[str, int, List[str], str]:
    """
    Run grep -l on the remote host; return (hostname, exit_code, matching_paths[], stderr_text).
    grep exit codes:
      0 -> matches found
      1 -> no matches
      2 -> error
    """
    try:
        client = connect_ssh(host, timeout)
    except (paramiko.AuthenticationException, paramiko.SSHException, socket.error) as e:
        return (host.hostname, 255, [], f"SSH/Network error: {e}")

    try:
        cmd = build_list_command(search, path_glob)
        stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
        stdin.close()

        out = stdout.read().decode(errors="replace")
        err = stderr.read().decode(errors="replace")
        exit_status = stdout.channel.recv_exit_status()

        # Parse paths: each line is a full path to a file matched
        paths = [line.strip() for line in out.splitlines() if line.strip()]

        return (host.hostname, exit_status, paths, err)
    finally:
        try:
            client.close()
        except Exception:
            pass

def sftp_download_files(host: HostConfig, paths: List[str], dest_root: str, timeout: int = 120) -> List[Tuple[str, str]]:
    """
    Download each remote path via SFTP to local dest_root/hostname/<full-remote-path>.
    Creates directories as needed.
    Returns a list of (remote_path, local_path) for successfully downloaded files.
    """
    downloaded = []
    try:
        client = connect_ssh(host, timeout)
        sftp = client.open_sftp()
    except (paramiko.AuthenticationException, paramiko.SSHException, socket.error) as e:
        print(f"[ERROR] {host.hostname}: SFTP connect failed: {e}", file=sys.stderr)
        return downloaded

    try:
        for rpath in paths:
            # Build local target path: dest_root/hostname/<full remote path...>
            local_path = os.path.join(dest_root, host.hostname, rpath.lstrip("/"))
            local_dir = os.path.dirname(local_path)
            os.makedirs(local_dir, exist_ok=True)

            try:
                sftp.get(rpath, local_path)
                downloaded.append((rpath, local_path))
            except FileNotFoundError:
                print(f"[WARN] {host.hostname}: Remote file not found: {rpath}", file=sys.stderr)
            except PermissionError:
                print(f"[WARN] {host.hostname}: Permission denied: {rpath}", file=sys.stderr)
            except Exception as e:
                print(f"[WARN] {host.hostname}: Failed to download {rpath}: {e}", file=sys.stderr)
    finally:
        try:
            sftp.close()
        except Exception:
            pass
        try:
            client.close()
        except Exception:
            pass

    return downloaded

# ----------------------------- CLI & Orchestration -----------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run grep on Solaris hosts over SSH and optionally download matching files.")
    parser.add_argument("--config", required=True, help="Path to JSON config with host entries (hostname, username, password[, port]).")
    parser.add_argument("--search", required=True, help="Literal search string (e.g., 'Retorno:99').")
    parser.add_argument("--path", required=True, help="Remote path or glob pattern (e.g., /var/.../ssnnMAB0076*)")
    parser.add_argument("--download", type=int, choices=[0, 1], default=0, help="If 1, download matching files.")
    parser.add_argument("--dest", default="downloads", help="Local destination root for downloads (default: downloads).")
    parser.add_argument("--parallel", type=int, default=4, help="Number of parallel SSH sessions (default: 4).")
    parser.add_argument("--timeout", type=int, default=120, help="Per-host SSH/command timeout seconds (default: 120).")
    return parser.parse_args()

def load_hosts(config_path: str) -> List[HostConfig]:
    with open(config_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    hosts: List[HostConfig] = []
    for entry in data:
        hosts.append(
            HostConfig(
                hostname=entry["hostname"],
                ip=entry["ip"],
                username=entry["username"],
                password=entry["password"],
                port=int(entry.get("port", 22)),
            )
        )
    if not hosts:
        raise ValueError("No hosts found in config.")
    return hosts

def print_host_results(hostname: str, exit_code: int, paths: List[str], err: str) -> None:
    sep = "=" * 80
    print(f"\n{sep}\nHost: {hostname}\nExit: {exit_code}\n{sep}")
    if paths:
        print("Matched files:")
        for p in paths:
            print(f"  Host: {hostname} | Path: {p}")
    else:
        print("Matched files: (none)")
    if err.strip():
        print(f"\n[stderr]\n{err.rstrip()}")

    if exit_code == 0:
        print(f"\n[INFO] Matches found on {hostname}.")
    elif exit_code == 1:
        print(f"\n[INFO] No matches found on {hostname}.")
    elif exit_code == 2:
        print(f"\n[WARN] Grep reported an error on {hostname} (exit 2).")
    elif exit_code == 255:
        print(f"\n[ERROR] SSH/Network failure contacting {hostname}.")
    else:
        print(f"\n[WARN] Non-zero exit code {exit_code} on {hostname}.")

def main() -> int:
    args = parse_args()
    try:
        hosts = load_hosts(args.config)
        print(hosts)
    except Exception as e:
        print(f"[FATAL] Could not load config: {e}", file=sys.stderr)
        return 2

    results = []
    downloads_summary = []

    with ThreadPoolExecutor(max_workers=max(args.parallel, 1)) as pool:
        futures = {
            pool.submit(run_list_on_host, host, args.search, args.path, args.timeout): host
            for host in hosts
        }

        for fut in as_completed(futures):
            host = futures[fut]
            try:
                hostname, exit_code, paths, err = fut.result()
            except Exception as e:
                hostname = host.hostname
                exit_code, paths, err = 255, [], f"Unhandled exception: {e}"

            print_host_results(hostname, exit_code, paths, err)
            results.append((hostname, exit_code, len(paths)))

            # If requested, download files that matched
            if args.download == 1 and exit_code == 0 and paths:
                dl = sftp_download_files(host, paths, args.dest, timeout=args.timeout)
                if dl:
                    print("\nDownloaded files:")
                    for r, l in dl:
                        print(f"  Host: {hostname} | Remote: {r} -> Local: {l}")
                downloads_summary.extend((hostname, r, l) for r, l in dl)

    # Summary
    total_hosts = len(results)
    matched_hosts = sum(1 for _, code, cnt in results if code == 0 and cnt > 0)
    no_match_hosts = sum(1 for _, code, cnt in results if code == 1 or cnt == 0)
    error_hosts = sum(1 for _, code, _ in results if code not in (0, 1))

    print("\nSummary:")
    print(f"  Hosts total : {total_hosts}")
    print(f"  Matches on  : {matched_hosts}")
    print(f"  No matches  : {no_match_hosts}")
    print(f"  Errors      : {error_hosts}")
    if args.download == 1:
        print(f"  Files downloaded: {len(downloads_summary) if downloads_summary else 0}")

    # Exit non-zero if any error occurred (but not for "no matches")
    return 0 if error_hosts == 0 else 1

if __name__ == "__main__":
    sys.exit(main())

