from peewee import CharField, TextField
from . import BaseModel

class EventNote(BaseModel):
    name = CharField(null=False, unique=True)
    note = TextField(null=False)
