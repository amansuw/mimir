# Mimir - Jira Review Data Extractor

Pull all your Jira activity (issues, comments, worklogs, changelog) and store it as structured JSON for LLM-powered review summaries.

## Setup

1. **Copy environment template:**
   ```bash
   cp .env.example .env
   ```

2. **Fill in your credentials in `.env`:**
   - `JIRA_BASE_URL` - Your Jira Cloud URL (e.g., `https://yourcompany.atlassian.net`)
   - `JIRA_EMAIL` - Your Jira account email
   - `JIRA_API_TOKEN` - Generate at https://id.atlassian.com/manage-profile/security/api-tokens
   - `JIRA_USERNAME` - Your Jira username (used in JQL queries)
   - `START_DATE` - Start date for data extraction (YYYY-MM-DD)
   - `GROQ_API_KEY` - Generate at https://console.groq.com/keys
   - `GROQ_MODEL_QUICK` - Fast model for per-issue summaries (default: `llama-3.1-8b-instant`)
   - `GROQ_MODEL_FULL` - Larger model for feature summaries and final review (default: `llama-3.3-70b-versatile`)

3. **Install dependencies:**
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

## Usage

The tool supports two commands:

### Extract and Summarize (Full Pipeline)
```bash
python main.py
```
or
```bash
python main.py all
```

### Extract Only
```bash
python main.py extract
```
Extracts Jira data and clears any existing output directories before starting fresh.

### Summarize Only
```bash
python main.py summarize
```
Generates LLM summaries from previously extracted data (requires prior extraction).

## Output

The script creates an `output/` directory with:

```
output/
├── raw/
│   ├── issues_raw.json         # Raw Jira API responses
│   └── comments_raw.json       # Raw comments per issue
├── normalized/
│   ├── issues_normalized.json  # Clean, LLM-ready issue data
│   ├── features_grouped.json   # Issues grouped by feature/product
│   ├── projects_grouped.json   # Issues grouped by Jira project (legacy)
│   └── summary.json            # High-level extraction summary
└── summaries/
    ├── issue_summaries.json    # LLM-generated per-issue summaries
    ├── feature_summaries.json  # LLM-generated per-feature summaries
    └── REVIEW_SUMMARY.md       # Final review document (ready to use!)
```

**Note:** Running `python main.py extract` clears all existing output directories before starting fresh extraction.

## Normalized Issue Structure

Each normalized issue contains:

```json
{
  "key": "PROJ-123",
  "project": "Payments",
  "projectKey": "PAY",
  "issueType": "Story",
  "summary": "Implement retry logic",
  "description": "...",
  "status": "Done",
  "priority": "High",
  "resolution": "Done",
  "assignee": "Your Name",
  "reporter": "Team Lead",
  "created": "2025-02-12T...",
  "updated": "2025-04-18T...",
  "labels": ["retry", "payments"],
  "components": ["Backend"],
  "fixVersions": ["Mobile v2"],
  "comments": [
    {
      "author": "Your Name",
      "date": "2025-03-01T...",
      "text": "Root cause was timeout"
    }
  ],
  "changelog": [
    {
      "date": "2025-03-01T...",
      "author": "Your Name",
      "field": "status",
      "from": "In Progress",
      "to": "Review"
    }
  ]
}
```

## Feature-Based Grouping

Instead of grouping by Jira projects (which are just boards), issues are grouped by **actual features/products** based on:

1. **Components** - Uses the first component as the feature name
2. **Fix Versions** - Falls back to first fix version if no component exists

This works automatically for any Jira project - no configuration needed. Issues without components or fix versions are grouped as "Other".

## LLM Summarization (Groq)

The script automatically generates summaries using Groq's LLM API:

1. **Per-issue summaries** - Each issue gets a 2-3 sentence summary
2. **Feature summaries** - Grouped by feature/product with key accomplishments
3. **Final review** - A polished markdown document with:
   - Executive Summary (2-3 sentences)
   - Key Themes (3-5 recurring themes)
   - **Top 10 Accomplishments** (ordered by impact, 3-5 sentences each)
   - Technical Growth Areas
   - Impact Statement

**Model Strategy:**

Two models are used depending on the task:

| Task | Primary Model | Fallback (on 429 rate limit) |
|------|--------------|-----------------------------|
| Per-issue summaries | `GROQ_MODEL_QUICK` (`llama-3.1-8b-instant`) | `groq/compound-mini` |
| Feature summaries | `GROQ_MODEL_FULL` (`llama-3.3-70b-versatile`) | `openai/gpt-oss-120b` |
| Final review | `GROQ_MODEL_FULL` (`llama-3.3-70b-versatile`) | `openai/gpt-oss-120b` |

The script automatically handles rate limiting with 2-second delays between requests. On a 429 rate-limit error, each request automatically retries once with its fallback model.

## JQL Query Used

The script pulls issues where you were:
- **Assignee** (`assignee = currentUser()`)
- **Reporter** (`reporter = currentUser()`)
- **Creator** (`creator = currentUser()`)
- **Watcher** (`watcher = currentUser()`)
- **Worklog Author** (`worklogAuthor = currentUser()`)

This matches Jira's "Worked on" view for comprehensive activity tracking. Issues are filtered by the `updated` date within your specified date range and sorted by most recently updated.

## Features

- **Automatic Rate Limiting:** 2-second delays between API requests to respect Groq's 30 RPM limit
- **Smart Model Fallback:** Automatically retries with a fallback model on 429 rate-limit errors
- **Fresh Extraction:** Clears existing data before each extraction to ensure clean state
- **Comprehensive JQL:** Matches Jira's "Worked on" view with 5 different user role filters
- **Feature-Based Grouping:** Groups issues by actual features/products (not Jira boards)
- **Filtered Summarization:** Only summarizes completed issues (excludes Open/Waiting statuses)
- **Month-by-Month Extraction:** Fetches data in monthly chunks to handle large date ranges efficiently
