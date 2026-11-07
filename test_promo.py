"""Offline regression checks: python -m unittest -v test_promo.py

Uses a fake Telegram client and clock; never signs in or sends messages.
"""
import asyncio
import logging
import os
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import AsyncMock, patch


class SlowModeWaitError(Exception):
    def __init__(self, seconds):
        self.seconds = seconds


class FloodWaitError(Exception):
    def __init__(self, seconds):
        self.seconds = seconds


class StopSimulation(BaseException):
    pass


class ChatInviteAlready:
    def __init__(self, chat):
        self.chat = chat


def load_promo(extra="", defaults=None):
    telethon = types.ModuleType("telethon")
    telethon.TelegramClient = lambda *args, **kwargs: types.SimpleNamespace()
    telethon.errors = types.SimpleNamespace(
        SlowModeWaitError=SlowModeWaitError, FloodWaitError=FloodWaitError,
    )
    telethon.functions = types.SimpleNamespace(messages=types.SimpleNamespace(
        CheckChatInviteRequest=lambda hash: types.SimpleNamespace(hash=hash),
    ))
    telethon.types = types.SimpleNamespace(
        MessageMediaWebPage=type("WebPage", (), {}),
        ChatInviteAlready=ChatInviteAlready,
    )
    sessions = types.ModuleType("telethon.sessions")
    sessions.StringSession = lambda value: value
    module = types.ModuleType("promo_under_test")
    env = {
        "TG_API_ID": "1", "TG_API_HASH": "test", "TG_SESSION": "test",
        "TG_EXTRA_CHATS": extra,
    }
    path = Path(__file__).with_name("telegram_promo.py")
    with patch.dict(sys.modules, {"telethon": telethon, "telethon.sessions": sessions}):
        with patch.dict(os.environ, env):
            exec(compile(path.read_text(), str(path), "exec"), module.__dict__)
            if defaults is not None:
                module.DEFAULT_TARGET_CHATS = defaults
                module.TARGET_CHATS = module.get_target_chats()
    return module


