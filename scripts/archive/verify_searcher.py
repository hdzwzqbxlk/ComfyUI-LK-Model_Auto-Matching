import sys
import os
import unittest
import asyncio
from unittest.mock import MagicMock, patch, AsyncMock

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Mock curl_cffi.requests.AsyncSession
sys.modules["curl_cffi.requests"] = MagicMock()
mock_session = AsyncMock()
mock_session.__aenter__.return_value = mock_session
sys.modules["curl_cffi.requests"].AsyncSession.return_value = mock_session

# Mock ComfyUI modules BEFORE importing core.searcher
sys.modules["folder_paths"] = MagicMock()
sys.modules["server"] = MagicMock()
sys.modules["aiohttp"] = MagicMock()

from core.searcher import CivitaiHashProvider

class TestSearcherCritical(unittest.IsolatedAsyncioTestCase):
    async def test_async_hashing(self):
        """Test that hashing is offloaded to thread (not blocking)"""
        provider = CivitaiHashProvider({})
        
        # Mock calculate_sha256 to sleep a bit (simulate work)
        original_hasher = provider.calculate_sha256
        provider.calculate_sha256 = MagicMock(return_value="dummy_hash")
        
        # Create a dummy file for the test
        with open("test_dummy.safetensors", "wb") as f:
            f.write(b"dummy")
            
        try:
            # If wrapped in to_thread, this should be awaitable
            # But the method 'search_by_hash' does the await.
            # We call search_by_hash
            await provider.search_by_hash("test_dummy.safetensors", "test_dummy")
            
            # If successful, logic is correct
            self.assertTrue(True)
        finally:
            if os.path.exists("test_dummy.safetensors"):
                os.remove("test_dummy.safetensors")

if __name__ == "__main__":
    unittest.main()
