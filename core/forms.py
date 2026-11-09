from django import forms
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from django.core.exceptions import ValidationError
from django.contrib.auth.password_validation import validate_password
import os
from .models import CTOMapFile, Company, CustomUser, Ticket, TicketMessage
from .security_validators import SecureFileValidator
from .rate_limiting import upload_rate_limit
from .utils import generate_random_password

class CTOMapFileForm(forms.ModelForm):
    class Meta:
        model = CTOMapFile
        fields = ["file", "description", "company"]
        widgets = {
            'file': forms.FileInput(attrs={
                'class': 'file-input-hidden',
                'accept': '.xlsx,.xls,.csv,.kml,.kmz',
                'id': 'id_file',
                'style': 'display: none;'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'placeholder': 'Adicione uma descrição para identificar melhor este arquivo...',
                'rows': 3,
                'maxlength': 500
            }),
            'company': forms.Select(attrs={
                'class': 'form-control',
                'id': 'id_company'
            })
        }
    
    def clean_file(self):
        file = self.cleaned_data.get('file')
        
        if not file:
            raise ValidationError("Por favor, selecione um arquivo.")
        
        # Usar validador seguro
        validator = SecureFileValidator()
        try:
            validator.validate_file(file)
        except ValidationError as e:
            raise e
        except Exception as e:
            raise ValidationError("Erro na validação do arquivo. Tente novamente.")
        
        return file
    
    def clean_description(self):
        description = self.cleaned_data.get('description', '')
        
        # Limpar espaços em branco extras
        description = description.strip()
        
        # Validar comprimento
        if len(description) > 500:
            raise ValidationError(
                "Descrição muito longa. "
                "Por favor, use no máximo 500 caracteres."
            )
        
        return description

class CompanyForm(forms.ModelForm):
    class Meta:
        model = Company
        fields = [
            'name', 'cnpj', 'email', 'phone', 'address', 'is_active',
            'plan_code', 'quota_enforcement',
            'module_verificador', 'module_alertas', 'module_olt',
        ]
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nome da empresa'
            }),
            'cnpj': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '00.000.000/0000-00',
                'maxlength': 18
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'email@empresa.com'
            }),
            'phone': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '(11) 99999-9999'
            }),
            'address': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Endereço completo da empresa'
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'plan_code': forms.Select(attrs={'class': 'form-control'}),
            'quota_enforcement': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'module_verificador': forms.CheckboxInput(attrs={'class': 'rm-module-card__input'}),
            'module_alertas': forms.CheckboxInput(attrs={'class': 'rm-module-card__input'}),
            'module_olt': forms.CheckboxInput(attrs={'class': 'rm-module-card__input'}),
        }

    def clean(self):
        cleaned = super().clean()
        plan_code = cleaned.get('plan_code')
        if plan_code:
            from core.plans import apply_plan_modules

            apply_plan_modules(self.instance, plan_code)
            cleaned['module_verificador'] = self.instance.module_verificador
            cleaned['module_alertas'] = self.instance.module_alertas
            cleaned['module_olt'] = self.instance.module_olt
        if not any([
            cleaned.get('module_verificador'),
            cleaned.get('module_alertas'),
            cleaned.get('module_olt'),
        ]):
            raise ValidationError('Selecione pelo menos um módulo para a empresa.')
        return cleaned

    def clean_cnpj(self):
        from .cnpj_utils import format_cnpj, cnpj_digits, hash_cnpj

        cnpj = self.cleaned_data.get('cnpj')
        if cnpj:
            cnpj_numbers = cnpj_digits(cnpj)
            if len(cnpj_numbers) != 14:
                raise ValidationError('CNPJ deve ter 14 dígitos')
            formatted = format_cnpj(cnpj_numbers)
            self.cleaned_data['cnpj'] = formatted
            h = hash_cnpj(cnpj_numbers)
            existing = Company.objects.filter(cnpj_hash=h)
            if self.instance.pk:
                existing = existing.exclude(pk=self.instance.pk)
            if existing.exists():
                raise ValidationError('Já existe uma empresa com este CNPJ')
        return self.cleaned_data.get('cnpj')

    def clean_email(self):
        email = self.cleaned_data.get('email', '').strip()
        if not email:
            raise ValidationError('Informe um e-mail válido.')
        if '@' not in email or email.startswith('@') or email.endswith('@'):
            raise ValidationError('E-mail inválido. Verifique o endereço informado.')
        return email

    def clean_phone(self):
        phone = self.cleaned_data.get('phone', '')
        if phone:
            digits = ''.join(filter(str.isdigit, phone))
            if len(digits) not in (10, 11):
                raise ValidationError('Telefone deve conter DDD + número (10 ou 11 dígitos).')
            ddd = digits[:2]
            if len(digits) == 10:
                number = f"{digits[2:6]}-{digits[6:]}"
            else:
                number = f"{digits[2:7]}-{digits[7:]}"
            formatted = f"({ddd}) {number}"
            self.cleaned_data['phone'] = formatted
        return self.cleaned_data.get('phone', '')

