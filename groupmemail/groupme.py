import json
import requests


class GroupMeClient:
    def __init__(self, token):
        self.params = {'token': token}

    def me(self):
        url = 'https://api.groupme.com/v3/users/me'
        r = requests.get(url, params=self.params)
        return r.json()

    def group_info(self, group_id):
        url = f'https://api.groupme.com/v3/groups/{group_id}'
        r = requests.get(url, params=self.params)
        return r.json()

    def create_message(self, group_id, text):
        url = f'https://api.groupme.com/v3/groups/{group_id}/messages'
        message = {'message': {'text': text}}
        data = json.dumps(message)
        headers = {'content-type': 'application/json'}
        r = requests.post(url, params=self.params, data=data, headers=headers)
        return r.json()

    def bots(self):
        url = 'https://api.groupme.com/v3/bots'
        r = requests.get(url, params=self.params)
        return r.json()

    def create_bot(self, name, group_id, callback_url):
        url = 'https://api.groupme.com/v3/bots'
        bot_def = {
            'name': name,
            'group_id': group_id,
            'callback_url': callback_url
        }
        bot = {'bot': bot_def}
        data = json.dumps(bot)
        r = requests.post(url, params=self.params, data=data)
        return r.json()

    def update_bot(self, bot_id, name, group_id, callback_url):
        url = f'https://api.groupme.com/v3/bots/{bot_id}'
        bot_def = {
            'bot_id': bot_id,
            'name': name,
            'group_id': group_id,
            'callback_url': callback_url
        }
        bot = {'bot': bot_def}
        data = json.dumps(bot)
        r = requests.post(url, params=self.params, data=data)
        return r

    def destroy_bot(self, bot_id):
        url = 'https://api.groupme.com/v3/bots/destroy'
        data = json.dumps({'bot_id': bot_id})
        r = requests.post(url, params=self.params, data=data)
        return r.status_code
