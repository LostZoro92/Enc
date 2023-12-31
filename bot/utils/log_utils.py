import traceback

from bot import LOG_CHANNEL, LOGS, LOGS_IN_CHANNEL, tele
from bot.fun.emojis import enmoji


def log(Exception, critical=False):
    trace = traceback.format_exc()
    LOGS.info(trace) if not critical else LOGS.critical(trace)


async def channel_log(Exception):
    if LOG_CHANNEL and LOGS_IN_CHANNEL:
        try:
            error = traceback.format_exc()
            msg = await tele.send_message(
                LOG_CHANNEL,
                f"**#ERROR\n\n⛱️ Summary of what happened:**\n`{error}`\n\nTo restict error messages to logs set the LOGS_IN_CHANNEL vars to False. {enmoji()}",
            )
            return msg
        except Exception:
            LOGS.info(error)
            LOGS.info(traceback.format_exc())


async def logger(Exception, critical=False):
    log(Exception, critical=critical)
    await channel_log(Exception)


async def getlogs(event, args, client):
    if str(event.sender_id) not in OWNER and event.sender_id != DEV:
        return await event.delete()
    await event.client.send_file(event.chat_id, file=LOG_FILE_NAME, force_document=True)
