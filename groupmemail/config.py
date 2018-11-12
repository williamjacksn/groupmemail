"""
List of environment variables:

ADMIN_EMAIL
DSN
EMAIL_SENDER
GROUPME_CLIENT_ID
LOG_FORMAT
LOG_LEVEL
MAILGUN_API_KEY
MAILGUN_DOMAIN
SCHEME
SECRET_KEY
SERVER_NAME
STRIPE_PUBLISHABLE_KEY
STRIPE_SECRET_KEY
"""

import os
import pathlib


class Config:
    admin_email: str
    dsn: str
    email_sender: str
    groupme_client_id: str
    log_format: str
    log_level: str
    mailgun_api_key: str
    mailgun_domain: str
    scheme: str
    secret_key: str
    server_name: str
    stripe_publishable_key: str
    stripe_secret_key: str

    def __init__(self):
        self.admin_email = os.getenv('ADMIN_EMAIL')
        self.dsn = os.getenv('DSN')
        self.email_sender = os.getenv('EMAIL_SENDER')
        self.groupme_client_id = os.getenv('GROUPME_CLIENT_ID')
        self.log_format = os.getenv('LOG_FORMAT', '%(levelname)s [%(name)s] %(message)s')
        self.log_level = os.getenv('LOG_LEVEL', 'INFO')
        self.mailgun_api_key = os.getenv('MAILGUN_API_KEY')
        self.mailgun_domain = os.getenv('MAILGUN_DOMAIN')
        self.scheme = os.getenv('SCHEME', 'http')
        self.secret_key = os.getenv('SECRET_KEY')
        self.server_name = os.getenv('SERVER_NAME', 'localhost:8080')
        self.stripe_publishable_key = os.getenv('STRIPE_PUBLISHABLE_KEY')
        self.stripe_secret_key = os.getenv('STRIPE_SECRET_KEY')

    @property
    def version(self) -> str:
        """Read version from Dockerfile"""
        dockerfile = pathlib.Path(__file__).resolve().parent.parent / 'Dockerfile'
        with open(dockerfile) as f:
            for line in f:
                if 'org.label-schema.version' in line:
                    return line.strip().split('=', maxsplit=1)[1]
        return 'unknown'
