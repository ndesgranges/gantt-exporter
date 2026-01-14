#!/usr/bin/env python3
"""Simple GitHub Project → Mermaid Gantt exporter."""

import argparse
import json
import os
import re
import sys
import urllib.request
import urllib.error
from datetime import date

GRAPHQL_URL = "https://api.github.com/graphql"


def die(msg):
    print(f"error: {msg}", file=sys.stderr)
    sys.exit(1)


def graphql(token, query, variables):
    data = json.dumps({"query": query, "variables": variables}).encode()
    req = urllib.request.Request(GRAPHQL_URL, data=data, method="POST")
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        die(f"GitHub API error {e.code}: {e.read().decode()}")


def fetch_items(token, login, project_number):
    query = """
    query($login: String!, $num: Int!, $after: String) {
      user(login: $login) {
        projectV2(number: $num) {
          title
          items(first: 100, after: $after) {
            pageInfo { hasNextPage endCursor }
            nodes {
              fieldValues(first: 20) {
                nodes {
                  __typename
                  ... on ProjectV2ItemFieldTextValue { text field { ... on ProjectV2FieldCommon { name } } }
                  ... on ProjectV2ItemFieldDateValue { date field { ... on ProjectV2FieldCommon { name } } }
                  ... on ProjectV2ItemFieldSingleSelectValue { name field { ... on ProjectV2FieldCommon { name } } }
                }
              }
            }
          }
        }
      }
    }
    """
    items = []
    after = None
    title = ""
    while True:
        resp = graphql(token, query, {"login": login, "num": project_number, "after": after})
        proj = resp["data"]["user"]["projectV2"]
        title = proj["title"]
        for node in proj["items"]["nodes"]:
            items.append(node)
        page = proj["items"]["pageInfo"]
        if not page["hasNextPage"]:
            break
        after = page["endCursor"]
    return title, items


def extract_field(fields, name):
    for f in fields:
        field_meta = f.get("field")
        if not field_meta:
            continue
        if field_meta.get("name") == name:
            return f.get("text") or f.get("date") or f.get("name")
    return None


def parse_date(s):
    if not s:
        return None
    try:
        return date.fromisoformat(s)
    except ValueError:
        return None


def escape(s):
    return re.sub(r"[\n\r:]+", " ", s).strip()


def main():
    parser = argparse.ArgumentParser(description="Export GitHub Project to Mermaid Gantt")
    parser.add_argument("--login", required=True, help="GitHub username")
    parser.add_argument("--project", type=int, required=True, help="Project number")
    parser.add_argument("--group", default="Subject", help="Field to group by")
    parser.add_argument("--start", default="Start date", help="Start date field")
    parser.add_argument("--end", default="End date", help="End date field")
    args = parser.parse_args()

    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not token:
        die("Set GITHUB_TOKEN or GH_TOKEN")

    title, raw = fetch_items(token, args.login, args.project)

    # Parse items
    tasks = []
    for node in raw:
        fields = (node.get("fieldValues") or {}).get("nodes") or []
        name = extract_field(fields, "Title")
        if not name:
            continue
        start = parse_date(extract_field(fields, args.start))
        end = parse_date(extract_field(fields, args.end))
        if not start and not end:
            continue
        if not start:
            start = end
        if not end:
            end = start
        group = extract_field(fields, args.group) or "Other"
        tasks.append({"name": escape(name), "group": escape(group), "start": start, "end": end})

    if not tasks:
        die("No tasks with dates found")

    # Group
    groups = {}
    for t in tasks:
        groups.setdefault(t["group"], []).append(t)

    # Output
    print("```mermaid")
    print("gantt")
    print(f"  title {escape(title)}")
    print("  dateFormat YYYY-MM-DD")
    print()
    for g in sorted(groups.keys()):
        print(f"  section {g}")
        for t in sorted(groups[g], key=lambda x: x["start"]):
            print(f"  {t['name']} : {t['start']}, {t['end']}")
        print()
    print("```")


if __name__ == "__main__":
    main()
