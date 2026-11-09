from django.db import migrations


def create_fibramar_company(apps, schema_editor):
    Company = apps.get_model('core', 'Company')
    if not Company.objects.filter(slug='fibramar').exists():
        Company.objects.create(
            name='Fibramar',
            slug='fibramar',
            cnpj='00.000.000/0000-00',
            email='contato@fibramar.com.br',
            phone='',
            address=''
        )


def delete_fibramar_company(apps, schema_editor):
    Company = apps.get_model('core', 'Company')
    Company.objects.filter(slug='fibramar').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0003_alter_company_slug'),
    ]

    operations = [
        migrations.RunPython(create_fibramar_company, delete_fibramar_company),
    ]