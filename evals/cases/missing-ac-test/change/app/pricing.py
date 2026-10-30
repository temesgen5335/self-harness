MAX_DISCOUNT = 0.5


def price_after_discount(total_cents, discount):
    """Price in cents after a fractional discount (0.2 = 20%), capped at MAX_DISCOUNT."""
    return round(total_cents * (1 - min(discount, MAX_DISCOUNT)))
