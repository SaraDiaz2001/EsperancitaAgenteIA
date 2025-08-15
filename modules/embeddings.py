import os
from langchain_community.document_loaders import TextLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from modules.database import update_vectorstore, get_existing_document_ids
import logging
from langchain.schema import Document

logger = logging.getLogger(__name__)

def load_and_store_documents(file_content, file_name):
    """Carga un documento, lo divide en chunks y lo almacena en ChromaDB."""
    try:
        file_path = f"data/documentos/{file_name}"
        
        # Asegurar que la carpeta existe
        os.makedirs(os.path.dirname(file_path), exist_ok=True)

        # Guardar el archivo en disco
        with open(file_path, "wb") as f:
            f.write(file_content.getbuffer())

        # Verificamos si el documento ya fue indexado
        existing_docs = get_existing_document_ids()
        if file_name in existing_docs:
            logger.info(f"⚠️ El documento {file_name} ya está indexado. Se omite.")
            return

        logger.info(f"📂 Cargando archivo: {file_path}")

        # 🔍 Intentar abrir el archivo en modo lectura antes de cargarlo
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                contenido = f.read()
            logger.info(f"✅ Archivo '{file_name}' cargado correctamente.\nContenido:\n{contenido[:500]}")  # Muestra solo los primeros 500 caracteres
        except Exception as e:
            logger.error(f"❌ Error al leer '{file_name}': {e}")
            return  # 🔴 Si no se puede leer, detenemos el proceso

             # Cargar documento manualmente
        with open(file_path, "r", encoding="utf-8") as f:
            contenido = f.read()

        # Crear un "documento" manualmente para simular lo que haría TextLoader
        documents = [Document(page_content=contenido, metadata={"source": file_path})]


        logger.info(f"📄 Documentos cargados: {len(documents)}")

        # Dividir en chunks
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
        docs = text_splitter.split_documents(documents)

        logger.info(f"🔍 Chunks generados: {len(docs)}")

        update_vectorstore(docs)  # 🚀 SOLO SE ACTUALIZA AQUÍ CUANDO SE SUBE UN DOCUMENTO
        logger.info(f"✅ Documentos indexados: {len(docs)}")

    except FileNotFoundError:
        logger.error(f"❌ Archivo no encontrado: {file_path}")
    except PermissionError:
        logger.error(f"❌ Permiso denegado para leer el archivo: {file_path}")
    except Exception as e:
        logger.error(f"❌ Error desconocido al cargar {file_name}: {e}")






    