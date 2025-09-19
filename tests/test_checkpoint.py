#!/usr/bin/env python

import unittest
import json
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock
from datetime import datetime

# Add project root to path for imports
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from spotify2ytmusic.checkpoint import CheckpointManager


class TestCheckpointManager(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.checkpoint_dir = Path(self.temp_dir) / "checkpoints"

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_checkpoint_manager_initialization(self):
        """Test that CheckpointManager initializes with correct paths"""
        manager = CheckpointManager("playlist_123", checkpoint_dir=str(self.checkpoint_dir))
        self.assertEqual(manager.playlist_id, "playlist_123")
        self.assertEqual(manager.checkpoint_path, self.checkpoint_dir / "playlist_123.json")

    def test_checkpoint_directory_creation(self):
        """Test that checkpoint directory is created if it doesn't exist"""
        manager = CheckpointManager("test_playlist", checkpoint_dir=str(self.checkpoint_dir))
        self.assertTrue(self.checkpoint_dir.exists())

    def test_save_first_track_progress(self):
        """Test saving progress for the first track"""
        manager = CheckpointManager("test_playlist", checkpoint_dir=str(self.checkpoint_dir))
        manager.save_progress(0, "youtube_id_1", {
            "name": "Test Song",
            "artist": "Test Artist"
        })

        # Verify progress is saved using public API
        processed_indices = manager.get_processed_indices()
        self.assertEqual(len(processed_indices), 1)
        self.assertIn(0, processed_indices)

        stats = manager.get_statistics()
        self.assertEqual(stats["successful"], 1)

    def test_save_multiple_tracks_progress(self):
        """Test saving progress for multiple tracks preserves all"""
        manager = CheckpointManager("test_playlist", checkpoint_dir=str(self.checkpoint_dir))
        manager.save_progress(0, "vid1", {"name": "Song1"})
        manager.save_progress(1, "vid2", {"name": "Song2"})
        manager.save_progress(2, "vid3", {"name": "Song3"})

        processed_indices = manager.get_processed_indices()
        self.assertEqual(len(processed_indices), 3)
        self.assertEqual(processed_indices, {0, 1, 2})

        stats = manager.get_statistics()
        self.assertEqual(stats["last_index"], 2)

    def test_load_existing_checkpoint(self):
        """Test loading an existing checkpoint returns processed indices"""
        manager = CheckpointManager("test_playlist", checkpoint_dir=str(self.checkpoint_dir))
        manager.save_progress(0, "vid1", {"name": "Song1"})
        manager.save_progress(2, "vid2", {"name": "Song2"})
        manager.save_progress(5, "vid3", {"name": "Song3"})

        # Create new manager instance to simulate resume
        new_manager = CheckpointManager("test_playlist", checkpoint_dir=str(self.checkpoint_dir))
        processed = new_manager.get_processed_indices()

        self.assertEqual(processed, {0, 2, 5})
        self.assertEqual(new_manager.get_last_processed_index(), 5)

    def test_no_checkpoint_returns_empty_set(self):
        """Test that no checkpoint returns empty set of indices"""
        manager = CheckpointManager("new_playlist", checkpoint_dir=str(self.checkpoint_dir))
        processed = manager.get_processed_indices()
        self.assertEqual(processed, set())
        self.assertEqual(manager.get_last_processed_index(), -1)

    def test_save_failed_track(self):
        """Test saving failed track information"""
        manager = CheckpointManager("test_playlist", checkpoint_dir=str(self.checkpoint_dir))
        manager.save_failed_track(10, {"name": "Failed Song"}, "No match found")

        stats = manager.get_statistics()
        self.assertEqual(stats["failed"], 1)

        # Verify failed track was saved by checking it doesn't appear in processed indices
        processed_indices = manager.get_processed_indices()
        self.assertNotIn(10, processed_indices)

    def test_clear_checkpoint(self):
        """Test clearing checkpoint removes file"""
        manager = CheckpointManager("test_playlist", checkpoint_dir=str(self.checkpoint_dir))
        manager.save_progress(0, "vid1", {"name": "Song1"})
        self.assertTrue(manager.checkpoint_path.exists())

        manager.clear()
        self.assertFalse(manager.checkpoint_path.exists())

    def test_get_statistics(self):
        """Test getting transfer statistics"""
        manager = CheckpointManager("test_playlist", checkpoint_dir=str(self.checkpoint_dir))
        manager.save_progress(0, "vid1", {"name": "Song1"})
        manager.save_progress(1, "vid2", {"name": "Song2"})
        manager.save_failed_track(2, {"name": "Failed"}, "Not found")

        stats = manager.get_statistics()
        self.assertEqual(stats["successful"], 2)
        self.assertEqual(stats["failed"], 1)
        self.assertEqual(stats["last_index"], 1)


if __name__ == "__main__":
    unittest.main()