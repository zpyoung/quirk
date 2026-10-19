# split-branch/weigh.awk
# Weighs a `git diff -U0` stream line by line for split-branch's review budget and prints one JSON
# object: totals, directory groups, per-file rows. POSIX/BSD awk only (macOS ships no gawk).
#
# A changed line costs its file's weight, capped by every discount that applies to the line.
# Patterns and weights come from ENVIRON rather than -v, because -v processes backslash escapes
# and would turn a pattern's `\.` into `.`.

function min(a, b) { return a < b ? a : b }

function fmt(x,    s) {
    s = sprintf("%.4f", x)
    sub(/0+$/, "", s)
    sub(/\.$/, "", s)
    return s
}

function jesc(s) {
    gsub(/\\/, "\\\\", s)
    gsub(/"/, "\\\"", s)
    gsub(/\t/, "\\t", s)
    return s
}

function hunk_count(range,    i) {
    i = index(range, ",")
    return i ? substr(range, i + 1) + 0 : 1
}

function classify(fp) {
    if (exclude_re != "" && fp ~ exclude_re) return "excluded"
    if (fixture_re != "" && fp ~ fixture_re) return "fixture"
    if (fp ~ /(^|\/)(tests?|specs?|__tests__)\//) return "test"
    if (fp ~ /\.(test|spec)\.[a-zA-Z]+$/) return "test"
    if (fp ~ /(_test|Test)\.[a-zA-Z]+$/) return "test"
    if (risky_re != "" && fp ~ risky_re) return "risky"
    if (prose_re != "" && fp ~ prose_re) return "prose"
    return "source"
}

# Sets the file's comment syntax (fline: line-comment regex, fblock: block style), import
# language (flang), and whether leading whitespace is significant (findent).
function meta(f,    n, parts, base, ext) {
    if (f in fkind) return
    fkind[f] = fbin[f] ? "binary" : classify(fpath[f])
    n = split(fpath[f], parts, "/")
    base = tolower(parts[n])
    ext = ""
    if (index(base, ".") > 0) { ext = base; sub(/^.*\./, "", ext) }
    fline[f] = ""; fblock[f] = ""; flang[f] = ""; findent[f] = 0

    if (ext == "py" || ext == "pyi") {
        fline[f] = "^#"; fblock[f] = "py"; flang[f] = "py"; findent[f] = 1
    } else if (ext ~ /^(js|jsx|ts|tsx|mjs|cjs|mts|cts)$/) {
        fline[f] = "^//"; fblock[f] = "c"; flang[f] = "js"
    } else if (ext == "go") {
        fline[f] = "^//"; fblock[f] = "c"; flang[f] = "go"
    } else if (ext == "rs") {
        fline[f] = "^//"; fblock[f] = "c"; flang[f] = "rs"
    } else if (ext ~ /^(java|kt|kts|scala|swift|groovy)$/) {
        fline[f] = "^//"; fblock[f] = "c"; flang[f] = "jvm"
    } else if (ext ~ /^(c|h|cc|cpp|cxx|hpp|hh|m|mm)$/) {
        fline[f] = "^//"; fblock[f] = "c"; flang[f] = "c"
    } else if (ext == "cs") {
        fline[f] = "^//"; fblock[f] = "c"; flang[f] = "cs"
    } else if (ext == "php") {
        fline[f] = "^(//|#)"; fblock[f] = "c"; flang[f] = "php"
    } else if (ext == "dart") {
        fline[f] = "^//"; fblock[f] = "c"; flang[f] = "dart"
    } else if (ext ~ /^(css|scss|less)$/) {
        fline[f] = (ext == "css") ? "" : "^//"; fblock[f] = "c"
    } else if (ext == "tf" || ext == "hcl") {
        fline[f] = "^(#|//)"; fblock[f] = "c"
    } else if (ext == "rb" || ext == "rake") {
        fline[f] = "^#"; flang[f] = "rb"
    } else if (ext == "ex" || ext == "exs") {
        fline[f] = "^#"; flang[f] = "ex"
    } else if (ext ~ /^(yaml|yml|nim|coffee)$/) {
        fline[f] = "^#"; findent[f] = 1
    } else if (ext ~ /^(pug|haml)$/) {
        fline[f] = "^//"; findent[f] = 1
    } else if (base == "makefile" || base == "gnumakefile" || ext == "mk") {
        fline[f] = "^#"; findent[f] = 1
    } else if (ext ~ /^(sh|bash|zsh|fish|pl|pm|r|toml|conf|cfg|cmake)$/ || base ~ /^dockerfile/) {
        fline[f] = "^#"
    } else if (ext == "ini") {
        fline[f] = "^(;|#)"
    } else if (ext ~ /^(sql|lua|hs)$/) {
        fline[f] = "^--"; fblock[f] = (ext == "sql") ? "c" : ""
    } else if (ext ~ /^(el|clj|cljs|lisp|scm|asm)$/) {
        fline[f] = "^;"
    } else if (ext ~ /^(html|htm|xml|svg|md|mdx|vue)$/) {
        fblock[f] = "html"
    }
}

function is_import(f, s, t,    lang) {
    lang = flang[f]
    if (lang == "go") {
        if (in_goimp[s]) {
            if (t ~ /^\)/) in_goimp[s] = 0
            return 1
        }
        if (t ~ /^import[ \t]*\(/) { in_goimp[s] = 1; return 1 }
        return t ~ /^import[ \t]/
    }
    if (lang == "py") return t ~ /^import[ \t]/ || t ~ /^from[ \t]+[^ \t]+[ \t]+import[ \t]/
    if (lang == "js") return t ~ /^import[ \t{*"']/ || t ~ /^export[ \t].*[ \t]from[ \t]*["']/ || t ~ /^(const|let|var)[ \t].*=[ \t]*require\(/ || t ~ /^require\(/
    if (lang == "rs") return t ~ /^(pub(\([a-z]+\))?[ \t]+)?use[ \t]/ || t ~ /^extern[ \t]+crate[ \t]/
    if (lang == "jvm") return t ~ /^import[ \t]/
    if (lang == "c") return t ~ /^#[ \t]*(include|import)[ \t]*[<"]/
    if (lang == "cs") return t ~ /^(global[ \t]+)?using[ \t]+(static[ \t]+)?[A-Za-z_][A-Za-z0-9_.]*([ \t]*=[ \t]*[A-Za-z_][A-Za-z0-9_.]*)?[ \t]*;$/
    if (lang == "php") return t ~ /^use[ \t]+[A-Za-z\\]/ || t ~ /^(require|include)(_once)?[ \t(]/
    if (lang == "rb") return t ~ /^require(_relative)?[ \t(]/
    if (lang == "ex") return t ~ /^(import|alias|require|use)[ \t]+[A-Z]/
    if (lang == "dart") return t ~ /^(import|export)[ \t]+["']/
    return 0
}

# Block-comment and go-import state is per diff side, because -U0 hunks list removed lines
# before added ones and the two sides are separate texts.
function line_kind(f, s, text,    t, q) {
    t = text
    sub(/^[ \t]+/, "", t)
    sub(/[ \t\r]+$/, "", t)
    if (t == "") return "blank"

    if (fblock[f] == "c") {
        if (in_c[s]) {
            if (index(t, "*/")) in_c[s] = 0
            return "comment"
        }
        if (substr(t, 1, 2) == "/*") {
            if (!index(substr(t, 3), "*/")) in_c[s] = 1
            return "comment"
        }
        if (t == "*" || t ~ /^\*[ \/]/) return "comment"
    } else if (fblock[f] == "py") {
        if (in_py[s] != "") {
            if (index(t, in_py[s])) in_py[s] = ""
            return "comment"
        }
        q = substr(t, 1, 3)
        if (q == "\"\"\"" || q == "'''") {
            if (!index(substr(t, 4), q)) in_py[s] = q
            return "comment"
        }
    } else if (fblock[f] == "html") {
        if (in_html[s]) {
            if (index(t, "-->")) in_html[s] = 0
            return "comment"
        }
        if (substr(t, 1, 4) == "<!--") {
            if (!index(substr(t, 5), "-->")) in_html[s] = 1
            return "comment"
        }
    }

    if (fline[f] != "" && t ~ fline[f] && t !~ /^#!/) return "comment"
    if (is_import(f, s, t)) return "import"
    return "code"
}

# Indentation-significant files keep leading whitespace, so a Python re-indent stays a real change.
function norm(i,    t) {
    t = lt[i]
    if (findent[lf[i]]) sub(/[ \t\r]+$/, "", t)
    else gsub(/[ \t\r]/, "", t)
    return t
}

function alnum_count(s) { return gsub(/[A-Za-z0-9]/, "", s) }

function dir_of(fp,    i) {
    i = index(fp, "/")
    return i ? substr(fp, 1, i - 1) : "(root)"
}

BEGIN {
    exclude_re = ENVIRON["EXCLUDE_PATTERNS"]
    fixture_re = ENVIRON["FIXTURE_PATTERNS"]
    risky_re = ENVIRON["RISKY_PATTERNS"]
    prose_re = ENVIRON["PROSE_PATTERNS"]

    fw["source"] = 1
    fw["excluded"] = 0
    fw["binary"] = 0
    fw["test"] = ENVIRON["TEST_WEIGHT"] + 0
    fw["fixture"] = ENVIRON["FIXTURE_WEIGHT"] + 0
    fw["risky"] = ENVIRON["RISKY_WEIGHT"] + 0
    fw["prose"] = ENVIRON["PROSE_WEIGHT"] + 0
    w_comment = ENVIRON["COMMENT_WEIGHT"] + 0
    w_import = ENVIRON["IMPORT_WEIGHT"] + 0
    w_moved = ENVIRON["MOVED_WEIGHT"] + 0
    w_deletion = ENVIRON["DELETION_WEIGHT"] + 0

    # git's own --color-moved minimum, so short lines like `}` never count as moved
    min_moved_alnum = 20

    nf = 0; nl = 0; nh = 0; in_hunk = 0
}

/^diff --git / {
    nf++
    path = $0
    sub(/^.* b\//, "", path)
    fpath[nf] = path
    fadd[nf] = 0; fdel[nf] = 0; fbin[nf] = 0
    old_path = ""
    in_hunk = 0
    next
}

in_hunk {
    c = substr($0, 1, 1)
    if (c == "\\") next
    if (c == "-" || c == "+") {
        nl++
        lf[nl] = nf; lh[nl] = nh; ls[nl] = c; lt[nl] = substr($0, 2)
        lk[nl] = line_kind(nf, c, lt[nl])
        if (c == "+") { fadd[nf]++; rem_new-- } else { fdel[nf]++; rem_old-- }
        if (rem_old <= 0 && rem_new <= 0) in_hunk = 0
        next
    }
    in_hunk = 0
}

/^@@ / {
    meta(nf)
    split($0, hp, " ")
    rem_old = hunk_count(hp[2])
    rem_new = hunk_count(hp[3])
    nh++
    in_hunk = (rem_old > 0 || rem_new > 0)
    in_c["-"] = 0; in_c["+"] = 0
    in_py["-"] = ""; in_py["+"] = ""
    in_html["-"] = 0; in_html["+"] = 0
    in_goimp["-"] = 0; in_goimp["+"] = 0
    next
}

/^--- / {
    p = substr($0, 5)
    if (p != "/dev/null") { sub(/^a\//, "", p); old_path = p }
    next
}

/^\+\+\+ / {
    p = substr($0, 5)
    if (p == "/dev/null") fpath[nf] = old_path
    else { sub(/^b\//, "", p); fpath[nf] = p }
    next
}

/^rename to / { fpath[nf] = substr($0, 11); next }

/^Binary files / { fbin[nf] = 1; next }

END {
    for (f = 1; f <= nf; f++) meta(f)

    # a removed/added pair with equal normalized text in one hunk is a whitespace-only edit
    for (i = 1; i <= nl; i++) {
        if (ls[i] != "+" || lk[i] == "blank") continue
        k = lh[i] SUBSEP norm(i)
        ws_q[k, ++ws_n[k]] = i
    }
    for (i = 1; i <= nl; i++) {
        if (ls[i] != "-" || lk[i] == "blank") continue
        k = lh[i] SUBSEP norm(i)
        if ((k in ws_n) && ws_used[k] < ws_n[k]) {
            j = ws_q[k, ++ws_used[k]]
            pair[i] = "ws"; pair[j] = "ws"
        }
    }

    # any other equal pair, anywhere in the diff, is a move
    for (i = 1; i <= nl; i++) {
        if (ls[i] != "+" || lk[i] == "blank" || (i in pair)) continue
        k = norm(i)
        if (alnum_count(k) < min_moved_alnum) continue
        mv_q[k, ++mv_n[k]] = i
    }
    for (i = 1; i <= nl; i++) {
        if (ls[i] != "-" || lk[i] == "blank" || (i in pair)) continue
        k = norm(i)
        if ((k in mv_n) && mv_used[k] < mv_n[k]) {
            j = mv_q[k, ++mv_used[k]]
            pair[i] = "moved"; pair[j] = "moved"
        }
    }

    split("code comment import moved whitespace_only blank", line_kinds, " ")
    for (n = 1; n <= 6; n++) kind_lines[line_kinds[n]] = 0
    total_weight = 0

    for (i = 1; i <= nl; i++) {
        f = lf[i]
        p = (i in pair) ? pair[i] : ""
        if (lk[i] == "blank") kind = "blank"
        else if (p == "ws") kind = "whitespace_only"
        else if (p == "moved") kind = "moved"
        else kind = lk[i]
        kind_lines[kind]++

        if (kind == "blank" || kind == "whitespace_only") wt = 0
        else {
            wt = fw[fkind[f]]
            if (p == "moved") wt = min(wt, w_moved)
            if (lk[i] == "comment") wt = min(wt, w_comment)
            if (lk[i] == "import") wt = min(wt, w_import)
            if (ls[i] == "-") wt = min(wt, w_deletion)
        }
        fweight[f] += wt
        total_weight += wt
    }

    split("source test excluded fixture risky prose", file_kinds, " ")
    for (n = 1; n <= 6; n++) raw[file_kinds[n]] = 0
    total_added = 0; total_deleted = 0
    ndirs = 0
    for (f = 1; f <= nf; f++) {
        lines = fadd[f] + fdel[f]
        total_added += fadd[f]; total_deleted += fdel[f]
        raw[fkind[f]] += lines
        d = dir_of(fpath[f])
        if (!(d in dir_seen)) { dir_seen[d] = 1; dirs[++ndirs] = d }
        dir_raw[d, fkind[f]] += lines
        dir_weight[d] += fweight[f]
        dir_files[d]++
    }

    for (i = 1; i <= ndirs; i++)
        for (j = i + 1; j <= ndirs; j++)
            if (dirs[j] < dirs[i]) { tmp = dirs[i]; dirs[i] = dirs[j]; dirs[j] = tmp }

    print "{"
    printf "  \"total_files\": %d,\n", nf
    printf "  \"total_lines_added\": %d,\n", total_added
    printf "  \"total_lines_deleted\": %d,\n", total_deleted
    printf "  \"total_lines\": %d,\n", total_added + total_deleted
    for (n = 1; n <= 6; n++) printf "  \"total_%s_lines\": %d,\n", file_kinds[n], raw[file_kinds[n]]
    for (n = 1; n <= 6; n++) printf "  \"total_%s_lines\": %d,\n", line_kinds[n], kind_lines[line_kinds[n]]
    printf "  \"weighted_review_lines\": %d,\n", int(total_weight + 0.5)
    printf "  \"weights\": {\"source\": 1, \"test\": %s, \"fixture\": %s, \"risky\": %s, \"prose\": %s, \"excluded\": 0, \"comment\": %s, \"import\": %s, \"moved\": %s, \"deletion\": %s, \"blank\": 0, \"whitespace_only\": 0},\n", \
        fmt(fw["test"]), fmt(fw["fixture"]), fmt(fw["risky"]), fmt(fw["prose"]), fmt(w_comment), fmt(w_import), fmt(w_moved), fmt(w_deletion)

    print "  \"directory_groups\": ["
    for (i = 1; i <= ndirs; i++) {
        d = dirs[i]
        printf "    {\"directory\": \"%s\"", jesc(d)
        for (n = 1; n <= 6; n++) printf ", \"%s_lines\": %d", file_kinds[n], dir_raw[d, file_kinds[n]]
        printf ", \"weighted_lines\": %s, \"file_count\": %d}%s\n", fmt(dir_weight[d]), dir_files[d], (i < ndirs ? "," : "")
    }
    print "  ],"

    print "  \"files\": ["
    for (f = 1; f <= nf; f++) {
        added = fbin[f] ? "-" : fadd[f]
        deleted = fbin[f] ? "-" : fdel[f]
        printf "    {\"file\": \"%s\", \"added\": \"%s\", \"deleted\": \"%s\", \"kind\": \"%s\", \"weighted_lines\": %s}%s\n", \
            jesc(fpath[f]), added, deleted, fkind[f], fmt(fweight[f]), (f < nf ? "," : "")
    }
    print "  ],"

    print "  \"excluded_files\": ["
    first = 1
    for (f = 1; f <= nf; f++) {
        if (fkind[f] != "excluded") continue
        printf "%s    \"%s\"", (first ? "" : ",\n"), jesc(fpath[f])
        first = 0
    }
    if (!first) printf "\n"
    print "  ]"
    print "}"
}
