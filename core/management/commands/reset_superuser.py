from django.core.management.base import BaseCommand
from core.models import CustomUser
from django.contrib.auth.hashers import make_password


class Command(BaseCommand):
    help = 'Deleta e recria um superusuário'

    def add_arguments(self, parser):
        parser.add_argument('email', type=str, help='Email do usuário')
        parser.add_argument('password', type=str, help='Senha do usuário')
        parser.add_argument('--username', type=str, help='Username (opcional, usa email se não fornecido)')

    def handle(self, *args, **options):
        email = options['email']
        password = options['password']
        username = options.get('username') or email.split('@')[0]

        # Deletar usuário existente se existir
        try:
            user = CustomUser.objects.get(email=email)
            self.stdout.write(f'🗑️  Deletando usuário existente: {user.username} ({user.email})')
            user.delete()
            self.stdout.write(self.style.SUCCESS(f'✅ Usuário deletado com sucesso!'))
        except CustomUser.DoesNotExist:
            self.stdout.write(f'ℹ️  Usuário com email {email} não existe. Criando novo usuário...')
        except CustomUser.MultipleObjectsReturned:
            # Se houver múltiplos usuários com o mesmo email, deletar todos
            users = CustomUser.objects.filter(email=email)
            self.stdout.write(f'⚠️  Encontrados {users.count()} usuários com email {email}. Deletando todos...')
            for user in users:
                self.stdout.write(f'🗑️  Deletando usuário: {user.username} ({user.email})')
                user.delete()
            self.stdout.write(self.style.SUCCESS(f'✅ Todos os usuários deletados!'))

        # Verificar se o username já existe (caso o email seja diferente)
        try:
            existing_user = CustomUser.objects.get(username=username)
            if existing_user.email != email:
                self.stdout.write(f'⚠️  Username {username} já existe com email diferente ({existing_user.email}).')
                self.stdout.write(f'🗑️  Deletando usuário com username {username}...')
                existing_user.delete()
                self.stdout.write(self.style.SUCCESS(f'✅ Usuário com username {username} deletado!'))
        except CustomUser.DoesNotExist:
            pass

        # Criar novo superusuário
        try:
            user = CustomUser.objects.create_user(
                username=username,
                email=email,
                password=password,
                role='RM',
                is_superuser=True,
                is_staff=True,
                is_active=True,
                company=None  # RM não deve ter empresa
            )
            self.stdout.write(self.style.SUCCESS(f'✅ Superusuário criado com sucesso!'))
            self.stdout.write(f'   Username: {user.username}')
            self.stdout.write(f'   Email: {user.email}')
            self.stdout.write(f'   Role: {user.role}')
            self.stdout.write(f'   is_superuser: {user.is_superuser}')
            self.stdout.write(f'   is_staff: {user.is_staff}')
            self.stdout.write(f'   is_active: {user.is_active}')
            self.stdout.write(f'   is_rm_admin: {user.is_rm_admin}')
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'❌ Erro ao criar usuário: {str(e)}'))
            raise

