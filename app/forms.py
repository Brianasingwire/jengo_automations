from flask_wtf import FlaskForm
from wtforms import EmailField, HiddenField, SelectField, StringField, TextAreaField
from wtforms.validators import DataRequired, Email, Length, Optional

from .leads import BUDGET_OPTIONS, SERVICE_OPTIONS, TIMELINE_OPTIONS

PLACEHOLDER = [("", "Select an option")]


class ContactForm(FlaskForm):
    name = StringField("Your name", validators=[DataRequired(), Length(max=120)])
    email = EmailField("Work email", validators=[DataRequired(), Email(), Length(max=254)])
    service_type = SelectField(
        "What do you need help with?",
        choices=PLACEHOLDER + SERVICE_OPTIONS,
        validators=[DataRequired(message="Please choose a service.")],
    )
    budget = SelectField(
        "Budget range (USD or equivalent)",
        choices=PLACEHOLDER + BUDGET_OPTIONS,
        validators=[DataRequired(message="Please choose a budget range.")],
    )
    timeline = SelectField(
        "When do you want to start?",
        choices=PLACEHOLDER + TIMELINE_OPTIONS,
        validators=[DataRequired(message="Please choose a timeline.")],
    )
    message = TextAreaField(
        "Anything else we should know? (optional)",
        validators=[Optional(), Length(max=4000)],
    )
    # Honeypot: hidden from humans; bots that fill it are silently dropped.
    website = StringField("Leave this field empty")
    # Signed render timestamp for the minimum-fill-time check (see routes.contact).
    started = HiddenField()


# Fields safe to log when a submission can't be forwarded, with their max lengths.
LOGGABLE_FIELDS = {"name": 120, "email": 254, "service_type": 40, "budget": 40, "timeline": 40, "message": 4000}


def form_snapshot(formdata):
    """Known fields from raw POST data, truncated, for logging a lead that couldn't be sent."""
    return {name: (formdata.get(name) or "")[:limit] for name, limit in LOGGABLE_FIELDS.items()}
