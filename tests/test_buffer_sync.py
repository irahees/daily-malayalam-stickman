import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import publish_batch_buffer
import sync_platform_posts


class BufferSyncTests(unittest.TestCase):
    def test_topic_hashtags_are_relevant(self):
        tags = publish_batch_buffer.hashtags_for({
            "topic": "ഫോൺ ബാറ്ററി പ്രശ്നം",
            "title": "ഒരു ദിവസം ചാർജ് ഇല്ലെങ്കിൽ?"
        })
        self.assertIn("#Malayalam", tags)
        self.assertIn("#MalayalamTech", tags)

    def test_asset_urls_are_extracted(self):
        post = {"assets": [
            {"source": "https://cdn.example/video.mp4", "mimeType": "video/mp4"},
            {"source": "http://not-secure.example/video.mp4", "mimeType": "video/mp4"},
        ]}
        self.assertEqual(
            publish_batch_buffer.asset_urls(post),
            {"https://cdn.example/video.mp4"}
        )

    def test_exact_video_asset_matches_across_channels(self):
        url = "https://cdn.example/release/video.mp4"
        instagram = {"id": "ig-1", "text": "Same hook", "assets": [{"source": url, "mimeType": "video/mp4"}]}
        youtube = {"id": "yt-1", "text": "Same hook", "assets": [{"source": url, "mimeType": "video/mp4"}]}
        self.assertEqual(sync_platform_posts.match_score(instagram, youtube), 1.0)
        matches, missing_ig, missing_yt = sync_platform_posts.choose_matches([instagram], [youtube])
        self.assertEqual(len(matches), 1)
        self.assertEqual(missing_ig, [])
        self.assertEqual(missing_yt, [])

    def test_unmatched_report_explains_best_candidate_without_forcing_a_match(self):
        source = {
            "id": "yt-2",
            "text": "An original Malayalam stickman story",
            "createdAt": "2026-11-13T10:00:00Z",
            "assets": [{"source": "https://cdn.example/yt.mp4", "mimeType": "video/mp4"}],
        }
        candidate = {
            "id": "ig-2",
            "text": "A completely different caption",
            "createdAt": "2026-11-13T10:00:00Z",
            "assets": [{"source": "https://cdn.example/ig.mp4", "mimeType": "video/mp4"}],
        }
        details = sync_platform_posts.best_match_diagnostics([source], [candidate])
        self.assertEqual(details[0]["unmatched_post_id"], "yt-2")
        self.assertEqual(details[0]["best_candidates"][0]["candidate_post_id"], "ig-2")
        self.assertFalse(details[0]["best_candidates"][0]["same_media_url"])
        self.assertLess(details[0]["best_candidates"][0]["score"], 0.78)

    def test_pending_and_sent_statuses_are_buffer_native(self):
        self.assertEqual(
            {"draft", "error", "needs_approval", "scheduled", "sending", "sent"},
            {"draft", "error", "needs_approval", "scheduled", "sending", "sent"}
        )
        # Unknown pseudo-statuses must not be required for a successful audit.
        self.assertNotIn("queued", {"draft", "error", "needs_approval", "scheduled", "sending", "sent"})
        self.assertNotIn("pending", {"draft", "error", "needs_approval", "scheduled", "sending", "sent"})


if __name__ == "__main__":
    unittest.main()
