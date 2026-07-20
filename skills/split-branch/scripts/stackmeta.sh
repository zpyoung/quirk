#!/usr/bin/env bash
# Emit, parse, and update split-branch stack metadata in PR/MR bodies.
# This file may be sourced as a library or run as a command.

set -euo pipefail

STACKMETA_START='<!-- split-branch:stack -->'
STACKMETA_END='<!-- /split-branch:stack -->'

# Values supplied by callers are arguments, so invalid values return 5. Exit 3
# is reserved for malformed metadata read from a body.
_stackmeta_validate_values() {
    if [[ $# -ne 4 ]]; then
        return 5
    fi

    local parent="$1"
    local base_sha="$2"
    local position="$3"
    local total="$4"

    [[ -n "$parent" && "$parent" != *$'\n'* && "$parent" != *$'\r'* ]] || return 5
    [[ "$base_sha" =~ ^[0-9A-Fa-f]{40}$ ]] || return 5
    [[ "$position" =~ ^[0-9]+$ && "$total" =~ ^[0-9]+$ ]] || return 5
}

stackmeta_emit() {
    if [[ $# -ne 4 ]]; then
        return 5
    fi
    _stackmeta_validate_values "$@" || return 5

    local parent="$1"
    local base_sha="$2"
    local position="$3"
    local total="$4"

    printf '%s\nparent: %s\nbase-sha: %s\nposition: %s/%s\n%s\n' \
        "$STACKMETA_START" "$parent" "$base_sha" "$position" "$total" "$STACKMETA_END"
}

# Validate a body and optionally print one field. With an empty field, print the
# opening and closing line numbers for use by stackmeta_upsert.
_stackmeta_read() {
    local field="$1"
    local body_file="${2:--}"

    awk -v wanted="$field" -v start_marker="$STACKMETA_START" -v end_marker="$STACKMETA_END" '
        $0 == start_marker {
            starts++
            if (starts == 1) {
                in_block = 1
                start_line = NR
            }
            next
        }
        $0 == end_marker {
            ends++
            if (in_block && ends == 1) {
                in_block = 0
                end_line = NR
            }
            next
        }
        in_block && index($0, "parent: ") == 1 {
            parent_count++
            parent = substr($0, 9)
            next
        }
        in_block && index($0, "base-sha: ") == 1 {
            sha_count++
            sha = substr($0, 11)
            next
        }
        in_block && index($0, "position: ") == 1 {
            position_count++
            position = substr($0, 11)
            next
        }
        END {
            # Multiple openings represent multiple attempted blocks. Orphan or
            # excess closing markers are malformed metadata, not extra blocks.
            if (starts > 1) exit 4
            if (starts == 0 && ends == 0) exit 2
            if (starts != 1 || ends != 1 || !start_line || !end_line || end_line < start_line ||
                parent_count != 1 || sha_count != 1 || position_count != 1 ||
                parent == "" || position == "" || length(sha) != 40 || sha ~ /[^0-9A-Fa-f]/) exit 3

            if (wanted == "parent") print parent
            else if (wanted == "base-sha") print sha
            else if (wanted == "position") print position
            else print start_line, end_line
        }
    ' "$body_file"
}

stackmeta_parse() {
    if [[ $# -ne 1 ]]; then
        return 5
    fi

    case "$1" in
        parent|base-sha|position) ;;
        *) return 5 ;;
    esac

    _stackmeta_read "$1"
}

stackmeta_upsert() {
    if [[ $# -ne 4 ]]; then
        return 5
    fi
    _stackmeta_validate_values "$@" || return 5

    local parent="$1"
    local base_sha="$2"
    local position="$3"
    local total="$4"
    local body_file
    local location_file
    body_file=$(mktemp "${TMPDIR:-/tmp}/stackmeta-body.XXXXXX")
    location_file=$(mktemp "${TMPDIR:-/tmp}/stackmeta-location.XXXXXX")
    cat >"$body_file"

    local read_status=0
    if _stackmeta_read "" "$body_file" >"$location_file"; then
        read_status=0
    else
        read_status=$?
    fi

    if [[ $read_status -eq 0 ]]; then
        local start_line
        local end_line
        read -r start_line end_line <"$location_file"

        if [[ $start_line -gt 1 ]]; then
            head -n $((start_line - 1)) "$body_file"
        fi
        stackmeta_emit "$parent" "$base_sha" "$position" "$total"
        tail -n "+$((end_line + 1))" "$body_file"
    elif [[ $read_status -eq 2 ]]; then
        cat "$body_file"
        if [[ -s "$body_file" ]]; then
            local final_byte
            final_byte=$(tail -c 1 "$body_file" | od -An -t u1 | tr -d ' ')
            if [[ "$final_byte" == "10" ]]; then
                printf '\n'
            else
                printf '\n\n'
            fi
        fi
        stackmeta_emit "$parent" "$base_sha" "$position" "$total"
    else
        rm -f "$body_file" "$location_file"
        return "$read_status"
    fi

    rm -f "$body_file" "$location_file"
}

_stackmeta_main() {
    if [[ $# -lt 1 ]]; then
        return 5
    fi

    local command="$1"
    shift
    case "$command" in
        emit) stackmeta_emit "$@" ;;
        parse) stackmeta_parse "$@" ;;
        upsert) stackmeta_upsert "$@" ;;
        *) return 5 ;;
    esac
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
    _stackmeta_main "$@"
fi
