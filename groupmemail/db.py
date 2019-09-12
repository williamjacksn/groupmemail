import datetime
import logging
import psycopg2
import psycopg2.extras

from typing import Dict, List, Optional

log = logging.getLogger(__name__)


class GroupMemailDatabase:
    def __init__(self, dsn: str):
        self.cnx = psycopg2.connect(dsn=dsn, cursor_factory=psycopg2.extras.RealDictCursor)
        self.cnx.autocommit = True

    def _q(self, sql: str, args: Dict = None) -> List[Dict]:
        if args is None:
            args = {}
        with self.cnx.cursor() as c:
            c.execute(sql, args)
            return c.fetchall()

    def _u(self, sql: str, args: Dict = None):
        if args is None:
            args = {}
        with self.cnx.cursor() as c:
            c.execute(sql, args)

    def add_schema_version(self, schema_version: int):
        sql = '''
            INSERT INTO schema_versions (schema_version, migration_date)
            VALUES (%(schema_version)s, %(migration_date)s)
        '''
        self._u(sql, {'schema_version': schema_version, 'migration_date': datetime.datetime.utcnow()})

    def create_user(self, user_id: int, email: str, token: str) -> Dict:
        params = {
            'email': email,
            'expiration': datetime.datetime.utcnow() + datetime.timedelta(days=30),
            'token': token,
            'user_id': user_id
        }
        sql = '''
            INSERT INTO users (user_id, token, expiration, email)
            VALUES (%(user_id)s, %(token)s, %(expiration)s, %(email)s)
        '''
        self._u(sql, params)
        return self.get_user_by_id(user_id)

    def extend(self, user_id: int, days: int):
        base = datetime.datetime.utcnow()
        params = {'user_id': user_id}
        sql = 'SELECT expiration FROM users WHERE user_id = %(user_id)s'
        for record in self._q(sql, params):
            base = record['expiration']
        base = max(base, datetime.datetime.utcnow())
        params['expiration'] = base + datetime.timedelta(days=days)
        sql = 'UPDATE users SET expiration = %(expiration)s, expiration_notified = FALSE WHERE user_id = %(user_id)s'
        self._u(sql, params)

    def get_bad_token_notified(self, user_id):
        sql = 'SELECT bad_token_notified FROM users WHERE user_id = %(user_id)s'
        for record in self._q(sql, {'user_id': user_id}):
            return record['bad_token_notified']
        return False

    def get_email(self, user_id: int) -> str:
        sql = 'SELECT email FROM users WHERE user_id = %(user_id)s'
        for record in self._q(sql, {'user_id': user_id}):
            return record['email']

    def get_expiration(self, user_id: int) -> datetime.datetime:
        sql = 'SELECT expiration FROM users WHERE user_id = %(user_id)s'
        for record in self._q(sql, {'user_id': user_id}):
            return record['expiration']

    def get_expiration_notified(self, user_id: int) -> bool:
        sql = 'SELECT expiration_notified FROM users WHERE user_id = %(user_id)s'
        for record in self._q(sql, {'user_id': user_id}):
            return record['expiration_notified']
        return False

    def get_token(self, user_id):
        sql = 'SELECT token FROM users WHERE user_id = %(user_id)s'
        for record in self._q(sql, {'user_id': user_id}):
            return record['token']

    def get_user_by_email(self, email: str) -> Optional[Dict]:
        log.debug(f'Looking for user with email {email}')
        params = {'email': email}

        # does this email exist in the users table?
        sql = 'SELECT email FROM users WHERE email = %(email)s'
        rows = self._q(sql, params)
        if not rows:
            # no, check the alt_emails table
            log.debug(f'{email} is not a primary email address, checking alternate emails')
            sql = 'SELECT primary_email FROM alt_emails WHERE alt_email = %(email)s'
            rows = self._q(sql, params)
            if not rows:
                # this isn't an alt email either
                log.debug(f'{email} is not an alternate email either')
                return None
            else:
                # this is an alt email
                primary_email = rows[0]['primary_email']
                log.debug(f'{email} is an alternate for {primary_email}')
                params['email'] = primary_email

        sql = '''
            SELECT bad_token_notified, email, expiration, expiration_notified, ignored, token, user_id
            FROM users
            WHERE email = %(email)s
        '''
        rows = self._q(sql, params)
        return rows[0]

    def get_user_by_id(self, user_id: int) -> Optional[Dict]:
        sql = '''
            SELECT bad_token_notified, email, expiration, expiration_notified, ignored, token, user_id
            FROM users
            WHERE user_id = %(user_id)s
        '''
        for record in self._q(sql, {'user_id': user_id}):
            return record

    def get_users(self) -> List[Dict]:
        sql = 'SELECT user_id, token FROM users'
        return self._q(sql)

    def migrate(self):
        log.info(f'The database is at schema version {self.version}')
        log.info('Checking for database migrations')
        if self.version < 1:
            log.info('Migrating from version 0 to version 1')
            self._u('''
                CREATE TABLE schema_versions (
                    schema_version INTEGER PRIMARY KEY,
                    migration_date TIMESTAMP NOT NULL
                )
            ''')
            self._u('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    token TEXT,
                    expiration TIMESTAMP,
                    email TEXT,
                    expiration_notified BOOLEAN,
                    bad_token_notified BOOLEAN
                )
            ''')
            self.add_schema_version(1)
        if self.version < 2:
            log.info('Migrating from version 1 to version 2')
            self._u('''
                ALTER TABLE users
                ADD COLUMN ignored BOOLEAN DEFAULT FALSE
            ''')
            self.add_schema_version(2)
        if self.version < 3:
            log.info('Migrating from version 2 to version 3')
            self._u('''
                CREATE TABLE IF NOT EXISTS alt_emails (
                    alt_email TEXT PRIMARY KEY,
                    primary_email TEXT
                )
            ''')
            self.add_schema_version(3)

    def set_bad_token_notified(self, user_id: int, bad_token_notified: bool):
        params = {
          'bad_token_notified': bad_token_notified,
          'user_id': user_id
        }
        sql = 'UPDATE users SET bad_token_notified = %(bad_token_notified)s WHERE user_id = %(user_id)s'
        self._u(sql, params)

    def set_expiration_notified(self, user_id: int, expiration_notified: bool):
        params = {
          'expiration_notified': expiration_notified,
          'user_id': user_id
        }
        sql = 'UPDATE users SET expiration_notified = %(expiration_notified)s WHERE user_id = %(user_id)s'
        self._u(sql, params)

    def set_token(self, user_id: int, token: str):
        params = {
          'token': token,
          'user_id': user_id
        }
        sql = 'UPDATE users SET token = %(token)s WHERE user_id = %(user_id)s'
        self._u(sql, params)

    def user_exists(self, user_id: int) -> bool:
        sql = 'SELECT 1 FROM users WHERE user_id = %(user_id)s'
        for _ in self._q(sql, {'user_id': user_id}):
            return True
        return False

    def user_is_expired(self, user_id):
        sql = 'SELECT expiration FROM users WHERE user_id = %(user_id)s'
        for record in self._q(sql, {'user_id': user_id}):
            return record['expiration'] < datetime.datetime.utcnow()

    @property
    def version(self) -> int:
        sql = 'SELECT count(*) table_count FROM information_schema.tables WHERE table_name = %(table_name)s'
        for record in self._q(sql, {'table_name': 'schema_versions'}):
            if record['table_count'] == 0:
                return 0
        sql = 'SELECT max(schema_version) current_version FROM schema_versions'
        for record in self._q(sql):
            return record['current_version']


class GroupMemailUser:
    bad_token_notified: bool = False
    email: str
    expiration: datetime.datetime
    expiration_notified: bool = False
    token: str
    user_id: int

    def update_from_dict(self, params: Dict):
        self.bad_token_notified = params.get('bad_token_notified', False)
        self.email = params.get('email')
        self.expiration = params.get('expiration', datetime.datetime.utcnow())
        self.expiration_notified = params.get('expiration_notified', False)
        self.token = params.get('token')
        self.user_id = params.get('user_id')


def expired(date: datetime.datetime) -> bool:
    return date < datetime.datetime.utcnow()
