import unittest
import os
import sys
import json
import shutil
import tempfile

# Add root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../proxion-keyring")))

from proxion_keyring.lens import Lens

class TestLens(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.mount_dir = os.path.join(self.test_dir, "Z_Drive")
        os.makedirs(self.mount_dir)
        
        # Create dummy files
        self.test_files = ["photo1.jpg", "holiday.png", "notes.txt"]
        for f in self.test_files:
            with open(os.path.join(self.mount_dir, f), "w") as f_out:
                f_out.write("test data")
        
        # Initialize Lens
        self.lens = Lens(data_dir=self.test_dir)
        # Mock MOUNT_POINTS for testing
        self.lens.MOUNT_POINTS = {self.mount_dir: "Test Mount"}

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_indexing(self):
        """Verify that Lens correctly indexes files in a mount point."""
        self.lens.scan_mounts()
        self.assertEqual(len(self.lens.index), 3)
        
        indexed_names = [item["name"] for item in self.lens.index]
        for name in self.test_files:
            self.assertIn(name, indexed_names)

    def test_search(self):
        """Verify that searching the index works."""
        self.lens.scan_mounts()
        
        # Exact match
        results = self.lens.search("photo1.jpg")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["name"], "photo1.jpg")
        
        # Partial match
        results = self.lens.search("photo")
        self.assertEqual(len(results), 1)
        
        # Case insensitive
        results = self.lens.search("PHOTO")
        self.assertEqual(len(results), 1)

        # No results
        results = self.lens.search("nonexistent")
        self.assertEqual(len(results), 0)

if __name__ == "__main__":
    unittest.main()
