import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import create_batch
import create_brief
import publish_batch_buffer


IST = ZoneInfo("Asia/Kolkata")


class DailyBatchTests(unittest.TestCase):
    def test_story_bank_has_42_unique_topics_and_titles(self):
        stories = create_brief.STORIES
        self.assertEqual(len(stories), 42)
        self.assertEqual(len({story["topic"] for story in stories}), 42)
        self.assertEqual(len({story["title"] for story in stories}), 42)

    def test_seven_daily_batches_do_not_repeat_stories(self):
        first_day = datetime(2026, 11, 15, 8, 0, tzinfo=IST).date()
        tracker_rows = []
        all_titles = []
        for offset in range(7):
            day = first_day + timedelta(days=offset)
            selected = create_batch.select_stories(day, tracker_rows)
            batch = [story["title"] for story in selected]
            self.assertEqual(len(batch), create_batch.BATCH_SIZE)
            self.assertEqual(len(set(batch)), create_batch.BATCH_SIZE)
            all_titles.extend(batch)
            tracker_rows.extend(
                {"batch_date_ist": day.isoformat(), "title": title}
                for title in batch
            )
        self.assertEqual(len(set(all_titles)), 42)

    def test_recent_tracker_titles_are_skipped(self):
        batch_day = datetime(2026, 11, 16, 8, 0, tzinfo=IST).date()
        tracker_rows = [
            {"batch_date_ist": "2026-11-14", "title": "കടൽവെള്ളം കുടിക്കാമോ?"},
            {"batch_date_ist": "2026-11-15", "title": "കേരളത്തിലെ കടകൾ അടച്ചാൽ?"},
        ]
        selected = create_batch.select_stories(batch_day, tracker_rows)
        titles = [story["title"] for story in selected]
        self.assertEqual(len(titles), 6)
        self.assertEqual(len(set(titles)), 6)
        self.assertNotIn("കടൽവെള്ളം കുടിക്കാമോ?", titles)
        self.assertNotIn("കേരളത്തിലെ കടകൾ അടച്ചാൽ?", titles)

    def test_titles_can_rotate_after_the_six_day_cooldown(self):
        batch_day = datetime(2026, 11, 16, 8, 0, tzinfo=IST).date()
        tracker_rows = [
            {"batch_date_ist": "2026-11-09", "title": "കടൽവെള്ളം കുടിക്കാമോ?"},
        ]
        selected = create_batch.select_stories(batch_day, tracker_rows)
        titles = [story["title"] for story in selected]
        self.assertIn("കടൽവെള്ളം കുടിക്കാമോ?", titles)

    def test_instagram_slots_use_sunday_monday_wednesday_friday(self):
        now = datetime(2026, 11, 15, 8, 41, tzinfo=IST)
        slots = publish_batch_buffer.next_slots("instagram", now, 4, [])
        self.assertEqual(
            [(slot.weekday(), slot.strftime("%H:%M")) for slot in slots],
            [(6, "12:00"), (0, "19:30"), (2, "19:30"), (4, "19:30")],
        )

    def test_youtube_slots_use_sunday_monday_wednesday_friday(self):
        now = datetime(2026, 11, 15, 8, 41, tzinfo=IST)
        slots = publish_batch_buffer.next_slots("youtube", now, 4, [])
        self.assertEqual(
            [(slot.weekday(), slot.strftime("%H:%M")) for slot in slots],
            [(6, "13:00"), (0, "18:30"), (2, "18:30"), (4, "18:30")],
        )

    def test_existing_post_blocks_the_whole_day(self):
        now = datetime(2026, 11, 15, 8, 41, tzinfo=IST)
        existing = [{
            "status": "scheduled",
            "dueAt": "2026-11-16T10:00:00Z",  # Monday afternoon in IST, not the planned slot
        }]
        slots = publish_batch_buffer.next_slots("instagram", now, 4, existing)
        self.assertNotEqual(slots[0].date().isoformat(), "2026-11-16")
        self.assertEqual(slots[0].strftime("%H:%M"), "12:00")


if __name__ == "__main__":
    unittest.main()
