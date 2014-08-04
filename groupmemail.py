import datetime
import flask
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

db_conn = psycopg2.connect(os.environ.get(u'DB_URI'))
db_conn.autocommit = True

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

    def create_message(self, group_id, text):
        url = u'https://api.groupme.com/v3/groups/{}/messages'.format(group_id)
        message = {u'message': {u'text': text}}
        data = json.dumps(message)
        headers = {u'content-type': u'application/json'}
        r = requests.post(url, params=self.params, data=data, headers=headers)
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
        return r.json()

    def update_bot(self, bot_id, name, group_id, callback_url):
        url = u'https://api.groupme.com/v3/bots/{}'.format(bot_id)
        bot_def = {
            u'bot_id': bot_id,
            u'name': name,
            u'group_id': group_id,
            u'callback_url': callback_url
        }
        bot = {u'bot': bot_def}
        data = json.dumps(bot)
        r = requests.post(url, params=self.params, data=data)
        return r

    def destroy_bot(self, bot_id):
        url = u'https://api.groupme.com/v3/bots/destroy'
        data = {u'bot_id': bot_id}
        r = requests.post(url, params=self.params, data=json.dumps(data))
        return r.status_code

class User(object):

    @classmethod
    def create(cls, user_id, token, email):
        u = cls()
        u.user_id = user_id
        u.token = token
        u.expiration = datetime.datetime.utcnow() + datetime.timedelta(30)
        u.email = email
        sql = (u'insert into users (user_id, token, expiration, email) '
            u'values (%s, %s, %s, %s)')
        with db_conn.cursor() as cur:
            db_conn.execute(sql, [user_id, token, u.expiration, email])
        u.expiration_notified = False
        u.bad_token_notified = False
        return u

    @classmethod
    def get_by_id(cls, user_id):
        u = cls()
        sql = (u'select user_id, token, expiration, email, '
            u'expiration_notified, bad_token_notified from users where '
            u'user_id = %s')
        with db_conn.cursor() as cur:
            cur.execute(sql, [user_id])
            r = cur.fetchone()
        if r is None:
            return None
        u.user_id = int(r[0])
        u.token = r[1].decode(u'utf-8')
        u.expiration = r[2]
        u.email = r[3].decode(u'utf-8')
        u.expiration_notified = bool(r[4])
        u.bad_token_notified = bool(r[5])
        return u

    @classmethod
    def get_by_email(cls, email):
        u = cls()
        sql = (u'select user_id, token, expiration, email, '
            u'expiration_notified, bad_token_notified from users where '
            u'email = %s')
        with db_conn.cursor() as cur:
            cur.execute(sql, [email])
            r = cur.fetchone()
        if r is None:
            return None
        u.user_id = int(r[0])
        u.token = r[1].decode(u'utf-8')
        u.expiration = r[2]
        u.email = r[3].decode(u'utf-8')
        u.expiration_notified = bool(r[4])
        u.bad_token_notified = bool(r[5])
        return u

    def __repr__(self):
        return '<User {}>'.format(self.email)

    @property
    def expired(self):
        return self.expiration < datetime.datetime.utcnow()

    def extend(self, days):
        base = self.expiration
        if self.expired:
            base = datetime.datetime.utcnow()

        self.expiration = base + datetime.timedelta(days)
        self.expiration_notified = False
        sql = (u'update users set expiration = %s, expiration_notified = '
            u'False where user_id = %s')
        with db_conn.cursor() as cur:
            cur.execute(sql, [self.expiration, self.user_id])

    def notify_bad_token(self):
        html_body = flask.render_template(u'email_problem.html')
        m = postmark.PMMail(
            api_key=POSTMARK_API_KEY,
            subject=u'GroupMemail delivery problem',
            sender=EMAIL_SENDER,
            to=self.email,
            html_body=html_body
        )
        m.send(test=False)

        self.bad_token_notified = True
        sql = u'update users set bad_token_notified = True where user_id = %s'
        with db_conn.cursor() as cur:
            cur.execute(sql, [self.user_id])

    def notify_expiration(self):
        html_body = flask.render_template(u'email_expired.html', user=self)
        m = postmark.PMMail(
            api_key=POSTMARK_API_KEY,
            subject=u'GroupMemail service expiration',
            sender=EMAIL_SENDER,
            to=self.email,
            html_body=html_body
        )
        m.send(test=False)

        self.expiration_notified = True
        sql = u'update users set expiration_notified = true where user_id = %s'
        with db_conn.cursor() as cur:
            cur.execute(sql, [self.user_id])

    def set_token(self, token):
        self.token = token
        self.bad_token_notified = False
        sql = (u'update users set token = %s, bad_token_notified = False '
            u'where user_id = %s')
        with db_conn.cursor() as cur:
            cur.execute(sql, [token, self.user_id])


