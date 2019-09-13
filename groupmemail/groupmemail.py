import flask
import functools
import groupmemail.config
import groupmemail.db
import groupmemail.groupme
import logging
import requests
import stripe
import stripe.error
import sys
import waitress
import werkzeug.middleware.proxy_fix

config = groupmemail.config.Config()
stripe.api_key = config.stripe_secret_key

app = flask.Flask(__name__)
app.wsgi_app = werkzeug.middleware.proxy_fix.ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_port=1)

app.secret_key = config.secret_key
app.config['PREFERRED_URL_SCHEME'] = config.scheme
app.config['SERVER_NAME'] = config.server_name


def login_required(f):
    @functools.wraps(f)
    def decorated_function(*args, **kwargs):
        groupme_token = flask.session.get('groupme_token')
        app.logger.debug(f'Checking login, groupme_token: {groupme_token}')
        if groupme_token is None:
            return flask.redirect(flask.url_for('index'))
        return f(*args, **kwargs)
    return decorated_function


def notify_bad_token(user_id: int):
    db = groupmemail.db.GroupMemailDatabase(config.dsn)
    user = db.get_user_by_id(user_id)
    html_body = flask.render_template('email_problem.html')
    requests.post(
        f'https://api.mailgun.net/v3/{config.mailgun_domain}/messages',
        auth=('api', config.mailgun_api_key),
        data={
            'from': config.email_sender,
            'to': user['email'],
            'subject': 'GroupMemail delivery problem',
            'html': html_body
        }
    )
    db.set_bad_token_notified(user_id, True)


def notify_expiration(user_id: int):
    db = groupmemail.db.GroupMemailDatabase(config.dsn)
    user = db.get_user_by_id(user_id)
    html_body = flask.render_template('email_expired.html', expiration=user['expiration'])
    requests.post(
        f'https://api.mailgun.net/v3/{config.mailgun_domain}/messages',
        auth=('api', config.mailgun_api_key),
        data={
            'from': config.email_sender,
            'to': user['email'],
            'subject': 'GroupMemail service expiration',
            'html': html_body
        }
    )
    db.set_expiration_notified(user_id, True)


def external_url(endpoint, **values):
    return flask.url_for(endpoint, _external=True, _scheme=config.scheme, **values)


@app.before_request
def before_request():
    app.logger.info(f'{flask.request.method} {flask.request.path}')


@app.route('/ping')
def ping():
    return 'pong'


@app.route('/')
def index():
    groupme_token = flask.session.get('groupme_token')
    if groupme_token is None:
        flask.g.cid = config.groupme_client_id
        return flask.render_template('landing.html')

    db = groupmemail.db.GroupMemailDatabase(config.dsn)
    gm = groupmemail.groupme.GroupMeClient(groupme_token)
    gm_user = gm.me()
    user = gm_user.get('response')
    user_id = user.get('user_id')
    db_user = db.get_user_by_id(user_id)
    if db_user is None:
        msg = 'Subscribe to a group to get free service for 30 days.'
    else:
        if db_user['token'] != groupme_token:
            db.set_token(user_id, groupme_token)
        if groupmemail.db.expired(db_user['expiration']):
            msg = 'Your GroupMemail service expired on {}.'
        else:
            msg = 'Your GroupMemail service will expire on {}.'
        msg = msg.format(db_user['expiration'].strftime('%d %B %Y'))
        db.set_bad_token_notified(user_id, False)
    user['expiration_msg'] = msg
    flask.g.user = user
    return flask.render_template('list.html')


@app.route('/login')
def login():
    if 'access_token' in flask.request.values:
        groupme_token = flask.request.values.get('access_token')
        flask.session['groupme_token'] = groupme_token
    return flask.redirect(flask.url_for('index'))


@app.route('/logout')
def logout():
    flask.session.pop('groupme_token')
    return flask.redirect(flask.url_for('index'))


@app.route('/subscribe/<int:group_id>')
@login_required
def subscribe(group_id):
    groupme_token = flask.session.get('groupme_token')
    gm = groupmemail.groupme.GroupMeClient(groupme_token)
    gm_user = gm.me()
    user_id = gm_user.get('response').get('id')
    email = gm_user.get('response').get('email')

    db = groupmemail.db.GroupMemailDatabase(config.dsn)
    db_user = db.get_user_by_id(user_id)
    if db_user is None:
        db_user = db.create_user(user_id, email, groupme_token)

    if db_user['token'] != groupme_token:
        db.set_token(user_id, groupme_token)

    if not groupmemail.db.expired(db_user['expiration']):
        url = external_url('incoming', user_id=user_id)
        app.logger.debug(f'User {user_id} ({email}) is subscribing to group {group_id}')
        app.logger.debug(f'Setting bot callback url to {url}')
        gm.create_bot('GroupMemail', group_id, url)

    return flask.redirect(flask.url_for('index'), code=303)


