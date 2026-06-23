import resend
from app.utils.constants import RESEND_API_KEY, FROM_EMAIL, RESET_PASSWORD_BASE_URL
from app.utils.logger import logger


def send_password_reset_email(to_email: str, reset_token: str) -> bool:
    if not RESEND_API_KEY:
        logger.error("RESEND_API_KEY not configured — cannot send reset email")
        return False

    resend.api_key = RESEND_API_KEY
    reset_url = f"{RESET_PASSWORD_BASE_URL}/reset-password?token={reset_token}"

    try:
        resend.Emails.send({
            "from": FROM_EMAIL,
            "to": [to_email],
            "subject": "Reset your AgileMood password",
            "html": (
                "<p>Você solicitou a redefinição de senha para a sua conta AgileMood.</p>"
                f'<p><a href="{reset_url}">Clique aqui para redefinir sua senha</a></p>'
                "<p>Este link expira em 15 minutos. Se você não solicitou isso, ignore este e-mail.</p>"
            ),
        })
        return True
    except Exception as e:
        logger.error(f"Failed to send reset email to {to_email}: {e}")
        return False
