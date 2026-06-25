"""conversation_store 턴 순서 안정성 테스트 (defect #2)."""
import os
import tempfile
import unittest

from tests.util_fixture import set_test_env

set_test_env()

_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
os.environ["USER_DB_PATH"] = _tmp.name

from backend import conversation_store


class ConversationTurnOrderTest(unittest.TestCase):
    def test_turns_returned_in_insertion_order_even_within_same_second(self):
        session = conversation_store.get_or_create_session(None, None)
        session_id = session["session_id"]

        expected = []
        for index in range(8):
            role = "user" if index % 2 == 0 else "assistant"
            content = f"메시지-{index}"
            conversation_store.add_turn(
                session_id,
                role,
                content,
                intent="docs" if role == "assistant" else None,
            )
            expected.append((role, content))

        turns = conversation_store.get_turns(session_id)
        self.assertEqual([(turn["role"], turn["content"]) for turn in turns], expected)

    def test_latest_user_and_assistant_intent_are_readable(self):
        session = conversation_store.get_or_create_session(None, None)
        session_id = session["session_id"]
        conversation_store.add_turn(session_id, "user", "필요한 서류가 뭐야?")
        conversation_store.add_turn(session_id, "assistant", "서류 안내", intent="docs")
        conversation_store.add_turn(session_id, "user", "그 서류는 어디서 발급해?")

        turns = conversation_store.get_turns(session_id)
        self.assertEqual(turns[-1]["content"], "그 서류는 어디서 발급해?")
        last_assistant = next(turn for turn in reversed(turns) if turn["role"] == "assistant")
        self.assertEqual(last_assistant["intent"], "docs")


if __name__ == "__main__":
    unittest.main()
