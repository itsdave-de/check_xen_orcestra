
# Xen Orchestra Backup Status Checker

This script allows you to check the status of Xen Orchestra (XO) backup jobs. It can be integrated with OITC/Nagios for monitoring purposes or used standalone to generate backup reports and metrics.

---

## Features

- **List Backup Jobs:** Display all available backup jobs from the logs.
- **Check Backup Status:** Verify the status of a specific backup job.
- **Generate Metrics:** Compute total data transferred, average transfer rates, and other metrics.
- **Warning Summary:** Display warnings generated during backups.

---

## Requirements

### System Requirements

- **Python Version:** Python 3.6 or later.

### Python Dependencies

Ensure the following Python modules are installed:
- `psutil`
- `humanize`

You can install these dependencies (Debian packaging):
```bash
apt install python3-psutil python3-humanize
```

### Additional Tools

- **Xen Orchestra CLI (xo-cli):** Ensure `xo-cli` is installed and available at the path `/opt/xen-orchestra/node_modules/.bin/xo-cli` (default).
- **Permissions:** User running the script must have access to `/tmp` directory for temporary JSON file creation.

---

## Setup

1. Clone or download the script to your local machine (e.g. `/usr/lib/nagios/plugins/xo_backup_status.py`)

2. Set the script as executable:
   ```bash
   chmod +x /usr/lib/nagios/plugins/xo_backup_status.py
   ```

3. Update the `USER` and `PASSWORD` variables in the script with your Xen Orchestra credentials:
   ```python
   USER = 'your_username'
   PASSWORD = 'your_password'
   ```
4. Ensure `xo-cli` is properly configured and functional. Test it by running:
   ```bash
   /opt/xen-orchestra/node_modules/.bin/xo-cli --register http://localhost your_username your_password
   ```

---

## Usage

Run the script using the following commands:

### List All Backup Jobs
To list all available backup jobs:
```bash
./xo_backup_status.py --listjobs
```

### Check Status of a Specific Backup Job
To check the status of a backup job:
```bash
./xo_backup_status.py --job "Job Name"
```

### Display Help
To display the help message:
```bash
./xo_backup_status.py --help
```

---

## Example Output

When checking the status of a job:
```plaintext
OK: Backup completed successfully for job 'Daily Backup'
Job Name: Daily Backup
Job ID: abc123
Status: success
Start Time: 2024-12-10 01:00:00
End Time: 2024-12-10 01:30:00
Duration: 30 minutes
Mode: full
Total Data Transferred: 120.34 GB
Average Transfer Rate: 68.12 MB/s
VMs: VM1, VM2, VM3
Warnings: 0
| vms=3; warnings=0; duration=1800s; total_size=120340000000; average_rate=68120000
```

---

## Notes

- The script generates temporary JSON logs in `/tmp/xo_backup_status.json`. Ensure the script has appropriate permissions to create and modify this file.
- To customize paths or settings, modify the constants in the script:
  ```python
  JSON_FILE = '/tmp/xo_backup_status.json'
  ```

---

## Troubleshooting

- **Error in Generating JSON File:**
  Ensure `xo-cli` is correctly configured and the credentials are valid.
  
- **File Locked Error:**
  Wait for other processes to release the JSON file or restart the system if the lock persists.

