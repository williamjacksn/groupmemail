import datetime
import flask
import flask.ext.sqlalchemy
import json
import os
import postmark
import psycopg2
import requests

app = flask.Flask(__name__)
app.debug = True
app.config[u'SQLALCHEMY_DATABASE_URI'] = os.environ.get(u'DB_URI')
db = flask.ext.sqlalchemy.SQLAlchemy(app)

GROUPME_CLIENT_ID = os.environ.get(u'GROUPME_CLIENT_ID')
POSTMARK_API_KEY = os.environ.get(u'POSTMARK_API_KEY')
EMAIL_SENDER = os.environ.get(u'EMAIL_SENDER')

class User(db.Model):
    user_id = db.Column(db.Integer, primary_key=True)
    token = db.Column(db.String, nullable=False)
    expiration = db.Column(db.DateTime, nullable=False)
    _email = None

    def __init__(self, user_id, token, expiration=None):
        self.user_id = user_id
        self.token = token
        if expiration is None:
            expiration = datetime.datetime.utcnow() + datetime.timedelta(7)
        self.expiration = expiration

    def __repr__(self):
        return '<User {}>'.format(self.user_id)

    @property
    def email(self):
        if self._email is None:
            url = u'https://api.groupme.com/v3/users/me'
            u = requests.get(url, params={u'token': self.token})
            self._email = u.json().get(u'response').get(u'email')
        return self._email

    def to_dict(self):
        user = {
            u'id': self.user_id,
            u'token': self.token,
            u'expiration': self.expiration
        }

@app.route(u'/groupme')
def groupme_index():
    if u'groupme_token' in flask.request.cookies:
        return flask.render_template(u'groupme_list.html')

    return flask.render_template(u'groupme_index.html', cid=GROUPME_CLIENT_ID)

@app.route(u'/groupme/login')
def groupme_login():
    index_url = flask.url_for(u'groupme_index')
    resp = flask.make_response(flask.redirect(index_url))

    if u'groupme_token' in flask.request.cookies:
        token = flask.request.cookies.get(u'groupme_token')
        resp.set_cookie(u'groupme_token', token)

    if u'access_token' in flask.request.args:
        token = flask.request.args.get(u'access_token')
        resp.set_cookie(u'groupme_token', token)

    return resp

@app.route(u'/groupme/logout')
def groupme_logout():
    index_url = flask.url_for(u'groupme_index')
    resp = flask.make_response(flask.redirect(index_url))
    resp.delete_cookie(u'groupme_token')
    return resp

@app.route(u'/groupme/subscribe/<int:user_id>/<int:group_id>')
def groupme_subscribe(user_id, group_id):
    token = flask.request.cookies.get(u'groupme_token')
    user = User.query.get(user_id)
    if user is None:
        user = User(user_id, token)
        db.session.add(user)
        db.session.commit()

    url = u'https://api.groupme.com/v3/bots'
    params = {u'token': token}
    cburl = flask.url_for(u'groupme_incoming', user_id=user_id, _external=True)
    bot_def = {
        u'name': u'Subtle Coolness Services',
        u'group_id': group_id,
        u'callback_url': cburl
    }
    data = {u'bot': bot_def}
    r = requests.post(url, params=params, data=json.dumps(data))
    return r.text

def get_group_name(group_id, token):
    url = u'https://api.groupme.com/v3/groups/{}'.format(group_id)
    g = requests.get(url, params={u'token': token})
    return g.json().get(u'response').get(u'name')

def build_email_body(j):
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
    return email_body

@app.route(u'/groupme/incoming/<int:user_id>', methods=[u'POST'])
def groupme_incoming(user_id):
    user = User.query.get(user_id)
    if user is None:
        app.logger.error(u'{} is not a known user_id'.format(user_id))
        flask.abort(404)

    params = {u'token': user.token}

    j = flask.request.get_json()
    app.logger.debug(j)
    for field in [u'name', u'text', u'group_id', u'attachments']:
        if field not in j:
            e_msg = u'Posted parameters did not include a required field: {}'
            app.logger.error(e_msg.format(field))
            flask.abort(500)

    group_name = get_group_name(j.get(u'group_id'), user.token)
    html_body = build_email_body(j)
    m = postmark.PMMail(
        api_key=POSTMARK_API_KEY,
        subject=u'New message in {}'.format(group_name),
        sender=EMAIL_SENDER,
        to=user.email,
        html_body=html_body
    )
    m.send(test=False)
    return u'Thank you.'

if __name__ == u'__main__':
    app.run(debug=True, host=u'0.0.0.0')
