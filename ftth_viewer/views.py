"""
Views Django para FTTH Viewer
"""
import os
import requests
import logging
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse, HttpResponse, Http404
from django.views.decorators.http import require_http_methods
from django.views.decorators.cache import cache_page
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
from django.db.models import Q
from concurrent.futures import ThreadPoolExecutor, as_completed
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import ensure_csrf_cookie
from functools import wraps

from core.json_responses import MSG_GENERIC, json_error
from core.permissions import rm_admin_required_json

logger = logging.getLogger(__name__)

from .utils import (
    ler_kml, ler_kmz, ler_csv, ler_excel, filtrar_coordenadas_brasil,
    calcular_distancia, calcular_rota_ruas_single, classificar_viabilidade,
    get_all_ctos, get_arquivo_caminho, get_cached_geocoding, set_cached_geocoding,
    invalidate_ftth_map_caches,
    remover_cto_do_mapa, normalize_address, generate_search_variations
)
from .models import ViabilidadeCache
from core.models import CTOMapFile, Company


@login_required
def index(request, company_slug=None):
    """Página principal do FTTH Viewer"""
    context = {
        'company_slug': company_slug,
    }
    return render(request, 'ftth_viewer/index.html', context)


@login_required
@require_http_methods(["GET"])
def api_arquivos(request, company_slug=None):
    """Lista todos os arquivos disponíveis apenas do banco de dados (enviados via upload)"""
    user = request.user
    
    # Permitir bypass do cache com parâmetro refresh
    force_refresh = request.GET.get('refresh', 'false').lower() == 'true'
    
    # Cache baseado no usuário e empresa
    cache_key = f'api_arquivos_{user.id}_{company_slug or (user.company.slug if user.company else "none")}'
    
    if not force_refresh:
        cached_result = cache.get(cache_key)
        if cached_result is not None:
            return JsonResponse(cached_result, safe=False)
    
    # Determinar empresa a ser listada
    target_company_slug = company_slug
    if not target_company_slug:
        if user.is_rm_admin or user.is_superuser:
            # RM Admin sem company_slug: tentar usar 'fibramar' como padrão
            target_company_slug = getattr(settings, 'DEFAULT_COMPANY_SLUG', 'fibramar')
        else:
            # Usuário normal usa empresa dele
            if not user.company:
                return JsonResponse({'erro': 'Usuário não está associado a uma empresa'}, status=403)
            target_company_slug = user.company.slug
    
    # Verificar permissões
    if not user.is_rm_admin and not user.is_superuser:
        if not user.company:
            return JsonResponse({'erro': 'Usuário não está associado a uma empresa'}, status=403)
        if target_company_slug != user.company.slug:
            return JsonResponse({'erro': 'Acesso negado à empresa'}, status=403)
    
    arquivos = []
    
    # Primeiro, tentar buscar do banco de dados
    try:
        if user.is_rm_admin or user.is_superuser:
            if target_company_slug:
                try:
                    company = Company.objects.only('id', 'name', 'slug').get(slug=target_company_slug)
                    maps = CTOMapFile.objects.filter(company=company).select_related('company').order_by('-uploaded_at')
                except Company.DoesNotExist:
                    maps = CTOMapFile.objects.none()
            else:
                # RM Admin sem company_slug específico: retornar apenas mapas da empresa do usuário (se tiver)
                # OU retornar erro se não tiver empresa associada
                if user.company:
                    maps = CTOMapFile.objects.filter(company=user.company).select_related('company').order_by('-uploaded_at')
                else:
                    # RM Admin sem empresa: não retornar mapas (precisa especificar empresa)
                    maps = CTOMapFile.objects.none()
        else:
            if not user.company:
                return JsonResponse({'erro': 'Usuário não está associado a uma empresa'}, status=403)
            maps = CTOMapFile.objects.filter(company=user.company).select_related('company').order_by('-uploaded_at')
        
        # Processar arquivos do banco
        for mapa in maps:
            if mapa.file:
                arquivos.append({
                    'nome': mapa.file_name,
                    'tipo': mapa.file_type,
                    'id': mapa.id,
                })
    except Exception as e:
        # Se houver erro ao acessar o banco, logar mas não buscar de pastas antigas
        logger.exception("Erro ao acessar banco de dados em api_arquivos: %s", e)
        # Não buscar mais de pastas antigas - apenas do banco de dados
    
    # Cachear resultado por 2 minutos
    result = arquivos
    cache.set(cache_key, result, 120)
    
    return JsonResponse(result, safe=False)


