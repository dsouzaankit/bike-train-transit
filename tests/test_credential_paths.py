# -*- coding: utf-8 -*-
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import credential_paths, local_deploy, transit_app  # noqa: E402


class CredentialPathsTests(unittest.TestCase):
    def test_load_json_credential_from_project_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            lib_dir = os.path.join(tmp, "lib")
            os.makedirs(lib_dir)
            path = os.path.join(tmp, "transit_credentials.json")
            with open(path, "w", encoding="utf-8") as fh:
                json.dump({"api_key": "test-key-123"}, fh)
            with mock.patch.object(credential_paths, "credential_roots", return_value=[tmp]):
                data = credential_paths.load_json_credential("transit_credentials.json")
            self.assertEqual(data.get("api_key"), "test-key-123")

    def test_credential_roots_skips_none_app_root(self):
        with mock.patch(
            "lib.log_paths.app_root",
            return_value=None,
        ):
            roots = credential_paths.credential_roots()
        self.assertTrue(all(isinstance(r, str) and r for r in roots))

    def test_load_json_credential_ignores_none_roots(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "transit_credentials.json")
            with open(path, "w", encoding="utf-8") as fh:
                json.dump({"api_key": "ok"}, fh)
            with mock.patch.object(
                credential_paths,
                "credential_roots",
                return_value=[None, "", tmp],
            ):
                data = credential_paths.load_json_credential("transit_credentials.json")
            self.assertEqual(data.get("api_key"), "ok")

    def test_transit_has_api_key_reads_credential_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "transit_credentials.json")
            with open(path, "w", encoding="utf-8") as fh:
                json.dump({"apiKey": "from-file"}, fh)
            with mock.patch.object(credential_paths, "credential_roots", return_value=[tmp]):
                with mock.patch.dict(os.environ, {}, clear=True):
                    self.assertTrue(transit_app.has_api_key())

    def test_transit_has_api_key_false_when_roots_include_none(self):
        with mock.patch.object(
            credential_paths,
            "credential_roots",
            return_value=[None],
        ):
            with mock.patch.dict(os.environ, {}, clear=True):
                self.assertFalse(transit_app.has_api_key())


class LocalDeployCredentialTests(unittest.TestCase):
    def test_deploy_copies_transit_credentials(self):
        with tempfile.TemporaryDirectory() as source:
            with tempfile.TemporaryDirectory() as documents:
                os.makedirs(os.path.join(source, "lib"))
                with open(os.path.join(source, local_deploy.MAIN_SCRIPT), "w") as fh:
                    fh.write("# stub\n")
                cred = os.path.join(source, "transit_credentials.json")
                with open(cred, "w", encoding="utf-8") as fh:
                    json.dump({"api_key": "phone-key"}, fh)
                dest_name = local_deploy.LOCAL_DIR_NAME
                dest_root = os.path.join(documents, dest_name)
                with mock.patch.object(
                    local_deploy,
                    "local_app_dir",
                    return_value=dest_root,
                ):
                    local_deploy.deploy_local_app(source)
                deployed = os.path.join(dest_root, "transit_credentials.json")
                self.assertTrue(os.path.isfile(deployed))
                with open(deployed, "r", encoding="utf-8") as fh:
                    self.assertEqual(json.load(fh)["api_key"], "phone-key")


if __name__ == "__main__":
    unittest.main(verbosity=2)
