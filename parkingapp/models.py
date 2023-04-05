from django.contrib import admin
from django.contrib.auth.models import User
from django.contrib.auth.hashers import make_password, check_password
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from django.utils.safestring import mark_safe
from django.core.exceptions import ValidationError
from django.db.models import signals
from django.apps import AppConfig
from django.core.validators import validate_email
import stripe
from django.conf import settings




stripe.api_key = settings.STRIPE_SECRET_KEY




class CustomerProfile(models.Model):
    full_name = models.CharField(max_length=200)
    phone_number = models.BigIntegerField()
    email = models.CharField(unique=True, max_length=200, validators=[validate_email])
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['full_name', 'phone_number']

    #def set_password(self, password):
       # self.password = make_password(password)

   # def check_password(self, password):
     #   return check_password(password, self.password)
     
    def __str__(self):
        return self.full_name or self.email


class CustomerVehicle(models.Model):
    user_id = models.ForeignKey(CustomerProfile, on_delete=models.CASCADE)
    Customervehicle_name=models.CharField(max_length=200)
    plate_number=models.CharField(max_length=10)
    color=models.CharField(max_length=20)
    is_active=models.BooleanField()
    entry_date= models.DateTimeField()
    updated_date=models.DateTimeField(null=True, blank=True)
    exit_date=models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.Customervehicle_name
    
    
class CreditCard(models.Model):
    users_id=models.ForeignKey(CustomerProfile,on_delete=models.CASCADE)
    card_number=models.BigIntegerField()
    cardholder_name=models.CharField(max_length=200)
    expiration_date=models.DateField()
    is_default=models.BooleanField()
    created_at=models.DateTimeField(auto_now_add=True)
    updated_at=models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.cardholder_name


class ParkingLot(models.Model):
    name=models.CharField(max_length=200)
    location=models.CharField(max_length=200)
    total_spaces=models.IntegerField()
    available_space=models.IntegerField()

    def __str__(self):
        return self.name


class ParkingReservation(models.Model):
    users_id=models.ForeignKey(CustomerProfile,on_delete=models.CASCADE)
    parking_reservation_id=models.ForeignKey(ParkingLot,on_delete=models.CASCADE)
    Customervehicle_id=models.ForeignKey(CustomerVehicle, on_delete=models.CASCADE)
    start_time=models.DateTimeField()
    end_time=models.DateTimeField(null=True, blank=True)
    is_active=models.BooleanField()
    is_paid = models.BooleanField(default=False)


    def save(self, *args, **kwargs):
        is_new_reservation = self.pk is None  # Check if the booking is being created for the first time
        super().save(*args, **kwargs)
        # Decrement available_space field of the related ParkingLot model only if the booking is being created for the first time
        if is_new_reservation:
            self.parking_reservation_id.available_space -= 1
            self.parking_reservation_id.save()
        # Increment available_space field of the related ParkingLot model if the exit_date is not None
        if self.Customervehicle_id.exit_date is not None:
            self.parking_reservation_id.available_space += 1
            self.parking_reservation_id.save()

        # Set the exit_date of the related CustomerVehicle model
        if self.Customervehicle_id.exit_date is None:
            self.Customervehicle_id.exit_date = timezone.now()
            self.Customervehicle_id.save()
            
        # Update is_paid field of the related Reservation model
        reservation_instance = ParkingReservation.objects.filter(Customervehicle_id=self.Customervehicle_id).first()
        if reservation_instance:
            reservation_instance.is_paid = self.is_paid
            reservation_instance.save()
    
     
    def pay(self, request, queryset):
        for reservation in queryset:
            payment = Payment.objects.create(
                amount=reservation.cost,
                card_number=reservation.card_number,
                cardholder_name=reservation.cardholder_name,
                expiration_month=reservation.expiration_month,
                expiration_year=reservation.expiration_year,
                cvv=reservation.cvv
            )
            payment.charge()
            reservation.is_paid = True
            reservation.save()
    
    pay.short_description = "Mark selected reservations as paid"
    actions = [pay]

            
            
            
    def charge_customer(self, token, amount):
    #Charge the customer using the given token and amount
    
        try:
            charge = stripe.Charge.create(
                amount=int(amount * 100),  # convert amount to cents
                currency="usd",
                description="Parking Reservation",
                source=token,
            )

            # update is_paid field of the model instance to True
            self.is_paid = True
            self.save()

            return True

        except stripe.error.CardError as e:
            # Since it's a decline, stripe.error.CardError will be caught
            body = e.json_body
            err = body.get('error', {})
            print("Status is: %s" % e.http_status)
            print("Type is: %s" % err.get('type'))
            print("Code is: %s" % err.get('code'))
            # param is '' in this case
            print("Param is: %s" % err.get('param'))
            print("Message is: %s" % err.get('message'))
            return False

        except stripe.error.RateLimitError as e:
            # Too many requests made to the API too quickly
            return False

        except stripe.error.InvalidRequestError as e:
            # Invalid parameters were supplied to Stripe's API
            return False

        except stripe.error.AuthenticationError as e:
            # Authentication with Stripe's API failed
            # (maybe you changed API keys recently)
            return False

        except stripe.error.APIConnectionError as e:
            # Network communication with Stripe failed
            return False

        except stripe.error.StripeError as e:
            # Display a very generic error to the user, and maybe send
            # yourself an email
            return False

        except Exception as e:
            # Something else happened, completely unrelated to Stripe
            return False
                
            
    def __str__(self):
        return f"{self.users_id.email}: {self.start_time} - {self.end_time}"
    
    
