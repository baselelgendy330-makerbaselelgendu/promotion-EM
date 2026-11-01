import asyncio
import logging
import os
import re

from telethon import TelegramClient, errors, functions, types
from telethon.sessions import StringSession


def required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing Railway variable: {name}")
    return value


API_ID = int(required_env("TG_API_ID"))
API_HASH = required_env("TG_API_HASH")
SESSION_STRING = required_env("TG_SESSION")

DEFAULT_TARGET_CHATS = [
    "elitemethodchat",
    "gemini3369",
    "ddh992",
    "OpenHuge_ai",
    "Hdc5NmE9",
    "Claudeaichatss",
    "aitoolsbuynsell",
    "ChatgptPlusDeal",
    "saleslabss",
    "amygpt",
    "maoli9112",
    "pwawz8",
    "https://t.me/+S3GSX490EWo2NTY9",
    "quanziai",
]
INTERVAL_SECONDS = 75 * 60


def get_target_chats() -> list[str]:
    """Keep configured groups and add public or private links from TG_EXTRA_CHATS."""
    extra_chats = re.split(r"[,;\s،]+", os.getenv("TG_EXTRA_CHATS", ""))
    targets = []
    seen = set()

    for value in [*DEFAULT_TARGET_CHATS, *extra_chats]:
        if not value:
            continue
        invite = re.fullmatch(
            r"(?:https?://)?(?:t\.me|telegram\.me)/(?:\+|joinchat/)([A-Za-z0-9_-]+)/?",
            value,
            flags=re.IGNORECASE,
        )
        if invite:
            # Invite hashes are case-sensitive; normalize only the link format.
            chat = "https://t.me/+" + invite.group(1)
            key = chat
        else:
            chat = re.sub(
                r"^(?:https?://)?(?:t\.me|telegram\.me)/", "", value,
                flags=re.IGNORECASE,
            ).rstrip("/").removeprefix("@")
            if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", chat):
                raise RuntimeError(
                    "TG_EXTRA_CHATS must contain group usernames, public links, "
                    "or private t.me/+hash / t.me/joinchat/hash invite links, "
                    "separated by commas or newlines. "
                    "Message links and numeric group IDs are not supported."
                )
            key = chat.lower()
        if key not in seen:
            targets.append(chat)
            seen.add(key)
    return targets


TARGET_CHATS = get_target_chats()


def chat_label(chat: str) -> str:
    return "private invite group" if chat.startswith("https://t.me/+") else "@" + chat

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

client = TelegramClient(
    StringSession(SESSION_STRING),
    API_ID,
    API_HASH,
    auto_reconnect=True,
    connection_retries=20,
    request_retries=10,
    retry_delay=5,
    flood_sleep_threshold=0,
    receive_updates=False,
)


async def reconnect() -> None:
    """Keep trying until the Telegram connection is available again."""
    while not client.is_connected():
        try:
            logging.warning("Telegram disconnected. Reconnecting...")
            await client.connect()

            if not await client.is_user_authorized():
                raise RuntimeError(
                    "TG_SESSION is no longer authorized. "
                    "Generate a new TG_SESSION."
                )

            logging.info("Telegram connection restored.")

        except Exception:
            logging.exception("Reconnect failed. Retrying in 10 seconds.")
            await asyncio.sleep(10)


async def telegram_call(operation):
    """Run one Telegram operation and retry after connection loss."""
    last_error = None

    for attempt in range(1, 4):
        try:
            await reconnect()
            return await operation()

        except (ConnectionError, OSError) as error:
            last_error = error
            logging.warning(
                "Connection lost during request (attempt %s/3).",
                attempt,
            )

            try:
                await client.disconnect()
            except Exception:
                pass

            await asyncio.sleep(attempt * 5)

    raise ConnectionError(
        "Could not restore the Telegram connection."
    ) from last_error


async def get_latest_saved_message():
    messages = await telegram_call(
        lambda: client.get_messages("me", limit=1)
    )

    if not messages:
        raise RuntimeError(
            "Saved Messages is empty. Send your promotional message "
            "to Saved Messages first."
        )

    return messages[0]


async def resolve_target_chat(chat):
    """Resolve a private invite only when this account already belongs to its group."""
    if not chat.startswith("https://t.me/+"):
        return chat

    invite_hash = chat.removeprefix("https://t.me/+")
    invite = await telegram_call(
        lambda: client(functions.messages.CheckChatInviteRequest(hash=invite_hash))
    )
    if not isinstance(invite, types.ChatInviteAlready):
        raise RuntimeError(
            "The TG_SESSION account must join the configured private group "
            "and have permission to send before announcements can be delivered."
        )
    return invite.chat


async def send_to_chat(chat, promo_message):
    chat = await resolve_target_chat(chat)
    text = promo_message.message or ""
    entities = promo_message.entities or None

    if promo_message.media and not isinstance(promo_message.media, types.MessageMediaWebPage):
        await telegram_call(
            lambda: client.send_file(
                chat,
                promo_message.media,
                caption=text,
                formatting_entities=entities,
            )
        )
        return

    if not text.strip():
        raise RuntimeError(
            "Latest Saved Messages item has no text or media to send."
        )

    await telegram_call(
        lambda: client.send_message(
            chat,
            text,
            formatting_entities=entities,
        )
    )


async def run_announcements():
    """Give each group its own timer while respecting account-wide waits."""
    loop = asyncio.get_running_loop()
    next_attempt = dict.fromkeys(TARGET_CHATS, loop.time())

    while True:
        delay = min(next_attempt.values()) - loop.time()
        if delay > 0:
            await asyncio.sleep(delay)

        due_chats = [
            chat for chat, due_at in next_attempt.items()
            if due_at <= loop.time()
        ]
        if not due_chats:
            continue

        try:
            message = await get_latest_saved_message()
        except (errors.SlowModeWaitError, errors.FloodWaitError) as error:
            delay = max(INTERVAL_SECONDS, error.seconds + 2)
            logging.warning("Reading Saved Messages delayed by %s seconds.", delay)
            await asyncio.sleep(delay)
            continue
        except Exception:
            logging.exception("Could not read the latest Saved Messages item.")
            await asyncio.sleep(INTERVAL_SECONDS)
            continue

        for chat in due_chats:
            label = chat_label(chat)
            delay = INTERVAL_SECONDS
            account_wait = 0
            try:
                await send_to_chat(chat, message)
                logging.info("Sent successfully to %s from Saved Messages.", label)
            except errors.SlowModeWaitError as error:
                delay = max(INTERVAL_SECONDS, error.seconds + 2)
                logging.warning("Slow mode in %s; retry in %s seconds.", label, delay)
            except errors.FloodWaitError as error:
                account_wait = error.seconds + 2
                delay = max(INTERVAL_SECONDS, account_wait)
                logging.warning("Telegram requires an account-wide wait of %s seconds.", account_wait)
            except Exception:
                logging.exception("Announcement failed for %s; continuing with other groups.", label)

            next_attempt[chat] = loop.time() + delay
            logging.info("Next attempt for %s in %s minutes.", label, delay / 60)
            if account_wait:
                await asyncio.sleep(account_wait)
                break


async def main():
    try:
        await reconnect()
        me = await telegram_call(client.get_me)
        logging.info(
            "Logged in as %s. Targets: %s. Interval: %s minutes per group.",
            me.first_name, ", ".join(chat_label(chat) for chat in TARGET_CHATS),
            INTERVAL_SECONDS / 60,
        )
        await run_announcements()
    finally:
        await client.disconnect()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
