import datetime
import flask
import groupmemail.config
import groupmemail.groupme
import logging
import psycopg2
import requests
import stripe
import stripe.error
import sys
import waitress

config = groupmemail.config.Config()

app = flask.Flask(__name__)
stripe.api_key = config.stripe_secret_key


db_conn = psycopg2.connect(config.dsn)
db_conn.autocommit = True


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
        sql = 'INSERT INTO users (user_id, token, expiration, email) VALUES (%s, %s, %s, %s)'
        with db_conn.cursor() as cur:
            cur.execute(sql, [user_id, token, u.expiration, email])
        u.expiration_notified = False
        u.bad_token_notified = False
        return u

    @classmethod
    def get_by_id(cls, user_id):
        u = cls()
        sql = """
            SELECT user_id, token, expiration, email, expiration_notified, bad_token_notified
            FROM users WHERE user_id = %s
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
            SELECT user_id, token, expiration, email, expiration_notified, bad_token_notified
            FROM users WHERE LOWER(email) = %s
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
        sql = 'UPDATE users SET expiration = %s, expiration_notified = FALSE WHERE user_id = %s'
        with db_conn.cursor() as cur:
            cur.execute(sql, [self.expiration, self.user_id])

    def notify_bad_token(self):
        html_body = flask.render_template('email_problem.html')
        requests.post(
            f'https://api.mailgun.net/v3/{config.mailgun_domain}/messages',
            auth=('api', config.mailgun_api_key),
            data={
                'from': config.email_sender,
                'to': self.email,
                'subject': 'GroupMemail delivery problem',
                'html': html_body
            }
        )

        self.bad_token_notified = True
        sql = 'UPDATE users SET bad_token_notified = TRUE WHERE user_id = %s'
        with db_conn.cursor() as cur:
            cur.execute(sql, [self.user_id])

    def notify_expiration(self):
        html_body = flask.render_template('email_expired.html', user=self)
        requests.post(
            f'https://api.mailgun.net/v3/{config.mailgun_domain}/messages',
            auth=('api', config.mailgun_api_key),
            data={
                'from': config.email_sender,
                'to': self.email,
                'subject': 'GroupMemail service expiration',
                'html': html_body
            }
        )

        self.expiration_notified = True
        sql = 'UPDATE users SET expiration_notified = TRUE WHERE user_id = %s'
        with db_conn.cursor() as cur:
            cur.execute(sql, [self.user_id])

    def set_token(self, token):
        self.token = token
        self.bad_token_notified = False
        sql = 'UPDATE users SET token = %s, bad_token_notified = FALSE WHERE user_id = %s'
        with db_conn.cursor() as cur:
            cur.execute(sql, [token, self.user_id])


def external_url(endpoint, **values):
    return flask.url_for(endpoint, _external=True, _scheme=config.scheme, **values)


@app.route('/ping')
def ping():
    app.logger.debug(f'{flask.request.method} {flask.request.full_path}')
    return 'pong'


@app.route('/')
def index():
    app.logger.debug(f'{flask.request.method} {flask.request.full_path}')
    if 'groupme_token' in flask.request.cookies:
        token = flask.request.cookies.get('groupme_token')
    else:
        flask.g.cid = config.groupme_client_id
        return flask.render_template('landing.html')

    gm = groupmemail.groupme.GroupMeClient(token)
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
    flask.g.user = user
    return flask.render_template('list.html')


@app.route('/login')
def login():
    app.logger.debug(f'{flask.request.method} {flask.request.full_path}')
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
    app.logger.debug(f'{flask.request.method} {flask.request.full_path}')
    index_url = external_url('index')
    resp = flask.make_response(flask.redirect(index_url, code=303))
    resp.delete_cookie('groupme_token')
    return resp


@app.route('/subscribe/<int:group_id>')
def subscribe(group_id):
    app.logger.debug(f'{flask.request.method} {flask.request.full_path}')
    if 'groupme_token' in flask.request.cookies:
        token = flask.request.cookies.get('groupme_token')
    else:
        return flask.redirect(external_url('index'), code=303)

    gm = groupmemail.groupme.GroupMeClient(token)
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
    app.logger.debug(f'{flask.request.method} {flask.request.full_path}')
    if 'groupme_token' in flask.request.cookies:
        token = flask.request.cookies.get('groupme_token')
    else:
        return flask.redirect(external_url('index'), code=303)

    gm = groupmemail.groupme.GroupMeClient(token)
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
    app.logger.debug(f'{flask.request.method} {flask.request.full_path}')
    if 'groupme_token' in flask.request.cookies:
        token = flask.request.cookies.get('groupme_token')
    else:
        return flask.redirect(external_url('index'), code=303)

    gm = groupmemail.groupme.GroupMeClient(token)
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

    flask.g.user = user
    flask.g.stripe_key = config.stripe_publishable_key
    return flask.render_template('payment.html')


@app.route('/charge', methods=['POST'])
def charge():
    app.logger.debug(f'{flask.request.method} {flask.request.full_path}')
    if 'groupme_token' in flask.request.cookies:
        token = flask.request.cookies.get('groupme_token')
    else:
        return flask.redirect(external_url('index'), code=303)

    amount = 600

    gm = groupmemail.groupme.GroupMeClient(token)
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
    except stripe.error.CardError:
        return flask.redirect(external_url('index'), code=303)

    db_user = User.get_by_id(user.get('user_id'))
    db_user.extend(180)

    return flask.redirect(external_url('index'), code=303)


@app.route('/incoming/<int:user_id>', methods=['POST'])
def incoming(user_id):
    app.logger.debug(f'{flask.request.method} {flask.request.full_path}')
    user = User.get_by_id(user_id)
    if user is None:
        app.logger.error(f'{user_id} is not a known user_id')
        flask.abort(404)

    j = flask.request.get_json()
    app.logger.debug(j)
    for field in ['name', 'text', 'group_id', 'attachments']:
        if field not in j:
            app.logger.error(f'Posted parameters did not include a required field: {field}')
            flask.abort(500)

    gm = groupmemail.groupme.GroupMeClient(user.token)

    if user.expired:
        app.logger.error(f'user_id {user_id} expired on {user.expiration}')
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
            app.logger.error(f'{user.email} was already notified of bad token.')
        else:
            app.logger.error(f'Sending bad token notification to {user.email}.')
            user.notify_bad_token()
        return 'Thank you.'

    try:
        group_name = gm_group.get('response').get('name')
    except AttributeError:
        if user.bad_token_notified:
            app.logger.error(f'{user.email} was already notified of bad token.')
        else:
            app.logger.error(f'Sending bad token notification to {user.email}.')
            user.notify_bad_token()
        return 'Thank you'

    html_body = flask.render_template('email_message.html', j=j)
    group_id = j.get('group_id')
    reply_to = f'{group_id}@{config.mailgun_domain}'
    requests.post(
        f'https://api.mailgun.net/v3/{config.mailgun_domain}/messages',
        auth=('api', config.mailgun_api_key),
        data={
            'from': config.email_sender,
            'h:Reply-To': reply_to,
            'to': user.email,
            'subject': f'New message in {group_name}',
            'html': html_body
        }
    )
    return 'Thank you.'


@app.route('/email', methods=['POST'])
def handle_email():
    app.logger.debug(f'{flask.request.method} {flask.request.full_path}')
    source = flask.request.form.get('sender')
    dest = flask.request.form.get('recipient').split('@')[0]
    text = flask.request.form.get('stripped-text')
    tokens = [line.strip() for line in text.splitlines()]
    if '' in tokens:
        empty_line_index = tokens.index('')
        tokens = tokens[:empty_line_index]
    message = ' '.join(tokens)

    user = User.get_by_email(source)
    if user is None:
        app.logger.error(f'Received mail from unknown address: {source}')
        flask.abort(406)

    gm = groupmemail.groupme.GroupMeClient(user.token)
    gm.create_message(dest, message)

    return 'Thank you.'


def main():
    logging.basicConfig(format=config.log_format, level='DEBUG', stream=sys.stdout)
    app.logger.debug(f'groupmemail {config.version}')
    app.logger.debug(f'Changing log level to {config.log_level}')
    logging.getLogger().setLevel(config.log_level)

    waitress.serve(app)
