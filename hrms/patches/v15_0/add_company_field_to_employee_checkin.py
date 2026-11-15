# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# License: MIT. See LICENSE

import frappe


def execute():
	"""Add `company` column to Employee Checkin and backfill from the linked Employee.

	The column is declared in the Employee Checkin DocType JSON and is normally
	synced during `bench migrate`. This patch guards the ALTER TABLE so it is
	safe to re-run, then backfills existing checkins from their Employee record
	so that Number Cards (and reports) can filter by company without error.
	"""
	# Ensure the column exists (idempotent)
	if not frappe.db.has_column("Employee Checkin", "company"):
		frappe.db.sql_ddl(
			"ALTER TABLE `tabEmployee Checkin` ADD COLUMN `company` VARCHAR(140)"
		)

	# Backfill company from the linked Employee record
	frappe.db.sql(
		"""
		UPDATE `tabEmployee Checkin` ec
		INNER JOIN `tabEmployee` e ON e.name = ec.employee
		SET ec.company = e.company
		WHERE ec.company IS NULL OR ec.company = ""
		"""
	)
