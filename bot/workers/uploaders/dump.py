import asyncio
import shutil

from bot import Path, pyro, pyro_errors
from bot.config import DUMP_CHANNEL, LOG_CHANNEL
from bot.utils.log_utils import logger
from bot.utils.os_utils import parse_dl, s_remove
from bot.workers.uploaders.upload import Uploader as uploader

dump_ = int(DUMP_CHANNEL) if DUMP_CHANNEL else None
sticker = "CAACAgEAAxkBAAI0aWKx36P2GY9Fq6xvN0SBU1V2xZYIAAKXAgACJ_hhR9HcWzoditT7HgQ"


async def dumpdl(dl, name, thum, user, message):
    try:
        dmp = "dump/" + name
        shutil.copy2(dl, dmp)
        _dmp = Path(dmp)
        fname = f"`{name}`"
        if dump_:
            message = await pyro.send_message(
                dump_, "`🚨 Incoming! 🚨`\n\n" + await parse_dl(name)
            )
            await asyncio.sleep(5)
            reply = await message.reply(f"__Dumping:__\n {fname}__…__", quote=True)
        elif message:
            reply = await message.reply(f"`Dumping` {fname}`…`", quote=True)
        await asyncio.sleep(2)
        if int(_dmp.stat().st_size) > 2126000000:
            dp = await reply.reply("**File too large to dump, Aborting…**", quote=True)
            f_reply = reply
        else:
            upload = uploader()
            dp = await upload.start(user, dmp, reply, thum, fname, message)

            if not upload.is_cancelled:
                f_reply = await reply.edit(f"{fname} __dumped successfully.__")
            else:
                f_reply = await reply.edit(f"`Dumping of {fname} was cancelled.`")
        if LOG_CHANNEL:
            chat = int(LOG_CHANNEL)
            await f_reply.copy(chat_id=chat)
            if dp is not None:
                await dp.copy(chat_id=chat)
    except pyro_errors.FloodWait as e:
        await asyncio.sleep(e.value)
        await dumpdl(dl, name, thum, user, message)
    except pyro_errors.BadRequest:
        await asyncio.sleep(20)
        await dumpdl(dl, name, thum, user, message)
    except Exception:
        await logger(Exception)
    finally:
        s_remove(dmp)
        await asyncio.sleep(5)
        if dump_:
            await message.reply_sticker(sticker)
