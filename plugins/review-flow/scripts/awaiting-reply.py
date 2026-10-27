#!/usr/bin/env python3
"""List the pull-request conversation items still waiting on a reply from the viewer.

Input is `gh api graphql --paginate --slurp` output for review threads, reviews and issue
comments. A thread waits while its last word is not the viewer's; a review body or top-level
comment waits until a later viewer comment links its anchor or quote-replies its first line.
GitHub timestamps share one UTC format, so they compare as strings.
"""
import argparse
import json
import re
import sys

CONNECTIONS = {"threads": "reviewThreads", "reviews": "reviews", "comments": "comments"}
ANCHORS = {"review": "#pullrequestreview-{}", "comment": "#issuecomment-{}"}


def who(author):
    if not author:
        return "ghost", False
    return author["login"], author.get("__typename") == "Bot"


def first_line(body):
    return next((l.strip() for l in body.splitlines() if l.strip()), "")


def quoted(body):
    return {l.lstrip()[1:].strip() for l in body.splitlines() if l.lstrip().startswith(">")}


def answers(reply, kind, node):
    anchor = re.escape(ANCHORS[kind].format(node["databaseId"])) + r"(?!\d)"
    return bool(re.search(anchor, reply["body"])) or first_line(node["body"]) in quoted(reply["body"])


def awaiting(threads, reviews, comments, viewer):
    me = viewer.lower()
    mine = [x for x in comments if who(x.get("author"))[0].lower() == me]
    items = []
    for t in threads:
        cs = t["comments"]["nodes"]
        if t["isResolved"] or not cs:
            continue
        last, _ = who(cs[-1].get("author"))
        if last.lower() == me:
            continue
        root, bot = who(cs[0].get("author"))
        items.append({
            "id": f"thread:{t['id']}", "kind": "thread", "url": cs[-1]["url"],
            "author": root, "last_author": last, "bot": bot, "at": cs[-1]["createdAt"],
            "path": t.get("path"),
            "line": t["line"] if t.get("line") is not None else t.get("originalLine"),
            "outdated": t["isOutdated"],
            "truncated": t["comments"]["pageInfo"]["hasNextPage"],
            "reply_to": cs[0]["databaseId"],
            "conversation": [{"author": who(x.get("author"))[0], "body": x["body"]} for x in cs],
        })
    for kind, nodes, stamp in (("review", reviews, "submittedAt"), ("comment", comments, "createdAt")):
        for n in nodes:
            login, bot = who(n.get("author"))
            if login.lower() == me or not n["body"].strip():
                continue
            if any(r["createdAt"] > n[stamp] and answers(r, kind, n) for r in mine):
                continue
            item = {
                "id": f"{kind}:{n['databaseId']}", "kind": kind, "url": n["url"],
                "author": login, "last_author": login, "bot": bot, "at": n[stamp],
                "conversation": [{"author": login, "body": n["body"]}],
            }
            if kind == "review":
                item["state"] = n["state"]
            items.append(item)
    return sorted(items, key=lambda i: i["at"])


def die(msg):
    print(msg, file=sys.stderr)
    sys.exit(2)


def load(path, conn):
    with open(path) as f:
        pages = json.load(f)
    if not isinstance(pages, list):
        die(f"{path}: expected the --slurp array of pages")
    nodes = []
    for p in pages:
        pr = p["data"]["repository"]["pullRequest"]
        if pr is None:
            die(f"pull request not found in {path}")
        nodes.extend(pr[conn]["nodes"])
    return nodes


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--viewer", required=True)
    for flag in CONNECTIONS:
        ap.add_argument(f"--{flag}", required=True)
    a = ap.parse_args()
    lists = {k: load(getattr(a, k), conn) for k, conn in CONNECTIONS.items()}
    json.dump(awaiting(lists["threads"], lists["reviews"], lists["comments"], a.viewer),
              sys.stdout, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
