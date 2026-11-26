"""tools/check_pr_shape.py on throwaway git repositories (no manuscript data)."""
import os
import subprocess
import sys
import tempfile
import unittest

TOOL = os.path.join(os.path.dirname(__file__), "..", "tools", "check_pr_shape.py")


class ShapeTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.git("init", "-q", "-b", "main")
        self.write("README", "x")
        self.commit("base")

    def tearDown(self):
        self.tmp.cleanup()

    def git(self, *a):
        return subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *a], cwd=self.tmp.name,
                              capture_output=True, text=True, check=True).stdout

    def write(self, name, text):
        fn = os.path.join(self.tmp.name, name)
        os.makedirs(os.path.dirname(fn) or self.tmp.name, exist_ok=True)
        open(fn, "w").write(text)

    def commit(self, msg):
        self.git("add", "-A")
        self.git("commit", "-q", "-m", msg)

    def check(self, *extra):
        r = subprocess.run([sys.executable, os.path.abspath(TOOL), "main", "--head", "pr", *extra],
                           cwd=self.tmp.name, capture_output=True, text=True)
        return r.returncode, r.stdout

    def test_stacked_branch_on_a_merged_experiment_is_one_experiment(self):
        self.git("checkout", "-q", "-b", "pr")
        self.write("experiments/A-1/me/experiment.json", "{}")
        self.commit("first")
        self.write("experiments/B-2/me/experiment.json", "{}")
        self.commit("second")
        # the first experiment is squash-merged to main separately
        self.git("checkout", "-q", "main")
        self.write("experiments/A-1/me/experiment.json", "{}")
        self.commit("squash of first")
        code, out = self.check("--list")
        self.assertEqual(code, 0, out)
        self.assertEqual(out.strip(), "experiments/B-2/me")

    def test_changed_copy_of_a_merged_experiment_still_counts(self):
        self.write("experiments/A-1/me/experiment.json", "{}")
        self.commit("merged")
        self.git("checkout", "-q", "-b", "pr")
        self.write("experiments/A-1/me/experiment.json", '{"edited": 1}')
        self.write("experiments/B-2/me/experiment.json", "{}")
        self.commit("two")
        code, out = self.check()
        self.assertEqual(code, 1)
        self.assertIn("split it into one pull request per directory: experiments/A-1/me, experiments/B-2/me", out)

    def test_code_files_are_still_refused(self):
        self.git("checkout", "-q", "-b", "pr")
        self.write("vs/x.py", "pass")
        self.write("experiments/B-2/me/experiment.json", "{}")
        self.commit("code")
        code, out = self.check()
        self.assertEqual(code, 1)
        self.assertIn("not allowed in an experiment PR: A vs/x.py", out)


if __name__ == "__main__":
    unittest.main()
