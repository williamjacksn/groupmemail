import os


class Config:
    log_format: str
    log_level: str
    scheme: str
    secret_key: str
    server_name: str
    version: str

    def __init__(self):
        """Instantiating a Config object will automatically read the following environment variables:

        APP_VERSION, LOG_FORMAT, LOG_LEVEL, SCHEME, SECRET_KEY, SERVER_NAME

        Some variables have defaults if they are not found in the environment:

        LOG_FORMAT="%(levelname)s [%(name)s] %(message)s"
        LOG_LEVEL=INFO
        SCHEME=http"""

        self.log_format = os.getenv('LOG_FORMAT', '%(levelname)s [%(name)s] %(message)s')
        self.log_level = os.getenv('LOG_LEVEL', 'INFO')
        self.scheme = os.getenv('SCHEME', 'http')
        self.secret_key = os.getenv('SECRET_KEY')
        self.server_name = os.getenv('SERVER_NAME')
        self.version = os.getenv('APP_VERSION', 'unknown')
