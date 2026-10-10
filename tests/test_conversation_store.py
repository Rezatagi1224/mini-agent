import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import conversation_store


class ConversationStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.temp_dir.name)
        self.patcher = patch.object(conversation_store, "DATA_DIR", self.data_dir)
        self.patcher.start()

    def tearDown(self):
        self.patcher.stop()
        self.temp_dir.cleanup()

    def test_round_trip_keeps_only_last_12_user_assistant_messages(self):
        conversation_id = "web:session-123"
        messages = []
        for index in range(8):
            messages.extend([
                {"role": "user", "content": f"user-{index}"},
                {"role": "assistant", "content": f"assistant-{index}"},
            ])
        messages.append({"role": "system", "content": "must be removed"})

        saved = conversation_store.save_history(conversation_id, messages)
        loaded = conversation_store.load_history(conversation_id)

        self.assertEqual(len(saved), 12)
        self.assertEqual(loaded, saved)
        self.assertEqual(loaded[0]["content"], "user-2")
        self.assertTrue(all(item["role"] in ("user", "assistant") for item in loaded))

    def test_expired_conversation_is_deleted_on_read(self):
        conversation_id = "web:expired"
        path = conversation_store._file_for(conversation_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        old_time = (datetime.now(timezone.utc) - timedelta(days=31)).isoformat()
        path.write_text(json.dumps({
            "updated_at": old_time,
            "history": [{"role": "user", "content": "old"}]
        }), encoding="utf-8")

        self.assertEqual(conversation_store.load_history(conversation_id), [])
        self.assertFalse(path.exists())

    def test_message_ledger_prevents_duplicate_processing(self):
        conversation_id = "instagram:sender-1"
        self.assertTrue(conversation_store.claim_message(conversation_id, "mid-1"))
        self.assertEqual(conversation_store.message_state(conversation_id, "mid-1"), "processing")
        self.assertFalse(conversation_store.claim_message(conversation_id, "mid-1"))
        conversation_store.mark_message_processed(conversation_id, "mid-1")
        self.assertEqual(conversation_store.message_state(conversation_id, "mid-1"), "done")
        self.assertFalse(conversation_store.claim_message(conversation_id, "mid-1"))

    def test_failed_message_can_be_retried(self):
        conversation_id = "instagram:sender-2"
        self.assertTrue(conversation_store.claim_message(conversation_id, "mid-2"))
        conversation_store.release_message(conversation_id, "mid-2")
        self.assertEqual(conversation_store.message_state(conversation_id, "mid-2"), "new")
        self.assertTrue(conversation_store.claim_message(conversation_id, "mid-2"))

    def test_prune_expired_removes_stale_files_and_keeps_recent_ones(self):
        conversation_store.save_history("web:active", [{"role": "user", "content": "recent"}])
        stale = conversation_store._file_for("web:stale")
        stale.parent.mkdir(parents=True, exist_ok=True)
        old_time = (datetime.now(timezone.utc) - timedelta(days=31)).isoformat()
        stale.write_text(json.dumps({
            "updated_at": old_time,
            "history": [{"role": "user", "content": "old"}]
        }), encoding="utf-8")

        self.assertEqual(conversation_store.prune_expired(), 1)
        self.assertEqual(conversation_store.load_history("web:active")[0]["content"], "recent")
        self.assertFalse(stale.exists())


if __name__ == "__main__":
    unittest.main()