class CustomUserForm(UserCreationForm):
    email = forms.EmailField(required=True, label='E-mail')
    first_name = forms.CharField(max_length=30, required=True, label='Nome')
    last_name = forms.CharField(max_length=30, required=True, label='Sobrenome')
    phone = forms.CharField(max_length=20, required=False, label='Telefone')

    class Meta:
        model = CustomUser
        fields = ('username', 'email', 'first_name', 'last_name', 'phone', 'role', 'company', 'is_active')
        widgets = {
            'username': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nome de usuário'
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'email@exemplo.com'
            }),
            'first_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nome'
            }),
            'last_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Sobrenome'
            }),
            'phone': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '(11) 99999-9999',
                'maxlength': '15',
                'pattern': r'[\(][0-9]{2}[\)][ ][0-9]{4,5}[-][0-9]{4}',
                'title': 'Digite o telefone no formato (DDD) 99999-9999'
            }),
            'role': forms.Select(attrs={
                'class': 'form-control'
            }),
            'company': forms.Select(attrs={
                'class': 'form-control'
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            })
        }

    def __init__(self, *args, **kwargs):
        self.current_user = kwargs.pop('current_user', None)
        super().__init__(*args, **kwargs)
        
        # Remover campo de confirmação de senha
        if 'password2' in self.fields:
            del self.fields['password2']
        
        # Configurar campo de senha com gerador automático
        if 'password1' in self.fields:
            self.fields['password1'].required = False
            self.fields['password1'].label = 'Senha'
            
            # Verificar se é novo usuário ou edição
            # Se não tem instance ou instance não tem pk, é novo usuário
            if hasattr(self, 'instance') and self.instance and hasattr(self.instance, 'pk'):
                is_new_user = not self.instance.pk
            else:
                is_new_user = True
            
            # Se é novo usuário, usar senha alfanumérica (letras e números)
            # Se é edição, usar senha apenas números (padrão antigo)
            if is_new_user:
                help_text = 'Clique no botão "Gerar Senha" para criar uma senha aleatória de 8 caracteres (letras e números), ou deixe em branco para gerar automaticamente ao salvar.'
            else:
                help_text = 'Clique no botão "Gerar Senha" para criar uma senha aleatória de 8 dígitos, ou deixe em branco para gerar automaticamente ao salvar.'
            
            self.fields['password1'].help_text = help_text
            self.fields['password1'].widget = forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Clique em "Gerar Senha" ou deixe em branco',
                'readonly': True,
                'id': 'id_password1',
                'data-is-new-user': 'true' if is_new_user else 'false'
            })
        
        # Adicionar labels em português para todos os campos
        self.fields['username'].label = 'Usuário'
        if 'email' in self.fields:
            self.fields['email'].label = 'E-mail'
        if 'first_name' in self.fields:
            self.fields['first_name'].label = 'Nome'
        if 'last_name' in self.fields:
            self.fields['last_name'].label = 'Sobrenome'
        if 'phone' in self.fields:
            self.fields['phone'].label = 'Telefone'
        if 'role' in self.fields:
            self.fields['role'].label = 'Função'
        if 'company' in self.fields:
            self.fields['company'].label = 'Empresa'
        if 'is_active' in self.fields:
            self.fields['is_active'].label = 'Usuário ativo'
        
        # Configurar campos baseado no usuário atual
        if self.current_user:
            if self.current_user.is_rm_admin or self.current_user.is_superuser:
                # RM admin ou superuser podem criar qualquer tipo de usuário
                self.fields['role'].choices = CustomUser.USER_ROLES
                self.fields['company'].queryset = Company.objects.filter(is_active=True)
            elif self.current_user.is_company_admin:
                # Admin da empresa só pode criar usuários da empresa
                self.fields['role'].choices = [
                    ('COMPANY_ADMIN', 'Administrador da Empresa'),
                    ('COMPANY_USER', 'Usuário da Empresa')
                ]
                self.fields['company'].queryset = Company.objects.filter(
                    id=self.current_user.company.id
                )
                self.fields['company'].initial = self.current_user.company
                # Remove opção vazia para evitar submissão sem empresa
                self.fields['company'].empty_label = None
            else:
                # Usuários normais não podem criar outros usuários
                raise ValidationError('Sem permissão para criar usuários')

    def clean_phone(self):
        phone = self.cleaned_data.get('phone', '')
        if phone:
            # Remove caracteres não numéricos
            digits = ''.join(filter(str.isdigit, phone))
            # Valida se tem 10 ou 11 dígitos (DDD + número)
            if len(digits) not in (10, 11):
                raise ValidationError('Telefone deve conter DDD + número (10 ou 11 dígitos). Exemplo: (11) 99999-9999')
            # Valida DDD (deve ser entre 11 e 99)
            ddd = digits[:2]
            if not (11 <= int(ddd) <= 99):
                raise ValidationError('DDD inválido. Deve estar entre 11 e 99.')
            # Formatar no padrão brasileiro
            if len(digits) == 10:
                # Telefone fixo: (DDD) XXXX-XXXX
                number = f"{digits[2:6]}-{digits[6:]}"
            else:
                # Celular: (DDD) 9XXXX-XXXX
                number = f"{digits[2:7]}-{digits[7:]}"
            formatted = f"({ddd}) {number}"
            self.cleaned_data['phone'] = formatted
        return self.cleaned_data.get('phone', '')
    
    # Removido clean_password2 - não há mais campo de confirmação
    
    def clean(self):
        cleaned_data = super().clean()
        role = cleaned_data.get('role')
        company = cleaned_data.get('company')
        
        # Se senha não foi fornecida, gerar automaticamente
        password1 = cleaned_data.get('password1')
        if not password1:
            # Senha será gerada no save()
            pass
        
        # Superuser pode criar qualquer combinação sem bloqueios de formulário
        if self.current_user and getattr(self.current_user, 'is_superuser', False):
            return cleaned_data
        
        # Validações baseadas no role
        if role == 'RM' and company:
            self.add_error('company', 'Administradores RM não devem ter empresa associada.')
        elif role in ['COMPANY_ADMIN', 'COMPANY_USER'] and not company:
            self.add_error('company', 'Usuários de empresa devem ter uma empresa associada.')
        
        # Validações baseadas no usuário atual
        if self.current_user and self.current_user.is_company_admin:
            if company != self.current_user.company:
                self.add_error('company', 'Você só pode criar usuários para sua empresa.')
            # Garantir que role seja válido para empresa
            if role not in ['COMPANY_ADMIN', 'COMPANY_USER']:
                self.add_error('role', 'Role inválido para usuários de empresa.')
        
        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        user.phone = self.cleaned_data.get('phone', '')
        
        # Definir role e company antes de salvar
        user.role = self.cleaned_data.get('role', 'COMPANY_USER')
        user.company = self.cleaned_data.get('company', None)
        
        # Garantir que role e company estejam corretos antes de salvar
        # As validações do clean() do formulário já foram feitas
        # Garantir consistência: RM não deve ter empresa, COMPANY_ADMIN/USER devem ter
        if user.role == 'RM':
            user.company = None
            user.company_id = None
        
        # Gerar senha aleatória se não fornecida
        password1 = self.cleaned_data.get('password1', '').strip()
        
        # Verificar se é um novo usuário (não tem pk)
        is_new_user = not user.pk
        
        # Verificar se é superusuário ou usuário antigo (edição)
        is_old_user_or_superuser = user.pk and (user.is_superuser or not is_new_user)
        
        self._send_welcome_email = False
        self._generated_password = None

        if not password1:
            if is_new_user:
                generated_password = generate_random_password(
                    length=14, simple=True, alphanumeric=True
                )
                user.set_password(generated_password)
                self._generated_password = generated_password
                user.must_change_password = True
                self._send_welcome_email = bool(user.email)
            else:
                generated_password = generate_random_password(length=14, simple=False)
                user.set_password(generated_password)
                self._generated_password = generated_password
                user.must_change_password = True
        else:
            user.set_password(password1)
            if is_new_user:
                user.must_change_password = True
                self._generated_password = password1
                self._send_welcome_email = bool(user.email)
        
        # Salvar o usuário
        # O save() do modelo ajusta os dados automaticamente e não chama clean()
        if commit:
            try:
                user.save()
            except Exception as e:
                # Capturar qualquer erro e adicionar ao formulário
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Erro ao salvar usuário: {str(e)}", exc_info=True)
                
                error_message = str(e)
                
                # Tentar identificar o tipo de erro
                if 'unique constraint' in error_message.lower() or 'already exists' in error_message.lower() or 'duplicate key' in error_message.lower():
                    if 'username' in error_message.lower() or 'user' in error_message.lower():
                        self.add_error('username', 'Este nome de usuário já está em uso.')
                    elif 'email' in error_message.lower():
                        self.add_error('email', 'Este e-mail já está em uso.')
                    else:
                        self.add_error(None, 'Este registro já existe no sistema.')
                elif isinstance(e, ValidationError):
                    # Se for ValidationError, tratar adequadamente
                    if hasattr(e, 'error_dict') and e.error_dict:
                        for field, errors in e.error_dict.items():
                            for error in errors:
                                self.add_error(field, error)
                    elif hasattr(e, 'error_list') and e.error_list:
                        for error in e.error_list:
                            self.add_error(None, str(error))
                    else:
                        self.add_error(None, error_message)
                else:
                    # Outro erro - adicionar como erro geral
                    self.add_error(None, f'Erro ao salvar usuário: {error_message}')
                
                # Re-lançar como ValidationError para que a view saiba
                raise ValidationError(f'Erro ao salvar usuário: {error_message}') from e
        
        return user

