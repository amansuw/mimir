"""
Jira API interaction functions.
Handles fetching, normalizing, and grouping issues.
"""

import requests
from requests.auth import HTTPBasicAuth
from datetime import datetime
from dateutil.relativedelta import relativedelta

from config import (
    JIRA_BASE_URL, JIRA_EMAIL, JIRA_API_TOKEN,
    START_DATE, END_DATE
)


def get_auth():
    """Get HTTP Basic Auth for Jira API."""
    return HTTPBasicAuth(JIRA_EMAIL, JIRA_API_TOKEN)


def get_headers():
    """Get headers for Jira API requests."""
    return {
        "Accept": "application/json",
        "Content-Type": "application/json"
    }


def build_jql(start_date, end_date):
    """Build JQL query to get all issues user worked on in a date range.
    
    Includes:
    - Issues assigned to user
    - Issues reported by user
    - Issues created by user
    - Issues user is watching
    - Issues where user logged work
    
    Based on Jira's "Worked on" view JQL pattern.
    """
    jql_parts = [
        'assignee = currentUser()',
        'reporter = currentUser()',
        'creator = currentUser()',
        'watcher = currentUser()',
        'worklogAuthor = currentUser()'
    ]
    
    jql = f'({" OR ".join(jql_parts)}) AND updated >= "{start_date}" AND updated <= "{end_date}"'
    jql += ' ORDER BY updated DESC'
    return jql


def fetch_issues_page(jql, start_at=0, max_results=50):
    """Fetch a page of issues from Jira using the new search/jql endpoint."""
    url = f"{JIRA_BASE_URL}/rest/api/3/search/jql"
    
    params = {
        "jql": jql,
        "startAt": start_at,
        "maxResults": max_results,
        "expand": "changelog",
        "fields": "*all"
    }
    
    response = requests.get(
        url,
        headers=get_headers(),
        auth=get_auth(),
        params=params
    )
    response.raise_for_status()
    return response.json()


def fetch_all_issues():
    """Fetch all issues for the configured date range, month by month."""
    all_issues = []
    
    # Parse dates
    start = datetime.strptime(START_DATE, "%Y-%m-%d")
    end = datetime.strptime(END_DATE, "%Y-%m-%d") if END_DATE else datetime.now()
    
    # Iterate month by month
    current_start = start
    while current_start < end:
        current_end = min(current_start + relativedelta(months=1) - relativedelta(days=1), end)
        
        start_str = current_start.strftime("%Y-%m-%d")
        end_str = current_end.strftime("%Y-%m-%d")
        
        print(f"  Fetching {start_str} to {end_str}...", end=" ")
        
        jql = build_jql(start_str, end_str)
        
        # Paginate through all results for this month
        start_at = 0
        month_issues = []
        
        while True:
            data = fetch_issues_page(jql, start_at=start_at)
            issues = data.get("issues", [])
            month_issues.extend(issues)
            
            if start_at + len(issues) >= data.get("total", 0):
                break
            start_at += len(issues)
        
        print(f"found {len(month_issues)} issues")
        all_issues.extend(month_issues)
        
        current_start = current_end + relativedelta(days=1)
    
    # Deduplicate by issue key
    seen_keys = set()
    unique_issues = []
    for issue in all_issues:
        key = issue.get("key")
        if key not in seen_keys:
            seen_keys.add(key)
            unique_issues.append(issue)
    
    print(f"\n  Total unique issues: {len(unique_issues)}")
    return unique_issues


def fetch_comments(issue_key):
    """Fetch all comments for an issue."""
    url = f"{JIRA_BASE_URL}/rest/api/3/issue/{issue_key}/comment"
    
    response = requests.get(
        url,
        headers=get_headers(),
        auth=get_auth()
    )
    response.raise_for_status()
    return response.json().get("comments", [])


def extract_text_from_adf(adf_content):
    """Extract plain text from Atlassian Document Format (ADF)."""
    if not adf_content:
        return ""
    
    if isinstance(adf_content, str):
        return adf_content
    
    text_parts = []
    
    def traverse(node):
        if isinstance(node, dict):
            if node.get("type") == "text":
                text_parts.append(node.get("text", ""))
            for child in node.get("content", []):
                traverse(child)
        elif isinstance(node, list):
            for item in node:
                traverse(item)
    
    traverse(adf_content)
    return " ".join(text_parts)


