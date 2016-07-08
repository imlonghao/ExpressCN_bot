#!/usr/bin/env python3

import random
import logging
import time
import rethinkdb as r
import requests
from vars import STATES
from telegram import Emoji, ReplyKeyboardMarkup
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, RegexHandler
from config import TELEGRAM_BOT_TOKEN, DB_HOST, DB_PORT, DB_NAME
from utils import error, send_async

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.DEBUG)
logger = logging.getLogger(__name__)

# 1: query
user_action = dict()

KB = [
    [
        '%s 查询/订阅快件' % Emoji.EYES,
        '%s 管理订阅' % Emoji.CLIPBOARD,
    ]
]


def id2com(id):
    ret = requests.get('http://m.kuaidi100.com/autonumber/auto?num=%s' % id)
    ret = ret.json()
    if ret == []:
        return False
    return ret[0]['comCode']


def id2query(id, comCode):
    ret = requests.get(
        'http://m.kuaidi100.com/query?type=%s&postid=%s&id=1&valicode=&temp=%s' % (comCode, id, str(random.random())))
    return ret.json()


def insertDB(json_data):
    json_data['id'] = json_data['nu']
    del json_data['nu']
    for each in json_data['data']:
        each['time'] = r.epoch_time(time.mktime(time.strptime(each['time'], '%Y-%m-%d %H:%M:%S')))
    r.table('traces').insert(json_data).run(db)


def updateDB(json_data):
    json_data['id'] = json_data['nu']
    del json_data['nu']
    for each in json_data['data']:
        each['time'] = r.epoch_time(time.mktime(time.strptime(each['time'], '%Y-%m-%d %H:%M:%S')))
    r.table('traces').get(json_data['id']).update(json_data).run(db)


def result(json_data):
    t = '[单号]  <b>{0}</b>\n' \
        '[状态]  {1}\n' \
        '[快递跟踪]\n'.format(
        json_data['id'],
        STATES[json_data['state']],
    )
    for i in json_data['data']:
        t += i['context'] + '\n'
        t += i['ftime'] + '\n'
    return t


def getDetail(id):
    express_status = r.table('traces').get(id).run(db)
    if not express_status:
        com = id2com(id)
        if not com:
            r.table('traces').insert({
                'id': id,
                'state': '-1'
            })
            return '快递单号不正确'
        status = id2query(id, com)
        if status['status'] != '200':
            r.table('traces').insert({
                'id': id,
                'state': '-1'
            })
            return '快递单号不正确'
        insertDB(status)
        return result(status)
    elif express_status['state'] == '-1':
        return '快递单号不正确'
    elif express_status['state'] not in ['3', '4']:
        status = id2query(id, express_status['com'])
        updateDB(status)
        return result(status)
    else:
        return result(express_status)


def help(bot, update):
    chat_id = update.message.chat.id
    if user_action.get(chat_id) == 1:
        express_id = update.message.text
        user_action[chat_id] = express_id
        result = getDetail(express_id)
        if result == '快递单号不正确':
            send_async(bot, chat_id, result,
                       reply_markup=ReplyKeyboardMarkup(keyboard=KB, one_time_keyboard=True))
            return
        subscribes = r.table('users').get(chat_id).run(db)
        if subscribes is not None and express_id in subscribes['value']:
            kb = [
                ['%s 取消对该快件的订阅' % Emoji.BELL_WITH_CANCELLATION_STROKE],
                [
                    '%s 查询/订阅快件' % Emoji.EYES,
                    '%s 管理订阅' % Emoji.CLIPBOARD,
                ]
            ]
        else:
            kb = [
                ['%s 订阅该快件' % Emoji.BELL],
                [
                    '%s 查询/订阅快件' % Emoji.EYES,
                    '%s 管理订阅' % Emoji.CLIPBOARD,
                ]
            ]
        send_async(bot, chat_id, result, parse_mode='html',
                   reply_markup=ReplyKeyboardMarkup(
                       keyboard=kb,
                       one_time_keyboard=True))
        return
    send_async(bot, chat_id, '请按照下面的提示进行操作~',
               reply_markup=ReplyKeyboardMarkup(keyboard=KB, one_time_keyboard=True))


