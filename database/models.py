from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import MetaData, Integer, String, DateTime, Date, Time, Boolean, CheckConstraint

from enum import Enum
from datetime import date, time, datetime
from zoneinfo import ZoneInfo

est = ZoneInfo('America/New_York')

metadata = MetaData()

class Base(DeclarativeBase):
    metadata = metadata

class Interval(Enum):
    NEVER=0
    DAILY=1
    WEEKLY=2
    MONTHLY=3

class Task(Base):
    __tablename__ = 'task'
    __table_args__ = (
        CheckConstraint('recurring_time >= 0 AND recurring_time <= 3', name='interval_constraint'),
    )
    
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(String)
    recurring_time: Mapped[int] = mapped_column(Integer, nullable=False, default=Interval.NEVER)
    due_date: Mapped[date] = mapped_column(Date, nullable=True) # if recurring time is not NEVER, then this represents first day
    due_time: Mapped[time] = mapped_column(Time, nullable=True)
    time_cost: Mapped[int] = mapped_column(Integer, nullable=False) # number of minutes to finish this task
    reminder: Mapped[int] = mapped_column(Integer, default=0) # number of days before due date for reminder
    completed: Mapped[bool] = mapped_column(Boolean, default=False)
    created: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=lambda:datetime.now(est), onupdate=lambda:datetime.now(est))
    
    def to_dict(self):
        temp = {
            "id": self.id,
            "title": self.title,
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "due_time": self.due_time.isoformat() if self.due_time else None,
            "time_cost": self.time_cost
        }
        return temp
    
    @property
    def get_recurring_name(self):
        return Interval(self.recurring_time).name