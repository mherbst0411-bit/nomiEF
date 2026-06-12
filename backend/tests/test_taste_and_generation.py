"""Tests for the Taste Profile Engine and Prompt Compiler.

Pure-stdlib (unittest) by design: the core IP must be testable with no
installation step. Run: python -m unittest discover backend/tests
"""

import unittest

from backend.app.taste.compiler import compile_spec
from backend.app.taste.engine import (FeedbackSignal, TasteProfile,
                                      TrackAttributes)


def _track(**kw) -> TrackAttributes:
    base = dict(genres=["lo-fi"], moods=["chill"], instruments=["piano"],
                tempo_bpm=80.0, energy=0.3, has_vocals=False)
    base.update(kw)
    return TrackAttributes(**base)


class TestTasteEngine(unittest.TestCase):

    def test_likes_increase_weights(self):
        p = TasteProfile()
        p.apply(FeedbackSignal("like", _track()))
        self.assertGreater(p.genres["lo-fi"], 0)
        self.assertGreater(p.moods["chill"], 0)
        self.assertGreater(p.instruments["piano"], 0)

    def test_dislikes_decrease_weights(self):
        p = TasteProfile()
        p.apply(FeedbackSignal("dislike", _track(genres=["edm"])))
        self.assertLess(p.genres["edm"], 0)

    def test_weights_saturate_within_bounds(self):
        p = TasteProfile()
        for _ in range(500):
            p.apply(FeedbackSignal("save", _track()))
        self.assertLessEqual(p.genres["lo-fi"], 1.0)
        for _ in range(500):
            p.apply(FeedbackSignal("dislike", _track()))
        self.assertGreaterEqual(p.genres["lo-fi"], -1.0)

    def test_learning_rate_decays_with_experience(self):
        p = TasteProfile()
        early = p.learning_rate
        p.event_count = 500
        self.assertLess(p.learning_rate, early)

    def test_tempo_converges_toward_liked_tempo(self):
        p = TasteProfile()
        for _ in range(40):
            p.apply(FeedbackSignal("like", _track(tempo_bpm=124.0)))
        self.assertAlmostEqual(p.tempo.value, 124.0, delta=5.0)
        self.assertGreater(p.tempo.confidence, 0.5)

    def test_skip_pushes_tempo_away(self):
        p = TasteProfile()
        p.apply(FeedbackSignal("like", _track(tempo_bpm=100.0)))
        before = p.tempo.value
        p.apply(FeedbackSignal("skip", _track(tempo_bpm=160.0)))
        self.assertLess(p.tempo.value, before)  # moved away from 160

    def test_unknown_event_raises(self):
        p = TasteProfile()
        with self.assertRaises(ValueError):
            p.apply(FeedbackSignal("teleport", _track()))

    def test_onboarding_seeds_profile(self):
        p = TasteProfile()
        p.seed_from_onboarding(genres=["Jazz", "  Soul "], moods=["warm"],
                               tempo_bpm=95, energy=0.4,
                               prefers_vocals=True)
        self.assertIn("jazz", p.genres)        # normalized
        self.assertIn("soul", p.genres)        # trimmed + normalized
        self.assertEqual(p.tempo.value, 95)
        self.assertEqual(p.vocal_affinity.value, 1.0)

    def test_roundtrip_serialization(self):
        p = TasteProfile()
        p.seed_from_onboarding(genres=["jazz"], moods=["warm"], tempo_bpm=95)
        p.apply(FeedbackSignal("like", _track()))
        restored = TasteProfile.from_json(p.to_json())
        self.assertEqual(restored.event_count, p.event_count)
        self.assertEqual(restored.genres, {k: round(v, 4)
                                           for k, v in p.genres.items()})

    def test_maturity_progression(self):
        p = TasteProfile()
        self.assertEqual(p.maturity, "getting to know you")
        p.event_count = 10
        self.assertEqual(p.maturity, "learning your taste")
        p.event_count = 50
        self.assertEqual(p.maturity, "knows you")


