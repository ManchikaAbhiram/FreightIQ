# Source Manifest and Verification Record

## Main source

- `manage.py` — Django command entry point.
- `config/` — settings, URL routing, ASGI and WSGI.
- `audit/models.py` — relational business and workflow models.
- `audit/forms.py` — registration, shipment and invoice forms.
- `audit/views.py` — authenticated role workspaces and operations.
- `audit/middleware.py` — approval checks and cache behavior.
- `audit/services/freight_calculator.py` — rate selection, weight tier, minimum charge, fuel and expected totals.
- `audit/services/invoice_validator.py` — validation findings and exception creation.
- `audit/services/workflow_service.py` — analyst, manager and carrier transitions.
- `audit/services/credit_service.py` — credit verification, application, reversal and reconciliation.
- `audit/management/commands/` — synthetic data generator, importer, exporter and validator.
- `data/master/` and `data/transactions/` — compact fictional CSV fixtures.
- `data/ground_truth/` — separate synthetic anomaly labels.
- `audit/templates/` and `audit/static/` — user interface templates, styles and scripts.
- `audit/tests.py` — automated Django tests.

## Included artifacts

- `PROJECT_EXECUTION_GUIDE.pdf` — local setup and workflow guide.
- `data/exports/validation_report.json` — sample report from the supplied full-scale local dataset.

The SQLite database, database backups, virtual environment, and Python bytecode are deliberately excluded from the public submission package. A fresh installation creates its own local database using committed migrations.

## Verification record supplied by the project owner

The owner reported that the local project passed `python manage.py test` with 14 tests and `python manage.py validate_freight_data` with `passed: true` and `error_count: 0`, after generating 100 synthetic carriers, 20,000 synthetic shipments, and 15,000 synthetic invoices. This is a report of the owner's local run, not a claim that this packaging process independently reran Django or browser tests.

Before production use, test the complete acceptance matrix, including organization isolation, workflow edge cases, finance concurrency, and browser session behavior.