@login_required
@require_http_methods(["GET"])
def api_coordenadas(request, company_slug=None):
    """Retorna coordenadas de um arquivo específico apenas do banco de dados"""
    try:
        arquivo_nome = request.GET.get('arquivo')
        map_id = request.GET.get('id')  # ID do mapa no banco de dados
        
        logger.debug(f"api_coordenadas: map_id={map_id}, arquivo={arquivo_nome}, company_slug={company_slug}, user={request.user.username if request.user.is_authenticated else 'anon'}")
        
        if not arquivo_nome and not map_id:
            return JsonResponse({'erro': 'Arquivo não especificado'}, status=400)
        
        force_refresh = request.GET.get('refresh', 'false').lower() == 'true'
        cache_key = f'api_coordenadas_{map_id or arquivo_nome}_{company_slug or "none"}'
        if not force_refresh:
            cached_coords = cache.get(cache_key)
            if cached_coords is not None:
                return JsonResponse(cached_coords, safe=False)
        
        user = request.user
        caminho = None
        ext = None
        
        # Determinar empresa - SEMPRE exigir empresa
        target_company = None
        if company_slug:
            try:
                target_company = Company.objects.get(slug=company_slug, is_active=True)
            except Company.DoesNotExist:
                return JsonResponse({'erro': 'Empresa não encontrada'}, status=404)
        elif user.is_authenticated:
            # Para usuários normais, SEMPRE usar a empresa deles
            if not user.is_rm_admin and not user.is_superuser:
                if not user.company:
                    return JsonResponse({'erro': 'Usuário não está associado a uma empresa'}, status=403)
                target_company = user.company
            # RM Admins: se não tiver company_slug, usar empresa do usuário se existir
            elif user.company:
                target_company = user.company
            else:
                return JsonResponse({'erro': 'É necessário especificar a empresa'}, status=400)
        else:
            return JsonResponse({'erro': 'Usuário não autenticado'}, status=401)
        
        if not target_company:
            return JsonResponse({'erro': 'Empresa não especificada'}, status=400)
        
        # Buscar do banco de dados - SEMPRE filtrar por empresa
        try:
            if map_id:
                # Buscar por ID (preferencial) - SEMPRE verificar se pertence à empresa
                try:
                    mapa = CTOMapFile.objects.get(id=map_id, company=target_company)
                except CTOMapFile.DoesNotExist:
                    return JsonResponse({'erro': 'Arquivo não encontrado ou não pertence à empresa'}, status=404)
                
                caminho = mapa.file.path if hasattr(mapa.file, 'path') else None
                # Verificar permissões adicionais (RM Admins podem ver, mas ainda precisa filtrar por empresa)
                if not user.is_rm_admin and not user.is_superuser:
                    if not user.company or user.company != mapa.company:
                        return JsonResponse({'erro': 'Acesso negado ao arquivo'}, status=403)
            elif arquivo_nome:
                # Buscar por nome do arquivo - SEMPRE filtrar por empresa
                # Tentar busca exata primeiro
                mapa = CTOMapFile.objects.filter(
                    company=target_company,
                    file__icontains=arquivo_nome
                ).first()
                
                # Se não encontrou, tentar busca mais flexível (sem extensão, case-insensitive)
                if not mapa:
                    # Remover extensão e espaços para busca mais flexível
                    arquivo_sem_ext = os.path.splitext(arquivo_nome)[0].strip()
                    mapa = CTOMapFile.objects.filter(
                        company=target_company,
                        file__isnull=False
                    ).filter(
                        Q(file__icontains=arquivo_sem_ext) | 
                        Q(file__icontains=arquivo_nome)
                    ).first()
                
                if not mapa:
                    # Verificar se há outros arquivos disponíveis para a empresa
                    outros_arquivos = CTOMapFile.objects.filter(
                        company=target_company,
                        file__isnull=False
                    ).values_list('file', flat=True)[:5]
                    
                    outros_nomes = [os.path.basename(str(f)) for f in outros_arquivos if f]
                    
                    erro_msg = f'Arquivo "{arquivo_nome}" não encontrado na empresa especificada'
                    if outros_nomes:
                        erro_msg += f'. Arquivos disponíveis: {", ".join(outros_nomes[:3])}'
                    
                    return JsonResponse({
                        'erro': erro_msg,
                        'detalhes': f'O arquivo "{arquivo_nome}" não foi encontrado no banco de dados da empresa.',
                        'solucao': 'Verifique o nome do arquivo ou faça upload novamente.'
                    }, status=404)
                
                if mapa and mapa.file:
                    caminho = mapa.file.path if hasattr(mapa.file, 'path') else None
                    # Verificar permissões adicionais
                    if not user.is_rm_admin and not user.is_superuser:
                        if not user.company or user.company != mapa.company:
                            return JsonResponse({'erro': 'Acesso negado ao arquivo'}, status=403)
        except CTOMapFile.DoesNotExist:
            pass
        except Exception as e:
            logger.error(f"Erro ao buscar arquivo no banco: {e}", exc_info=True)
            return json_error(MSG_GENERIC, status=500, exc=e)
        
        # Não buscar mais de pastas antigas - apenas do banco de dados
        if not caminho:
            logger.warning(f"Arquivo não encontrado no banco: map_id={map_id}, arquivo={arquivo_nome}, company={target_company.slug if target_company else None}")
            return JsonResponse({
                'erro': 'Arquivo não encontrado no banco de dados',
                'detalhes': 'O arquivo não foi encontrado no banco de dados. Verifique se o mapa foi enviado corretamente.',
                'solucao': 'Faça upload do arquivo novamente através da interface web.'
            }, status=404)
        
        # Verificar se o arquivo existe fisicamente
        if not os.path.exists(caminho):
            logger.warning(f"Arquivo não existe fisicamente: {caminho} (map_id: {map_id}, arquivo: {arquivo_nome})")
            
            detalhes = (
                'O arquivo existe no banco de dados, mas não foi encontrado no disco do servidor.'
            )
            solucao = (
                'Faça upload do arquivo novamente pela interface web. '
                'Na VPS, confira se VPS_MEDIA_ROOT aponta para a pasta correta (veja docs/deploy/DEPLOY.md).'
            )
            body = {
                'erro': 'Arquivo não encontrado no sistema de arquivos',
                'detalhes': detalhes,
                'solucao': solucao,
                'arquivo': arquivo_nome or f'map_id_{map_id}',
            }
            if settings.DEBUG:
                body['caminho_esperado'] = caminho
            return JsonResponse(body, status=404)
        
        # Determinar extensão se não foi definida
        if not ext:
            file_name_ext = os.path.splitext(caminho)[1].lower().lstrip('.')
            if file_name_ext:
                ext = file_name_ext
            else:
                # Tentar detectar pelo conteúdo
                try:
                    with open(caminho, 'rb') as f:
                        first_bytes = f.read(4)
                        if first_bytes[:2] == b'PK':
                            ext = 'kmz'
                        elif first_bytes.startswith(b'<?') or first_bytes.startswith(b'<'):
                            ext = 'kml'
                except Exception as e:
                    logger.warning(f"Erro ao detectar tipo de arquivo: {e}")
                    pass
        
        if not ext:
            logger.warning(f"Tipo de arquivo não identificado: {caminho}")
            return JsonResponse({'erro': 'Tipo de arquivo não identificado'}, status=400)
        
        # Normalizar extensão
        ext = ext.lstrip('.').lower()
        
        logger.debug(f"Processando arquivo: {caminho}, tipo: {ext}")
        
        if ext == 'kml':
            coords = ler_kml(caminho)
        elif ext == 'kmz':
            coords = ler_kmz(caminho)
        elif ext == 'csv':
            coords = ler_csv(caminho)
        elif ext in ['xls', 'xlsx']:
            coords = ler_excel(caminho)
        else:
            logger.warning(f"Tipo de arquivo não suportado: {ext}")
            return JsonResponse({'erro': f'Tipo de arquivo não suportado: {ext}'}, status=400)
        
        if not coords:
            logger.warning(f"Nenhuma coordenada encontrada no arquivo: {caminho}")
            return JsonResponse({'erro': 'Nenhuma coordenada encontrada no arquivo'}, status=404)
        
        # Cachear coordenadas por 1 hora (arquivos não mudam frequentemente)
        cache.set(cache_key, coords, 3600)
        
        logger.info(f"Coordenadas carregadas com sucesso: {len(coords)} pontos do arquivo {caminho}")
        return JsonResponse(coords, safe=False)
    except Exception as e:
        return json_error(
            "Erro ao processar requisição.",
            status=500,
            exc=e,
            logger_name=__name__,
        )