def fromManage(bot, update, groups):
    chat_id = update.message.chat.id
    express_id = groups[0]
    user_action[chat_id] = 1
    update.message.text = express_id
    help(bot, update)


def query(bot, update):
    chat_id = update.message.chat.id
    user_action[chat_id] = 1
    send_async(bot, chat_id, '请输入您的快件单号')


def subscribe(bot, update):
    chat_id = update.message.chat.id
    subscribes = r.table('users').get(chat_id).run(db)
    if subscribes is None:
        r.table('users').insert({
            'id': chat_id,
            'value': [user_action[chat_id]]
        }).run(db)
        send_async(bot, chat_id, '订阅成功，如果快件有更新您将会收到通知',
                   reply_markup=ReplyKeyboardMarkup(keyboard=KB, one_time_keyboard=True))
    elif user_action[chat_id] in subscribes['value']:
        send_async(bot, chat_id, '订阅失败，您已经订阅了该快件',
                   reply_markup=ReplyKeyboardMarkup(keyboard=KB, one_time_keyboard=True))
    else:
        subscribes['value'].append(user_action[chat_id])
        r.table('users').get(chat_id).update(subscribes).run(db)
        send_async(bot, chat_id, '订阅成功，如果快件有更新您将会收到通知',
                   reply_markup=ReplyKeyboardMarkup(keyboard=KB, one_time_keyboard=True))


def unsubscribe(bot, update):
    chat_id = update.message.chat.id
    subscribes = r.table('users').get(chat_id).run(db)
    if subscribes is None:
        send_async(bot, chat_id, '取消订阅失败，您什么也没有订阅',
                   reply_markup=ReplyKeyboardMarkup(keyboard=KB, one_time_keyboard=True))
    elif user_action[chat_id] not in subscribes['value']:
        send_async(bot, chat_id, '取消订阅失败，您并没有订阅这个快件',
                   reply_markup=ReplyKeyboardMarkup(keyboard=KB, one_time_keyboard=True))
    else:
        subscribes['value'].remove(user_action[chat_id])
        r.table('users').get(chat_id).update(subscribes).run(db)
        send_async(bot, chat_id, '取消订阅成功',
                   reply_markup=ReplyKeyboardMarkup(keyboard=KB, one_time_keyboard=True))


def manageSubscribe(bot, update):
    chat_id = update.message.chat.id
    subscribes = r.table('users').get(chat_id).run(db)
    if subscribes is None:
        send_async(bot, chat_id, '您什么也没有订阅',
                   reply_markup=ReplyKeyboardMarkup(keyboard=KB, one_time_keyboard=True))
        return
    kb = []
    for sub in subscribes['value']:
        q = r.table('traces').get(sub).run(db)
        kb.append(['[{0}] {1} ({2})'.format(
            q['com'],
            q['id'],
            STATES[q['state']]
        )])
    kb.append([
        '%s 查询/订阅快件' % Emoji.EYES,
        '%s 管理订阅' % Emoji.CLIPBOARD,
    ])
    send_async(bot, chat_id, '以下的是您的订阅',
               reply_markup=ReplyKeyboardMarkup(keyboard=kb, one_time_keyboard=True))


def main():
    global db
    db = r.connect(DB_HOST, DB_PORT, DB_NAME)
    updater = Updater(TELEGRAM_BOT_TOKEN, workers=5)
    dp = updater.dispatcher
    dp.add_handler(CommandHandler('help', help))
    dp.add_handler(CommandHandler('start', help))
    dp.add_handler(RegexHandler('^' + Emoji.EYES, query))
    dp.add_handler(RegexHandler('^' + Emoji.CLIPBOARD, manageSubscribe))
    dp.add_handler(RegexHandler('^' + Emoji.BELL, subscribe))
    dp.add_handler(RegexHandler('^' + Emoji.BELL_WITH_CANCELLATION_STROKE, unsubscribe))
    dp.add_handler(RegexHandler('^\[.*\] (.*) \(.*\)$', fromManage, pass_groups=True))
    dp.add_handler(MessageHandler([Filters.text], help))
    dp.add_error_handler(error)
    updater.start_polling()
    updater.idle()


if __name__ == '__main__':
    main()
