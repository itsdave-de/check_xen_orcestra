#!/usr/bin/env python3
import subprocess
import os
import json
import time
from datetime import datetime, timedelta
import argparse
import psutil
import humanize

# XOrchestra credentials
USER = 'username' # Change to your XOrchestra username
PASSWORD = 'password' # Change to your XOrchestra password

# Path
JSON_FILE = '/tmp/xo_backup_status.json'
CLI_REGISTER = f'/opt/xen-orchestra/node_modules/.bin/xo-cli --register http://localhost {USER} {PASSWORD}'
CLI_COMMAND = f'/opt/xen-orchestra/node_modules/.bin/xo-cli backupNg.getAllLogs ndjson=true @={JSON_FILE}'

def generate_json():
    try:
        register = subprocess.run(CLI_REGISTER.split(), stderr=subprocess.PIPE)
        result = subprocess.run(CLI_COMMAND.split(), stderr=subprocess.PIPE)
        if register.returncode != 0:
            print(f"CRITICAL: Error registering XO CLI: {register.stderr}")
            exit(2)
        elif result.returncode != 0:
            print(f"CRITICAL: Error generating JSON file: {result.stderr}")
            exit(2)
    except Exception as e:
        print(f"CRITICAL: Failed to generate JSON file: {e}")
        exit(2)

def load_json():
    try:
        with open(JSON_FILE, 'r') as infile:
            backups = [json.loads(line) for line in infile.readlines()]
        return backups
    except Exception as e:
        print(f"CRITICAL: Failed to load JSON file: {e}")
        exit(2)

def is_file_locked(file_path):
    """Check if a file is currently locked by any process."""
    for proc in psutil.process_iter(['pid', 'open_files']):
        try:
            open_files = proc.info['open_files']
            if open_files:  # Some processes may not have 'open_files'
                for file in open_files:
                    if file_path == file.path:
                        return True
        except (psutil.AccessDenied, psutil.NoSuchProcess):
            continue
    return False


def is_recent(file_path, max_age=3600):
    # Check if the file exists
    if not os.path.exists(file_path):
        return False

    # Wait until the file is not locked
    while is_file_locked(file_path):
        time.sleep(1)  # Wait for 1 second before retrying

    # Check if the file is non-empty and contains valid JSON
    try:
        with open(file_path, 'r') as file:
            content = file.read().strip()  # Read and remove any surrounding whitespace
            if not content:
                return False  # File is empty
            json.loads(content)  # Validate JSON format
    except (json.JSONDecodeError, Exception):
        return False  # File is not valid JSON or some other error occurred

    # Check if the file is recent
    file_age = datetime.now() - datetime.fromtimestamp(os.path.getmtime(file_path))
    if file_age >= timedelta(seconds=max_age):
        return False
    else:
        return file_age < timedelta(seconds=max_age)


def list_jobs():
    if not is_recent(JSON_FILE):
        generate_json()
    
    backups = load_json()
    job_names = set(b['jobName'] for b in backups if 'jobName' in b)
    
    if not job_names:
        print("No jobs found in the backup logs.")
        exit(0)
    
    print("Available jobs:")
    for job in sorted(job_names):
        print(f"- {job}")

def calculate_transfer_metrics(tasks):
    total_size = 0  # Total data size in bytes
    total_time = 0  # Total time in milliseconds

    for task in tasks:
        # Extraindo tamanho transferido e tempos
        size = task.get('result', {}).get('size', 0)
        start = task.get('start', 0)
        end = task.get('end', 0)

        # Verificando se os valores são válidos
        if size > 0 and start > 0 and end > start:
            total_size += size
            total_time += (end - start)

    # Convertendo tempo total para segundos
    total_time_seconds = total_time / 1000.0 if total_time > 0 else 1

    # Calculando taxa média
    average_rate = total_size / total_time_seconds if total_time_seconds > 0 else 0

    return total_size, average_rate


def extract_transfer_tasks(backup_data):
    transfer_tasks = []

    def find_transfer_tasks(tasks):
        for task in tasks:
            if isinstance(task, dict):  # Verifique se é um dicionário
                # Se a mensagem é "transfer", adicione à lista
                if task.get('message') == 'transfer':
                    transfer_tasks.append(task)
                # Se existirem mais subtasks, percorra recursivamente
                subtasks = task.get('tasks', [])
                if subtasks:
                    find_transfer_tasks(subtasks)

    # Inicie a busca a partir das tarefas principais
    find_transfer_tasks(backup_data.get('tasks', []))
    return transfer_tasks


