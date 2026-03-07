from langchain.chat_models import init_chat_model
from langchain.tools import tool
from langchain.agents import create_agent
from langchain_core.messages import AIMessage
import os
import mongodb_mentor as mongo

# ══════════════════════════════════════════════════════════════
#  Environment
# ══════════════════════════════════════════════════════════════

os.environ["LANGSMITH_TRACING"] = "true"
os.environ["LANGSMITH_ENDPOINT"] = "https://api.smith.langchain.com"
os.environ["LANGSMITH_PROJECT"] = "mentor-agent"

LANGSMITH_API_KEY = os.environ.get("LANGSMITH_API_KEY")

DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "sk-daadb7c9968f4c07b802743b631164d1")

model = init_chat_model(
    "deepseek-chat",
    model_provider="deepseek",
    api_key=DEEPSEEK_API_KEY,
)

# ═════════════════════════════════
# Reflection Tools
# ═════════════════════════════════

@tool
def record_reflection(content: str, tags: str = "") -> str:
    """
    Save a personal reflection or journal entry.
    Accepts the reflection text and an optional comma-separated tag string e.g. 'mindset,trading,discipline'.
    Stores: content (str), tags (list), created_at (UTC timestamp), week (ISO int), year (int).
    """
    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []
    result = mongo.save_reflection(content, tag_list)
    if "error" in result:
        return f"Failed to save reflection: {result['error']}"
    return f"Reflection saved at {result['created_at']}."


@tool
def get_this_week_reflections() -> str:
    """Fetch all reflections recorded during the current ISO week (Monday to Sunday)."""
    entries = mongo.get_reflections_this_week()
    if not entries:
        return "No reflections found for this week."
    lines = [f"This Week's Reflections ({len(entries)} entries):\n"]
    for i, e in enumerate(entries, 1):
        tags = ", ".join(e.get("tags", [])) or "none"
        lines.append(f"[{i}] {e['created_at'][:10]}  |  Tags: {tags}\n{e['content']}\n")
    return "\n".join(lines)


@tool
def get_last_week_reflections() -> str:
    """Fetch all reflections from the previous ISO week. Use this at session start to establish continuity."""
    entries = mongo.get_reflections_last_week()
    if not entries:
        return "No reflections found for last week."
    lines = [f"Last Week's Reflections ({len(entries)} entries):\n"]
    for i, e in enumerate(entries, 1):
        tags = ", ".join(e.get("tags", [])) or "none"
        lines.append(f"[{i}] {e['created_at'][:10]}  |  Tags: {tags}\n{e['content']}\n")
    return "\n".join(lines)


@tool
def get_recent_reflections(limit: int = 10) -> str:
    """Fetch the N most recent reflections across all weeks. Accepts limit (int, default 10)."""
    entries = mongo.get_recent_reflections(limit)
    if not entries:
        return "No reflections found."
    lines = [f"Recent {len(entries)} Reflections:\n"]
    for i, e in enumerate(entries, 1):
        tags = ", ".join(e.get("tags", [])) or "none"
        lines.append(f"[{i}] {e['created_at'][:10]}  |  Tags: {tags}\n{e['content']}\n")
    return "\n".join(lines)


# ═════════════════════════════════
# Incident Tools
# ═════════════════════════════════

@tool
def record_incident(title: str, description: str, lesson: str = "", tags: str = "") -> str:
    """
    Record an incident, mistake, or emotionally challenging situation.
    Accepts:
        title       - short label for the incident e.g. 'Panic-sold at the bottom'
        description - detailed account of what happened and how the user felt
        lesson      - what the user will do differently next time (optional)
        tags        - comma-separated root-cause labels e.g. 'fomo,emotion,discipline' (optional)
    Stores: title (str), description (str), lesson (str), tags (list), created_at (UTC timestamp), week (ISO int), year (int).
    """
    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []
    result = mongo.save_incident(title, description, lesson, tag_list)
    if "error" in result:
        return f"Failed to record incident: {result['error']}"
    return f"Incident '{title}' recorded at {result['created_at']}."


@tool
def get_recent_incidents(limit: int = 10) -> str:
    """Fetch the N most recent incidents across all weeks. Accepts limit (int, default 10)."""
    entries = mongo.get_recent_incidents(limit)
    if not entries:
        return "No incidents recorded yet."
    lines = [f"Recent {len(entries)} Incidents:\n"]
    for i, e in enumerate(entries, 1):
        tags = ", ".join(e.get("tags", [])) or "none"
        lines.append(
            f"[{i}] {e['created_at'][:10]}  |  {e['title']}  |  Tags: {tags}\n"
            f"  What happened: {e['description']}\n"
            f"  Lesson: {e.get('lesson') or 'Not recorded'}\n"
        )
    return "\n".join(lines)