@login_required
@require_http_methods(["GET"])
def api_contar_pontos(request, company_slug=None):
    """Conta o número de pontos em um arquivo"""
    arquivo = request.GET.get('arquivo')
    if not arquivo:
        return JsonResponse({'erro': 'Arquivo não especificado'}, status=400)
    
    caminho = get_arquivo_caminho(arquivo)
    if not caminho or not os.path.exists(caminho):
        return JsonResponse({'erro': 'Arquivo não encontrado'}, status=404)
    
    ext = os.path.splitext(arquivo)[1].lower()
    
    try:
        if ext == '.kml':
            coords = ler_kml(caminho)
        elif ext == '.kmz':
            coords = ler_kmz(caminho)
        elif ext == '.csv':
            coords = ler_csv(caminho)
        elif ext in ['.xls', '.xlsx']:
            coords = ler_excel(caminho)
        else:
            return JsonResponse({'erro': 'Tipo de arquivo não suportado'}, status=400)
        
        total_pontos = 0
        for item in coords:
            if item.get('tipo') == 'point':
                total_pontos += 1
            elif item.get('tipo') == 'line':
                total_pontos += len(item.get('coordenadas', []))
        
        return JsonResponse({'total': total_pontos})
    except Exception as e:
        return json_error("Erro ao processar arquivo.", status=500, exc=e, logger_name=__name__)