class PromoTests(unittest.TestCase):
    def setUp(self):
        self.old_log_level = logging.root.manager.disable
        logging.disable(logging.CRITICAL)

    def tearDown(self):
        logging.disable(self.old_log_level)

    def simulate(self, module, end=4500, fail_send=None, fail_read=None, send_failures=None):
        now = 0
        sends = []
        reads = []

        async def sleep(delay):
            nonlocal now
            self.assertGreater(delay, 0)
            if now + delay > end:
                raise StopSimulation()
            now += delay

        async def read():
            reads.append(now)
            if fail_read and len(reads) == 1:
                raise fail_read
            return len(reads)

        async def send(chat, message):
            sends.append((now, chat, message))
            if send_failures and (now, chat) in send_failures:
                raise send_failures[(now, chat)]
            if fail_send and len(sends) == 1:
                raise fail_send

        module.get_latest_saved_message = read
        module.send_to_chat = send
        # Replace only the module's asyncio reference, not the real event loop.
        module.asyncio = types.SimpleNamespace(
            sleep=sleep,
            get_running_loop=lambda: types.SimpleNamespace(time=lambda: now),
        )
        with self.assertRaises(StopSimulation):
            asyncio.run(module.run_announcements())
        return sends, reads

    def test_requested_groups_and_75_minutes(self):
        module = load_promo()
        self.assertEqual(module.TARGET_CHATS, [
            "elitemethodchat", "gemini3369", "ddh992", "OpenHuge_ai", "Hdc5NmE9",
            "Claudeaichatss", "aitoolsbuynsell", "ChatgptPlusDeal", "saleslabss",
            "amygpt", "maoli9112", "pwawz8", "https://t.me/+S3GSX490EWo2NTY9",
            "quanziai", "asoftwarez",
        ])
        self.assertEqual(module.INTERVAL_SECONDS, 4500)

    def test_all_configured_groups_receive_one_message_per_round(self):
        module = load_promo()
        sends, reads = self.simulate(module)
        self.assertEqual(sends, [
            (time, chat, message)
            for time, message in [(0, 1), (4500, 2)]
            for chat in module.TARGET_CHATS
        ])
        self.assertEqual(len(sends), 30)
        self.assertEqual(reads, [0, 4500])

    def test_usernames_links_and_duplicates(self):
        module = load_promo(
            "@GroupOne,https://t.me/GroupTwo/\nGROUPONE،@elitemethodchat;telegram.me/GroupThree",
            defaults=["elitemethodchat"],
        )
        self.assertEqual(module.TARGET_CHATS, [
            "elitemethodchat", "GroupOne", "GroupTwo", "GroupThree",
        ])

    def test_invalid_targets_fail_before_sending(self):
        for value in ["https://t.me/+", "https://t.me/group/123", "-10012345"]:
            with self.subTest(value=value), self.assertRaises(RuntimeError):
                load_promo(value)

    def test_private_invite_formats_preserve_case_and_remove_duplicates(self):
        module = load_promo(
            "https://t.me/+S3GSX490EWo2NTY9,"
            "https://telegram.me/joinchat/S3GSX490EWo2NTY9/,"
            "https://t.me/+s3GSX490EWo2NTY9",
            defaults=["elitemethodchat"],
        )
        self.assertEqual(module.TARGET_CHATS, [
            "elitemethodchat", "https://t.me/+S3GSX490EWo2NTY9",
            "https://t.me/+s3GSX490EWo2NTY9",
        ])

    def test_extra_existing_groups_are_not_sent_twice(self):
        module = load_promo("https://t.me/Hdc5NmE9,@hdc5nme9,https://t.me/+S3GSX490EWo2NTY9")
        self.assertEqual(len(module.TARGET_CHATS), 15)

    def test_private_group_is_resolved_for_existing_member(self):
        module = load_promo()
        entity = object()
        module.client = AsyncMock(return_value=ChatInviteAlready(entity))
        module.reconnect = AsyncMock()
        result = asyncio.run(module.resolve_target_chat("https://t.me/+S3GSX490EWo2NTY9"))
        self.assertIs(result, entity)
        module.client.assert_awaited_once()
        self.assertEqual(module.client.await_args.args[0].hash, "S3GSX490EWo2NTY9")

    def test_private_nonmember_or_peek_cannot_send(self):
        module = load_promo()
        # A preview can have a chat field, but is not proof of membership.
        module.client = AsyncMock(return_value=types.SimpleNamespace(chat=object()))
        module.reconnect = AsyncMock()
        message = types.SimpleNamespace(message="ad", entities=None, media=None)
        with self.assertRaisesRegex(RuntimeError, "must join"):
            asyncio.run(module.send_to_chat("https://t.me/+S3GSX490EWo2NTY9", message))
        module.client.send_message.assert_not_awaited()
        module.client.send_file.assert_not_awaited()

    def test_private_resolution_flood_wait_reaches_scheduler(self):
        module = load_promo()
        module.client = AsyncMock(side_effect=FloodWaitError(120))
        module.reconnect = AsyncMock()
        with self.assertRaises(FloodWaitError):
            asyncio.run(module.resolve_target_chat("https://t.me/+S3GSX490EWo2NTY9"))

    def test_latest_saved_text_and_media_are_preserved(self):
        for media in [None, object()]:
            with self.subTest(media=media):
                module = load_promo()
                entity = object()
                formatting = [object()]
                message = types.SimpleNamespace(message="Saved promotion", entities=formatting, media=media)
                module.client = AsyncMock(return_value=ChatInviteAlready(entity))
                module.client.get_messages.return_value = [message]
                module.reconnect = AsyncMock()

                async def run():
                    saved = await module.get_latest_saved_message()
                    await module.send_to_chat("https://t.me/+S3GSX490EWo2NTY9", saved)

                asyncio.run(run())
                module.client.get_messages.assert_awaited_once_with("me", limit=1)
                if media is None:
                    module.client.send_message.assert_awaited_once_with(
                        entity, "Saved promotion", formatting_entities=formatting,
                    )
                else:
                    module.client.send_file.assert_awaited_once_with(
                        entity, media, caption="Saved promotion", formatting_entities=formatting,
                    )

    def test_each_group_receives_each_round_with_fresh_message(self):
        sends, reads = self.simulate(load_promo("othergroup", defaults=["elitemethodchat"]), end=9000)
        self.assertEqual(sends, [
            (0, "elitemethodchat", 1), (0, "othergroup", 1),
            (4500, "elitemethodchat", 2), (4500, "othergroup", 2),
            (9000, "elitemethodchat", 3), (9000, "othergroup", 3),
        ])
        self.assertEqual(reads, [0, 4500, 9000])

    def test_one_group_failure_does_not_stop_others(self):
        sends, _ = self.simulate(load_promo("othergroup", defaults=["elitemethodchat"]), fail_send=RuntimeError("denied"))
        self.assertEqual([(t, chat) for t, chat, _ in sends], [
            (0, "elitemethodchat"), (0, "othergroup"),
            (4500, "elitemethodchat"), (4500, "othergroup"),
        ])

    def test_slow_mode_only_delays_affected_group(self):
        sends, _ = self.simulate(
            load_promo("othergroup", defaults=["elitemethodchat"]), end=9000, fail_send=SlowModeWaitError(7200),
        )
        self.assertEqual([(t, chat) for t, chat, _ in sends], [
            (0, "elitemethodchat"), (0, "othergroup"),
            (4500, "othergroup"), (7202, "elitemethodchat"),
            (9000, "othergroup"),
        ])

    def test_repeated_slow_mode_retries_without_blocking_other_groups(self):
        module = load_promo("othergroup", defaults=["elitemethodchat"])
        sends, reads = self.simulate(module, end=4684, send_failures={
            (0, "elitemethodchat"): SlowModeWaitError(60),
            (62, "elitemethodchat"): SlowModeWaitError(120),
        })
        self.assertEqual([(time, chat) for time, chat, _ in sends], [
            (0, "elitemethodchat"), (0, "othergroup"),
            (62, "elitemethodchat"), (184, "elitemethodchat"),
            (4500, "othergroup"), (4684, "elitemethodchat"),
        ])
        self.assertEqual(reads, [0, 62, 184, 4500, 4684])
        self.assertEqual([message for _, _, message in sends], [1, 1, 2, 3, 4, 5])

    def test_flood_wait_pauses_all_groups_and_reads(self):
        sends, reads = self.simulate(
            load_promo("othergroup", defaults=["elitemethodchat"]), end=9002, fail_send=FloodWaitError(9000),
        )
        self.assertEqual([(t, chat) for t, chat, _ in sends], [
            (0, "elitemethodchat"),
            (9002, "elitemethodchat"), (9002, "othergroup"),
        ])
        self.assertEqual(reads, [0, 9002])

    def test_short_flood_wait_keeps_failed_group_interval(self):
        sends, reads = self.simulate(
            load_promo("othergroup", defaults=["elitemethodchat"]), end=4512, fail_send=FloodWaitError(10),
        )
        self.assertEqual([(t, chat) for t, chat, _ in sends], [
            (0, "elitemethodchat"), (12, "othergroup"),
            (4500, "elitemethodchat"), (4512, "othergroup"),
        ])
        self.assertEqual(reads, [0, 12, 4500, 4512])

    def test_saved_message_failure_waits_before_retry(self):
        sends, reads = self.simulate(
            load_promo("othergroup", defaults=["elitemethodchat"]), fail_read=RuntimeError("empty"),
        )
        self.assertEqual(reads, [0, 4500])
        self.assertEqual([(t, chat) for t, chat, _ in sends], [
            (4500, "elitemethodchat"), (4500, "othergroup"),
        ])

    def test_saved_message_flood_wait_is_respected(self):
        sends, reads = self.simulate(
            load_promo("othergroup", defaults=["elitemethodchat"]), end=9002, fail_read=FloodWaitError(9000),
        )
        self.assertEqual(reads, [0, 9002])
        self.assertTrue(all(t == 9002 for t, _, _ in sends))
        self.assertEqual(len(sends), 2)


if __name__ == "__main__":
    unittest.main()