def normalize_issue(issue, comments):
    """Normalize a single issue into a clean structure."""
    fields = issue.get("fields", {})
    changelog = issue.get("changelog", {})
    
    # Extract changelog events and fix versions
    changelog_events = []
    fix_versions = set()
    
    for history in changelog.get("histories", []):
        for item in history.get("items", []):
            changelog_events.append({
                "date": history.get("created", ""),
                "author": history.get("author", {}).get("displayName", "Unknown"),
                "field": item.get("field", ""),
                "from": item.get("fromString", ""),
                "to": item.get("toString", "")
            })
            # Collect Fix Versions from changelog
            if item.get("field") == "Fix Version" and item.get("toString"):
                fix_versions.add(item["toString"])
    
    # Extract comments
    normalized_comments = []
    for comment in comments:
        body = comment.get("body", "")
        text = extract_text_from_adf(body) if isinstance(body, dict) else body
        normalized_comments.append({
            "author": comment.get("author", {}).get("displayName", "Unknown"),
            "date": comment.get("created", ""),
            "text": text
        })
    
    # Extract description
    description = fields.get("description", "")
    description_text = extract_text_from_adf(description) if isinstance(description, dict) else (description or "")
    
    return {
        "key": issue.get("key", ""),
        "project": fields.get("project", {}).get("name", "Unknown"),
        "projectKey": fields.get("project", {}).get("key", ""),
        "issueType": fields.get("issuetype", {}).get("name", "Unknown"),
        "summary": fields.get("summary", ""),
        "description": description_text,
        "status": fields.get("status", {}).get("name", "Unknown"),
        "priority": fields.get("priority", {}).get("name", "") if fields.get("priority") else "",
        "resolution": fields.get("resolution", {}).get("name", "") if fields.get("resolution") else "",
        "assignee": fields.get("assignee", {}).get("displayName", "") if fields.get("assignee") else "",
        "reporter": fields.get("reporter", {}).get("displayName", "") if fields.get("reporter") else "",
        "created": fields.get("created", ""),
        "updated": fields.get("updated", ""),
        "labels": fields.get("labels", []),
        "components": [c.get("name", "") for c in fields.get("components", [])],
        "fixVersions": list(fix_versions),
        "comments": normalized_comments,
        "changelog": changelog_events
    }


def get_feature_for_issue(issue):
    """Determine the feature/product an issue belongs to.
    
    Uses components and fix versions directly as feature names.
    Works for any Jira project without hardcoded mappings.
    
    Priority:
    1. First component (if exists)
    2. First fix version (if exists)
    3. None (will be grouped as "Other")
    """
    components = issue.get("components", [])
    fix_versions = issue.get("fixVersions", [])
    
    # Use first component as feature name
    if components:
        return components[0]
    
    # Fall back to first fix version
    if fix_versions:
        return fix_versions[0]
    
    # No feature identified
    return None


def group_by_feature(normalized_issues):
    """Group normalized issues by feature/product instead of Jira project."""
    features = {}
    
    for issue in normalized_issues:
        feature_name = get_feature_for_issue(issue) or "Other"
        
        if feature_name not in features:
            features[feature_name] = {
                "featureName": feature_name,
                "issues": [],
                "stats": {
                    "totalIssues": 0,
                    "issueTypes": {},
                    "statuses": {}
                }
            }
        
        features[feature_name]["issues"].append(issue)
        
        # Update stats
        stats = features[feature_name]["stats"]
        stats["totalIssues"] += 1
        
        issue_type = issue.get("issueType", "Other")
        stats["issueTypes"][issue_type] = stats["issueTypes"].get(issue_type, 0) + 1
        
        status = issue.get("status", "Unknown")
        stats["statuses"][status] = stats["statuses"].get(status, 0) + 1
    
    # Sort features by issue count (most issues first), but keep "Other" at the end
    sorted_features = dict(sorted(
        features.items(),
        key=lambda x: (x[0] == "Other", -x[1]["stats"]["totalIssues"])
    ))
    
    return sorted_features


def group_by_project(normalized_issues):
    """Group normalized issues by project (legacy - use group_by_feature instead)."""
    projects = {}
    for issue in normalized_issues:
        project_key = issue.get("projectKey", "Unknown")
        project_name = issue.get("project", "Unknown")
        
        if project_key not in projects:
            projects[project_key] = {
                "projectKey": project_key,
                "projectName": project_name,
                "issues": [],
                "stats": {
                    "totalIssues": 0,
                    "issueTypes": {},
                    "statuses": {}
                }
            }
        
        projects[project_key]["issues"].append(issue)
        
        # Update stats
        stats = projects[project_key]["stats"]
        stats["totalIssues"] += 1
        
        issue_type = issue.get("issueType", "Other")
        stats["issueTypes"][issue_type] = stats["issueTypes"].get(issue_type, 0) + 1
        
        status = issue.get("status", "Unknown")
        stats["statuses"][status] = stats["statuses"].get(status, 0) + 1
    
    return projects
