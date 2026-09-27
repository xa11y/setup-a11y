# setup-a11y

GitHub Action for setting up accessibility dependencies in GitHub runners so you
can drive [xa11y](https://github.com/xa11y/xa11y) accessibility tests in CI.

On **Linux** it installs the system libraries xa11y needs and (optionally) brings
up a headless display (Xvfb), a D-Bus session, and the AT-SPI bridge — exporting
the right environment to later steps. On **macOS** it can grant the
Accessibility (TCC) permission the runner needs. On **Windows** it is a no-op
(UI Automation works out of the box).

## Usage

```yaml
jobs:
  a11y-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: xa11y/setup-a11y@v1
      # DISPLAY / DBUS / AT-SPI are now live for the rest of the job
      - run: pytest tests/
```

Need GTK/WebKit or Electron libraries? Select extra package groups:

```yaml
      - uses: xa11y/setup-a11y@v1
        with:
          package-groups: base gtk      # or: base electron
          extra-packages: my-app-deps   # any additional apt packages
```

On macOS, grant the Accessibility permission to the process running your tests:

```yaml
      - uses: xa11y/setup-a11y@v1
        with:
          macos-tcc-client: /opt/hostedtoolcache/Python/3.12.x/x64/bin/python3
```

## Inputs

| Input | Default | Description |
| --- | --- | --- |
| `package-groups` | `base` | Space-separated apt package groups to install on Linux. Available: `base`, `gtk`, `electron`, `link`. See [`apt-packages.txt`](./apt-packages.txt). |
| `extra-packages` | `""` | Additional apt packages to install on Linux (space-separated). |
| `install-deps` | `true` | Install system dependencies on Linux. Set to `false` to skip apt entirely. |
| `apt-cache-version` | `2` | Deprecated compatibility input; apt packages are installed directly. |
| `setup-display` | `true` | Start Xvfb and export `DISPLAY` (Linux only). |
| `setup-atspi` | `true` | Start a D-Bus session + AT-SPI bridge and export their env (Linux only). |
| `setup-window-manager` | `false` | Start fluxbox (Linux only). Some toolkits (e.g. egui via AccessKit) only publish their tree once a window manager has mapped the window. |
| `display` | `:99` | X display number to use for Xvfb (Linux only). |
| `macos-tcc-client` | `""` | Path to the binary that needs the Accessibility (TCC) permission on macOS. When empty, the action prints a warning instead. |

## Pinning a version

The examples above use `@v1`. You can also pin to a specific tag or commit SHA
for stricter supply-chain guarantees, or use `@main` to track the latest.

## Links

- **xa11y** — cross-platform accessibility library: <https://github.com/xa11y/xa11y>
- **Setting up GitHub Actions / CI** — see the xa11y docs: <https://xa11y.dev/guides/ci/>

This action was previously published from `xa11y/xa11y` as
`xa11y/xa11y/.github/actions/setup-a11y`. It now lives here for a cleaner
reference name: `xa11y/setup-a11y`.

## Daily canary

The [daily canary](./.github/workflows/nightly-integ.yml) tests the released
`v1` action against `xa11y/xa11y` at 07:00 UTC. It probes the installed
libraries and AT-SPI bus, then runs the xa11y workspace tests. A failed run
opens one issue in this repository; later failures reuse the open issue.
GitHub can disable scheduled workflows after prolonged repository inactivity,
so check that the canary workflow remains enabled after quiet periods.
