from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string


def send_templated(to, subject, template, context, attachments=None, reply_to=None):
    """Render emails/<template>.txt and .html and send them."""
    from apps.core.models import OrganisationSettings

    org = OrganisationSettings.load()
    ctx = {"org": org, "SITE_URL": settings.SITE_URL, **context}
    text = render_to_string(f"emails/{template}.txt", ctx)
    html = render_to_string(f"emails/{template}.html", ctx)
    msg = EmailMultiAlternatives(
        subject=subject,
        body=text,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[to] if isinstance(to, str) else to,
        reply_to=reply_to,
    )
    msg.attach_alternative(html, "text/html")
    for name, content, mimetype in attachments or []:
        msg.attach(name, content, mimetype)
    msg.send()
