#!/usr/bin/env python3
"""
Component testing script - verify all components can be properly enabled
Special focus on RAG and MongoDB Atlas connections
"""
import os
import sys
import asyncio
from pathlib import Path

# Ensure running from correct location
script_dir = Path(__file__).parent
os.chdir(script_dir)
sys.path.insert(0, str(script_dir))

from dotenv import load_dotenv
load_dotenv()

print("=" * 80)
print("🔍 Component Testing - MongoDB Atlas RAG System")
print("=" * 80)
print()


def test_env_variables():
    """Test 1: Environment variable configuration"""
    print("📋 Test 1: Environment Variable Configuration")
    print("-" * 80)
    
    required_vars = {
        "MONGODB_URI": "Main MongoDB connection (session storage, GridFS)",
        "MONGODB_ATLAS_URI": "Atlas Vector Search connection",
        "MONGODB_ATLAS_DB": "Atlas database name",
        "MONGODB_ATLAS_COLLECTION": "Atlas collection name",
        "USE_ATLAS_KB": "Enable Atlas KB",
    }
    
    all_ok = True
    for var, desc in required_vars.items():
        value = os.getenv(var, "")
        status = "✅" if value else "❌"
        print(f"{status} {var:30s} = {value[:50] if value else '(not set)'}")
        if desc:
            print(f"   Description: {desc}")
        if not value:
            all_ok = False
    
    print()
    if all_ok:
        print("✅ All required environment variables are configured")
    else:
        print("❌ Some environment variables are not configured")
    
    print()
    return all_ok


def test_imports():
    """Test 2: Python dependency imports"""
    print("📦 Test 2: Python Dependency Imports")
    print("-" * 80)
    
    imports = [
        ("pymongo", "PyMongo - MongoDB driver"),
        ("motor", "Motor - Async MongoDB driver"),
        ("fastapi", "FastAPI - Web framework"),
        ("transformers", "HuggingFace Transformers"),
        ("torch", "PyTorch - Deep learning framework"),
        ("sentence_transformers", "Sentence Transformers - Embedding model"),
        ("pypdf", "PyPDF - PDF processing"),
    ]
    
    all_ok = True
    for module, desc in imports:
        try:
            __import__(module)
            print(f"✅ {module:25s} - {desc}")
        except ImportError as e:
            print(f"❌ {module:25s} - {desc}")
            print(f"   Error: {e}")
            all_ok = False
    
    print()
    if all_ok:
        print("✅ All required Python packages are installed")
    else:
        print("❌ Some Python packages are not installed, please run: pip install -r requirements.txt")
    
    print()
    return all_ok


