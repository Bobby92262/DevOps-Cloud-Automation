#!/usr/bin/bash
#
# Some basic monitoring functionality; Tested on Amazon Linux 2023.
#

# Token retrieval
TOKEN=`curl -s -X PUT "http://169.254.169.254/latest/api/token" -H "X-aws-ec2-metadata-token-ttl-seconds: 21600"`

# Collect system metrics
INSTANCE_ID=$(curl -s -H "X-aws-ec2-metadata-token: $TOKEN" http://169.254.169.254/latest/meta-data/instance-id)

MEMORYUSAGE=$(free -m | awk '/Mem/ {printf "Memory Used: %.1f%%\n", $3/$2*100 }')

HTTPD_PROCESSES=$(ps -A | grep -c httpd)

#Log SetUp dir/file
LOG_DIR="$HOME/monitoring_logs"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/monitor_$(date +'%Y%m%d_%H%M%S').log"

# Capture uptime and CPU-consuming processes
UPTIME=$(uptime | tee -a "$LOG_FILE")
CPU_PROCESSES=$(ps aux --sort=-%cpu | head -n 11)

#Colors 
RED="\e[31m" GREEN="\e[32m" YELLOW="\e[33m" BLUE="\e[34m" CYAN="\e[36m" RESET="\e[0m"


#Util Functions
log() {
	local COLOR="$1"
	local text="$2"
	echo -e "${COLOR}${text}${RESET}" # Console
	echo -e "${text}" >> "$LOG_FILE"  # File
}

# Header utility
section() {
	log "$CYAN" "\n============ $1 ==========="
}

# log instance metadata and basic metric
log "$BLUE" "Instance ID: $INSTANCE_ID"
log "$BLUE" "Memory utilisation: $MEMORYUSAGE"
log "$BLUE" "No of processes: $PROCESSES"

# log OS and kernel info
section "OS and Kernal Info"
hostnamectl | grep "Operating System" | tee -a "$LOG_FILE"
uname -r | tee -a "$LOG_FILE"

#Monitor Apache server
section "Apache server check"
if [ $HTTPD_PROCESSES -ge 1 ]
then
    log "$GREEN" "Web server is running"
else
    log "$RED" "Web server is NOT running"
fi

# Resource usage summary
section "Resource Usage"
log "$GREEN" "Uptime: $UPTIME"

#Monitor Processes by CPU
section "Top 10 CPU-consuming processes"
echo -e "$CPU_PROCESSES" >> "$LOG_FILE"
echo -e "$CPU_PROCESSES"
CPU_COUNT=$(echo "$CPU_PROCESSES" | tail -n +2 | wc -l)
if [ "$CPU_COUNT" -ge 1 ]
then
	log "$BLUE" "Top 10 CPU consuming processes logged."
	
else
	log "$RED" "No active processes found"
fi

# System Threshold checks
section "System Usage"

# Extract CPU idle percentage
CPU_IDLE=$(vmstat 1 2 | tail -1 | awk '{print 100 - $15}')

# Extract disk uage percentage for root
DISK_USED=$(df --output=pcent / | tail -1 | tr -dc '0-9')

# Extract free memory
MEM_FREE=$( awk '/MemAvailable:/ {print int($2/1024)}' /proc/meminfo)

# Alert if CPU idle is below threshold
if [[ "$CPU_IDLE" =~ ^[0-9]+$ ]] && [ "$CPU_IDLE" -lt 90 ]
then
	log "$YELLOW" "Low CPU detected (IDLE: ${CPU_IDLE}%)"
fi

# Alert if disk used exceeds threshold
if [[ "$DISK_USED" =~ ^[0-9]+$ ]] && [ "$DISK_USED" -gt 10 ]
then
	log "$YELLOW" "Disk usage > 10% (${DISK_USED}%)"
fi

# Alert if free memory is low
if [[ "$MEM_FREE" =~ ^[0-9]+$ ]] && [ "$MEM_FREE" -lt 300 ]
then
	log "$YELLOW" "Free memory less than 300MB (${MEM_FREE} MB)"
fi

#Finish
log "$GREEN" "\n Monitoring complete. Log saved to $LOG_FILE"
##### REFERENCE #############
#https://medium.com/@prajwalpatil0402/monitoring-ec2-instances-with-shell-and-python-scripts-7fa94becab0b
