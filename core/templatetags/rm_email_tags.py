from django import template

from core.rm_transactional_email import get_templates_for_user

register = template.Library()


@register.simple_tag
def get_rm_email_templates(user):
    return get_templates_for_user(user)