class ParkingSpaceBooking(models.Model):
    user = models.ForeignKey(CustomerProfile, on_delete=models.CASCADE)
    parking_reservation = models.ForeignKey(ParkingReservation, on_delete=models.CASCADE, blank=True, null=True)
    is_paid = models.BooleanField(default=False)
    parking_lot = models.ForeignKey(ParkingLot, on_delete=models.CASCADE)

    def parking_space(self):
        # calculate the corresponding parking space based on the parking_lot field
        # and return it as a string
        return f"{self.parking_lot.name} - {self.parking_lot.available_space}/{self.parking_lot.total_spaces}"
    parking_space.short_description = 'Parking Space'

    def clean(self):
        super().clean()
        if self.parking_reservation and self.parking_reservation.users_id != self.user:
            raise ValidationError('You cannot book another user\'s reservation.')
        
        
class ParkingSpaceBookingAdmin(admin.ModelAdmin):
    list_display = ('user', 'parking_reservation', 'is_paid')

    def save_model(self, request, obj, form, change):
        if not obj.parking_reservation:
            # create a new parking reservation for the admin
            reservation = ParkingReservation.objects.create(
                parking_lot=obj.parking_lot,
                start_time=timezone.now(),
                end_time=timezone.now() + timezone.timedelta(hours=1),
                is_paid=True
            )
            obj.parking_reservation = reservation

        # check if the parking reservation for the booking belongs to the same user
        if obj.parking_reservation.users_id != obj.user:
            raise ValidationError("You cannot book another user's reservation.")

        # check if the reservation is already paid and set is_paid flag accordingly
        obj.is_paid = obj.parking_reservation.is_paid

        # Update is_paid field of other bookings for the same reservation
        bookings = ParkingSpaceBooking.objects.filter(parking_reservation=obj.parking_reservation)
        for booking in bookings:
            booking.is_paid = obj.is_paid
            booking.save()

        super().save_model(request, obj, form, change)



@receiver(signals.post_save, sender=ParkingReservation)
def update_parking_reservation_booking_is_paid(sender, instance, **kwargs):
    # Get all the ParkingSpaceBooking objects that are associated with this reservation
    bookings = ParkingSpaceBooking.objects.filter(parking_reservation=instance)

    # Update the is_paid field of each booking
    for booking in bookings:
        booking.is_paid = instance.is_paid
        booking.save()



class YourAppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'parkingapp'

    def ready(self):
        import parkingapp.signals



from parkingapp.models import ParkingReservation

class Payment(models.Model):
    reservation = models.ForeignKey(ParkingReservation, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=8, decimal_places=2)
    payment_date = models.DateTimeField(auto_now_add=True)

    




#class Payment(models.Model):
 #   users_id=models.ForeignKey(CustomerProfiles,on_delete=models.CASCADE)
  #  reservation_id=models.ForeignKey(ParkingReservations,on_delete=models.CASCADE)
   # card_id=models.ForeignKey(CreditCards, on_delete=models.CASCADE)
    #amount=models.FloatField()
    #is_successful=models.BooleanField()
    #created_at=models.DateTimeField(auto_now_add=True)
