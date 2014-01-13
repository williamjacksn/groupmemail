import flask
import os
import postmark
import psycopg2
import requests

app = flask.Flask(__name__)
app.debug = True

GROUPME_ACCESS_TOKEN = os.environ.get(u'GROUPME_ACCESS_TOKEN')
GROUPME_CLIENT_ID = os.environ.get(u'GROUPME_CLIENT_ID')
POSTMARK_API_KEY = os.environ.get(u'POSTMARK_API_KEY')
EMAIL_SENDER = os.environ.get(u'EMAIL_SENDER')
EMAIL_TARGET = os.environ.get(u'EMAIL_TARGET')
DB_URL = os.environ.get(u'HEROKU_POSTGRESQL_COBALT_URL')

@app.route(u'/groupme')
def groupme_index():
    if u'groupme_token' in flask.request.cookies:
        db = GMMailDatabase()
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

@app.route(u'/groupme/new_message', methods=[u'POST'])
def groupme_new_message():
    j = flask.request.get_json()
    app.logger.debug(j)
    for field in [u'name', u'text', u'group_id', u'attachments']:
        if field not in j:
            e_msg = u'Posted parameters did not include a required field: {}'
            app.logger.error(e_msg.format(field))
            flask.abort(500)
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
    m = postmark.PMMail(
        api_key=POSTMARK_API_KEY,
        subject=u'New message in {}'.format(group_name),
        sender=EMAIL_SENDER,
        to=EMAIL_TARGET,
        html_body=email_body
    )
    m.send(test=False)
    return u'Thank you.'


class GMMailDatabase(object):
    def __init__(self):
        self.cnx = psycopg2.connect(DB_URL)
        cur = self.cnx.cursor()
        cur.execute(u'create table if not exists users (user_id integer '
            u'primary key, email text unique not null, expiration timestamp '
            u'default (current_timestamp + interval \'1 week\') not null)')
        cur.execute(u'create table if not exists subscriptions (user_id '
            u'integer references users on delete cascade, group_id integer '
            u'not null, primary key (user_id, group_id))')
        self.cnx.commit()
        cur.close()


if __name__ == u'__main__':
    app.run(debug=True, host=u'0.0.0.0')
