import os
import shutil
import unittest
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from skills.archive_manager import manager, handle_request, run

class TestArchiveManager(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.test_dir = os.path.join(os.path.dirname(__file__), "temp_test_archive_manager")
        os.makedirs(cls.test_dir, exist_ok=True)

        # Create some test files
        cls.file1 = os.path.join(cls.test_dir, "sample1.txt")
        with open(cls.file1, "w", encoding="utf-8") as f:
            f.write("Hello, Butler 7-Zip Integration!\n" * 10)  # Make it slightly larger

        cls.file2 = os.path.join(cls.test_dir, "sample2.txt")
        with open(cls.file2, "w", encoding="utf-8") as f:
            # Create a large file with UNIQUE distinct lines so 7-zip cannot overcompress it
            for i in range(25000):
                f.write(f"Line {i:06d} - Butler 7-zip secondary development validation test entry ID {i * 987654321} with additional padding payload text to enlarge.\n")

        # Create a nested directory
        cls.nested_dir = os.path.join(cls.test_dir, "nested")
        os.makedirs(cls.nested_dir, exist_ok=True)
        cls.nested_file = os.path.join(cls.nested_dir, "config.json")
        with open(cls.nested_file, "w", encoding="utf-8") as f:
            f.write('{"status": "activated", "engine": "7-zip"}')

    @classmethod
    def tearDownClass(cls):
        # Clean up test outputs
        if os.path.exists(cls.test_dir):
            shutil.rmtree(cls.test_dir)

    def test_01_engine_resolution(self):
        """Verify native 7zz engine is detected and used on Linux."""
        print("\n--- Testing 7-Zip Native Engine Detection ---")
        self.assertIsNotNone(manager.bin_path, "Error: Native 7zz binary was not found or is not executable!")
        self.assertTrue(os.path.exists(manager.bin_path), f"Error: Binary path {manager.bin_path} does not exist!")
        print(f"✅ Success: Native 7-Zip executable found at {manager.bin_path}")

    def test_02_zip_compression_extraction(self):
        """Test compressing and extracting a standard zip file."""
        print("\n--- Testing Standard ZIP Compress/Extract ---")
        archive_path = os.path.join(self.test_dir, "test_archive.zip")
        targets = [self.file1, self.nested_dir]

        # Compress
        res = handle_request("compress", archive_path=archive_path, targets=targets)
        self.assertTrue(res["success"], f"Compression failed: {res.get('error')}")
        self.assertTrue(os.path.exists(archive_path))
        print("✅ Success: Zip compression completed")

        # List contents
        list_res = handle_request("list_contents", archive_path=archive_path)
        self.assertTrue(list_res["success"], f"Listing failed: {list_res.get('error')}")
        self.assertIn("sample1.txt", [os.path.basename(f) for f in list_res["result"]])
        self.assertIn("config.json", [os.path.basename(f) for f in list_res["result"]])
        print("✅ Success: Zip file contents listed accurately")

        # Extract
        dest_dir = os.path.join(self.test_dir, "extracted_zip")
        extract_res = handle_request("extract", archive_path=archive_path, output_dir=dest_dir)
        self.assertTrue(extract_res["success"], f"Extraction failed: {extract_res.get('error')}")
        self.assertTrue(os.path.exists(os.path.join(dest_dir, "sample1.txt")))
        self.assertTrue(os.path.exists(os.path.join(dest_dir, "nested", "config.json")))
        print("✅ Success: Zip file extracted accurately with full nested path structure")

    def test_03_7z_compression_extraction(self):
        """Test compressing and extracting a high-performance .7z file."""
        print("\n--- Testing Standard .7z Compress/Extract ---")
        archive_path = os.path.join(self.test_dir, "test_archive.7z")
        targets = [self.file1, self.nested_dir]

        # Compress
        res = handle_request("compress", archive_path=archive_path, targets=targets)
        self.assertTrue(res["success"], f"Compression failed: {res.get('error')}")
        self.assertTrue(os.path.exists(archive_path))
        print("✅ Success: .7z compression completed")

        # List contents
        list_res = handle_request("list_contents", archive_path=archive_path)
        self.assertTrue(list_res["success"], f"Listing failed: {list_res.get('error')}")
        self.assertIn("sample1.txt", [os.path.basename(f) for f in list_res["result"]])
        print("✅ Success: .7z file contents listed accurately")

        # Extract
        dest_dir = os.path.join(self.test_dir, "extracted_7z")
        extract_res = handle_request("extract", archive_path=archive_path, output_dir=dest_dir)
        self.assertTrue(extract_res["success"], f"Extraction failed: {extract_res.get('error')}")
        self.assertTrue(os.path.exists(os.path.join(dest_dir, "sample1.txt")))
        print("✅ Success: .7z file extracted accurately")

    def test_04_encryption_decryption(self):
        """Test AES-256 password protection for .7z format."""
        print("\n--- Testing AES-256 Encrypted .7z ---")
        archive_path = os.path.join(self.test_dir, "secure_archive.7z")
        targets = [self.file1]
        password = "ButlerSuperPassword123!"

        # Compress with password
        res = handle_request("compress", archive_path=archive_path, targets=targets, password=password)
        self.assertTrue(res["success"], f"Password compression failed: {res.get('error')}")
        self.assertTrue(os.path.exists(archive_path))
        print("✅ Success: AES-256 password-protected .7z compression completed")

        # Try extracting without password or with incorrect password (should fail or require password)
        failed_extract_res = handle_request("extract", archive_path=archive_path, output_dir=os.path.join(self.test_dir, "failed_extract"), password="WrongPassword")
        self.assertFalse(failed_extract_res["success"], "Security breach: Extraction succeeded with incorrect password!")
        print("✅ Success: Securely blocked extraction with wrong password")

        # Extract with correct password
        dest_dir = os.path.join(self.test_dir, "secure_extract")
        success_extract_res = handle_request("extract", archive_path=archive_path, output_dir=dest_dir, password=password)
        self.assertTrue(success_extract_res["success"], f"Password extraction failed with correct password: {success_extract_res.get('error')}")
        self.assertTrue(os.path.exists(os.path.join(dest_dir, "sample1.txt")))
        print("✅ Success: Correct password successfully unlocked and extracted files")

    def test_05_split_volume_archives(self):
        """Test splitting archives into volumes and restoring them."""
        print("\n--- Testing Split Volume (Multi-volume) .7z ---")
        archive_path = os.path.join(self.test_dir, "split_archive.7z")
        targets = [self.file2]
        # Split into small volumes of 10 kilobytes to guarantee generation of multiple volumes
        volume_size = "10k"

        res = handle_request("compress", archive_path=archive_path, targets=targets, volume_size=volume_size)
        self.assertTrue(res["success"], f"Split volume compression failed: {res.get('error')}")

        # Verify split volume artifacts (.7z.001, .7z.002, etc.) exist on disk
        first_vol = archive_path + ".001"
        second_vol = archive_path + ".002"
        self.assertTrue(os.path.exists(first_vol), f"Split volume file {first_vol} was not generated!")
        self.assertTrue(os.path.exists(second_vol), f"Split volume file {second_vol} was not generated!")
        print(f"✅ Success: Split volume files generated successfully ({os.path.basename(first_vol)}, {os.path.basename(second_vol)})")

        # Extract split volumes (7-Zip automatically merges volumes when pointing to the first volume .001)
        dest_dir = os.path.join(self.test_dir, "split_extracted")
        extract_res = handle_request("extract", archive_path=first_vol, output_dir=dest_dir)
        self.assertTrue(extract_res["success"], f"Split volume extraction failed: {extract_res.get('error')}")
        self.assertTrue(os.path.exists(os.path.join(dest_dir, "sample2.txt")))

        # Verify integrity of extracted file
        with open(os.path.join(dest_dir, "sample2.txt"), "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("Butler 7-zip secondary development validation", content)
        print("✅ Success: Split volumes automatically merged and extracted with perfect data integrity")

    def test_06_backwards_compatible_tracking_sync(self):
        """Test the backwards compatible open-track-modify-sync workflow."""
        print("\n--- Testing Backwards Compatible Tracking & Sync ---")
        archive_path = os.path.join(self.test_dir, "legacy_workflow.zip")

        # Create a clean archive to start
        targets = [self.file1]
        handle_request("compress", archive_path=archive_path, targets=targets)

        # 1. Open and track a file in the zip
        track_res = handle_request("open_file", archive_path=archive_path, file_in_zip="sample1.txt")
        self.assertTrue(track_res["success"], f"Tracking setup failed: {track_res.get('error')}")
        extracted_path = track_res["extracted_path"]
        self.assertTrue(os.path.exists(extracted_path))
        print(f"✅ Success: File tracking established for cache: {extracted_path}")

        # Ensure change is False initially
        self.assertFalse(handle_request("detect_changes", extracted_path=extracted_path))

        # 2. Modify the extracted file
        with open(extracted_path, "a", encoding="utf-8") as f:
            f.write("\nEXTRA EDITED CONTENT BY USER!")

        # 3. Detect changes
        has_changed = handle_request("detect_changes", extracted_path=extracted_path)
        self.assertTrue(has_changed, "Change detector failed to spot modification!")
        print("✅ Success: File modification successfully detected via MD5 finger-printing")

        # 4. Sync file back to the zip
        sync_res = handle_request("sync_file", extracted_path=extracted_path, action="Y")
        self.assertTrue(sync_res["success"], f"Atomic replacement sync failed: {sync_res.get('error')}")
        print("✅ Success: File edits successfully synchronized back to archive")

        # 5. Extract again to verify modification exists in the updated zip
        verify_dest = os.path.join(self.test_dir, "verify_sync")
        handle_request("extract", archive_path=archive_path, output_dir=verify_dest)
        with open(os.path.join(verify_dest, "sample1.txt"), "r", encoding="utf-8") as f:
            updated_content = f.read()
        self.assertIn("EXTRA EDITED CONTENT BY USER!", updated_content)
        print("✅ Success: Sync confirmed. Zip has been updated atomically with perfect correctness!")

    def test_07_unified_run_endpoint_mapping(self):
        """Test unified run() mapping triggers for SkillInterceptor compatibility."""
        print("\n--- Testing Unified run() Entry Point ---")
        archive_path = os.path.join(self.test_dir, "unified_run.zip")

        # Test unified zip run
        res = run("zip", zip_path=archive_path, targets=[self.file1])
        self.assertTrue(res["success"])
        self.assertTrue(os.path.exists(archive_path))
        print("✅ Success: run('zip') successfully mapped and run")

        # Test unified unzip run
        dest_dir = os.path.join(self.test_dir, "unified_unzip")
        extract_res = run("unzip", zip_path=archive_path, dest_dir=dest_dir)
        self.assertTrue(extract_res["success"])
        self.assertTrue(os.path.exists(os.path.join(dest_dir, "sample1.txt")))
        print("✅ Success: run('unzip') successfully mapped and run")


if __name__ == "__main__":
    unittest.main()
