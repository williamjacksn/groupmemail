import os
import requests

from flask import abort, Flask, request
from postmark import PMMail

app = Flask(__name__)
app.debug = True

GROUPME_ACCESS_TOKEN = os.environ.get(u'GROUPME_ACCESS_TOKEN')
POSTMARK_API_KEY = os.environ.get(u'POSTMARK_API_KEY')
EMAIL_SENDER = os.environ.get(u'EMAIL_SENDER')
EMAIL_TARGET = os.environ.get(u'EMAIL_TARGET')

@app.route(u'/groupme/new_message', methods=[u'POST'])
def groupme_new_message():
    j = request.get_json()
    app.logger.debug(j)
    for field in [u'name', u'text', u'group']:
        if field not in j:
            e_msg = u'Posted parameters did not include a required field: {}'
            app.logger.error(e_msg.format(field))
            abort(500)
    g = requests.get(
        u'https://api.groupme.com/v3/groups/{group}'.format(**j),
        params={u'token': GROUPME_ACCESS_TOKEN}
    )
    group_name = g.json().get(u'response').get(u'name')
    m = PMMail(
        api_key=POSTMARK_API_KEY,
        subject=u'New message in {}'.format(group_name),
        sender=EMAIL_SENDER,
        to=EMAIL_TARGET,
        text_body=u'{name} said: {text}'.format(**j)
    )
    m.send(test=False)
    return u'Thank you.'

if __name__ == u'__main__':
    app.run(debug=True, host=u'0.0.0.0')
