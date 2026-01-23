"""
Main entry point for Jira Review Extractor.
Supports extract, summarize, and all commands.
"""

import sys
import json
from datetime import datetime

from config import (
    JIRA_BASE_URL, JIRA_EMAIL, JIRA_API_TOKEN,
    START_DATE, END_DATE,
    RAW_DIR, NORMALIZED_DIR, SUMMARIES_DIR
)
from jira_api import (
    fetch_all_issues, fetch_comments, normalize_issue, group_by_feature, group_by_project
)
from summarizer import run_summarization, save_json


def run_extraction():
    """Extract data from Jira."""
    print("=" * 60)
    print("🚀 Jira Data Extraction")
    print("=" * 60)
    
    # Validate configuration
    if not all([JIRA_BASE_URL, JIRA_EMAIL, JIRA_API_TOKEN]):
        print("❌ Error: Missing required environment variables.")
        print("   Please copy .env.example to .env and fill in your credentials.")
        return None, None
    
    print("\n📋 Configuration:")
    print(f"   Base URL: {JIRA_BASE_URL}")
    print(f"   Email: {JIRA_EMAIL}")
    print(f"   Start Date: {START_DATE}")
    if END_DATE:
        print(f"   End Date: {END_DATE}")
    print()
    
    # Clear existing data and create fresh directories
    import shutil
    for dir_path in [RAW_DIR, NORMALIZED_DIR, SUMMARIES_DIR]:
        if dir_path.exists():
            shutil.rmtree(dir_path)
            print(f"🗑️  Cleared: {dir_path}")
    
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    NORMALIZED_DIR.mkdir(parents=True, exist_ok=True)
    
    # Step 1: Fetch all issues
    issues = fetch_all_issues()
    
    if not issues:
        print("⚠️  No issues found matching the query.")
        return None, None
    
    # Save raw data
    save_json(issues, RAW_DIR / "issues_raw.json")
    print(f"\n💾 Saved raw issues: {RAW_DIR / 'issues_raw.json'}")
    
    # Step 2: Fetch comments for each issue
    print("\n💬 Fetching comments...")
    all_comments = {}
    for i, issue in enumerate(issues, 1):
        key = issue.get("key", "")
        if i % 20 == 0:
            print(f"  Progress: {i}/{len(issues)}...")
        try:
            comments = fetch_comments(key)
            all_comments[key] = comments
        except Exception as e:
            print(f"  ⚠️  Failed to fetch comments for {key}: {e}")
            all_comments[key] = []
    
    save_json(all_comments, RAW_DIR / "comments_raw.json")
    print(f"💾 Saved comments: {RAW_DIR / 'comments_raw.json'}")
    
    # Step 3: Normalize all issues
    print("\n🔄 Normalizing issues...")
    normalized_issues = []
    
    for issue in issues:
        key = issue.get("key", "")
        comments = all_comments.get(key, [])
        normalized = normalize_issue(issue, comments)
        normalized_issues.append(normalized)
    
    # Save normalized issues
    save_json(normalized_issues, NORMALIZED_DIR / "issues_normalized.json")
    
    # Step 4: Group by feature (based on components and fix versions)
    print("\n📊 Grouping by feature...")
    features = group_by_feature(normalized_issues)
    save_json(features, NORMALIZED_DIR / "features_grouped.json")
    
    # Also save legacy project grouping for reference
    projects = group_by_project(normalized_issues)
    save_json(projects, NORMALIZED_DIR / "projects_grouped.json")
    
    # Step 5: Generate summary
    end_str = END_DATE if END_DATE else "present"
    summary = {
        "extractedAt": datetime.now().isoformat(),
        "dateRange": f"{START_DATE} to {end_str}",
        "totalIssues": len(normalized_issues),
        "totalFeatures": len(features),
        "features": [
            {
                "name": f["featureName"],
                "issues": f["stats"]["totalIssues"],
                "issueTypes": f["stats"]["issueTypes"],
                "statuses": f["stats"]["statuses"]
            }
            for f in features.values()
        ]
    }
    save_json(summary, NORMALIZED_DIR / "summary.json")
    
    # Print summary
    print("\n" + "=" * 60)
    print("✅ Extraction Complete!")
    print("=" * 60)
    print("\n📈 Summary:")
    print(f"   Total Issues: {summary['totalIssues']}")
    print(f"   Total Features: {summary['totalFeatures']}")
    for f in summary['features']:
        print(f"     - {f['name']}: {f['issues']} issues")
    print("\n📁 Output Files:")
    print(f"   Raw data:        {RAW_DIR}/")
    print(f"   Normalized data: {NORMALIZED_DIR}/")
    
    return normalized_issues, features


def load_extracted_data():
    """Load previously extracted data from files."""
    issues_path = NORMALIZED_DIR / "issues_normalized.json"
    features_path = NORMALIZED_DIR / "features_grouped.json"
    
    if not issues_path.exists() or not features_path.exists():
        print("❌ No extracted data found. Run 'python main.py extract' first.")
        return None, None
    
    print("📂 Loading extracted data...")
    with open(issues_path, "r", encoding="utf-8") as f:
        normalized_issues = json.load(f)
    with open(features_path, "r", encoding="utf-8") as f:
        features = json.load(f)
    
    print(f"   Loaded {len(normalized_issues)} issues across {len(features)} features")
    return normalized_issues, features


def main():
    """Main entry point with command support."""
    mode = sys.argv[1] if len(sys.argv) > 1 else "all"
    
    if mode == "extract":
        # Extract only
        run_extraction()
        print("\n💡 Run 'python main.py summarize' to generate LLM summaries.")
    
    elif mode == "summarize":
        # Summarize only (load existing data)
        normalized_issues, features = load_extracted_data()
        if normalized_issues and features:
            run_summarization(normalized_issues, features)
            print("\n" + "=" * 60)
            print("🎉 Summarization Done!")
            print("=" * 60)
            print(f"\n📄 Review summary: {SUMMARIES_DIR / 'REVIEW_SUMMARY.md'}")
    
    elif mode == "all" or mode not in ["extract", "summarize"]:
        # Run both
        normalized_issues, features = run_extraction()
        if normalized_issues and features:
            run_summarization(normalized_issues, features)
            print("\n" + "=" * 60)
            print("🎉 All Done!")
            print("=" * 60)
            print(f"\n📄 Review summary: {SUMMARIES_DIR / 'REVIEW_SUMMARY.md'}")


if __name__ == "__main__":
    main()
