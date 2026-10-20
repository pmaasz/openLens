"""Release automation contract for the Windows/macOS executables (#35).

Release Please creates releases with the repository GITHUB_TOKEN, and GitHub
deliberately does not start another workflow from those events. The release
workflow therefore has to be called by the Release Please workflow itself; a
`release: published` trigger alone silently produced no executables (v0.4.0
had none).

These tests read the workflow YAML and pin that contract, the platform matrix,
and the macOS app-bundle packaging. They are intentionally structural: the
actual builds only run on GitHub-hosted Windows/macOS runners.
"""

import pathlib
import unittest

try:
    import yaml

    YAML_AVAILABLE = True
except ImportError:  # pragma: no cover - pre-commit pulls PyYAML in
    yaml = None
    YAML_AVAILABLE = False

WORKFLOWS = pathlib.Path(__file__).resolve().parents[1] / ".github" / "workflows"


def _load(name):
    with (WORKFLOWS / name).open(encoding="utf-8") as handle:
        document = yaml.safe_load(handle)
    # PyYAML resolves the YAML 1.1 boolean `on` as a key. Normalise it back to
    # the string used by GitHub Actions.
    if True in document:
        document["on"] = document.pop(True)
    return document


def _checkout(job):
    return next(
        step for step in job["steps"] if str(step.get("uses", "")).startswith("actions/checkout")
    )


def _step_using(job, action):
    return next(step for step in job["steps"] if str(step.get("uses", "")).startswith(action))


@unittest.skipUnless(YAML_AVAILABLE, "PyYAML not available")
class TestReleaseWorkflow(unittest.TestCase):
    def setUp(self):
        self.release = _load("release.yaml")
        self.release_please = _load("release-please.yaml")

    def test_release_please_calls_the_release_workflow(self):
        jobs = self.release_please["jobs"]
        publisher = jobs["release-please"]
        self.assertIn("release_created", publisher["outputs"])
        self.assertIn("tag_name", publisher["outputs"])

        caller = jobs["release"]
        self.assertEqual(caller["uses"], "./.github/workflows/release.yaml")
        self.assertIn("release_created", caller["if"])
        self.assertEqual(
            caller["with"]["tag_name"],
            "${{ needs.release-please.outputs.tag_name }}",
        )

    def test_release_workflow_is_callable_and_accepts_a_tag(self):
        triggers = self.release["on"]
        self.assertIn("workflow_call", triggers)
        self.assertIn("tag_name", triggers["workflow_call"]["inputs"])
        self.assertIn("openlens-v*", triggers["push"]["tags"])

    def test_release_jobs_check_out_the_release_tag(self):
        for job_name in ("publish", "executable"):
            checkout = _checkout(self.release["jobs"][job_name])
            self.assertIn("RELEASE_TAG", checkout["with"]["ref"])

    def test_executables_are_built_for_windows_and_both_macos_arches(self):
        matrix = self.release["jobs"]["executable"]["strategy"]["matrix"]["include"]
        runners = {entry["os"] for entry in matrix}
        suffixes = {entry["suffix"] for entry in matrix}

        self.assertIn("windows-latest", runners)
        self.assertIn("macos-latest", runners)
        self.assertIn("macos-15-intel", runners)
        self.assertIn("Windows", suffixes)
        self.assertIn("macOS-arm64", suffixes)
        self.assertIn("macOS-x64", suffixes)

    def test_macos_app_bundle_is_zipped_before_attachment(self):
        job = self.release["jobs"]["executable"]
        package = next(
            step for step in job["steps"] if step.get("name") == "Package release artifact"
        )
        run = package["run"]

        self.assertIn("ditto", run)
        self.assertIn(".zip", run)
        self.assertIn("macOS", run)

        attach = _step_using(job, "softprops/action-gh-release")
        self.assertEqual(attach["with"]["files"], "package/*")
        self.assertIn("RELEASE_TAG", attach["if"])

    def test_pypi_publish_requires_explicit_enablement(self):
        publish = self.release["jobs"]["publish"]
        pypi = _step_using(publish, "pypa/gh-action-pypi-publish")
        self.assertIn("vars.PYPI_PUBLISH_ENABLED", pypi["if"])

        # The wheel and sdist must still attach even when PyPI is not ours to
        # publish to (the PyPI `openlens` project belongs to someone else).
        attach = _step_using(publish, "softprops/action-gh-release")
        self.assertEqual(attach["with"]["files"], "dist/*")

    def test_manual_dispatch_can_build_without_touching_a_release(self):
        triggers = self.release["on"]
        self.assertIn("workflow_dispatch", triggers)

        executable = self.release["jobs"]["executable"]
        upload = _step_using(executable, "actions/upload-artifact")
        self.assertIn("RELEASE_TAG", upload["if"])
        self.assertEqual(upload["with"]["path"], "package/*")

        self.assertIn("workflow_dispatch", self.release["jobs"]["publish"]["if"])


if __name__ == "__main__":
    unittest.main()
