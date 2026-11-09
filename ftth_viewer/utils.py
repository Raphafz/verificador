"""
Funções auxiliares para processamento de arquivos KML/KMZ/CSV/XLS e cálculos geográficos
"""
import os
import sys
import json
import xml.etree.ElementTree as ET
import requests
import zipfile
import math
import csv
import pandas as pd
import unicodedata
import re
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from django.conf import settings
from django.core.cache import cache
from .models import GeocodingCache, ViabilidadeCache


def _normalize_decimal(value):
    """Converte valores numéricos que podem estar em string para float."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        value_str = str(value).strip()
        if not value_str:
            return None
        value_str = value_str.replace(',', '.')
        return float(value_str)
    except (ValueError, TypeError):
        return None


def _coords_match(lat1, lon1, lat2, lon2, tolerance=1e-5):
    """Verifica se duas coordenadas são equivalentes dentro de uma tolerância."""
    if None in (lat1, lon1, lat2, lon2):
        return False
    return abs(lat1 - lat2) <= tolerance and abs(lon1 - lon2) <= tolerance


def get_base_path():
    """Retorna o caminho base do projeto"""
    return Path(settings.BASE_DIR)


def ler_kml(caminho_kml):
    """Lê um arquivo KML e extrai coordenadas"""
    try:
        tree = ET.parse(caminho_kml)
        root = tree.getroot()
        
        ns = {'kml': 'http://www.opengis.net/kml/2.2'}
        coordenadas = []
        
        for placemark in root.findall('.//kml:Placemark', ns):
            nome = placemark.find('.//kml:name', ns)
            nome_texto = nome.text if nome is not None else "Sem nome"
            
            # Buscar coordenadas em Point
            point = placemark.find('.//kml:Point/kml:coordinates', ns)
            if point is not None:
                coords = point.text.strip().split(',')
                if len(coords) >= 2:
                    try:
                        lon, lat = float(coords[0]), float(coords[1])
                        coordenadas.append({
                            'nome': nome_texto,
                            'lat': lat,
                            'lng': lon,
                            'tipo': 'point'
                        })
                    except ValueError:
                        continue
            
            # Buscar coordenadas em LineString
            linestring = placemark.find('.//kml:LineString/kml:coordinates', ns)
            if linestring is not None:
                coords_text = linestring.text.strip()
                pontos = []
                for linha in coords_text.split('\n'):
                    linha = linha.strip()
                    if linha:
                        coords = linha.split(',')
                        if len(coords) >= 2:
                            try:
                                lon, lat = float(coords[0]), float(coords[1])
                                pontos.append([lat, lon])
                            except ValueError:
                                continue
                
                if pontos:
                    coordenadas.append({
                        'nome': nome_texto,
                        'coordenadas': pontos,
                        'tipo': 'line'
                    })
        
        return coordenadas
    except Exception as e:
        print(f"Erro ao ler KML {caminho_kml}: {e}")
        return []


def ler_kmz(caminho_kmz, filtrar_brasil=False):
    """Lê um arquivo KMZ e extrai coordenadas"""
    import tempfile
    try:
        with zipfile.ZipFile(caminho_kmz, 'r') as kmz:
            for arquivo in kmz.namelist():
                if arquivo.endswith('.kml'):
                    with kmz.open(arquivo) as kml_file:
                        with tempfile.NamedTemporaryFile(mode='wb', delete=False, suffix='.kml') as temp_kml:
                            temp_kml.write(kml_file.read())
                            temp_path = temp_kml.name
                        
                        coordenadas = ler_kml(temp_path)
                        
                        # Remover arquivo temporário
                        if os.path.exists(temp_path):
                            os.remove(temp_path)
                        
                        if filtrar_brasil:
                            coordenadas = filtrar_coordenadas_brasil(coordenadas)
                        
                        return coordenadas
        return []
    except Exception as e:
        print(f"Erro ao ler KMZ {caminho_kmz}: {e}")
        return []


def filtrar_coordenadas_brasil(coordenadas):
    """Filtra coordenadas que estão dentro do território brasileiro"""
    coordenadas_filtradas = []
    for coord in coordenadas:
        if coord.get('tipo') == 'point':
            lat, lng = coord['lat'], coord['lng']
            if -34 <= lat <= 5 and -74 <= lng <= -32:
                coordenadas_filtradas.append(coord)
        else:
            coordenadas_filtradas.append(coord)
    return coordenadas_filtradas


def ler_csv(caminho_csv):
    """Lê um arquivo CSV e extrai coordenadas"""
    try:
        coordenadas = []
        
        with open(caminho_csv, 'r', encoding='utf-8') as f:
            sample = f.read(1024)
            sniffer = csv.Sniffer()
            delimiter = sniffer.sniff(sample).delimiter
        
        df = pd.read_csv(caminho_csv, delimiter=delimiter, encoding='utf-8')
        
        lat_cols = [col for col in df.columns if any(keyword in col.lower() for keyword in ['lat', 'latitude', 'y'])]
        lng_cols = [col for col in df.columns if any(keyword in col.lower() for keyword in ['lng', 'lon', 'longitude', 'x'])]
        nome_cols = [col for col in df.columns if any(keyword in col.lower() for keyword in ['nome', 'name', 'id', 'cto'])]
        
        if not lat_cols or not lng_cols:
            numeric_cols = df.select_dtypes(include=[float, int]).columns
            if len(numeric_cols) >= 2:
                lat_col = numeric_cols[0]
                lng_col = numeric_cols[1]
            else:
                return []
        else:
            lat_col = lat_cols[0]
            lng_col = lng_cols[0]
        
        nome_col = nome_cols[0] if nome_cols else None
        
        for index, row in df.iterrows():
            try:
                lat = float(row[lat_col])
                lng = float(row[lng_col])
                nome = str(row[nome_col]) if nome_col and pd.notna(row[nome_col]) else f"Ponto {index + 1}"
                
                coordenadas.append({
                    'nome': nome,
                    'lat': lat,
                    'lng': lng,
                    'tipo': 'point'
                })
            except (ValueError, TypeError):
                continue
        
        return coordenadas
    except Exception as e:
        print(f"Erro ao ler CSV {caminho_csv}: {e}")
        return []


def ler_excel(caminho_excel):
    """Lê um arquivo Excel (XLS ou XLSX) e extrai coordenadas"""
    try:
        coordenadas = []
        df = pd.read_excel(caminho_excel)
        
        lat_cols = [col for col in df.columns if any(keyword in col.lower() for keyword in ['lat', 'latitude', 'y'])]
        lng_cols = [col for col in df.columns if any(keyword in col.lower() for keyword in ['lng', 'lon', 'longitude', 'x'])]
        nome_cols = [col for col in df.columns if any(keyword in col.lower() for keyword in ['nome', 'name', 'id', 'cto'])]
        
        if not lat_cols or not lng_cols:
            numeric_cols = df.select_dtypes(include=[float, int]).columns
            if len(numeric_cols) >= 2:
                lat_col = numeric_cols[0]
                lng_col = numeric_cols[1]
            else:
                return []
        else:
            lat_col = lat_cols[0]
            lng_col = lng_cols[0]
        
        nome_col = nome_cols[0] if nome_cols else None
        
        for index, row in df.iterrows():
            try:
                lat = float(row[lat_col])
                lng = float(row[lng_col])
                nome = str(row[nome_col]) if nome_col and pd.notna(row[nome_col]) else f"Ponto {index + 1}"
                
                coordenadas.append({
                    'nome': nome,
                    'lat': lat,
                    'lng': lng,
                    'tipo': 'point'
                })
            except (ValueError, TypeError):
                continue
        
        return coordenadas
    except Exception as e:
        print(f"Erro ao ler Excel {caminho_excel}: {e}")
        return []


def calcular_distancia(lat1, lon1, lat2, lon2):
    """Calcula a distância entre dois pontos usando a fórmula de Haversine (metros)"""
    R = 6371000  # Raio da Terra em metros
    
    lat1_rad = math.radians(lat1)
    lon1_rad = math.radians(lon1)
    lat2_rad = math.radians(lat2)
    lon2_rad = math.radians(lon2)
    
    dlat = lat2_rad - lat1_rad
    dlon = lon2_rad - lon1_rad
    
    a = math.sin(dlat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    
    return R * c


def _openrouteservice_api_key() -> str:
    key = (getattr(settings, "OPENROUTESERVICE_API_KEY", None) or "").strip()
    if not key or key == "sua-chave-api-aqui":
        return ""
    return key


def _calcular_rota_openrouteservice(lat1, lon1, lat2, lon2):
    """Rota por ruas via OpenRouteService (requer OPENROUTESERVICE_API_KEY)."""
    api_key = _openrouteservice_api_key()
    if not api_key:
        return None
    url = "https://api.openrouteservice.org/v2/directions/driving-car"
    headers = {
        "Authorization": api_key,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    body = {
        "coordinates": [[lon1, lat1], [lon2, lat2]],
        "geometry": True,
    }
    timeout = getattr(settings, "ROUTING_TIMEOUT", 15)
    resp = requests.post(url, json=body, headers=headers, timeout=timeout)
    resp.raise_for_status()
    data = resp.json()
    routes = data.get("routes") or []
    if not routes:
        return None
    route = routes[0]
    summary = route.get("summary") or {}
    distancia = float(summary.get("distance", 0))
    geometry = route.get("geometry") or {}
    coords = geometry.get("coordinates") or [[lon1, lat1], [lon2, lat2]]
    if distancia <= 0:
        return None
    return distancia, coords


def calcular_rota_ruas(lat1, lon1, lat2, lon2):
    """Calcula rota (OpenRouteService se houver chave, senão OSRM) → (distancia_metros, geometria)."""
    try:
        cache_key = f"route_{lat1:.6f},{lon1:.6f}->{lat2:.6f},{lon2:.6f}"
        cached = cache.get(cache_key)
        if cached:
            return cached

        if _openrouteservice_api_key():
            try:
                ors_result = _calcular_rota_openrouteservice(lat1, lon1, lat2, lon2)
                if ors_result:
                    cache.set(cache_key, ors_result, 1800)
                    return ors_result
            except Exception as e:
                print(f"Erro ao calcular rota OpenRouteService: {e}")

        base_url = "https://router.project-osrm.org/route/v1/driving"
        url = f"{base_url}/{lon1:.6f},{lat1:.6f};{lon2:.6f},{lat2:.6f}"
        params = {
            "overview": "simplified",
            "geometries": "geojson",
            "alternatives": "false",
            "steps": "false"
        }
        headers = {"User-Agent": "FTTH-Viewer-Django/1.0"}
        
        # Reduzir timeout para respostas mais rápidas (5 segundos ao invés de 15)
        timeout = min(getattr(settings, 'FTTH_ROUTING_TIMEOUT', 15), 5)  # Máximo 5 segundos
        resp = requests.get(url, params=params, headers=headers, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
        
        if data.get("routes"):
            route = data["routes"][0]
            distancia = float(route.get("distance", calcular_distancia(lat1, lon1, lat2, lon2)))
            coords = route.get("geometry", {}).get("coordinates") or [[lon1, lat1], [lon2, lat2]]
            result = (distancia, coords)
            cache.set(cache_key, result, 1800)  # Cache por 30 minutos
            return result
    except Exception as e:
        print(f"Erro ao calcular rota OSRM: {e}")
    
    # Fallback para distância euclidiana
    distancia = calcular_distancia(lat1, lon1, lat2, lon2)
    coords = [[lon1, lat1], [lon2, lat2]]
    return distancia, coords


def calcular_rota_ruas_single(lat1, lon1, lat2, lon2, cto_info=None):
    """Versão single-threaded para processamento paralelo"""
    distancia, coords = calcular_rota_ruas(lat1, lon1, lat2, lon2)
    return distancia, coords, cto_info


def classificar_viabilidade(distancia_metros):
    """Classifica a viabilidade baseada na distância"""
    config = getattr(settings, 'FTTH_VIABILIDADE_CONFIG', {
        'viavel': 300,
        'limitada': 800,
        'inviavel': 800
    })
    
    if distancia_metros <= config['viavel']:
        return {
            "status": "Viável",
            "cor": "#28a745",
            "descricao": "Instalação viável"
        }
    elif distancia_metros <= config['limitada']:
        return {
            "status": "Viabilidade Limitada",
            "cor": "#ffc107",
            "descricao": "Instalação com limitações"
        }
    else:
        return {
            "status": "Sem viabilidade",
            "cor": "#dc3545",
            "descricao": "Instalação não viável"
        }


def normalize_address(address):
    """Normaliza endereço removendo acentos e normalizando abreviações comuns"""
    if not address:
        return address
    
    # Remover acentos
    nfkd = unicodedata.normalize('NFKD', address)
    text = ''.join([c for c in nfkd if not unicodedata.combining(c)])
    
    # Normalizar para minúsculas
    text = text.lower().strip()
    
    # Normalizar abreviações comuns de endereços brasileiros
    abbreviations = {
        r'\br\b': 'rua',
        r'\bav\b': 'avenida',
        r'\bavenida\b': 'avenida',
        r'\bpç\b': 'praça',
        r'\bpraça\b': 'praça',
        r'\btv\b': 'travessa',
        r'\btravessa\b': 'travessa',
        r'\bal\b': 'alameda',
        r'\balameda\b': 'alameda',
        r'\bstr\b': 'rua',
        r'\bst\b': 'rua',
        r'\brod\b': 'rodovia',
        r'\brodovia\b': 'rodovia',
        r'\besp\b': 'estrada',
        r'\bestrada\b': 'estrada',
        r'\bpr\b': 'praia',
        r'\bpraia\b': 'praia',
        r'\bcond\b': 'condominio',
        r'\bcondominio\b': 'condominio',
        r'\bcondomínio\b': 'condominio',
        r'\bres\b': 'residencial',
        r'\bresidencial\b': 'residencial',
        r'\bap\b': 'apartamento',
        r'\bapto\b': 'apartamento',
        r'\bapartamento\b': 'apartamento',
        r'\bbl\b': 'bloco',
        r'\bbloco\b': 'bloco',
        r'\bqd\b': 'quadra',
        r'\bquadra\b': 'quadra',
        r'\blt\b': 'lote',
        r'\blote\b': 'lote',
        r'\bs/n\b': '',
        r'\bsin numero\b': '',
        r'\bsem numero\b': '',
    }
    
    for pattern, replacement in abbreviations.items():
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    
    # Remover caracteres especiais e normalizar espaços
    text = re.sub(r'[^\w\s]', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    
    return text


def generate_search_variations(address):
    """Gera variações da busca para tentar encontrar o endereço"""
    variations = []
    
    # Versão original
    variations.append(address.strip())
    
    # Versão normalizada
    normalized = normalize_address(address)
    if normalized != address.lower().strip():
        variations.append(normalized)
    
    # Versão com "Brasil" no final (ajuda Nominatim)
    if 'brasil' not in address.lower() and 'brazil' not in address.lower():
        variations.append(f"{address.strip()}, Brasil")
        variations.append(f"{normalized}, brasil")
    
    # Versão com "Rio de Janeiro" no final (se não mencionar cidade)
    if 'rio de janeiro' not in address.lower() and 'rj' not in address.lower():
        variations.append(f"{address.strip()}, Rio de Janeiro, RJ, Brasil")
        variations.append(f"{normalized}, rio de janeiro, rj, brasil")
    
    # Remover duplicatas mantendo a ordem
    seen = set()
    unique_variations = []
    for var in variations:
        var_lower = var.lower().strip()
        if var_lower and var_lower not in seen:
            seen.add(var_lower)
            unique_variations.append(var)
    
    return unique_variations


def get_cached_geocoding(query):
    """Busca geocodificação por hash SHA-256; remove entradas expiradas (TTL)."""
    from django.utils import timezone
    from .geocoding_privacy import cache_key_for_query

    if not query:
        return None

    try:
        key_hash, _ = cache_key_for_query(str(query))
        cache_obj = GeocodingCache.objects.get(cache_key_hash=key_hash)
    except GeocodingCache.DoesNotExist:
        return None
    except Exception:
        return None

    if cache_obj.is_expired:
        cache_obj.delete()
        return None

    cache_obj.updated_at = timezone.now()
    cache_obj.save(update_fields=["updated_at"])
    return cache_obj.to_dict()


def set_cached_geocoding(query, data):
    """
    Persiste apenas coordenadas + região anonimizada (sem endereço completo).
    Chave única por hash normalizado — uma linha por consulta lógica.
    """
    from .geocoding_privacy import (
        anonymize_display_name,
        cache_key_for_query,
        compute_expires_at,
    )

    if not query or not data:
        return

    key_hash, query_type = cache_key_for_query(str(query))
    full_label = data.get("endereco_completo") or ""
    locality_hint = anonymize_display_name(full_label)

    GeocodingCache.objects.update_or_create(
        cache_key_hash=key_hash,
        defaults={
            "query_type": query_type,
            "lat": float(data["lat"]),
            "lng": float(data["lng"]),
            "locality_hint": locality_hint[:120],
            "expires_at": compute_expires_at(),
        },
    )


def purge_expired_geocoding_cache() -> int:
    """Remove entradas com TTL vencido."""
    from django.utils import timezone

    deleted, _ = GeocodingCache.objects.filter(expires_at__lt=timezone.now()).delete()
    return deleted


def get_all_ctos(company=None):
    """Retorna todos os CTOs apenas dos arquivos enviados via upload (banco de dados)"""
    from django.core.cache import cache
    
    # Verificar cache primeiro (por empresa)
    if company:
        cache_key = f'get_all_ctos_{company.id}'
        cached_coords = cache.get(cache_key)
        if cached_coords is not None:
            return cached_coords
    
    coords = []
    
    # Primeiro, tentar buscar do banco de dados
    try:
        from core.models import CTOMapFile
        
        # IMPORTANTE: Sempre exigir empresa - nunca retornar todos os arquivos
        if not company:
            # Se não foi fornecida empresa, não retornar nada
            return []
        
        # Filtrar APENAS por empresa específica - otimizar query
        map_files = CTOMapFile.objects.filter(
            company=company, 
            file__isnull=False
        ).only('id', 'file', 'company_id').select_related('company')
        
        # Processar cada arquivo do banco
        for map_file in map_files:
            try:
                # Verificar se o arquivo existe fisicamente
                if not map_file.file or not hasattr(map_file.file, 'path'):
                    continue
                
                caminho = map_file.file.path
                if not os.path.exists(caminho):
                    continue
                
                # Determinar extensão
                file_name = map_file.file.name
                ext = os.path.splitext(file_name)[1].lower().lstrip('.')
                
                # Ler coordenadas baseado no tipo
                try:
                    if ext == 'kml':
                        arquivo_coords = ler_kml(caminho)
                    elif ext == 'kmz':
                        arquivo_coords = ler_kmz(caminho)
                    elif ext == 'csv':
                        arquivo_coords = ler_csv(caminho)
                    elif ext in ['xls', 'xlsx']:
                        arquivo_coords = ler_excel(caminho)
                    else:
                        continue
                    
                    # Adicionar informações do arquivo
                    for coord in arquivo_coords:
                        coord["arquivo"] = os.path.basename(file_name)
                        coord["map_id"] = map_file.id
                        coords.append(coord)
                except Exception as e:
                    # Log erro mas continue processando outros arquivos
                    print(f"Erro ao processar arquivo {file_name}: {e}")
                    continue
            except Exception as e:
                # Log erro mas continue processando outros arquivos
                print(f"Erro ao acessar arquivo {map_file.id}: {e}")
                continue
    except Exception as e:
        # Se houver erro ao acessar o banco, logar mas não buscar de pastas antigas
        print(f"Erro ao acessar banco de dados: {e}")
        # Não buscar mais de pastas antigas - apenas do banco de dados
    
    # Não buscar mais de pastas antigas ou diretórios do sistema
    # Apenas usar mapas que foram enviados via upload (banco de dados)
    
    # Cachear resultado por 1 hora (CTOs não mudam frequentemente)
    if company:
        cache_key = f'get_all_ctos_{company.id}'
        cache.set(cache_key, coords, 3600)  # 1 hora
    
    return coords


def invalidate_ftth_map_caches(company, map_id=None, user=None, company_slug=None):
    """Invalida caches Django e ViabilidadeCache após alteração em mapas/CTOs."""
    if not company:
        return
    slug = company_slug or getattr(company, 'slug', None) or 'none'
    keys = [f'get_all_ctos_{company.id}']
    if user is not None:
        keys.append(f'api_arquivos_{user.id}_{slug}')
    if map_id is not None:
        keys.append(f'api_coordenadas_{map_id}_{slug}')
    cache.delete_many(keys)
    ViabilidadeCache.objects.filter(company=company).delete()


def get_arquivo_caminho(arquivo):
    """Retorna o caminho completo de um arquivo baseado na extensão"""
    settings_map = {
        '.kml': getattr(settings, 'FTTH_KML_DIR', None),
        '.kmz': getattr(settings, 'FTTH_KMZ_DIR', None),
        '.csv': getattr(settings, 'FTTH_CSV_DIR', None),
        '.xls': getattr(settings, 'FTTH_XLS_DIR', None),
        '.xlsx': getattr(settings, 'FTTH_XLSX_DIR', None),
    }
    
    ext = Path(arquivo).suffix.lower()
    diretorio = settings_map.get(ext)
    
    if diretorio and os.path.exists(diretorio):
        return os.path.join(diretorio, arquivo)
    return None


def adicionar_cto_kml(caminho_kml, nome_cto, lat, lng):
    """Adiciona um CTO a um arquivo KML"""
    try:
        # Ler arquivo existente
        tree = ET.parse(caminho_kml)
        root = tree.getroot()
        
        ns = {'kml': 'http://www.opengis.net/kml/2.2'}
        
        # Encontrar ou criar Document
        document = root.find('.//kml:Document', ns)
        if document is None:
            # Se não houver Document, criar um
            document = ET.SubElement(root, '{http://www.opengis.net/kml/2.2}Document')
        
        # Criar novo Placemark
        placemark = ET.SubElement(document, '{http://www.opengis.net/kml/2.2}Placemark')
        
        # Adicionar nome
        name_elem = ET.SubElement(placemark, '{http://www.opengis.net/kml/2.2}name')
        name_elem.text = nome_cto
        
        # Adicionar Point com coordenadas
        point = ET.SubElement(placemark, '{http://www.opengis.net/kml/2.2}Point')
        coords_elem = ET.SubElement(point, '{http://www.opengis.net/kml/2.2}coordinates')
        coords_elem.text = f"{lng:.6f},{lat:.6f},0"
        
        # Salvar arquivo
        tree.write(caminho_kml, encoding='utf-8', xml_declaration=True)
        return True
    except Exception as e:
        print(f"Erro ao adicionar CTO em KML {caminho_kml}: {e}")
        return False


def adicionar_cto_kmz(caminho_kmz, nome_cto, lat, lng):
    """Adiciona um CTO a um arquivo KMZ"""
    import tempfile
    import shutil
    try:
        # Criar diretório temporário
        temp_dir = tempfile.mkdtemp()
        
        # Extrair KMZ
        with zipfile.ZipFile(caminho_kmz, 'r') as kmz:
            kmz.extractall(temp_dir)
        
        # Encontrar arquivo KML dentro do KMZ
        kml_file = None
        for arquivo in os.listdir(temp_dir):
            if arquivo.endswith('.kml'):
                kml_file = os.path.join(temp_dir, arquivo)
                break
        
        if not kml_file:
            # Se não houver KML, criar um novo
            kml_file = os.path.join(temp_dir, 'doc.kml')
            root = ET.Element('{http://www.opengis.net/kml/2.2}kml')
            document = ET.SubElement(root, '{http://www.opengis.net/kml/2.2}Document')
            tree = ET.ElementTree(root)
            tree.write(kml_file, encoding='utf-8', xml_declaration=True)
        
        # Adicionar CTO ao KML
        if not adicionar_cto_kml(kml_file, nome_cto, lat, lng):
            shutil.rmtree(temp_dir)
            return False
        
        # Recriar KMZ
        with zipfile.ZipFile(caminho_kmz, 'w', zipfile.ZIP_DEFLATED) as kmz:
            for root, dirs, files in os.walk(temp_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, temp_dir)
                    kmz.write(file_path, arcname)
        
        # Limpar diretório temporário
        shutil.rmtree(temp_dir)
        return True
    except Exception as e:
        print(f"Erro ao adicionar CTO em KMZ {caminho_kmz}: {e}")
        return False


def adicionar_cto_csv(caminho_csv, nome_cto, lat, lng):
    """Adiciona um CTO a um arquivo CSV"""
    try:
        # Ler CSV existente para detectar delimitador e colunas
        with open(caminho_csv, 'r', encoding='utf-8') as f:
            sample = f.read(1024)
            f.seek(0)
            sniffer = csv.Sniffer()
            delimiter = sniffer.sniff(sample).delimiter
            reader = csv.DictReader(f, delimiter=delimiter)
            fieldnames = reader.fieldnames
        
        # Se não houver colunas de nome, lat, lng, criar padrão
        if not fieldnames:
            fieldnames = ['nome', 'lat', 'lng']
        
        # Garantir que existam colunas necessárias
        if 'nome' not in fieldnames:
            fieldnames.insert(0, 'nome')
        if 'lat' not in fieldnames:
            fieldnames.append('lat')
        if 'lng' not in fieldnames:
            fieldnames.append('lng')
        
        # Ler todos os dados existentes
        f.seek(0)
        reader = csv.DictReader(f, delimiter=delimiter)
        rows = list(reader)
        
        # Adicionar novo CTO
        new_row = {}
        for field in fieldnames:
            if field == 'nome':
                new_row[field] = nome_cto
            elif field == 'lat':
                new_row[field] = str(lat)
            elif field == 'lng':
                new_row[field] = str(lng)
            else:
                new_row[field] = ''
        
        rows.append(new_row)
        
        # Escrever CSV atualizado
        with open(caminho_csv, 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=delimiter)
            writer.writeheader()
            writer.writerows(rows)
        
        return True
    except Exception as e:
        print(f"Erro ao adicionar CTO em CSV {caminho_csv}: {e}")
        return False


def adicionar_cto_excel(caminho_excel, nome_cto, lat, lng):
    """Adiciona um CTO a um arquivo Excel"""
    try:
        # Ler Excel existente
        df = pd.read_excel(caminho_excel)
        
        # Verificar se existem colunas de nome, lat, lng
        nome_cols = [col for col in df.columns if any(keyword in col.lower() for keyword in ['nome', 'name', 'id', 'cto'])]
        lat_cols = [col for col in df.columns if any(keyword in col.lower() for keyword in ['lat', 'latitude', 'y'])]
        lng_cols = [col for col in df.columns if any(keyword in col.lower() for keyword in ['lng', 'lon', 'longitude', 'x'])]
        
        # Se não houver colunas apropriadas, criar novas
        if not nome_cols:
            df['nome'] = ''
        if not lat_cols:
            df['lat'] = None
        if not lng_cols:
            df['lng'] = None
        
        # Usar primeira coluna encontrada ou criar padrão
        nome_col = nome_cols[0] if nome_cols else 'nome'
        lat_col = lat_cols[0] if lat_cols else 'lat'
        lng_col = lng_cols[0] if lng_cols else 'lng'
        
        # Adicionar nova linha
        new_row = df.iloc[0].copy() if len(df) > 0 else pd.Series()
        new_row[nome_col] = nome_cto
        new_row[lat_col] = lat
        new_row[lng_col] = lng
        
        # Adicionar ao DataFrame
        df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
        
        # Salvar Excel
        df.to_excel(caminho_excel, index=False)
        return True
    except Exception as e:
        print(f"Erro ao adicionar CTO em Excel {caminho_excel}: {e}")
        return False


def adicionar_cto_ao_mapa(caminho_arquivo, nome_cto, lat, lng, file_type=None):
    """Adiciona um CTO a um arquivo de mapa baseado no tipo"""
    if not file_type:
        ext = os.path.splitext(caminho_arquivo)[1].lower().lstrip('.')
        file_type = ext
    
    file_type = file_type.lower()
    
    if file_type == 'kml':
        return adicionar_cto_kml(caminho_arquivo, nome_cto, lat, lng)
    elif file_type == 'kmz':
        return adicionar_cto_kmz(caminho_arquivo, nome_cto, lat, lng)
    elif file_type == 'csv':
        return adicionar_cto_csv(caminho_arquivo, nome_cto, lat, lng)
    elif file_type in ['xls', 'xlsx']:
        return adicionar_cto_excel(caminho_arquivo, nome_cto, lat, lng)
    else:
        print(f"Tipo de arquivo não suportado para adicionar CTO: {file_type}")
        return False


def remover_cto_kml(caminho_kml, lat, lng, nome_cto=None, tolerance=1e-5):
    """Remove um CTO de um arquivo KML"""
    try:
        tree = ET.parse(caminho_kml)
        root = tree.getroot()

        ns = {'kml': 'http://www.opengis.net/kml/2.2'}
        candidatos = root.findall('.//kml:Document', ns) + root.findall('.//kml:Folder', ns)
        if not candidatos:
            candidatos = [root]

        removed = False
        target_name = nome_cto.strip().lower() if nome_cto else None

        for parent in candidatos:
            for placemark in list(parent.findall('kml:Placemark', ns)):
                coords_elem = placemark.find('.//kml:Point/kml:coordinates', ns)
                if coords_elem is None or not coords_elem.text:
                    continue

                coords = coords_elem.text.strip().split(',')
                if len(coords) < 2:
                    continue

                try:
                    coord_lng = float(coords[0])
                    coord_lat = float(coords[1])
                except ValueError:
                    continue

                name_elem = placemark.find('kml:name', ns)
                name_text = name_elem.text.strip().lower() if name_elem is not None and name_elem.text else ''

                matches = _coords_match(coord_lat, coord_lng, lat, lng, tolerance)
                if target_name:
                    matches = matches or (name_text == target_name)

                if matches:
                    parent.remove(placemark)
                    removed = True

        if removed:
            tree.write(caminho_kml, encoding='utf-8', xml_declaration=True)
        return removed
    except Exception as e:
        print(f"Erro ao remover CTO em KML {caminho_kml}: {e}")
        return False


def remover_cto_kmz(caminho_kmz, lat, lng, nome_cto=None, tolerance=1e-5):
    """Remove um CTO de um arquivo KMZ"""
    import tempfile
    import shutil

    try:
        temp_dir = tempfile.mkdtemp()
        with zipfile.ZipFile(caminho_kmz, 'r') as kmz:
            kmz.extractall(temp_dir)

        kml_file = None
        for arquivo in os.listdir(temp_dir):
            if arquivo.endswith('.kml'):
                kml_file = os.path.join(temp_dir, arquivo)
                break

        if not kml_file:
            shutil.rmtree(temp_dir)
            return False

        removed = remover_cto_kml(kml_file, lat, lng, nome_cto=nome_cto, tolerance=tolerance)
        if not removed:
            shutil.rmtree(temp_dir)
            return False

        with zipfile.ZipFile(caminho_kmz, 'w', zipfile.ZIP_DEFLATED) as kmz:
            for root_dir, dirs, files in os.walk(temp_dir):
                for file in files:
                    file_path = os.path.join(root_dir, file)
                    arcname = os.path.relpath(file_path, temp_dir)
                    kmz.write(file_path, arcname)

        shutil.rmtree(temp_dir)
        return True
    except Exception as e:
        print(f"Erro ao remover CTO em KMZ {caminho_kmz}: {e}")
        return False


def remover_cto_csv(caminho_csv, lat, lng, nome_cto=None, tolerance=1e-5):
    """Remove um CTO de um arquivo CSV"""
    try:
        with open(caminho_csv, 'r', encoding='utf-8') as f:
            sample = f.read(1024)
            f.seek(0)
            try:
                delimiter = csv.Sniffer().sniff(sample).delimiter if sample else ','
            except csv.Error:
                delimiter = ','
            reader = csv.DictReader(f, delimiter=delimiter)
            fieldnames = reader.fieldnames or []
            rows = list(reader)

        if not rows:
            return False

        lat_cols = [col for col in fieldnames if any(keyword in col.lower() for keyword in ['lat', 'latitude', 'y'])]
        lng_cols = [col for col in fieldnames if any(keyword in col.lower() for keyword in ['lng', 'lon', 'longitude', 'x'])]
        nome_cols = [col for col in fieldnames if any(keyword in col.lower() for keyword in ['nome', 'name', 'id', 'cto'])]

        if not lat_cols or not lng_cols:
            return False

        lat_col = lat_cols[0]
        lng_col = lng_cols[0]
        nome_col = nome_cols[0] if nome_cols else None
        target_name = nome_cto.strip().lower() if nome_cto else None

        filtered_rows = []
        removed = False

        for row in rows:
            row_lat = _normalize_decimal(row.get(lat_col))
            row_lng = _normalize_decimal(row.get(lng_col))
            match = _coords_match(row_lat, row_lng, lat, lng, tolerance)

            if target_name and nome_col:
                nome_val = str(row.get(nome_col, '')).strip().lower()
                match = match or (nome_val == target_name)

            if match:
                removed = True
                continue

            filtered_rows.append(row)

        if not removed:
            return False

        with open(caminho_csv, 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=delimiter)
            writer.writeheader()
            writer.writerows(filtered_rows)

        return True
    except Exception as e:
        print(f"Erro ao remover CTO em CSV {caminho_csv}: {e}")
        return False


def remover_cto_excel(caminho_excel, lat, lng, nome_cto=None, tolerance=1e-5):
    """Remove um CTO de um arquivo Excel"""
    try:
        df = pd.read_excel(caminho_excel)
    except Exception as e:
        print(f"Erro ao ler Excel {caminho_excel}: {e}")
        return False

    if df.empty:
        return False

    nome_cols = [col for col in df.columns if isinstance(col, str) and any(keyword in col.lower() for keyword in ['nome', 'name', 'id', 'cto'])]
    lat_cols = [col for col in df.columns if isinstance(col, str) and any(keyword in col.lower() for keyword in ['lat', 'latitude', 'y'])]
    lng_cols = [col for col in df.columns if isinstance(col, str) and any(keyword in col.lower() for keyword in ['lng', 'lon', 'longitude', 'x'])]

    if not lat_cols or not lng_cols:
        return False

    lat_col = lat_cols[0]
    lng_col = lng_cols[0]
    nome_col = nome_cols[0] if nome_cols else None
    target_name = nome_cto.strip().lower() if nome_cto else None

    def _row_match(row):
        row_lat = _normalize_decimal(row.get(lat_col))
        row_lng = _normalize_decimal(row.get(lng_col))
        match = _coords_match(row_lat, row_lng, lat, lng, tolerance)

        if target_name and nome_col:
            nome_val = row.get(nome_col)
            if pd.notna(nome_val):
                match = match or (str(nome_val).strip().lower() == target_name)
        return match

    mask = df.apply(_row_match, axis=1)
    if not mask.any():
        return False

    df = df[~mask]
    df.to_excel(caminho_excel, index=False)
    return True


def remover_cto_do_mapa(caminho_arquivo, lat, lng, nome_cto=None, file_type=None):
    """Remove um CTO de um arquivo de mapa baseado no tipo"""
    if not file_type:
        ext = os.path.splitext(caminho_arquivo)[1].lower().lstrip('.')
        file_type = ext

    file_type = (file_type or '').lower()

    if file_type == 'kml':
        return remover_cto_kml(caminho_arquivo, lat, lng, nome_cto=nome_cto)
    if file_type == 'kmz':
        return remover_cto_kmz(caminho_arquivo, lat, lng, nome_cto=nome_cto)
    if file_type == 'csv':
        return remover_cto_csv(caminho_arquivo, lat, lng, nome_cto=nome_cto)
    if file_type in ['xls', 'xlsx']:
        return remover_cto_excel(caminho_arquivo, lat, lng, nome_cto=nome_cto)

    print(f"Tipo de arquivo não suportado para remover CTO: {file_type}")
    return False

