import datetime
import flask
import flask.ext.sqlalchemy
import json
import os
import postmark
import psycopg2
import requests
import stripe

stripe_keys = {
    u'publishable_key': os.environ.get(u'STRIPE_PUBLISHABLE_KEY'),
    u'secret_key': os.environ.get(u'STRIPE_SECRET_KEY')
}
stripe.api_key = stripe_keys.get(u'secret_key')

app = flask.Flask(__name__)
app.debug = True
app.config[u'SQLALCHEMY_DATABASE_URI'] = os.environ.get(u'DB_URI')
db = flask.ext.sqlalchemy.SQLAlchemy(app)

GM_CID = os.environ.get(u'GROUPME_CLIENT_ID')
POSTMARK_API_KEY = os.environ.get(u'POSTMARK_API_KEY')
EMAIL_SENDER = os.environ.get(u'EMAIL_SENDER')
SCHEME = os.environ.get(u'SCHEME')

class GroupMeClient(object):
    def __init__(self, token):
        self.params = {u'token': token}

    def me(self):
        url = u'https://api.groupme.com/v3/users/me'
        r = requests.get(url, params=self.params)
        return r.json()

    def group_info(self, group_id):
        url = u'https://api.groupme.com/v3/groups/{}'.format(group_id)
        r = requests.get(url, params=self.params)
        return r.json()

    def bots(self):
        url = u'https://api.groupme.com/v3/bots'
        r = requests.get(url, params=self.params)
        return r.json()

    def create_bot(self, name, group_id, callback_url):
        url = u'https://api.groupme.com/v3/bots'
        bot_def = {
            u'name': name,
            u'group_id': group_id,
            u'callback_url': callback_url
        }
        bot = {u'bot': bot_def}
        data = json.dumps(bot)
        r = requests.post(url, params=self.params, data=data)

    def destroy_bot(self, bot_id):
        url = u'https://api.groupme.com/v3/bots/destroy'
        data = {u'bot_id': bot_id}
        r = requests.post(url, params=self.params, data=json.dumps(data))
        return r.status_code

class User(db.Model):
    user_id = db.Column(db.Integer, primary_key=True)
    token = db.Column(db.String, nullable=False)
    expiration = db.Column(db.DateTime, nullable=False)
    _email = None

    def __init__(self, user_id, token, expiration=None):
        self.user_id = user_id
        self.token = token
        if expiration is None:
            expiration = datetime.datetime.utcnow() + datetime.timedelta(30)
        self.expiration = expiration

    def __repr__(self):
        return '<User {}>'.format(self.user_id)

    @property
    def email(self):
        if self._email is None:
            gm = GroupMeClient(self.token)
            gm_user = gm.me()
            self._email = gm_user.get(u'response').get(u'email')
        return self._email

    def to_dict(self):
        user = {
            u'id': self.user_id,
            u'token': self.token,
            u'expiration': self.expiration
        }

def external_url(endpoint, **values):
    return flask.url_for(endpoint, _external=True, _scheme=SCHEME, **values)

@app.route(u'/')
def index():
    if u'groupme_token' in flask.request.cookies:
        token = flask.request.cookies.get(u'groupme_token')
    else:
        return flask.render_template(u'landing.html', cid=GM_CID)

    gm = GroupMeClient(token)
    gm_user = gm.me()
    user = gm_user.get(u'response')
    db_user = User.query.get(user.get(u'user_id'))
    if db_user is None:
        msg = u'Subscribe to a group to get free service for 30 days.'
    else:
        if db_user.expiration < datetime.datetime.utcnow():
            msg = u'Your GroupMemail service expired on {}.'
        else:
            msg = u'Your GroupMemail service will expire on {}.'
        msg = msg.format(db_user.expiration.strftime(u'%d %B %Y'))
    user[u'expiration_msg'] = msg
    return flask.render_template(u'list.html', user=user)

@app.route(u'/login')
def login():
    resp = flask.make_response(flask.redirect(flask.url_for(u'index')))

    if u'groupme_token' in flask.request.cookies:
        token = flask.request.cookies.get(u'groupme_token')
        resp.set_cookie(u'groupme_token', token)

    if u'access_token' in flask.request.args:
        token = flask.request.args.get(u'access_token')
        resp.set_cookie(u'groupme_token', token)

    return resp

