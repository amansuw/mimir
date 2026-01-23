"""
LLM-powered summarization pipeline.
Generates issue summaries, feature summaries, and final review.
"""

import json
import time
from datetime import datetime

from config import (
    GROQ_API_KEY, GROQ_MODEL_QUICK, GROQ_MODEL_FULL,
    SUMMARIES_DIR, START_DATE, END_DATE, EXCLUDED_STATUSES
)
from llm import quick_summary_request, full_summary_request


def save_json(data, filepath):
    """Save data as JSON to file."""
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def summarize_issue(issue):
    """Generate a brief summary of a single issue."""
    # Build context from issue data
    context_parts = [
        f"Issue: {issue['key']}",
        f"Type: {issue['issueType']}",
        f"Summary: {issue['summary']}",
        f"Status: {issue['status']}"
    ]
    
    if issue.get("description"):
        desc = issue["description"][:500]
        context_parts.append(f"Description: {desc}")
    
    if issue.get("comments"):
        recent_comments = issue["comments"][-3:]
        for c in recent_comments:
            context_parts.append(f"Comment by {c['author']}: {c['text'][:200]}")
    
    context = "\n".join(context_parts)
    
    prompt = f"""Summarize this Jira issue in 2-3 sentences focusing on what was accomplished.
Write in third-person (not "I"). Be specific about technical work done.

{context}

Summary:"""

    messages = [
        {"role": "system", "content": "You are a technical writer creating concise issue summaries for a performance review. Focus on accomplishments and impact."},
        {"role": "user", "content": prompt}
    ]
    
    return quick_summary_request(messages)


def summarize_feature(feature_name, issue_summaries):
    """Generate a feature-level summary from issue summaries."""
    # Score issues by complexity signals in summary text
    def score_issue(issue):
        score = 0
        summary_lower = issue.get('summary', '').lower()
        if any(w in summary_lower for w in ['replace', 'migrate', 'refactor', 'architect', 'integration']):
            score += 10
        if any(w in summary_lower for w in ['multiple', 'packages', 'months', 'complex', 'major']):
            score += 8
        if any(w in summary_lower for w in ['revamp', 'overhaul', 'redesign']):
            score += 8
        return score
    
    sorted_issues = sorted(issue_summaries, key=score_issue, reverse=True)
    top_issues = sorted_issues[:25]
    
    issues_text = "\n".join([
        f"- {s['summary'][:120]}"
        for s in top_issues
    ])
    
    prompt = f"""Summarize work on "{feature_name}" feature/product at a high level (third-person perspective).

Work items ({len(issue_summaries)} total):
{issues_text}

Write:
1. Overview (2-3 sentences, third-person: "The contributor..." or "Work on this feature...")
2. Key accomplishments (group related items together)
3. Impact statement

IMPORTANT: Group related tickets into single accomplishments. Don't list the same work multiple times."""

    messages = [
        {"role": "system", "content": "You are helping prepare a performance review summary. Be professional, concise, and highlight impact."},
        {"role": "user", "content": prompt}
    ]
    
    # Use full model for feature-level summaries (better synthesis)
    return full_summary_request(messages)


def generate_final_review(feature_summaries, total_issues):
    """Generate the final consolidated review summary."""
    features_text = "\n\n".join([
        f"## {f['feature']} ({f['issueCount']} issues)\n{f['summary']}"
        for f in feature_summaries
        if f.get('summary')  # Skip failed summaries
    ])
    
    prompt = f"""Create a comprehensive performance review summary from these feature contributions. Write in THIRD-PERSON (not "I" - use "The contributor" or passive voice).

Total: {total_issues} issues across features/products

{features_text}

Write a well-formatted summary document with the following structure:

## Executive Summary
2-3 sentences providing a high-level overview of the contributor's work and overall impact.

## Key Themes
Bullet points identifying 3-5 recurring themes across all projects (e.g., "System reliability improvements", "Mobile app enhancements").

## Top 10 Accomplishments

List EXACTLY 10 major accomplishments, ordered from MOST IMPACTFUL to LEAST IMPACTFUL. For each accomplishment:
- Use a clear, bold heading describing the feature/project
- Write 3-5 sentences explaining:
  * What was done technically (specific technologies, integrations, or systems involved)
  * Why it was challenging or significant (complexity, scope, business criticality)
  * The measurable impact or outcome (user experience, performance, reliability)

Format each accomplishment as:
### 1. [Accomplishment Title]
[3-5 sentence paragraph]

## Technical Growth Areas
Bullet points highlighting skills demonstrated or developed.

## Impact Statement
A concluding paragraph summarizing the overall value delivered.

IMPORTANT RULES:
- Write in third-person throughout (never use "I" or "my")
- Group related work into single accomplishments (don't repeat similar items)
- Prioritize complex, multi-month, or architectural efforts over small/quick fixes
- Order accomplishments by business/technical impact (most impactful first)
- Each accomplishment MUST have 3-5 substantive sentences, not one-liners
- Use proper markdown formatting with headers and bold text"""

    messages = [
        {"role": "system", "content": "You are a technical writer creating an objective, well-formatted performance review summary. Write in third-person. Focus on technical depth, clear structure, and measurable impact. Use proper markdown formatting."},
        {"role": "user", "content": prompt}
    ]
    
    # Use full model for final review (better synthesis)
    return full_summary_request(messages)


