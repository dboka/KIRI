# Security And Secrets

Do not commit passwords, API tokens, Oracle wallets, `.env` files, or provider credentials.

CLIDATA download scripts read credentials only from environment variables:

```powershell
$env:CLIDATA_ORACLE_USER = "..."
$env:CLIDATA_ORACLE_PASSWORD = "..."
$env:CLIDATA_ORACLE_DSN = "host:port/service"
$env:CLIDATA_ELEMENT = "..."
$env:CLIDATA_ORACLE_INSTANTCLIENT = "C:\path\to\instantclient"
```

`CLIDATA_ORACLE_DSN` and `CLIDATA_ELEMENT` are required. `CLIDATA_ORACLE_INSTANTCLIENT` is optional when local client discovery is sufficient.

If a secret is ever pushed, rotate it immediately. Removing it from code is not enough because Git history and tags can retain old values.
