# Configuração do Gunicorn para produção VPS
import multiprocessing
import os

# Diretório da aplicação
chdir = "/var/www/saas-viabilidade"

# Configuração do WSGI
wsgi_app = "saas_viabilidade.wsgi:application"

# Configuração de workers
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = "sync"
worker_connections = 1000
timeout = 120
keepalive = 5

# Configuração de logs
accesslog = "/var/log/gunicorn/access.log"
errorlog = "/var/log/gunicorn/error.log"
loglevel = "info"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# Configuração de segurança
bind = "127.0.0.1:8000"
backlog = 2048
max_requests = 1000
max_requests_jitter = 50
preload_app = True

# Configuração de usuário (será configurado pelo systemd)
# user = "appuser"
# group = "appuser"

# Configuração de threads (se usar worker_class = "gthread")
# threads = 2

def on_starting(server):
    """Callback quando o servidor inicia"""
    server.log.info("🚀 Servidor Gunicorn iniciando...")

def on_reload(server):
    """Callback quando o servidor recarrega"""
    server.log.info("🔄 Servidor Gunicorn recarregando...")

def worker_int(worker):
    """Callback quando um worker recebe SIGINT ou SIGQUIT"""
    worker.log.info("⚠️ Worker recebeu sinal de interrupção")

def pre_fork(server, worker):
    """Callback antes de criar um novo worker"""
    pass

def post_fork(server, worker):
    """Callback após criar um novo worker"""
    server.log.info(f"✅ Worker {worker.pid} criado")

def when_ready(server):
    """Callback quando o servidor está pronto para aceitar conexões"""
    server.log.info("✅ Servidor Gunicorn pronto para aceitar conexões")

def on_exit(server):
    """Callback quando o servidor encerra"""
    server.log.info("👋 Servidor Gunicorn encerrando...")