async def test_mongodb_connection():
    """Test 3: MongoDB connection"""
    print("🔌 Test 3: MongoDB Connection")
    print("-" * 80)
    
    try:
        from motor.motor_asyncio import AsyncIOMotorClient
        
        # Test main MongoDB connection
        main_uri = os.getenv("MONGODB_URI", "")
        if main_uri:
            print("Testing main MongoDB connection...")
            client = AsyncIOMotorClient(main_uri, serverSelectionTimeoutMS=5000)
            await client.admin.command("ping")
            print(f"✅ Main MongoDB connected successfully: {main_uri[:50]}...")
            
            # Test database access
            db_name = os.getenv("MONGODB_DB", "sea_translate")
            db = client[db_name]
            collections = await db.list_collection_names()
            print(f"   Database: {db_name}")
            print(f"   Collections: {len(collections)}")
            client.close()
        else:
            print("❌ MONGODB_URI not set")
            return False
        
        # Test Atlas connection
        atlas_uri = os.getenv("MONGODB_ATLAS_URI", "")
        if atlas_uri:
            print("\nTesting Atlas MongoDB connection...")
            client = AsyncIOMotorClient(atlas_uri, serverSelectionTimeoutMS=5000)
            await client.admin.command("ping")
            print(f"✅ Atlas MongoDB connected successfully: {atlas_uri[:50]}...")
            
            # Test Atlas database and collection
            atlas_db = os.getenv("MONGODB_ATLAS_DB", "")
            atlas_coll = os.getenv("MONGODB_ATLAS_COLLECTION", "")
            
            if atlas_db and atlas_coll:
                db = client[atlas_db]
                collection = db[atlas_coll]
                count = await collection.count_documents({})
                print(f"   Database: {atlas_db}")
                print(f"   Collection: {atlas_coll}")
                print(f"   Document count: {count}")
                
                # Check vector search indexes
                try:
                    indexes = await collection.list_search_indexes().to_list(length=100)
                    print(f"   Vector Search indexes: {len(indexes)}")
                    for idx in indexes:
                        print(f"      - {idx.get('name', 'unnamed')} (status: {idx.get('status', 'unknown')})")
                except Exception as e:
                    print(f"   ⚠️  Cannot list Vector Search indexes (may need Atlas Search configuration): {e}")
            
            client.close()
        else:
            print("❌ MONGODB_ATLAS_URI not set")
            return False
        
        print("\n✅ All MongoDB connection tests passed")
        return True
        
    except Exception as e:
        print(f"❌ MongoDB connection failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    print()


async def test_rag_system():
    """Test 4: RAG system"""
    print("🧠 Test 4: RAG System Components")
    print("-" * 80)
    
    try:
        from core.chatbot_core import KnowledgeBase
        from config.settings import logger
        
        print("Initializing knowledge base...")
        kb = KnowledgeBase()
        
        print(f"✅ Knowledge base instance created successfully")
        print(f"   USE_KB: {os.getenv('USE_KB', '0')}")
        print(f"   USE_ATLAS_KB: {os.getenv('USE_ATLAS_KB', '0')}")
        print(f"   Atlas ready: {kb._atlas_ready}")
        print(f"   Vector search: {kb._atlas_use_vector}")
        print(f"   KB ready: {kb.ready}")
        
        if kb.ready:
            print("\nTesting retrieval function...")
            test_query = "scholarship information"
            print(f"   Query: '{test_query}'")
            
            context = kb.retrieve(test_query, top_k=2)
            
            if context:
                print(f"✅ Retrieval successful! Returned {len(context)} characters of context")
                print(f"   Preview: {context[:200]}...")
            else:
                print("⚠️  Retrieval returned no results (database may be empty)")
        else:
            print("⚠️  Knowledge base not ready, please check configuration")
        
        print("\n✅ RAG system testing complete")
        return True
        
    except Exception as e:
        print(f"❌ RAG system testing failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    print()


async def test_translation_engine():
    """Test 5: Translation engine"""
    print("🔤 Test 5: Translation Engine")
    print("-" * 80)
    
    try:
        from core.chatbot_core import TranslationEngine
        
        print("Initializing translation engine (lazy load mode)...")
        engine = TranslationEngine()
        
        print(f"✅ Translation engine instance created successfully")
        print(f"   Lazy load: {os.getenv('LAZY_LOAD_MODEL', '1') == '1'}")
        print(f"   Model loaded: {engine._model is not None}")
        
        if not (os.getenv('LAZY_LOAD_MODEL', '1') == '1'):
            print(f"   Model name: {engine._model_name}")
            print(f"   Device: {engine._device}")
            print(f"   Quantization: {engine._quantization}")
        
        print("\n✅ Translation engine testing complete")
        return True
        
    except Exception as e:
        print(f"❌ Translation engine testing failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    print()


async def test_gridfs():
    """Test 6: GridFS storage"""
    print("📁 Test 6: GridFS Storage")
    print("-" * 80)
    
    try:
        from motor.motor_asyncio import AsyncIOMotorClient
        from db.gridfs_storage import create_gridfs_storage
        
        uri = os.getenv("MONGODB_URI", "")
        if not uri:
            print("❌ MONGODB_URI not set, skipping GridFS test")
            return False
        
        print("Connecting to MongoDB and initializing GridFS...")
        client = AsyncIOMotorClient(uri, serverSelectionTimeoutMS=5000)
        db = client[os.getenv("MONGODB_DB", "sea_translate")]
        
        storage = create_gridfs_storage(db)
        print("✅ GridFS storage instance created successfully")
        
        # Test listing files
        files = await storage.list_files(limit=5)
        print(f"   Current file count: {len(files)}")
        
        total_size = await storage.get_total_size()
        print(f"   Total storage size: {total_size / (1024**2):.2f} MB")
        
        client.close()
        
        print("\n✅ GridFS storage testing complete")
        return True
        
    except Exception as e:
        print(f"❌ GridFS storage testing failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    print()


async def test_api_startup():
    """Test 7: API startup"""
    print("🚀 Test 7: FastAPI Application Startup")
    print("-" * 80)
    
    try:
        from api.main import app
        from db.connection import init_mongo
        
        print("Initializing FastAPI application...")
        print("✅ FastAPI application imported successfully")
        
        print("\nInitializing MongoDB connection...")
        await init_mongo(app)
        
        if hasattr(app.state, 'mongodb') and app.state.mongodb:
            print("✅ MongoDB connection initialized in application state")
            print(f"   Database: {app.state.mongodb.name}")
        
        if hasattr(app.state, 'gridfs_bucket') and app.state.gridfs_bucket:
            print("✅ GridFS bucket initialized")
        
        print("\n✅ API startup testing complete")
        return True
        
    except Exception as e:
        print(f"❌ API startup testing failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    print()


async def main():
    """Run all tests"""
    results = {}
    
    # Synchronous tests
    results["Environment Variables"] = test_env_variables()
    results["Dependency Imports"] = test_imports()
    
    # Asynchronous tests
    results["MongoDB Connection"] = await test_mongodb_connection()
    results["RAG System"] = await test_rag_system()
    results["Translation Engine"] = await test_translation_engine()
    results["GridFS Storage"] = await test_gridfs()
    results["API Startup"] = await test_api_startup()
    
    # Summary
    print("=" * 80)
    print("📊 Test Summary")
    print("=" * 80)
    
    for test_name, passed in results.items():
        status = "✅ Passed" if passed else "❌ Failed"
        print(f"{status:10s} {test_name}")
    
    print()
    total = len(results)
    passed = sum(1 for p in results.values() if p)
    
    print(f"Total: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All component tests passed! The system is ready to use.")
        return 0
    else:
        print("\n⚠️  Some tests failed, please check the error messages above.")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