def external_url(endpoint, **values):
    return flask.url_for(endpoint, _external=True, _scheme=SCHEME, **values)

@app.route(u'/ping')
def ping():
    return u'pong'

@app.route(u'/')
def index():
    if u'groupme_token' in flask.request.cookies:
        token = flask.request.cookies.get(u'groupme_token')
    else:
        return flask.render_template(u'landing.html', cid=GM_CID)

    gm = GroupMeClient(token)
    gm_user = gm.me()
    user = gm_user.get(u'response')
    db_user = User.get_by_id(user.get(u'user_id'))
    if db_user is None:
        msg = u'Subscribe to a group to get free service for 30 days.'
    else:
        if db_user.token != token:
            db_user.set_token(token)
        if db_user.expired:
            msg = u'Your GroupMemail service expired on {}.'
        else:
            msg = u'Your GroupMemail service will expire on {}.'
        msg = msg.format(db_user.expiration.strftime(u'%d %B %Y'))
    user[u'expiration_msg'] = msg
    return flask.render_template(u'list.html', user=user)

@app.route(u'/login')
def login():
    index_url = external_url(u'index')
    resp = flask.make_response(flask.redirect(index_url, code=303))

    if u'groupme_token' in flask.request.cookies:
        token = flask.request.cookies.get(u'groupme_token')
        resp.set_cookie(u'groupme_token', token)

    if u'access_token' in flask.request.args:
        token = flask.request.args.get(u'access_token')
        resp.set_cookie(u'groupme_token', token)

    return resp

@app.route(u'/logout')
def logout():
    index_url = external_url(u'index')
    resp = flask.make_response(flask.redirect(index_url, code=303))
    resp.delete_cookie(u'groupme_token')
    return resp

@app.route(u'/subscribe/<int:group_id>')
def subscribe(group_id):
    if u'groupme_token' in flask.request.cookies:
        token = flask.request.cookies.get(u'groupme_token')
    else:
        return flask.redirect(flask.external_url(u'index'), code=303)

    gm = GroupMeClient(token)
    gm_user = gm.me()
    user_id = gm_user.get(u'response').get(u'id')
    email = gm_user.get(u'response').get(u'email')

    db_user = User.get_by_id(user_id)
    if db_user is None:
        db_user = User.create(user_id, token, email)

    if db_user.token != token:
        db_user.set_token(token)

    if not db_user.expired:
        url = external_url(u'incoming', user_id=user_id)
        gm.create_bot(u'GroupMemail', group_id, url)

    return flask.redirect(external_url(u'index'), code=303)

@app.route(u'/unsubscribe/<int:group_id>')
def unsubscribe(group_id):
    if u'groupme_token' in flask.request.cookies:
        token = flask.request.cookies.get(u'groupme_token')
    else:
        return flask.redirect(flask.external_url(u'index'), code=303)

    gm = GroupMeClient(token)
    gm_user = gm.me()
    user_id = gm_user.get(u'response').get(u'id')

    url = flask.url_for(u'incoming', user_id=user_id)

    bots = gm.bots()
    for bot in bots.get(u'response'):
        if int(bot.get(u'group_id')) == group_id:
            if url in bot.get(u'callback_url'):
                d = gm.destroy_bot(bot.get(u'bot_id'))

    return flask.redirect(external_url(u'index'), code=303)