@login_required
@require_http_methods(["GET"])
def api_geocode(request, company_slug=None):
    """Geocodificação direta (endereço -> coordenadas) e reversa (coordenadas -> endereço) usando OpenStreetMap Nominatim com cache"""
    endereco = request.GET.get('endereco')
    lat = request.GET.get('lat')
    lon = request.GET.get('lon')
    
    # Geocodificação reversa (coordenadas -> endereço)
    if lat and lon:
        try:
            lat_float = float(lat)
            lon_float = float(lon)
            
            # Verificar cache primeiro (usar coordenadas como chave)
            cache_key = f"{lat_float:.6f},{lon_float:.6f}"  # alinhado ao hash de reverse (6 casas)
            cached_result = get_cached_geocoding(cache_key)
            if cached_result:
                return JsonResponse(cached_result)
            
            # Fazer geocodificação reversa via Nominatim
            url = "https://nominatim.openstreetmap.org/reverse"
            params = {
                'lat': lat_float,
                'lon': lon_float,
                'format': 'json',
                'addressdetails': 1,
                'accept-language': 'pt-BR,pt,en'
            }
            headers = {'User-Agent': 'FTTH-Viewer-Django/1.0'}
            
            response = requests.get(url, params=params, headers=headers, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            if data and 'display_name' in data:
                geocoding_result = {
                    'lat': lat_float,
                    'lng': lon_float,
                    'endereco_completo': data['display_name']
                }
                # Armazenar no cache usando coordenadas como chave
                set_cached_geocoding(cache_key, geocoding_result)
                return JsonResponse(geocoding_result)
            else:
                return JsonResponse(
                    {'erro': 'Endereço não encontrado para estas coordenadas', 'codigo': 'geocode_nao_encontrado'},
                    status=422,
                )
                
        except ValueError:
            return JsonResponse({'erro': 'Coordenadas inválidas'}, status=400)
        except Exception as e:
            return json_error("Erro na geocodificação reversa.", status=500, exc=e, logger_name=__name__)
    
    # Geocodificação direta (endereço -> coordenadas)
    if not endereco:
        return JsonResponse({'erro': 'Endereço ou coordenadas não especificados'}, status=400)
    
    # Verificar cache primeiro (com busca normalizada)
    cached_result = get_cached_geocoding(endereco)
    if cached_result:
        return JsonResponse(cached_result)
    
    # Gerar variações da busca para tentar diferentes formatos
    search_variations = generate_search_variations(endereco)
    last_error = None
    
    for variation in search_variations:
        try:
            url = "https://nominatim.openstreetmap.org/search"
            params = {
                'q': variation,
                'format': 'json',
                'limit': 3,  # Buscar até 3 resultados para escolher o melhor
                'countrycodes': 'br',
                'addressdetails': 1,  # Incluir detalhes do endereço
                'extratags': 1  # Incluir tags extras
            }
            headers = {
                'User-Agent': f'FTTH-Viewer-Django/1.0 ({getattr(settings, "SITE_DOMAIN", "rmsys.app")})',
                'Accept-Language': 'pt-BR,pt;q=0.9'
            }
            
            response = requests.get(url, params=params, headers=headers, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            if data and len(data) > 0:
                # Escolher o melhor resultado (priorizar resultados com score mais alto)
                # Se tiver múltiplos, escolher o primeiro (já vem ordenado por relevância)
                resultado = data[0]
                
                # Verificar se o resultado está no Brasil (pelas coordenadas ou pelo addressdetails)
                lat = float(resultado['lat'])
                lng = float(resultado['lon'])
                
                # Verificação básica de coordenadas brasileiras
                if -34 <= lat <= 5 and -74 <= lng <= -32:
                    geocoding_result = {
                        'lat': lat,
                        'lng': lng,
                        'endereco_completo': resultado.get('display_name', variation)
                    }
                    # Armazenar no cache (usar o endereço original, não a variação)
                    set_cached_geocoding(endereco, geocoding_result)
                    return JsonResponse(geocoding_result)
                else:
                    # Resultado não está no Brasil, continuar tentando outras variações
                    last_error = 'Endereço encontrado fora do Brasil'
                    continue
            else:
                # Sem resultados para esta variação, tentar próxima
                last_error = 'Endereço não encontrado'
                continue
                
        except requests.exceptions.Timeout:
            last_error = 'Timeout na busca de endereço'
            continue
        except requests.exceptions.RequestException as e:
            last_error = f'Erro na requisição: {str(e)}'
            # Para erros de rede, não continuar tentando
            break
        except (KeyError, ValueError, IndexError) as e:
            last_error = f'Erro ao processar resposta: {str(e)}'
            continue
        except Exception as e:
            last_error = f'Erro inesperado: {str(e)}'
            logger.error(f'Erro inesperado na geocodificação: {e}', exc_info=True)
            continue
    
    # Se nenhuma variação funcionou, retornar erro de negócio (422 — não confundir com rota inexistente)
    return JsonResponse(
        {'erro': last_error or 'Endereço não encontrado', 'codigo': 'geocode_nao_encontrado'},
        status=422,
    )


@login_required
@require_http_methods(["GET"])
def api_cep(request, company_slug=None):
    """Consulta CEP via ViaCEP com fallback BrasilAPI (proxy — evita 404 no browser)."""
    import re

    cep = re.sub(r"\D", "", request.GET.get("cep", ""))
    if len(cep) != 8:
        return JsonResponse({"erro": "CEP inválido"}, status=400)

    info = None
    try:
        response = requests.get(f"https://viacep.com.br/ws/{cep}/json/", timeout=8)
        response.raise_for_status()
        data = response.json()
        if data.get("erro"):
            raise ValueError("ViaCEP sem resultado")
        info = {
            "street": data.get("logradouro") or "",
            "neighborhood": data.get("bairro") or "",
            "city": data.get("localidade") or "",
            "state": data.get("uf") or "",
            "raw": data,
        }
    except Exception:
        for url in (
            f"https://brasilapi.com.br/api/cep/v2/{cep}",
            f"https://brasilapi.com.br/api/cep/v1/{cep}",
        ):
            try:
                response = requests.get(url, timeout=8)
                if response.status_code == 404:
                    continue
                response.raise_for_status()
                data = response.json()
                if data.get("errors") or data.get("message"):
                    continue
                info = {
                    "street": data.get("street") or "",
                    "neighborhood": data.get("neighborhood") or "",
                    "city": data.get("city") or "",
                    "state": data.get("state") or "",
                    "raw": data,
                }
                break
            except Exception:
                continue

    if not info:
        return JsonResponse({"erro": "CEP não encontrado"}, status=404)

    address_parts = [
        info["street"],
        info["neighborhood"],
        f"{info['city']}{' - ' + info['state'] if info['state'] else ''}",
        "Brasil",
    ]
    display_name = ", ".join(p for p in address_parts if p)

    return JsonResponse(
        {
            "cep": cep,
            "display_name": display_name or f"{cep}, Brasil",
            "street": info["street"],
            "neighborhood": info["neighborhood"],
            "city": info["city"],
            "state": info["state"],
        }
    )


@login_required
@require_http_methods(["GET"])
def api_geocode_suggestions(request, company_slug=None):
    """Retorna sugestões de endereços enquanto o usuário digita (autocomplete)"""
    query = request.GET.get('q', '').strip()
    if not query or len(query) < 3:
        return JsonResponse({'suggestions': []})
    
    try:
        url = "https://nominatim.openstreetmap.org/search"
        params = {
            'q': f"{query}, Brasil",
            'format': 'json',
            'limit': 5,  # Limitar a 5 sugestões
            'countrycodes': 'br',
            'addressdetails': 1
        }
        headers = {
            'User-Agent': f'FTTH-Viewer-Django/1.0 ({getattr(settings, "SITE_DOMAIN", "rmsys.app")})',
            'Accept-Language': 'pt-BR,pt;q=0.9'
        }
        
        response = requests.get(url, params=params, headers=headers, timeout=5)
        response.raise_for_status()
        
        data = response.json()
        suggestions = []
        
        if data:
            for item in data[:5]:  # Limitar a 5 sugestões
                lat = float(item['lat'])
                lng = float(item['lon'])
                
                # Verificar se está no Brasil
                if -34 <= lat <= 5 and -74 <= lng <= -32:
                    suggestions.append({
                        'display_name': item.get('display_name', ''),
                        'lat': lat,
                        'lng': lng,
                        'address': item.get('address', {})
                    })
        
        return JsonResponse({'suggestions': suggestions})
        
    except Exception as e:
        logger.warning(f'Erro ao buscar sugestões de endereço: {e}')
        return JsonResponse({'suggestions': []})


@login_required
@require_http_methods(["GET"])
def api_verificar_viabilidade(request, company_slug=None):
    """Verifica viabilidade de instalação FTTH"""
    try:
        lat = request.GET.get("lat")
        lon = request.GET.get("lon")
        
        if lat is None or lon is None:
            return JsonResponse({"erro": "Coordenadas não fornecidas"}, status=400)
        
        try:
            lat = float(lat)
            lon = float(lon)
        except (ValueError, TypeError):
            return JsonResponse({"erro": "Coordenadas inválidas"}, status=400)
        
        # Determinar empresa ANTES de verificar cache (para cache separado por empresa)
        company = None
        user = request.user
        
        # Se company_slug foi fornecido, usar ele (prioridade)
        if company_slug:
            try:
                company = Company.objects.get(slug=company_slug, is_active=True)
            except Company.DoesNotExist:
                return JsonResponse({"erro": "Empresa não encontrada"}, status=404)
        elif user.is_authenticated:
            # Para usuários normais, SEMPRE usar a empresa deles
            if not user.is_rm_admin and not user.is_superuser:
                if not user.company:
                    return JsonResponse({"erro": "Usuário não está associado a uma empresa"}, status=403)
                company = user.company
            # RM Admins e superusers: se não tiver company_slug, usar empresa do usuário se existir
            elif user.company:
                company = user.company
            # Se RM Admin não tem empresa e não forneceu slug, não pode verificar sem especificar empresa
            else:
                return JsonResponse({"erro": "É necessário especificar a empresa para verificação"}, status=400)
        else:
            return JsonResponse({"erro": "Usuário não autenticado"}, status=401)
        
        if not company:
            return JsonResponse({"erro": "Empresa não especificada"}, status=400)
        
        # Obter IDs dos mapas ativos (se fornecidos)
        map_ids_param = request.GET.get('map_ids', '').strip()
        map_ids_list = []
        mapas_hash = ''
        
        if map_ids_param:
            # Parsear lista de IDs dos mapas (separados por vírgula)
            map_ids_list = [mid.strip() for mid in map_ids_param.split(',') if mid.strip()]
            # Ordenar para garantir consistência (hash sempre igual para mesmos mapas)
            map_ids_list.sort()
            mapas_hash = ','.join(map_ids_list)
        
        force_refresh = request.GET.get('refresh', '').lower() in ('1', 'true', 'yes')

        # Verificar cache de viabilidade - incluir empresa E mapas ativos no cache
        if not force_refresh:
            try:
                cache_obj = ViabilidadeCache.objects.get(
                    lat=lat,
                    lon=lon,
                    company=company,
                    mapas_hash=mapas_hash
                )
                return JsonResponse(cache_obj.resultado)
            except ViabilidadeCache.DoesNotExist:
                pass

        from core.quotas import QuotaExceeded, enforce_quota

        try:
            enforce_quota(company, "viability_month", user=user)
        except QuotaExceeded as exc:
            return JsonResponse({"erro": str(exc), "quota_exceeded": True}, status=403)
        
        # Company já foi determinado acima (antes de verificar cache)
        
        # Buscar CTOs APENAS da empresa especificada
        ctos = get_all_ctos(company=company)
        
        # Se map_ids foram fornecidos, filtrar CTOs apenas dos mapas ativos
        if map_ids_list:
            allowed_map_ids = {str(mid) for mid in map_ids_list}
            ctos = [
                cto for cto in ctos
                if str(cto.get('map_id')) in allowed_map_ids
            ]
        
        if not ctos:
            return JsonResponse(
                {
                    "erro": "Nenhum CTO encontrado"
                    + (" nos mapas selecionados" if map_ids_list else ""),
                    "codigo": "sem_cto",
                },
                status=422,
            )
        
        # Fase 1: Filtrar por distância euclidiana (otimizado)
        # Limitar busca inicial a CTOs próximos (raio de ~5km) para reduzir processamento
        ctos_com_distancia = []
        MAX_INITIAL_RADIUS = 5000  # 5km em metros
        
        for cto in ctos:
            try:
                cto_lat = float(cto["lat"])
                cto_lon = float(cto["lng"])
                distancia_euclidiana = calcular_distancia(lat, lon, cto_lat, cto_lon)
                
                # Filtrar apenas CTOs dentro do raio inicial (otimização)
                if distancia_euclidiana <= MAX_INITIAL_RADIUS:
                    ctos_com_distancia.append({
                        **cto,
                        "distancia_euclidiana": distancia_euclidiana
                    })
            except (ValueError, TypeError, KeyError):
                continue
        
        # Se não encontrou CTOs próximos, expandir busca
        if not ctos_com_distancia:
            # Buscar todos os CTOs sem filtro de raio
            for cto in ctos:
                try:
                    cto_lat = float(cto["lat"])
                    cto_lon = float(cto["lng"])
                    distancia_euclidiana = calcular_distancia(lat, lon, cto_lat, cto_lon)
                    ctos_com_distancia.append({
                        **cto,
                        "distancia_euclidiana": distancia_euclidiana
                    })
                except (ValueError, TypeError, KeyError):
                    continue
        
        if not ctos_com_distancia:
            return JsonResponse({"erro": "Nenhum CTO válido encontrado"}, status=404)
        
        # Ordenar e pegar os 5 melhores candidatos
        ctos_com_distancia.sort(key=lambda x: x["distancia_euclidiana"])
        num_candidatos = min(5, len(ctos_com_distancia))
        ctos_candidatos = ctos_com_distancia[:num_candidatos]
        
        # Fase 2: Calcular rota real para os candidatos (PARALELO)
        cto_mais_proximo = None
        menor_distancia = float('inf')
        melhor_geometria = None
        
        tarefas = []
        for cto in ctos_candidatos:
            try:
                cto_lat = float(cto["lat"])
                cto_lon = float(cto["lng"])
                tarefas.append((lat, lon, cto_lat, cto_lon, cto))
            except (ValueError, TypeError, KeyError):
                continue
        
        # Executar cálculos em paralelo (aumentar workers para mais velocidade)
        with ThreadPoolExecutor(max_workers=min(5, len(tarefas))) as executor:
            futures = {
                executor.submit(calcular_rota_ruas_single, tarefa[0], tarefa[1], tarefa[2], tarefa[3], tarefa[4]): i 
                for i, tarefa in enumerate(tarefas)
            }
            
            for future in as_completed(futures):
                try:
                    distancia_ruas, geometria, cto = future.result()
                    if distancia_ruas < menor_distancia:
                        menor_distancia = distancia_ruas
                        cto_mais_proximo = cto
                        melhor_geometria = geometria
                except Exception as e:
                    logger.warning("Erro no processamento paralelo de viabilidade: %s", e)
                    continue
        
        if not cto_mais_proximo:
            return JsonResponse({"erro": "Nenhum CTO válido encontrado"}, status=404)
        
        # Classificar viabilidade
        viabilidade = classificar_viabilidade(menor_distancia)
        
        # Preparar resposta
        resultado = {
            "viabilidade": viabilidade,
            "cto": {
                "nome": cto_mais_proximo.get("nome", "CTO"),
                "lat": float(cto_mais_proximo["lat"]),
                "lon": float(cto_mais_proximo["lng"]),
                "arquivo": cto_mais_proximo.get("arquivo", ""),
                "map_id": cto_mais_proximo.get("map_id")
            },
            "distancia": {
                "metros": round(menor_distancia, 2),
                "km": round(menor_distancia / 1000, 3)
            },
            "rota": {
                "geometria": melhor_geometria
            }
        }
        
        # Salvar no cache - incluir empresa E mapas ativos para separar caches
        ViabilidadeCache.objects.update_or_create(
            lat=lat,
            lon=lon,
            company=company,  # Incluir empresa no cache
            mapas_hash=mapas_hash,  # Incluir hash dos mapas ativos no cache
            defaults={'resultado': resultado}
        )
        
        return JsonResponse(resultado)
        
    except Exception as e:
        return json_error(
            "Erro na verificação de viabilidade.",
            status=500,
            exc=e,
            logger_name=__name__,
        )


@login_required
@rm_admin_required_json
@require_http_methods(["GET"])
def api_cache_geocoding_stats(request, company_slug=None):
    """Retorna estatísticas do cache de geocodificação (global — apenas RM)."""
    from .models import GeocodingCache
    from django.utils import timezone
    from .geocoding_privacy import get_retention_days, get_ttl_hours

    agora = timezone.now()
    total_entries = GeocodingCache.objects.count()
    valid_entries = GeocodingCache.objects.filter(expires_at__gt=agora).count()
    expired_entries = GeocodingCache.objects.filter(expires_at__lte=agora).count()

    return JsonResponse({
        'total_entries': total_entries,
        'valid_entries': valid_entries,
        'expired_entries': expired_entries,
        'cache_ttl_hours': get_ttl_hours(),
        'retention_days': get_retention_days(),
        'storage_mode': 'hash_sha256_no_full_address',
    })


@login_required
@rm_admin_required_json
@require_http_methods(["POST"])
def api_cache_geocoding_clear(request, company_slug=None):
    """Limpa o cache de geocodificação (global — apenas RM)."""
    from .models import GeocodingCache
    from .utils import purge_expired_geocoding_cache

    expired_removed = purge_expired_geocoding_cache()
    count = GeocodingCache.objects.count()
    GeocodingCache.objects.all().delete()
    return JsonResponse({
        'mensagem': f'Cache de geocodificação limpo ({count} entradas removidas, {expired_removed} expiradas antes)',
    })


@ensure_csrf_cookie
@require_http_methods(["POST"])
def api_adicionar_cto(request, company_slug=None):
    """Adiciona um novo CTO a um mapa existente - apenas para COMPANY_ADMIN e RM"""
    from .utils import adicionar_cto_ao_mapa
    
    # Verificar autenticação manualmente para retornar JSON em vez de redirecionar
    if not request.user.is_authenticated:
        return JsonResponse({'erro': 'Usuário não autenticado'}, status=401)
    
    user = request.user
    
    # Verificar se é admin da empresa ou RM
    if not (user.is_company_admin or user.is_rm_admin or user.is_superuser):
        return JsonResponse({'erro': 'Apenas administradores podem adicionar CTOs'}, status=403)
    
    # Obter dados do POST
    try:
        import json
        data = json.loads(request.body) if request.body else {}
        nome_cto = data.get('nome_cto', '').strip()
        lat = data.get('lat')
        lon = data.get('lon')
        map_id = data.get('map_id')
    except json.JSONDecodeError:
        return JsonResponse({'erro': 'Dados inválidos'}, status=400)
    
    # Validar dados
    if not nome_cto:
        return JsonResponse({'erro': 'Nome do CTO é obrigatório'}, status=400)
    
    if lat is None or lon is None:
        return JsonResponse({'erro': 'Coordenadas são obrigatórias'}, status=400)
    
    try:
        lat = float(lat)
        lon = float(lon)
    except (ValueError, TypeError):
        return JsonResponse({'erro': 'Coordenadas inválidas'}, status=400)
    
    if not map_id:
        return JsonResponse({'erro': 'ID do mapa é obrigatório'}, status=400)
    
    # Buscar mapa
    try:
        mapa = CTOMapFile.objects.get(id=map_id)
    except CTOMapFile.DoesNotExist:
        return JsonResponse({'erro': 'Mapa não encontrado'}, status=404)
    
    # Verificar se o usuário tem acesso ao mapa
    if not user.is_rm_admin and not user.is_superuser:
        if not user.company or user.company != mapa.company:
            return JsonResponse({'erro': 'Acesso negado ao mapa'}, status=403)
    
    # Verificar se o arquivo existe
    if not mapa.file or not hasattr(mapa.file, 'path'):
        return JsonResponse({'erro': 'Arquivo do mapa não encontrado'}, status=404)
    
    caminho_arquivo = mapa.file.path
    if not os.path.exists(caminho_arquivo):
        return JsonResponse({'erro': 'Arquivo do mapa não existe no sistema de arquivos'}, status=404)
    
    # Adicionar CTO ao arquivo
    try:
        sucesso = adicionar_cto_ao_mapa(
            caminho_arquivo,
            nome_cto,
            lat,
            lon,
            file_type=mapa.file_type
        )
        
        if not sucesso:
            return JsonResponse({'erro': 'Erro ao adicionar CTO ao arquivo'}, status=500)
        
        invalidate_ftth_map_caches(
            mapa.company,
            map_id=map_id,
            user=user,
            company_slug=company_slug,
        )
        # Isso pode ser feito em background ou na próxima leitura
        
        return JsonResponse({
            'sucesso': True,
            'mensagem': f'CTO "{nome_cto}" adicionado com sucesso ao mapa',
            'cto': {
                'nome': nome_cto,
                'lat': lat,
                'lon': lon
            }
        })
        
    except Exception as e:
        return json_error("Erro ao adicionar CTO.", status=500, exc=e, logger_name=__name__)


@ensure_csrf_cookie
@require_http_methods(["POST"])
def api_remover_cto(request, company_slug=None):
    """Remove um CTO existente de um arquivo de mapa - apenas para COMPANY_ADMIN e RM"""
    if not request.user.is_authenticated:
        return JsonResponse({'erro': 'Usuário não autenticado'}, status=401)

    user = request.user

    if not (user.is_company_admin or user.is_rm_admin or user.is_superuser):
        return JsonResponse({'erro': 'Apenas administradores podem remover CTOs'}, status=403)

    try:
        import json
        data = json.loads(request.body) if request.body else {}
    except json.JSONDecodeError:
        return JsonResponse({'erro': 'Dados inválidos'}, status=400)

    map_id = data.get('map_id')
    lat = data.get('lat')
    lon = data.get('lon')
    nome_cto = (data.get('nome_cto') or data.get('nome') or '').strip()

    if not map_id:
        return JsonResponse({'erro': 'ID do mapa é obrigatório'}, status=400)

    if lat is None or lon is None:
        return JsonResponse({'erro': 'Coordenadas são obrigatórias'}, status=400)

    try:
        lat = float(lat)
        lon = float(lon)
    except (ValueError, TypeError):
        return JsonResponse({'erro': 'Coordenadas inválidas'}, status=400)

    try:
        mapa = CTOMapFile.objects.get(id=map_id)
    except CTOMapFile.DoesNotExist:
        return JsonResponse({'erro': 'Mapa não encontrado'}, status=404)

    if not user.is_rm_admin and not user.is_superuser:
        if not user.company or user.company != mapa.company:
            return JsonResponse({'erro': 'Acesso negado ao mapa'}, status=403)

    if not mapa.file or not hasattr(mapa.file, 'path'):
        return JsonResponse({'erro': 'Arquivo do mapa não encontrado'}, status=404)

    caminho_arquivo = mapa.file.path
    if not os.path.exists(caminho_arquivo):
        return JsonResponse({'erro': 'Arquivo do mapa não existe no sistema de arquivos'}, status=404)

    try:
        removido = remover_cto_do_mapa(
            caminho_arquivo,
            lat,
            lon,
            nome_cto=nome_cto,
            file_type=mapa.file_type
        )

        if not removido:
            return JsonResponse({'erro': 'CTO não encontrado no arquivo'}, status=404)

        invalidate_ftth_map_caches(
            mapa.company,
            map_id=map_id,
            user=user,
            company_slug=company_slug,
        )

        return JsonResponse({
            'sucesso': True,
            'mensagem': f'CTO removido com sucesso do mapa "{mapa.file_name}"'
        })

    except Exception as e:
        return json_error("Erro ao remover CTO.", status=500, exc=e, logger_name=__name__)

