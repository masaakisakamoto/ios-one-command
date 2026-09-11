# Contributing

Start with a minimal sample project and the shareable report. Do not include
customer app sources, Apple account details, private keys or raw signing logs in
an issue. The included issue template asks for reproduction steps and a report.

The CLI is standard-library Python 3.9+. Run:

```bash
python3 -m unittest discover -s tests
```

On a Mac, also run `bash Verify_On_Mac.command` and
`python3 scripts/simulator_smoke.py`. Record actual Xcode/device versions in
`docs/validation.md`; never equate tool doubles with a real build.

Keep changes focused on local build/install/launch, selection, actionable errors,
and recoverable execution. Preserve project signing and bundle identities unless
the user explicitly overrides them. Never infer a Team from a certificate CN suffix.
Add regression tests for failures affecting source preservation, target choice,
signing, install order, process cancellation, or distribution contents.

The source ZIP and standalone launcher are generated, not edited manually.
After reviewing changed source, regenerate them with:

```bash
python3 scripts/package_release.py
```

This refreshes `public-files.json` and writes files under `dist/`. The manifest
is used to publish a reviewed source set; it is not a cryptographic signature.

The current preview was prepared with AI assistance. Human and device verification
are recorded separately from generated code and automated test results.