@app.route(u'/logout')
def logout():
    resp = flask.make_response(flask.redirect(external_url(u'index')))
    resp.delete_cookie(u'groupme_token')
    return resp

@app.route(u'/groupme/auth')
def groupme_auth():
    if u'access_token' in flask.request.args:
        token = flask.request.args.get(u'access_token')
        url = flask.url_for(u'login', access_token=token)
        url = u'{}{}'.format(os.environ.get(u'BASE_URL'), url)
        return flask.redirect(url)

    return flask.redirect(flask.url_for(u'index'))

@app.route(u'/subscribe/<int:group_id>')
def subscribe(group_id):
    if u'groupme_token' in flask.request.cookies:
        token = flask.request.cookies.get(u'groupme_token')
    else:
        return flask.redirect(flask.url_for(u'index'))

    gm = GroupMeClient(token)
    gm_user = gm.me()
    user_id = gm_user.get(u'response').get(u'id')

    db_user = User.query.get(user_id)
    if db_user is None:
        db_user = User(user_id, token)
        db.session.add(db_user)
        db.session.commit()

    url = external_url(u'groupme_incoming', user_id=user_id)
    gm.create_bot(u'Subtle Coolness Services', group_id, url)

    return flask.redirect(external_url(u'index'))

@app.route(u'/unsubscribe/<int:group_id>')
def unsubscribe(group_id):
    if u'groupme_token' in flask.request.cookies:
        token = flask.request.cookies.get(u'groupme_token')
    else:
        return flask.redirect(flask.url_for(u'index'))

    gm = GroupMeClient(token)
    gm_user = gm.me()
    user_id = gm_user.get(u'response').get(u'id')

    url = flask.url_for(u'groupme_incoming', user_id=user_id)

    bots = gm.bots()
    for bot in bots.get(u'response'):
        if int(bot.get(u'group_id')) == group_id:
            if url in bot.get(u'callback_url'):
                d = gm.destroy_bot(bot.get(u'bot_id'))

    return flask.redirect(external_url(u'index'))

@app.route(u'/payment')
def payment():
    if u'groupme_token' in flask.request.cookies:
        token = flask.request.cookies.get(u'groupme_token')
    else:
        return flask.redirect(flask.url_for(u'index'))

    gm = GroupMeClient(token)
    gm_user = gm.me()
    user = gm_user.get(u'response')
    db_user = User.query.get(user.get(u'user_id'))
    if db_user is None:
        msg = u'Subscribe to a group to get free service for 30 days.'
    else:
        if db_user.expiration < datetime.datetime.utcnow():
            msg = u'Your GroupMemail service expired on {}.'
        else:
            msg = u'Your GroupMemail service will expire on {}.'
        msg = msg.format(db_user.expiration.strftime(u'%d %B %Y'))
    user[u'expiration_msg'] = msg

    key = stripe_keys.get(u'publishable_key')
    return flask.render_template(u'payment.html', key=key, user=user)

@app.route(u'/charge', methods=[u'POST'])
def charge():
    if u'groupme_token' in flask.request.cookies:
        token = flask.request.cookies.get(u'groupme_token')
    else:
        return flask.redirect(flask.url_for(u'index'))

    amount = 600

    gm = GroupMeClient(token)
    gm_user = gm.me()
    user = gm_user.get(u'response')

    card = flask.request.form.get(u'stripeToken')
    customer = stripe.Customer.create(email=user.get(u'email'), card=card)

    try:
        charge = stripe.Charge.create(
            customer=customer.id,
            amount=amount,
            currency=u'usd',
            description=u'GroupMemail Service: 6 months'
        )
    except stripe.CardError as e:
        return flask.redirect(flask.url_for(u'index'))

    db_user = User.query.get(user.get(u'user_id'))
    db_user.expiration = db_user.expiration + datetime.timedelta(180)
    db.session.add(db_user)
    db.session.commit()

    return flask.redirect(flask.url_for(u'index'))

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

    gm = GroupMeClient(user.token)

    gm_group = gm.group_info(j.get(u'group_id'))
    group_name = gm_group.get(u'response').get(u'name')
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
