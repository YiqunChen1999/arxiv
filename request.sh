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
    # nohup ./download.sh Request >> ./outputs/scheduled.txt &
}

get_sleep_seconds() {
    target="$1"  # Format: "YYYY-MM-DD HH:MM"
    
    # Get current and target timestamps
    current_ts=$(date +%s)
    target_ts=$(date -j -f "%Y-%m-%d %H:%M" "$wait_until_time" +%s)
    
    # Calculate difference
    diff_seconds=$((target_ts - current_ts))
    
    # Return positive value only
    if [ $diff_seconds -lt 0 ]; then
        echo 0
    else
        echo $diff_seconds
    fi
}

# Example usage:
# sleep_seconds=$(get_sleep_seconds "2024-03-20 15:30")

echo "Wait Until Time: $wait_until_time"

# endless loop
while true; do
    sleep_for_seconds=$(get_sleep_seconds $wait_until_time)
    echo "Sleeping $sleep_for_seconds seconds"
    sleep $sleep_for_seconds

    # run the job
    run_job
    echo "Submitted job to background at $date"

    # wait until the next day
    wait_until_time=$(date -v+1d -j -f "%Y-%m-%d %H:%M" "$wait_until_time" "+%Y-%m-%d %H:%M")
done
