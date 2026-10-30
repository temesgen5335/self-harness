def format_cents(cents):
    """Format an integer amount of cents as dollars, e.g. 1234 -> '$12.34', -5 -> '-$0.05'."""
    if not isinstance(cents, int) or isinstance(cents, bool):
        raise TypeError("cents must be an int")
    sign = "-" if cents < 0 else ""
    dollars, rest = divmod(abs(cents), 100)
    return f"{sign}${dollars:,}.{rest:02d}"
