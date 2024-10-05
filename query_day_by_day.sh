#!/bin/zsh

from=${1}
to=${2}

# Function to check if a date is in the correct format
validate_date() {
    local input_date=$1
    if [[ $input_date =~ ^[0-9]{4}-(0[1-9]|1[0-2])-(0[1-9]|[12][0-9]|3[01])$ ]]; then
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
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS
        local seconds1=$(date -j -f "%Y-%m-%d" "$date1" "+%s")
        local seconds2=$(date -j -f "%Y-%m-%d" "$date2" "+%s")
    else
        # Linux
        local seconds1=$(date -d "$date1" +%s)
        local seconds2=$(date -d "$date2" +%s)
    fi

    # Compute the delta in seconds
    local delta_seconds=$((seconds2 - seconds1))

    # Convert the delta in seconds to days
    local delta_days=$((delta_seconds / 86400))

    echo $delta_days
}

# Function to add days to a date
add_days_to_date() {
    local start_date=$1
    local days_to_add=$2

    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS
        date -j -v +"$days_to_add"d -f "%Y-%m-%d" "$start_date" "+%Y-%m-%d"
    else
        # Linux
        date -d "$start_date + $days_to_add days" "+%Y-%m-%d"
    fi
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
echo "# Query arxiv from $date1 (include) to $date2 (include). $delta_days days in total."

for delta in $(seq 0 $delta_days); do
    current_date=$(add_days_to_date "$date1" "$delta")
    # echo $current_date
    python arxiver/main.py --datetime $current_date --translate --batch_mode --model "zhipuai-glm-4-flash"
    sleep 3  # Sleep for 3 seconds before next arxiv query
done
