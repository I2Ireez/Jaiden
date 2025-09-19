#!/usr/bin/env python

import unittest
import tempfile
import shutil
import json
from pathlib import Path
from unittest.mock import patch, MagicMock, call

# Add project root to path for imports
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from spotify2ytmusic.backend import copy_all_playlists
from spotify2ytmusic.checkpoint import CheckpointManager


class TestCopyAllPlaylistsResume(unittest.TestCase):
    """Test resume functionality across multiple playlists in copy_all_playlists"""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.checkpoint_dir = Path(self.temp_dir) / "checkpoints"

        # Create a mock playlists.json with multiple playlists
        self.test_playlists = {
            "playlists": [
                {
                    "id": "playlist_1",
                    "name": "Test Playlist 1",
                    "tracks": [
                        {
                            "track": {
                                "name": "Song 1",
                                "artists": [{"name": "Artist 1"}],
                                "album": {"name": "Album 1"}
                            }
                        }
                    ]
                },
                {
                    "id": "playlist_2",
                    "name": "Test Playlist 2",
                    "tracks": [
                        {
                            "track": {
                                "name": "Song 2",
                                "artists": [{"name": "Artist 2"}],
                                "album": {"name": "Album 2"}
                            }
                        }
                    ]
                },
                {
                    "id": "playlist_3",
                    "name": "Test Playlist 3",
                    "tracks": [
                        {
                            "track": {
                                "name": "Song 3",
                                "artists": [{"name": "Artist 3"}],
                                "album": {"name": "Album 3"}
                            }
                        }
                    ]
                }
            ]
        }

        # Save test playlists to temp file
        self.playlists_file = Path(self.temp_dir) / "playlists.json"
        with open(self.playlists_file, 'w') as f:
            json.dump(self.test_playlists, f)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    @patch('spotify2ytmusic.backend.get_ytmusic')
    @patch('spotify2ytmusic.backend.load_playlists_json')
    @patch('spotify2ytmusic.backend.get_playlist_id_by_name')
    @patch('spotify2ytmusic.backend._ytmusic_create_playlist')
    @patch('spotify2ytmusic.backend.copier')
    @patch('spotify2ytmusic.backend.CheckpointManager')
    def test_resume_skips_completed_playlists(self, mock_checkpoint_manager, mock_copier,
                                            mock_create_playlist, mock_get_playlist_id,
                                            mock_load_playlists, mock_get_ytmusic):
        """Test that resume functionality skips already completed playlists"""

        # Setup mocks
        mock_load_playlists.return_value = self.test_playlists
        mock_yt = MagicMock()
        mock_get_ytmusic.return_value = mock_yt
        mock_get_playlist_id.return_value = None  # Force playlist creation
        mock_create_playlist.return_value = "test_playlist_id"

        # Setup checkpoint managers
        master_checkpoint = MagicMock()
        individual_checkpoint = MagicMock()

        def checkpoint_manager_side_effect(name):
            if name == "all_playlists_master":
                return master_checkpoint
            else:
                return individual_checkpoint

        mock_checkpoint_manager.side_effect = checkpoint_manager_side_effect

        # Simulate that playlist_1 is already completed
        master_checkpoint.checkpoint_path.exists.return_value = True
        master_checkpoint.load_checkpoint.return_value = {
            'completed_playlists': ['playlist_1']
        }
        individual_checkpoint.checkpoint_path.exists.return_value = False
        individual_checkpoint.get_statistics.return_value = {'successful': 0}

        # Run copy_all_playlists with resume=True
        copy_all_playlists(resume=True, dry_run=True)

        # Verify that copier was only called for playlist_2 and playlist_3 (not playlist_1)
        self.assertEqual(mock_copier.call_count, 2, "Copier should be called only for non-completed playlists")

        # Verify master checkpoint was used correctly
        master_checkpoint.checkpoint_path.exists.assert_called_once()
        master_checkpoint.load_checkpoint.assert_called_once()

    @patch('spotify2ytmusic.backend.get_ytmusic')
    @patch('spotify2ytmusic.backend.load_playlists_json')
    @patch('spotify2ytmusic.backend.get_playlist_id_by_name')
    @patch('spotify2ytmusic.backend._ytmusic_create_playlist')
    @patch('spotify2ytmusic.backend.copier')
    @patch('spotify2ytmusic.backend.CheckpointManager')
    def test_master_checkpoint_updated_on_completion(self, mock_checkpoint_manager, mock_copier,
                                                   mock_create_playlist, mock_get_playlist_id,
                                                   mock_load_playlists, mock_get_ytmusic):
        """Test that master checkpoint is updated when playlists complete"""

        # Setup mocks
        mock_load_playlists.return_value = self.test_playlists
        mock_yt = MagicMock()
        mock_get_ytmusic.return_value = mock_yt
        mock_get_playlist_id.return_value = None
        mock_create_playlist.return_value = "test_playlist_id"

        # Setup checkpoint managers
        master_checkpoint = MagicMock()
        individual_checkpoint = MagicMock()

        def checkpoint_manager_side_effect(name):
            if name == "all_playlists_master":
                return master_checkpoint
            else:
                return individual_checkpoint

        mock_checkpoint_manager.side_effect = checkpoint_manager_side_effect

        # No existing master checkpoint
        master_checkpoint.checkpoint_path.exists.return_value = False
        individual_checkpoint.checkpoint_path.exists.return_value = False

        # Run copy_all_playlists (not dry run to trigger checkpoint updates)
        copy_all_playlists(resume=True, dry_run=False)

        # Verify master checkpoint save_checkpoint was called for each completed playlist
        # Note: Set order is not guaranteed, so we check the calls differently
        self.assertEqual(master_checkpoint.save_checkpoint.call_count, 3)

        # Check that each call contains the expected cumulative playlists
        calls = master_checkpoint.save_checkpoint.call_args_list

        # First call should have 1 playlist
        call_1_playlists = set(calls[0][0][0]['completed_playlists'])
        self.assertEqual(len(call_1_playlists), 1)
        self.assertIn('playlist_1', call_1_playlists)

        # Second call should have 2 playlists
        call_2_playlists = set(calls[1][0][0]['completed_playlists'])
        self.assertEqual(len(call_2_playlists), 2)
        self.assertIn('playlist_1', call_2_playlists)
        self.assertIn('playlist_2', call_2_playlists)

        # Third call should have all 3 playlists
        call_3_playlists = set(calls[2][0][0]['completed_playlists'])
        self.assertEqual(len(call_3_playlists), 3)
        self.assertIn('playlist_1', call_3_playlists)
        self.assertIn('playlist_2', call_3_playlists)
        self.assertIn('playlist_3', call_3_playlists)

    @patch('spotify2ytmusic.backend.get_ytmusic')
    @patch('spotify2ytmusic.backend.load_playlists_json')
    @patch('spotify2ytmusic.backend.get_playlist_id_by_name')
    @patch('spotify2ytmusic.backend._ytmusic_create_playlist')
    @patch('spotify2ytmusic.backend.copier')
    @patch('spotify2ytmusic.backend.CheckpointManager')
    def test_reset_checkpoint_clears_master_checkpoint(self, mock_checkpoint_manager, mock_copier,
                                                     mock_create_playlist, mock_get_playlist_id,
                                                     mock_load_playlists, mock_get_ytmusic):
        """Test that --reset-checkpoint clears the master checkpoint"""

        # Setup mocks
        mock_load_playlists.return_value = self.test_playlists
        mock_yt = MagicMock()
        mock_get_ytmusic.return_value = mock_yt
        mock_get_playlist_id.return_value = None
        mock_create_playlist.return_value = "test_playlist_id"

        # Setup checkpoint managers
        master_checkpoint = MagicMock()
        individual_checkpoint = MagicMock()

        def checkpoint_manager_side_effect(name):
            if name == "all_playlists_master":
                return master_checkpoint
            else:
                return individual_checkpoint

        mock_checkpoint_manager.side_effect = checkpoint_manager_side_effect
        individual_checkpoint.checkpoint_path.exists.return_value = False

        # Run copy_all_playlists with reset_checkpoint=True
        copy_all_playlists(reset_checkpoint=True, dry_run=True)

        # Verify master checkpoint was cleared
        master_checkpoint.clear.assert_called_once()

        # Verify individual checkpoints were also cleared for each playlist
        self.assertEqual(individual_checkpoint.clear.call_count, 3)

    @patch('spotify2ytmusic.backend.get_ytmusic')
    @patch('spotify2ytmusic.backend.load_playlists_json')
    @patch('spotify2ytmusic.backend.get_playlist_id_by_name')
    @patch('spotify2ytmusic.backend._ytmusic_create_playlist')
    @patch('spotify2ytmusic.backend.copier')
    @patch('spotify2ytmusic.backend.CheckpointManager')
    def test_mixed_completion_state_resume(self, mock_checkpoint_manager, mock_copier,
                                         mock_create_playlist, mock_get_playlist_id,
                                         mock_load_playlists, mock_get_ytmusic):
        """Test resume with mixed completion states (some complete, some partial, some new)"""

        # Setup mocks
        mock_load_playlists.return_value = self.test_playlists
        mock_yt = MagicMock()
        mock_get_ytmusic.return_value = mock_yt
        mock_get_playlist_id.return_value = None
        mock_create_playlist.return_value = "test_playlist_id"

        # Setup checkpoint managers with complex return logic
        master_checkpoint = MagicMock()
        individual_checkpoints = {}

        def checkpoint_manager_side_effect(name):
            if name == "all_playlists_master":
                return master_checkpoint
            else:
                if name not in individual_checkpoints:
                    individual_checkpoints[name] = MagicMock()
                return individual_checkpoints[name]

        mock_checkpoint_manager.side_effect = checkpoint_manager_side_effect

        # Master checkpoint shows playlist_1 is completed
        master_checkpoint.checkpoint_path.exists.return_value = True
        master_checkpoint.load_checkpoint.return_value = {
            'completed_playlists': ['playlist_1']
        }

        # Individual checkpoint states:
        # playlist_1: Should not be checked (already completed)
        # playlist_2: Has partial progress
        # playlist_3: No checkpoint (new)
        def individual_exists_side_effect():
            def exists_func(checkpoint_obj):
                if checkpoint_obj == individual_checkpoints.get('all_playlists_playlist_2'):
                    return True
                return False
            return exists_func

        # Set up individual checkpoint existence
        for name, checkpoint in individual_checkpoints.items():
            if 'playlist_2' in name:
                checkpoint.checkpoint_path.exists.return_value = True
                checkpoint.get_statistics.return_value = {'successful': 5}
            else:
                checkpoint.checkpoint_path.exists.return_value = False
                checkpoint.get_statistics.return_value = {'successful': 0}

        # Run copy_all_playlists with resume=True
        copy_all_playlists(resume=True, dry_run=True)

        # Verify:
        # - copier called only for playlist_2 and playlist_3 (playlist_1 skipped)
        # - playlist_2 checkpoint was checked for partial progress
        # - playlist_3 treated as new
        self.assertEqual(mock_copier.call_count, 2, "Should process only non-completed playlists")

        # Verify that checkpoint manager was created for playlist_2 and playlist_3 but not playlist_1
        expected_checkpoint_names = set()
        for call_args in mock_checkpoint_manager.call_args_list:
            expected_checkpoint_names.add(call_args[0][0])

        self.assertIn("all_playlists_master", expected_checkpoint_names)
        self.assertIn("all_playlists_playlist_2", expected_checkpoint_names)
        self.assertIn("all_playlists_playlist_3", expected_checkpoint_names)
        # playlist_1 checkpoint should not be created since it's already completed


if __name__ == "__main__":
    unittest.main()