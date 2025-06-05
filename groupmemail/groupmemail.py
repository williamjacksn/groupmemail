import flask
import groupmemail.config
import logging
import sys
import waitress
import werkzeug.middleware.proxy_fix

config = groupmemail.config.Config()

app = flask.Flask(__name__)
app.wsgi_app = werkzeug.middleware.proxy_fix.ProxyFix(
    app.wsgi_app, x_for=1, x_proto=1, x_port=1
)

app.secret_key = config.secret_key
app.config["PREFERRED_URL_SCHEME"] = config.scheme
app.config["SERVER_NAME"] = config.server_name


@app.before_request
def before_request():
    app.logger.debug(f"{flask.request.method} {flask.request.path}")


@app.route("/email", methods=["POST"])
@app.route("/login")
@app.route("/logout")
@app.route("/payment")
@app.route("/payment-success")
@app.route("/ping")
@app.route("/reset-callback-urls")
@app.route("/stripe-webhook", methods=["POST"])
@app.route("/")
def index():
    return "ok"


@app.route("/incoming/<int:entity_id>", methods=["POST"])
@app.route("/subscribe/<int:entity_id>")
@app.route("/unsubscribe/<int:entity_id>")
def with_entity_id(entity_id):
    return "ok"


def main():
    logging.basicConfig(format=config.log_format, level="DEBUG", stream=sys.stdout)
    app.logger.debug(f"groupmemail {config.version}")
    app.logger.debug(f"Changing log level to {config.log_level}")
    logging.getLogger().setLevel(config.log_level)

    waitress.serve(app, ident=None)
