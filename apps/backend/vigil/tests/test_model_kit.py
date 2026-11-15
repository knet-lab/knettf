"""model-kit/base.py 是给模型方的接口副本，必须和平台的 vigil/detection/base.py 完全一致。"""

from pathlib import Path

from django.test import SimpleTestCase

ROOT = Path(__file__).resolve().parents[4]


class ModelKitTests(SimpleTestCase):
    def test_base_copy_in_sync(self):
        platform = (ROOT / "apps/backend/vigil/detection/base.py").read_text()
        kit = (ROOT / "model-kit/base.py").read_text()
        self.assertEqual(kit, platform, "接口变了：cp apps/backend/vigil/detection/base.py model-kit/base.py")
