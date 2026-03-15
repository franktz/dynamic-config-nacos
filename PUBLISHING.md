# Publishing Checklist

This package now has the main publishing metadata prepared for a PyPI release.

Primary author: FrankTang (<franktz2003@gmail.com>)

## Current Release Metadata

1. PyPI distribution name

Current package name: `dynamic-config-nacos`

The original name `dynamic-config` is already registered on PyPI, so
`dynamic-config-nacos` is used instead to avoid naming conflicts.

2. License

Chosen license: `MIT`

The repository should include a `LICENSE` file with the full MIT license text.

3. Author or maintainer metadata

Current author and maintainer metadata:

- FrankTang
- franktz2003@gmail.com

4. Project URLs

- Homepage: <https://github.com/franktz/dynamic-config-nacos>
- Repository: <https://github.com/franktz/dynamic-config-nacos>
- Documentation: <https://github.com/franktz/dynamic-config-nacos>
- Issues: <https://github.com/franktz/dynamic-config-nacos/issues>

5. Project status and audience

- Development Status: `Beta`
- Intended Audience: `Developers`

## Publishing Methods

### Option 1: PyPI API Token

This is the simplest way to publish manually from your local machine.

How it works:

- You create an API token in your PyPI account settings
- PyPI gives you a token string that usually starts with `pypi-`
- You store that token in an environment variable such as `PYPI_TOKEN`
- `twine upload` uses the token instead of your username and password

This project's upload scripts already support that flow.

### Option 2: Trusted Publisher

This is usually the better long-term setup for automated releases.

How it works:

- You connect PyPI to a GitHub Actions workflow
- GitHub uses OIDC to prove the workflow identity to PyPI
- No long-lived PyPI token needs to be stored in repository secrets

For a first release, the easiest path is usually:

1. Publish manually with a PyPI API token
2. Verify that the package metadata and install experience look correct
3. Set up Trusted Publisher later if you want automated releases

This repository is now prepared for that flow with:

- workflow file: `.github/workflows/publish.yml`
- GitHub environment name: `pypi`
- PyPI project URL: <https://pypi.org/project/dynamic-config-nacos/>

## Trusted Publisher Setup For This Repository

To enable GitHub Actions Trusted Publishing on PyPI, add a GitHub publisher for
the existing PyPI project with these exact values:

- PyPI project: `dynamic-config-nacos`
- Repository owner: `franktz`
- Repository name: `dynamic-config-nacos`
- Workflow filename: `publish.yml`
- GitHub environment name: `pypi`

After that, the workflow in `.github/workflows/publish.yml` can publish to PyPI
without storing a `PYPI_TOKEN` secret in GitHub.

Recommended GitHub-side setup:

1. Create a repository environment named `pypi`
2. Optionally require manual approval for that environment
3. Create GitHub Releases when you want to publish automatically

The workflow currently supports two triggers:

- manual run via `workflow_dispatch`
- automatic publish when a GitHub Release is marked as published

## Files Already Updated

- `pyproject.toml`
- `README.md`
- `README.zh-CN.md`
- `how-to-use.md`
- `how-to-use.zh-CN.md`
- `LICENSE`

## Local Release Flow

1. Install release tooling

```bash
python3.12 -m pip install -e .[release]
```

2. Build distributions

```bash
bash scripts/build_dist.sh
```

3. Validate metadata and README rendering

```bash
bash scripts/check_dist.sh
```

4. Upload to TestPyPI first

```bash
bash scripts/upload_testpypi.sh
```

5. Upload to PyPI only after TestPyPI looks correct

```bash
bash scripts/upload_pypi.sh
```

## Environment Variables Used by Upload Scripts

Token-based upload expects:

- `PYPI_TOKEN`
- `TEST_PYPI_TOKEN`

## Trusted Publisher Notes

According to PyPI's Trusted Publisher documentation, GitHub Actions publishing
can use OIDC and does not require storing a long-lived API token in repository
secrets.

If you plan to use GitHub Actions, PyPI typically needs:

- repository owner
- repository name
- workflow filename
- an optional environment name such as `pypi`

References:

- [PyPI Trusted Publishers](https://docs.pypi.org/trusted-publishers/)
- [Adding a Trusted Publisher](https://docs.pypi.org/trusted-publishers/adding-a-publisher/)
- [PyPI Help](https://pypi.org/help/)
