#!/bin/bash

from=${1}
to=${2}

# Function to check if a date is in the correct format
validate_date() {
    local date=$1
    if [[ $date =~ ^[0-9]{4}-(0[1-9]|1[0-2])-(0[1-9]|[12][0-9]|3[01])$ ]]; then
        return 0
    else
        return 1
    fi
}

# Function to compute the delta days between two dates
compute_delta_days() {
    local date1=$1
    local date2=$2

    # Convert the dates to seconds since the epoch
    local seconds1=$(date -d "$date1" +%s)
    local seconds2=$(date -d "$date2" +%s)

    # Compute the delta in seconds
    local delta_seconds=$((seconds2 - seconds1))

    # Convert the delta in seconds to days
    local delta_days=$((delta_seconds / 86400))

    echo $delta_days
}

# Prompt the user for two dates
date1=${from}
date2=${to}

# Validate the dates
if ! validate_date "$date1"; then
    echo "Error: '$date1' is not a valid date in the format YYYY-MM-DD."
    exit 1
fi

if ! validate_date "$date2"; then
    echo "Error: '$date2' is not a valid date in the format YYYY-MM-DD."
    exit 1
fi

# Compute the delta days
delta_days=$(compute_delta_days "$date1" "$date2")

# Output the result
echo "Query arxiv from $date1 (include) to $date2 (include). $delta_days days in total."

for delta in $(seq 0 $delta_days); do
    date=$(date -d "$date1 + $delta days" +%Y-%m-%d)
    # echo $date
    python main.py --datetime $date
    sleep 3  # Sleep for 3 seconds before next arxiv query
done
