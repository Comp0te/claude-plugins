# Per-file hunk ranges and added lines of a combined diff (`gh pr diff <N>`, never --patch),
# in new-file coordinates: one unindented path per file, then "  H: a-b ..." and "  A: n ...".
# Must run on macOS /usr/bin/awk (one-true-awk): no two-argument split, no gawk extensions.
# Fixtures: tests/review-flow/hunk-map/, run by scripts/check-hunk-map.py.

# +++/--- are headers only between `diff --git` and the first @@; after it, an added line
# whose text starts with "++ " arrives as "+++ " and must not open a new file.
/^diff --git/ { inhdr=1; next }
inhdr && /^--- /    { next }
inhdr && /^\+\+\+ / { f=$2; sub(/^b\//,"",f);
                      if (f=="/dev/null") { file=""; inhdr=0; next }
                      file=f; order[++k]=file; inhdr=0; next }
/^@@/ { inhdr=0; match($0, /\+[0-9]+(,[0-9]+)?/); h=substr($0,RSTART+1,RLENGTH-1);
        split(h, b, ","); nl=b[1]+0; len=(b[2]==""?1:b[2]+0);
        hunks[file]=hunks[file] " " nl "-" (nl+len-1); cur=nl; next }
/^\+/ { adds[file]=adds[file] " " cur; cur++; next }
/^-/  { next }
/^ /  { cur++; next }
END { for (j=1;j<=k;j++) { f=order[j]; print f; print "  H:" hunks[f]; print "  A:" adds[f] } }
