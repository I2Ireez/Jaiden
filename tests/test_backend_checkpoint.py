#!/usr/bin/env python

import unittest
import tempfile
import shutil
import ast
from pathlib import Path

# Add project root to path for imports
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from spotify2ytmusic.checkpoint import CheckpointManager


class TestBackendCheckpointIntegration(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.checkpoint_dir = Path(self.temp_dir) / "checkpoints"

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_copier_function_signature_has_checkpoint_manager(self):
        """Test that copier function signature includes checkpoint_manager parameter"""
        # Read the backend.py file directly and parse the AST
        backend_path = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) / 'spotify2ytmusic' / 'backend.py'
        with open(backend_path, 'r') as f:
            content = f.read()

        # Parse the AST to find the copier function
        tree = ast.parse(content)

        copier_found = False
        checkpoint_param_found = False

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == 'copier':
                copier_found = True
                # Check if checkpoint_manager is in the parameters
                for arg in node.args.args:
                    if arg.arg == 'checkpoint_manager':
                        checkpoint_param_found = True
                        break
                break

        self.assertTrue(copier_found, "copier function not found in backend.py")
        self.assertTrue(checkpoint_param_found, "checkpoint_manager parameter not found in copier function signature")

    def test_copier_function_has_checkpoint_logic(self):
        """Test that copier function contains checkpoint-related logic"""
        # Read the backend.py file and look for checkpoint-related code
        backend_path = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) / 'spotify2ytmusic' / 'backend.py'
        with open(backend_path, 'r') as f:
            content = f.read()

        # Check for key checkpoint functionality
        self.assertIn("checkpoint_manager", content, "checkpoint_manager variable not found in backend.py")
        self.assertIn("get_processed_indices", content, "get_processed_indices call not found")
        self.assertIn("save_progress", content, "save_progress call not found")
        self.assertIn("save_failed_track", content, "save_failed_track call not found")
        self.assertIn("RESUMING", content, "Resume message not found")

    def test_copier_function_enumerates_tracks(self):
        """Test that copier function enumerates tracks for index tracking"""
        backend_path = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) / 'spotify2ytmusic' / 'backend.py'
        with open(backend_path, 'r') as f:
            content = f.read()

        # Should enumerate tracks to get indices
        self.assertIn("enumerate(src_tracks)", content, "Track enumeration not found")
        self.assertIn("for idx,", content, "Index variable in loop not found")


if __name__ == "__main__":
    unittest.main()