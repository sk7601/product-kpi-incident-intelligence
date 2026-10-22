from sqlalchemy import inspect

from product.database import Base, engine


def test_schema():
    db = engine("sqlite://")
    Base.metadata.create_all(db)
    assert len(inspect(db).get_table_names()) == 9
    Base.metadata.drop_all(db)
    db.dispose()
