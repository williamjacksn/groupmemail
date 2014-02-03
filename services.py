import datetime
import flask
import flask.ext.sqlalchemy
import os
import postmark
import psycopg2
import requests

app = flask.Flask(__name__)
app.debug = True
app.config[u'SQLALCHEMY_DATABASE_URI'] = os.environ.get(u'DB_URI')
db = flask.ext.sqlalchemy.SQLAlchemy(app)

GROUPME_ACCESS_TOKEN = os.environ.get(u'GROUPME_ACCESS_TOKEN')
GROUPME_CLIENT_ID = os.environ.get(u'GROUPME_CLIENT_ID')
POSTMARK_API_KEY = os.environ.get(u'POSTMARK_API_KEY')
EMAIL_SENDER = os.environ.get(u'EMAIL_SENDER')
EMAIL_TARGET = os.environ.get(u'EMAIL_TARGET')

class User(db.Model):
    user_id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String, unique=True, nullable=False)
    token = db.Column(db.String, nullable=False)
    expiration = db.Column(db.DateTime, nullable=False)
    subscriptions = db.relationship(u'Subscription')

    def __init__(self, user_id, email, expiration=None):
        self.user_id = user_id
        self.email = email
        if expiration is None:
            expiration = datetime.datetime.utcnow() + datetime.timedelta(7)
        self.expiration = expiration

    def __repr__(self):
        return '<User {} ({})>'.format(self.user_id, self.email)

    def to_dict(self):
        user = {
            u'id': self.user_id,
            u'email': self.email,
            u'expiration': self.expiration,
            u'subscriptions': []
        }
        for sub in self.subscriptions:
            user[u'subscriptions'].append(sub.group_id)
        return user

class Subscription(db.Model):
    _user_fk = db.ForeignKey(u'user.user_id')
    user_id = db.Column(db.Integer, _user_fk, primary_key=True)

    group_id = db.Column(db.Integer, primary_key=True, nullable=False)

    def __init__(self, user, group_id):
        self.user = user
        self.group_id = group_id

@app.route(u'/groupme')
def groupme_index():
    if u'groupme_token' in flask.request.cookies:
        template_vars = dict()
        template_vars[u'token'] = flask.request.cookies.get(u'groupme_token')
        return flask.render_template(u'groupme_list.html', **template_vars)

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

@app.route(u'/groupme/users/<int:user_id>', methods=[u'GET'])
def groupme_get_user(user_id):
    user = User.query.get_or_404(user_id)
    resp = {
        u'users': [ user.to_dict() ]
    }
    return flask.jsonify(resp)

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

    j = flask.request.get_json()
    app.logger.debug(j)
    for field in [u'name', u'text', u'group_id', u'attachments']:
        if field not in j:
            e_msg = u'Posted parameters did not include a required field: {}'
            app.logger.error(e_msg.format(field))
            flask.abort(500)

    group_id = j.get(u'group_id')

    url = u'https://api.groupme.com/v3/groups/{group_id}'.format(**j)
    g = requests.get(url, params={u'token': GROUPME_ACCESS_TOKEN})

    group_name = g.json().get(u'response').get(u'name')
    email_body = build_email_body(j)
    m = postmark.PMMail(
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
