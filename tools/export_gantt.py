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
              content {
                __typename
                ... on Issue {
                  title
                  closedAt
                  milestone { title dueOn }
                }
                ... on PullRequest {
                  title
                  closedAt
                  milestone { title dueOn }
                }
                ... on DraftIssue {
                  title
                }
              }
              fieldValues(first: 20) {
                nodes {
                  __typename
                  ... on ProjectV2ItemFieldTextValue { text field { ... on ProjectV2FieldCommon { name } } }
                  ... on ProjectV2ItemFieldDateValue { date field { ... on ProjectV2FieldCommon { name } } }
                  ... on ProjectV2ItemFieldSingleSelectValue { name field { ... on ProjectV2FieldCommon { name } } }
                  ... on ProjectV2ItemFieldMilestoneValue { milestone { title dueOn } field { ... on ProjectV2FieldCommon { name } } }
                  ... on ProjectV2ItemFieldIterationValue { title startDate duration field { ... on ProjectV2FieldCommon { name } } }
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


def extract_milestone(node):
    """Extract milestone info (title, dueOn) from node content (Issue/PR) or fieldValues."""
    # First try content.milestone (GitHub repo milestone on Issue/PR)
    content = node.get("content")
    if content and content.get("milestone"):
        ms = content["milestone"]
        return {"title": ms.get("title"), "due": ms.get("dueOn")}

    # Fallback to fieldValues (Project field milestone)
    fields = (node.get("fieldValues") or {}).get("nodes") or []
    for f in fields:
        if f.get("__typename") == "ProjectV2ItemFieldMilestoneValue":
            ms = f.get("milestone")
            if ms:
                return {"title": ms.get("title"), "due": ms.get("dueOn")}
    return None


def extract_iteration(fields):
    """Extract iteration info (title, startDate, duration) from fields."""
    for f in fields:
        if f.get("__typename") == "ProjectV2ItemFieldIterationValue":
            return {
                "title": f.get("title"),
                "start": f.get("startDate"),
                "duration": f.get("duration"),
            }
    return None


def parse_date(s):
    if not s:
        return None
    try:
        # Handle ISO format with timezone (e.g., "2026-06-14T00:00:00Z")
        if "T" in s:
            s = s.split("T")[0]
        return date.fromisoformat(s)
    except ValueError:
        return None


def escape(s):
    return re.sub(r"[\n\r:]+", " ", s).strip()


def fetch_repo_milestones(token, owner, repo):
    """Fetch milestones directly from a repository."""
    query = """
    query($owner: String!, $repo: String!) {
      repository(owner: $owner, name: $repo) {
        milestones(first: 100, states: [OPEN, CLOSED]) {
          nodes {
            title
            dueOn
            description
          }
        }
      }
    }
    """
    resp = graphql(token, query, {"owner": owner, "repo": repo})
    if "errors" in resp:
        die(f"GraphQL error: {resp['errors']}")
    repo_data = resp.get("data", {}).get("repository")
    if not repo_data:
        die(f"Repository {owner}/{repo} not found or no access")
    return repo_data.get("milestones", {}).get("nodes", [])


def main():
    parser = argparse.ArgumentParser(description="Export GitHub Project to Mermaid Gantt")
    parser.add_argument("--login", required=True, help="GitHub username")
    parser.add_argument("--project", type=int, required=True, help="Project number")
    parser.add_argument("--repo", help="Repository (owner/name) to fetch milestones from")
    parser.add_argument("--group", default="Subject", help="Field to group by")
    parser.add_argument("--start", default="Start date", help="Start date field")
    parser.add_argument("--default-duration", type=int, default=7, help="Default duration in days for tasks without end date")
    parser.add_argument("--min-duration", type=int, default=3, help="Minimum visual duration in days for short tasks")
    parser.add_argument("--list", action="store_true", help="List all items (debug)")
    parser.add_argument("--include-undated", action="store_true", help="Include tasks without dates (uses today)")
    args = parser.parse_args()

    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not token:
        die("Set GITHUB_TOKEN or GH_TOKEN")

    title, raw = fetch_items(token, args.login, args.project)

    # Debug: list all items
    if args.list:
        print(f"Project: {title}")
        print(f"Items: {len(raw)}")
        for i, node in enumerate(raw):
            fields = (node.get("fieldValues") or {}).get("nodes") or []
            name = extract_field(fields, "Title") or "(no title)"
            ms = extract_milestone(node)
            it = extract_iteration(fields)
            start = extract_field(fields, args.start)
            end = extract_field(fields, args.end)
            group = extract_field(fields, args.group)
            print(f"\n{i+1}. {name}")
            print(f"   Raw node: {node}")
            print(f"   Group: {group or '-'}")
            print(f"   Start: {start or '-'}, End: {end or '-'}")
            if ms:
                print(f"   Milestone: {ms['title']} (due: {ms['due'] or '-'})")
            if it:
                print(f"   Iteration: {it['title']} (start: {it['start']}, {it['duration']} days)")
        return

    # Parse items into tasks and milestones
    tasks = []
    milestones = {}  # title -> due date
    today = date.today()

    # Fetch milestones from repo if specified
    if args.repo:
        parts = args.repo.split("/")
        if len(parts) != 2:
            die("--repo must be in format owner/name")
        owner, repo_name = parts
        repo_milestones = fetch_repo_milestones(token, owner, repo_name)
        for ms in repo_milestones:
            ms_due = parse_date(ms.get("dueOn"))
            if ms_due and ms.get("title"):
                milestones[ms["title"]] = ms_due

    for node in raw:
        fields = (node.get("fieldValues") or {}).get("nodes") or []
        content = node.get("content") or {}
        name = extract_field(fields, "Title")
        if not name:
            continue

        # Check for milestone
        ms = extract_milestone(node)
        if ms and ms.get("title"):
            ms_due = parse_date(ms.get("due"))
            if ms_due and ms["title"] not in milestones:
                milestones[ms["title"]] = ms_due

        # Check for iteration (can use as date source)
        it = extract_iteration(fields)

        start = parse_date(extract_field(fields, args.start))

        # End date priority: closedAt > Target date > default duration
        closed_at = parse_date(content.get("closedAt"))
        target_date = parse_date(extract_field(fields, "Target date"))
        end = closed_at or target_date

        # Fallback to iteration dates if no start/end
        if not start and not end and it:
            start = parse_date(it.get("start"))
            if start and it.get("duration"):
                from datetime import timedelta
                end = start + timedelta(days=int(it["duration"]))

        # Handle tasks without dates
        if not start and not end:
            if args.include_undated:
                # Use today as start, with default duration
                start = today
            else:
                continue

        if not start:
            start = end
        if not end:
            # Give task a default duration
            from datetime import timedelta
            end = start + timedelta(days=args.default_duration)

        # Ensure minimum visual duration
        from datetime import timedelta
        if (end - start).days < args.min_duration:
            end = start + timedelta(days=args.min_duration)

        group = extract_field(fields, args.group) or "Other"
        tasks.append({"name": escape(name), "group": escape(group), "start": start, "end": end})

    if not tasks and not milestones:
        die("No tasks found")

    # Group tasks
    groups = {}
    for t in tasks:
        groups.setdefault(t["group"], []).append(t)

    # Calculate max group name length for leftPadding
    max_group_name_len = max((len(task["group"]) for task in tasks), default=0)
    if milestones:
        max_group_name_len = max(max_group_name_len, len("Milestones"))
    # Rough estimate: ~6-7 pixels per character, aim for padding
    left_padding = max(150, min(500, max_group_name_len * 7))

    # Output
    print("```mermaid")
    print(f"%%{{init: {{'gantt': {{'leftPadding': {left_padding}}}}}}}%%")
    print("gantt")
    print(f"  title {escape(title)}")
    print("  dateFormat YYYY-MM-DD")
    print()

    # Milestones section
    if milestones:
        print("  section Milestones")
        for ms_title, ms_due in sorted(milestones.items(), key=lambda x: x[1]):
            print(f"  {escape(ms_title)} : milestone, m{hash(ms_title) % 1000}, {ms_due}, 0d")
        print()

    # Task sections
    for g in sorted(groups.keys()):
        print(f"  section {g}")
        for t in sorted(groups[g], key=lambda x: x["start"]):
            print(f"  {t['name']} : {t['start']}, {t['end']}")
        print()
    print("```")


if __name__ == "__main__":
    main()
