# Contributors

Thank you to all who contribute to MCP Zileo RAG.

## Organizations

### Assistance Micro Design
- **GitHub**: https://github.com/assistance-micro-design
- **Website**: https://www.assistancemicrodesign.net/
- **Role**: Project Owner and Primary Maintainer

## Individual Contributors

| Name | GitHub | Contributions |
|------|--------|---------------|
| *Your name here* | *@username* | *Description* |

## How to Contribute

We welcome contributions. Please see:
- [README.md](README.md) for project overview and setup
- [docs/](docs/) for architecture and API references
- [SECURITY.md](SECURITY.md) for security reporting
- [.github/PULL_REQUEST_TEMPLATE.md](.github/PULL_REQUEST_TEMPLATE.md) for the PR checklist

### Development requirements

- Python 3.11+
- Docker & Docker Compose (for Qdrant)
- A Mistral API key (for embeddings + OCR tests)

### Validation before PR

```bash
ruff check --fix src/ tests/
ruff format src/ tests/
mypy src/
pytest --cov=src --cov-fail-under=80
```

### Adding Yourself as a Contributor

1. Fork the repository
2. Add your name to this file in your PR
3. Submit a Pull Request

## License

All contributions are made under the [GNU Affero General Public License v3.0 or later](LICENSE). By submitting a contribution, you agree to license your work under these terms.
