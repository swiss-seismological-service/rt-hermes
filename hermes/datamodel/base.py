import enum
import functools
import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, Float, Integer, MetaData, String
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.orm import DeclarativeBase


class ORMBase(DeclarativeBase, AsyncAttrs):
    """
    Base class for all ORM
    """
    metadata = MetaData(naming_convention={
        "ix": "ix_%(column_0_label)s",
        "uq": "uq_%(table_name)s_%(column_0_name)s",
        "ck": "ck_%(table_name)s_`%(constraint_name)s`",
        "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
        "pk": "pk_%(table_name)s"
    })
    oid = Column(UUID, primary_key=True, default=uuid.uuid4)

    @declared_attr
    def __tablename__(cls):
        if cls.__name__.endswith('Table'):
            return cls.__name__[:-len('Table')].rstrip().lower()
        return cls.__name__.lower()


def EpochMixin(name: str, epoch_type: str | None = None,
               column_prefix: str = '') -> type[object]:
    """
    Mixin factory for common Epoch types from QuakeML.

    Epoch types provide the fields `starttime` and `endtime`, optionally
    with a prefix.

    Args:
        name: Name of the class returned.
        epoch_type: Type of the epoch to be returned. Valid values
            are `None`, `default`, `open`, and `finite`.
        column_prefix: Prefix used for DB columns. Capital
            letters are converted to lowercase.

    Returns:
        A mixin class with the fields `starttime` and `endtime`.
    """

    # Add underscore between prefix and column name, lowercase prefix.
    if column_prefix != '':
        column_prefix = '%s_' % column_prefix
    column_prefix = column_prefix.lower()

    class Boundary(enum.Enum):
        LEFT = enum.auto()
        RIGHT = enum.auto()

    def create_datetime(boundary, column_prefix, **kwargs):

        def _make_datetime(boundary, **kwargs):

            if boundary is Boundary.LEFT:
                field_name = 'starttime'
            elif boundary is Boundary.RIGHT:
                field_name = 'endtime'
            else:
                raise ValueError('Invalid boundary: {!r}.'.format(boundary))

            @declared_attr
            def _datetime(cls):
                return Column(
                    '%s%s' %
                    (column_prefix,
                     field_name),
                    TIMESTAMP(precision=0),
                    **kwargs)

            return _datetime

        return _make_datetime(boundary, **kwargs)

    if epoch_type is None or epoch_type == 'default':
        _func_map = (('starttime', create_datetime(Boundary.LEFT,
                                                   column_prefix,
                                                   nullable=False)),
                     ('endtime', create_datetime(Boundary.RIGHT,
                                                 column_prefix)))
    elif epoch_type == 'open':
        _func_map = (('starttime', create_datetime(Boundary.LEFT,
                                                   column_prefix)),
                     ('endtime', create_datetime(Boundary.RIGHT,
                                                 column_prefix)))
    elif epoch_type == 'finite':
        _func_map = (('starttime', create_datetime(Boundary.LEFT,
                                                   column_prefix,
                                                   nullable=False)),
                     ('endtime', create_datetime(Boundary.RIGHT,
                                                 column_prefix,
                                                 nullable=False)))
    else:
        raise ValueError('Invalid epoch_type: {!r}.'.format(epoch_type))

    def __dict__(func_map, attr_prefix):

        return {'{}{}'.format(attr_prefix, attr_name): attr
                for attr_name, attr in func_map}

    return type(name, (object,), __dict__(_func_map, column_prefix))


DefaultEpochMixin = EpochMixin(name='DefaultEpochMixin', epoch_type='default')
OpenEpochMixin = EpochMixin(name='OpenEpochMixin', epoch_type='open')
FiniteEpochMixin = EpochMixin(name='FiniteEpochMixin', epoch_type='finite')


class NameMixin(object):
    """
    SQLAlchemy mixin providing a general purpose unique
    and not nullable `name` attribute.
    """
    name = Column(String, unique=True, nullable=False)


