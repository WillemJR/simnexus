import unittest
import threading
import time
import os
import shutil
import numpy as np
from simnexus.actions import WorkAction
from simnexus.remote_actions import RemoteAction, ServerAction

class FileGenTask(WorkAction):
    def solve(self, val_dict=None):
        # Create dummy files
        with open('data.txt', 'w') as f: f.write('data')
        with open('image.png', 'w') as f: f.write('image')
        with open('log.log', 'w') as f: f.write('log')
        return True

class EchoTask(WorkAction):
    """Returns its inputs plus a numpy array, exercising the restricted
    JSON serialization in both directions."""
    def solve(self, val_dict=None):
        return {'received': val_dict, 'curve': np.array([0.0, 0.5, 1.0])}

class TestRemotePatterns(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ServerAction(port=50052)
        cls.server.add_graph("file_gen", FileGenTask("gen"), "Generates dummy files")
        cls.server.add_graph("echo", EchoTask("echo"), "Echoes val_dict and a numpy array")
        cls.server_thread = threading.Thread(target=cls.server.start, daemon=True)
        cls.server_thread.start()
        time.sleep(1) # Wait for server

    @classmethod
    def tearDownClass(cls):
        cls.server.stop()

    def test_specific_pattern(self):
        remote = RemoteAction("rem1", "file_gen", 'localhost:50052', output_patterns=['data.txt'])
        remote.solve({})
        self.assertTrue(os.path.exists('data.txt'))
        self.assertFalse(os.path.exists('image.png'))
        self.assertFalse(os.path.exists('log.log'))
        # Cleanup
        if os.path.exists('data.txt'): os.remove('data.txt')

    def test_wildcard_pattern(self):
        remote = RemoteAction("rem2", "file_gen", 'localhost:50052', output_patterns=['*.png'])
        remote.solve({})
        self.assertFalse(os.path.exists('data.txt'))
        self.assertTrue(os.path.exists('image.png'))
        self.assertFalse(os.path.exists('log.log'))
        # Cleanup
        if os.path.exists('image.png'): os.remove('image.png')

    def test_multiple_patterns(self):
        remote = RemoteAction("rem3", "file_gen", 'localhost:50052', output_patterns=['*.txt', '*.log'])
        remote.solve({})
        self.assertTrue(os.path.exists('data.txt'))
        self.assertFalse(os.path.exists('image.png'))
        self.assertTrue(os.path.exists('log.log'))
        # Cleanup
        if os.path.exists('data.txt'): os.remove('data.txt')
        if os.path.exists('log.log'): os.remove('log.log')

    def test_json_serialization_roundtrip(self):
        remote = RemoteAction("rem_echo", "echo", 'localhost:50052')
        result = remote.solve({'K': 0.2, 'T': 75, 'label': 'case_1'})
        self.assertEqual(result['received'], {'K': 0.2, 'T': 75, 'label': 'case_1'})
        self.assertTrue(np.array_equal(result['curve'], np.array([0.0, 0.5, 1.0])))

    def test_unserializable_val_dict_raises(self):
        from simnexus.errors import SerializationError
        remote = RemoteAction("rem_bad", "echo", 'localhost:50052')
        with self.assertRaises(SerializationError):
            remote.solve({'payload': object()})

    def test_no_patterns(self):
        remote = RemoteAction("rem4", "file_gen", 'localhost:50052', output_patterns=[])
        remote.solve({})
        self.assertFalse(os.path.exists('data.txt'))
        self.assertFalse(os.path.exists('image.png'))
        self.assertFalse(os.path.exists('log.log'))

if __name__ == '__main__':
    unittest.main()
