#!/usr/bin/env python3

import logging
from telegram.ext.dispatcher import run_async

logger = logging.getLevelName(__name__)


def error(bot, update, error):
    logger.exception(error)


@run_async
def send_async(bot, *args, **kwargs):
    try:
        bot.sendMessage(*args, **kwargs)
    except Exception as e:
        error(None, None, e)
