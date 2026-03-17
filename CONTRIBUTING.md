# Contributing to `protocollab`

First off, thank you for considering contributing to `protocollab`! It's people like you that make `protocollab` such a great tool.

## Code of Conduct

This project and everyone participating in it is governed by our [Code of Conduct](CODE_OF_CONDUCT.md). By participating, you are expected to uphold this code.

## How Can I Contribute?

### Reporting Bugs

- Ensure the bug was not already reported by searching on GitHub under [Issues](https://github.com/yourname/protocollab/issues).
- If you're unable to find an open issue addressing the problem, [open a new one](https://github.com/yourname/protocollab/issues/new). Be sure to include a **title and clear description**, as much relevant information as possible, and a **code sample** or an **executable test case** demonstrating the expected behavior that is not occurring.

### Suggesting Enhancements

- Open a new issue with a clear title and detailed description of the proposed enhancement.
- Explain why this enhancement would be useful to most users.
- If possible, provide a sketch of how it might be implemented.

### Pull Requests

- Fill in the required template.
- Do not include issue numbers in the PR title.
- Follow the [style guides](#style-guides).
- Include appropriate tests.
- Document new code.
- End all files with a newline.

## Style Guides

### Git Commit Messages

- Use the present tense ("Add feature" not "Added feature").
- Use the imperative mood ("Move cursor to..." not "Moves cursor to...").
- Limit the first line to 72 characters or less.
- Reference issues and pull requests liberally after the first line.

### Python Style Guide

- Follow [PEP 8](https://www.python.org/dev/peps/pep-0008/).
- Use [Black](https://github.com/psf/black) with default settings for code formatting.
- Use [isort](https://github.com/PyCQA/isort) to sort imports.
- Use [flake8](https://flake8.pycqa.org/) for linting.
- Use [mypy](http://mypy-lang.org/) for static type checking. All public APIs must have type annotations.
- Write docstrings in [Google style](https://google.github.io/styleguide/pyguide.html#38-comments-and-docstrings).

### Testing

- Write tests for all new features and bug fixes.
- Run the existing test suite with `pytest` to ensure no regressions.
- Aim for at least 80% code coverage. Pull requests that decrease coverage significantly will be asked to improve tests.

### Documentation

- Update the `docs/` folder (MkDocs) for any user-facing changes.
- Use clear, concise language.
- Include examples where appropriate.

## Development Setup

1. Fork the repository and clone your fork.
2. Install [Poetry](https://python-poetry.org/): `pip install poetry`
3. Install dependencies: `poetry install`
4. Install pre-commit hooks: `poetry run pre-commit install`
5. Run tests: `poetry run pytest`

## Security Notes

Because security is a core feature of `protocollab`, any changes that affect the loading or processing of YAML must be reviewed with extra care. If you discover a potential security vulnerability, please do NOT open an issue; instead, follow the instructions in our [SECURITY policy](SECURITY.md).

## Thank You!

Your contributions to open source, large or small, make projects like this possible. Thank you for taking the time to contribute.