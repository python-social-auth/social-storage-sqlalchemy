"""SQLAlchemy models for Social Auth"""
import base64
import six
import json

try:
    import transaction
except ImportError:
    transaction = None

from sqlalchemy import Column, Integer, String
from sqlalchemy.exc import IntegrityError
from sqlalchemy.types import PickleType, Text
from sqlalchemy.schema import UniqueConstraint
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.ext.mutable import MutableDict

from social_core.storage import UserMixin, AssociationMixin, NonceMixin, \
                                CodeMixin, PartialMixin, BaseStorage

class JSONPickler(object):
    """JSON pickler wrapper around json lib since SQLAlchemy invokes
    dumps with extra positional parameters"""

    @classmethod
    def dumps(cls, value, *args, **kwargs):
        """Dumps the python value into a JSON string"""
        return json.dumps(value)

    @classmethod
    def loads(cls, value):
        """Parses the JSON string and returns the corresponding python value"""
        return json.loads(value)


# JSON type field
class JSONType(PickleType):
    impl = Text

    def __init__(self, *args, **kwargs):
        kwargs['pickler'] = JSONPickler
        super(JSONType, self).__init__(*args, **kwargs)


class SQLAlchemyMixin(object):
    COMMIT_SESSION = True

    @classmethod
    def _session(cls):
        raise NotImplementedError('Implement in subclass')

    @classmethod
    def _query(cls):
        return cls._session().query(cls)

    @classmethod
    def _new_instance(cls, model, *args, **kwargs):
        return cls._save_instance(model(*args, **kwargs))

    @classmethod
    def _save_instance(cls, instance):
        cls._session().add(instance)
        if cls.COMMIT_SESSION:
            cls._session().commit()
            cls._session().flush()
        else:
            cls._flush()
        return instance

    @classmethod
    def _flush(cls):
        try:
            cls._session().flush()
        except AssertionError:
            if transaction:
                with transaction.manager as manager:
                    manager.commit()
            else:
                cls._session().commit()

    def save(self):
        self._save_instance(self)


class SQLAlchemyUserMixin(SQLAlchemyMixin, UserMixin):
    """Social Auth association model"""
    __tablename__ = 'social_auth_usersocialauth'
    __table_args__ = (UniqueConstraint('provider', 'uid'),)
    id = Column(Integer, primary_key=True)
    provider = Column(String(32))
    uid = None
    user_id = None
    user = None

    @declared_attr
    def extra_data(cls):
        return Column(MutableDict.as_mutable(JSONType))

    @classmethod
    def changed(cls, user):
        cls._save_instance(user)

    def set_extra_data(self, extra_data=None):
        if super(SQLAlchemyUserMixin, self).set_extra_data(extra_data):
            self._save_instance(self)

    @classmethod
    def allowed_to_disconnect(cls, user, backend_name, association_id=None):
        if association_id is not None:
            qs = cls._query().filter(cls.id != association_id)
        else:
            qs = cls._query().filter(cls.provider != backend_name)
        qs = qs.filter(cls.user == user)

        if hasattr(user, 'has_usable_password'):  # TODO
            valid_password = user.has_usable_password()
        else:
            valid_password = True
        return valid_password or qs.count() > 0

    @classmethod
    def disconnect(cls, entry):
        cls._session().delete(entry)
        cls._flush()

    @classmethod
    def user_query(cls):
        return cls._session().query(cls.user_model())

    @classmethod
    def user_exists(cls, *args, **kwargs):
        """
        Return True/False if a User instance exists with the given arguments.
        Arguments are directly passed to filter() manager method.
        """
        return cls.user_query().filter_by(*args, **kwargs).count() > 0

    @classmethod
    def get_username(cls, user):
        return getattr(user, 'username', None)

    @classmethod
    def create_user(cls, *args, **kwargs):
        return cls._new_instance(cls.user_model(), *args, **kwargs)

    @classmethod
    def get_user(cls, pk):
        return cls.user_query().get(pk)

    @classmethod
    def get_users_by_email(cls, email):
        return cls.user_query().filter_by(email=email)

    @classmethod
    def get_social_auth(cls, provider, uid):
        if not isinstance(uid, six.string_types):
            uid = str(uid)
        try:
            return cls._query().filter_by(provider=provider,
                                          uid=uid)[0]
        except IndexError:
            return None

    @classmethod
    def get_social_auth_for_user(cls, user, provider=None, id=None):
        qs = cls._query().filter_by(user_id=user.id)
        if provider:
            qs = qs.filter_by(provider=provider)
        if id:
            qs = qs.filter_by(id=id)
        return qs

    @classmethod
    def create_social_auth(cls, user, uid, provider):
        if not isinstance(uid, six.string_types):
            uid = str(uid)
        return cls._new_instance(cls, user=user, uid=uid, provider=provider)


