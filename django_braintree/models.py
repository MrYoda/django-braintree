import logging
from decimal import Decimal

from django.db import models
from django.conf import settings
from django.utils.six import python_2_unicode_compatible, text_type

from braintree import Transaction


class UserVaultManager(models.Manager):
    def for_user(self, user):
        """ Returns UserVault object for user or None"""
        try:
            return self.get(user=user)
        except UserVault.DoesNotExists:
            return None
    
    def is_in_vault(self, user):
        return True if self.filter(user=user).count() > 0 else False


@python_2_unicode_compatible
class UserVault(models.Model):
    """Keeping it open that one user can have multiple vault credentials, hence the FK to User and not a OneToOne."""
    user = models.OneToOneField(settings.AUTH_USER_MODEL)
    vault_id = models.CharField(max_length=64, unique=True)
    
    objects = UserVaultManager()
    
    def __str__(self):
        return text_type(self.user)
    
    def charge(self, amount):
        """
        Charges the users credit card, with he passed $amount, if they are in the vault.
        Returns the payment_log instance or None (if charge fails etc.)
        """
        try:
            result = Transaction.sale(
                {
                    'amount': amount.quantize(Decimal('.01')),
                    'customer_id': self.vault_id,
                    "options": {
                        "submit_for_settlement": True
                    }
                }
            )

            if result.is_success:
                # create a payment log
                payment_log = PaymentLog.objects.create(
                    user=self.user, amount=amount,
                    transaction_id=result.transaction.id
                )
                return payment_log
            else:
                raise ValueError('Logical error in CC transaction')
        except ValueError:
            logging.error('Failed to charge $%s to user: %s with vault_id: %s' % (amount, self.user, self.vault_id))
            return None


@python_2_unicode_compatible
class PaymentLog(models.Model):
    """
    Captures raw charges made to a users credit card. Extra info related to this payment should be a OneToOneField
    referencing this model.
    """
    user = models.ForeignKey(settings.AUTH_USER_MODEL)
    amount = models.DecimalField(max_digits=7, decimal_places=2)
    timestamp = models.DateTimeField(auto_now=True)
    transaction_id = models.CharField(max_length=128)
    
    def __str__(self):
        return '%s charged $%s - %s' % (self.user, self.amount, self.transaction_id)
