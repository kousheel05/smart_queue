from django.conf import settings
from twilio.rest import Client


def send_sms(phone, message):
    """
    Send SMS using Twilio credentials from settings.py (.env).
    """
    try:
        # If Twilio is not configured, skip safely
        if not settings.TWILIO_ACCOUNT_SID or not settings.TWILIO_AUTH_TOKEN or not settings.TWILIO_PHONE_NUMBER:
            print("Twilio credentials missing in settings. SMS not sent.")
            return False

        client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)

        client.messages.create(
            body=message,
            from_=settings.TWILIO_PHONE_NUMBER,
            to=phone
        )

        print(f"SMS sent to {phone}")
        return True

    except Exception as e:
        print("Twilio SMS Error:", e)
        return False
