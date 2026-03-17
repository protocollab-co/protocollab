# Security Policy

## Reporting a Vulnerability

We take the security of `protocollab` seriously. If you believe you've found a security vulnerability, please follow these steps:

1. **Do not disclose the vulnerability publicly** (e.g., in GitHub Issues, Discussions, or Twitter).
2. **Send a private report** to [cherninkiy@gmail.com](mailto:cherninkiy@gmail.com) or use GitHub's private vulnerability reporting tool (if enabled).
3. Provide as much information as possible:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Suggested fix (if any)

## Supported Versions

We currently support the latest version of `protocollab` with security updates.
| Version | Supported |
| ------- | --------- |
| latest           | ✅        |
| older than latest | ❌        |

## Security Measures in `protocollab`

`protocollab` includes built-in security hardening in its YAML loader:
- Protection against Billion Laughs (YAML alias/anchor expansion)
- Path traversal prevention in `!include` directives
- Recursion depth limits
- File size restrictions

These measures are designed to safely handle untrusted specifications.