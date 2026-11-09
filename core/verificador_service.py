"""
Serviço de verificação de viabilidade (Migrado para Django)
Agora usa serviços Django nativos ao invés de Flask
"""
import os
import logging
import uuid
from typing import Dict, Any, Optional, List
from django.conf import settings
from django.core.files.uploadedfile import UploadedFile
from django.utils import timezone
from core.models import CTOMapFile, Company, CustomUser
from core.audit_logger import AuditLogger
from core.security_validators import SecureFileValidator
# Substitui integrações antigas do app 'verificador' pelo novo 'ftth_viewer'
from ftth_viewer import utils as ftth_utils

logger = logging.getLogger(__name__)


class VerificadorService:
    """
    Serviço principal de verificação - agora Django native
    Mantém interface compatível com código existente
    """
    
    @classmethod
    def verificar_arquivo(cls, uploaded_file: UploadedFile, company: Company, user: CustomUser) -> Dict[str, Any]:
        """
        Verifica viabilidade de um arquivo CTO usando Django native
        
        Args:
            uploaded_file: Arquivo enviado pelo usuário
            company: Empresa do usuário
            user: Usuário que fez o upload
            
        Returns:
            Dict com resultados da análise
        """
        temp_path = None
        validator = SecureFileValidator()

        try:
            validator.validate_file(uploaded_file)
            uploaded_file.seek(0)
            # Salvar arquivo temporariamente
            temp_path = cls._save_temp_file(uploaded_file)
            file_type = cls._get_file_extension(uploaded_file.name)
            
            # Usar serviço Django nativo (ftth_viewer utils)
            coords = cls._ler_arquivo_por_extensao(temp_path)
            processing_time = None  # opcional: medição se necessário
            viability_score = min(100, max(0, 100 - len(coords) * 0.1))
            result = {
                'success': True,
                'results': {
                    'viability_score': int(viability_score),
                    'issues': ["Nenhuma coordenada encontrada no arquivo"] if len(coords) == 0 else ([] if len(coords) <= 1000 else ["Muitas coordenadas podem impactar a performance"]),
                    'recommendations': (["Verifique o formato do arquivo"] if len(coords) == 0 else ([] if len(coords) <= 1000 else ["Considere dividir o arquivo em partes menores"])),
                    'coordinates_count': len(coords),
                    'processing_time': processing_time or 0,
                    'file_info': {
                        'name': uploaded_file.name,
                        'type': cls._get_file_extension(uploaded_file.name),
                        'size': uploaded_file.size,
                    }
                }
            }
            
            # Log da ação
            AuditLogger.log_user_action(
                user=user,
                action='map_analysis',
                details={
                    'file_name': uploaded_file.name,
                    'file_size': uploaded_file.size,
                    'company': company.name,
                    'success': result.get('success', False),
                    'service': 'django_native'
                }
            )
        except Exception as e:
            logger.error(f"Erro na verificação Django: {str(e)}")
            result = {
                'success': False,
                'error': f'Erro na análise: {str(e)}',
                'status': 'failed'
            }
        finally:
            # Sempre limpar arquivo temporário, mesmo em caso de erro
            if temp_path:
                cls._cleanup_temp_file(temp_path)
        
        # Adicionar analysis_id se não existir
        if result and result.get('success') and 'analysis_id' not in result:
            result['analysis_id'] = str(uuid.uuid4())
            result['status'] = 'completed'
        
        return result
    
    @classmethod
    def verificar_coordenadas(cls, lat: float, lon: float, company: Company, user: CustomUser) -> Dict[str, Any]:
        """
        Verifica viabilidade de coordenadas específicas usando Django native
        
        Args:
            lat: Latitude
            lon: Longitude
            company: Empresa do usuário
            user: Usuário que fez a verificação
            
        Returns:
            Dict com resultados da análise
        """
        try:
            # Usar serviço Django nativo (ftth_viewer utils)
            # Estratégia: semelhante ao ftth_viewer.views.api_verificar_viabilidade
            # Passar a empresa para filtrar CTOs corretos
            ctos = ftth_utils.get_all_ctos(company=company)
            if not ctos:
                return {
                    'success': False,
                    'error': 'Nenhum CTO encontrado',
                    'status': 'failed'
                }

            ctos_com_distancia = []
            for cto in ctos:
                try:
                    cto_lat = float(cto.get('lat'))
                    cto_lon = float(cto.get('lng'))
                    distancia_euclidiana = ftth_utils.calcular_distancia(lat, lon, cto_lat, cto_lon)
                    ctos_com_distancia.append({**cto, 'distancia_euclidiana': distancia_euclidiana})
                except (ValueError, TypeError, KeyError):
                    continue
            if not ctos_com_distancia:
                return {
                    'success': False,
                    'error': 'Nenhum CTO válido encontrado',
                    'status': 'failed'
                }

            ctos_com_distancia.sort(key=lambda x: x['distancia_euclidiana'])
            candidatos = ctos_com_distancia[:min(5, len(ctos_com_distancia))]

            from concurrent.futures import ThreadPoolExecutor, as_completed
            melhor = None
            menor_dist = float('inf')
            melhor_geom = None
            with ThreadPoolExecutor(max_workers=4) as executor:
                futures = {
                    executor.submit(ftth_utils.calcular_rota_ruas_single, lat, lon, float(c.get('lat')), float(c.get('lng')), c): c
                    for c in candidatos
                }
                for future in as_completed(futures):
                    try:
                        dist_ruas, geom, cto_info = future.result()
                        if dist_ruas < menor_dist:
                            menor_dist = dist_ruas
                            melhor = cto_info
                            melhor_geom = geom
                    except Exception:
                        continue

            if not melhor:
                return {
                    'success': False,
                    'error': 'Nenhum CTO válido encontrado',
                    'status': 'failed'
                }

            viabilidade = ftth_utils.classificar_viabilidade(menor_dist)
            resultado = {
                'viabilidade': viabilidade,
                'cto': {
                    'nome': melhor.get('nome', 'CTO'),
                    'lat': float(melhor['lat']),
                    'lon': float(melhor['lng']),
                    'arquivo': melhor.get('arquivo', ''),
                },
                'distancia': {
                    'metros': round(menor_dist, 2),
                    'km': round(menor_dist / 1000, 3),
                },
                'rota': {'geometria': melhor_geom},
            }

            return {
                'success': True,
                'status': 'completed',
                'results': resultado,
            }
            
        except Exception as e:
            logger.error(f"Erro na verificação de coordenadas: {str(e)}")
            return {
                'success': False,
                'error': f'Erro na análise: {str(e)}',
                'status': 'failed'
            }
    
    @classmethod
    def listar_arquivos_disponiveis(cls) -> List[Dict[str, Any]]:
        """
        Lista arquivos disponíveis no sistema Django
        
        Returns:
            Lista de arquivos disponíveis
        """
        try:
            arquivos = []
            mapas = CTOMapFile.objects.filter(is_processed=True).select_related('company')
            
            for mapa in mapas:
                if mapa.file:
                    arquivos.append({
                        'nome': mapa.file_name,
                        'tipo': mapa.file_type,
                        'company': mapa.company.name,
                        'uploaded_at': mapa.uploaded_at.isoformat() if mapa.uploaded_at else None
                    })
            
            return arquivos
            
        except Exception as e:
            logger.error(f"Erro ao listar arquivos: {str(e)}")
            return []
    
    @classmethod
    def obter_coordenadas_arquivo(cls, arquivo: str) -> List[Dict[str, Any]]:
        """
        Obtém coordenadas de um arquivo específico
        
        Args:
            arquivo: Nome do arquivo
            
        Returns:
            Lista de coordenadas
        """
        try:
            # Buscar arquivo no Django
            mapa = CTOMapFile.objects.filter(file__icontains=arquivo).first()
            
            if mapa and mapa.file and hasattr(mapa.file, 'path'):
                return cls._ler_arquivo_por_extensao(mapa.file.path)
            
            return []
            
        except Exception as e:
            logger.error(f"Erro ao obter coordenadas: {str(e)}")
            return []
    
    @classmethod
    def geocodificar_endereco(cls, endereco: str) -> Dict[str, Any]:
        """
        Geocodifica um endereço usando Django native
        
        Args:
            endereco: Endereço para geocodificar
            
        Returns:
            Coordenadas do endereço
        """
        try:
            resultado = cls._geocodificar(endereco)
            
            if resultado:
                return resultado
            else:
                return {'error': 'Endereço não encontrado'}
                
        except Exception as e:
            logger.error(f"Erro na geocodificação: {str(e)}")
            return {'error': f'Erro na geocodificação: {str(e)}'}
    
    @classmethod
    def verificar_status_flask(cls) -> Dict[str, Any]:
        """
        Verifica se o serviço está funcionando
        Retorna status Django (sempre online agora)
        """
        return {
            'status': 'online',
            'service': 'django_native',
            'flask_response': {'migrated': True}
        }
    
    @classmethod
    def _save_temp_file(cls, uploaded_file: UploadedFile) -> str:
        """
        Salva arquivo temporariamente para análise
        
        Args:
            uploaded_file: Arquivo enviado
            
        Returns:
            Caminho do arquivo temporário
        """
        # Criar diretório temporário se não existir
        temp_dir = os.path.join(settings.MEDIA_ROOT, 'temp_verificacao')
        os.makedirs(temp_dir, exist_ok=True)
        
        # Gerar nome único para o arquivo
        safe_name = os.path.basename(uploaded_file.name)
        temp_filename = f"{uuid.uuid4()}_{safe_name}"
        temp_path = os.path.join(temp_dir, temp_filename)
        
        # Salvar arquivo
        with open(temp_path, 'wb') as f:
            for chunk in uploaded_file.chunks():
                f.write(chunk)
        
        return temp_path
    
    @classmethod
    def _cleanup_temp_file(cls, temp_path: str):
        """
        Remove arquivo temporário de forma segura
        
        Args:
            temp_path: Caminho do arquivo temporário
        """
        try:
            if temp_path and os.path.exists(temp_path):
                os.remove(temp_path)
                logger.debug(f"Arquivo temporário removido: {temp_path}")
        except PermissionError as e:
            logger.warning(f"Sem permissão para remover arquivo temporário {temp_path}: {e}")
            # Tentar novamente após um pequeno delay (arquivo pode estar em uso)
            import time
            time.sleep(0.1)
            try:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
            except Exception as retry_error:
                logger.error(f"Falha ao remover arquivo temporário após retry {temp_path}: {retry_error}")
        except Exception as e:
            logger.error(f"Erro inesperado ao remover arquivo temporário {temp_path}: {e}")
    
    @classmethod
    def _get_file_extension(cls, filename: str) -> str:
        """
        Obtém extensão do arquivo
        
        Args:
            filename: Nome do arquivo
            
        Returns:
            Extensão do arquivo
        """
        return filename.split('.')[-1].lower() if '.' in filename else ''

    @classmethod
    def _ler_arquivo_por_extensao(cls, caminho_arquivo: str):
        ext = cls._get_file_extension(caminho_arquivo).lower()
        if ext == 'kml':
            return ftth_utils.ler_kml(caminho_arquivo)
        if ext == 'kmz':
            return ftth_utils.ler_kmz(caminho_arquivo)
        if ext == 'csv':
            return ftth_utils.ler_csv(caminho_arquivo)
        if ext in ('xls', 'xlsx'):
            return ftth_utils.ler_excel(caminho_arquivo)
        return []

    @classmethod
    def _geocodificar(cls, endereco: str):
        # Usa cache persistente do ftth_viewer e fallback para Nominatim
        cached = ftth_utils.get_cached_geocoding(endereco)
        if cached:
            return cached
        import requests
        url = "https://nominatim.openstreetmap.org/search"
        params = { 'q': endereco, 'format': 'json', 'limit': 1, 'countrycodes': 'br' }
        headers = { 'User-Agent': 'FTTH-Viewer-Django/1.0' }
        resp = requests.get(url, params=params, headers=headers, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if not data:
            return None
        res = {
            'lat': float(data[0]['lat']),
            'lng': float(data[0]['lon']),
            'endereco_completo': data[0]['display_name'],
        }
        ftth_utils.set_cached_geocoding(endereco, res)
        return res


class VerificadorIntegrationManager:
    """Gerenciador de integração - agora Django native"""
    
    @classmethod
    def processar_upload_arquivo(cls, uploaded_file: UploadedFile, company: Company, user: CustomUser) -> Dict[str, Any]:
        """
        Processa upload de arquivo completo usando Django native
        
        Args:
            uploaded_file: Arquivo enviado
            company: Empresa do usuário
            user: Usuário que fez o upload
            
        Returns:
            Resultado completo do processamento
        """
        validator = SecureFileValidator()

        try:
            validator.validate_file(uploaded_file)
            uploaded_file.seek(0)
            # 1. Criar registro no banco Django
            cto_file = CTOMapFile.objects.create(
                file=uploaded_file,
                description=f"Análise de {uploaded_file.name}",
                company=company,
                uploaded_by=user,
                is_processed=False
            )
            
            # 2. Verificar arquivo usando Django native
            result = VerificadorService.verificar_arquivo(uploaded_file, company, user)
            
            # 3. Atualizar registro Django com resultado
            if result.get('success'):
                cto_file.is_processed = True
                cto_file.processed_at = timezone.now()
                
                # Salvar dados do resultado
                results = result.get('results', {})
                cto_file.viability_score = results.get('viability_score')
                cto_file.analysis_results = results
                cto_file.issues_found = results.get('issues', [])
                cto_file.recommendations = results.get('recommendations', [])
                cto_file.coordinates_count = results.get('coordinates_count', 0)
                cto_file.processing_time = results.get('processing_time')
                
                if results.get('file_info'):
                    cto_file.file_size = results['file_info'].get('size')
                
                cto_file.description = f"Análise concluída - {results.get('viability_score', 'N/A')} pontos"
                cto_file.save()
            
            return {
                'success': result.get('success', False),
                'cto_file_id': cto_file.id,
                'django_result': result,
                'service': 'django_native'
            }
            
        except Exception as e:
            logger.error(f"Erro no processamento completo: {str(e)}")
            return {
                'success': False,
                'error': f'Erro no processamento: {str(e)}'
            }
    
    @classmethod
    def obter_estatisticas_integracao(cls) -> Dict[str, Any]:
        """
        Obtém estatísticas da integração Django
        
        Returns:
            Estatísticas da integração
        """
        try:
            # Estatísticas Django
            total_files = CTOMapFile.objects.count()
            processed_files = CTOMapFile.objects.filter(is_processed=True).count()
            
            return {
                'service_status': {
                    'status': 'online',
                    'service': 'django_native',
                    'migrated_from_flask': True
                },
                'django_stats': {
                    'total_files': total_files,
                    'processed_files': processed_files,
                    'processing_rate': (processed_files / total_files * 100) if total_files > 0 else 0
                },
                'integration_active': True
            }
            
        except Exception as e:
            logger.error(f"Erro ao obter estatísticas: {str(e)}")
            return {
                'error': str(e),
                'integration_active': False
            }