def run_summarization(normalized_issues, features):
    """Run the full LLM summarization pipeline."""
    from jira_api import get_feature_for_issue
    
    if not GROQ_API_KEY:
        print("\n⚠️  GROQ_API_KEY not set. Skipping LLM summarization.")
        print("   Add your Groq API key to .env to enable summarization.")
        return
    
    # Filter out incomplete issues (Open, Waiting for support)
    completed_issues = [
        issue for issue in normalized_issues
        if issue.get("status") not in EXCLUDED_STATUSES
    ]
    skipped = len(normalized_issues) - len(completed_issues)
    
    print("\n🤖 Running LLM Summarization (Groq)...")
    print(f"   Quick summaries: {GROQ_MODEL_QUICK}")
    print(f"   Full summaries: {GROQ_MODEL_FULL}")
    print(f"   Processing {len(completed_issues)} completed issues (skipped {skipped} open/waiting)")
    SUMMARIES_DIR.mkdir(parents=True, exist_ok=True)
    
    # Step 1: Summarize each issue
    print("\n📝 Summarizing individual issues...")
    issue_summaries = []
    
    for i, issue in enumerate(completed_issues, 1):
        print(f"  [{i}/{len(completed_issues)}] {issue['key']}...", end=" ")
        feature = get_feature_for_issue(issue) or "Other"
        try:
            summary = summarize_issue(issue)
            issue_summaries.append({
                "key": issue["key"],
                "feature": feature,
                "project": issue["project"],
                "projectKey": issue["projectKey"],
                "originalSummary": issue["summary"],
                "summary": summary
            })
            print("✓")
            time.sleep(2)  # Rate limit buffer - 30 RPM = 2s between requests
        except Exception as e:
            print(f"✗ ({e})")
            issue_summaries.append({
                "key": issue["key"],
                "feature": feature,
                "project": issue["project"],
                "projectKey": issue["projectKey"],
                "originalSummary": issue["summary"],
                "summary": f"[Summary failed] {issue['summary']}"
            })
    
    save_json(issue_summaries, SUMMARIES_DIR / "issue_summaries.json")
    
    # Step 2: Summarize by feature (not by Jira project)
    print("\n📊 Summarizing by feature...")
    feature_summaries = []
    
    for feature_name, feature_data in features.items():
        feature_issues = [s for s in issue_summaries if s["feature"] == feature_name]
        
        if not feature_issues:
            continue
            
        print(f"  {feature_name} ({len(feature_issues)} issues)...", end=" ")
        try:
            summary = summarize_feature(feature_name, feature_issues)
            feature_summaries.append({
                "feature": feature_name,
                "issueCount": len(feature_issues),
                "summary": summary
            })
            print("✓")
            time.sleep(2)
        except Exception as e:
            print(f"✗ ({e})")
    
    save_json(feature_summaries, SUMMARIES_DIR / "feature_summaries.json")
    
    # Step 3: Generate final review
    print("\n📄 Generating final review summary...")
    try:
        final_review = generate_final_review(
            feature_summaries, 
            len(completed_issues)
        )
        
        # Save as markdown
        review_path = SUMMARIES_DIR / "REVIEW_SUMMARY.md"
        with open(review_path, "w", encoding="utf-8") as f:
            f.write("# Performance Review Summary\n\n")
            f.write(f"*Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}*\n\n")
            end_str = END_DATE if END_DATE else "present"
            f.write(f"*Period: {START_DATE} to {end_str}*\n\n")
            f.write("---\n\n")
            f.write(final_review)
        print(f"  💾 Saved: {review_path}")
        
    except Exception as e:
        print(f"  ✗ Failed to generate final review: {e}")
