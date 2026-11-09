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

    def test_all_and_unknown(self):
        self.assertTrue(panel.matches_preset('All processes', 'foo.exe', ''))
        self.assertFalse(panel.matches_preset('Unknown', 'foo.exe', 'Spotify'))

if __name__ == '__main__': unittest.main()
