import asyncio
import logging
import os

from telethon import TelegramClient, errors, types
from telethon.sessions import StringSession


def required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing Railway variable: {name}")
    return value


API_ID = int(required_env("TG_API_ID"))
API_HASH = required_env("TG_API_HASH")
SESSION_STRING = required_env("TG_SESSION")

TARGET_CHAT = "elitemethodchat"
INTERVAL_SECONDS = 90 * 60

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
    flood_sleep_threshold=60,
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


async def send_to_chat(chat, promo_message):
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


async def main():
    await reconnect()
    me = await telegram_call(client.get_me)
    logging.info("Logged in as %s. Target: @%s. Interval: 90 minutes.", me.first_name, TARGET_CHAT)
    try:
        while True:
            delay = INTERVAL_SECONDS
            try:
                message = await get_latest_saved_message()
                await send_to_chat(TARGET_CHAT, message)
                logging.info("Sent successfully to @%s from Saved Messages.", TARGET_CHAT)
            except (errors.SlowModeWaitError, errors.FloodWaitError) as error:
                delay = max(INTERVAL_SECONDS, error.seconds + 2)
                logging.warning("Telegram requires a wait; next attempt in %s seconds.", delay)
            except Exception:
                logging.exception("Announcement failed.")
            logging.info("Next attempt in %s minutes.", delay / 60)
            await asyncio.sleep(delay)
    finally:
        await client.disconnect()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