class CreationInfoMixin(object):
    """
    SQLAlchemy mixin emulating type `CreationInfo` from QuakeML.
    """
    creationinfo_author = Column(String)
    creationinfo_agencyid = Column(String)
    creationinfo_creationtime = Column(
        TIMESTAMP(precision=0),
        default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    creationinfo_version = Column(String)


def QuantityMixin(name: str,
                  quantity_type: str,
                  column_prefix: str | None = None,
                  optional: bool = True,
                  index: bool = False):
    """
    Mixin factory for common `Quantity` types from QuakeML.

    Quantity types provide the fields:
    - `value`
    - `uncertainty`
    - `loweruncertainty`
    - `upperuncertainty`
    - `confidencelevel`

    Note, that a `column_prefix` may be prepended.

    Args:
        name:           Name of the class returned.
        quantity_type:  Type of the quantity to be returned. Valid values
                        are `int`, `real` or rather `float` and `time`.
        column_prefix:  Prefix used for DB columns. If `None`, then
                        `name` with an appended underscore `_` is used.
                        Capital Letters are converted to lowercase.
        optional:       Flag making the `value` field optional.

    The usage of `QuantityMixin` is illustrated below:

    Examples:
        Define a ORM mapping using the Quantity mixin factory:

        ```python
        class FooBar(QuantityMixin('foo', 'int'),
                     QuantityMixin('bar', 'real'),
                     ORMBase):

            def __repr__(self):
                return '<FooBar (foo_value=%d, bar_value=%f)>' % (
                    self.foo_value, self.bar_value)

        # create instance of "FooBar"
        foobar = FooBar(foo_value=1, bar_value=2)
        ```
    """

    if column_prefix is None:
        column_prefix = '%s_' % name

    column_prefix = column_prefix.lower()

    def create_value(quantity_type, column_prefix, optional):

        def _make_value(sql_type, column_prefix, optional):

            @declared_attr
            def _value(cls):
                return Column('%svalue' % column_prefix, sql_type,
                              nullable=optional, index=index)

            return _value

        if quantity_type == 'int':
            return _make_value(Integer, column_prefix, optional)
        elif quantity_type in ('real', 'float'):
            return _make_value(Float, column_prefix, optional)
        elif quantity_type == 'time':
            return _make_value(TIMESTAMP, column_prefix, optional)

        raise ValueError('Invalid quantity_type: {}'.format(quantity_type))

    @declared_attr
    def _uncertainty(cls):
        return Column('%suncertainty' % column_prefix, Float)

    @declared_attr
    def _lower_uncertainty(cls):
        return Column('%sloweruncertainty' % column_prefix, Float)

    @declared_attr
    def _upper_uncertainty(cls):
        return Column('%supperuncertainty' % column_prefix, Float)

    @declared_attr
    def _confidence_level(cls):
        return Column('%sconfidencelevel' % column_prefix, Float)

    _func_map = (('value',
                  create_value(quantity_type, column_prefix, optional)),
                 ('uncertainty', _uncertainty),
                 ('loweruncertainty', _lower_uncertainty),
                 ('upperuncertainty', _upper_uncertainty),
                 ('confidencelevel', _confidence_level),
                 )

    def __dict__(func_map, attr_prefix):

        return {'{}{}'.format(attr_prefix, attr_name): attr
                for attr_name, attr in func_map}

    return type(name, (object,), __dict__(_func_map, column_prefix))


RealQuantityMixin = functools.partial(QuantityMixin,
                                      quantity_type='float')
IntegerQuantityMixin = functools.partial(QuantityMixin,
                                         quantity_type='int')
TimeQuantityMixin = functools.partial(QuantityMixin,
                                      quantity_type='time')
ObservationEpochMixin = EpochMixin(name='observation',
                                   column_prefix='observation',
                                   epoch_type='open')
ScheduleEpochMixin = EpochMixin(name='schedule',
                                column_prefix='schedule',
                                epoch_type='open')
ForecastEpochMixin = EpochMixin(name='forecast',
                                column_prefix='forecast',
                                epoch_type='open')
