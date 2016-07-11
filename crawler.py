#!/usr/bin/env python3
#
# Copyright (c) 2016 imlonghao <shield@fastmail.com>
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

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
        express = r.table('traces').get(subscribe).run(db)
        if express['state'] in ['3', '4']:
            continue
        data = requests.get('http://m.kuaidi100.com/query?type=%s&postid=%s&id=1&valicode=&temp=%s' % (
            express['com'], express['id'], str(random.random()))).json()
        if len(express['data']) == len(data['data']):
            continue
        data['id'] = data['nu']
        del data['nu']
        for each in data['data']:
            each['time'] = r.epoch_time(time.mktime(time.strptime(each['time'], '%Y-%m-%d %H:%M:%S')))
        r.table('traces').get(express['id']).update(data).run(db)
        text = '快递 {0} 有更新\n\n'.format(data['id'])
        for i in data['data'][:len(data['data']) - len(express['data'])]:
            text += '{0}\n{1}'.format(
                i['context'],
                i['ftime']
            )
        bot.sendMessage(user['id'], text)
