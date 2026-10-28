# FreightIQ — Freight Invoice Audit, Investigation & Reconciliation

FreightIQ is a Django web application for validating freight invoices against contracted rates and shipment data, investigating exceptions, recording manager decisions and carrier responses, and tracking credit-note verification, application, and reconciliation. Business names and generated transactions are fictional synthetic data.

## Features

- Django authentication and approval-based, role-specific workspaces
- Shipment registry and delivery evidence
- Contract/rate-card freight calculation using `Decimal`
- Invoice validation and exception creation
- Analyst investigation, manager approval/return/rejection, and carrier response
- Finance credit-note verification, application, reversal, and reconciliation
- Audit events, CSV import/export, synthetic data generation, and validation
- Automated Django tests and workflow/data documentation

## Requirements

- Windows 10/11 (commands below use PowerShell; Command Prompt works with equivalent activation syntax)
- Python 3.11 or 3.12 recommended
- Internet access for Bootstrap and icon/font CDNs used by the UI

## Install and run on Windows

Open PowerShell in the folder containing `manage.py`:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
```

The repository intentionally does **not** include `db.sqlite3` or database backups. Migrations create a clean local database. Create the initial administrator with `createsuperuser`; do not use public registration to create a system administrator.

Generate a compact demo dataset first:

```powershell
python manage.py generate_freight_data --seed 20261022 --carriers 12 --shipments 100 --invoices 70
python manage.py validate_freight_data
python manage.py check
python manage.py test
python manage.py runserver
```

Open <http://127.0.0.1:8000/> and sign in with the administrator credentials you created. Stop the development server with `Ctrl+C`.

### Optional: full-scale synthetic dataset

For a larger local demonstration, run this only after the compact setup works:

```powershell
python manage.py generate_freight_data --seed 20261022 --carriers 100 --shipments 20000 --invoices 15000
python manage.py validate_freight_data
python manage.py test
```

This creates many related records and takes longer. Do not add `--reset` if you need to preserve existing synthetic finance/workflow records. Back up any local database before schema or data maintenance.

## Roles and workflow

1. A Planner records shipment, route, cargo, weight/dimensions, service, and delivery information.
2. A Supplier submits an invoice with charge values and supporting evidence.
3. FreightIQ selects the applicable contract rate, calculates billable weight and expected charges, and records validation findings.
4. A Logistics Analyst investigates an exception and recommends a credit or no credit.
5. An Operations Manager approves, rejects with a reason, or returns the case for further work.
6. The Carrier/Warehouse Operator accepts, disputes, or counteroffers.
7. Finance records the actual credit note, verifies it, applies eligible verified amounts, and reconciles the persisted balances.
8. Audit events retain important workflow actions and explanations.

## Calculation overview

- Dimensional weight is derived from dimensions, quantity, and the configured rate-card divisor.
- Billable weight is the greater of actual and dimensional weight.
- Base freight uses the applicable rate card and weight tier, including minimum charges where configured.
- Fuel and eligible accessorial charges are calculated from contract rules.
- Invoice discrepancy is billed total minus expected total. A positive value indicates a potential overcharge; it does not by itself mean a credit has been approved or recovered.
- Monetary calculations use `Decimal` rather than binary floating-point arithmetic.

## Data commands

```powershell
python manage.py generate_freight_data --seed 20261022 --carriers 12 --shipments 100 --invoices 70
python manage.py validate_freight_data
python manage.py export_freight_data --directory data/exports
python manage.py import_freight_csv --directory data
```

Compact synthetic CSV fixtures are included under `data/master/` and `data/transactions/`. Ground-truth labels are stored separately under `data/ground_truth/`. The sample validation report under `data/exports/validation_report.json` records a successful full-scale validation from the supplied local project; it is an example report, not a validation of a fresh checkout.

## Tests and validation

Run these from the project root with the virtual environment activated:

```powershell
python manage.py check
python manage.py test
python manage.py validate_freight_data
```

**Reported local verification for the supplied project:** the user ran all 14 automated tests successfully and `validate_freight_data` returned `passed: true`, `error_count: 0` after generating 100 synthetic carriers, 20,000 synthetic shipments, and 15,000 synthetic invoices. The database contained 20,001 shipments in total because one non-synthetic shipment was preserved. These results describe that local database and are not a promise that every workflow has been manually browser-tested on a fresh installation.

## Security and production notes

- Never commit database files, backups, `.env` files, credentials, or virtual environments.
- Configure `DJANGO_SECRET_KEY`, `DJANGO_DEBUG`, and `DJANGO_ALLOWED_HOSTS` through environment variables for deployment. The development fallback secret is not suitable for production.
- Before public production deployment, use `DEBUG=False`, configure HTTPS and trusted hosts, use a production database and suitable static/media storage, and perform a security and acceptance review.
- Test every role and lifecycle edge case. Passing unit tests and data validation does not replace end-to-end browser verification.

## Documentation

- `PROJECT_EXECUTION_GUIDE.pdf` — Windows execution and workflow guide
- `docs/DATA_DICTIONARY.md` — model fields and validation concepts
- `docs/DATA_MODEL.md` — entity relationships
- `docs/WORKFLOW.md` — workflow states and transitions
- `docs/SOURCE_MANIFEST.md` — source inventory and verification notes
- `data/README.md` — synthetic data provenance and commands
