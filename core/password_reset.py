"""
Views customizadas para recuperação de senha no sistema multi-tenant
"""
from django.contrib.auth import views as auth_views
from django.contrib.auth.tokens import default_token_generator
from django.contrib.sites.shortcuts import get_current_site
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.shortcuts import redirect, render
from django.urls import reverse
from django.contrib import messages
from django.conf import settings
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.cache import never_cache
from django.utils.decorators import method_decorator
from django.http import Http404
from django.db.models import Q
from core.models import CustomUser, Company
from core.email.send_transactional import send_transactional_html
from core.email_branding import get_email_branding_context
import logging

logger = logging.getLogger(__name__)


class CompanyPasswordResetView(auth_views.PasswordResetView):
    """View para solicitar reset de senha (empresa)"""
    template_name = 'company/password_reset.html'
    email_template_name = 'core/email/password_reset.html'
    subject_template_name = 'company/password_reset_subject.txt'
    success_url = 'company:password_reset_done'
    
    def dispatch(self, request, *args, **kwargs):
        # Verificar se a empresa existe
        company_slug = kwargs.get('company_slug')
        if company_slug:
            try:
                company = Company.objects.get(slug=company_slug, is_active=True)
                self.company = company
            except Company.DoesNotExist:
                raise Http404("Empresa não encontrada")
        else:
            raise Http404("Slug da empresa é obrigatório")
        return super().dispatch(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['company'] = self.company
        context['company_slug'] = self.company.slug
        return context
    
    def form_valid(self, form):
        email = form.cleaned_data['email']
        
        # Buscar usuários com esse email que pertencem à empresa
        users = CustomUser.objects.filter(
            email__iexact=email,
            company=self.company,
            is_active=True
        )
        
        if users.exists():
            # Enviar email para cada usuário encontrado
            for user in users:
                self.send_reset_email(user)
            
            # Sempre mostrar mensagem de sucesso (mesmo se não encontrar)
            # Por segurança, não revelar se o email existe ou não
            messages.success(
                self.request,
                'Se o e-mail fornecido estiver cadastrado, você receberá um link para redefinir sua senha.'
            )
        else:
            # Mesma mensagem por segurança
            messages.success(
                self.request,
                'Se o e-mail fornecido estiver cadastrado, você receberá um link para redefinir sua senha.'
            )
        
        return redirect('company:password_reset_done', company_slug=self.company.slug)
    
    def send_reset_email(self, user):
        """Envia email de reset de senha customizado"""
        token = default_token_generator.make_token(user)
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        current_site = get_current_site(self.request)
        domain = current_site.domain
        protocol = 'https' if self.request.is_secure() else 'http'
        
        # URL de reset
        reset_url = reverse(
            'company:password_reset_confirm',
            kwargs={
                'company_slug': self.company.slug,
                'uidb64': uid,
                'token': token
            }
        )
        reset_url = f"{protocol}://{domain}{reset_url}"
        
        # Renderizar email
        context = {
            'user': user,
            'company': self.company,
            'reset_url': reset_url,
            'domain': domain,
            'protocol': protocol,
            'site_name': current_site.name,
            **get_email_branding_context(self.request),
        }
        
        subject = render_to_string(
            'company/password_reset_subject.txt',
            context
        ).strip()
        
        message = render_to_string(
            'core/email/password_reset.html',
            context
        )
        
        try:
            send_transactional_html(
                subject=subject,
                html=message,
                recipient_list=[user.email],
                fail_silently=False,
            )
            logger.info(f"Email de reset de senha enviado para {user.email} (empresa: {self.company.slug})")
        except Exception as e:
            logger.error(f"Erro ao enviar email de reset: {str(e)}")


class CompanyPasswordResetDoneView(auth_views.PasswordResetDoneView):
    """View após solicitar reset (empresa)"""
    template_name = 'company/password_reset_done.html'
    
    def dispatch(self, request, *args, **kwargs):
        company_slug = kwargs.get('company_slug')
        if company_slug:
            try:
                self.company = Company.objects.get(slug=company_slug, is_active=True)
            except Company.DoesNotExist:
                raise Http404("Empresa não encontrada")
        else:
            raise Http404("Slug da empresa é obrigatório")
        return super().dispatch(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['company'] = self.company
        context['company_slug'] = self.company.slug
        return context


class CompanyPasswordResetConfirmView(auth_views.PasswordResetConfirmView):
    """View para confirmar e definir nova senha (empresa)"""
    template_name = 'company/password_reset_confirm.html'
    success_url = 'company:password_reset_complete'
    post_reset_login = False
    
    def dispatch(self, request, *args, **kwargs):
        company_slug = kwargs.get('company_slug')
        if company_slug:
            try:
                self.company = Company.objects.get(slug=company_slug, is_active=True)
            except Company.DoesNotExist:
                raise Http404("Empresa não encontrada")
        else:
            raise Http404("Slug da empresa é obrigatório")
        return super().dispatch(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['company'] = self.company
        context['company_slug'] = self.company.slug
        return context
    
    def get_user(self, uidb64):
        """Sobrescrever para validar que o usuário pertence à empresa"""
        try:
            uid = force_str(urlsafe_base64_decode(uidb64))
            user = CustomUser.objects.get(pk=uid)
            
            # Verificar se o usuário pertence à empresa
            if user.company != self.company:
                return None
                
            return user
        except (TypeError, ValueError, OverflowError, CustomUser.DoesNotExist):
            return None
    
    def get_success_url(self):
        return reverse('company:password_reset_complete', kwargs={'company_slug': self.company.slug})


class CompanyPasswordResetCompleteView(auth_views.PasswordResetCompleteView):
    """View após confirmar reset (empresa)"""
    template_name = 'company/password_reset_complete.html'
    
    def dispatch(self, request, *args, **kwargs):
        company_slug = kwargs.get('company_slug')
        if company_slug:
            try:
                self.company = Company.objects.get(slug=company_slug, is_active=True)
            except Company.DoesNotExist:
                raise Http404("Empresa não encontrada")
        else:
            raise Http404("Slug da empresa é obrigatório")
        return super().dispatch(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['company'] = self.company
        context['company_slug'] = self.company.slug
        return context


# Views para RM (sem empresa)
class RMPasswordResetView(auth_views.PasswordResetView):
    """View para solicitar reset de senha (RM)"""
    template_name = 'rm/password_reset.html'
    email_template_name = 'core/email/password_reset.html'
    subject_template_name = 'rm/password_reset_subject.txt'
    success_url = 'rm:password_reset_done'
    
    def form_valid(self, form):
        email = form.cleaned_data['email']
        
        # Buscar usuários RM com esse email (sem empresa ou RM admins)
        users = CustomUser.objects.filter(
            email__iexact=email,
            is_active=True
        ).filter(
            Q(role='RM') | Q(company__isnull=True) | Q(is_superuser=True)
        )
        
        if users.exists():
            for user in users:
                self.send_reset_email(user)
            
            messages.success(
                self.request,
                'Se o e-mail fornecido estiver cadastrado, você receberá um link para redefinir sua senha.'
            )
        else:
            messages.success(
                self.request,
                'Se o e-mail fornecido estiver cadastrado, você receberá um link para redefinir sua senha.'
            )
        
        return redirect('rm:password_reset_done')
    
    def send_reset_email(self, user):
        """Envia email de reset de senha para RM"""
        token = default_token_generator.make_token(user)
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        current_site = get_current_site(self.request)
        domain = current_site.domain
        protocol = 'https' if self.request.is_secure() else 'http'
        
        reset_url = reverse(
            'rm:password_reset_confirm',
            kwargs={
                'uidb64': uid,
                'token': token
            }
        )
        reset_url = f"{protocol}://{domain}{reset_url}"
        
        context = {
            'user': user,
            'reset_url': reset_url,
            'domain': domain,
            'protocol': protocol,
            'site_name': current_site.name,
            **get_email_branding_context(self.request),
        }
        
        subject = render_to_string('rm/password_reset_subject.txt', context).strip()
        message = render_to_string('core/email/password_reset.html', context)
        
        try:
            send_transactional_html(
                subject=subject,
                html=message,
                recipient_list=[user.email],
                fail_silently=False,
            )
            logger.info(f"Email de reset de senha enviado para {user.email} (RM)")
        except Exception as e:
            logger.error(f"Erro ao enviar email de reset: {str(e)}")


class RMPasswordResetDoneView(auth_views.PasswordResetDoneView):
    """View após solicitar reset (RM)"""
    template_name = 'rm/password_reset_done.html'


class RMPasswordResetConfirmView(auth_views.PasswordResetConfirmView):
    """View para confirmar e definir nova senha (RM)"""
    template_name = 'rm/password_reset_confirm.html'
    success_url = 'rm:password_reset_complete'
    post_reset_login = False
    
    def get_user(self, uidb64):
        """Sobrescrever para validar que é usuário RM"""
        try:
            uid = force_str(urlsafe_base64_decode(uidb64))
            user = CustomUser.objects.get(pk=uid)
            
            # Verificar se é RM ou superuser
            if not (user.role == 'RM' or user.is_superuser or user.company is None):
                return None
                
            return user
        except (TypeError, ValueError, OverflowError, CustomUser.DoesNotExist):
            return None


class RMPasswordResetCompleteView(auth_views.PasswordResetCompleteView):
    """View após confirmar reset (RM)"""
    template_name = 'rm/password_reset_complete.html'

