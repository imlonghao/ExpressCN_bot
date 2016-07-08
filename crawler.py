#!/usr/bin/env python3

import time
import random
import requests
import rethinkdb as r
from telegram import Bot
from config import TELEGRAM_BOT_TOKEN, DB_HOST, DB_PORT, DB_NAME

db = r.connect(DB_HOST, DB_PORT, DB_NAME)
bot = Bot(TELEGRAM_BOT_TOKEN)

for user in r.table('users').run(db):
    for subscribe in user['value']:
        for express in r.table('traces').get(subscribe).filter(r.row['state'] not in ['3', '4']).run(db):
            data = requests.get('http://m.kuaidi100.com/query?type=%s&postid=%s&id=1&valicode=&temp=%s' % (
                express['com'], express['id'], str(random.random()))).json()
            if express['data'] == data['data']:
                continue
            data['id'] = data['nu']
            del data['nu']
            for each in data['data']:
                each['time'] = r.epoch_time(time.mktime(time.strptime(each['time'], '%Y-%m-%d %H:%M:%S')))
            r.table('traces').get(express['id']).update(data).run(db)
            text = '快递 {0} 有更新\n\n'
            for i in data['data'][:len(data['data']) - len(express['data'])]:
                text += '{0}\n{1}'.format(
                    i['context'],
                    i['ftime']
                )
            bot.sendMessage(user['id'], text)
