from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import yt_dlp
import os
import tempfile
import uuid
import shutil
from werkzeug.utils import secure_filename
import threading
import time
import logging

app = Flask(__name__)
CORS(app)  # Permitir CORS para el frontend

# Configuración de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Directorio temporal para descargas
TEMP_DIR = tempfile.mkdtemp()

# Diccionario para trackear progreso de descargas
download_progress = {}


class ProgressHook:
    def __init__(self, download_id):
        self.download_id = download_id

    def __call__(self, d):
        if d['status'] == 'downloading':
            try:
                percent = d.get('_percent_str', '0%').replace('%', '')
                download_progress[self.download_id] = {
                    'status': 'downloading',
                    'progress': float(percent),
                    'speed': d.get('_speed_str', ''),
                    'eta': d.get('_eta_str', '')
                }
            except (ValueError, KeyError):
                pass
        elif d['status'] == 'finished':
            download_progress[self.download_id] = {
                'status': 'finished',
                'progress': 100,
                'filename': d['filename']
            }


def get_video_info(url):
    """Obtener información del video sin descargarlo"""
    try:
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            return {
                'title': info.get('title', 'Unknown'),
                'duration': info.get('duration', 0),
                'uploader': info.get('uploader', 'Unknown'),
                'view_count': info.get('view_count', 0),
                'thumbnail': info.get('thumbnail', ''),
                'formats': len(info.get('formats', []))
            }
    except Exception as e:
        logger.error(f"Error getting video info: {str(e)}")
        return None


def download_video(url, quality, download_id, output_path):
    """Función para descargar video en background"""
    try:
        # Configurar opciones de descarga según la calidad
        format_selector = {
            'best': 'best',
            'worst': 'worst',
            'bestvideo+bestaudio': 'bestvideo+bestaudio/best',
            '720p': 'best[height<=720]',
            '480p': 'best[height<=480]'
        }.get(quality, 'best')

        ydl_opts = {
            'format': format_selector,
            'outtmpl': output_path,
            'progress_hooks': [ProgressHook(download_id)],
            'quiet': True,
            'no_warnings': True,
            'extractaudio': False,
            'audioformat': 'mp3',
            'embed_subs': False,
            'writesubtitles': False,
            'writeautomaticsub': False,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

    except Exception as e:
        logger.error(f"Error downloading video: {str(e)}")
        download_progress[download_id] = {
            'status': 'error',
            'error': str(e)
        }


@app.route('/')
def home():
    return jsonify({
        'message': 'Video Downloader API',
        'version': '1.0.0',
        'endpoints': {
            'POST /download': 'Descargar video',
            'GET /info': 'Obtener información del video',
            'GET /progress/<download_id>': 'Obtener progreso de descarga'
        }
    })


@app.route('/info', methods=['GET'])
def video_info():
    """Endpoint para obtener información del video"""
    url = request.args.get('url')
    if not url:
        return jsonify({'error': 'URL requerida'}), 400

    info = get_video_info(url)
    if info:
        return jsonify(info)
    else:
        return jsonify({'error': 'No se pudo obtener información del video'}), 400


@app.route('/download', methods=['POST'])
def download():
    """Endpoint principal para descargar videos"""
    try:
        data = request.get_json()
        url = data.get('url')
        quality = data.get('quality', 'best')

        if not url:
            return jsonify({'error': 'URL requerida'}), 400

        # Generar ID único para la descarga
        download_id = str(uuid.uuid4())

        # Crear directorio temporal para esta descarga
        download_dir = os.path.join(TEMP_DIR, download_id)
        os.makedirs(download_dir, exist_ok=True)

        # Nombre del archivo de salida
        output_path = os.path.join(download_dir, f'video_{download_id}.%(ext)s')

        # Inicializar progreso
        download_progress[download_id] = {
            'status': 'starting',
            'progress': 0
        }

        # Iniciar descarga en background
        thread = threading.Thread(
            target=download_video,
            args=(url, quality, download_id, output_path)
        )
        thread.daemon = True
        thread.start()

        # Esperar un poco para que inicie la descarga
        time.sleep(2)

        # Buscar el archivo descargado
        downloaded_files = []
        for file in os.listdir(download_dir):
            if file.startswith(f'video_{download_id}'):
                downloaded_files.append(os.path.join(download_dir, file))

        if downloaded_files:
            file_path = downloaded_files[0]

            # Leer el archivo y enviarlo
            def remove_file():
                time.sleep(60)  # Esperar 1 minuto antes de eliminar
                try:
                    shutil.rmtree(download_dir)
                except:
                    pass

            # Programar eliminación del archivo
            cleanup_thread = threading.Thread(target=remove_file)
            cleanup_thread.daemon = True
            cleanup_thread.start()

            # Determinar el tipo de contenido
            if file_path.endswith('.mp4'):
                mimetype = 'video/mp4'
            elif file_path.endswith('.webm'):
                mimetype = 'video/webm'
            elif file_path.endswith('.mkv'):
                mimetype = 'video/x-matroska'
            else:
                mimetype = 'application/octet-stream'

            return send_file(
                file_path,
                as_attachment=True,
                download_name=f'video_{int(time.time())}.{file_path.split(".")[-1]}',
                mimetype=mimetype
            )
        else:
            return jsonify({'error': 'Error al descargar el archivo'}), 500

    except Exception as e:
        logger.error(f"Error in download endpoint: {str(e)}")
        return jsonify({'error': f'Error interno del servidor: {str(e)}'}), 500


@app.route('/progress/<download_id>', methods=['GET'])
def get_progress(download_id):
    """Endpoint para obtener el progreso de una descarga"""
    progress = download_progress.get(download_id, {'status': 'not_found'})
    return jsonify(progress)


@app.route('/health', methods=['GET'])
def health_check():
    """Endpoint de verificación de salud"""
    return jsonify({
        'status': 'healthy',
        'timestamp': time.time(),
        'temp_dir': TEMP_DIR,
        'active_downloads': len(download_progress)
    })


# Limpiar archivos temporales al iniciar
def cleanup_temp_files():
    """Limpiar archivos temporales antiguos"""
    try:
        if os.path.exists(TEMP_DIR):
            for item in os.listdir(TEMP_DIR):
                item_path = os.path.join(TEMP_DIR, item)
                if os.path.isdir(item_path):
                    shutil.rmtree(item_path)
                else:
                    os.remove(item_path)
        logger.info("Archivos temporales limpiados")
    except Exception as e:
        logger.error(f"Error limpiando archivos temporales: {str(e)}")


# Limpiar archivos temporales cada hora
def periodic_cleanup():
    while True:
        time.sleep(3600)  # 1 hora
        cleanup_temp_files()


if __name__ == '__main__':
    # Iniciar limpieza periódica
    cleanup_thread = threading.Thread(target=periodic_cleanup)
    cleanup_thread.daemon = True
    cleanup_thread.start()

    # Limpiar archivos temporales al inicio
    cleanup_temp_files()

    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)