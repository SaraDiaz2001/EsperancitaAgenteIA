from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from modules.logger import logger
import os

# Variables globales para embeddings y ChromaDB
embeddings = None
vectorstore = None

def get_vectorstore():
    """Carga el modelo de embeddings y devuelve la base de datos vectorial."""
    global embeddings, vectorstore
    if vectorstore is not None:
        return vectorstore  # Si ya está creado, lo reutilizamos

    try:
        if embeddings is None:
            logger.info("🔄 Cargando modelo de embeddings...")  
            embeddings = HuggingFaceEmbeddings(model_name="jinaai/jina-embeddings-v2-base-es")

        vectorstore = Chroma(persist_directory="./chroma_db", embedding_function=embeddings)
        logger.info("✅ Base de datos vectorial cargada correctamente.")
        return vectorstore
    except Exception as e:
        logger.error(f"❌ Error al cargar el modelo de embeddings o ChromaDB: {e}")
        return None

def get_existing_document_ids():
    """Recupera los IDs de los documentos ya indexados en ChromaDB."""
    if vectorstore is None:
        get_vectorstore()
    
    try:
        return set(vectorstore.get()['ids'])  # Obtenemos los IDs de los documentos almacenados
    except Exception as e:
        logger.error(f"❌ Error al obtener documentos existentes de ChromaDB: {e}")
        return set()

def update_vectorstore(new_docs):
    """Solo actualiza ChromaDB si hay documentos nuevos."""
    global vectorstore
    if vectorstore is None:
        vectorstore = get_vectorstore()

    if new_docs:
        vectorstore.add_documents(new_docs)
        logger.info(f"📄 {len(new_docs)} nuevos documentos indexados en ChromaDB.")





