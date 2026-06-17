from .settings import *  # noqa: F401, F403

# Allow all apps to migrate into all databases so cross-DB FKs
# (e.g. kcore_user referenced by autotf_terraformconfig) resolve in tests.
DATABASE_ROUTERS = ['backend.test_settings.AllDbRouter']


class AllDbRouter:
    _ROUTES = {'vigil': 'vigil', 'autotf': 'autotf'}

    def db_for_read(self, model, **hints):
        return self._ROUTES.get(model._meta.app_label)

    def db_for_write(self, model, **hints):
        return self._ROUTES.get(model._meta.app_label)

    def allow_relation(self, obj1, obj2, **hints):
        return True

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        # vigil migrations contain PostgreSQL-specific SQL; keep them on their own DB only.
        if app_label == 'vigil':
            return db == 'vigil'
        # autotf must migrate to autotf; also mirror kcore/auth/contenttypes there
        # so that cross-DB FK references to kcore_user resolve in SQLite tests.
        if db == 'autotf':
            return app_label in ('autotf', 'kcore', 'auth', 'contenttypes')
        # default DB: everything except vigil and autotf
        if db == 'default':
            return app_label not in ('vigil', 'autotf')
        return False
