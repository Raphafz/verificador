# Generated migration for db_index fields
# Esta migração adiciona db_index=True aos campos que foram criados sem índice
# na migração inicial mas agora têm db_index=True no modelo

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0010_add_performance_indexes'),
    ]

    operations = [
        # Alterar campos para adicionar db_index=True
        # Isso garante que o Django reconheça que os campos têm índices
        
        # CustomUser.created_at - adicionar db_index=True
        migrations.AlterField(
            model_name='customuser',
            name='created_at',
            field=models.DateTimeField(auto_now_add=True, db_index=True, verbose_name='Criado em'),
        ),
        
        # CTOMapFile.uploaded_at - adicionar db_index=True
        migrations.AlterField(
            model_name='ctomapfile',
            name='uploaded_at',
            field=models.DateTimeField(auto_now_add=True, db_index=True, verbose_name='Enviado em'),
        ),
        
        # Adicionar índices explícitos também (para garantir que existam no banco)
        migrations.AddIndex(
            model_name='customuser',
            index=models.Index(fields=['created_at'], name='core_customuser_created_at_idx'),
        ),
        
        migrations.AddIndex(
            model_name='ctomapfile',
            index=models.Index(fields=['uploaded_at'], name='core_ctomapfile_uploaded_at_idx'),
        ),
    ]

