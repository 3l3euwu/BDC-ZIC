import importlib.util
import pathlib
import unittest

path = pathlib.Path(__file__).resolve().parents[1] / 'mod/BDC_ZIC/panel/panel.py'
spec = importlib.util.spec_from_file_location('panel', path)
panel = importlib.util.module_from_spec(spec)
spec.loader.exec_module(panel)

class PresetTests(unittest.TestCase):
    def test_spotify_window_and_song_title(self):
        self.assertTrue(panel.matches_preset('Spotify', 'spotify.exe', 'Song — Artist'))
        self.assertTrue(panel.matches_preset('Spotify', 'browser.exe', 'Spotify – Web Player'))
        self.assertFalse(panel.matches_preset('Spotify', 'spotify.exe', ''))
        self.assertFalse(panel.matches_preset('Spotify', 'other.exe', 'Song — Artist'))

    def test_yolotube_and_youtube(self):
        self.assertTrue(panel.matches_preset('YoloTube / YouTube', 'chrome.exe', 'Track – YouTube'))
        self.assertTrue(panel.matches_preset('YoloTube / YouTube', 'foo.exe', 'YOLOTUBE'))
        self.assertFalse(panel.matches_preset('YoloTube / YouTube', 'youtube.exe', ''))
        self.assertFalse(panel.matches_preset('YoloTube / YouTube', 'other.exe', 'Other'))

    def test_launch_steam_uri(self):
        calls = []
        panel.launch_game(calls.append)
        self.assertEqual(calls, ['steam://rungameid/2406770'])

    def test_all_and_unknown(self):
        self.assertTrue(panel.matches_preset('All processes', 'foo.exe', ''))
        self.assertFalse(panel.matches_preset('Unknown', 'foo.exe', 'Spotify'))


class EffectSettingsTests(unittest.TestCase):
    def test_round_trip_and_disabled_level(self):
        import tempfile
        from unittest.mock import patch
        class Var:
            def __init__(self, value): self.value = value
            def get(self): return self.value
        class Status:
            def set(self, value): raise AssertionError(value)
        with tempfile.TemporaryDirectory() as folder, patch.object(panel, 'STREAM', pathlib.Path(folder)):
            instance = panel.Panel.__new__(panel.Panel)
            instance.volume = Var(7)
            instance.effect_vars = {'reverb': (Var(True), Var(8)), 'muffle': (Var(False), Var(4))}
            instance.status = Status()
            self.assertTrue(instance.save_effects())
            text = (pathlib.Path(folder) / 'effects.ini').read_text()
            self.assertIn('reverb=8', text)
            self.assertIn('muffle=0', text)
            self.assertIn('muffle_level=4', text)
            loaded = instance.load_effects()
            self.assertEqual(loaded['reverb'], (True, 8))
            self.assertEqual(loaded['muffle'], (False, 4))
            self.assertEqual(loaded['volume'], 7)

if __name__ == '__main__': unittest.main()
