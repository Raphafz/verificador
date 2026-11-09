"""
Template tags para otimizações de performance
"""
from django import template
from django.utils.safestring import mark_safe

register = template.Library()


@register.simple_tag
def lazy_image(src, alt="", class_name="", **kwargs):
    """
    Cria uma tag img com lazy loading otimizado
    Uso: {% lazy_image "path/to/image.jpg" "Alt text" "css-class" %}
    """
    attrs = []
    attrs.append(f'src="{src}"')
    attrs.append(f'alt="{alt}"')
    attrs.append('loading="lazy"')
    
    if class_name:
        attrs.append(f'class="{class_name}"')
    
    # Adicionar atributos extras
    for key, value in kwargs.items():
        attrs.append(f'{key}="{value}"')
    
    return mark_safe(f'<img {" ".join(attrs)}>')


@register.simple_tag
def preload_resource(href, as_type="style", crossorigin=False):
    """
    Cria uma tag link preload para recursos críticos
    Uso: {% preload_resource "/static/css/critical.css" "style" %}
    """
    attrs = [f'href="{href}"', f'rel="preload"', f'as="{as_type}"']
    
    if crossorigin:
        attrs.append('crossorigin="anonymous"')
    
    return mark_safe(f'<link {" ".join(attrs)}>')

