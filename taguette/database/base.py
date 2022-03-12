import prometheus_client


PROM_DATABASE_VERSION = prometheus_client.Gauge('database_version',
                                                "Database version",
                                                ['version'])
PROM_COMMAND = prometheus_client.Counter('commands_total',
                                         "Number of commands",
                                         ['type'])
