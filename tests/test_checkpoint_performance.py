#!/usr/bin/env python

import unittest
import tempfile
import shutil
import json
import sys
import os
from pathlib import Path
from unittest.mock import patch, mock_open

# Add project root to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from spotify2ytmusic.checkpoint import CheckpointManager


class TestCheckpointPerformance(unittest.TestCase):
    """Test performance behavior and file optimization features of checkpoint system."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.checkpoint_dir = Path(self.temp_dir) / "checkpoints"
        self.checkpoint_dir.mkdir(exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_checkpoint_uses_append_only_storage_behavior(self):
        """Test that saving tracks appends to separate file instead of rewriting entire checkpoint."""
        checkpoint = CheckpointManager("append_test", str(self.checkpoint_dir))

        # Save first track
        checkpoint.save_progress(0, "vid_0", {"name": "Song 0"})

        # Check that a separate .processed file was created (not just .json)
        processed_file = checkpoint.checkpoint_dir / f"{checkpoint.playlist_id}.processed"
        self.assertTrue(processed_file.exists(),
                       "Should create separate .processed file for append-only storage")

        # Save second track
        initial_size = processed_file.stat().st_size
        checkpoint.save_progress(1, "vid_1", {"name": "Song 1"})
        new_size = processed_file.stat().st_size

        # File should have grown (appended), not rewritten
        self.assertGreater(new_size, initial_size,
                          "Processed file should grow by appending, not be rewritten")

    def test_checkpoint_stores_metadata_separately_from_track_data(self):
        """Test that metadata is stored separately from track data for efficiency."""
        checkpoint = CheckpointManager("metadata_test", str(self.checkpoint_dir))

        # Save some tracks
        checkpoint.save_progress(0, "vid_0", {"name": "Song 0"})
        checkpoint.save_progress(1, "vid_1", {"name": "Song 1"})

        # Should have separate metadata file
        metadata_file = checkpoint.checkpoint_dir / f"{checkpoint.playlist_id}.json"
        processed_file = checkpoint.checkpoint_dir / f"{checkpoint.playlist_id}.processed"

        self.assertTrue(metadata_file.exists(), "Should have metadata file")
        self.assertTrue(processed_file.exists(), "Should have processed tracks file")

        # Metadata file should be small (not contain all track data)
        metadata_size = metadata_file.stat().st_size
        processed_size = processed_file.stat().st_size

        # For small datasets, just ensure metadata is smaller than processed data
        # For larger datasets, the ratio would be much better
        self.assertLess(metadata_size, processed_size,
                       "Metadata file should be smaller than processed tracks file")

    def test_checkpoint_reading_indices_after_corruption_still_works(self):
        """Test that indices can be read even if main checkpoint file is corrupted (only possible with separate storage)."""
        checkpoint = CheckpointManager("corruption_test", str(self.checkpoint_dir))

        # Save some tracks
        for i in range(10):
            checkpoint.save_progress(i, f"vid_{i}", {"name": f"Song {i}"})

        # Corrupt the main checkpoint file (simulate file corruption)
        checkpoint.checkpoint_path.write_text("{ corrupted json data")

        # Should still work and return correct indices even with corrupted main file
        indices = checkpoint.get_processed_indices()
        self.assertEqual(len(indices), 10)
        self.assertEqual(indices, set(range(10)))

    def test_checkpoint_saves_to_append_only_log_file(self):
        """Test that saves append to a separate log file rather than modifying main JSON."""
        checkpoint = CheckpointManager("append_log_test", str(self.checkpoint_dir))

        # Save first track
        checkpoint.save_progress(0, "vid_0", {"name": "Song 0"})

        # Should create append-only log file
        log_file = checkpoint.checkpoint_dir / f"{checkpoint.playlist_id}.log"
        self.assertTrue(log_file.exists(), "Should create append-only log file for track saves")

        # Get initial log size
        initial_log_size = log_file.stat().st_size

        # Save second track
        checkpoint.save_progress(1, "vid_1", {"name": "Song 1"})

        # Log file should have grown (new entry appended)
        new_log_size = log_file.stat().st_size
        self.assertGreater(new_log_size, initial_log_size,
                         "Append-only log file should grow with new entries")

    def test_checkpoint_uses_index_cache_for_fast_lookups(self):
        """Test that checkpoint system maintains an in-memory index cache for O(1) lookups."""
        checkpoint = CheckpointManager("cache_test", str(self.checkpoint_dir))

        # Add several tracks to build up data
        for i in range(100):
            checkpoint.save_progress(i, f"vid_{i}", {"name": f"Song {i}"})

        # Should maintain in-memory index cache
        self.assertTrue(hasattr(checkpoint, '_index_cache'),
                       "Should maintain in-memory index cache for performance")

        # Cache should contain all saved indices
        expected_indices = set(range(100))
        actual_indices = checkpoint.get_processed_indices()
        self.assertEqual(actual_indices, expected_indices,
                        "Index cache should return all saved indices")

        # Cache should auto-update with new entries
        checkpoint.save_progress(150, "vid_150", {"name": "New Song"})
        updated_indices = checkpoint.get_processed_indices()
        self.assertIn(150, updated_indices, "Cache should auto-update with new entries")


if __name__ == "__main__":
    unittest.main()