# Generated migration for performance indexes

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0009_customuser_must_change_password'),
    ]

    operations = [
        # Indexes para CustomUser
        migrations.AddIndex(
            model_name='customuser',
            index=models.Index(fields=['company', 'role'], name='core_custom_company_role_idx'),
        ),
        migrations.AddIndex(
            model_name='customuser',
            index=models.Index(fields=['username'], name='core_custom_username_idx'),
        ),
        migrations.AddIndex(
            model_name='customuser',
            index=models.Index(fields=['email'], name='core_custom_email_idx'),
        ),
        
        # Indexes para Company
        migrations.AddIndex(
            model_name='company',
            index=models.Index(fields=['slug'], name='core_company_slug_idx'),
        ),
        migrations.AddIndex(
            model_name='company',
            index=models.Index(fields=['is_active', 'name'], name='core_company_active_name_idx'),
        ),
        migrations.AddIndex(
            model_name='company',
            index=models.Index(fields=['cnpj'], name='core_company_cnpj_idx'),
        ),
        
        # Indexes para CTOMapFile (se ainda não existirem)
        migrations.AddIndex(
            model_name='ctomapfile',
            index=models.Index(fields=['company', 'processing_status'], name='core_ctomapfile_company_status_idx'),
        ),
        migrations.AddIndex(
            model_name='ctomapfile',
            index=models.Index(fields=['uploaded_by', 'uploaded_at'], name='core_ctomapfile_user_uploaded_idx'),
        ),
        migrations.AddIndex(
            model_name='ctomapfile',
            index=models.Index(fields=['file_type', 'is_processed'], name='core_ctomapfile_type_processed_idx'),
        ),
    ]

