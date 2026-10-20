"""Shared pieces of the list endpoints behind the SPA's server-side tables. Each list takes
start / page_length / sort_by / sort_order and returns {"rows": [...], "total": n}."""


def order_by(sort_by, sort_order, sortable, default):
	"""ORDER BY for the column the table is sorted by, when the list allows sorting on it."""
	if sort_by in sortable:
		return f"{sort_by} {'asc' if sort_order == 'asc' else 'desc'}"
	return default


def date_range(from_date=None, to_date=None):
	"""Filter value for a date between two optional bounds, or None when both are empty."""
	if from_date and to_date:
		return ["between", [from_date, to_date]]
	if from_date:
		return [">=", from_date]
	if to_date:
		return ["<=", to_date]
	return None
