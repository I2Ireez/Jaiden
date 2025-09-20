#!/usr/bin/env python

import unittest
import tempfile
import json
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add project root to path for imports
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from spotify2ytmusic.checkpoint import CheckpointManager


class TestFailedFilePreservation(unittest.TestCase):
    """Test that .failed files are preserved when checkpoint is cleared"""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.checkpoint_dir = Path(self.temp_dir) / ".checkpoint"
        self.checkpoint_dir.mkdir(exist_ok=True)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_both_processed_and_failed_preserved_after_clear(self):
        """CRITICAL: Both .processed and .failed files should be preserved when checkpoint is cleared"""
        # Create checkpoint manager and add both successful and failed tracks
        manager = CheckpointManager("test_playlist", checkpoint_dir=str(self.checkpoint_dir))

        # Add some successful tracks (simulating tracks 0-4999)
        manager.save_progress(0, "video_0", {
            "name": "Track 0",
            "artist": "Artist",
            "album": "Album"
        })
        manager.save_progress(1, "video_1", {
            "name": "Track 1",
            "artist": "Artist",
            "album": "Album"
        })
        manager.save_progress(4999, "video_4999", {
            "name": "Track 4999",
            "artist": "Artist",
            "album": "Album"
        })

        # Add some failed tracks (simulating tracks exceeding size limit)
        manager.save_failed_track(5000, {
            "name": "Track 5001",
            "artist": "Artist",
            "album": "Album"
        }, "playlist_size_exceeded: Track 5001 exceeds YouTube Music 5000 track limit")

        manager.save_failed_track(5001, {
            "name": "Track 5002",
            "artist": "Artist",
            "album": "Album"
        }, "playlist_size_exceeded: Track 5002 exceeds YouTube Music 5000 track limit")

        # Verify both files exist and have content
        processed_file = self.checkpoint_dir / "test_playlist.processed"
        failed_file = self.checkpoint_dir / "test_playlist.failed"

        self.assertTrue(processed_file.exists(), "Processed file should exist after saving successful tracks")
        self.assertTrue(failed_file.exists(), "Failed file should exist after saving failed tracks")

        # Read the content to verify it has our tracks
        with open(processed_file, 'r') as f:
            processed_content = f.read()
        self.assertIn("Track 0", processed_content, "Processed file should contain Track 0")
        self.assertIn("Track 4999", processed_content, "Processed file should contain Track 4999")

        with open(failed_file, 'r') as f:
            failed_content = f.read()
        self.assertIn("Track 5001", failed_content, "Failed file should contain Track 5001")
        self.assertIn("Track 5002", failed_content, "Failed file should contain Track 5002")
        self.assertIn("playlist_size_exceeded", failed_content, "Failed file should contain size limit error")

        # CRITICAL TEST: Clear the checkpoint (this is what happens after playlist completion)
        manager.clear()

        # BOTH FILES SHOULD STILL EXIST - this is the bug we're fixing
        self.assertTrue(processed_file.exists(),
                       "CRITICAL BUG: .processed file should be preserved after checkpoint.clear()")
        self.assertTrue(failed_file.exists(),
                       "CRITICAL BUG: .failed file should be preserved after checkpoint.clear()")

        # Content should still be there
        with open(processed_file, 'r') as f:
            processed_after_clear = f.read()
        self.assertIn("Track 0", processed_after_clear,
                     "Processed tracks should still be available after clear")
        self.assertIn("Track 4999", processed_after_clear,
                     "Processed tracks should still be available after clear")

        with open(failed_file, 'r') as f:
            failed_after_clear = f.read()
        self.assertIn("Track 5001", failed_after_clear,
                     "Failed tracks should still be available after clear")
        self.assertIn("Track 5002", failed_after_clear,
                     "Failed tracks should still be available after clear")

    def test_multiple_playlists_failed_files_preserved(self):
        """Test that failed files from multiple playlists are all preserved"""
        # Simulate two playlists with failed tracks
        manager1 = CheckpointManager("playlist_1", checkpoint_dir=str(self.checkpoint_dir))
        manager2 = CheckpointManager("playlist_2", checkpoint_dir=str(self.checkpoint_dir))

        # Add failed tracks to first playlist
        manager1.save_failed_track(5000, {"name": "P1 Track 5001"}, "size limit exceeded")

        # Add failed tracks to second playlist
        manager2.save_failed_track(5000, {"name": "P2 Track 5001"}, "size limit exceeded")

        # Clear first playlist (simulating completion)
        manager1.clear()

        # Both failed files should still exist
        failed_file1 = self.checkpoint_dir / "playlist_1.failed"
        failed_file2 = self.checkpoint_dir / "playlist_2.failed"

        self.assertTrue(failed_file1.exists(), "Playlist 1 failed file should be preserved")
        self.assertTrue(failed_file2.exists(), "Playlist 2 failed file should not be affected")

        # Verify content is preserved
        with open(failed_file1, 'r') as f:
            content1 = f.read()
        with open(failed_file2, 'r') as f:
            content2 = f.read()

        self.assertIn("P1 Track 5001", content1)
        self.assertIn("P2 Track 5001", content2)


if __name__ == '__main__':
    unittest.main()