class SQLAlchemyNonceMixin(SQLAlchemyMixin, NonceMixin):
    __tablename__ = 'social_auth_nonce'
    __table_args__ = (UniqueConstraint('server_url', 'timestamp', 'salt'),)
    id = Column(Integer, primary_key=True)
    server_url = Column(String(255))
    timestamp = Column(Integer)
    salt = Column(String(40))

    @classmethod
    def use(cls, server_url, timestamp, salt):
        kwargs = {'server_url': server_url, 'timestamp': timestamp,
                  'salt': salt}
        try:
            return cls._query().filter_by(**kwargs)[0]
        except IndexError:
            return cls._new_instance(cls, **kwargs)


class SQLAlchemyAssociationMixin(SQLAlchemyMixin, AssociationMixin):
    __tablename__ = 'social_auth_association'
    __table_args__ = (UniqueConstraint('server_url', 'handle'),)
    id = Column(Integer, primary_key=True)
    server_url = Column(String(255))
    handle = Column(String(255))
    secret = Column(String(255))  # base64 encoded
    issued = Column(Integer)
    lifetime = Column(Integer)
    assoc_type = Column(String(64))

    @classmethod
    def store(cls, server_url, association):
        # Don't use get_or_create because issued cannot be null
        try:
            assoc = cls._query().filter_by(server_url=server_url,
                                           handle=association.handle)[0]
        except IndexError:
            assoc = cls(server_url=server_url,
                        handle=association.handle)
        assoc.secret = base64.encodestring(association.secret).decode()
        assoc.issued = association.issued
        assoc.lifetime = association.lifetime
        assoc.assoc_type = association.assoc_type
        cls._save_instance(assoc)

    @classmethod
    def get(cls, *args, **kwargs):
        return cls._query().filter_by(*args, **kwargs)

    @classmethod
    def remove(cls, ids_to_delete):
        cls._query().filter(cls.id.in_(ids_to_delete)).delete(
            synchronize_session='fetch'
        )


class SQLAlchemyCodeMixin(SQLAlchemyMixin, CodeMixin):
    __tablename__ = 'social_auth_code'
    __table_args__ = (UniqueConstraint('code', 'email'),)
    id = Column(Integer, primary_key=True)
    email = Column(String(200))
    code = Column(String(32), index=True)

    @classmethod
    def get_code(cls, code):
        return cls._query().filter(cls.code == code).first()


class SQLAlchemyPartialMixin(SQLAlchemyMixin, PartialMixin):
    __tablename__ = 'social_auth_partial'
    id = Column(Integer, primary_key=True)
    token = Column(String(32), index=True)
    data = Column(MutableDict.as_mutable(JSONType))
    next_step = Column(Integer)
    backend = Column(String(32))

    @classmethod
    def load(cls, token):
        return cls._query().filter(cls.token == token).first()

    @classmethod
    def destroy(cls, token):
        partial = cls.load(token)
        if partial:
            cls._session().delete(partial)


class BaseSQLAlchemyStorage(BaseStorage):
    user = SQLAlchemyUserMixin
    nonce = SQLAlchemyNonceMixin
    association = SQLAlchemyAssociationMixin
    code = SQLAlchemyCodeMixin
    partial = SQLAlchemyPartialMixin

    @classmethod
    def is_integrity_error(cls, exception):
        return exception.__class__ is IntegrityError
