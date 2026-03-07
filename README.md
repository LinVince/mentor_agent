# Mentor Agent

A personal growth mentor powered by DeepSeek + LangChain, backed by MongoDB,
served over Flask, and delivered via LINE Messaging API.

## Project Structure

```
mentor_agent/
├── app.py              # Flask server + LINE webhook
├── mentor_agent.py     # LangChain agent, tools, DeepSeek model
├── mongodb_mentor.py   # MongoDB helpers (reflections, incidents, reminders, growth)
├── requirements.txt
└── .env                # secrets (never commit this)
```

## Setup

1. Copy `.env.example` to `.env` and fill in your values:

```
MONGO_DB_PASSWORD=your_mongo_password
DEEPSEEK_API_KEY=sk-...
LANGSMITH_API_KEY=ls__...   # optional
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Run the server:

```bash
python app.py
```

Server starts on port 5001.

## MongoDB Collections

All stored in the `mentor_journal` database:

| Collection    | Purpose                                      |
|---------------|----------------------------------------------|
| reflections   | Dated journal entries with ISO week tracking |
| incidents     | Mistakes and lessons learned                 |
| reminders     | Persistent notes the mentor resurfaces       |
| growth_log    | Milestones and breakthroughs                 |

## REST Endpoints

| Method | Path             | Description                          |
|--------|------------------|--------------------------------------|
| GET    | /                | Health check                         |
| GET    | /prompt?prompt=  | Quick agent query                    |
| POST   | /prompt          | Async agent query (returns job_id)   |
| GET    | /jobs/:id        | Check async job status               |
| POST   | /callback        | LINE webhook                         |
| POST   | /reflect         | Directly save a reflection           |
| POST   | /remind          | Directly save a reminder             |
| GET    | /weekly          | Get weekly summary (?year=&week=)    |

## Agent Tools

The mentor agent has 13 tools:

- record_reflection — save a journal entry
- get_this_week_reflections — current week's entries
- get_last_week_reflections — previous week's entries
- get_recent_reflections — N most recent entries
- record_incident — log a mistake or incident with lesson
- get_recent_incidents — review recent incidents
- get_incidents_by_tag — find patterns by tag
- add_reminder — save a persistent reminder
- get_active_reminders — fetch all active reminders
- dismiss_reminder — deactivate a reminder
- record_growth_milestone — log an achievement
- get_growth_timeline — see progress over time
- get_weekly_summary — full week snapshot

## Example LINE / POST messages

```
"I want to start my weekly review"
"I overtraded today because of FOMO. Log this as an incident."
"Remind me to always check volume before entering a breakout."
"What did I reflect on last week?"
"I finally held a winner without cutting early — record this as a milestone."
"Show me all my incidents tagged trading"
```
