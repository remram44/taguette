from prometheus_client import REGISTRY
from prometheus_client.metrics_core import GaugeMetricFamily
import sqlalchemy
from sqlalchemy.sql import functions

from . import database


class Collector(object):
    def __init__(self, DBSession):
        self.DBSession = DBSession

    def collect(self):
        db = self.DBSession()

        documents = GaugeMetricFamily(
            'documents',
            "Total number of documents",
        )

        (nb_documents,), = db.execute(
            sqlalchemy.select([
                functions.count(),
            ]).select_from(database.Document.__table__)
        )
        documents.add_metric([], nb_documents)

        users = GaugeMetricFamily(
            'users',
            "Total number of users",
        )

        (nb_users,), = db.execute(
            sqlalchemy.select([
                functions.count(),
            ]).select_from(database.User.__table__)
        )
        users.add_metric([], nb_users)

        projects = GaugeMetricFamily(
            'projects',
            "Total number of projects",
        )

        (nb_projects,), = db.execute(
            sqlalchemy.select([
                functions.count(),
            ]).select_from(database.Project.__table__)
        )
        projects.add_metric([], nb_projects)

        return [documents, users, projects]


def init(DBSession):
    REGISTRY.register(Collector(DBSession))
