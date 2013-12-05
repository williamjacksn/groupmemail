import os
import requests

from flask import abort, Flask, render_template, request
from postmark import PMMail

app = Flask(__name__)
app.debug = True

GROUPME_ACCESS_TOKEN = os.environ.get(u'GROUPME_ACCESS_TOKEN')
GROUPME_CLIENT_ID = os.environ.get(u'GROUPME_CLIENT_ID')
POSTMARK_API_KEY = os.environ.get(u'POSTMARK_API_KEY')
EMAIL_SENDER = os.environ.get(u'EMAIL_SENDER')
EMAIL_TARGET = os.environ.get(u'EMAIL_TARGET')

@app.route(u'/groupme')
def groupme_index():
    if u'access_token' not in request.args:
        return render_template(u'groupme_index.html', cid=GROUPME_CLIENT_ID)

    template_vars = dict()
    token = request.args.get(u'access_token')
    url = u'https://api.groupme.com/v3/users/me'
    params = {u'token': token}
    u = requests.get(url, params=params)
    user = u.json().get(u'response')
    template_vars[u'username'] = user.get(u'name')
    template_vars[u'user_img'] = user.get(u'image_url')

    url = u'https://api.groupme.com/v3/groups'
    g = requests.get(url, params=params)
    template_vars[u'groups'] = g.json().get(u'response')

    return render_template(u'groupme_list.html', **template_vars)

@app.route(u'/groupme/new_message', methods=[u'POST'])
def groupme_new_message():
    j = request.get_json()
    app.logger.debug(j)
    for field in [u'name', u'text', u'group_id', u'attachments']:
        if field not in j:
            e_msg = u'Posted parameters did not include a required field: {}'
            app.logger.error(e_msg.format(field))
            abort(500)
    g = requests.get(
        u'https://api.groupme.com/v3/groups/{group_id}'.format(**j),
        params={u'token': GROUPME_ACCESS_TOKEN}
    )
    group_name = g.json().get(u'response').get(u'name')
    if j.get(u'text') is None:
        email_body = u'<p>{name} posted a picture:</p>'.format(**j)
    else:
        email_body = u'<p>{name} said: {text}</p>'.format(**j)

    for attachment in j.get(u'attachments'):
        if attachment.get(u'type') == u'image':
            img_tag = u'<img src="{url}" />'.format(**attachment)
            email_body = u'{}\n\n<p>{}</p>'.format(email_body, img_tag)

    a_tag = u'<a href="https://app.groupme.com/chats">Go to GroupMe</a>'
    email_body = u'{}\n\n<p>{}</p>'.format(email_body, a_tag)
    m = PMMail(
        api_key=POSTMARK_API_KEY,
        subject=u'New message in {}'.format(group_name),
        sender=EMAIL_SENDER,
        to=EMAIL_TARGET,
        html_body=email_body
    )
    m.send(test=False)
    return u'Thank you.'

if __name__ == u'__main__':
    app.run(debug=True, host=u'0.0.0.0')