def format_backup_output(backup_data):
    job_name = backup_data.get('jobName', 'Unknown')
    job_id = backup_data.get('jobId', 'Unknown')
    status = backup_data.get('status', 'Unknown')
    
    start_timestamp = backup_data['start'] // 1000
    end_timestamp = backup_data['end'] // 1000
    start_time = datetime.fromtimestamp(start_timestamp)
    end_time = datetime.fromtimestamp(end_timestamp)
    
    mode = backup_data.get('data', {}).get('mode', 'Unknown')
    vms = [task['data']['name_label'] for task in backup_data.get('tasks', []) if task['data']['type'] == 'VM']
    warnings = []

    # Calculate duration using datetime objects
    duration = end_time - start_time
    duration_readable = humanize.precisedelta(duration, minimum_unit="seconds")

    # Collect warnings from tasks
    for task in backup_data.get('tasks', []):
        for subtask in task.get('tasks', []):
            warnings.extend(subtask.get('warnings', []))

    # Summary
    num_vms = len(vms)
    num_warnings = len(warnings)

    # Extract only "transfer" subtasks safely
    transfer_tasks = extract_transfer_tasks(backup_data)

    # Calculate metrics using validated transfer tasks
    total_size, average_rate = calculate_transfer_metrics(transfer_tasks)

    # Convert to human-readable sizes
    total_size_gb = total_size / (1024 ** 3)  # Convert to GB
    average_rate_mb_s = average_rate / (1024 ** 2)  # Convert to MB/s

    # Perfdata for Nagios
    perfdata = f"vms={num_vms}; warnings={num_warnings}; duration={int((end_time - start_time).total_seconds())}s; total_size={total_size}; average_rate={average_rate}"  

    # Output format
    output = [
        f"Job Name: {job_name}",
        f"Job ID: {job_id}",
        f"Status: {status}",
        f"Start Time: {start_time.strftime('%Y-%m-%d %H:%M:%S')}",
        f"End Time: {end_time.strftime('%Y-%m-%d %H:%M:%S')}",
        f"Duration: {duration_readable}",
        f"Mode: {mode}",
        f"Total Data Transferred: {total_size_gb:.2f} GB",
        f"Average Transfer Rate: {average_rate_mb_s:.2f} MB/s",
        f"VMs: {', '.join(vms) if vms else 'No VMs'}",
        f"Warnings: {num_warnings}",
    ]

    if warnings:
        output.append("Details of Warnings:")
        for warning in warnings:
            path = warning['data']['path']
            message = warning['message']
            output.append(f"  - {message}: {path}")

    output.append(f"| {perfdata}")
    return "\n".join(output)

# Check backup job status
def check_backup_status(job_name):
    # Generate the JSON file if it's not recent
    if not is_recent(JSON_FILE):
        generate_json()
    
    # Load the backup logs
    backups = load_json()
    today = datetime.today().date()
    
    # Filter logs for the specified job and today's date
    job_logs = [
        b for b in backups
        if b.get('jobName') == job_name and datetime.fromtimestamp(b['start'] // 1000).date() == today
    ]
    
    if not job_logs:
        # No logs found for the specified job
        print(f"UNKNOWN: No backup logs found for job '{job_name}' today")
        exit(3)

    # Get the most recent log
    job_log = max(job_logs, key=lambda b: b['start'])

    # Format the output
    output = format_backup_output(job_log)

    # Determine Nagios exit code
    if job_log['status'] == 'success':
        print(f"OK: Backup completed successfully for job '{job_name}'\n{output}")
        exit(0)
    elif job_log['status'] == 'failure':
        print(f"CRITICAL: Backup failed for job '{job_name}'\n{output}")
        exit(2)
    else:
        print(f"UNKNOWN: Backup status unknown for job '{job_name}'\n{output}")
        exit(3)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Check Xen Orchestra Backup Status for Nagios")
    parser.add_argument('-j', '--job', help="Name of the backup job to check")
    parser.add_argument('--listjobs', action='store_true', help="List all available backup jobs")
    args = parser.parse_args()
    
    if args.listjobs:
        list_jobs()
    elif args.job:
        check_backup_status(args.job)
    else:
        print("ERROR: You must specify either --job or --listjobs.")
        parser.print_help()
        exit(1)