@app.route('/unsubscribe/<int:group_id>')
@login_required
def unsubscribe(group_id):
    groupme_token = flask.session.get('groupme_token')
    gm = groupmemail.groupme.GroupMeClient(groupme_token)
    gm_user = gm.me()
    user_id = gm_user.get('response').get('id')

    url = flask.url_for('incoming', user_id=user_id)
    app.logger.debug(f'User {user_id} wants to unsubscribe from group {group_id}')
    app.logger.debug(f'Looking for bot with callback url {url}')

    bots = gm.bots()
    for bot in bots.get('response'):
        if int(bot.get('group_id')) == group_id:
            if url in bot.get('callback_url'):
                bot_id = bot.get('bot_id')
                app.logger.debug(f'Destroying bot with id {bot_id}')
                gm.destroy_bot(bot_id)

    return flask.redirect(flask.url_for('index'), code=303)


@app.route('/payment')
@login_required
def payment():
    groupme_token = flask.session.get('groupme_token')
    gm = groupmemail.groupme.GroupMeClient(groupme_token)
    gm_user = gm.me()
    user = gm_user.get('response')
    user_id = user.get('user_id')
    db = groupmemail.db.GroupMemailDatabase(config.dsn)
    db_user = db.get_user_by_id(user_id)
    if db_user is None:
        msg = 'Subscribe to a group to get free service for 30 days.'
    else:
        if groupmemail.db.expired(db_user['expiration']):
            msg = 'Your GroupMemail service expired on {}.'
        else:
            msg = 'Your GroupMemail service will expire on {}.'
        msg = msg.format(db_user['expiration'].strftime('%d %B %Y'))
    user['expiration_msg'] = msg

    flask.g.user = user
    flask.g.stripe_key = config.stripe_publishable_key
    flask.g.stripe_sku = config.stripe_sku
    return flask.render_template('payment.html')


@app.route('/reset-callback-urls')
@login_required
def reset_callback_urls():
    groupme_token = flask.session.get('groupme_token')
    gm = groupmemail.groupme.GroupMeClient(groupme_token)
    gm_user = gm.me()
    user = gm_user.get('response')
    user_id = user.get('user_id')
    db = groupmemail.db.GroupMemailDatabase(config.dsn)
    db_user = db.get_user_by_id(user_id)
    email = db_user.get('email')
    if email == config.admin_email:
        app.logger.debug('Resetting callback urls ...')
        for u in db.get_users():
            user_id = u['user_id']
            url_fragment = flask.url_for('incoming', user_id=user_id)
            gm = groupmemail.groupme.GroupMeClient(u['token'])
            bots = gm.bots()
            if bots.get('response') is None:
                continue
            for bot in bots.get('response'):
                bot_id = bot.get('bot_id')
                if url_fragment in bot.get('callback_url'):
                    new_cb_url = external_url('incoming', user_id=u['user_id'])
                    app.logger.debug(f'Updating bot {bot_id} for user {user_id} with callback url {new_cb_url}')
                    gm.update_bot(bot_id, bot.get('name'), bot.get('group_id'), new_cb_url)
    return flask.redirect(flask.url_for('index'), code=303)


@app.route('/stripe-webhook', methods=['POST'])
def stripe_webhook():
    sig_header = flask.request.headers.get('stripe-signature')
    event = None
    try:
        event = stripe.Webhook.construct_event(flask.request.data, sig_header, config.stripe_webhook_secret)
    except ValueError as e:
        app.logger.warning(f'Invalid webhook payload: {e}')
        flask.abort(404)
    except stripe.error.SignatureVerificationError as e:
        app.logger.warning(f'Invalid webhook signature: {e}')
        flask.abort(404)
    app.logger.info(f'I received a webhook: {event.type}')
    return 'OK'


