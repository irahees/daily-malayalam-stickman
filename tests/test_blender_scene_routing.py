from __future__ import annotations

import ast
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RENDERER = ROOT / "src" / "blender_full_renderer.py"
VIDEO_PIPELINE = ROOT / "src" / "create_video_3d.py"


def load_category_function():
    tree = ast.parse(RENDERER.read_text(encoding="utf-8"))
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "category_for")
    module = ast.Module(body=[node], type_ignores=[])
    namespace = {}
    exec(compile(module, str(RENDERER), "exec"), namespace)
    return namespace["category_for"]


class BlenderSceneRoutingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.category_for = load_category_function()
        cls.renderer_source = RENDERER.read_text(encoding="utf-8")

    def test_current_story_topics_route_to_specific_sets(self):
        examples = {
            "വിത്തിന്റെ വളർച്ചാ യാത്ര": "seed",
            "പൂച്ച മുരളുന്നതിന്റെ കാരണം": "cat",
            "നായയുടെ വാലാട്ടലിന്റെ അർത്ഥം": "dog",
            "മത്സ്യം ശ്വസിക്കുന്ന രീതി": "fish",
            "ഐസ് വെള്ളത്തിൽ പൊങ്ങുന്നത്": "ice",
            "മഴവില്ലിന്റെ ഏഴ് നിറങ്ങൾ": "rainbow",
        }
        for story, expected in examples.items():
            with self.subTest(story=story):
                self.assertEqual(self.category_for(story), expected)

    def test_specific_topics_have_registered_3d_builders(self):
        for category in ("seed", "cat", "dog", "fish", "ice", "rainbow"):
            with self.subTest(category=category):
                self.assertIn(f'"{category}":build_{category}', self.renderer_source)
                self.assertIn(f"def build_{category}(", self.renderer_source)

    def test_specialized_categories_are_checked_before_generic_water(self):
        source = self.renderer_source
        self.assertLess(source.index('return "fish"'), source.index('return "rain"'))
        self.assertLess(source.index('return "ice"'), source.index('return "rain"'))
        self.assertLess(source.index('return "rainbow"'), source.index('return "rain"'))

    def test_full_video_pipeline_targets_30_fps_and_safe_subtitles(self):
        source = VIDEO_PIPELINE.read_text(encoding="utf-8")
        self.assertIn("FPS=30", source)
        self.assertIn('"-r","30"', source)
        self.assertIn("(18,735,522,900)", source)


if __name__ == "__main__":
    unittest.main()
