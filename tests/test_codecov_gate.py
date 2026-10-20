#!/usr/bin/env python3
"""Codecov must have a floor and must not fail silently (#551).

The upload used to run with `fail_ci_if_error` unset and no `codecov.yml`, so
every upload failed with "Token required - not valid tokenless upload" while
the job stayed green and Codecov showed nothing at all. There is no
`CODECOV_TOKEN` secret in the repository; the action authenticates with the
workflow's OIDC token instead, which requires `id-token: write` on the test
job.

These tests pin the two properties that make coverage meaningful: an upload
failure fails the build, and the project/patch statuses have thresholds.
"""

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CODECOV_YML = REPO_ROOT / "codecov.yml"
CI = REPO_ROOT / ".github" / "workflows" / "ci.yml"


class TestCodecovConfiguration(unittest.TestCase):
    def test_the_floor_file_exists(self):
        self.assertTrue(CODECOV_YML.is_file(), "codecov.yml is missing")

    def test_project_and_patch_have_targets(self):
        text = CODECOV_YML.read_text(encoding="utf-8")
        self.assertIn("project:", text)
        self.assertIn("patch:", text)
        self.assertRegex(text, r"(?m)^\s+target:\s*auto\s*$")
        self.assertRegex(text, r"(?m)^\s+threshold:\s*1%\s*$")
        self.assertRegex(text, r"(?m)^\s+target:\s*80%\s*$")


class TestTheUploadCannotFailSilently(unittest.TestCase):
    def test_the_lint_job_grants_the_oidc_token(self):
        text = CI.read_text(encoding="utf-8")
        self.assertRegex(text, r"(?m)^\s+id-token:\s*write\s*$")

    def test_the_upload_step_is_strict_and_uses_oidc(self):
        text = CI.read_text(encoding="utf-8")
        self.assertIn("codecov/codecov-action@v5", text)
        self.assertRegex(text, r"(?m)^\s+use_oidc:\s*true\s*$")
        self.assertRegex(text, r"(?m)^\s+fail_ci_if_error:\s*true\s*$")
        self.assertNotIn(
            "codecov/codecov-action@v4",
            text,
            "v4 cannot authenticate with the workflow OIDC token",
        )

    def test_the_action_options_belong_to_the_upload_step(self):
        """The three options must be in one step, not scattered fragments."""
        text = CI.read_text(encoding="utf-8")
        step = re.search(r"- name: Upload to Codecov\n(.*?)(?=\n      - name:|\Z)", text, re.DOTALL)
        self.assertIsNotNone(step, "no 'Upload to Codecov' step")
        body = step.group(1)
        self.assertIn("use_oidc: true", body)
        self.assertIn("fail_ci_if_error: true", body)
        self.assertIn("codecov/codecov-action@v5", body)


if __name__ == "__main__":
    unittest.main()
