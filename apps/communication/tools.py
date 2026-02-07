"""
Communication Tools for SecureAssist.
"""
from core.decorators import agent_tool


@agent_tool(
    name="send_email",
    description="Send an email using configured SMTP settings.",
    secrets=["EMAIL_HOST_PASSWORD"],
    requires_approval=True,  # Email requires user approval
    log_response_to_orm=True,
    category="communication"
)
async def send_email(
    to: str,
    subject: str,
    body: str,
    html: bool = False,
    _secret_EMAIL_HOST_PASSWORD: str = None
) -> dict:
    """
    Send an email.
    
    Requires user approval before sending.
    """
    from django.core.mail import send_mail
    from django.conf import settings
    
    try:
        send_mail(
            subject=subject,
            message=body if not html else "",
            html_message=body if html else None,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[to],
            fail_silently=False,
        )
        
        return {
            "status": "sent",
            "to": to,
            "subject": subject
        }
        
    except Exception as e:
        return {"error": f"Failed to send email: {str(e)}"}