class CustomUserChangeForm(forms.ModelForm):
    email = forms.EmailField(required=True)
    first_name = forms.CharField(max_length=30, required=True)
    last_name = forms.CharField(max_length=30, required=True)
    phone = forms.CharField(max_length=20, required=False)

    class Meta:
        model = CustomUser
        fields = ('username', 'email', 'first_name', 'last_name', 'phone', 'role', 'company', 'is_active')
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nome de usuário'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'email@exemplo.com'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nome'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Sobrenome'}),
            'phone': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '(11) 99999-9999',
                'maxlength': '15',
                'pattern': r'[\(][0-9]{2}[\)][ ][0-9]{4,5}[-][0-9]{4}',
                'title': 'Digite o telefone no formato (DDD) 99999-9999'
            }),
            'role': forms.Select(attrs={'class': 'form-control'}),
            'company': forms.Select(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'})
        }

    def __init__(self, *args, **kwargs):
        self.current_user = kwargs.pop('current_user', None)
        super().__init__(*args, **kwargs)
        
        # Adicionar labels em português para todos os campos
        self.fields['username'].label = 'Usuário'
        if 'email' in self.fields:
            self.fields['email'].label = 'E-mail'
        if 'first_name' in self.fields:
            self.fields['first_name'].label = 'Nome'
        if 'last_name' in self.fields:
            self.fields['last_name'].label = 'Sobrenome'
        if 'phone' in self.fields:
            self.fields['phone'].label = 'Telefone'
        if 'role' in self.fields:
            self.fields['role'].label = 'Função'
        if 'company' in self.fields:
            self.fields['company'].label = 'Empresa'
        if 'is_active' in self.fields:
            self.fields['is_active'].label = 'Usuário ativo'
        
        # Configurar campos baseado no usuário atual
        if self.current_user:
            if self.current_user.is_rm_admin or self.current_user.is_superuser:
                self.fields['role'].choices = CustomUser.USER_ROLES
                self.fields['company'].queryset = Company.objects.filter(is_active=True)
            elif self.current_user.is_company_admin:
                self.fields['role'].choices = [
                    ('COMPANY_ADMIN', 'Administrador da Empresa'),
                    ('COMPANY_USER', 'Usuário da Empresa')
                ]
                if self.current_user.company:
                    self.fields['company'].queryset = Company.objects.filter(id=self.current_user.company.id)
                    self.fields['company'].initial = self.current_user.company
                    self.fields['company'].empty_label = None
            else:
                raise ValidationError('Sem permissão para editar usuários')

    def clean_phone(self):
        phone = self.cleaned_data.get('phone', '')
        if phone:
            # Remove caracteres não numéricos
            digits = ''.join(filter(str.isdigit, phone))
            # Valida se tem 10 ou 11 dígitos (DDD + número)
            if len(digits) not in (10, 11):
                raise ValidationError('Telefone deve conter DDD + número (10 ou 11 dígitos). Exemplo: (11) 99999-9999')
            # Valida DDD (deve ser entre 11 e 99)
            ddd = digits[:2]
            if not (11 <= int(ddd) <= 99):
                raise ValidationError('DDD inválido. Deve estar entre 11 e 99.')
            # Formatar no padrão brasileiro
            if len(digits) == 10:
                # Telefone fixo: (DDD) XXXX-XXXX
                number = f"{digits[2:6]}-{digits[6:]}"
            else:
                # Celular: (DDD) 9XXXX-XXXX
                number = f"{digits[2:7]}-{digits[7:]}"
            formatted = f"({ddd}) {number}"
            self.cleaned_data['phone'] = formatted
        return self.cleaned_data.get('phone', '')
    
    def clean(self):
        cleaned_data = super().clean()
        role = cleaned_data.get('role')
        company = cleaned_data.get('company')
        
        # Superuser pode editar qualquer combinação
        if self.current_user and getattr(self.current_user, 'is_superuser', False):
            return cleaned_data
        
        if role == 'RM' and company:
            raise ValidationError('Administradores RM não devem ter empresa associada.')
        elif role in ['COMPANY_ADMIN', 'COMPANY_USER'] and not company:
            raise ValidationError('Usuários de empresa devem ter uma empresa associada.')
        
        if self.current_user and self.current_user.is_company_admin:
            if company != self.current_user.company:
                raise ValidationError('Você só pode editar usuários da sua empresa.')
            # Garantir que role seja válido para empresa
            if role not in ['COMPANY_ADMIN', 'COMPANY_USER']:
                raise ValidationError('Role inválido para usuários de empresa.')
        
        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        user.phone = self.cleaned_data.get('phone', '')
        if commit:
            user.save()
        return user