@tool
def get_incidents_by_tag(tag: str) -> str:
    """
    Fetch all incidents matching a single tag to identify recurring patterns.
    Accepts a single lowercase tag e.g. 'fomo' or 'discipline'. Do not pass multiple tags.
    """
    entries = mongo.get_incidents_by_tag(tag)
    if not entries:
        return f"No incidents found with tag '{tag}'."
    lines = [f"Incidents tagged '{tag}' ({len(entries)} found):\n"]
    for i, e in enumerate(entries, 1):
        lines.append(
            f"[{i}] {e['created_at'][:10]}  |  {e['title']}\n"
            f"  {e['description']}\n"
            f"  Lesson: {e.get('lesson') or 'Not recorded'}\n"
        )
    return "\n".join(lines)


# ═════════════════════════════════
# Reminder Tools
# ═════════════════════════════════

@tool
def add_reminder(content: str, priority: str = "medium") -> str:
    """
    Save a persistent reminder that will be surfaced at every future session.
    Accepts:
        content  - the full reminder text e.g. 'Never enter without checking weekly KD first'
        priority - 'high', 'medium', or 'low' (default 'medium')
    Stores: content (str), priority (str), active (bool, default True), created_at (UTC timestamp).
    """
    if priority not in ("low", "medium", "high"):
        priority = "medium"
    result = mongo.save_reminder(content, priority)
    if "error" in result:
        return f"Failed to save reminder: {result['error']}"
    return f"Reminder saved (priority: {priority})."


@tool
def get_active_reminders() -> str:
    """
    Fetch all currently active reminders sorted by priority (high first).
    Always call this at the start of every session and read the reminders back to the user.
    """
    entries = mongo.get_active_reminders()
    if not entries:
        return "No active reminders."
    lines = [f"Active Reminders ({len(entries)}):\n"]
    for i, e in enumerate(entries, 1):
        lines.append(f"[{i}] [{e['priority'].upper()}]  {e['content']}  (added {e['created_at'][:10]})")
    return "\n".join(lines)


@tool
def dismiss_reminder(content_snippet: str) -> str:
    """
    Deactivate a reminder by matching a word or phrase from its content. Case-insensitive.
    Accepts a snippet specific enough to identify one reminder e.g. 'weekly KD'.
    """
    return mongo.dismiss_reminder(content_snippet)


# ═════════════════════════════════
# Growth Tools
# ═════════════════════════════════

@tool
def record_growth_milestone(title: str, description: str, category: str = "general") -> str:
    """
    Record a growth milestone or personal breakthrough.
    Accepts:
        title       - short achievement label e.g. 'Held a winner past my usual exit'
        description - what happened and why it represents genuine growth
        category    - one of: 'trading', 'mindset', 'discipline', 'knowledge', 'habit', 'emotion', 'general'
    Stores: title (str), description (str), category (str), created_at (UTC timestamp), week (ISO int), year (int).
    """
    result = mongo.save_growth_milestone(title, description, category)
    if "error" in result:
        return f"Failed to record milestone: {result['error']}"
    return f"Growth milestone '{title}' recorded."


@tool
def get_growth_timeline(limit: int = 20) -> str:
    """Fetch the N most recent growth milestones. Accepts limit (int, default 20)."""
    entries = mongo.get_growth_timeline(limit)
    if not entries:
        return "No growth milestones recorded yet."
    lines = [f"Growth Timeline ({len(entries)} milestones):\n"]
    for i, e in enumerate(entries, 1):
        lines.append(
            f"[{i}] {e['created_at'][:10]}  [{e['category'].upper()}]  {e['title']}\n"
            f"  {e['description']}\n"
        )
    return "\n".join(lines)


# ═════════════════════════════════
# Weekly Summary Tool
# ═════════════════════════════════

