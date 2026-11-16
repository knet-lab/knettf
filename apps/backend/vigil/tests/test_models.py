"""
上线门槛：settings.VIGIL_MODELS 里启用的每个模型都要能从仓库里的 files/ 加载，
并且输入输出符合接口（与 manage.py check_model 相同的规则）。CI 不通过就不会自动部署。
"""

from django.conf import settings
from django.test import SimpleTestCase

from vigil.detection.registry import load_model
from vigil.management.commands.check_model import check


class EnabledModelsTests(SimpleTestCase):
    def test_enabled_models_load_and_match_interface(self):
        self.assertTrue(settings.VIGIL_MODELS, "VIGIL_MODELS 为空：至少启用一个模型")
        for path in settings.VIGIL_MODELS:
            with self.subTest(model=path):
                self.assertEqual(check(load_model(path)), [])
