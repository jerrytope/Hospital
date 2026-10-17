class PaymentError(Exception):
    """Raised when a provider call fails; the message is safe to show to staff."""


class Provider:
    """Interface every payment provider implements.

    Checkout methods return a URL to redirect the donor to. Money state changes only
    happen in webhook handling (apps.payments.handlers), never on the return page.
    """

    name = ""

    def start_one_time(self, donation, return_url, cancel_url):
        raise NotImplementedError

    def start_recurring(self, donation, recurring, return_url, cancel_url):
        raise NotImplementedError

    def cancel_recurring(self, recurring):
        raise NotImplementedError

    def pause_recurring(self, recurring):
        raise NotImplementedError

    def resume_recurring(self, recurring):
        raise NotImplementedError

    def change_recurring(self, recurring, amount=None, day_of_month=None):
        raise NotImplementedError

    def manage_card_url(self, recurring, return_url):
        raise NotImplementedError

    def refund(self, donation):
        raise NotImplementedError

    def verify_return(self, donation):
        """Optional fast-path check on the return page; must stay idempotent."""
        return None

    def parse_webhook(self, request):
        """Verify signature and return (event_id, event_type, payload) or raise PaymentError."""
        raise NotImplementedError
