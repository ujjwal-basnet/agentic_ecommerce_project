"""
Post Scheduler
--------------
Reads posts from scheduled_posts.json and publishes them at the right time.

scheduled_posts.json format:
[
  {
    "image_url": "https://example.com/photo.jpg",
    "caption": "Hello world! #instagram",
    "scheduled_time": "2026-04-13 10:00:00",
    "status": "pending"
  }
]

Statuses: pending → published / failed
"""

import json
import os
import time
from datetime import datetime
from instagram_api import create_image_container, publish_post

POSTS_FILE = os.path.join(os.path.dirname(__file__), "scheduled_posts.json")


def _load_posts() -> list:
    if os.path.exists(POSTS_FILE):
        with open(POSTS_FILE) as f:
            return json.load(f)
    return []


def _save_posts(posts: list):
    with open(POSTS_FILE, "w") as f:
        json.dump(posts, f, indent=2)


def schedule_post(image_url: str, caption: str, scheduled_time: str):
    """
    Add a post to the queue.
    scheduled_time format: "YYYY-MM-DD HH:MM:SS"
    """
    posts = _load_posts()
    posts.append({
        "image_url": image_url,
        "caption": caption,
        "scheduled_time": scheduled_time,
        "status": "pending",
    })
    _save_posts(posts)
    print(f"[scheduler] Post queued for {scheduled_time}")


def _publish_one(post: dict) -> str:
    """Try to publish a single post. Returns new status."""
    creation_id = create_image_container(post["image_url"], post["caption"])
    if not creation_id:
        return "failed"
    # Instagram recommends waiting ~30s between container creation and publish
    time.sleep(30)
    success = publish_post(creation_id)
    return "published" if success else "failed"


def check_and_publish():
    """Called by the scheduler loop. Publishes any due pending posts."""
    posts = _load_posts()
    now = datetime.now()
    changed = False

    for post in posts:
        if post["status"] != "pending":
            continue
        try:
            due = datetime.strptime(post["scheduled_time"], "%Y-%m-%d %H:%M:%S")
        except ValueError:
            print(f"[scheduler] Bad date format: {post['scheduled_time']}")
            continue

        if now >= due:
            print(f"[scheduler] Publishing post scheduled for {post['scheduled_time']}...")
            post["status"] = _publish_one(post)
            print(f"[scheduler] Status: {post['status']}")
            changed = True

    if changed:
        _save_posts(posts)


def run_loop(interval_seconds: int = 60):
    """Continuously check for due posts. Run in a background thread."""
    print("[scheduler] Starting post scheduler...")
    while True:
        check_and_publish()
        time.sleep(interval_seconds)


if __name__ == "__main__":
    # Quick CLI to add a scheduled post
    print("Schedule a new post")
    image_url = input("Image URL: ").strip()
    caption = input("Caption: ").strip()
    scheduled_time = input("Scheduled time (YYYY-MM-DD HH:MM:SS): ").strip()
    schedule_post(image_url, caption, scheduled_time)
