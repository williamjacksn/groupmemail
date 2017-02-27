import datetime
import flask
import json
import os
import postmark
import psycopg2
import requests
import stripe

stripe_keys = {
    'publishable_key': os.environ.get('STRIPE_PUBLISHABLE_KEY'),
    'secret_key': os.environ.get('STRIPE_SECRET_KEY')
}
stripe.api_key = stripe_keys.get('secret_key')

app = flask.Flask(__name__)

db_conn = psycopg2.connect(os.environ.get('DB_URI'))
db_conn.autocommit = True

GM_CID = os.environ.get('GROUPME_CLIENT_ID')
POSTMARK_API_KEY = os.environ.get('POSTMARK_API_KEY')
EMAIL_SENDER = os.environ.get('EMAIL_SENDER')
SCHEME = os.environ.get('SCHEME')


class GroupMeClient(object):
    def __init__(self, token):
        self.params = {'token': token}

    def me(self):
        url = 'https://api.groupme.com/v3/users/me'
        r = requests.get(url, params=self.params)
        return r.json()

    def group_info(self, group_id):
        url = 'https://api.groupme.com/v3/groups/{}'.format(group_id)
        r = requests.get(url, params=self.params)
        return r.json()

    def create_message(self, group_id, text):
        url = 'https://api.groupme.com/v3/groups/{}/messages'.format(group_id)
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
        url = 'https://api.groupme.com/v3/bots/{}'.format(bot_id)
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
        data = {'bot_id': bot_id}
        r = requests.post(url, params=self.params, data=json.dumps(data))
        return r.status_code


class User(object):

    def __init__(self):
        self.bad_token_notified = None
        self.email = None
        self.expiration = None
        self.expiration_notified = None
        self.token = None
        self.user_id = None

    @classmethod
    def create(cls, user_id, token, email):
        u = cls()
        u.user_id = user_id
        u.token = token
        u.expiration = datetime.datetime.utcnow() + datetime.timedelta(30)
        u.email = email
        sql = """
            INSERT INTO users (user_id, token, expiration, email)
            VALUES (%s, %s, %s, %s)
        """
        with db_conn.cursor() as cur:
            cur.execute(sql, [user_id, token, u.expiration, email])
        u.expiration_notified = False
        u.bad_token_notified = False
        return u

    @classmethod
    def get_by_id(cls, user_id):
        u = cls()
        sql = """
            SELECT user_id, token, expiration, email, expiration_notified,
            bad_token_notified FROM users WHERE user_id = %s
        """
        with db_conn.cursor() as cur:
            cur.execute(sql, [user_id])
            r = cur.fetchone()
        if r is None:
            return None
        u.user_id = int(r[0])
        u.token = r[1]
        u.expiration = r[2]
        u.email = r[3]
        u.expiration_notified = bool(r[4])
        u.bad_token_notified = bool(r[5])
        return u

    @classmethod
    def get_by_email(cls, email):
        u = cls()
        sql = """
            SELECT user_id, token, expiration, email, expiration_notified,
            bad_token_notified FROM users WHERE LOWER(email) = %s
        """
        with db_conn.cursor() as cur:
            cur.execute(sql, [email.lower()])
            r = cur.fetchone()
        if r is None:
            return None
        u.user_id = int(r[0])
        u.token = r[1]
        u.expiration = r[2]
        u.email = r[3]
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
        sql = """
            UPDATE users SET expiration = %s, expiration_notified = FALSE
            WHERE user_id = %s
        """
        with db_conn.cursor() as cur:
            cur.execute(sql, [self.expiration, self.user_id])

    def notify_bad_token(self):
        html_body = flask.render_template('email_problem.html')
        m = postmark.PMMail(
            api_key=POSTMARK_API_KEY,
            subject=u'GroupMemail delivery problem',
            sender=EMAIL_SENDER,
            to=self.email,
            html_body=html_body
        )
        m.send(test=False)

        self.bad_token_notified = True
        sql = 'UPDATE users SET bad_token_notified = TRUE WHERE user_id = %s'
        with db_conn.cursor() as cur:
            cur.execute(sql, [self.user_id])

    def notify_expiration(self):
        html_body = flask.render_template('email_expired.html', user=self)
        m = postmark.PMMail(
            api_key=POSTMARK_API_KEY,
            subject=u'GroupMemail service expiration',
            sender=EMAIL_SENDER,
            to=self.email,
            html_body=html_body
        )
        m.send(test=False)

        self.expiration_notified = True
        sql = 'UPDATE users SET expiration_notified = TRUE WHERE user_id = %s'
        with db_conn.cursor() as cur:
            cur.execute(sql, [self.user_id])

    def set_token(self, token):
        self.token = token
        self.bad_token_notified = False
        sql = """
            UPDATE users SET token = %s, bad_token_notified = FALSE
            WHERE user_id = %s"""
        with db_conn.cursor() as cur:
            cur.execute(sql, [token, self.user_id])


