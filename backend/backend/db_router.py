class AppRouter:
    ROUTES = {
        'kcore': 'default',
        'vigil': 'vigil',
        'autotf': 'autotf',
    }

    def db_for_read(self, model, **hints):
        return self.ROUTES.get(model._meta.app_label)

    def db_for_write(self, model, **hints):
        return self.ROUTES.get(model._meta.app_label)

    def allow_relation(self, obj1, obj2, **hints):
        return True

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        if app_label in self.ROUTES:
            return db == self.ROUTES[app_label]
        return db == 'default'
