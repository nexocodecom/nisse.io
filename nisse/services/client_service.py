from sqlalchemy.orm import Session
from flask_injector import inject
from nisse.models.database import Client
from werkzeug.security import gen_salt


class ClientService(object):
    @inject
    def __init__(self, session: Session):
        self.db = session()

    def find(self, client_id):
        return self.db.query(Client)\
            .filter(client_id == client_id)\
            .first()

    def delete(self, client: Client):
        """ Delete existing token. """
        self.db.delete(Client)
        self.db.commit()
        return self

    def generate(self):
        """ Generate a new public client with the ObjectID helper."""
        client = Client(client_id=gen_salt(40), client_type='public')
        self.db.add(client)
        self.db.commit()
        return client

    def __del__(self):
        if self.db is not None:
            self.db.close()