def external_url(endpoint, **values):
    return flask.url_for(endpoint, _external=True, _scheme=SCHEME, **values)


@app.route('/ping')
def ping():
    return 'pong'


@app.route('/')
def index():
    if 'groupme_token' in flask.request.cookies:
        token = flask.request.cookies.get('groupme_token')
    else:
        return flask.render_template('landing.html', cid=GM_CID)

    gm = GroupMeClient(token)
    gm_user = gm.me()
    user = gm_user.get('response')
    db_user = User.get_by_id(user.get('user_id'))
    if db_user is None:
        msg = 'Subscribe to a group to get free service for 30 days.'
    else:
        if db_user.token != token:
            db_user.set_token(token)
        if db_user.expired:
            msg = 'Your GroupMemail service expired on {}.'
        else:
            msg = 'Your GroupMemail service will expire on {}.'
        msg = msg.format(db_user.expiration.strftime('%d %B %Y'))
    user['expiration_msg'] = msg
    return flask.render_template('list.html', user=user)


@app.route('/login')
def login():
    index_url = external_url('index')
    resp = flask.make_response(flask.redirect(index_url, code=303))

    if 'groupme_token' in flask.request.cookies:
        token = flask.request.cookies.get('groupme_token')
        resp.set_cookie('groupme_token', token)

    if 'access_token' in flask.request.args:
        token = flask.request.args.get('access_token')
        resp.set_cookie('groupme_token', token)

    return resp


@app.route('/logout')
def logout():
    index_url = external_url('index')
    resp = flask.make_response(flask.redirect(index_url, code=303))
    resp.delete_cookie('groupme_token')
    return resp


@app.route('/subscribe/<int:group_id>')
def subscribe(group_id):
    if 'groupme_token' in flask.request.cookies:
        token = flask.request.cookies.get('groupme_token')
    else:
        return flask.redirect(external_url('index'), code=303)

    gm = GroupMeClient(token)
    gm_user = gm.me()
    user_id = gm_user.get('response').get('id')
    email = gm_user.get('response').get('email')

    db_user = User.get_by_id(user_id)
    if db_user is None:
        db_user = User.create(user_id, token, email)

    if db_user.token != token:
        db_user.set_token(token)

    if not db_user.expired:
        url = external_url('incoming', user_id=user_id)
        gm.create_bot('GroupMemail', group_id, url)

    return flask.redirect(external_url('index'), code=303)


@app.route('/unsubscribe/<int:group_id>')
def unsubscribe(group_id):
    if 'groupme_token' in flask.request.cookies:
        token = flask.request.cookies.get('groupme_token')
    else:
        return flask.redirect(external_url('index'), code=303)

    gm = GroupMeClient(token)
    gm_user = gm.me()
    user_id = gm_user.get('response').get('id')

    url = flask.url_for('incoming', user_id=user_id)

    bots = gm.bots()
    for bot in bots.get('response'):
        if int(bot.get('group_id')) == group_id:
            if url in bot.get('callback_url'):
                gm.destroy_bot(bot.get('bot_id'))

    return flask.redirect(external_url('index'), code=303)


@app.route('/payment')
def payment():
    if 'groupme_token' in flask.request.cookies:
        token = flask.request.cookies.get('groupme_token')
    else:
        return flask.redirect(external_url('index'), code=303)

    gm = GroupMeClient(token)
    gm_user = gm.me()
    user = gm_user.get('response')
    db_user = User.get_by_id(user.get('user_id'))
    if db_user is None:
        msg = 'Subscribe to a group to get free service for 30 days.'
    else:
        if db_user.expired:
            msg = 'Your GroupMemail service expired on {}.'
        else:
            msg = 'Your GroupMemail service will expire on {}.'
        msg = msg.format(db_user.expiration.strftime('%d %B %Y'))
    user['expiration_msg'] = msg

    key = stripe_keys.get('publishable_key')
    return flask.render_template('payment.html', key=key, user=user)


