import os
import requests

from flask import Flask, request
from postmark import PMMail

app = Flask(__name__)

POSTMARK_API_KEY = os.environ.get(u'POSTMARK_API_KEY')
GROUPME_ACCESS_TOKEN = os.environ.get(u'GROUPME_ACCESS_TOKEN')

@app.route(u'/groupme/new_message', methods=[u'POST'])
def hello_word():
    j = request.get_json()
    g = requests.get(
        u'https://api.groupme.com/v3/groups/{group}'.format(**j),
        params={u'token': GROUPME_ACCESS_TOKEN}
    )
    group_name = g.json().get(u'response').get(u'name')
    m = PMMail(
        api_key=POSTMARK_API_KEY,
        subject=u'New message in {}'.format(group_name),
        sender=u'william@subtlecoolness.com',
        to=u'william@subtlecoolness.com',
        text_body=u'{name} said: {text}'.format(**j)
    )
    m.send(test=False)
    return u'Thank you.'

if __name__ == u'__main__':
    app.run(host=u'0.0.0.0')
