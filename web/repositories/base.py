from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from hermes.datamodel.base import ORMBase
from hermes.schemas.base import Model


def async_repository_factory(model: Model, orm_model: ORMBase):

    class AsyncRepositoryBase:
        model: Model
        orm_model: ORMBase

        @classmethod
        async def get_by_id(cls, session: AsyncSession, oid: str | UUID
                            ) -> Model:
            q = select(cls.orm_model).where(
                getattr(cls.orm_model, 'oid') == oid)
            result = await session.execute(q)
            result = result.unique().scalar_one_or_none()
            return cls.model.model_validate(result) if result else None

        @classmethod
        async def get_all(cls, session: AsyncSession) -> list:
            q = select(cls.orm_model)
            result = await session.execute(q)
            result = result.unique().scalars().all()
            return [cls.model.model_validate(row) for row in result]

    AsyncRepositoryBase.model = model
    AsyncRepositoryBase.orm_model = orm_model

    return AsyncRepositoryBase