@app.route('/charge', methods=['POST'])
def charge():
    if 'groupme_token' in flask.request.cookies:
        token = flask.request.cookies.get('groupme_token')
    else:
        return flask.redirect(external_url('index'), code=303)

    amount = 600

    gm = GroupMeClient(token)
    gm_user = gm.me()
    user = gm_user.get('response')

    card = flask.request.form.get('stripeToken')
    customer = stripe.Customer.create(email=user.get('email'), card=card)

    try:
        stripe.Charge.create(
            customer=customer.id,
            amount=amount,
            currency='usd',
            description='GroupMemail Service: 6 months'
        )
    except stripe.CardError:
        return flask.redirect(external_url('index'), code=303)

    db_user = User.get_by_id(user.get('user_id'))
    db_user.extend(180)

    return flask.redirect(external_url('index'), code=303)


@app.route('/incoming/<int:user_id>', methods=['POST'])
def incoming(user_id):
    user = User.get_by_id(user_id)
    if user is None:
        app.logger.error('{} is not a known user_id'.format(user_id))
        flask.abort(404)

    j = flask.request.get_json()
    app.logger.debug(j)
    for field in ['name', 'text', 'group_id', 'attachments']:
        if field not in j:
            e_msg = 'Posted parameters did not include a required field: {}'
            app.logger.error(e_msg.format(field))
            flask.abort(500)

    gm = GroupMeClient(user.token)

    if user.expired:
        err = 'user_id {} expired on {}'.format(user_id, user.expiration)
        app.logger.error(err)
        url = flask.url_for('incoming', user_id=user_id)
        for bot in gm.bots().get('response'):
            if int(bot.get('group_id')) == int(j.get('group_id')):
                if url in bot.get('callback_url'):
                    gm.destroy_bot(bot.get('bot_id'))
        if not user.expiration_notified:
            user.notify_expiration()
        return '', 204

    gm_group = gm.group_info(j.get('group_id'))
    if gm_group is None:
        if user.bad_token_notified:
            err = '{} was already notified of bad token.'.format(user.email)
            app.logger.error(err)
        else:
            err = 'Sending bad token notification to {}.'.format(user.email)
            app.logger.error(err)
            user.notify_bad_token()
        return 'Thank you.'

    try:
        group_name = gm_group.get('response').get('name')
    except AttributeError:
        if user.bad_token_notified:
            err = '{} was already notified of bad token.'.format(user.email)
            app.logger.error(err)
        else:
            err = 'Sending bad token notification to {}.'.format(user.email)
            app.logger.error(err)
            user.notify_bad_token()
        return 'Thank you'

    html_body = flask.render_template('email_message.html', j=j)
    reply_to_tokens = list(EMAIL_SENDER.partition('@'))
    reply_to_tokens.insert(1, '+{}'.format(j.get('group_id')))
    reply_to = ''.join(reply_to_tokens)
    m = postmark.PMMail(
        api_key=POSTMARK_API_KEY,
        subject='New message in {}'.format(group_name),
        sender=EMAIL_SENDER,
        reply_to=reply_to,
        to=user.email,
        html_body=html_body
    )
    m.send(test=False)
    return 'Thank you.'


@app.route('/email', methods=['POST'])
def handle_email():
    j = flask.request.get_json()

    source = j.get('FromFull').get('Email')
    dest = j.get('MailboxHash')
    text = j.get('TextBody')

    user = User.get_by_email(source)
    if user is None:
        err = 'Received mail from unknown address: {}'.format(source)
        app.logger.error(err)
        flask.abort(404)

    tokens = text.splitlines()
    if '' in tokens:
        empty_line_index = tokens.index('')
        tokens = tokens[:empty_line_index]
    message = ' '.join(tokens)
    gm = GroupMeClient(user.token)
    gm.create_message(dest, message)

    return 'Thank you.'

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')