@tool
def get_weekly_summary(year: int = 0, week: int = 0) -> str:
    """
    Fetch a full summary of reflections, incidents, and growth milestones for a given ISO week.
    Accepts year (int) and week (int, 1-53). Pass 0 for both to default to the current week.
    Use for weekly review sessions.
    """
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    y = year if year else now.year
    w = week if week else now.isocalendar()[1]

    data = mongo.get_weekly_summary(y, w)
    lines = [f"Weekly Summary - Year {data['year']}, Week {data['week']}\n{'='*50}"]

    lines.append(f"\nReflections ({len(data['reflections'])}):")
    if data["reflections"]:
        for e in data["reflections"]:
            lines.append(f"  {e['created_at'][:10]}  {e['content'][:200]}")
    else:
        lines.append("  None this week.")

    lines.append(f"\nIncidents ({len(data['incidents'])}):")
    if data["incidents"]:
        for e in data["incidents"]:
            lines.append(f"  {e['created_at'][:10]}  {e['title']}: {e['description'][:150]}")
            if e.get("lesson"):
                lines.append(f"    Lesson: {e['lesson'][:150]}")
    else:
        lines.append("  None this week.")

    lines.append(f"\nGrowth Milestones ({len(data['growth'])}):")
    if data["growth"]:
        for e in data["growth"]:
            lines.append(f"  {e['created_at'][:10]}  [{e['category']}]  {e['title']}")
    else:
        lines.append("  None this week.")

    return "\n".join(lines)


# ══════════════════════════════════════════════════════════════
#  AGENT
# ══════════════════════════════════════════════════════════════

SYSTEM_PROMPT = """
You are a personal growth mentor and accountability coach.

AUTOMATIC CLASSIFICATION AND STORAGE
Every time the user sends a message that contains personal content, you must:
1. Silently classify what type of content it is (see rules below).
2. Call the appropriate storage tool immediately — do not ask permission.
3. After storing, respond naturally as a mentor.

Classification rules:

INCIDENT — store with record_incident if the message describes:
- A mistake, bad decision, or poor trade
- An emotional reaction that led to a bad outcome (fear, FOMO, revenge, panic)
- A rule that was broken
- Something that went wrong and the user regrets
For title: extract a short 3-8 word label from the content.
For description: use the full detail the user provided.
For lesson: extract it if the user stated one; otherwise leave empty.
For tags: infer root-cause tags from the content e.g. 'fomo', 'emotion', 'discipline', 'risk', 'overtrading'.

REFLECTION — store with record_reflection if the message describes:
- A general observation about themselves or their behaviour
- A thought, feeling, or awareness that is not tied to a specific mistake
- End-of-day or end-of-week journaling
- A goal, intention, or commitment going forward
For tags: infer topic tags from the content e.g. 'mindset', 'trading', 'habit', 'focus', 'patience'.

REMINDER — store with add_reminder if the message contains:
- A rule the user wants to remember permanently
- A commitment phrased as "I should always...", "Never...", "Remember to...", "Remind me..."
- Something they want surfaced in future sessions
For priority: use 'high' if the user signals urgency or importance; otherwise 'medium'.

GROWTH MILESTONE — store with record_growth_milestone if the message describes:
- Something the user did well or better than before
- A behaviour they successfully changed
- A moment of self-awareness or breakthrough
For category: infer from content — 'trading', 'mindset', 'discipline', 'knowledge', 'habit', 'emotion', or 'general'.

A single message may contain multiple types. Store each one separately with the correct tool.
If the message is purely a question or command with no personal content to store, skip storage and respond directly.

SESSION START BEHAVIOUR
At the very start of every new session:
1. Call get_active_reminders and read them back to the user.
2. Call get_last_week_reflections to establish context.
3. Ask the user what they want to focus on today.

GENERAL BEHAVIOUR
- Identify recurring patterns across incidents and reflections and gently name them.
- Celebrate growth milestones warmly but honestly.
- Ask one thoughtful follow-up question after responding, not multiple.
- Be direct and honest — not just a cheerleader.

Return plain text only. Do not use markdown bold, headers, or bullet symbols.
""".strip()

agent = create_agent(
    model=model,
    tools=[
        record_reflection,
        get_this_week_reflections,
        get_last_week_reflections,
        get_recent_reflections,
        record_incident,
        get_recent_incidents,
        get_incidents_by_tag,
        add_reminder,
        get_active_reminders,
        dismiss_reminder,
        record_growth_milestone,
        get_growth_timeline,
        get_weekly_summary,
    ],
    system_prompt=SYSTEM_PROMPT,
)


def get_response_from_agent(user_input: str) -> str:
    response = agent.invoke({"messages": [{"role": "user", "content": user_input}]})
    for msg in reversed(response["messages"]):
        if isinstance(msg, AIMessage):
            return msg.content
    return "I could not generate a response."