@app.route(u'/payment')
def payment():
    if u'groupme_token' in flask.request.cookies:
        token = flask.request.cookies.get(u'groupme_token')
    else:
        return flask.redirect(flask.external_url(u'index'), code=303)

    gm = GroupMeClient(token)
    gm_user = gm.me()
    user = gm_user.get(u'response')
    db_user = User.get_by_id(user.get(u'user_id'))
    if db_user is None:
        msg = u'Subscribe to a group to get free service for 30 days.'
    else:
        if db_user.expired:
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
        return flask.redirect(flask.external_url(u'index'), code=303)

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
        return flask.redirect(flask.external_url(u'index'), code=303)

    db_user = User.get_by_id(user.get(u'user_id'))
    db_user.extend(180)

    return flask.redirect(flask.external_url(u'index'), code=303)

@app.route(u'/incoming/<int:user_id>', methods=[u'POST'])
def incoming(user_id):
    user = User.get_by_id(user_id)
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

    if user.expired:
        err = u'user_id {} expired on {}'.format(user_id, user.expiration)
        app.logger.error(err)
        url = flask.url_for(u'incoming', user_id=user_id)
        for bot in gm.bots().get(u'response'):
            if int(bot.get(u'group_id')) == int(j.get(u'group_id')):
                if url in bot.get(u'callback_url'):
                    d = gm.destroy_bot(bot.get(u'bot_id'))
        if not user.expiration_notified:
            user.notify_expiration()
        return u'', 204

    gm_group = gm.group_info(j.get(u'group_id'))
    if gm_group is None:
        if user.bad_token_notified:
            err = u'{} was already notified of bad token.'.format(user.email)
            app.logger.error(err)
        else:
            err = u'Sending bad token notification to {}.'.format(user.email)
            app.logger.error(err)
            user.notify_bad_token()
        return u'Thank you.'

    try:
        group_name = gm_group.get(u'response').get(u'name')
    except:
        if user.bad_token_notified:
            err = u'{} was already notified of bad token.'.format(user.email)
            app.logger.error(err)
        else:
            err = u'Sending bad token notification to {}.'.format(user.email)
            app.logger.error(err)
            user.notify_bad_token()
        return u'Thank you'

    html_body = flask.render_template(u'email_message.html', j=j)
    reply_to_tokens = list(EMAIL_SENDER.partition(u'@'))
    reply_to_tokens.insert(1, u'+{}'.format(j.get(u'group_id')))
    reply_to = u''.join(reply_to_tokens)
    m = postmark.PMMail(
        api_key=POSTMARK_API_KEY,
        subject=u'New message in {}'.format(group_name),
        sender=EMAIL_SENDER,
        reply_to=reply_to,
        to=user.email,
        html_body=html_body
    )
    m.send(test=False)
    return u'Thank you.'

@app.route(u'/email', methods=[u'POST'])
def handle_email():
    j = flask.request.get_json()

    source = j.get(u'FromFull').get(u'Email')
    dest = j.get(u'MailboxHash')
    text = j.get(u'TextBody')

    user = User.get_by_email(source)
    if user is None:
        err = u'Received mail from unknown address: {}'.format(source)
        app.logger.error(err)
        flask.abort(404)

    tokens = text.splitlines()
    if u'' in tokens:
        empty_line_index = tokens.index(u'')
        tokens = tokens[:empty_line_index]
    message = u' '.join(tokens)
    gm = GroupMeClient(user.token)
    r = gm.create_message(dest, message)

    return u'Thank you.'

if __name__ == u'__main__':
    app.run(debug=True, host=u'0.0.0.0')