@app.route('/payment-success')
@login_required
def payment_success():
    groupme_token = flask.session.get('groupme_token')
    gm = groupmemail.groupme.GroupMeClient(groupme_token)
    gm_user = gm.me()
    user = gm_user.get('response')
    user_id = user.get('user_id')

    db = groupmemail.db.GroupMemailDatabase(config.dsn)
    db.extend(user_id, 180)

    return flask.redirect(flask.url_for('index'), code=303)


@app.route('/incoming/<int:user_id>', methods=['POST'])
def incoming(user_id):
    db = groupmemail.db.GroupMemailDatabase(config.dsn)
    user = db.get_user_by_id(user_id)
    if user is None:
        app.logger.error(f'{user_id} is not a known user_id')
        flask.abort(404)

    if user['ignored']:
        app.logger.warning(f'{user_id} is currently being ignored')
        flask.abort(404)

    email = user['email']

    j = flask.request.get_json()
    app.logger.debug(f'request body: {j}')
    if j is None:
        flask.abort(400)
    for field in ['name', 'text', 'group_id', 'attachments']:
        if field not in j:
            app.logger.error(f'Posted parameters did not include a required field: {field}')
            flask.abort(400)

    gm = groupmemail.groupme.GroupMeClient(user['token'])

    expiration = user['expiration']
    if groupmemail.db.expired(expiration):
        app.logger.error(f'user_id {user_id} expired on {expiration}')
        url = flask.url_for('incoming', user_id=user_id)
        for bot in gm.bots().get('response'):
            if int(bot.get('group_id')) == int(j.get('group_id')):
                if url in bot.get('callback_url'):
                    gm.destroy_bot(bot.get('bot_id'))
        if not user['expiration_notified']:
            notify_expiration(user_id)
        return '', 204

    group_id = j.get('group_id')
    gm_group = gm.group_info(group_id)
    app.logger.debug(f'group_info: {gm_group}')

    if gm_group['meta']['code'] == 404:
        app.logger.error(f'Group ID {group_id} was not found')
        flask.abort(400)

    if gm_group is None:
        if user['bad_token_notified']:
            app.logger.error(f'{email} was already notified of bad token.')
        else:
            app.logger.error(f'Sending bad token notification to {email}.')
            notify_bad_token(user_id)
        return 'Thank you.'

    try:
        group_name = gm_group.get('response').get('name')
    except AttributeError:
        if user['bad_token_notified']:
            app.logger.error(f'{email} was already notified of bad token.')
        else:
            app.logger.error(f'Sending bad token notification to {email}.')
            notify_bad_token(user_id)
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
            'to': email,
            'subject': f'New message in {group_name}',
            'html': html_body
        }
    )
    return 'Thank you.'


def get_canonical_email(email: str) -> str:
    """Canonicalize an email address. Currently this means removing any plus-codes from the username part."""
    username, _, domain = email.partition('@')
    username, _, _ = username.partition('+')
    canonical_email = f'{username}@{domain}'.lower()
    return canonical_email


@app.route('/email', methods=['POST'])
def handle_email():
    source = get_canonical_email(flask.request.values.get('sender'))
    dest = flask.request.values.get('recipient').split('@')[0]
    text = flask.request.values.get('stripped-text')
    if text is None:
        app.logger.warning(f'Email from {source} to {dest} does not have stripped-text')
        app.logger.debug(flask.request.values)
        return 'Thank you.'

    app.logger.info(f'Handling email from {source} to {dest}')

    tokens = [line.strip() for line in text.splitlines()]
    if '' in tokens:
        empty_line_index = tokens.index('')
        tokens = tokens[:empty_line_index]
    message = ' '.join(tokens)

    db = groupmemail.db.GroupMemailDatabase(config.dsn)
    user = db.get_user_by_email(source)
    if user is None:
        app.logger.error(f'Received email from unknown address: {source}')
        app.logger.debug(flask.request.values)
        flask.abort(406)

    gm = groupmemail.groupme.GroupMeClient(user['token'])
    gm.create_message(dest, message)

    return 'Thank you.'


def main():
    logging.basicConfig(format=config.log_format, level='DEBUG', stream=sys.stdout)
    app.logger.debug(f'groupmemail {config.version}')
    app.logger.debug(f'Changing log level to {config.log_level}')
    logging.getLogger().setLevel(config.log_level)

    if config.dsn is None:
        app.logger.critical('Missing environment variable DSN; the database is unavailable')
    else:
        groupmemail.db.GroupMemailDatabase(config.dsn).migrate()

    waitress.serve(app, ident=None)
