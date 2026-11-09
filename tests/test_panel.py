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


class OutputParsingTests(unittest.TestCase):
    def test_non_default_only_and_unicode(self):
        output = 'default\tid-default\tSpeakers\navailable\tid-music\tCasque é\n'
        self.assertEqual(panel.parse_outputs(output), [('id-music', 'Casque é')])
    def test_invalid_list_fails_closed(self):
        for value in ('garbage', 'unknown\tid\tname', 'available\t\tname'):
            with self.assertRaises(ValueError): panel.parse_outputs(value)
    def test_empty_list(self):
        self.assertEqual(panel.parse_outputs(''), [])

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
            instance.auto_room = Var(False)
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

class AutoRoomTests(unittest.TestCase):
    def test_room_effect_mapping(self):
        self.assertEqual(panel.auto_room_effects((0, 0, 0, 0)), {'reverb': 0, 'size': 0, 'distance': 0})
        self.assertEqual(panel.auto_room_effects((0, 2, 5, 400)), {'reverb': 0, 'size': 0, 'distance': 0})
        self.assertEqual(panel.auto_room_effects((8, 8, 5, 1600)), {'reverb': 8, 'size': 8, 'distance': 3})
        self.assertEqual(panel.auto_room_effects((10, 10, 5, 4000))['distance'], 10)

    def test_stale_partial_and_out_of_range(self):
        import tempfile
        import os
        with tempfile.TemporaryDirectory() as folder:
            p = pathlib.Path(folder) / 'room.txt'
            p.write_text('6 4 3 1200', encoding='ascii')
            stamp = p.stat().st_mtime
            self.assertEqual(panel.read_room(p, now=stamp), (6, 4, 3, 1200))
            self.assertIsNone(panel.read_room(p, now=stamp + 4))
            p.write_text('3 99 2 1200', encoding='ascii')
            self.assertIsNone(panel.read_room(p, now=p.stat().st_mtime))
            p.write_text('0 0', encoding='ascii')
            self.assertIsNone(panel.read_room(p, now=p.stat().st_mtime))

    def test_auto_room_is_locked_and_manual_preserved(self):
        import tempfile
        from unittest.mock import patch
        class Var:
            def __init__(self, value): self.value = value
            def get(self): return self.value
        class Status:
            def set(self, value): raise AssertionError(value)
        with tempfile.TemporaryDirectory() as folder, patch.object(panel, 'STREAM', pathlib.Path(folder)):
            instance = panel.Panel.__new__(panel.Panel)
            instance.volume, instance.auto_room, instance.status = Var(5), Var(True), Status()
            instance.effect_vars = {'reverb': (Var(False), Var(7)), 'size': (Var(True), Var(3)), 'distance': (Var(True), Var(6))}
            (panel.STREAM / 'auto-room').touch()
            (panel.STREAM / 'room.txt').write_text('8 6 4 1600')
            self.assertTrue(instance.save_effects())
            text = (panel.STREAM / 'effects.ini').read_text()
            self.assertIn('auto_room=0', text)
            self.assertIn('reverb=0', text); self.assertIn('size=3', text); self.assertIn('distance=6', text)
            self.assertFalse((panel.STREAM / 'auto-room').exists())
            self.assertFalse((panel.STREAM / 'room.txt').exists())
            self.assertFalse(instance.load_effects()['auto_room'])
            self.assertEqual(instance.load_effects()['reverb'], (False, 7))
            self.assertEqual(instance.load_effects()['size'], (True, 3))
            self.assertEqual(instance.load_effects()['distance'], (True, 6))

if __name__ == '__main__': unittest.main()