class TicketForm(forms.ModelForm):
    """Formulário para criar tickets"""
    
    class Meta:
        model = Ticket
        fields = ['title', 'description', 'priority']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Título do ticket'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 5,
                'placeholder': 'Descreva seu problema ou solicitação...'
            }),
            'priority': forms.Select(attrs={
                'class': 'form-select'
            })
        }
        labels = {
            'title': 'Título',
            'description': 'Descrição',
            'priority': 'Prioridade'
        }
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        self.company = kwargs.pop('company', None)
        super().__init__(*args, **kwargs)
        
        # Limitar prioridades disponíveis para clientes
        if self.user and not self.user.is_rm_admin:
            # Clientes podem escolher apenas baixa, normal ou alta
            self.fields['priority'].choices = [
                ('baixa', 'Baixa'),
                ('normal', 'Normal'),
                ('alta', 'Alta'),
            ]
    
    def clean(self):
        cleaned_data = super().clean()
        title = cleaned_data.get('title')
        description = cleaned_data.get('description')
        
        if title and len(title.strip()) < 5:
            raise ValidationError('O título deve ter pelo menos 5 caracteres.')
        
        if description and len(description.strip()) < 10:
            raise ValidationError('A descrição deve ter pelo menos 10 caracteres.')
        
        return cleaned_data


class TicketMessageForm(forms.ModelForm):
    """Formulário para adicionar mensagens ao ticket (chat)"""
    
    class Meta:
        model = TicketMessage
        fields = ['message']
        widgets = {
            'message': forms.Textarea(attrs={
                'class': 'form-control company-tickets-chat__textarea',
                'rows': 3,
                'placeholder': 'Escreva sua mensagem…',
                'required': True,
                'minlength': 1,
                'aria-label': 'Mensagem do ticket',
            })
        }
        labels = {
            'message': 'Mensagem'
        }
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        self.ticket = kwargs.pop('ticket', None)
        super().__init__(*args, **kwargs)
    
    def clean_message(self):
        message = self.cleaned_data.get('message')
        if message and len(message.strip()) < 1:
            raise ValidationError('A mensagem não pode estar vazia.')
        return message