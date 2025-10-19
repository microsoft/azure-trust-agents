# Contributing to Azure Trust and Compliance Multi-Agents Hack

You can contribute to the Azure Trust and Compliance Multi-Agents Hack with issues and pull requests (PRs). Simply filing issues for problems you encounter is a great way to contribute. Contributing code is greatly appreciated.

This project leverages the **Microsoft Agent Framework** for building enterprise-grade compliance agents, and we follow similar contribution patterns and standards.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Reporting Issues](#reporting-issues)
- [Getting Started](#getting-started)
- [Development Environment](#development-environment)
- [Project Structure](#project-structure)
- [Contributing Changes](#contributing-changes)
- [Submitting Changes](#submitting-changes)
- [Community](#community)

## Code of Conduct

This project has adopted the [Microsoft Open Source Code of Conduct](https://opensource.microsoft.com/codeofconduct/). Please read our [Code of Conduct](CODE_OF_CONDUCT.md) before contributing.

## Reporting Issues

We always welcome bug reports and overall feedback. Here are a few tips on how you can make reporting your issue as effective as possible.

### Where to Report

- **Bugs & Issues**: File a [GitHub issue](../../issues) for problems you encounter
- **Feature Requests**: Use GitHub issues with the `enhancement` label  
- **Questions**: Use GitHub Discussions for questions and community support

### Writing a Good Bug Report

Good bug reports make it easier for maintainers to verify and root cause the underlying problem. The better a bug report, the faster the problem will be resolved. Ideally, a bug report should contain the following information:

- A high-level description of the problem
- A _minimal reproduction_, i.e. the smallest size of code/configuration required to reproduce the wrong behavior
- A description of the _expected behavior_, contrasted with the _actual behavior_ observed
- Information on the environment: OS/distribution, Python version, Azure regions, etc.
- Additional information, e.g. Is it a regression from previous versions? Are there any known workarounds?

## Getting Started

### Prerequisites

Before you begin, ensure you have the following:

- **GitHub account** with access to GitHub Codespaces and GitHub Copilot
- **Azure subscription** with Owner rights
- **Familiarity with:**
  - Generative AI solutions and Azure Services
  - Microsoft Agent Framework concepts
  - Azure AI Foundry and OpenTelemetry (for observability contributions)

**Note:** All technical environment prerequisites (Python version, dependencies, development tools, Azure CLI, etc.) are automatically configured in the GitHub Codespaces environment. You don't need to install or configure these locally.

## Development Environment

### Using GitHub Codespaces (Required)

**⚠️ Important: This project only supports development through GitHub Codespaces. Issues encountered on local development environments will not be supported.**

1. Fork the repository
2. Open your fork in GitHub Codespaces
3. The development environment will be automatically configured with all necessary dependencies

The Codespaces environment includes:
- Pre-configured Python environment with all dependencies
- Azure CLI and necessary tools
- Proper VS Code extensions and settings
- Container environment optimized for the hackathon challenges

### Local Development Setup (Not Supported)

**⚠️ Local development is not supported for this project.** Please use GitHub Codespaces for all development work.

If you attempt local development, you may encounter:
- Environment configuration issues
- Dependency conflicts
- Azure service connectivity problems
- Missing development tools and extensions

**All issues related to local development environments will be closed without support.** The project is designed to work seamlessly in the provided Codespaces environment.

## Project Structure

The project is organized into progressive challenges:

```
azure-trust-agents/
├── challenge-0/          # Setup & Data Ingestion
│   ├── data/            # Sample datasets (customers, transactions, regulations)
│   └── infra/           # Azure deployment templates
├── challenge-1/          # Microsoft Agent Framework
│   ├── agents/          # Core compliance agents
│   └── workflow/        # Sequential orchestration
├── challenge-2/          # MCP Server Integration
│   └── agents/          # Alert and fraud detection agents
├── challenge-3/          # Observability & Telemetry
│   ├── workbooks/       # Azure monitoring templates
│   └── batch_run/       # Multi-transaction processing
└── challenge-4/          # Responsible AI & Production
```

## Contributing Changes

Project maintainers will merge accepted code changes from contributors.

### DOs and DON'Ts

**DO:**

- **DO** give priority to the current style of the project or file you're changing if it diverges from the general guidelines
- **DO** include tests when adding new features. When fixing bugs, start with adding a test that highlights how the current behavior is broken
- **DO** keep discussions focused. When a new or related topic comes up it's often better to create a new issue than to side track the discussion
- **DO** clearly state on an issue that you are going to take on implementing it
- **DO** follow responsible AI principles and maintain compliance focus

**DON'T:**

- **DON'T** surprise us with big pull requests. Instead, file an issue and start a discussion so we can agree on a direction before you invest a large amount of time
- **DON'T** commit code that you didn't write. If you find code that you think is a good fit to add to the project, file an issue and start a discussion before proceeding
- **DON'T** submit PRs that alter licensing related files or headers. If you believe there's a problem with them, file an issue and we'll be happy to discuss it
- **DON'T** make breaking changes to existing agent interfaces without filing an issue and discussing with us first
- **DON'T** create issues for minor typos or formatting issues. Instead, submit a direct PR with the fix


### Finding Issues to Work On

- Check the [Issues](../../issues) tab for open issues
- Look for issues labeled with:
  - `good first issue` - Great for new contributors
  - `help wanted` - Community contributions welcome
  - `agent-framework` - Microsoft Agent Framework specific
  - `mcp-integration` - Model Context Protocol related
  - `observability` - Monitoring and telemetry improvements

### General Guidelines

- **Clear and Concise**: Samples should demonstrate specific features without unnecessary complexity
- **Consistent Structure**: All samples should follow the same folder structure and naming conventions
- **Incremental Complexity**: Start simple and gradually increase complexity across sample sets
- **Over-documentation**: Include extensive comments, README files, and explanatory text

## Submitting Changes

### Suggested Workflow

We use and recommend the following workflow:

1. **Create an issue for your work**
   - You can skip this step for trivial changes
   - Reuse an existing issue on the topic, if there is one
   - Get agreement from the team and the community that your proposed change is a good one
   - Clearly state that you are going to take on implementing it, if that's the case. You can request that the issue be assigned to you

2. **Create a personal fork** of the repository on GitHub (if you don't already have one)

3. **In your fork, create a branch** off of main:
   ```bash
   git checkout -b feature/your-feature-name
   # or
   git checkout -b issue-123
   ```
   Name the branch so that it clearly communicates your intentions

4. **Make and commit your changes** to your branch:
   ```bash
   git add .
   git commit -m "feat: add new fraud detection agent capability"
   ```

5. **Add new tests** corresponding to your change, if applicable

6. **Run quality checks** to ensure your build is clean and all tests are passing:
   ```bash
   # Run tests
   python -m pytest --cov=agents tests/
   
   # Check code formatting (if using ruff)
   ruff format --check .
   ruff check .
   ```

7. **Create a PR** against the repository's **main** branch:
   - State in the description what issue or improvement your change is addressing
   - Verify that all the Continuous Integration checks are passing
   ```bash
   git push origin feature/your-feature-name
   ```

8. **Wait for feedback** or approval of your changes from the code maintainers

9. **When area owners have signed off**, and all checks are green, your PR will be merged

### Commit Message Format

Use conventional commit format for clear change tracking:

```
feat: add new fraud detection agent capability
fix: resolve MCP server connection timeout
docs: update challenge-2 setup instructions
test: add unit tests for risk analyzer agent
style: format code according to standards
refactor: reorganize agent workflow logic
perf: improve transaction processing speed
chore: update dependencies
```

### Pull Request Requirements

- [ ] Code follows project style guidelines and Agent Framework patterns
- [ ] Tests pass and coverage meets 80% minimum requirement
- [ ] Documentation is updated (README, docstrings, comments)
- [ ] Changes maintain backward compatibility (or breaking changes are clearly documented)
- [ ] PR description clearly explains the changes and motivation
- [ ] All commits follow conventional commit format

### PR - CI Process

The continuous integration (CI) system will automatically perform the required builds and run tests for PRs. Builds and test runs must be clean.

If the CI build fails for any reason, the PR issue will be updated with a link that can be used to determine the cause of the failure.

### Review Process

1. **Automated Checks:** CI/CD pipeline runs tests and quality checks
2. **Code Review:** Maintainers review code for:
   - Compliance with Agent Framework patterns
   - Regulatory compliance and responsible AI principles
   - Code quality and maintainability
3. **Testing:** Changes are validated in representative Azure environments
4. **Approval:** At least one maintainer approval required
5. **Merge:** Changes are merged to main branch

## Community

### Getting Help

- **Documentation:** Start with the challenge guides and README files
- **Issues:** Create an issue for bugs or feature requests
- **Discussions:** Use GitHub Discussions for questions and ideas

### Communication Channels

- **GitHub Issues:** Bug reports and feature requests
- **GitHub Discussions:** General questions and community discussions
- **Pull Request Comments:** Code-specific discussions

## License

By contributing to this project, you agree that your contributions will be licensed under the [MIT License](LICENSE).

---

Thank you for contributing to the Azure Trust and Compliance Multi-Agents Hack! Your contributions help advance the state of AI-powered regulatory compliance and make financial services more transparent and trustworthy. 🚀