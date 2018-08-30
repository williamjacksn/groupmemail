import os


class Config:
    dsn: str
    email_sender: str
    groupme_client_id: str
    log_format: str
    log_level: str
    mailgun_api_key: str
    mailgun_domain: str
    scheme: str
    stripe_publishable_key: str
    stripe_secret_key: str
    version: str = '1.0.1'

    def __init__(self):
        self.dsn = os.getenv('DSN')
        self.email_sender = os.getenv('EMAIL_SENDER')
        self.groupme_client_id = os.getenv('GROUPME_CLIENT_ID')
        self.log_format = os.getenv('LOG_FORMAT', '%(levelname)s [%(name)s] %(message)s')
        self.log_level = os.getenv('LOG_LEVEL', 'DEBUG')
        self.mailgun_api_key = os.getenv('MAILGUN_API_KEY')
        self.mailgun_domain = os.getenv('MAILGUN_DOMAIN')
        self.scheme = os.getenv('SCHEME', 'http')
        self.stripe_publishable_key = os.getenv('STRIPE_PUBLISHABLE_KEY')
        self.stripe_secret_key = os.getenv('STRIPE_SECRET_KEY')
