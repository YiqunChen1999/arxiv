# #!/bin/zsh

# source /Users/yiqunchen/.zshrc

# script_folder="${0:a:h}"
# python="$HOME/miniconda3/envs/arxiv/bin/python"
# main="$script_folder/arxiver/main.py"
# pipeline=$1
# # default datetime is yesterday
# datetime=${2:-$(date -v-1d +%Y-%m-%d)}

# $python $main --pipeline $pipeline --datetime $datetime


# This script is used to run the job every day
# The job is to download the arxiv papers and translate them
# The job is run in the background
# The output is saved in ./outputs/scheduled.txt
wait_until_time=${1:-"$(date -v+1d +%Y-%m-%d) 11:45"}

run_job() {
    nohup ./download.sh RequestThenTranslate >> ./outputs/scheduled.txt &
    nohup ./download.sh RequestThenTranslate $(date -v-3d +%Y-%m-%d) >> ./outputs/scheduled.txt &
    # nohup ./download.sh Request >> ./outputs/scheduled.txt &
    echo "Submitted job to background at $date"
}

get_sleep_seconds() {
    target="$1"  # Format: "YYYY-MM-DD HH:MM"
    
    # Get current and target timestamps
    current_ts=$(date +%s)
    target_ts=$(date -j -f "%Y-%m-%d %H:%M" "$target" +%s)
    
    # Calculate difference
    diff_seconds=$((target_ts - current_ts))
    
    # Return positive value only
    if [ $diff_seconds -lt 0 ]; then
        echo 0
    else
        echo $diff_seconds
    fi
}

sleep_until_time() {
    target="$1"  # Format: "YYYY-MM-DD HH:MM"
    echo "Wait Until Time: $target"
    sleep_seconds=$(get_sleep_seconds "$target")
    echo "Sleeping $sleep_seconds seconds"
    sleep $sleep_seconds
}

# Example usage:
# sleep_seconds=$(get_sleep_seconds "2024-03-20 15:30")

# endless loop
schedule_requests() {
    # endless loop to schedule the job daily
    while true; do
        sleep_until_time "$wait_until_time"
        run_job
        # update wait_until_time to the next day
        wait_until_time=$(date -v+1d -j -f "%Y-%m-%d %H:%M" "$wait_until_time" "+%Y-%m-%d %H:%M")
    done
}

schedule_requests