class TestPromptCompiler(unittest.TestCase):

    def _mature_profile(self) -> TasteProfile:
        p = TasteProfile()
        for _ in range(20):
            p.apply(FeedbackSignal("like", _track(
                genres=["lo-fi", "jazz"], moods=["chill"],
                instruments=["piano"], tempo_bpm=85, energy=0.3)))
            p.apply(FeedbackSignal("dislike", _track(
                genres=["death metal"], moods=["aggressive"],
                instruments=["distorted guitar"], tempo_bpm=180,
                energy=0.95)))
        return p

    def test_profile_shapes_spec(self):
        p = self._mature_profile()
        spec = compile_spec(p, "something for studying")
        self.assertIn("lo-fi", spec.prompt_tags)
        self.assertIn("death metal", spec.negative_tags)
        self.assertIsNotNone(spec.tempo_bpm)
        self.assertTrue(spec.personalization_trace["applied"])

    def test_strength_zero_disables_personalization(self):
        p = self._mature_profile()
        spec = compile_spec(p, "anything", personalization_strength=0.0)
        self.assertEqual(spec.prompt_tags, [])
        self.assertEqual(spec.negative_tags, [])
        self.assertIsNone(spec.tempo_bpm)

    def test_user_prompt_not_duplicated_or_overridden(self):
        p = self._mature_profile()
        spec = compile_spec(p, "a lo-fi beat for rainy days")
        self.assertNotIn("lo-fi", spec.prompt_tags)  # already in prompt
        self.assertEqual(spec.user_prompt, "a lo-fi beat for rainy days")

    def test_lyrics_imply_vocals(self):
        p = TasteProfile()
        spec = compile_spec(p, "a ballad", lyrics="city lights and rain")
        self.assertTrue(spec.want_vocals)

    def test_duration_clamped(self):
        p = TasteProfile()
        spec = compile_spec(p, "epic", duration_seconds=9999)
        self.assertLessEqual(spec.duration_seconds, 240)

    def test_trace_is_explainable(self):
        p = self._mature_profile()
        spec = compile_spec(p, "music for a road trip")
        dims = {a["dimension"] for a in spec.personalization_trace["applied"]}
        self.assertIn("genre", dims)


class TestMockBackend(unittest.TestCase):

    def test_mock_generates_playable_wav(self):
        import wave as wave_mod
        import io
        from backend.app.generation.backends import MockBackend
        from backend.app.taste.compiler import GenerationSpec

        spec = GenerationSpec(prompt_tags=["lo-fi"], user_prompt="test",
                              duration_seconds=10, tempo_bpm=90, energy=0.4)
        result = MockBackend().generate(spec)
        self.assertEqual(result.audio_format, "wav")
        with wave_mod.open(io.BytesIO(result.audio_bytes)) as w:
            self.assertGreater(w.getnframes(), 0)
            self.assertEqual(w.getframerate(), 22050)

    def test_mock_is_deterministic_per_prompt(self):
        from backend.app.generation.backends import MockBackend
        from backend.app.taste.compiler import GenerationSpec
        spec = GenerationSpec(prompt_tags=[], user_prompt="same prompt",
                              duration_seconds=8)
        a = MockBackend().generate(spec).audio_bytes
        b = MockBackend().generate(spec).audio_bytes
        self.assertEqual(a, b)

    def test_different_prompts_differ(self):
        from backend.app.generation.backends import MockBackend
        from backend.app.taste.compiler import GenerationSpec
        a = MockBackend().generate(GenerationSpec(
            prompt_tags=[], user_prompt="prompt A",
            duration_seconds=8)).audio_bytes
        b = MockBackend().generate(GenerationSpec(
            prompt_tags=[], user_prompt="prompt B",
            duration_seconds=8)).audio_bytes
        self.assertNotEqual(a, b)


if __name__ == "__main__":
    unittest.main()
