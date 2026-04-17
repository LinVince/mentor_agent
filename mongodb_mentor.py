import os
from datetime import datetime, timezone
from pymongo import MongoClient, DESCENDING
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
from dotenv import load_dotenv

load_dotenv()

DB_PASSWORD = os.environ.get("MONGO_DB_PASSWORD")
print("DEBUG ENV VALUE:", os.environ.get("MONGO_DB_PASSWORD"))
if not DB_PASSWORD:
    raise ValueError("MONGO_DB_PASSWORD environment variable not set.")

MONGO_URI = (
    f"mongodb+srv://vincejim91126_db_user:{DB_PASSWORD}"
    "@mentordb.7m1yabo.mongodb.net/mentor_journal"
    "?retryWrites=true&w=majority&appName=mentordb"
)


try:
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    client.admin.command("ping")
    print("Mentor MongoDB connected!")
except (ConnectionFailure, ServerSelectionTimeoutError) as e:
    print(f"Mentor MongoDB connection failed: {e}")
    client = None

db = client.get_database() if client is not None else None

# ─── Collections ──────────────────────────────────────────────────────────────
# mentor_journal.reflections   – dated journal entries
# mentor_journal.incidents     – incidents / mistakes / learnings
# mentor_journal.reminders     – persistent reminders to surface regularly
# mentor_journal.growth_log    – periodic growth milestones


def _ts():
    """UTC ISO timestamp string."""
    return datetime.now(timezone.utc).isoformat()


def _col(name: str):
   return db[name] if db is not None else None


# ─── Reflections ──────────────────────────────────────────────────────────────

def save_reflection(content: str, tags: list = None) -> dict:
    """Save a new reflection entry."""
    col = _col("reflections")
    if col is None:
        return {"error": "DB unavailable"}
    doc = {
        "content":    content,
        "tags":       tags or [],
        "created_at": _ts(),
        "week":       datetime.now(timezone.utc).isocalendar()[1],   # ISO week number
        "year":       datetime.now(timezone.utc).year,
    }
    result = col.insert_one(doc)
    return {"inserted_id": str(result.inserted_id), "created_at": doc["created_at"]}


def get_reflections_this_week() -> list:
    """Fetch all reflections from the current ISO week."""
    col = _col("reflections")
    if col is None:
        return []
    now  = datetime.now(timezone.utc)
    week = now.isocalendar()[1]
    year = now.year
    return list(col.find({"week": week, "year": year}, {"_id": 0}).sort("created_at", DESCENDING))


def get_reflections_last_week() -> list:
    """Fetch all reflections from the previous ISO week."""
    col = _col("reflections")
    if col is None:
        return []
    now       = datetime.now(timezone.utc)
    this_week = now.isocalendar()[1]
    year      = now.year
    last_week = this_week - 1
    if last_week == 0:
        last_week = 52
        year -= 1
    return list(col.find({"week": last_week, "year": year}, {"_id": 0}).sort("created_at", DESCENDING))


def get_recent_reflections(limit: int = 10) -> list:
    """Fetch the most recent N reflections."""
    col = _col("reflections")
    if col is None:
        return []
    return list(col.find({}, {"_id": 0}).sort("created_at", DESCENDING).limit(limit))


# ─── Incidents ────────────────────────────────────────────────────────────────

def save_incident(title: str, description: str, lesson: str = "", tags: list = None) -> dict:
    """Record an incident or mistake with an optional lesson learned."""
    col = _col("incidents")
    if col is None:
        return {"error": "DB unavailable"}
    doc = {
        "title":       title,
        "description": description,
        "lesson":      lesson,
        "tags":        tags or [],
        "created_at":  _ts(),
        "week":        datetime.now(timezone.utc).isocalendar()[1],
        "year":        datetime.now(timezone.utc).year,
    }
    result = col.insert_one(doc)
    return {"inserted_id": str(result.inserted_id), "created_at": doc["created_at"]}


def get_recent_incidents(limit: int = 10) -> list:
    col = _col("incidents")
    if col is None:
        return []
    return list(col.find({}, {"_id": 0}).sort("created_at", DESCENDING).limit(limit))


def get_incidents_by_tag(tag: str) -> list:
    col = _col("incidents")
    if col is None:
        return []
    return list(col.find({"tags": tag}, {"_id": 0}).sort("created_at", DESCENDING))


# ─── Reminders ────────────────────────────────────────────────────────────────

def save_reminder(content: str, priority: str = "medium") -> dict:
    """Save a persistent reminder (priority: low / medium / high)."""
    col = _col("reminders")
    if col is None:
        return {"error": "DB unavailable"}
    doc = {
        "content":    content,
        "priority":   priority,
        "active":     True,
        "created_at": _ts(),
    }
    result = col.insert_one(doc)
    return {"inserted_id": str(result.inserted_id)}


def get_active_reminders() -> list:
    col = _col("reminders")
    if col is None:
        return []
    return list(col.find({"active": True}, {"_id": 0}).sort("priority", DESCENDING))


def dismiss_reminder(content_snippet: str) -> str:
    """Mark a reminder inactive by matching a snippet of its content."""
    col = _col("reminders")
    if col is None:
        return "DB unavailable"
    result = col.update_one(
        {"content": {"$regex": content_snippet, "$options": "i"}, "active": True},
        {"$set": {"active": False, "dismissed_at": _ts()}}
    )
    return "Dismissed." if result.modified_count else "No matching active reminder found."


# ─── Growth Log ───────────────────────────────────────────────────────────────

def save_growth_milestone(title: str, description: str, category: str = "general") -> dict:
    """Record a growth milestone or achievement."""
    col = _col("growth_log")
    if col is None:
        return {"error": "DB unavailable"}
    doc = {
        "title":       title,
        "description": description,
        "category":    category,
        "created_at":  _ts(),
        "week":        datetime.now(timezone.utc).isocalendar()[1],
        "year":        datetime.now(timezone.utc).year,
    }
    result = col.insert_one(doc)
    return {"inserted_id": str(result.inserted_id)}


def get_growth_timeline(limit: int = 20) -> list:
    col = _col("growth_log")
    if col is None:
        return []
    return list(col.find({}, {"_id": 0}).sort("created_at", DESCENDING).limit(limit))


def get_weekly_summary(year: int = None, week: int = None) -> dict:
    """Pull everything recorded in a given ISO week (defaults to current week)."""
    now         = datetime.now(timezone.utc)
    target_year = year  or now.year
    target_week = week  or now.isocalendar()[1]
    query       = {"week": target_week, "year": target_year}

    def _fetch(collection_name):
        col = _col(collection_name)
        return list(col.find(query, {"_id": 0}).sort("created_at", 1)) if col is not None else []

    return {
        "year":        target_year,
        "week":        target_week,
        "reflections": _fetch("reflections"),
        "incidents":   _fetch("incidents"),
        "growth":      _fetch("growth_log"),
    }
