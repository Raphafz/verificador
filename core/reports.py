"""
Sistema de Relatórios Avançados para RM Systems SaaS
"""
from django.db.models import Count, Q, Avg, Sum
from django.utils import timezone
from datetime import timedelta, datetime
from django.http import HttpResponse
import csv
import json

from .models import Company, CustomUser, CTOMapFile

class ReportGenerator:
    """Gerador de relatórios avançados"""
    
    @staticmethod
    def get_dashboard_metrics(company=None):
        """Métricas do dashboard"""
        base_query = CTOMapFile.objects.all()
        if company:
            base_query = base_query.filter(company=company)
        
        now = timezone.now()
        this_month = now.replace(day=1)
        this_week = now - timedelta(days=7)
        
        return {
            'total_maps': base_query.count(),
            'maps_this_month': base_query.filter(uploaded_at__gte=this_month).count(),
            'maps_this_week': base_query.filter(uploaded_at__gte=this_week).count(),
            'success_rate': ReportGenerator._calculate_success_rate(base_query),
            'avg_processing_time': ReportGenerator._calculate_avg_processing_time(base_query),
            'top_file_types': ReportGenerator._get_top_file_types(base_query),
            'upload_trends': ReportGenerator._get_upload_trends(base_query, 30)
        }
    
    @staticmethod
    def get_company_metrics(company):
        """Métricas específicas da empresa"""
        users = CustomUser.objects.filter(company=company)
        maps = CTOMapFile.objects.filter(company=company)
        
        return {
            'company_info': {
                'name': company.name,
                'created_at': company.created_at,
                'total_users': users.count(),
                'active_users': users.filter(is_active=True).count(),
                'inactive_users': users.filter(is_active=False).count()
            },
            'map_statistics': {
                'total_maps': maps.count(),
                'by_file_type': ReportGenerator._get_file_type_distribution(maps),
                'by_status': ReportGenerator._get_status_distribution(maps),
                'upload_frequency': ReportGenerator._get_upload_frequency(maps),
                'largest_files': ReportGenerator._get_largest_files(maps, 10)
            },
            'user_activity': {
                'recent_logins': ReportGenerator._get_recent_logins(users),
                'user_roles': ReportGenerator._get_user_role_distribution(users),
                'inactive_users': ReportGenerator._get_inactive_users(users)
            },
            'performance_metrics': {
                'avg_file_size': ReportGenerator._calculate_avg_file_size(maps),
                'processing_success_rate': ReportGenerator._calculate_processing_success_rate(maps),
                'peak_upload_times': ReportGenerator._get_peak_upload_times(maps)
            }
        }
    
    @staticmethod
    def get_system_wide_metrics():
        """Métricas do sistema completo"""
        companies = Company.objects.all()
        users = CustomUser.objects.all()
        maps = CTOMapFile.objects.all()
        
        return {
            'system_overview': {
                'total_companies': companies.count(),
                'total_users': users.count(),
                'total_maps': maps.count(),
                'active_companies': companies.filter(
                    customuser__is_active=True
                ).distinct().count()
            },
            'company_rankings': ReportGenerator._get_company_rankings(companies),
            'usage_statistics': {
                'maps_by_company': ReportGenerator._get_maps_by_company(companies),
                'users_by_company': ReportGenerator._get_users_by_company(companies),
                'growth_metrics': ReportGenerator._get_growth_metrics(companies, users, maps)
            },
            'file_analysis': {
                'total_file_size': maps.aggregate(total=Sum('file_size'))['total'] or 0,
                'avg_file_size': maps.aggregate(avg=Avg('file_size'))['avg'] or 0,
                'file_type_distribution': ReportGenerator._get_file_type_distribution(maps),
                'upload_patterns': ReportGenerator._get_upload_patterns(maps)
            }
        }
    
    @staticmethod
    def _calculate_success_rate(query):
        """Calcula taxa de sucesso"""
        total = query.count()
        if total == 0:
            return 0
        
        successful = query.filter(status='processed').count()
        return round((successful / total) * 100, 2)
    
    @staticmethod
    def _calculate_avg_processing_time(query):
        """Calcula tempo médio de processamento"""
        processed_maps = query.filter(status='processed')
        if not processed_maps.exists():
            return 0
        
        # Simular tempo de processamento baseado no tamanho do arquivo
        total_time = 0
        for map_file in processed_maps:
            if map_file.file_size:
                # Estimativa: 1 segundo por MB
                estimated_time = map_file.file_size / (1024 * 1024)
                total_time += estimated_time
        
        return round(total_time / processed_maps.count(), 2)
    
    @staticmethod
    def _get_top_file_types(query, limit=5):
        """Top tipos de arquivo"""
        return list(query.values('file_type').annotate(
            count=Count('id')
        ).order_by('-count')[:limit])
    
    @staticmethod
    def _get_upload_trends(query, days=30):
        """Tendências de upload"""
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)
        
        trends = []
        for i in range(days):
            date = start_date + timedelta(days=i)
            count = query.filter(
                uploaded_at__date=date.date()
            ).count()
            trends.append({
                'date': date.strftime('%Y-%m-%d'),
                'count': count
            })
        
        return trends
    
    @staticmethod
    def _get_file_type_distribution(query):
        """Distribuição por tipo de arquivo"""
        return list(query.values('file_type').annotate(
            count=Count('id')
        ).order_by('-count'))
    
    @staticmethod
    def _get_status_distribution(query):
        """Distribuição por status"""
        return list(query.values('status').annotate(
            count=Count('id')
        ).order_by('-count'))
    
    @staticmethod
    def _get_upload_frequency(query):
        """Frequência de uploads"""
        now = timezone.now()
        return {
            'daily': query.filter(uploaded_at__gte=now - timedelta(days=1)).count(),
            'weekly': query.filter(uploaded_at__gte=now - timedelta(days=7)).count(),
            'monthly': query.filter(uploaded_at__gte=now - timedelta(days=30)).count()
        }
    
    @staticmethod
    def _get_largest_files(query, limit=10):
        """Maiores arquivos"""
        return list(query.order_by('-file_size')[:limit].values(
            'original_filename', 'file_size', 'uploaded_at'
        ))
    
    @staticmethod
    def _get_recent_logins(users):
        """Logins recentes"""
        return list(users.filter(
            last_login__isnull=False
        ).order_by('-last_login')[:10].values(
            'username', 'last_login'
        ))
    
    @staticmethod
    def _get_user_role_distribution(users):
        """Distribuição de roles"""
        return list(users.values('role').annotate(
            count=Count('id')
        ).order_by('-count'))
    
    @staticmethod
    def _get_inactive_users(users):
        """Usuários inativos"""
        return list(users.filter(is_active=False).values(
            'username', 'email', 'last_login'
        ))
    
    @staticmethod
    def _calculate_avg_file_size(query):
        """Tamanho médio dos arquivos"""
        result = query.aggregate(avg=Avg('file_size'))
        return round(result['avg'] or 0, 2)
    
    @staticmethod
    def _calculate_processing_success_rate(query):
        """Taxa de sucesso do processamento"""
        total = query.count()
        if total == 0:
            return 0
        
        successful = query.filter(status='processed').count()
        return round((successful / total) * 100, 2)
    
    @staticmethod
    def _get_peak_upload_times(query):
        """Horários de pico de upload"""
        # Agrupar por hora do dia
        hourly_uploads = {}
        for map_file in query:
            hour = map_file.uploaded_at.hour
            hourly_uploads[hour] = hourly_uploads.get(hour, 0) + 1
        
        # Encontrar os 3 horários com mais uploads
        sorted_hours = sorted(hourly_uploads.items(), key=lambda x: x[1], reverse=True)
        return sorted_hours[:3]
    
    @staticmethod
    def _get_company_rankings(companies):
        """Ranking de empresas"""
        return list(companies.annotate(
            user_count=Count('customuser'),
            map_count=Count('ctomapfile')
        ).order_by('-map_count')[:10])
    
    @staticmethod
    def _get_maps_by_company(companies):
        """Mapas por empresa"""
        return list(companies.annotate(
            map_count=Count('ctomapfile')
        ).order_by('-map_count'))
    
    @staticmethod
    def _get_users_by_company(companies):
        """Usuários por empresa"""
        return list(companies.annotate(
            user_count=Count('customuser')
        ).order_by('-user_count'))
    
    @staticmethod
    def _get_growth_metrics(companies, users, maps):
        """Métricas de crescimento"""
        now = timezone.now()
        last_month = now - timedelta(days=30)
        
        return {
            'new_companies_this_month': companies.filter(
                created_at__gte=last_month
            ).count(),
            'new_users_this_month': users.filter(
                date_joined__gte=last_month
            ).count(),
            'new_maps_this_month': maps.filter(
                uploaded_at__gte=last_month
            ).count()
        }
    
    @staticmethod
    def _get_upload_patterns(query):
        """Padrões de upload"""
        now = timezone.now()
        patterns = {
            'by_day_of_week': {},
            'by_hour': {},
            'by_month': {}
        }
        
        for map_file in query:
            # Por dia da semana
            day = map_file.uploaded_at.strftime('%A')
            patterns['by_day_of_week'][day] = patterns['by_day_of_week'].get(day, 0) + 1
            
            # Por hora
            hour = map_file.uploaded_at.hour
            patterns['by_hour'][hour] = patterns['by_hour'].get(hour, 0) + 1
            
            # Por mês
            month = map_file.uploaded_at.strftime('%Y-%m')
            patterns['by_month'][month] = patterns['by_month'].get(month, 0) + 1
        
        return patterns

class ExportManager:
    """Gerenciador de exportação de relatórios"""
    
    @staticmethod
    def export_to_csv(data, filename):
        """Exportar dados para CSV"""
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        writer = csv.writer(response)
        
        # Escrever cabeçalhos
        if data:
            writer.writerow(data[0].keys())
            
            # Escrever dados
            for row in data:
                writer.writerow(row.values())
        
        return response
    
    @staticmethod
    def export_to_json(data, filename):
        """Exportar dados para JSON"""
        response = HttpResponse(
            json.dumps(data, indent=2, default=str),
            content_type='application/json'
        )
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response
